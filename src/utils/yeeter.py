import logging
from datetime import datetime, timezone

from pytz import timezone as pytz_timezone


class Yeeter:
    def __init__(self, log_filename="yeeted.log"):
        self.logger = logging.getLogger("Yeeter")
        self.logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.CustomFormatter())
        self.logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(self.CustomFormatter())
        self.logger.addHandler(file_handler)

    class CustomFormatter(logging.Formatter):
        """Custom formatter that adjusts time to Berlin time zone and formats logs."""

        def converter(self, timestamp):
            """Converts the UTC time to Berlin time using timezone-aware datetime."""
            # Create a timezone-aware UTC datetime object
            utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            berlin_time = utc_time.astimezone(pytz_timezone("Europe/Berlin"))
            return berlin_time

        def formatTime(self, record, datefmt=None):
            """Formats the time in the desired format without milliseconds."""
            # Convert the record's creation time and return only up to seconds
            record_time = self.converter(record.created)
            return record_time.strftime("%Y-%m-%d %H:%M")

        def format(self, record):
            """Format the log message to include time, level, and message."""
            log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            record.asctime = self.formatTime(record)
            formatter = logging.Formatter(log_format)
            return formatter.format(record)

    # New method to log quickly
    def yeet(self, message: str):
        """Shorthand for logging an info message."""
        self.logger.info(message)

    def yeet_error(self, message: str):
        """Shorthand for logging an error message."""
        self.logger.error(message)


if __name__ == "__main__":
    yeeter = Yeeter()
    yeeter.yeet("Scraping product: 123456")
    yeeter.yeet_error("Error scraping product 123456: Connection timed out")
