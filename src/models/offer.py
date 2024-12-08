import logging
from dataclasses import dataclass, field


@dataclass
class Offer:
    price: float = None
    quantity: str = None
    unit_price: float = None
    promotion_price: float = None
    promotion_unit_price: float = None
    id: int = field(init=False, default=None)

    def save_to_db(self, cursor):
        """Insert offer data into PostgreSQL and return the offer ID."""
        try:
            cursor.execute(
                """
                INSERT INTO offer (
                    price, quantity, unit_price, promotion_price, promotion_unit_price
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    self.price,
                    self.quantity,
                    self.unit_price,
                    self.promotion_price,
                    self.promotion_unit_price,
                ),
            )
            result = cursor.fetchone()
            if result is None:
                raise Exception("Failed to fetch offer ID after insert.")
            self.id = result["id"]
            logging.info(f"Offer inserted with ID {self.id}.")
            return self.id
        except Exception as e:
            logging.error(f"Error inserting Offer: {e}", exc_info=True)
            raise

    def update_in_postgres(self, cursor):
        """Update an offer entry in PostgreSQL."""
        if self.id is None:
            return self.save_to_db(cursor)
        try:
            cursor.execute(
                """
                UPDATE offer
                SET price = %s, quantity = %s, unit_price = %s,
                    promotion_price = %s, promotion_unit_price = %s
                WHERE id = %s;
                """,
                (
                    self.price,
                    self.quantity,
                    self.unit_price,
                    self.promotion_price,
                    self.promotion_unit_price,
                    self.id,
                ),
            )
            logging.info(f"Offer with ID {self.id} updated.")
            return self.id
        except Exception as e:
            logging.error(f"Error updating offer: {e}", exc_info=True)
            raise
