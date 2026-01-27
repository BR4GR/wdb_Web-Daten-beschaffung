import pdb
import time
import traceback
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ConnectionFailure, PyMongoError
from pymongo.server_api import ServerApi

from src.utils.yeeter import Yeeter, yeet


class MongoService:
    def __init__(self, uri: str, db_name: str, yeeter: Yeeter):
        try:
            self.client = MongoClient(uri, server_api=ServerApi("1"))
            self.db = self.client[db_name]
            self.yeeter = yeeter
            # Ensure required collections exist
            for collection in [
                "products",
                "categories",
                "id_scraped_at",
                "unit_price_history",
                "request_counts",
            ]:
                self.yeeter.yeet(f"Ensuring collection exists: {collection}")
                self.ensure_collection_exists(collection)
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

    def ensure_collection_exists(self, collection_name: str):
        """Ensure that a collection exists in the database."""
        if collection_name not in self.db.list_collection_names():
            self.db.create_collection(collection_name)
            self.yeeter.yeet(f"Created collection: {collection_name}")
        else:
            self.yeeter.yeet(f"Collection existed: {collection_name}")

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

    def insert_product(self, product_data: dict) -> bool:
        """
        Insert a new product document if the price is new or the product doesn't exist in the database.

        Args:
            product_data (dict): Dictionary containing product details.

        Returns:
            bool: True if a price update was detected, False otherwise.
        """
        try:
            migros_id = product_data.get("migrosId")
            description = product_data.get("description")
            name = product_data.get("name")

            if not migros_id:
                self.yeeter.error(
                    "Product does not contain migrosId, skipping insertion."
                )
                return False

            # Check if product has offer
            if not product_data.get("offer"):
                self.yeeter.error(
                    f"Product with migrosId {migros_id} does not have an offer, skipping insertion."
                )
                return False

            existing_product = self.get_latest_product_entry_by_migros_id(migros_id)
            new_price = product_data.get("offer", {}).get("price", {})

            if not existing_product:
                # Product doesn't exist, insert as new
                product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.db.products.insert_one(product_data)
                self.yeeter.yeet(
                    f"Inserted new product {name} with migrosId: {migros_id}"
                )
                return False

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
                return True

            else:
                # Product exists with the same price, skip insertion
                self.yeeter.logger.debug(
                    f"Product with migrosId {migros_id} already exists with the same unitPrice. Skipping insertion."
                )
                return False
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
        self, days: int, limit: int = None, only_edible: bool = True, exclude_edible: bool = False
    ) -> list:
        """
        Retrieve migrosIds of products that haven't been scraped in the last 'x' days.
        Results are sorted by lastScraped ascending (oldest first).
        Excludes products marked as notFound=True.

        Args:
            days (int): The number of days since the last scrape.
            limit (int): Maximum number of products to retrieve. None = no limit.
            only_edible (bool): If True, only fetch products with nutrients information.
            exclude_edible (bool): If True, exclude products with nutrients information.

        Returns:
            list: List of migrosIds that meet the criteria, sorted oldest first.
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = {
                "lastScraped": {"$lt": cutoff_date},
                # Exclude products that are marked as permanently not found
                "$or": [
                    {"notFound": {"$exists": False}},
                    {"notFound": False}
                ]
            }

            if only_edible or exclude_edible:
                # Get edible product IDs
                edible_ids = self.db.products.distinct(
                    "migrosId",
                    {"productInformation.nutrientsInformation": {"$exists": True}},
                )
                if only_edible:
                    query["migrosId"] = {"$in": edible_ids}
                elif exclude_edible:
                    query["migrosId"] = {"$nin": edible_ids}

            # Fetch product IDs sorted by lastScraped (oldest first)
            cursor = self.db.id_scraped_at.find(
                query, {"migrosId": 1}
            ).sort("lastScraped", 1)  # 1 = ascending (oldest first)

            if limit:
                cursor = cursor.limit(limit)

            ids_to_scrape = [product["migrosId"] for product in cursor]
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
                {"$set": {"lastScraped": current_date, "notFound": False, "notFoundCount": 0}},
                upsert=True,
            )
            self.yeeter.yeet(
                f"Saved scraped product ID {migros_id} with lastScraped date {current_date}."
            )
        except Exception as e:
            self.yeeter.error(f"Error saving scraped product ID {migros_id}: {str(e)}")
            self.log_debug_info()
            raise

    def mark_product_not_found(self, migros_id: str) -> None:
        """
        Mark a product as not found (no longer exists on Migros website).
        Increments notFoundCount and sets notFound=True after 3 consecutive failures.

        Args:
            migros_id (str): The unique ID of the product.
        """
        try:
            current_date = datetime.now(timezone.utc)
            # Increment the not found counter
            result = self.db.id_scraped_at.find_one_and_update(
                {"migrosId": migros_id},
                {
                    "$set": {"lastScraped": current_date},
                    "$inc": {"notFoundCount": 1}
                },
                upsert=True,
                return_document=ReturnDocument.AFTER
            )
            not_found_count = result.get("notFoundCount", 1)

            # After 3 consecutive failures, mark as permanently not found
            if not_found_count >= 3:
                self.db.id_scraped_at.update_one(
                    {"migrosId": migros_id},
                    {"$set": {"notFound": True}}
                )
                self.yeeter.alarm(
                    f"Product {migros_id} marked as NOT FOUND after {not_found_count} consecutive failures."
                )
            else:
                self.yeeter.yeet(
                    f"Product {migros_id} not found (attempt {not_found_count}/3). Updated lastScraped."
                )
        except Exception as e:
            self.yeeter.error(f"Error marking product {migros_id} as not found: {str(e)}")
            self.log_debug_info()
            raise

    def get_not_found_products_count(self) -> dict:
        """
        Get counts of products marked as not found.

        Returns:
            dict: Contains 'permanently_not_found' (notFound=True) and
                  'pending_not_found' (notFoundCount > 0 but < 3) counts.
        """
        try:
            permanently_not_found = self.db.id_scraped_at.count_documents(
                {"notFound": True}
            )
            pending_not_found = self.db.id_scraped_at.count_documents(
                {"notFoundCount": {"$gt": 0, "$lt": 3}, "notFound": {"$ne": True}}
            )
            self.yeeter.yeet(
                f"Not found products: {permanently_not_found} permanent, {pending_not_found} pending"
            )
            return {
                "permanently_not_found": permanently_not_found,
                "pending_not_found": pending_not_found
            }
        except Exception as e:
            self.yeeter.error(f"Error getting not found products count: {str(e)}")
            return {"permanently_not_found": 0, "pending_not_found": 0}

    def reset_not_found_products(self) -> int:
        """
        Reset all products marked as not found so they can be re-checked.
        Useful if Migros restructures their product IDs or brings back discontinued products.

        Returns:
            int: Number of products reset.
        """
        try:
            result = self.db.id_scraped_at.update_many(
                {"$or": [{"notFound": True}, {"notFoundCount": {"$gt": 0}}]},
                {"$set": {"notFound": False, "notFoundCount": 0}}
            )
            self.yeeter.yeet(f"Reset {result.modified_count} not-found products.")
            return result.modified_count
        except Exception as e:
            self.yeeter.error(f"Error resetting not found products: {str(e)}")
            return 0

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
