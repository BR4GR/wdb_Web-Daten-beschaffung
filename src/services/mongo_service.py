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
            print("Product does not contain migrosId, skipping insertion.")
            return

        existing_product = self.get_latest_product_entry(migros_id)
        new_unit_price = (
            product_data.get("offer", {})
            .get("price", {})
            .get("unitPrice", {})
            .get("value")
        )

        if (
            not existing_product
            or existing_product.get("offer", {})
            .get("price", {})
            .get("unitPrice", {})
            .get("value")
            != new_unit_price
        ):
            # Add the current timestamp or 'dateAdded' to the product data
            product_data["dateAdded"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self.db.products.insert_one(product_data)
            print(f"Inserted new product with migrosId: {migros_id}")
        else:
            print(
                f"Product with migrosId {migros_id} already exists with the same unitPrice. Skipping insertion."
            )

    # Save scraped product ID with the date
    def save_scraped_product_id(self, migros_id: str, date: str) -> None:
        if not self.is_product_scraped_today(migros_id, date):
            self.db.scraped_ids.insert_one({"migrosId": migros_id, "date": date})

    # Check if a product has been scraped today
    def is_product_scraped_today(self, migros_id: str, date: str) -> bool:
        return (
            self.db.scraped_ids.find_one({"migrosId": migros_id, "date": date})
            is not None
        )

    # Remove all scraped IDs from a previous day
    def reset_scraped_ids(self, current_date: str):
        self.db.scraped_ids.delete_many({"date": {"$ne": current_date}})
