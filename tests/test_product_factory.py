import json
import os

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

from src.models.nutrition import Nutrition
from src.models.offer import Offer
from src.models.product import Product
from src.models.product_factory import ProductFactory


@pytest.fixture(scope="module")
def db_connection():
    """Fixture to create and return a database connection."""
    # Connect to the test database
    conn = psycopg2.connect(
        host="postgres_test",
        port=5432,
        dbname="test_db",
        user="test_user",
        password="test_password",
    )
    conn.autocommit = False  # Ensure transactions are used
    yield conn
    # Close the database connection after all tests in the module have run
    conn.close()


@pytest.fixture(scope="function")
def cursor(db_connection):
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    # Truncate tables before each test
    cursor.execute("TRUNCATE TABLE product CASCADE;")
    cursor.execute("TRUNCATE TABLE offer CASCADE;")
    cursor.execute("TRUNCATE TABLE nutrients CASCADE;")
    yield cursor
    # Roll back any changes made during the test
    db_connection.rollback()
    cursor.close()


test_cases = [
    {
        "json_file": "100100300000-2024-09-26T12:21:23.json",
        "expected": {
            # Product Details
            "migros_id": "100100300000",
            "name": "Chocolate bars",
            "brand": "Frey",
            "title": "Frey · Chocolate bars · Milk chocolate with hazelnuts",
            "gtins": "7616500010031",
            "scraped_at": "2024-09-26T12:21:23",
            "ingredients": "sugar, whole and ground <strong>hazelnuts</strong> 21%, cocoa butter⁺, skimmed <strong>milk</strong> powder, cocoa mass⁺, concentrated <strong>butter</strong>, emulsifier: lecithins, natural flavouring.\n⁺ Rainforest Alliance Certified\n\nCocoa solids: 30% minimum in chocolate.\nMilk solids: 18% minimum in chocolate.",
            # Offer Details
            "offer_price": 7.2,
            "offer_unit_price": 1.8,
            "offer_promotion_price": 5.8,
            "offer_quantity": "400g",
            # Nutrition Details
            "nutrition_unit": "g",
            "nutrition_quantity": 100,
            "nutrition_kJ": 2360,
            "nutrition_kcal": 567,
            "nutrition_fat": 37,
            "nutrition_saturates": 15,
            "nutrition_carbohydrate": 49,
            "nutrition_sugars": 47,
            "nutrition_fibre": 3.6,
            "nutrition_protein": 7.6,
            "nutrition_salt": 0.17,
        },
    },
    {
        "json_file": "100124900000-2024-10-05T19:23:58.json",
        "expected": {
            # Product Details
            "migros_id": "100124900000",
            "name": "milk chocolate",
            "brand": "Frey",
            "title": "Frey · milk chocolate · with almonds",
            "gtins": "7616500669826",
            "scraped_at": "2024-10-05T19:23:58",
            "ingredients": "sugar, <strong>almonds</strong> 25%, whole <strong>milk </strong>powder, cocoa butter⁺, cocoa mass⁺, ground <strong>hazelnuts</strong>, emulsifier: lecithins, natural flavouring.\n⁺ Rainforest Alliance Certified\n\nCocoa solids: 31% minimum in chocolate.\nMilk solids: 25% minimum in chocolate.",
            # Offer Details
            "offer_price": 2.2,
            "offer_unit_price": 2.2,
            "offer_promotion_price": None,  # No promotion price
            "offer_quantity": "100g",
            # Nutrition Details
            "nutrition_unit": "g",
            "nutrition_quantity": 100,
            "nutrition_kJ": 2377,
            "nutrition_kcal": 571,
            "nutrition_fat": 39,
            "nutrition_saturates": 16,
            "nutrition_carbohydrate": 41,
            "nutrition_sugars": 38,
            "nutrition_fibre": 4.1,
            "nutrition_protein": 12,
            "nutrition_salt": 0.19,
        },
    },
    {
        "json_file": "220622085000-2024-09-16T11:03:35.json",
        "expected": {
            # Product Details
            "migros_id": "220622085000",
            "name": "Pork ragout",
            "brand": "M-Budget",
            "title": "M-Budget · Pork ragout",
            "gtins": "7617027755955",
            "scraped_at": "2024-09-16T11:03:35",
            "ingredients": "Schweinefleisch",
            # Offer Details
            "offer_price": 1.2,
            "offer_unit_price": 1.20,
            "offer_promotion_price": None,  # No promotion price
            "offer_quantity": "100 g",
            # Nutrition Details
            "nutrition_unit": "g",
            "nutrition_quantity": 100,
            "nutrition_kJ": 570,
            "nutrition_kcal": 136,
            "nutrition_fat": 5.7,
            "nutrition_saturates": 2.1,
            "nutrition_carbohydrate": 0.5,
            "nutrition_sugars": 0.5,
            "nutrition_fibre": 0.5,
            "nutrition_protein": 21,
            "nutrition_salt": 0.1,
        },
    },
    {
        "json_file": "100035819.json",
        "expected": {
            # Product Details
            "migros_id": "230500255000",
            "name": "Wiener",
            "brand": "M-Classic",
            "title": "M-Classic · Wiener · 5x (2+2 pieces)",
            "gtins": "7610200070845",
            "scraped_at": "2024-09-15T21:14:06",
            "ingredients": "Schweinefleisch (*A), Wasser, Speck (*B), Rindfleisch (*C), Schwarten (*D), Nitritpökelsalz (Kochsalz, Konservierungsstoff: Natriumnitrit), Würzmischung, Glucose, Antioxidationsmittel: Ascorbinsäure, Stabilisatoren: Diphosphate, Polyphosphate, Hülle: Schafsaitling.\n*Die effektive Herkunft ist auf der Verpackung angegeben.",
            # Offer Details
            "offer_price": 12,
            "offer_unit_price": 1.20,
            "offer_promotion_price": 8.5,  # No promotion price
            "offer_quantity": "1 piece",
            # Nutrition Details
            "nutrition_unit": "g",
            "nutrition_quantity": 100,
            "nutrition_kJ": 1104,
            "nutrition_kcal": 267,
            "nutrition_fat": 23,
            "nutrition_saturates": 8.6,
            "nutrition_carbohydrate": 0.9,
            "nutrition_sugars": 0.9,
            "nutrition_fibre": 0.5,
            "nutrition_protein": 14,
            "nutrition_salt": 1.8,
        },
    },
]


