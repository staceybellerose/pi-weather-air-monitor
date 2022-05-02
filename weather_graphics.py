import json
from datetime import datetime
from typing import Callable, Any

import board
import busio
import digitalio
from PIL import Image, ImageDraw, ImageFont
from adafruit_epd.epd import Adafruit_EPD
from adafruit_epd.ssd1680 import Adafruit_SSD1680

from aio_logger import AIO_Logger
from eprint import eprint
from buzzer_alarm import sound_the_alarm

_NORMAL_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_BOLD_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_WEATHER_FONT = "/usr/share/fonts/truetype/meteocons/meteocons.ttf"

IAQ_SAMPLES = 15  # number of samples between Adafruit.IO writes

alert_font = ImageFont.truetype(_BOLD_FONT, 10)
tiny_font = ImageFont.truetype(_BOLD_FONT, 12)
small_font = ImageFont.truetype(_BOLD_FONT, 16)
small_label_font = ImageFont.truetype(_BOLD_FONT, 14)
medium_font = ImageFont.truetype(_NORMAL_FONT, 20)
medium_b_font = ImageFont.truetype(_BOLD_FONT, 20)
large_font = ImageFont.truetype(_BOLD_FONT, 24)
label_font = ImageFont.truetype(_NORMAL_FONT, 24)
icon_font = ImageFont.truetype(_WEATHER_FONT, 48)

# Map the OpenWeatherMap icon code to the appropriate Meteocons font
# character. See http://www.alessioatzeni.com/meteocons/ for icons.
ICON_MAP = {
    "01d": "B", "01n": "C",
    "02d": "H", "02n": "I",
    "03d": "N", "03n": "5",
    "04d": "Y", "04n": "%",
    "09d": "Q", "09n": "7",
    "10d": "R", "10n": "8",
    "11d": "Z", "11n": "&",
    "13d": "W", "13n": "#",
    "50d": "J", "50n": "K",
}

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ALERT_ICON = "⚠"


class Forecast:
    def __init__(self):
        self.temprange: str = None
        self.date: float = None
        self.dow: str = None
        self.text: str = None
        self.icon: str = None
        self.pop: str = None


