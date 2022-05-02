import configparser

from eprint import eprint

class Settings:
    """
    A class to read a settings/ini file and parse the required values.

    Properties
    ----------
    weather_token: str
        OpenWeather API token
    geocoding_token: str
        PositionStack API token
    query: str
        Free-form location query
    country: str
        Country code used to filter geocoding results;
        either 2-letter or 3-letter
    adafruit_username: str
        Username for Adafruit.IO.
    adafruit_key: str
        Authentication Key for Adafruit.IO.
    celsius: bool
        Flag indicating whether Celsius should be displayed;
        if False, use Fahrenheit
    am_pm: bool
        Flag indicating whether to display 12-hour clock with AM/PM;
        if False, use 24-hour clock
    starting_screen: str
        Initial screen to show on the display;
        one of: weather, iaq, forecast

    Methods
    -------
    dump: Dump the parsed settings file to stderr for debugging.
    """
    def __init__(self, inifilepath: str):
        """
        Parameters
        ----------
        inifilepath: A string containing a path to the settings file.
        """
        config = configparser.ConfigParser()
        config.read_file(open(inifilepath))
        try:
            openweather = config['openweatherapi']
            self._weather_token = openweather.get('token')

            positionstack = config['positionstack']
            self._geocoding_token = positionstack.get('token')
            self._query = positionstack.get('query')
            self._country = positionstack.get('country')

            adafruit = config['adafruit']
            self._adafruit_key = adafruit.get('key')
            self._adafruit_username = adafruit.get('username')

            display = config['display']
            self._celsius = display.getboolean('celsius', fallback = False)
            self._am_pm = display.getboolean('am_pm', fallback = True)
            self._starting_screen = display.get('starting_screen')

        except configparser.Error:
            raise RuntimeError(
                "Invalid settings file. Please use config.ini.sample to create a properly formatted file."
            )
        if len(self._weather_token) == 0:
            raise RuntimeError(
                "You need to set your OpenWeather token first. If you don't already have one, you can register for a free account at https://home.openweathermap.org/users/sign_up"
            )
        if len(self._geocoding_token) == 0:
            raise RuntimeError(
                "You need to set your PositionStack token first. If you don't already have one, you can register for a free account at https://positionstack.com/signup/free"
            )
        if len(self._adafruit_key) == 0 or len(self._adafruit_username) == 0:
            raise RuntimeError(
                "You need to set your Adafruit IO key and username first. If you don't already have one, you can register for a free account at https://io.adafruit.com/"
            )

    def dump(self):
        """
        Dump the parsed settings file to stderr for debugging.
        """
        eprint("Parsed settings file")
        eprint("Location to look up:", self._query, self._country)
        eprint("Celsius:", self._celsius)
        eprint("AM/PM indicator:", self._am_pm)
        eprint("Starting Screen:", self._starting_screen)

    @property
    def weather_token(self):
        return self._weather_token

    @property
    def geocoding_token(self):
        return self._geocoding_token

    @property
    def query(self):
        return self._query

    @property
    def country(self):
        return self._country

    @property
    def adafruit_key(self):
        return self._adafruit_key

    @property
    def adafruit_username(self):
        return self._adafruit_username

    @property
    def celsius(self):
        return self._celsius

    @property
    def am_pm(self):
        return self._am_pm

    @property
    def starting_screen(self):
        return self._starting_screen
