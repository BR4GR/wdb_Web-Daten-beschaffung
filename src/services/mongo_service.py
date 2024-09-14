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
        self.db.categories.insert_one(category_data)
