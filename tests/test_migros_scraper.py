import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from src.migros_scraper import MigrosScraper
from src.services.mongo_service import MongoService
from src.utils.yeeter import Yeeter


@pytest.fixture(scope="module")
def scraper():
    """
    Fixture to initialize and clean up the MigrosScraper instance.
    """
    # Setup dependencies
    yeeter = Yeeter()
    mongo_service = MongoService("mongodb://test_mongo:27017", "testdb", yeeter)

    # Initialize the scraper
    scraper = MigrosScraper(
        mongo_service=mongo_service,
        yeeter=yeeter,
        average_request_sleep_time=0,
        disable_check_for_product_cards=True,
    )

    # Clean up all collections before each test
    mongo_service.db.categories.delete_many({})
    mongo_service.db.category_tracker.delete_many({})
    mongo_service.db.products.delete_many({})
    mongo_service.db.unit_price_history.delete_many({})
    mongo_service.db.id_scraped_at.delete_many({})
    mongo_service.db.request_counts.delete_many({})
    mongo_service.db.id_scraped_at.delete_many({})

    yield scraper

    # Cleanup after tests
    scraper.close()
    mongo_service.close()


def test_load_main_page(scraper):
    """
    Test that the scraper correctly loads the main page and finds expected elements.
    """
    scraper.load_main_page()
    print(scraper.driver.page_source)

    # Check if a known element exists on the page (e.g., a navigation menu or header).
    element = scraper.driver.find_element(By.ID, "splash")
    assert (
        element is not None
    ), "Main navigation not found. Page may not have loaded correctly."


def test_get_and_store_base_categories(scraper):
    """
    Test fetching and storing base categories.
    """
    scraper.get_and_store_base_categories()

    # Verify base categories are stored in MongoDB
    stored_categories = list(scraper.mongo_service.db.categories.find())
    assert len(stored_categories) > 0, "No categories were stored in the database."


def test_scrape_category_via_url(scraper):
    """
    Test scraping a category by URL.
    """
    category_url = "https://www.migros.ch/en/category/fruits-vegetables"
    slugs = scraper.scrape_category_via_url(category_url, "fruit-vegetables")
    print("slugs")
    print(slugs)
    print(" end slugs")

    # Check if slugs are returned
    assert len(slugs) > 0, "No subcategory slugs were found for the category."


def test_scrape_product_by_id(scraper):
    """
    Test scraping a single product by its Migros ID.
    """
    test_product_id = "104101900000"  # Example product ID
    scraper.scrape_product_by_id(test_product_id)

    # Check if the product was stored in MongoDB
    product = scraper.mongo_service.db.products.find_one({"migrosId": test_product_id})
    assert product is not None, f"Product with ID {test_product_id} was not stored."


def test_make_request_and_validate(scraper):
    """
    Test making a request to a valid URL and validating its response.
    """
    test_url = scraper.BASE_URL
    scraper.make_request_and_validate(test_url)
    print("current url")
    print(scraper.driver.current_url)
    print("end current url")
    print("test url")
    print(test_url)
    print("end test url")

    # Check if the current URL in the driver matches the test URL
    assert scraper.driver.current_url.rstrip("/") == test_url.rstrip(
        "/"
    ), "URL validation failed after request."


def test_current_day_in_iso(scraper):
    """
    Test that the current day is returned in ISO format.
    """
    iso_date = scraper.current_day_in_iso()
    assert isinstance(iso_date, str), "Current day in ISO format is not a string."


def test_handle_unexpected_error(scraper):
    """
    Test error handling by forcing an invalid operation.
    """
    invalid_url = "https://invalid.migros.ch/"
    try:
        scraper.make_request_and_validate(invalid_url)
    except SystemExit as e:
        assert "Scraper stopped" in str(e), "Unexpected error was not handled properly."
