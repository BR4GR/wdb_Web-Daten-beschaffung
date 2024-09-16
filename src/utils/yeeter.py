import logging
from datetime import datetime, timezone

from colorama import Fore, Style, init
from pytz import timezone as pytz_timezone

# Initialize colorama for Windows compatibility
init(autoreset=True)


class Yeeter:
    def __init__(self, log_filename="yeeted.log"):
        self.logger = logging.getLogger("Yeeter")
        self.logger.setLevel(logging.DEBUG)

        # Define log format to include asctime, log level, logger name, and message
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.CustomFormatter(log_format, colored=True))
        self.logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(self.CustomFormatter(log_format, colored=False))
        self.logger.addHandler(file_handler)

    class CustomFormatter(logging.Formatter):
        """Custom formatter that adjusts time to Berlin time zone and formats logs."""

        def __init__(self, fmt, colored: bool = False):
            super().__init__(fmt)
            self.colored = colored

        def converter(self, timestamp):
            """Converts the UTC time to Berlin time using timezone-aware datetime."""
            utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            berlin_time = utc_time.astimezone(pytz_timezone("Europe/Berlin"))
            return berlin_time

        def formatTime(self, record, datefmt=None):
            """Formats the time in the desired format without milliseconds."""
            record_time = self.converter(record.created)
            return record_time.strftime("%Y-%m-%d %H:%M:%S")

        def format(self, record):
            """Override the default format to add color."""
            record.asctime = self.formatTime(record)  # Override the asctime field
            log_message = super().format(record)

            if self.colored:
                if record.levelno == logging.INFO:
                    return f"{Fore.GREEN}{log_message}{Style.RESET_ALL}"
                elif record.levelno == logging.ERROR:
                    return f"{Fore.RED}{log_message}{Style.RESET_ALL}"
                elif record.levelno == logging.WARNING:
                    return f"{Fore.YELLOW}{log_message}{Style.RESET_ALL}"
                elif record.levelno == logging.DEBUG:
                    return f"{Fore.CYAN}{log_message}{Style.RESET_ALL}"
                else:
                    return log_message
            return log_message

    # New method to log quickly
    def yeet(self, message: str):
        """Shorthand for logging an info message."""
        self.logger.info(message)

    def yeet_error(self, message: str):
        """Shorthand for logging an error message."""
        self.logger.error(message)

    def alarm(self, message: str):
        """Shorthand for logging a warning message."""
        self.logger.warning(message)

    def yeet_bug(self, message: str):
        """Shorthand for logging a debug message."""
        self.logger.debug(message)


def yeet(self, message: str):
    """Shorthand for logging an info message."""
    self.logger.info(message)


if __name__ == "__main__":
    yeeter = Yeeter()
    yeeter.yeet("Scraping product: 123456")
    yeeter.yeet_error("Error scraping product 123456: Connection timed out")
    yeeter.alarm("Product price is higher than usual")
    yeeter.yeet_bug("fix it")
