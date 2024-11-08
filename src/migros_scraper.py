import gzip
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import brotli
from dotenv import load_dotenv
from pymongo import MongoClient
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver

from src.services.mongo_service import MongoService
from src.utils.yeeter import Yeeter


class MigrosScraper:
    BASE_URL = "https://www.migros.ch/en/"

    def __init__(
        self,
        mongo_service: MongoService,
        yeeter: Yeeter,
        driver_path: str = "/usr/bin/chromedriver",
        binary_location: str = "/usr/bin/chromium",
        average_request_sleep_time: float = 4.0,
    ):
        self.driver = self._initialize_driver(driver_path, binary_location)
        self.mongo_service: MongoService = mongo_service
        self.yeeter: Yeeter = yeeter
        self.base_categories = []
        self.known_ids = set(mongo_service.get_all_known_migros_ids())
        self.todays_scraped_product_ids = set(
            mongo_service.retrieve_id_scraped_at_last_24_hours()
        )
        self.average_request_sleep_time = average_request_sleep_time

    def _initialize_driver(
        self, driver_path: str, binary_location: str
    ) -> webdriver.Chrome:
        service = Service(driver_path)
        options = Options()
        options.binary_location = binary_location
        options.add_argument("--headless")  # Ensures no UI is needed
        options.add_argument("--no-sandbox")  # Required for running Chrome in Docker
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "--disable-gpu"
        )  # Recommended when running in headless mode
        options.add_argument("--remote-debugging-port=9222")
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
        return datetime.now(timezone.utc).date().isoformat()

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
            scraped_product_ids=self.todays_scraped_product_ids,
            base_categories=self.base_categories,
        )

    def _get_specific_response(
        self, url_contains: str, max_wait_time: int = 10
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
        """
        Fetch all base categories and ensure they are tracked in MongoDB.
        if we encounter a product that was never seen before we will scrape it.
        """
        self.yeet("Fetching and storing base categories")
        self.load_main_page()
        categories_response = self._get_specific_response("storemap")

        self.base_categories = categories_response.get("categories", [])
        for category in self.base_categories:
            self.mongo_service.insert_category(category)
        untracked_categories = self.mongo_service.get_untracked_base_categories(
            self.base_categories
        )
        if untracked_categories:
            self.mongo_service.insert_new_base_categories(untracked_categories)

        product_data = self._get_specific_response("product-cards", 5)
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    if migros_id not in self.known_ids:
                        self.known_ids.add(migros_id)
                        self.scrape_product_by_id(migros_id)
        self.scrape_categories_from_base()

    def scrape_categories_from_base(self) -> None:
        """
        Try to get all subcategories for each base category.
        if we encounter a product that was never seen before we will scrape it.
        """
        for category in self.base_categories:
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

    def scrape_category_via_url(self, category_url: str, slug: str) -> list[str]:
        """Scrape a category by loading the URL and capturing the network requests."""
        self.yeet(f"Scraping category URL: {category_url}")
        self.make_request_and_validate(category_url)

        product_data = self._get_specific_response("product-cards", 5)
        if product_data:
            for product in product_data:
                migros_id = product.get("migrosId")
                if migros_id:
                    if migros_id not in self.known_ids:
                        self.known_ids.add(migros_id)
                        self.scrape_product_by_id(migros_id)

        category_data = self._get_specific_response("search/category")
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

    def reset_scraped_ids_daily(self) -> None:
        """Reset the scraped_product_ids in MongoDB if the date has changed."""
        mongo_service.reset_scraped_ids(self.current_day_in_iso())

    def scrape_product_by_id(self, migros_id: str) -> None:
        """Scrape a product by its migrosId."""
        if self.mongo_service.is_product_scraped_last_24_hours(migros_id):
            self.yeet(f"Product {migros_id} was already scraped today. Skipping.")
            self.todays_scraped_product_ids.add(migros_id)
            return

        product_uri = self.BASE_URL + "product/" + migros_id
        self.yeet(f"Scraping product: {product_uri}")
        try:
            self.make_request_and_validate(product_uri)

            product_data = self._get_specific_response("product-detail")
            if product_data:
                self.mongo_service.insert_product(product_data[0])

            self.mongo_service.save_scraped_product_id(migros_id)
            self.todays_scraped_product_ids.add(migros_id)

            product_cards = self._get_specific_response("product-cards", 5)
            if product_cards:
                for product in product_cards:
                    new_id = product.get("migrosId")
                    if new_id and new_id not in self.known_ids:
                        self.known_ids.add(new_id)
                        self.scrape_product_by_id(new_id)
        except Exception as e:
            self.error(f"Error scraping product {migros_id}: {str(e)}")

    def make_request_and_validate(self, url: str) -> None:
        """
        Wrapper function to delete the acumulated requests,
        handle the driver.get(), increment request counter,
        and check for valid response (HTTP 200).
        If a error status code is encountered, stop the scraper.
        """
        try:
            del self.driver.requests
            self.driver.get(url)
            self.mongo_service.increment_request_count(self.current_day_in_iso())
            delay = random.uniform(0.0, (self.average_request_sleep_time * 2))
            self.yeet(f"Sleeping for {delay:.2f} seconds before the next request.")
            time.sleep(delay)

            for request in self.driver.requests:
                if url in request.url and request.response:
                    if request.response.status_code == 429:
                        self.error(f"Encountered HTTP 429 Too Many Requests.")
                        retry_after = int(
                            request.response.headers.get("Retry-After", 60)
                        )
                        if retry_after > 3600:
                            self.error(
                                f"Retry-After value is too high ({retry_after} seconds). Stopping scraper."
                            )
                            self._log_scraper_state(url, request)
                        self.error(f"Retrying after {retry_after} seconds.")
                        time.sleep(retry_after)
                        self.make_request_and_validate(url)
                        return

                    elif request.response.status_code >= 400:
                        self.error(
                            f"Error: {url} returned HTTP status {request.response.status_code}. Stopping scraper."
                        )
                        self._log_scraper_state(url, request)
                        self.close()
                        raise SystemExit(f"Scraper stopped due to error on URL: {url}")

        except WebDriverException as e:
            self.error(f"WebDriverException on {url}: {str(e)}")
            self._log_scraper_state(url)
            self.close()
            raise SystemExit(f"Scraper stopped due to WebDriverException on URL: {url}")

        except Exception as e:
            self.error(f"Unexpected error during request to {url}: {str(e)}")
            self._log_scraper_state(url)
            self.close()
            raise SystemExit(f"Scraper stopped due to unexpected error on URL: {url}")


if __name__ == "__main__":
    load_dotenv()

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
    RUNNING_IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

    yeeter = Yeeter()
    mongo_service = MongoService(MONGO_URI, MONGO_DB_NAME, yeeter)
    average_request_sleep_time = 2.0
    if not RUNNING_IN_GITHUB_ACTIONS:
        average_request_sleep_time = 12.0

    scraper = MigrosScraper(
        mongo_service=mongo_service,
        yeeter=yeeter,
        average_request_sleep_time=average_request_sleep_time,
    )
    try:
        yeeter.yeet("Running in GitHub Actions:")
        yeeter.yeet(RUNNING_IN_GITHUB_ACTIONS)
        days = 5 if RUNNING_IN_GITHUB_ACTIONS else 3
        limit = 400 if RUNNING_IN_GITHUB_ACTIONS else 10001
        yeeter.yeet(f"{days} days, {limit} products")

        edible_ids = mongo_service.db.products.distinct(
            "migrosId", {"productInformation.nutrientsInformation": {"$exists": True}}
        )
        yeeter.yeet(f"Found {len(edible_ids)} edible products.")

        yeeter.yeet(f"Fetching products not scraped in {days}+ days.")
        ids_to_scrape = mongo_service.get_products_not_scraped_in_days(
            days=days, limit=limit
        )
        yeeter.yeet(f"Scraping {len(ids_to_scrape)} products.")
        yeeter.yeet(ids_to_scrape)

        for migros_id in ids_to_scrape:
            scraper.scrape_product_by_id(migros_id)

        yeeter.yeet("Finished scraping products. Closing scraper.")
    finally:
        scraper.close()
