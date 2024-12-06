import pdb
import time
import traceback
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from pymongo.server_api import ServerApi

from src.utils.yeeter import Yeeter, yeet


class MongoService:
    def __init__(self, uri: str, db_name: str, yeeter: Yeeter):
        try:
            self.client = MongoClient(uri, server_api=ServerApi("1"))
            self.db = self.client[db_name]
            self.yeeter = yeeter
            self.yeeter.yeet(f"Connected to MongoDB database: {db_name}")
        except ConnectionFailure as e:
            self.yeeter.error(f"MongoDB connection failed: {str(e)}")
            self.log_debug_info()
            raise SystemExit("Unable to connect to MongoDB. Exiting...")
        except Exception as e:
            self.yeeter.error(
                f"Unexpected error during MongoDB initialization: {str(e)}"
            )
            self.log_debug_info()
            raise

    def log_debug_info(self):
        """
        Logs detailed debugging information, including the current stack trace and local variables.
        """
        debug_info = traceback.format_exc()  # Get the current exception traceback
        self.yeeter.error(f"Traceback:\n{debug_info}")

        # Optionally, log local variables for additional context
        frame = traceback.extract_tb(traceback.walk_stack(None)[-1].frame)[-1]
        local_vars = frame[0].f_locals
        self.yeeter.error(f"Local variables: {local_vars}")

    def close(self):
        """Close the MongoDB client connection."""
        try:
            self.client.close()
            self.yeeter.yeet("MongoDB connection closed.")
        except Exception as e:
            self.yeeter.error(f"Error while closing MongoDB connection: {str(e)}")

    def current_day_in_iso(self):
        """
        Returns:
            str: The current day in ISO 8601 format.
        """
        return datetime.now(timezone.utc).date().isoformat()

    # ----------------------------------------------
    #       categories
    # ----------------------------------------------

    def check_category_exists(self, category_id: int) -> bool:
        """
        Check if a category with the given ID exists.

        Args:
            category_id (int): The ID of the category to check.

        Returns:
            bool: True if the category exists, False otherwise.
        """
        try:
            return self.db.categories.find_one({"id": category_id}) is not None
        except PyMongoError as e:
            self.yeeter.error(f"Error checking category existence: {str(e)}")
            return False

    def insert_category(self, category_data: dict) -> None:
        """
        Insert a new category if it does not already exist.

        Args:
            category_data (dict): The category data to insert.
        """
        try:
            if not self.check_category_exists(category_data["id"]):
                self.db.categories.insert_one(category_data)
                self.yeeter.yeet(f"Inserted new category: {category_data['id']}")
        except PyMongoError as e:
            self.yeeter.error(f"Error inserting category: {str(e)}")

    # ----------------------------------------------
    #       category_tracker
    # ----------------------------------------------

    def insert_new_base_categories(self, new_categories: list) -> None:
        """
        Insert new base categories into the category_tracker collection.

        Args:
            new_categories (list): List of categories to be inserted.
        """
        try:
            for category in new_categories:
                if not self.db.category_tracker.find_one({"id": category["id"]}):
                    category["last_scraped"] = None
                    self.db.category_tracker.insert_one(category)
                    self.yeeter.yeet(f"Inserted new base category: {category['id']}")
        except Exception as e:
            self.yeeter.error(f"Error inserting new base categories: {str(e)}")
            self.log_debug_info()
            raise

    def get_untracked_base_categories(self, base_categories: list) -> list:
        """
        Fetch base categories that are not yet tracked in the category_tracker.

        Args:
            base_categories (list): List of base categories to check against the database.

        Returns:
            list: Categories that are not yet tracked.
        """
        try:
            tracked_categories_ids = self.db.category_tracker.distinct("id")
            untracked = [
                category
                for category in base_categories
                if category["id"] not in tracked_categories_ids
            ]
            self.yeeter.yeet(f"Found {len(untracked)} untracked base categories.")
            return untracked
        except Exception as e:
            self.yeeter.error(f"Error fetching untracked base categories: {str(e)}")
            self.log_debug_info()
            raise

    def get_unscraped_categories(self) -> list:
        """
        Fetch categories that have never been scraped (i.e., last_scraped is None).

        Returns:
            list: Categories that have not been scraped.
        """
        try:
            unscraped = list(self.db.category_tracker.find({"last_scraped": None}))
            self.yeeter.yeet(f"Found {len(unscraped)} unscraped categories.")
            return unscraped
        except Exception as e:
            self.yeeter.error(f"Error fetching unscraped categories: {str(e)}")
            self.log_debug_info()
            raise

    def mark_category_as_scraped(self, category_id: int, current_day) -> None:
        """
        Mark a category as scraped today or insert it if it's new.

        Args:
            category_id (int): ID of the category to mark as scraped.
            current_day (str): The current day in ISO format.
        """
        try:
            result = self.db.category_tracker.update_one(
                {"id": category_id},
                {"$set": {"last_scraped": current_day}},
                upsert=True,
            )
            if result.matched_count:
                self.yeeter.yeet(
                    f"Updated category {category_id} as scraped for {current_day}."
                )
            else:
                self.yeeter.yeet(
                    f"Inserted new category {category_id} as scraped for {current_day}."
                )
        except Exception as e:
            self.yeeter.error(f"Error marking category as scraped: {str(e)}")
            self.log_debug_info()
            raise

    def get_oldest_scraped_category(self) -> dict:
        """
        Fetch the category that was scraped the longest time ago,
        or a category that has never been scraped.

        Returns:
            dict: The oldest scraped category or a never-scraped category.
        """
        try:
            oldest = self.db.category_tracker.find_one(sort=[("last_scraped", 1)])
            if oldest:
                self.yeeter.yeet(
                    f"Oldest scraped category: {oldest['id']} (last scraped: {oldest.get('last_scraped')})."
                )
            else:
                self.yeeter.yeet("No categories found in the database.")
            return oldest
        except Exception as e:
            self.yeeter.error(f"Error fetching oldest scraped category: {str(e)}")
            self.log_debug_info()
            raise

    # ----------------------------------------------
    #       products
    # ----------------------------------------------

    def check_product_exists(self, migros_id: str) -> bool:
        """
        Check if a product with the given migrosId already exists in the MongoDB collection.

        Args:
            migros_id (str): The unique ID of the product.

        Returns:
            bool: True if the product exists, False otherwise.
        """
        try:
            exists = self.db.products.find_one({"migrosId": migros_id}) is not None
            self.yeeter.yeet(f"Product with migrosId {migros_id} exists: {exists}")
            return exists
        except Exception as e:
            self.yeeter.error(
                f"Error checking product existence for migrosId {migros_id}: {str(e)}"
            )
            self.log_debug_info()
            raise

    def insert_product(self, product_data: dict) -> None:
        """
        Insert a new product document if the price is new or the product doesn't exist in the database.

        Args:
            product_data (dict): Dictionary containing product details.
        """
        try:
            migros_id = product_data.get("migrosId")
            description = product_data.get("description")
            name = product_data.get("name")

            if not migros_id:
                self.yeeter.error(
                    "Product does not contain migrosId, skipping insertion."
                )
                return

            # Check if product has offer
            if not product_data.get("offer"):
                self.yeeter.error(
                    f"Product with migrosId {migros_id} does not have an offer, skipping insertion."
                )
                return

            existing_product = self.get_latest_product_entry_by_migros_id(migros_id)
            new_price = product_data.get("offer", {}).get("price", {})

            if not existing_product:
                # Product doesn't exist, insert as new
                product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.db.products.insert_one(product_data)
                self.yeeter.yeet(
                    f"Inserted new product {name} with migrosId: {migros_id}"
                )

            elif existing_product.get("offer", {}).get("price", {}) != new_price:
                # Unit price has changed, insert as new and log price change
                product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.db.products.insert_one(product_data)

                # Log the price change in the 'unit_price_history' collection
                price_change_entry = {
                    "migrosId": migros_id,
                    "newPrice": new_price,
                    "dateChanged": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                self.db.unit_price_history.insert_one(price_change_entry)
                self.yeeter.yeet(
                    f"\033[1;32mNew unit price detected for product {name} with migrosId: {migros_id}. Logged price change.\033[0m"
                )

            else:
                # Product exists with the same price, skip insertion
                self.yeeter.logger.debug(
                    f"Product with migrosId {migros_id} already exists with the same unitPrice. Skipping insertion."
                )
        except Exception as e:
            self.yeeter.error(
                f"Error inserting product with migrosId {migros_id}: {str(e)}"
            )
            self.log_debug_info()
            raise

    def get_latest_product_entry_by_migros_id(self, migros_id: str) -> dict:
        """
        Fetch the latest product entry for a given migrosId, based on the date it was added.

        Args:
            migros_id (str): The unique ID of the product.

        Returns:
            dict: The latest product entry, or None if not found.
        """
        try:
            product = self.db.products.find_one(
                {"migrosId": migros_id}, sort=[("dateAdded", -1)]
            )
            if product:
                self.yeeter.yeet(
                    f"Found latest product entry for migrosId {migros_id}."
                )
            return product
        except Exception as e:
            self.yeeter.error(
                f"Error fetching latest product entry for migrosId {migros_id}: {str(e)}"
            )
            self.log_debug_info()
            raise

    def get_all_known_migros_ids(self) -> list:
        """
        Fetch all migrosIds of the known products.

        Returns:
            list: List of all known migrosIds.
        """
        try:
            ids = self.db.products.distinct("migrosId")
            self.yeeter.yeet(f"Fetched {len(ids)} known migrosIds.")
            return ids
        except Exception as e:
            self.yeeter.error(f"Error fetching all known migrosIds: {str(e)}")
            self.log_debug_info()
            raise

    def get_products_not_scraped_in_days(
        self, days: int, limit: int = 100, only_edible=True
    ) -> list:
        """
        Retrieve migrosIds of products that haven't been scraped in the last 'x' days.

        Args:
            days (int): The number of days since the last scrape.
            limit (int): Maximum number of products to retrieve.
            only_edible (bool): If True, only fetch products with nutrients information.

        Returns:
            list: List of migrosIds that meet the criteria.
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = {"lastScraped": {"$lt": cutoff_date}}

            if only_edible:
                # Add the filter for only edible products
                edible_ids = self.db.products.distinct(
                    "migrosId",
                    {"productInformation.nutrientsInformation": {"$exists": True}},
                )
                query["migrosId"] = {"$in": edible_ids}

            # Fetch product IDs with the defined limit
            products = self.db.id_scraped_at.find(
                query, {"migrosId": 1}  # Only return migrosId
            ).limit(limit)

            ids_to_scrape = [product["migrosId"] for product in products]
            self.yeeter.yeet(
                f"Found {len(ids_to_scrape)} products that haven't been scraped in {days}+ days."
            )
            return ids_to_scrape
        except Exception as e:
            self.yeeter.error(
                f"Error retrieving products not scraped in {days} days: {str(e)}"
            )
            self.log_debug_info()
            raise

    # ----------------------------------------------
    #       unit_price_history
    # ----------------------------------------------

    def get_price_history(self, migros_id: str):
        """
        Fetch the price history for a given product.

        Args:
            migros_id (str): The unique ID of the product.

        Returns:
            list: A list of price history entries sorted by dateChanged.
        """
        try:
            price_history = list(
                self.db.unit_price_history.find({"migrosId": migros_id}).sort(
                    "dateChanged", 1
                )
            )
            self.yeeter.yeet(
                f"Retrieved price history for migrosId {migros_id}, {len(price_history)} records found."
            )
            return price_history
        except Exception as e:
            self.yeeter.error(
                f"Error fetching price history for migrosId {migros_id}: {str(e)}"
            )
            self.log_debug_info()
            raise

    # ----------------------------------------------
    #       id_scraped_at
    # ----------------------------------------------

    def save_scraped_product_id(self, migros_id: str) -> None:
        """
        Save the scraped product ID with the current date.

        Args:
            migros_id (str): The unique ID of the product.

        Returns:
            None
        """
        try:
            current_date = datetime.now(timezone.utc)
            self.db.id_scraped_at.update_one(
                {"migrosId": migros_id},
                {"$set": {"lastScraped": current_date}},
                upsert=True,
            )
            self.yeeter.yeet(
                f"Saved scraped product ID {migros_id} with lastScraped date {current_date}."
            )
        except Exception as e:
            self.yeeter.error(f"Error saving scraped product ID {migros_id}: {str(e)}")
            self.log_debug_info()
            raise

    def is_product_scraped_last_24_hours(self, migros_id: str) -> bool:
        """
        Check if a product with the given migrosId has been scraped in the last 24 hours.

        Args:
            migros_id (str): The unique ID of the product.

        Returns:
            bool: True if the product was scraped in the last 24 hours, False otherwise.
        """
        try:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=24)

            scraped = self.db.id_scraped_at.find_one(
                {
                    "migrosId": migros_id,
                    "lastScraped": {"$gte": cutoff_time},
                }
            )
            result = scraped is not None
            self.yeeter.yeet(f"Product {migros_id} scraped in last 24 hours: {result}")
            return result
        except Exception as e:
            self.yeeter.error(
                f"Error checking if product {migros_id} was scraped in the last 24 hours: {str(e)}"
            )
            self.log_debug_info()
            raise

    def retrieve_id_scraped_at_last_24_hours(self) -> list[int]:
        """
        Retrieve all id_scraped_at entries that have been scraped in the last 24 hours.

        Returns:
            list[int]: List of migrosIds scraped in the last 24 hours.
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            scraped_ids = [
                scraped_data["migrosId"]
                for scraped_data in self.db.id_scraped_at.find(
                    {"lastScraped": {"$gte": cutoff_time}}
                )
                if "migrosId" in scraped_data
            ]
            self.yeeter.yeet(
                f"Retrieved {len(scraped_ids)} product IDs scraped in the last 24 hours."
            )
            return scraped_ids
        except Exception as e:
            self.yeeter.error(
                f"Error retrieving products scraped in the last 24 hours: {str(e)}"
            )
            self.log_debug_info()
            raise

    # ----------------------------------------------
    #       request_counts
    # ----------------------------------------------

    def get_request_count(self, date: str) -> int:
        """
        Retrieve the request count for the given date.

        Args:
            date (str): The target date in ISO format.

        Returns:
            int: The request count for the specified date.
        """
        try:
            record = self.db.request_counts.find_one({"date": date})
            count = record.get("count", 0) if record else 0
            self.yeeter.yeet(f"Request count for {date}: {count}")
            return count
        except Exception as e:
            self.yeeter.error(f"Error retrieving request count for {date}: {str(e)}")
            self.log_debug_info()
            raise

    def increment_request_count(self, date: str, count: int = 1) -> None:
        """
        Increment the request count for the given date.

        Args:
            date (str): The target date in ISO format.
            count (int): The increment value (default is 1).

        Returns:
            None
        """
        try:
            self.db.request_counts.update_one(
                {"date": date}, {"$inc": {"count": count}}, upsert=True
            )
            self.yeeter.yeet(f"Incremented request count for {date} by {count}.")
        except Exception as e:
            self.yeeter.error(f"Error incrementing request count for {date}: {str(e)}")
            self.log_debug_info()
            raise


if __name__ == "__main__":
    yeeter = Yeeter()
    ms = MongoService("mongodb://localhost:27017", "exampledb", yeeter)
    migros_id = "123456"
    ms.yeeter.yeet(
        f"\033[1;32mNew unit price detected for product with migrosId: {migros_id}. Logged price change.\033[0m"
    )
    ms.yeeter.bugreport("fix bugs")
    ms.yeeter.alarm("ALAAAARM")
