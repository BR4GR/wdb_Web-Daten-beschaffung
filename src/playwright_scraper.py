"""
Playwright-based Migros scraper prototype.
Uses Firefox to bypass Cloudflare and intercepts API responses.
"""

import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Response

from src.services.mongo_service import MongoService
from src.utils.yeeter import Yeeter

load_dotenv()

# Global reference for signal handler
_scraper_instance = None


class PlaywrightMigrosScraper:
    BASE_URL = "https://www.migros.ch/en/"
    SEARCH_API = "onesearch-oc-seaapi"
    PRODUCT_DETAIL_API = "product-display"
    STOREMAP_API = "onesearch-oc-storemap"

    def __init__(
        self,
        mongo_service: MongoService,
        yeeter: Yeeter,
        headless: bool = False,
        average_sleep_time: float = 3.0,
    ):
        self.mongo_service = mongo_service
        self.yeeter = yeeter
        self.headless = headless
        self.average_sleep_time = average_sleep_time

        self.known_ids = set()
        self.scraped_products = []
        self.scraped_categories = []
        self.captured_responses = {}
        self.new_products_queue = []  # Queue for newly discovered products
        self.page = None  # Will be set when browser is running

        # Statistics tracking
        self.stats = {
            "start_time": None,
            "end_time": None,
            "products_scraped": 0,
            "new_ids_discovered": 0,
            "price_updates_found": 0,
            "batches_completed": 0,
            "errors": 0,
            "interrupted": False,
        }

        # Register this instance globally for signal handling
        global _scraper_instance
        _scraper_instance = self

        # Load known IDs from MongoDB
        try:
            self.known_ids = set(mongo_service.get_all_known_migros_ids())
            self.yeeter.yeet(f"Loaded {len(self.known_ids)} known product IDs")
        except Exception as e:
            self.yeeter.error(f"Error loading known IDs: {e}")

    def _handle_response(self, response: Response):
        """Capture relevant API responses."""
        url = response.url

        try:
            if self.SEARCH_API in url and "/search" in url and response.status == 200:
                data = response.json()
                self.captured_responses["search"] = data
                product_ids = data.get("productIds", [])
                self.yeeter.yeet(f"Captured search response: {len(product_ids)} product IDs")

            elif self.PRODUCT_DETAIL_API in url and response.status == 200:
                data = response.json()
                # Collect ALL products from product-display API
                products_to_store = []
                if isinstance(data, dict) and data.get("migrosId"):
                    products_to_store = [data]
                elif isinstance(data, list):
                    products_to_store = [p for p in data if isinstance(p, dict) and p.get("migrosId")]

                for product in products_to_store:
                    migros_id = product.get("migrosId")
                    if migros_id not in self.captured_responses.get("products", {}):
                        if "products" not in self.captured_responses:
                            self.captured_responses["products"] = {}
                        self.captured_responses["products"][migros_id] = product

                        # Track new products for immediate scraping
                        if migros_id and migros_id not in self.known_ids:
                            self.new_products_queue.append(migros_id)
                            self.yeeter.yeet(f"NEW product discovered: {migros_id}")

            elif self.STOREMAP_API in url and response.status == 200:
                data = response.json()
                self.captured_responses["storemap"] = data
                self.yeeter.yeet(f"Captured storemap response")

            # Capture full product details (with productInformation) from product detail pages
            if response.status == 200 and "migros" in url:
                try:
                    data = response.json()
                    if isinstance(data, dict) and data.get("productInformation"):
                        if "full_product_detail" not in self.captured_responses:
                            self.captured_responses["full_product_detail"] = data
                    elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and data[0].get("productInformation"):
                        if "full_product_detail" not in self.captured_responses:
                            self.captured_responses["full_product_detail"] = data[0]
                except:
                    pass

        except Exception as e:
            # Silently ignore non-JSON responses
            pass

    def _random_sleep(self):
        """Sleep for a random duration around average_sleep_time."""
        sleep_time = random.uniform(
            self.average_sleep_time * 0.5,
            self.average_sleep_time * 1.5
        )
        self.yeeter.yeet(f"Sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)

    def write_stats_to_file(self, reason: str = "completed"):
        """Write scraping statistics to a log file."""
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        self.stats["products_scraped"] = len(self.scraped_products)

        # Calculate duration
        duration = "N/A"
        if self.stats["start_time"]:
            try:
                start = datetime.fromisoformat(self.stats["start_time"])
                end = datetime.fromisoformat(self.stats["end_time"])
                duration_seconds = (end - start).total_seconds()
                hours, remainder = divmod(int(duration_seconds), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration = f"{hours}h {minutes}m {seconds}s"
            except:
                pass

        # Build log content
        log_content = f"""
================================================================================
SCRAPER RUN SUMMARY - {reason.upper()}
================================================================================
Start Time:          {self.stats["start_time"]}
End Time:            {self.stats["end_time"]}
Duration:            {duration}

STATISTICS:
-----------
Products Scraped:    {self.stats["products_scraped"]}
New IDs Discovered:  {self.stats["new_ids_discovered"]}
Price Updates Found: {self.stats["price_updates_found"]}
Batches Completed:   {self.stats["batches_completed"]}
Errors Encountered:  {self.stats["errors"]}
Interrupted:         {self.stats["interrupted"]}

================================================================================
"""
        # Write to file
        log_file = "scraper_stats.log"
        try:
            with open(log_file, "a") as f:
                f.write(log_content)
            self.yeeter.yeet(f"Stats written to {log_file}")
        except Exception as e:
            self.yeeter.error(f"Failed to write stats to file: {e}")

        # Also print to console
        print(log_content)

    def run(self, max_categories: int = 5, max_products_per_category: int = 100):
        """
        Main scraping loop.

        Args:
            max_categories: Maximum number of categories to scrape
            max_products_per_category: Maximum products to scrape per category
        """
        self.yeeter.yeet("Starting Playwright scraper with Firefox...")

        with sync_playwright() as p:
            browser = p.firefox.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
            )
            page = context.new_page()

            # Set up response interception
            page.on("response", self._handle_response)

            try:
                # Step 1: Load main page to get Cloudflare clearance
                self.yeeter.yeet("Loading main page...")
                page.goto(self.BASE_URL, wait_until="networkidle")
                self._random_sleep()

                # Step 2: Get categories from storemap
                categories = self._get_categories(page)
                self.yeeter.yeet(f"Found {len(categories)} categories")

                # Step 3: Scrape each category
                for i, category in enumerate(categories[:max_categories]):
                    self.yeeter.yeet(f"Processing category {i+1}/{min(len(categories), max_categories)}: {category['name']}")
                    self._scrape_category(page, category, max_products_per_category)
                    self._random_sleep()

                self.yeeter.yeet(f"Scraping complete. Products scraped: {len(self.scraped_products)}")

            except Exception as e:
                self.yeeter.error(f"Error during scraping: {e}")
                raise
            finally:
                browser.close()

    def run_rescrape_batched(self, days: int = 5, batch_size: int = 500, only_edible: bool = True, exclude_edible: bool = False, queue_new_ids: bool = False):
        """
        Re-scrape products that haven't been scraped in X days, using batched queries to avoid memory exhaustion.

        Args:
            days: Number of days since last scrape to trigger re-scrape
            batch_size: Number of products to fetch per batch
            only_edible: If True, only scrape products with nutrition information
            exclude_edible: If True, exclude products with nutrition information
            queue_new_ids: If True, add new IDs to the back of the queue instead of scraping immediately

        Returns:
            List of newly discovered IDs (if queue_new_ids=True)
        """
        if only_edible:
            filter_str = "edible "
        elif exclude_edible:
            filter_str = "non-edible "
        else:
            filter_str = ""
        self.yeeter.yeet(f"Starting batched re-scrape: {filter_str}products not scraped in {days}+ days (batch size: {batch_size})")

        # Initialize start time if not already set (when called directly, not via run_two_phase)
        if not self.stats["start_time"]:
            self.stats["start_time"] = datetime.now(timezone.utc).isoformat()

        # Track new IDs discovered during this phase (for queue_new_ids mode)
        discovered_new_ids = []
        total_scraped = 0
        batch_number = 0

        with sync_playwright() as p:
            browser = p.firefox.launch(headless=self.headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
            )
            page = context.new_page()
            page.on("response", self._handle_response)

            try:
                # Load main page first to get Cloudflare clearance
                self.yeeter.yeet("Loading main page for Cloudflare clearance...")
                page.goto(self.BASE_URL, wait_until="networkidle")
                self._random_sleep()

                # Process in batches
                while True:
                    batch_number += 1
                    self.yeeter.yeet(f"--- Fetching batch {batch_number} ---")

                    # Fetch next batch of IDs (sorted by oldest first)
                    ids_to_scrape = self.mongo_service.get_products_not_scraped_in_days(
                        days=days, limit=batch_size, only_edible=only_edible, exclude_edible=exclude_edible
                    )

                    if not ids_to_scrape:
                        self.yeeter.yeet(f"No more products to scrape in batch {batch_number}")
                        break

                    self.yeeter.yeet(f"Batch {batch_number}: {len(ids_to_scrape)} products to scrape")

                    # Re-scrape each product in this batch
                    for i, migros_id in enumerate(ids_to_scrape):
                        self.yeeter.yeet(f"Batch {batch_number} [{i+1}/{len(ids_to_scrape)}]: {migros_id}")
                        self._scrape_product_by_id(page, migros_id)
                        total_scraped += 1

                        if queue_new_ids:
                            # Collect new IDs but don't scrape them yet
                            if self.new_products_queue:
                                for new_id in self.new_products_queue:
                                    if new_id not in discovered_new_ids:
                                        discovered_new_ids.append(new_id)
                                        self.stats["new_ids_discovered"] += 1
                                        self.yeeter.yeet(f"Queued new ID for later: {new_id}")
                                self.new_products_queue.clear()
                        else:
                            # Immediately scrape any newly discovered products
                            self._process_new_products_queue(page)

                        self._random_sleep()

                    self.stats["batches_completed"] += 1
                    self.yeeter.yeet(f"Batch {batch_number} complete. Total scraped so far: {total_scraped}")

                self.yeeter.yeet(f"All batches complete. Total products scraped: {total_scraped}")
                if discovered_new_ids:
                    self.yeeter.yeet(f"Discovered {len(discovered_new_ids)} new IDs (queued for later)")

            except Exception as e:
                self.stats["errors"] += 1
                self.yeeter.error(f"Error during batched re-scrape: {e}")
                raise
            finally:
                browser.close()

        return discovered_new_ids

    def run_two_phase_rescrape(self, days: int = 5, batch_size: int = 500):
        """
        Three-phase re-scrape with batching to avoid memory exhaustion:
        Phase 1: Re-scrape edible products (with nutrition) not scraped in X days.
                 New IDs discovered go to the back of the queue. Sorted oldest first.
        Phase 2: Scrape the newly discovered IDs from Phase 1.
        Phase 3: Re-scrape non-edible products not scraped in X days.
                 New IDs can be scraped immediately. Sorted oldest first.

        Args:
            days: Number of days since last scrape to trigger re-scrape
            batch_size: Number of products to fetch per batch (default: 500)
        """
        # Initialize stats
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat()

        self.yeeter.yeet("=" * 60)
        self.yeeter.yeet("PHASE 1: Re-scraping edible products (with nutrition)")
        self.yeeter.yeet(f"Batched (size: {batch_size}). Sorted oldest first. New IDs queued.")
        self.yeeter.yeet("=" * 60)

        # Phase 1: Edible products only, queue new IDs, batched
        queued_new_ids = self.run_rescrape_batched(
            days=days,
            batch_size=batch_size,
            only_edible=True,
            exclude_edible=False,
            queue_new_ids=True
        )

        # Phase 2: Scrape queued new IDs from Phase 1 (in batches to avoid memory issues)
        if queued_new_ids:
            self.yeeter.yeet("=" * 60)
            self.yeeter.yeet(f"PHASE 2: Scraping {len(queued_new_ids)} newly discovered IDs from Phase 1")
            self.yeeter.yeet("=" * 60)

            with sync_playwright() as p:
                browser = p.firefox.launch(headless=self.headless)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
                )
                page = context.new_page()
                page.on("response", self._handle_response)

                try:
                    self.yeeter.yeet("Loading main page for Cloudflare clearance...")
                    page.goto(self.BASE_URL, wait_until="networkidle")
                    self._random_sleep()

                    for i, migros_id in enumerate(queued_new_ids):
                        self.yeeter.yeet(f"Scraping queued ID {i+1}/{len(queued_new_ids)}: {migros_id}")
                        self._scrape_product_by_id(page, migros_id)
                        self._process_new_products_queue(page)
                        self._random_sleep()

                except Exception as e:
                    self.yeeter.error(f"Error scraping queued IDs: {e}")
                    raise
                finally:
                    browser.close()
        else:
            self.yeeter.yeet("=" * 60)
            self.yeeter.yeet("PHASE 2: No new IDs discovered in Phase 1, skipping")
            self.yeeter.yeet("=" * 60)

        self.yeeter.yeet("=" * 60)
        self.yeeter.yeet("PHASE 3: Re-scraping non-edible products")
        self.yeeter.yeet(f"Batched (size: {batch_size}). Sorted oldest first. New IDs scraped immediately.")
        self.yeeter.yeet("=" * 60)

        # Phase 3: Non-edible products only, scrape new IDs immediately, batched
        self.run_rescrape_batched(
            days=days,
            batch_size=batch_size,
            only_edible=False,
            exclude_edible=True,
            queue_new_ids=False
        )

        self.yeeter.yeet("=" * 60)
        self.yeeter.yeet(f"All phases complete. Total products scraped: {len(self.scraped_products)}")
        self.yeeter.yeet("=" * 60)

        # Write final stats
        self.write_stats_to_file("completed")

    def _get_categories(self, page: Page) -> list:
        """Get categories by navigating to a category page and capturing storemap."""
        self.captured_responses.clear()

        # Navigate to a category page to trigger storemap API
        page.goto(f"{self.BASE_URL}category/dairy-eggs-fresh-convenience-foo", wait_until="networkidle")
        page.wait_for_timeout(3000)

        storemap = self.captured_responses.get("storemap", {})
        categories = []

        # Extract categories from storemap
        if storemap:
            for cat in storemap.get("categories", []):
                categories.append({
                    "id": cat.get("id"),
                    "name": cat.get("name"),
                    "slug": cat.get("slug"),
                    "path": cat.get("path"),
                })

        # Fallback: use simple search terms if storemap didn't work
        if not categories:
            self.yeeter.yeet("Storemap not captured, using fallback search terms")
            categories = [
                {"name": "chocolate", "slug": "chocolate"},
                {"name": "milk", "slug": "milk"},
                {"name": "bread", "slug": "bread"},
                {"name": "cheese", "slug": "cheese"},
                {"name": "coffee", "slug": "coffee"},
            ]

        return categories

    def _scrape_category(self, page: Page, category: dict, max_products: int):
        """Scrape products from a category using search."""
        name = category.get("name", "")
        if not name:
            self.yeeter.error(f"Category has no name: {category}")
            return

        self.captured_responses.clear()
        self.captured_responses["products"] = {}

        # Use search page - products are captured automatically via product-display API
        search_url = f"{self.BASE_URL}search?query={name.replace(' ', '+')}"
        self.yeeter.yeet(f"Navigating to {search_url}")
        page.goto(search_url, wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Scroll down to load more products
        self.yeeter.yeet("Scrolling to load more products...")
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(2000)

        # Get captured products from product-display API responses
        captured_products = self.captured_responses.get("products", {})
        self.yeeter.yeet(f"Captured {len(captured_products)} products from page")

        # Get search metadata
        search_data = self.captured_responses.get("search", {})
        total_products = search_data.get("numberOfProducts", 0)
        self.yeeter.yeet(f"Search found {total_products} total products")

        # Store category info
        if search_data.get("categories"):
            for cat_data in search_data["categories"]:
                self._store_category(cat_data)

        # Collect products to fetch full details for
        products_to_detail = []
        for migros_id, product_data in captured_products.items():
            if len(products_to_detail) >= max_products:
                break
            products_to_detail.append(product_data)

        self.yeeter.yeet(f"Fetching full details for {len(products_to_detail)} products...")

        # Second pass: visit each product page for full details
        products_stored = 0
        for product_data in products_to_detail:
            product_url = product_data.get("productUrls")
            migros_id = product_data.get("migrosId")

            if not product_url:
                # Fallback: construct URL from migrosId
                product_url = f"{self.BASE_URL}product/{migros_id}"

            full_product = self._fetch_full_product_details(page, product_url, migros_id)
            if full_product:
                self._store_product(full_product)
                self.scraped_products.append(migros_id)
                products_stored += 1
            else:
                # Store partial data if full fetch failed
                self._store_product(product_data)
                self.scraped_products.append(migros_id)
                products_stored += 1

            # Immediately scrape any newly discovered products
            self._process_new_products_queue(page)
            self._random_sleep()

        self.yeeter.yeet(f"Stored {products_stored} products from {category['name']}")

    def _fetch_full_product_details(self, page: Page, product_url: str, migros_id: str) -> Optional[dict]:
        """
        Navigate to a product page and capture full details including nutrients, ingredients, etc.

        Args:
            page: Playwright page object
            product_url: Full URL to the product page
            migros_id: The migrosId for logging

        Returns:
            Full product data dict or None if capture failed
        """
        self.yeeter.yeet(f"Fetching full details for {migros_id}: {product_url}")

        # Clear previous product captures but keep a flag for this specific product
        if "full_product" in self.captured_responses:
            del self.captured_responses["full_product"]

        try:
            # Clear full_product_detail before navigating
            if "full_product_detail" in self.captured_responses:
                del self.captured_responses["full_product_detail"]

            page.goto(product_url, wait_until="networkidle")
            page.wait_for_timeout(4000)

            # First check if we captured full product detail from a different API
            if self.captured_responses.get("full_product_detail"):
                product_data = self.captured_responses["full_product_detail"]
                self.yeeter.yeet(f"Got FULL details for {migros_id} (with productInformation)")
                return product_data

            # Look for the full product detail in captured responses
            # The product-display API on detail pages returns complete data
            captured_products = self.captured_responses.get("products", {})

            # Find the product we're looking for
            if migros_id in captured_products:
                product_data = captured_products[migros_id]
                # Check if this has full details (productInformation section)
                if product_data.get("productInformation"):
                    self.yeeter.yeet(f"Got full details for {migros_id} (with nutrients/ingredients)")
                    return product_data
                else:
                    self.yeeter.yeet(f"Got product {migros_id} but without full details")
                    return product_data

            # Try to find any product that was captured (might have different ID format)
            for pid, pdata in captured_products.items():
                if pdata.get("productInformation"):
                    self.yeeter.yeet(f"Got full details for {pid} (with nutrients/ingredients)")
                    return pdata

            self.yeeter.error(f"No full product data captured for {migros_id}")
            return None

        except Exception as e:
            self.yeeter.error(f"Error fetching full details for {migros_id}: {e}")
            return None

    def _store_product(self, product_data: dict):
        """Store product data in MongoDB."""
        try:
            # Add timestamp
            product_data["scrapedAt"] = datetime.now(timezone.utc).isoformat()
            migros_id = product_data.get("migrosId", "unknown")

            # insert_product returns True if a price update was detected
            is_price_update = self.mongo_service.insert_product(product_data)
            if is_price_update:
                self.stats["price_updates_found"] += 1

            # Record that we scraped this product
            self.mongo_service.save_scraped_product_id(migros_id)
            self.known_ids.add(migros_id)
            self.yeeter.yeet(f"Stored product {migros_id}")

        except Exception as e:
            self.stats["errors"] += 1
            self.yeeter.error(f"Error storing product: {e}")

    def _scrape_product_by_id(self, page: Page, migros_id: str) -> bool:
        """
        Scrape a single product by its migrosId.

        Args:
            page: Playwright page object
            migros_id: The product's migrosId

        Returns:
            True if product was scraped successfully, False otherwise
        """
        # Skip if already scraped recently
        if self.mongo_service.is_product_scraped_last_24_hours(migros_id):
            self.yeeter.yeet(f"Product {migros_id} already scraped today. Skipping.")
            return False

        product_url = f"{self.BASE_URL}product/{migros_id}"
        full_product = self._fetch_full_product_details(page, product_url, migros_id)

        if full_product:
            self._store_product(full_product)
            self.scraped_products.append(migros_id)
            return True
        else:
            # Try to use partial data if we have it
            partial_data = self.captured_responses.get("products", {}).get(migros_id)
            if partial_data:
                self._store_product(partial_data)
                self.scraped_products.append(migros_id)
                return True

        # No product data found - mark as not found
        # This updates lastScraped and tracks consecutive failures
        # After 3 failures, the product will be excluded from future scraping
        self.mongo_service.mark_product_not_found(migros_id)
        return False

    def _process_new_products_queue(self, page: Page):
        """Process any newly discovered products that aren't in known_ids."""
        if not self.new_products_queue:
            return

        # Deduplicate the queue
        unique_new_ids = list(dict.fromkeys(self.new_products_queue))
        self.new_products_queue.clear()

        self.yeeter.yeet(f"Processing {len(unique_new_ids)} newly discovered products...")

        for migros_id in unique_new_ids:
            if migros_id in self.known_ids:
                continue

            self.stats["new_ids_discovered"] += 1
            self._scrape_product_by_id(page, migros_id)
            self._random_sleep()

    def _store_category(self, category_data: dict):
        """Store category data in MongoDB."""
        try:
            self.mongo_service.insert_category(category_data)
            self.scraped_categories.append(category_data.get("id"))

        except Exception as e:
            self.yeeter.error(f"Error storing category: {e}")


def _signal_handler(signum, frame):
    """Handle interrupt signals and write stats before exiting."""
    global _scraper_instance
    print(f"\n\nReceived signal {signum}, shutting down gracefully...")
    if _scraper_instance:
        _scraper_instance.stats["interrupted"] = True
        _scraper_instance.write_stats_to_file("interrupted")
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(description="Playwright-based Migros scraper")
    parser.add_argument("--rescrape", action="store_true", help="Re-scrape products not scraped in X days")
    parser.add_argument("--two-phase", action="store_true", help="Three-phase rescrape: edible first (queue new IDs), then new IDs, then non-edible")
    parser.add_argument("--days", type=int, default=5, help="Days since last scrape for re-scrape mode (default: 5)")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for fetching products (default: 500)")
    parser.add_argument("--only-edible", action="store_true", help="Only scrape products with nutrition info (for --rescrape mode)")
    parser.add_argument("--categories", type=int, default=10, help="Max categories to scrape (default: 10)")
    parser.add_argument("--products", type=int, default=50, help="Max products per category (default: 50)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

    if not MONGO_URI or not MONGO_DB_NAME:
        print("Error: MONGO_URI and MONGO_DB_NAME must be set in .env")
        return

    yeeter = Yeeter()
    mongo_service = MongoService(MONGO_URI, MONGO_DB_NAME, yeeter)

    scraper = PlaywrightMigrosScraper(
        mongo_service=mongo_service,
        yeeter=yeeter,
        headless=args.headless,
        average_sleep_time=3.0,
    )

    try:
        if args.two_phase:
            scraper.run_two_phase_rescrape(days=args.days, batch_size=args.batch_size)
        elif args.rescrape:
            scraper.run_rescrape_batched(days=args.days, batch_size=args.batch_size, only_edible=args.only_edible)
        else:
            scraper.run(
                max_categories=args.categories,
                max_products_per_category=args.products,
            )
    except Exception as e:
        scraper.stats["errors"] += 1
        scraper.stats["interrupted"] = True
        scraper.write_stats_to_file(f"error: {e}")
        raise
    finally:
        mongo_service.close()


if __name__ == "__main__":
    main()
