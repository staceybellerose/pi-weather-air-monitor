from Adafruit_IO import Client, Group, Feed

# Change this feed group name if necessary
GROUP_NAME = 'iaq_stats' # The feed group to use

FEED_TEMPERATURE = 'temperature'  # The name of the temperature feed
FEED_HUMIDITY = 'humidity'  # The name of the humidity feed
FEED_PRESSURE = 'pressure'  # The name of the pressure feed
FEED_IAQ = 'iaq'  # The name of the IAQ feed

class AIO_Logger:
    """
    Adafruit.IO API Client wrapper.
    """
    def __init__(self, aio_user, aio_key):
        """
        Parameters
        ----------
        aio_user: Username for Adafruit.IO.
        aio_key: Authentication Key for Adafruit.IO.
        """
        self.aio = Client(aio_user, aio_key)
        self.create_group_if_needed()
        self.temperature_feed = self.get_feed(FEED_TEMPERATURE)
        self.humidity_feed = self.get_feed(FEED_HUMIDITY)
        self.pressure_feed = self.get_feed(FEED_PRESSURE)
        self.iaq_feed = self.get_feed(FEED_IAQ)

    def create_group_if_needed(self):
        """
        Create a Feed Group on Adafruit.IO if it doesn't already exist.
        """
        self.group = None
        group_list: list[Group] = self.aio.groups()
        for group in group_list:
            if group.name == GROUP_NAME:
                self.group = group
                break
        if self.group is None:
            self.group = self.aio.create_group(GROUP_NAME)

    def get_feed(self, feed_name: str):
        """
        Get a Feed object based on the feed_name parameter.

        The Feed will be associated with our feed group.

        Parameters
        ----------
        feed_name: The name of the feed to retrieve/create.
        """
        feed_key = "%s.%s" % (self.group.key, feed_name)
        feed_list: list[Feed] = self.aio.feeds()
        for feed in feed_list:
            if feed.key == feed_key:
                return feed
        # didn't find the feed, so create it
        return self.aio.create_feed(feed_name, self.group.key)

    def log(self, temperature, humidity, pressure, iaq):
        """
        Log IAQ data to Adafruit.IO

        Parameters
        ----------
        temperature: Current ambient temperature.
        humidity: Current relative humidity, as a percent.
        pressure: Current atmospheric pressure.
        iaq: Current calculated IAQ.
        """
        self.aio.send(self.temperature_feed.key, temperature)
        self.aio.send(self.humidity_feed.key, humidity)
        self.aio.send(self.pressure_feed.key, pressure)
        self.aio.send(self.iaq_feed.key, iaq)
