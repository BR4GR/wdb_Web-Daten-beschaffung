import logging
from datetime import datetime

from pytz import timezone


class Yeeter:
    def __init__(self, log_filename="yeeted.log"):
        # Create a logger
        self.logger = logging.getLogger("Yeeter")
        self.logger.setLevel(logging.INFO)

        # Create handlers for both console and file
        console_handler = logging.StreamHandler()  # Console handler
        file_handler = logging.FileHandler(log_filename)  # File handler

        # Set logging format
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        console_handler.setFormatter(self.CustomFormatter())
        file_handler.setFormatter(self.CustomFormatter())

        # Add handlers to the logger
        self.logger.addHandler(console_handler)
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

    def info(self, message):
        """Logs an info message."""
        self.logger.info(message)

    def error(self, message):
        """Logs an error message."""
        self.logger.error(message)
