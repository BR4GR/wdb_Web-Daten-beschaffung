import gzip
import json
import os
import random
import time
from datetime import datetime

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
        self.base_categories = []
        self.product_ids = set(
            mongo_service.retrieve_todays_scraped_ids(self.current_day_in_iso())
        )
        self.scraped_product_ids = set(
            mongo_service.retrieve_todays_scraped_ids(self.current_day_in_iso())
        )
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

    def current_day_in_iso(self):
        """Return the current day in ISO format."""
        return datetime.now().date().isoformat()

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
                    try:
                        # Check if the request has a response
                        if request.response is None:
                            print(
                                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                f"No response for request: {request.url}",
                            )
                            continue  # Skip to the next request

                        # Check if the response body exists
                        response_body = request.response.body
                        if response_body is None:
                            print(
                                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                f"Empty response body for request: {request.url}",
                            )
                            continue  # Skip to the next request

                        # Handle response encoding
                        encoding = request.response.headers.get("Content-Encoding", "")
                        response_body = self._decompress_response(
                            response_body, encoding
                        )

                        # Parse the response JSON
                        return json.loads(response_body.decode("utf-8"))

                    except json.JSONDecodeError:
                        print(
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                            "Error decoding JSON response.",
                        )
                        print(response_body)
                        return {}
                    except AttributeError as e:
                        print(
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                            f"Attribute error: {str(e)}",
                        )
                        continue  # Skip to the next request
                    except Exception as e:
                        print(
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                            f"Unexpected error: {str(e)}",
                        )
                        continue  # Skip to the next request

            if time.time() - start_time > max_wait_time:
                print(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    f"Timeout: {url_contains} request not found.",
                )
                return {}

            time.sleep(1)

    def get_and_store_base_categories(self) -> None:
        """Fetch all base categories and ensure they are tracked in MongoDB."""
        self.load_main_page()
        categories_response = self._get_category_response("storemap")

        self.base_categories = categories_response.get("categories", [])
        for category in self.base_categories:
            self.mongo_service.insert_category(category)
        # Store any new categories in the category_tracker collection
        untracked_categories = self.mongo_service.get_untracked_base_categories(
            self.base_categories
        )
        if untracked_categories:
            self.mongo_service.insert_new_base_categories(untracked_categories)

        product_data = self._get_category_response("product-cards")
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    self.product_ids.add(migros_id)

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

    def scrape_categorie_from_base(self) -> None:
        """Try to get all subcategories for each base category."""
        category = mongo_service.get_oldest_scraped_category()
        category_url = self.BASE_URL + "category/" + category["slug"]
        second_level_slugs = self.scrape_category_via_url(
            category_url, category["slug"]
        )
        self.mongo_service.mark_category_as_scraped(
            category["id"], self.current_day_in_iso()
        )
        for slug in second_level_slugs:
            url = self.BASE_URL + "category/" + category["slug"] + "/" + slug
            self.scrape_category_via_url(url, slug)
            self.scrape_products()

    def scrape_category_via_url(self, category_url: str, slug: str) -> list[str]:
        """Scrape a category by loading the URL and capturing the network requests."""
        print(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            f"Scraping category URL: {category_url}",
        )
        del self.driver.requests
        self.driver.get(category_url)
        time.sleep(3)  # Adjust this time if necessary

        # Log each network request URL to a file named after the category slug
        for request in self.driver.requests:
            self.log_request(slug, request)

        # Capture the network request with "category" in the URL
        category_data = self._get_category_response("search/category")

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
            slugs = [
                category["slug"]
                for category in category_data.get("categories", [])
                if category.get("level") == 3
            ]
            return slugs
        else:
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Failed to fetch data for category: {category_url}",
            )
            return []

    def get_next_category_to_scrape(self) -> dict:
        """Find the next category to scrape."""
        # Check if any base category has never been scraped
        untracked_categories = self.mongo_service.get_untracked_base_categories(
            self.base_categories
        )
        if untracked_categories:
            return untracked_categories[0]  # Scrape the first untracked category

        # Otherwise, find the category that was scraped the longest time ago
        return self.mongo_service.get_oldest_scraped_category()

    def reset_scraped_ids_daily(self) -> None:
        """Reset the scraped_product_ids in MongoDB if the date has changed."""
        mongo_service.reset_scraped_ids(self.current_day_in_iso())

    def scrape_product_by_id(self, migros_id: str) -> None:
        """Scrape a product by its migrosId."""
        # Check if product was already scraped today
        if self.mongo_service.is_product_scraped_today(
            migros_id, self.current_day_in_iso()
        ):
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Product {migros_id} was already scraped today. Skipping.",
            )
            self.scraped_product_ids.add(migros_id)
            return

        product_uri = self.BASE_URL + "product/" + migros_id
        del self.driver.requests
        try:
            self.driver.get(product_uri)
            time.sleep(3)

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
            self.mongo_service.save_scraped_product_id(
                migros_id, self.current_day_in_iso()
            )
        except Exception as e:
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Error scraping product {migros_id}: {str(e)}",
            )

    def scrape_products(self) -> None:
        """Scrape all products from the Migros website."""
        max_time = 60 * 60  # 1 hour
        start_time = time.time()
        try:
            while (len(self.product_ids) > len(self.scraped_product_ids)) and (
                time.time() - start_time < max_time
            ):
                ids_to_scrape = self.product_ids - self.scraped_product_ids
                print(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    f"Scraping {len(ids_to_scrape)} products",
                )
                for migros_id in ids_to_scrape:
                    self.scrape_product_by_id(migros_id)
        except Exception as e:
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Error during product scraping: {str(e)}",
            )

    def load_main_page(self) -> None:
        """Load the main page of the Migros website."""
        self.driver.get(self.BASE_URL)
        time.sleep(3)  # Adjust this time if necessary

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
        scraper.get_and_store_base_categories()  # Get base categories
        scraper.scrape_products()  # Scrape products
        print(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            f"scraped product IDs (migrosIds): {scraper.scraped_product_ids}",
        )

        scraper.scrape_categorie_from_base()  # Scrape subcategories
        print(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            f"Collected product IDs (migrosIds): {scraper.product_ids}",
        )
        scraper.scrape_products()  # Scrape products
        print(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            f"scraped product IDs (migrosIds): {scraper.scraped_product_ids}",
        )

        # Log the migrosIds
        log_filename = f"{scraper.LOG_DIR}/00migrosIds.log"
        if not os.path.exists(scraper.LOG_DIR):
            os.makedirs(scraper.LOG_DIR)

        with open(log_filename, "a") as log_file:
            for product_id in scraper.product_ids:
                log_file.write(f"{product_id}\n")

    finally:
        scraper.close()  # Make sure to close the driver
