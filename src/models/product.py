import logging
from dataclasses import dataclass, field

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
    gtins: str = ""
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
