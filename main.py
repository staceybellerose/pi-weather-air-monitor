import sys
import os.path
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime

import board
import digitalio

from weather_graphics import Weather_Graphics
from settings import Settings
from eprint import eprint

FORECAST_URL = "http://api.openweathermap.org/data/2.5/onecall"
GEOCODING_URL = "http://api.positionstack.com/v1/forward"
DEBOUNCE_DELAY = 0.3
WEATHER_REFRESH = 1800 # 30 minutes
SCREEN_REFRESH = WEATHER_REFRESH / 2 # 15 minutes

# C application to read IAQ from BME680 sensor
BME680_READER_PATH = './bsec/reader'

DISPLAY_WEATHER = "weather"
DISPLAY_IAQ = "iaq"
DISPLAY_FORECAST = "forecast"
DISPLAY_ALERT = "alert"

settings = Settings('config.ini')
settings.dump()
gfx = Weather_Graphics(am_pm=settings.am_pm, celsius=settings.celsius)
gfx.initialize_aio(settings.adafruit_username, settings.adafruit_key)
current_screen = settings.starting_screen
has_sensor_reader = os.path.isfile(BME680_READER_PATH)

# Make the geocoding api call
def geocode(query: str, country: str, token: str):
    """
    Call the geocoding API endpoint from postitionstack.com and
    return the location of the sent query.

    Parameters
    ----------
    query: Free-form location query (e.g. address, zip/postal code,
        city name, region name).
    country: Country code used to filter geocoding results;
        either a 2-letter or 3-letter ISO-3166 Country Code.
    token: Your postitionstack API access key.

    Returns
    -------
    A tuple containing latitude, longitude, and locality name.
    """
    params = {"access_key": token, "query": query, "country": country}
    geocoding_source = GEOCODING_URL + "?" + urllib.parse.urlencode(params)
    locality = None
    response = urllib.request.urlopen(geocoding_source)
    if response.getcode() == 200:
        value = response.read()
        data = json.loads(value.decode("utf-8"))["data"][0]
        latitude = data["latitude"]
        longitude = data["longitude"]
        locality = data["locality"]
        eprint("Geocoding lookup sucessful:", locality)
        eprint("Latitude:", latitude, "Longitude:", longitude)
    else:
        raise RuntimeError(
            "Unable to retrieve geocoding data at {}".format(geocoding_source)
        )
    return (latitude, longitude, locality)

async def download_weather(latitude, longitude, token, lock: asyncio.Lock):
    """
    Coroutine to download weather data every WEATHER_REFRESH seconds.

    (WEATHER_REFRESH should be set to at least 30 minutes).

    Parameters
    ----------
    latitude: The latitude of the location.
    longitude: The longitude of the location.
    locality: The name of the location (used for display).
    token: Your OpenWeather API key.
    lock: An asyncio lock, used to synchronize screen updates and
        weather downloads.
    """
    params = {
        "lat": latitude,
        "lon": longitude,
        "exclude": "minutely,hourly",
        "units": "metric",
        "appid": token
    }
    forecast_source = FORECAST_URL + "?" + urllib.parse.urlencode(params)
    while True:
        async with lock:
            eprint("Updating weather at", datetime.now().strftime("%I:%M %p"))
            response = urllib.request.urlopen(forecast_source)
            if response.getcode() == 200:
                forecast_data = response.read()
                eprint("Weather data retrieved")
                await gfx.update_weather(forecast_data)
            else:
                eprint("Unable to retrieve data at %s" % forecast_source)
        await asyncio.sleep(WEATHER_REFRESH)

async def handle_sensor():
    """
    Coroutine to handle a BME680 sensor, connected via I2C.

    The actual reading of the sensor is handled by a C program,
    to access the IAQ data. This function starts the C program
    as a subprocess and reads its output.
    """
    if not has_sensor_reader:
        eprint("Unable to find sensor reader application! Skipping sensor data.")
        return
    while True:
        # Set up a subprocess to read from the BME680.This is
        # embedded in a while True loop so that if the sensor
        # process is terminated, it will be restarted.
        eprint("Initializing BME680 sensor")
        process = await asyncio.create_subprocess_exec(
            BME680_READER_PATH,
            stdout=asyncio.subprocess.PIPE
        )
        # read and ignore the header line
        _bme680_header = await process.stdout.readline()
        while process.returncode is None:
            line = await process.stdout.readline()
            bme680_data = line.decode().strip()
            if '|' in bme680_data:
                gfx.update_iaq(bme680_data)
        # read data left after process was terminated
        (stdout_data, _) = await process.communicate()
        for line in stdout_data.decode().split("\n"):
            bme680_data = line.strip()
            if '|' in bme680_data:
                gfx.update_iaq(bme680_data)

