import time
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.server_api import ServerApi

from src.utils.yeeter import Yeeter, yeet


class MongoService:
    def __init__(self, uri: str, db_name: str, yeeter: Yeeter):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.yeeter = yeeter

    def close(self):
        self.client.close()

    def current_day_in_iso(self):
        """Return the current day in ISO format."""
        return datetime.now(timezone.utc).date().isoformat()

    # ----------------------------------------------
    #       categories
    # ----------------------------------------------

    def check_category_exists(self, category_id: int) -> bool:
        """Check if a category with the given ID already exists in the MongoDB collection."""
        return self.db.categories.find_one({"id": category_id}) is not None

    def insert_category(self, category_data: dict) -> None:
        """Insert a new category document into the categories collection."""
        if not self.check_category_exists(category_data["id"]):
            self.db.categories.insert_one(category_data)
            self.yeeter.yeet(f"Inserted new category: {category_data['id']}")

    # ----------------------------------------------
    #       category_tracker
    # ----------------------------------------------

    def insert_new_base_categories(self, new_categories: list) -> None:
        """Insert new base categories into the category_tracker collection."""
        for category in new_categories:
            # Check if the category exists by its ID
            if not self.db.category_tracker.find_one({"id": category["id"]}):
                # If not found, insert the full category with last_scraped set to None
                category["last_scraped"] = (
                    None  # Initialize last_scraped as None (empty)
                )
                self.db.category_tracker.insert_one(category)

    def get_untracked_base_categories(self, base_categories: list) -> list:
        """Fetch base categories that are not yet tracked in the category_tracker."""
        tracked_categories_ids = self.db.category_tracker.distinct("id")
        return [
            category
            for category in base_categories
            if category["id"] not in tracked_categories_ids
        ]

    def get_unscraped_categories(self) -> list:
        """Fetch categories that have never been scraped (i.e., last_scraped is None)."""
        return list(self.db.category_tracker.find({"last_scraped": None}))

    def mark_category_as_scraped(self, category_id: int, current_day) -> None:
        """Mark a category as scraped today or insert if it's new."""
        self.db.category_tracker.update_one(
            {"id": category_id},
            {"$set": {"last_scraped": current_day}},
            upsert=True,
        )

    def get_oldest_scraped_category(self) -> dict:
        """
        Fetch the category that was scraped the longest time ago.
        also return a category that has never been scraped.
        """
        return self.db.category_tracker.find_one(
            sort=[("last_scraped", 1)],
        )

    # ----------------------------------------------
    #       products
    # ----------------------------------------------

    def check_product_exists(self, migros_id: str) -> bool:
        """Check if a product with the given migrosId already exists in the MongoDB collection."""
        return self.db.products.find_one({"migrosId": migros_id}) is not None

    def insert_product(self, product_data: dict) -> None:
        """Insert a new product document if the price is new or the product doesn't exist
        in the db jet."""
        migros_id = product_data.get("migrosId")
        description = product_data.get("description")
        name = product_data.get("name")
        if not migros_id:
            self.yeeter.error("Product does not contain migrosId, skipping insertion.")
            return

        # check if product has offer
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
            self.yeeter.yeet(f"Inserted new product {name} with migrosId: {migros_id}")

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

    def get_latest_product_entry_by_migros_id(self, migros_id: str) -> dict:
        """Fetch the latest product entry for a given migrosId, based on the date it was added."""
        return self.db.products.find_one(
            {"migrosId": migros_id}, sort=[("dateAdded", -1)]
        )

    def get_all_known_migros_ids(self) -> list:
        """Fetch all migrosIds of the known products."""
        return self.db.products.distinct("migrosId")

    def get_products_not_scraped_in_days(
        self, days: int, limit: int = 100, only_edible=True
    ) -> list:
        """Retrieve migrosIds of products that haven't been scraped in the last 'x' days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Base query to get products not scraped in 'x' days
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

    # ----------------------------------------------
    #       unit_price_history
    # ----------------------------------------------

    def get_price_history(self, migros_id: str):
        """Fetch the price history for a given product."""
        return list(
            self.db.unit_price_history.find({"migrosId": migros_id}).sort(
                "dateChanged", 1
            )
        )

    # ----------------------------------------------
    #       scraped_ids
    # ----------------------------------------------

    def save_scraped_product_id(self, migros_id: str) -> None:
        """Save the scraped product ID with the current date."""
        current_date = datetime.now(timezone.utc)
        self.db.id_scraped_at.update_one(
            {"migrosId": migros_id},
            {"$set": {"lastScraped": current_date}},
            upsert=True,
        )

    def is_product_scraped_last_24_hours(self, migros_id: str) -> bool:
        """Check if a product with the given migrosId has been scraped in the last 24 hours."""
        # Get the current time and calculate the cutoff time (24 hours ago)
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=24)

        # Query for products that were scraped within the last 24 hours
        return (
            self.db.id_scraped_at.find_one(
                {
                    "migrosId": migros_id,
                    "lastScraped": {
                        "$gte": cutoff_time
                    },  # Check if lastScraped is greater than or equal to the cutoff
                }
            )
            is not None
        )

    def retrieve_scraped_ids_last_24_hours(self) -> list[int]:
        """Retrieve all scraped_ids entries that have been scraped in the last 24 hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        # Find all entries where lastScraped is within the last 24 hours
        return [
            scraped_data["migrosId"]
            for scraped_data in self.db.id_scraped_at.find(
                {"lastScraped": {"$gte": cutoff_time}}
            )
            if "migrosId" in scraped_data  # Ensure the key exists
        ]

    # ----------------------------------------------
    #       request_counts
    # ----------------------------------------------

    def get_request_count(self, date: str) -> int:
        """Retrieve the request count for the given date."""
        record = self.db.request_counts.find_one({"date": date})
        if record:
            return record.get("count", 0)
        return 0

    def increment_request_count(self, date: str, count: int = 1) -> None:
        """Increment the request count for the given date."""
        self.db.request_counts.update_one(
            {"date": date}, {"$inc": {"count": count}}, upsert=True
        )

    # deleteagain

    # Migrate data from scraped_ids to id_scraped_at
    def migrate_scraped_ids_to_new_format(self):
        # Aggregate to get the most recent scrape date for each migrosId
        pipeline = [
            {
                "$group": {
                    "_id": "$migrosId",
                    "lastScraped": {"$max": "$date"},  # Get the most recent 'date'
                }
            }
        ]

        # Run the aggregation pipeline
        results = self.db.scraped_ids.aggregate(pipeline)
        self.yeeter.yeet("Starting migration of scraped_ids to id_scraped_at...")

        # Convert the results to a list for the length count (but don't consume the cursor)
        results_list = list(results)
        self.yeeter.yeet(f"Found {len(results_list)} results")

        # Process the aggregated results
        for result in results_list:  # Use the list version of the results here
            migros_id = result["_id"]
            last_scraped = result.get("lastScraped")

            self.yeeter.yeet(
                f"Processing migrosId {migros_id} with last scraped: {last_scraped}"
            )

            # Convert 'lastScraped' to datetime if it's a string
            self.yeeter.yeet(f"is str = {isinstance(last_scraped, str)}")
            if isinstance(last_scraped, str):
                try:
                    last_scraped = datetime.strptime(last_scraped, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    print(f"Skipping document with invalid date format: {last_scraped}")
                    continue

            # If no valid 'lastScraped' set last scraped to 1 year ago
            if not last_scraped:
                self.yeeter.yeet("No valid 'lastScraped' found, setting to 1 year ago.")
                last_scraped = datetime.now(timezone.utc) - timedelta(days=365)

            # Create the new document for id_scraped_at
            new_doc = {
                "migrosId": migros_id,
                "lastScraped": last_scraped,
            }

            # Insert into the new collection
            self.db.id_scraped_at.update_one(
                {"migrosId": migros_id},  # Match by 'migrosId' to avoid duplicates
                {"$set": new_doc},
                upsert=True,
            )
            self.yeeter.yeet(
                f"Migrated migrosId {migros_id}, last scraped: {last_scraped}"
            )

        print("Migration complete.")


if __name__ == "__main__":
    yeeter = Yeeter()
    ms = MongoService("mongodb://localhost:27017", "exampledb", yeeter)
    migros_id = "123456"
    ms.yeeter.yeet(
        f"\033[1;32mNew unit price detected for product with migrosId: {migros_id}. Logged price change.\033[0m"
    )
    ms.yeeter.bugreport("fix bugs")
    ms.yeeter.alarm("ALAAAARM")