class Weather_Graphics:
    def __init__(self, *, am_pm=False, celsius=True):
        """
        Parameters
        ----------
        am_pm: Flag indicating whether to display 12-hour clock with AM/PM;
            if False, use 24-hour clock.
        celsius: Flag indicating whether Celsius should be displayed;
            if False, use Fahrenheit.
        """
        # initialize the display
        self.display = Adafruit_SSD1680(
            122, 250, busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO),
            cs_pin=digitalio.DigitalInOut(board.CE0),
            dc_pin=digitalio.DigitalInOut(board.D22),
            sramcs_pin=None,
            rst_pin=digitalio.DigitalInOut(board.D27),
            busy_pin=digitalio.DigitalInOut(board.D17)
        )
        self.display.rotation = 1

        self.am_pm = am_pm
        self.celsius = celsius
        self.timeformat = "%I:%M %p" if self.am_pm else "%H:%M"

        self._forecast: list[Forecast] = []
        self._weather_icon = None
        self._locality = None
        self._main_text = None
        self._temperature = None
        self._description = None
        self._time_text = None
        self._iaq_temperature = None
        self._iaq_pressure = None
        self._iaq_humidity = None
        self._iaq_quality = None
        self._iaq_time = None
        self._iaq_log_time = 0
        self._alert_event = None
        self._alert_description = None

    @property
    def locality(self):
        return self._locality

    @locality.setter
    def locality(self, value):
        self._locality = value

    def initialize_aio(self, aio_user, aio_key):
        """
        Initialize the Adafruit.IO API Client.

        Parameters
        ----------
        aio_user: Username for Adafruit.IO.
        aio_key: Authentication Key for Adafruit.IO.
        """
        self.aio_logger = AIO_Logger(aio_user, aio_key)

    def get_icon(self, code):
        """
        Convert weather code from OpenWeather to Meteocons weather icon.
        """
        return ICON_MAP[code]

    def has_alert(self):
        """
        Return True if there is a current weather alert; False otherwise.
        """
        return self._alert_event is not None

    def c_to_f(temperature: float) -> float:
        """
        Convert Celsius temperature to Fahrenheit.
        """
        return (temperature * 9 / 5) + 32

    def format_temperature(self, temperature: float) -> str:
        """
        Format a numeric temperature to a string, converting if needed.
        """
        if self.celsius:
            return "%d°C" % temperature
        else:
            return "%d°F" % self.c_to_f(temperature)

    def format_temp_range(self, min: float, max: float) -> str:
        """
        Format a temperature range to a string, converting if needed.
        """
        if self.celsius:
            return "%d\N{EN DASH}%d°C" % (min, max)
        else:
            return "%d\N{EN DASH}%d°F" % (self.c_to_f(min), self.c_to_f(max))

    async def update_weather(self, weather_json: str):
        """
        Update weather data used for display.

        Parameters
        ----------
        weather_json: string containing JSON object of weather data.
        """
        weather = json.loads(weather_json.decode("utf-8"))
        self._weather_icon = self.get_icon(weather["current"]["weather"][0]["icon"])
        self._main_text = weather["current"]["weather"][0]["main"]
        description:str = weather["current"]["weather"][0]["description"]
        description = description[:1].upper() + description[1:].lower()
        self._description = description  # example: "light rain"
        self._temperature = self.format_temperature(weather["current"]["temp"])
        previous_alert = self._alert_event
        if "alerts" in weather:
            self._alert_event = weather["alerts"][0]["event"].replace(" ", "\n")
            self._alert_description = weather["alerts"][0]["description"]
        else:
            self._alert_event = None
            self._alert_description = None
        self.update_time()
        self.update_forecast(weather["daily"])
        if previous_alert is None and self._alert_event is not None:
            eprint("NEW WEATHER ALERT RECEIVED")
            await sound_the_alarm()

    def update_time(self):
        """
        Update the time used for the display.
        """
        now = datetime.now()
        self._time_text = now.strftime(self.timeformat)

    def update_forecast(self, daily):
        """
        Update weather forecast data.

        Parameters
        ----------
        daily: deserialized JSON daily weather forecast data.
        """
        self._forecast = []
        for day in daily:
            forecast = Forecast()
            min = day["temp"]["min"]
            max = day["temp"]["max"]
            forecast.temprange = self.format_temp_range(min, max)
            forecast.date = float(day["dt"])
            forecast.dow = datetime.fromtimestamp(float(day["dt"])).strftime("%a")
            if day["weather"][0]["main"].lower() == "thunderstorm":
                forecast.text = "Storm"
            else:
                forecast.text = day["weather"][0]["main"]
            forecast.icon = self.get_icon(day["weather"][0]["icon"])
            forecast.pop = "%d%%" % (day["pop"] * 100)
            self._forecast.append(forecast)
        if datetime.now().hour > 12:  # remove today's forecast if after noon
            self._forecast.pop(0)

    def update_iaq(self, data):
        """
        Capture the current IAQ data for display and logging.

        Parameters
        ----------
        data: A pipe-delimited string containing the IAQ data.
        """
        if not "|" in data:
            eprint("Invalid data format (missing pipe)", data)
            return
        (timestamp, temperature, pressure, humidity, _gas, iaq) = data.split("|")
        timer = float(timestamp)
        self._iaq_temperature = self.format_temperature(float(temperature))
        self._iaq_pressure = pressure
        self._iaq_humidity = humidity
        self._iaq_quality = iaq
        self._iaq_time = datetime.fromtimestamp(timer).strftime(self.timeformat)
        if timer > self._iaq_log_time + IAQ_SAMPLES and self.aio_logger is not None:
            # Log the current IAQ data to Adafruit IO
            self._iaq_log_time = timer
            self.aio_logger.log(
                temperature,
                humidity.rstrip("%"),
                pressure,
                iaq
            )

    async def update_display(self, draw_function: Callable[[Any], None]):
        """
        Coroutine to update the e-ink display based on draw_function.

        Parameters
        ----------
        draw_function: a function that takes an ImageDraw object and
            draws the appropriate weather data on it for display.
        """
        self.display.fill(Adafruit_EPD.WHITE)
        image = Image.new(
            "RGB",
            (self.display.width, self.display.height),
            color=WHITE
        )
        draw = ImageDraw.Draw(image)

        await draw_function(draw) # call the function that does the actual drawing

        self.display.image(image)
        self.display.display()

    async def update_weather_display(self):
        """
        Coroutine to display current weather data on the e-ink display.
        """
        await self.update_display(self.draw_weather)

    async def update_forecast_display(self):
        """
        Coroutine to display 3 days of Forecast data on the e-ink display.
        """
        await self.update_display(self.draw_forecast)

    async def update_alert_display(self):
        """
        Coroutine to display Weather Alert data on the e-ink display.
        """
        await self.update_display(self.draw_alert)

    async def update_iaq_display(self):
        """
        Coroutine to display current IAQ data on the e-ink display.
        """
        await self.update_display(self.draw_iaq)

    async def draw_weather(self, draw):
        """
        Coroutine to draw the weather data on the draw buffer.

        Parameters
        ----------
        draw: an ImageDraw object set up to draw on the display.
        """
        # Draw the icon
        draw.text(
            (self.display.width // 2, self.display.height // 2),
            self._weather_icon,
            font=icon_font,
            fill=BLACK,
            anchor="mm"
        )
        # Draw the city
        draw.text(
            (5, 5),
            self.locality,
            font=medium_font,
            fill=BLACK,
            anchor="la"
        )
        # Draw the time
        (_, font_height) = medium_font.getsize(self._time_text)
        draw.text(
            (5, font_height * 2 - 5),
            self._time_text,
            font=medium_font,
            fill=BLACK,
            anchor="la"
        )
        # Draw the main text
        (_, font_height) = large_font.getsize(self._main_text)
        draw.text(
            (5, self.display.height - font_height * 2),
            self._main_text,
            font=large_font,
            fill=BLACK,
            anchor="la"
        )
        # Draw the description
        draw.text(
            (5, self.display.height - 5),
            self._description,
            font=small_font,
            fill=BLACK,
            anchor="lb"
        )
        # Draw the temperature
        draw.text(
            (self.display.width - 5, self.display.height - 5),
            self._temperature,
            font=large_font,
            fill=BLACK,
            anchor="rb"
        )
        # Draw the alert, if any
        if self._alert_event is not None:
            (_, icon_font_height) = large_font.getsize(ALERT_ICON)
            draw.text(
                (self.display.width - 5, 0),
                ALERT_ICON,
                font=large_font,
                fill=BLACK,
                anchor="rt"
            )
            (font_width, _) = small_label_font.getsize_multiline(self._alert_event)
            draw.multiline_text(
                (self.display.width - font_width - 5, icon_font_height + 2),
                self._alert_event,
                font=small_label_font,
                fill=BLACK,
                align="right"
            )

    async def draw_forecast(self, draw):
        """
        Coroutine to draw the forecast data on the draw buffer.

        Parameters
        ----------
        draw: an ImageDraw object set up to draw on the display.
        """
        xpos = [40, self.display.width // 2, self.display.width - 40]
        for i in range(3):
            forecast = self._forecast[i]
            # Draw the day of the week
            draw.text(
                (xpos[i], 5),
                forecast.dow,
                font=medium_font,
                fill=BLACK,
                anchor="ma"
            )
            # Draw the temperature range
            draw.text(
                (xpos[i], 30),
                forecast.temprange,
                font=small_font,
                fill=BLACK,
                anchor="ma"
            )
            # Draw the forecast text
            draw.text(
                (xpos[i], 45),
                forecast.text,
                font=medium_b_font,
                fill=BLACK,
                anchor="ma"
            )
            # Draw the icon
            draw.text(
                (xpos[i], 70),
                forecast.icon,
                font=icon_font,
                fill=BLACK,
                anchor="ma"
            )
            # Draw the probability of precipitation
            if forecast.pop is not None:
                y = 79 if forecast.icon in ["Q", "R", "W", "7", "8", "#"] else 88
                fill = BLACK if forecast.icon in ["Q", "R", "W", "Z"] else WHITE
                if forecast.icon in ["Q", "R", "W", "Z", "7", "8", "#", "&"]:
                    draw.text(
                        (xpos[i], y),
                        forecast.pop,
                        font=tiny_font,
                        fill=fill,
                        anchor="ma"
                    )

    async def draw_alert(self, draw):
        """
        Coroutine to draw the alert data on the draw buffer.

        Parameters
        ----------
        draw: an ImageDraw object set up to draw on the display.
        """
        # Draw the alert text
        event = self._alert_event.replace("\n", " ")
        (_, font_height) = medium_b_font.getsize(event)
        draw.text(
            (5, 5),
            event,
            font=medium_b_font,
            fill=BLACK,
            anchor="lt"
        )
        # Draw the alert icon
        draw.text(
            (self.display.width - 5, 0),
            ALERT_ICON,
            font=large_font,
            fill=BLACK,
            anchor="rt"
        )
        # Draw the alert description
        draw.multiline_text(
            (5, font_height + 5),
            self._alert_description,
            font=alert_font,
            fill=BLACK,
            spacing=3
        )

    async def draw_iaq(self, draw):
        """
        Coroutine to draw the IAQ data on the draw buffer.

        Parameters
        ----------
        draw: an ImageDraw object set up to draw on the display.
        """
        # Draw the label
        draw.text(
            (5, self.display.height - 3),
            "Internal Air Quality Monitor",
            font=small_label_font,
            fill=BLACK,
            anchor="lb"
        )
        # Draw the time
        (_, time_font_height) = small_font.getsize(self._iaq_time)
        draw.text(
            (self.display.width - 3, 5),
            self._iaq_time,
            font=small_font,
            fill=BLACK,
            anchor="ra"
        )
        # Draw the IAQ - left justified
        (_, font_height) = large_font.getsize(self._iaq_quality)
        label_y = time_font_height * 2 + 5
        data_y = label_y + font_height + 2
        draw.text(
            (3, data_y),
            self._iaq_quality,
            font=large_font,
            fill=BLACK,
            anchor="la"
        )
        # Draw the IAQ label - left justified
        draw.text((3, label_y), "IAQ", font=label_font, fill=BLACK, anchor="la")
        # Draw the relative humidity - centered
        draw.text(
            (self.display.width // 2, data_y),
            self._iaq_humidity,
            font=large_font,
            fill=BLACK,
            anchor="ma"
        )
        # Draw the relative humidity label - centered
        draw.text(
            (self.display.width // 2, label_y),
            "RH%",
            font=label_font,
            fill=BLACK,
            anchor="ma"
        )
        # Draw the temperature - right justified
        draw.text(
            (self.display.width - 3, data_y),
            self._iaq_temperature,
            font=large_font,
            fill=BLACK,
            anchor="ra"
        )
        # Draw the temperature label - right justified
        draw.text(
            (self.display.width - 3, label_y),
            "TEMP",
            font=label_font,
            fill=BLACK,
            anchor="ra"
        )
