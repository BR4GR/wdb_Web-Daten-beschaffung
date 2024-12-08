import logging
import os
import pdb
import traceback

from dotenv import load_dotenv
from psycopg2 import connect
from psycopg2.extensions import cursor as PostgresCursor
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from pymongo.server_api import ServerApi

from src.models.category import Category
from src.models.product import Product
from src.models.product_factory import ProductFactory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class MongoToPostgresSync:
    def __init__(
        self, mongo_uri: str, mongo_db_name: str, postgres_cursor: PostgresCursor
    ):
        """
        Initialize the MongoToPostgresSync class.

        Args:
            mongo_uri (str): The MongoDB connection URI.
            mongo_db_name (str): The name of the MongoDB database.
            postgres_cursor (PostgresCursor): The PostgreSQL cursor for database operations.
        """
        self.mongo_client = MongoClient(mongo_uri, server_api=ServerApi("1"))
        self.mongo_db = self.mongo_client[mongo_db_name]
        self.postgres_cursor = postgres_cursor

    def sync_categories(self):
        """
        Sync categories from MongoDB to PostgreSQL.
        Compares data in MongoDB with PostgreSQL and updates/inserts as necessary.
        """
        try:
            mongo_categories = self.mongo_db.categories.find(
                {}, {"_id": 0}
            )  # Fetch all categories
            logging.info(
                f"Found {self.mongo_db.categories.count_documents({})} categories in MongoDB."
            )

            for mongo_category in mongo_categories:
                try:
                    logging.info(f"Processing category: {mongo_category.get('id')}.")
                    # Deserialize category data
                    category = Category.from_json(mongo_category)

                    # Save category to PostgreSQL
                    category.save_to_db(self.postgres_cursor)
                except Exception as e:
                    logging.error(
                        f"Error syncing category {mongo_category.get('id')}: {e}"
                    )
        except Exception as e:
            logging.error(f"Error during category sync: {e}")

    def sync_products(self):
        """
        Synchronize products from MongoDB to PostgreSQL.
        """
        logging.info("Starting product synchronization...")

        # Fetch all products from MongoDB
        mongo_products = self.mongo_db.products.find(
            {}, {"_id": 1, "migrosId": 1, "dateAdded": 1}
        )
        for mongo_product in mongo_products:
            try:
                mongo_product_id = mongo_product["_id"]
                migros_id = mongo_product["migrosId"]
                scraped_at = mongo_product["dateAdded"]
                logging.info(f"Processing product: {migros_id}, {scraped_at}.")

                # Fetch full product data from MongoDB
                full_mongo_product = self.mongo_db.products.find_one(
                    {"_id": mongo_product_id}
                )
                if not full_mongo_product:
                    logging.warning(f"Product {mongo_product_id} not found in MongoDB.")
                    continue

                # Fetch the corresponding product from PostgreSQL
                sql_product = Product.get_by_migros_id_and_scrape_date(
                    self.postgres_cursor, migros_id, scraped_at
                )

                # Convert MongoDB product to a Product object
                mongo_product_obj = ProductFactory.create_product_from_json(
                    full_mongo_product
                )

                # Sync logic: insert, update, or skip
                if not sql_product:
                    logging.info(f"Inserting new product: {migros_id}, {scraped_at}.")
                    mongo_product_obj.save_to_db(self.postgres_cursor)
                elif not mongo_product_obj.equals(sql_product):
                    logging.info(f"Updating product: {migros_id}, {scraped_at}.")
                    mongo_product_obj.update_in_postgres(self.postgres_cursor)
                else:
                    logging.info(
                        f"Product {migros_id}, {scraped_at} is already up-to-date."
                    )
            except Exception as e:
                logging.error(f"Error syncing product {mongo_product_id}: {e}")
                self.log_debug_info()

        logging.info("Product synchronization complete.")

    def close_connections(self):
        """Close connections to MongoDB and PostgreSQL."""
        try:
            self.mongo_client.close()
            logging.info("MongoDB connection closed.")
        except Exception as e:
            logging.error(f"Error closing MongoDB connection: {e}")
            self.log_debug_info()

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


POSTGRES_CONFIG = {
    "dbname": "postgres_db",
    "user": "postgres",
    "password": "password",
    "host": "postgres",
    "port": 5432,
}


def main():
    load_dotenv()

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
    # Connect to PostgreSQL
    with connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cursor:
            # Initialize the sync service
            sync_service = MongoToPostgresSync(MONGO_URI, MONGO_DB_NAME, cursor)

            # Perform category synchronization
            sync_service.sync_categories()

            # Perform synchronization
            # sync_service.sync_products()

            # Commit changes to PostgreSQL
            conn.commit()

            # Close connections
            sync_service.close_connections()


if __name__ == "__main__":
    main()
