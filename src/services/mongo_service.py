import time

from pymongo import MongoClient
from pymongo.server_api import ServerApi


class MongoService:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri, server_api=ServerApi("1"))
        self.db = self.client[db_name]

    def close(self):
        self.client.close()

    def check_category_exists(self, category_id: int) -> bool:
        """Check if a category with the given ID already exists in the MongoDB collection."""
        return self.db.categories.find_one({"id": category_id}) is not None

    def insert_category(self, category_data: dict) -> None:
        """Insert a new category document into the categories collection."""
        if not self.check_category_exists(category_data["id"]):
            self.db.categories.insert_one(category_data)

    def check_product_exists(self, migros_id: str) -> bool:
        """Check if a product with the given migrosId already exists in the MongoDB collection."""
        return self.db.products.find_one({"migrosId": migros_id}) is not None

    def get_latest_product_entry(self, migros_id: str) -> dict:
        """Fetch the latest product entry for a given migrosId, based on the date it was added."""
        return self.db.products.find_one(
            {"migrosId": migros_id}, sort=[("dateAdded", -1)]
        )

    def insert_product(self, product_data: dict) -> None:
        """Insert a new product document if the unitPrice is new or the product doesn't exist."""
        migros_id = product_data.get("migrosId")
        if not migros_id:
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "Product does not contain migrosId, skipping insertion.",
            )
            return

        existing_product = self.get_latest_product_entry(migros_id)
        new_unit_price = (
            product_data.get("offer", {})
            .get("price", {})
            .get("unitPrice", {})
            .get("value")
        )

        if not existing_product:
            # Product doesn't exist, insert as new
            product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.db.products.insert_one(product_data)
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Inserted new product with migrosId: {migros_id}",
            )

        elif (
            existing_product.get("offer", {})
            .get("price", {})
            .get("unitPrice", {})
            .get("value")
            != new_unit_price
        ):
            # Unit price has changed, insert as new and log price change
            product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.db.products.insert_one(product_data)

            # Log the price change in the 'unit_price_history' collection
            price_change_entry = {
                "migrosId": migros_id,
                "newPrice": new_unit_price,
                "dateChanged": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            self.db.unit_price_history.insert_one(price_change_entry)
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"New unit price detected for product with migrosId: {migros_id}. Logged price change.",
            )

        else:
            # Product exists with the same price, skip insertion
            print(
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                f"Product with migrosId {migros_id} already exists with the same unitPrice. Skipping insertion.",
            )

    def get_price_history(self, migros_id: str):
        """Fetch the price history for a given product."""
        return list(
            self.db.unit_price_history.find({"migrosId": migros_id}).sort(
                "dateChanged", 1
            )
        )

    def save_scraped_product_id(self, migros_id: str, date: str) -> None:
        """Save the scraped product ID with the date to prevent scraping the same product multiple times per day.
        this is needed because we start multiple actions a day"""
        if not self.is_product_scraped_today(migros_id, date):
            self.db.scraped_ids.insert_one({"migrosId": migros_id, "date": date})

    def is_product_scraped_today(self, migros_id: str, date: str) -> bool:
        """Check if a product with the given migrosId has already been scraped today."""
        return (
            self.db.scraped_ids.find_one({"migrosId": migros_id, "date": date})
            is not None
        )

    def reset_scraped_ids(self, current_date: str):
        """Remove all scraped_ids entries that are not from the current date."""
        self.db.scraped_ids.delete_many({"date": {"$ne": current_date}})

    def retrieve_todays_scraped_ids(self, current_date: str) -> list[int]:
        """Retrieve all scraped_ids entries that are from the current date."""
        return [
            scraped_data["migrosId"]
            for scraped_data in self.db.scraped_ids.find({"date": current_date})
            if "migrosId" in scraped_data  # Ensure the key exists
        ]

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

    def get_oldest_scraped_category(self) -> dict:
        """Fetch the category that was scraped the longest time ago."""
        return self.db.category_tracker.find_one(
            sort=[("last_scraped", 1)],
        )

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
