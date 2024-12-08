import logging

from psycopg2 import connect
from psycopg2.extensions import cursor as PostgresCursor
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

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
        self.mongo_client = MongoClient(mongo_uri)
        self.mongo_db = self.mongo_client[mongo_db_name]
        self.postgres_cursor = postgres_cursor

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
                logging.error(f"Error syncing product {_id}: {e}")

        logging.info("Product synchronization complete.")

    def close_connections(self):
        """Close connections to MongoDB and PostgreSQL."""
        try:
            self.mongo_client.close()
            logging.info("MongoDB connection closed.")
        except Exception as e:
            logging.error(f"Error closing MongoDB connection: {e}")


from psycopg2 import connect
from psycopg2.extras import RealDictCursor

MONGO_URI = "mongodb://mongo:27017"
MONGO_DB_NAME = "productsandcategories"
POSTGRES_CONFIG = {
    "dbname": "postgres_db",
    "user": "postgres",
    "password": "password",
    "host": "postgres",
    "port": 5432,
}


def main():
    # Connect to PostgreSQL
    with connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cursor:
            # Initialize the sync service
            sync_service = MongoToPostgresSync(MONGO_URI, MONGO_DB_NAME, cursor)

            # Perform synchronization
            sync_service.sync_products()

            # Commit changes to PostgreSQL
            conn.commit()

            # Close connections
            sync_service.close_connections()


if __name__ == "__main__":
    main()