@pytest.mark.parametrize("test_case", test_cases)
def test_create_product_from_json(cursor, test_case):
    """Test the creation of a product from JSON data."""
    json_file = test_case["json_file"]
    expected = test_case["expected"]

    # Load the test data
    data_file = os.path.join(os.path.dirname(__file__), "data", json_file)
    with open(data_file, "r", encoding="utf-8") as f:
        product_json = json.load(f)

    # Instantiate the ProductFactory
    product_factory = ProductFactory()

    # Call the method under test
    product = product_factory.create_product_from_json(product_json, cursor)

    # Assertions for Product
    assert isinstance(product, Product)
    assert product.migros_id == expected["migros_id"]
    assert product.name == expected["name"]
    assert product.brand == expected["brand"]
    assert product.title == expected["title"]
    assert product.gtins == expected["gtins"]
    assert product.scraped_at.isoformat() == expected["scraped_at"]
    assert expected["ingredients"] in product.ingredients

    # Assertions for Offer
    assert isinstance(product.offer, Offer)
    assert product.offer.price == expected["offer_price"]
    assert product.offer.unit_price == expected["offer_unit_price"]
    assert product.offer.promotion_price == expected["offer_promotion_price"]
    assert product.offer.quantity == expected["offer_quantity"]

    # Assertions for Nutrition
    assert isinstance(product.nutrition, Nutrition)
    assert product.nutrition.unit == expected["nutrition_unit"]
    assert product.nutrition.quantity == expected["nutrition_quantity"]
    assert product.nutrition.kJ == expected["nutrition_kJ"]
    assert product.nutrition.kcal == expected["nutrition_kcal"]
    assert product.nutrition.fat == expected["nutrition_fat"]
    assert product.nutrition.saturates == expected["nutrition_saturates"]
    assert product.nutrition.carbohydrate == expected["nutrition_carbohydrate"]
    assert product.nutrition.sugars == expected["nutrition_sugars"]
    assert product.nutrition.fibre == expected["nutrition_fibre"]
    assert product.nutrition.protein == expected["nutrition_protein"]
    assert product.nutrition.salt == expected["nutrition_salt"]

    # Verify data inserted into the database
    # Check that the product was inserted
    cursor.execute(
        "SELECT * FROM product WHERE migros_id = %s AND scraped_at = %s;",
        (product.migros_id, product.scraped_at),
    )
    product_row = cursor.fetchone()
    assert product_row is not None

    # Check that the offer was inserted
    cursor.execute("SELECT * FROM offer WHERE id = %s;", (product.offer.id,))
    offer_row = cursor.fetchone()
    assert offer_row is not None

    # Check that the nutrition was inserted
    cursor.execute("SELECT * FROM nutrients WHERE id = %s;", (product.nutrition.id,))
    nutrition_row = cursor.fetchone()
    assert nutrition_row is not None
