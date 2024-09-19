import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from colorama import Fore, Style, init
from pytz import timezone as pytz_timezone

# Initialize colorama for Windows compatibility
init(autoreset=True)


class Yeeter:
    def __init__(
        self,
        log_filename="scraper.log",
        log_dir="src/logs",
        max_bytes=5000000,
        backup_count=5,
    ):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        log_filepath = os.path.join(self.log_dir, log_filename)
        self.logger = logging.getLogger("Yeeter")
        self.logger.setLevel(logging.DEBUG)

        # Define log format to include asctime, log level, logger name, and message
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.CustomFormatter(log_format, colored=True))
        self.logger.addHandler(console_handler)

        file_handler = RotatingFileHandler(
            log_filepath, maxBytes=max_bytes, backupCount=backup_count
        )
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
                if record.levelno == logging.ERROR:
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
        """Shorthand for printing an info message."""
        self.logger.info(message)

    def error(self, message: str):
        """Shorthand for printing an error message."""
        self.logger.error(message)

    def alarm(self, message: str):
        """Shorthand for printing a warning message."""
        self.logger.warning(message)

    def bugreport(self, message: str):
        """Shorthand for printing a debug message."""
        self.logger.debug(message)

    def clear_log_files(self) -> None:
        """Delete all log files in the log directory."""
        for log_file in os.listdir(self.log_dir):
            log_file_path = os.path.join(self.log_dir, log_file)
            if os.path.isfile(log_file_path):
                os.remove(log_file_path)  # Delete the file
                self.yeet(f"Deleted log file: {log_file_path}")

    def log_scraper_state(
        self, url: str, request=None, scraped_product_ids=None, base_categories=None
    ):
        """
        Log the final state of the scraper before shutdown.
        This captures details about the URL, request, response, and any other relevant data.
        """
        self.yeet(f"Logging scraper state for URL: {url}")

        # Log current URL being processed
        self.yeet(f"Current URL: {url}")

        # Log the request and response if available
        if request:
            self.yeet(f"Request URL: {request.url}")
            if request.response:
                self.yeet(f"Response Status Code: {request.response.status_code}")
                self.yeet(f"Response Headers: {request.response.headers}")
            else:
                self.yeet("No response available for this request.")
        else:
            self.yeet("No specific request object available.")

        # Log the number of products or categories scraped
        if scraped_product_ids is not None:
            self.yeet(f"Total products scraped so far: {len(scraped_product_ids)}")

        if base_categories is not None:
            self.yeet(f"Total categories scraped so far: {len(base_categories)}")

        # Log the last scraped product ID or category
        if scraped_product_ids and len(scraped_product_ids) > 0:
            last_product_id = list(scraped_product_ids)[-1]
            self.yeet(f"Last scraped product ID: {last_product_id}")

        if base_categories and len(base_categories) > 0:
            last_category = base_categories[-1]
            self.yeet(f"Last scraped category: {last_category.get('name', 'Unknown')}")


def yeet(self, message: str):
    """Shorthand for printing an info message."""
    self.logger.info(message)


if __name__ == "__main__":
    yeeter = Yeeter()
    yeeter.yeet("Scraping product: 123456")
    yeeter.error("Error scraping product 123456: Connection timed out")
    yeeter.alarm("Product price is higher than usual")

    yeeter.bugreport("fix it")
