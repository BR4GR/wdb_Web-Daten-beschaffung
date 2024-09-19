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
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver

from services.mongo_service import MongoService
from utils.yeeter import Yeeter


class MigrosScraper:
    BASE_URL = "https://www.migros.ch/en/"

    def __init__(
        self,
        mongo_service: MongoService,
        yeeter: Yeeter,
        driver_path: str = "/usr/bin/chromedriver",
        binary_location: str = "/usr/bin/chromium",
    ):
        self.driver = self._initialize_driver(driver_path, binary_location)
        self.mongo_service = mongo_service
        self.yeeter = yeeter
        self.base_categories = []
        self.product_ids = set(
            mongo_service.retrieve_todays_scraped_ids(self.current_day_in_iso())
        )
        self.scraped_product_ids = set(
            mongo_service.retrieve_todays_scraped_ids(self.current_day_in_iso())
        )

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

    def load_main_page(self) -> None:
        """Load the main page of the Migros website."""
        self.make_request_and_validate(self.BASE_URL)

    def close(self) -> None:
        """Close the WebDriver session."""
        if self.driver:
            self.driver.quit()

    def yeet(self, message: str):
        """print an info message."""
        self.yeeter.yeet(message)

    def error(self, message: str):
        """print an error message."""
        self.yeeter.error(message)

    def bugreport(self, message: str):
        """print a debug message."""
        self.yeeter.bugreport(message)

    def alarm(self, message: str):
        """prnt a warning message."""
        self.yeeter.alarm(message)

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

    def _log_scraper_state(self, url: str, request=None) -> None:
        """
        Use the Yeeter to log the scraper state before shutdown.
        """
        self.yeeter.log_scraper_state(
            url=url,
            request=request,
            scraped_product_ids=self.scraped_product_ids,
            base_categories=self.base_categories,
        )

    def _get_category_response(
        self, url_contains: str, max_wait_time: int = 30
    ) -> dict:
        """Helper function to capture a network request and return the response."""
        start_time = time.time()

        while True:
            for request in self.driver.requests:
                if url_contains in request.url:
                    try:
                        if request.response is None:
                            self.alarm(f"No response for request: {request.url}")
                            continue

                        response_body = request.response.body
                        if response_body is None:
                            self.alarm(
                                f"Empty response body for request: {request.url}"
                            )
                            continue

                        encoding = request.response.headers.get("Content-Encoding", "")
                        response_body = self._decompress_response(
                            response_body, encoding
                        )

                        return json.loads(response_body.decode("utf-8"))

                    except json.JSONDecodeError:
                        self.error("Error decoding JSON response.")
                        self.error(response_body)
                        return {}
                    except AttributeError as e:
                        self.error(f"Attribute error: {str(e)}")
                        continue
                    except Exception as e:
                        self.error(f"Unexpected error: {str(e)}")
                        continue

            if time.time() - start_time > max_wait_time:
                self.yeet(f"Timeout: {url_contains} request not found.")
                return {}

            time.sleep(1)

    def get_and_store_base_categories(self) -> None:
        """Fetch all base categories and ensure they are tracked in MongoDB."""
        self.yeet("Fetching and storing base categories")
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
        self.yeet(f"Scraping category URL: {category_url}")
        self.make_request_and_validate(category_url)

        product_data = self._get_category_response("product-cards")
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    self.product_ids.add(migros_id)

        category_data = self._get_category_response("search/category")
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
            self.error(f"Failed to fetch data for category: {category_url}")
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
            self.yeet(f"Product {migros_id} was already scraped today. Skipping.")
            self.scraped_product_ids.add(migros_id)
            return

        product_uri = self.BASE_URL + "product/" + migros_id
        self.yeet(f"Scraping product: {product_uri}")
        try:
            self.make_request_and_validate(product_uri)

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
            self.error(f"Error scraping product {migros_id}: {str(e)}")

    def scrape_products(self) -> None:
        """Scrape all products from the Migros website."""
        max_time = 60 * 60  # 1 hour
        start_time = time.time()
        try:
            while (len(self.product_ids) > len(self.scraped_product_ids)) and (
                time.time() - start_time < max_time
            ):
                ids_to_scrape = self.product_ids - self.scraped_product_ids
                self.yeet(f"Scraping {len(ids_to_scrape)} products")
                for migros_id in ids_to_scrape:
                    self.scrape_product_by_id(migros_id)
        except Exception as e:
            self.error(f"Error during product scraping: {str(e)}")

    def make_request_and_validate(self, url: str) -> None:
        """
        Wrapper function to delete the acumulated requests,
        handle the driver.get(), increment request counter,
        and check for valid response (HTTP 200).
        If a non-200 status code is encountered, stop the scraper.
        """
        try:
            del self.driver.requests
            self.driver.get(url)
            self.mongo_service.increment_request_count(self.current_day_in_iso())
            time.sleep(2)

            for request in self.driver.requests:
                if url in request.url and request.response:
                    if request.response.status_code >= 400:
                        self.error(
                            f"Error: {url} returned HTTP status {request.response.status_code}. Stopping scraper."
                        )
                        self._log_scraper_state(
                            url, request
                        )  # Log final state before exit
                        self.close()
                        raise SystemExit(f"Scraper stopped due to error on URL: {url}")

        # Handle WebDriver-specific errors
        except WebDriverException as e:
            self.error(f"WebDriverException on {url}: {str(e)}")
            self._log_scraper_state(url)  # Log final state before exit
            self.close()
            raise SystemExit(f"Scraper stopped due to WebDriverException on URL: {url}")

        # Catch all other exceptions
        except Exception as e:
            self.error(f"Unexpected error during request to {url}: {str(e)}")
            self._log_scraper_state(url)  # Log final state before exit
            self.close()
            raise SystemExit(f"Scraper stopped due to unexpected error on URL: {url}")


if __name__ == "__main__":
    load_dotenv()

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

    yeeter = Yeeter()
    mongo_service = MongoService(MONGO_URI, MONGO_DB_NAME, yeeter)

    scraper = MigrosScraper(mongo_service=mongo_service, yeeter=yeeter)
    try:
        scraper.get_and_store_base_categories()
        scraper.scrape_products()
        scraper.scrape_categorie_from_base()
        scraper.scrape_products()

    finally:
        scraper.close()
