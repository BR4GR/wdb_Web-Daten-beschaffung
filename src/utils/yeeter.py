import logging
from datetime import datetime

from pytz import timezone


class Yeeter:
    def __init__(self, log_filename="yeeted.log"):
        self.logger = logging.getLogger("Yeeter")
        self.logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.CustomFormatter())
        self.logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(self.CustomFormatter())
        self.logger.addHandler(file_handler)

    class CustomFormatter(logging.Formatter):
        """Custom formatter that adjusts time to Berlin time zone."""

        def converter(self, timestamp):
            """Converts the UTC time to Berlin time."""
            utc_time = datetime.utcfromtimestamp(timestamp)
            berlin_time = utc_time.astimezone(timezone("Europe/Berlin"))
            return berlin_time.timetuple()

        def formatTime(self, record, datefmt=None):
            record.created = self.converter(record.created)
            return super().formatTime(record, datefmt)

    # New method to log quickly
    def yeet(self, message: str):
        """Shorthand for logging an info message."""
        self.logger.info(message)

    def yeet_error(self, message: str):
        """Shorthand for logging an error message."""
        self.logger.error(message)
