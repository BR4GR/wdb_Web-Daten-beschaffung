import logging
from dataclasses import dataclass, field


@dataclass
class Nutrition:
    unit: str = None
    quantity: int = None
    kcal: int = None
    kJ: int = None
    fat: str = None
    saturates: str = None
    carbohydrate: str = None
    sugars: str = None
    fibre: str = None
    protein: str = None
    salt: str = None
    id: int = field(init=False, default=None)

    def save_to_db(self, cursor):
        """Insert nutrients data into PostgreSQL and return the nutrient ID."""
        try:
            cursor.execute(
                """
                INSERT INTO nutrients (
                    unit, quantity, kcal, kJ, fat, saturates, carbohydrate, sugars, fibre, protein, salt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    self.unit,
                    self.quantity,
                    self.kcal,
                    self.kJ,
                    self.fat,
                    self.saturates,
                    self.carbohydrate,
                    self.sugars,
                    self.fibre,
                    self.protein,
                    self.salt,
                ),
            )
            result = cursor.fetchone()
            if result is None:
                raise Exception("Failed to fetch offer ID after insert.")
            self.id = result["id"]
            logging.info(f"Nutrients inserted with ID {self.id}.")
            return self.id
        except Exception as e:
            logging.error(f"Error inserting nutrients: {e}", exc_info=True)
            raise

    def update_in_postgres(self, cursor):
        """Update a nutrition entry in PostgreSQL."""
        if self.id is None:
            return self.save_to_db(cursor)
        try:
            cursor.execute(
                """
                UPDATE nutrients
                SET unit = %s, quantity = %s, kcal = %s, kJ = %s, fat = %s, saturates = %s,
                    carbohydrate = %s, sugars = %s, fibre = %s, protein = %s, salt = %s
                WHERE id = %s
                RETURNING id;
                """,
                (
                    self.unit,
                    self.quantity,
                    self.kcal,
                    self.kJ,
                    self.fat,
                    self.saturates,
                    self.carbohydrate,
                    self.sugars,
                    self.fibre,
                    self.protein,
                    self.salt,
                    self.id,
                ),
            )
            result = cursor.fetchone()
            if result is None:
                raise Exception("Failed to fetch nutrient ID after update.")
            self.id = result["id"]
            logging.info(f"Nutrients updated with ID {self.id}.")
            return self.id
        except Exception as e:
            logging.error(f"Error updating nutrients: {e}", exc_info=True)
            raise
