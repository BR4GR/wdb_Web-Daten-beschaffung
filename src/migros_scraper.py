import gzip
import json
import time

import brotli  # Brotli decompression is sometimes used as well
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver  # Import from selenium-wire instead of selenium

from services import mongo_service


class MigrosScraper:
    BASE_URL = "https://www.migros.ch/en"

    def __init__(
        self,
        mongo_service,
        driver_path: str = "/usr/bin/chromedriver",
        binary_location: str = "/usr/bin/chromium",
    ):
        self.driver = self._initialize_driver(driver_path, binary_location)
        self.mongo_service = mongo_service
        self.product_ids = set()  # Store unique product IDs
        self.base_categories = {}  # Store base categories as a dictionary

    def _initialize_driver(
        self, driver_path: str, binary_location: str
    ) -> webdriver.Chrome:
        service = Service(driver_path)
        options = Options()
        options.binary_location = binary_location
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    def load_main_page(self) -> None:
        self.driver.get(self.BASE_URL)
        # time.sleep(5)  # Adjust this time if necessary

    def _get_storemap_response(self):
        for request in self.driver.requests:
            if "storemap" in request.url:
                return request
        return None

    def _decompress_response(self, response, encoding: str):
        if encoding == "gzip":
            return gzip.decompress(response)
        elif encoding == "br":
            return brotli.decompress(response)
        return response

    def _process_categories(self, categories):
        for category in categories:
            self.base_categories[category["id"]] = category["name"]

            if not self.mongo_service.check_category_exists(category["id"]):
                self.mongo_service.insert_category(category)
                print(f"Inserted new category: {category['name']}")
            else:
                print(f"Category already exists: {category['name']}")

    def get_base_categories(self) -> dict:
        self.load_main_page()

        start_time = time.time()
        max_wait_time = 30  # Maximum wait time in seconds

        while True:
            request = self._get_storemap_response()
            if request:
                encoding = request.response.headers.get("Content-Encoding", "")
                print(f"Encoding: {encoding}")

                response = self._decompress_response(request.response.body, encoding)

                try:
                    response_str = response.decode("utf-8")
                    data = json.loads(response_str)
                    categories = data.get("categories", [])
                    self._process_categories(categories)
                    return self.base_categories
                except json.JSONDecodeError:
                    print("Error decoding JSON response.")
                    return {}

            if time.time() - start_time > max_wait_time:
                print("Timeout: Storemap request not found.")
                break

            time.sleep(1)  # Short sleep to prevent busy-waiting

        return {}

    def close(self) -> None:
        """Method to close the WebDriver session (i.e., close the browser window)."""
        if self.driver:
            self.driver.quit()
