import logging
from dataclasses import dataclass, field


@dataclass
class Category:
    name: str = None
    path: str = None
    slug: str = None
    id: int = field(default=None)

    def save_to_db(self, cursor):
        """Insert category data into PostgreSQL and return the category ID."""
        try:
            cursor.execute(
                """
                INSERT INTO category (name, path, slug)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (self.name, self.path, self.slug),
            )
            result = cursor.fetchone()
            if result is None:
                raise Exception("Failed to fetch category ID after insert.")
            self.id = result["id"]
            logging.info(f"Category '{self.name}' inserted with ID {self.id}.")
            return self.id
        except Exception as e:
            logging.error(f"Error inserting Category: {e}", exc_info=True)
            raise

    # unserialize json data
    @staticmethod
    def from_json(json_data):
        return Category(
            id=json_data.get("id"),
            name=json_data.get("name"),
            path=json_data.get("path"),
            slug=json_data.get("slug"),
        )
