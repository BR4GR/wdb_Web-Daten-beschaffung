import logging
from dataclasses import dataclass, field

import psycopg2
from psycopg2.extras import RealDictCursor

from src.models.product_factory import ProductFactory
from src.models.nutrition import Nutrition
from src.models.offer import Offer

# Set up logging (if not already configured)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass
class Product:
    migros_id: str
    name: str
    brand: str = None
    title: str = None
    origin: str = None
    description: str = None
    ingredients: str = None
    gtins: str = None
    scraped_at: str = None
    offer: Offer = None
    nutrition: Nutrition = None

    def save_to_db(self, cursor):
        """Insert product data and related offer and nutrition into PostgreSQL."""
        try:
            # Save Offer and Nutrition first, if they exist
            offer_id = None
            if self.offer:
                offer_id = self.offer.save_to_db(cursor)

            nutrient_id = None
            if self.nutrition:
                nutrient_id = self.nutrition.save_to_db(cursor)

            # Insert Product
            cursor.execute(
                """
                INSERT INTO product (
                    migros_id, name, brand, title, origin, description, ingredients,
                    nutrient_id, offer_id, gtins, scraped_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    self.migros_id,
                    self.name,
                    self.brand,
                    self.title,
                    self.origin,
                    self.description,
                    self.ingredients,
                    nutrient_id,
                    offer_id,
                    self.gtins,
                    self.scraped_at,
                ),
            )
            logging.info(
                f"Product '{self.name}' and related data inserted into database."
            )
        except Exception as e:
            logging.error(f"Error inserting product '{self.name}': {e}", exc_info=True)
            raise

    def update_in_postgres(self, cursor):
        """Update an existing product in PostgreSQL."""
        # Update or insert the related nutrition and offer
        self.nutrition_id = (
            self.nutrition.update_in_postgres(cursor) if self.nutrition else None
        )
        self.offer_id = self.offer.update_in_postgres(cursor) if self.offer else None

        # Update the product itself
        cursor.execute(
            """
            UPDATE product
            SET name = %s, brand = %s, title = %s, origin = %s,
                description = %s, ingredients = %s, gtins = %s,
                nutrient_id = %s, offer_id = %s
            WHERE migros_id = %s AND scraped_at = %s;
            """,
            (
                self.name,
                self.brand,
                self.title,
                self.origin,
                self.description,
                self.ingredients,
                self.gtins,
                self.nutrition_id,
                self.offer_id,
                self.migros_id,
                self.scraped_at,
            ),
        )

    def equals(self, other: "Product") -> bool:
        """Compare two Product objects for equality."""
        return (
            self.migros_id == other.migros_id
            and self.name == other.name
            and self.brand == other.brand
            and self.title == other.title
            and self.origin == other.origin
            and self.description == other.description
            and self.ingredients == other.ingredients
            and self.gtins == other.gtins
            and self.scraped_at == other.scraped_at
            and self.nutrition == other.nutrition
            and self.offer == other.offer
        )

    @staticmethod
    def sync_from_mongo_to_sql(postgres_cursor, mongo_db):
        """
        Sync products from MongoDB to PostgreSQL.
        Compares data in MongoDB with PostgreSQL and updates/inserts as necessary.
        """
        mongo_products = mongo_db.products.find(
            {}, {"_id": 1, "migrosId": 1, "dateAdded": 1}
        )
        logging.info(f"Found {mongo_products.count()} products in MongoDB.")

        for mongo_product in mongo_products:
            try:
                migros_id = mongo_product.get("migrosId")
                scraped_at = mongo_product.get("dateAdded")

                # Fetch full product data from MongoDB
                full_mongo_product = mongo_db.products.find_one(
                    {"_id": mongo_product["_id"]}
                )
                if not full_mongo_product:
                    logging.warning(
                        f"Product {mongo_product['_id']} not found in MongoDB."
                    )
                    continue

                # Fetch the corresponding product from PostgreSQL
                sql_product = Product.get_by_migros_id_and_scrape_date(
                    postgres_cursor, migros_id, scraped_at
                )

                # Convert MongoDB product to Product object
                mongo_product_obj = ProductFactory.create_product_from_json(
                    full_mongo_product
                )

                # Sync product if necessary
                if not sql_product:
                    logging.info(f"Inserting new product: {migros_id}, {scraped_at}.")
                    mongo_product_obj.save_to_db(postgres_cursor)
                elif not mongo_product_obj.equals(sql_product):
                    logging.info(f"Updating product: {migros_id}, {scraped_at}.")
                    mongo_product_obj.update_in_postgres(postgres_cursor)
                else:
                    logging.info(
                        f"Product {migros_id}, {scraped_at} is already up-to-date."
                    )
            except Exception as e:
                logging.error(
                    f"Error syncing product {mongo_product['_id']}: {e}", exc_info=True
                )

    @staticmethod
    def get_by_migros_id_and_scrape_date(cursor, migros_id, scraped_at) -> "Product":
        """
        Fetch a product from PostgreSQL by Migros ID and scrape date.
        Includes nutrition and offer details.
        """
        try:
            cursor.execute(
                """
                SELECT * FROM product
                WHERE migros_id = %s AND scraped_at = %s;
                """,
                (migros_id, scraped_at),
            )
            row = cursor.fetchone()
            if row:
                return Product(
                    migros_id=row["migros_id"],
                    name=row["name"],
                    brand=row["brand"],
                    title=row["title"],
                    origin=row["origin"],
                    description=row["description"],
                    ingredients=row["ingredients"],
                    gtins=row["gtins"],
                    scraped_at=row["scraped_at"],
                    nutrition=(
                        Nutrition.get_by_id(cursor, row["nutrient_id"])
                        if row["nutrient_id"]
                        else None
                    ),
                    offer=(
                        Offer.get_by_id(cursor, row["offer_id"])
                        if row["offer_id"]
                        else None
                    ),
                )
        except Exception as e:
            logging.error(f"Error fetching product by Migros ID and scrape date: {e}")
        return None
