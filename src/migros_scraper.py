import gzip
import json
import os
import time

import brotli
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver

from services.mongo_service import MongoService


class MigrosScraper:
    BASE_URL = "https://www.migros.ch/en/"
    LOG_DIR = "logs"

    def __init__(
        self,
        mongo_service: MongoService,
        driver_path: str = "/usr/bin/chromedriver",
        binary_location: str = "/usr/bin/chromium",
    ):
        self.driver = self._initialize_driver(driver_path, binary_location)
        self.mongo_service = mongo_service
        self.base_categories = []  # Store full base categories
        self.product_ids = set()  # Track all product IDs found (using migrosId)
        self.scraped_product_ids = set()  # Track all product IDs alresdy scraped
        self._clear_log_files()

    def _initialize_driver(
        self, driver_path: str, binary_location: str
    ) -> webdriver.Chrome:
        service = Service(driver_path)
        options = Options()
        options.binary_location = binary_location
        options.add_argument("--headless")  # Run Chrome in headless mode
        options.add_argument(
            "--disable-dev-shm-usage"
        )  # Overcome limited resource problems
        options.add_argument("--remote-debugging-port=9222")  # Enable remote debugging
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    def _decompress_response(self, response: bytes, encoding: str) -> bytes:
        """Decompress response if necessary."""
        if encoding == "gzip":
            return gzip.decompress(response)
        elif encoding == "br":
            return brotli.decompress(response)
        return response

    def _get_category_response(
        self, url_contains: str, max_wait_time: int = 30
    ) -> dict:
        """Helper function to capture a network request and return the response."""
        start_time = time.time()

        while True:
            for request in self.driver.requests:
                if url_contains in request.url:
                    response = request.response.body
                    encoding = request.response.headers.get("Content-Encoding", "")
                    response = self._decompress_response(response, encoding)

                    try:
                        return json.loads(response.decode("utf-8"))
                    except json.JSONDecodeError:
                        print("Error decoding JSON response.")
                        print(response)
                        return {}

            if time.time() - start_time > max_wait_time:
                print(f"Timeout: {url_contains} request not found.")
                return {}

            time.sleep(1)

    def get_base_categories(self) -> list:
        """Fetch and store the full base categories with all attributes."""
        self.load_main_page()
        categories_response = self._get_category_response("storemap")

        categories = categories_response.get("categories", [])
        for category in categories:
            self.mongo_service.insert_category(category)
            self.base_categories.append(category)

        product_data = self._get_category_response("product-cards")
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    self.product_ids.add(migros_id)

        return self.base_categories

    def scrape_categories_from_base(self) -> None:
        """Try to get all subcategories for each base category."""
        for category in self.base_categories:
            category_url = self.BASE_URL + "category/" + category["slug"]
            second_level_slugs = self.scrape_category_via_url(
                category_url, category["slug"]
            )
            for slug in second_level_slugs:
                url = self.BASE_URL + "category/" + category["slug"] + "/" + slug
                self.scrape_category_via_url(url, slug)

    def scrape_category_via_url(self, category_url: str, slug: str) -> list[str]:
        """Scrape a category by loading the URL and capturing the network requests."""
        del self.driver.requests
        self.driver.get(category_url)
        time.sleep(10)  # Adjust this time if necessary

        # Log each network request URL to a file named after the category slug
        for request in self.driver.requests:
            self.log_request(slug, request)

        # Capture the network request with "category" in the URL
        category_data = self._get_category_response("search/category")
        slugs = [
            category["slug"]
            for category in category_data.get("categories", [])
            if category.get("level") == 3
        ]

        # Capture product data from the "product-cards" endpoint
        product_data = self._get_category_response("product-cards")
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    self.product_ids.add(migros_id)

        if category_data:
            for category in category_data.get("categories", []):
                self.mongo_service.insert_category(category)
            return slugs
        else:
            print(f"Failed to fetch data for category: {category_url}")
            return []

    def scrape_product_by_id(self, migros_id: str) -> None:
        """Scrape a product by its migrosId."""
        product_uri = self.BASE_URL + "product/" + migros_id
        del self.driver.requests
        try:
            self.driver.get(product_uri)
            time.sleep(5)

            product_cards = self._get_category_response("product-cards")
            if product_cards:
                for product in product_cards:
                    new_id = product.get("migrosId")
                    if new_id:
                        self.product_ids.add(new_id)

            product_data = self._get_category_response("product-detail")
            if product_data:
                self.mongo_service.insert_product(product_data[0])
            self.scraped_product_ids.add(migros_id)
        except Exception as e:
            print(f"Error scraping product {migros_id}: {str(e)}")

    def scrape_products(self) -> None:
        """Scrape all products from the Migros website."""
        max_time = 60 * 60  # 1 hour
        start_time = time.time()
        try:
            while (len(self.product_ids) > len(self.scraped_product_ids)) and (
                time.time() - start_time < max_time
            ):
                ids_to_scrape = self.product_ids - self.scraped_product_ids
                print(f"Scraping {len(ids_to_scrape)} products")
                for migros_id in ids_to_scrape:
                    self.scrape_product_by_id(migros_id)
        except Exception as e:
            print(f"Error during product scraping: {str(e)}")

    def load_main_page(self) -> None:
        """Load the main page of the Migros website."""
        self.driver.get(self.BASE_URL)
        time.sleep(5)  # Adjust this time if necessary

    def _clear_log_files(self) -> None:
        """Clear all log files in the log directory."""
        if not os.path.exists(self.LOG_DIR):
            os.makedirs(self.LOG_DIR)  # Create the log directory if it doesn't exist
        else:
            for log_file in os.listdir(self.LOG_DIR):
                log_file_path = os.path.join(self.LOG_DIR, log_file)
                if os.path.isfile(log_file_path):
                    open(log_file_path, "w").close()  # Clear the file

    def log_request(self, slug: str, request: str) -> None:
        """Append request URLs to a log file named after the slug."""
        log_filename = f"{self.LOG_DIR}/{slug}.log"
        with open(log_filename, "a") as log_file:
            log_file.write(f"{request}\n")

    def close(self) -> None:
        """Close the WebDriver session."""
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    # Load environment variables from .env
    load_dotenv()

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

    # Initialize MongoDB Service
    mongo_service = MongoService(MONGO_URI, MONGO_DB_NAME)

    # Initialize and run the scraper
    scraper = MigrosScraper(mongo_service=mongo_service)
    try:
        scraper.get_base_categories()  # Get base categories
        # scraper.scrape_categories_from_base()  # Scrape subcategories
        print(f"Collected product IDs (migrosIds): {scraper.product_ids}")
        scraper.scrape_products()  # Scrape products
        print(f"scraped product IDs (migrosIds): {scraper.scraped_product_ids}")

        # Log the migrosIds
        log_filename = f"{scraper.LOG_DIR}/migrosIds.log"
        if not os.path.exists(scraper.LOG_DIR):
            os.makedirs(scraper.LOG_DIR)

        with open(log_filename, "a") as log_file:
            for product_id in scraper.product_ids:
                log_file.write(f"{product_id}\n")

    finally:
        scraper.close()  # Make sure to close the driver