async def handle_button(lock: asyncio.Lock):
    """
    Coroutine to process button presses.

    Parameters
    ----------
    lock: An asyncio lock, used to synchronize screen updates and
        weather downloads.
    """
    global current_screen
    # screenprinting on Adafruit 2.13" e-Ink board is incorrect.
    # The labels for GPIO 5 and 6 are swapped.
    up_button = digitalio.DigitalInOut(board.D6)
    up_button.switch_to_input()
    down_button = digitalio.DigitalInOut(board.D5)
    down_button.switch_to_input()
    await asyncio.sleep(1)
    eprint("Handling buttons")
    while True:
        up_pressed = not up_button.value
        down_pressed = not down_button.value
        if up_pressed or down_pressed:
            eprint("Detected button press")
            await asyncio.sleep(DEBOUNCE_DELAY)
        if up_pressed and has_sensor_reader:
            # display IAQ
            async with lock:
                current_screen = DISPLAY_IAQ
                eprint("Updating display to show IAQ")
                await gfx.update_iaq_display()
        elif down_pressed and (
            current_screen == DISPLAY_WEATHER and gfx.has_alert()
        ):
            # display the alert
            async with lock:
                current_screen = DISPLAY_ALERT
                eprint("Updating display to show alert")
                await gfx.update_alert_display()
        elif down_pressed and (
            current_screen == DISPLAY_WEATHER or current_screen == DISPLAY_ALERT
        ):
            # display the forecast
            async with lock:
                current_screen = DISPLAY_FORECAST
                eprint("Updating display to show forecast")
                await gfx.update_forecast_display()
        elif down_pressed:
            # display the weather
            async with lock:
                current_screen = DISPLAY_WEATHER
                eprint("Updating display to show weather")
                await gfx.update_weather_display()
        await asyncio.sleep(0.1)

async def update_display(lock: asyncio.Lock):
    """
    Coroutine to update the display every SCREEN_REFRESH seconds.

    SCREEN_REFRESH should be set to at least 15 minutes to avoid
    damage to the e-ink display.

    Parameters
    ----------
    lock: An asyncio lock, used to synchronize screen updates and
        weather downloads.
    """
    global current_screen
    await asyncio.sleep(0.5)
    while True:
        eprint("Updating display time to", datetime.now().strftime("%I:%M %p"))
        gfx.update_time()
        if current_screen == DISPLAY_WEATHER:
            async with lock:
                eprint("Displaying weather")
                await gfx.update_weather_display()
        elif current_screen == DISPLAY_FORECAST:
            async with lock:
                eprint("Displaying forecast")
                await gfx.update_forecast_display()
        elif current_screen == DISPLAY_IAQ and has_sensor_reader:
            async with lock:
                eprint("Displaying iaq")
                await gfx.update_iaq_display()
        elif current_screen == DISPLAY_ALERT:
            async with lock:
                # switch to the weather display
                current_screen = DISPLAY_WEATHER
                eprint("Displaying weather")
                await gfx.update_weather_display()
        else:
            eprint("Unknown screen selected:", current_screen)
            async with lock:
                # switch to the weather display
                current_screen = DISPLAY_WEATHER
                eprint("Displaying weather")
                await gfx.update_weather_display()
        await asyncio.sleep(SCREEN_REFRESH)

async def main():
    """
    Main loop - set up an asyncio lock and run the coroutines.
    """
    (latitude, longitude, locality) = geocode(
        settings.query, settings.country, settings.geocoding_token
    )
    gfx.locality = locality
    lock = asyncio.Lock()
    await asyncio.gather(
        download_weather(latitude, longitude, settings.weather_token, lock),
        update_display(lock),
        handle_button(lock),
        handle_sensor()
    )

try:
    asyncio.run(main())
except KeyboardInterrupt:
    eprint("Shutdown requested... exiting")
    sys.exit(0)
