import pytest
from pymongo import MongoClient

from src.services.mongo_service import MongoService
from src.utils.yeeter import Yeeter
from tests.data.base_categories import base_categories
from tests.data.higher_level_categories import higher_level_categories
from tests.data.koriander import koriander
from tests.data.oliveoil import oliveoil
from tests.data.oliveoil_offer_missing import oliveoil_offer_missing
from tests.data.oliveoil_price_change import oliveoil_price_change
from tests.data.oliveoil_price_change_2 import oliveoil_price_change_2
from tests.data.penne import penne


@pytest.fixture(scope="function")
def mongo_service():
    """
    Pytest fixture that provides a MongoService instance connected to the test database.
    Cleans up all collections before and after each test.

    Yields:
        MongoService: An instance of the MongoService class.
    """
    client: MemoryError = MongoClient("mongodb://mongo:27017/")
    yeeter: Yeeter = Yeeter()  # Use a real Yeeter instance

    # Initialize the MongoService with test database
    mongo_service: MongoService = MongoService(
        uri="mongodb://mongo:27017", db_name="testdb", yeeter=yeeter
    )

    # Clean up all collections before each test
    mongo_service.db.categories.delete_many({})
    mongo_service.db.category_tracker.delete_many({})
    mongo_service.db.products.delete_many({})
    mongo_service.db.unit_price_history.delete_many({})
    mongo_service.db.scraped_ids.delete_many({})
    mongo_service.db.request_counts.delete_many({})

    yield mongo_service

    # Clean up after the test
    mongo_service.close()

    # ----------------------------------------------
    #       categories
    # ----------------------------------------------


def test_check_category_exists_empty_db(mongo_service: MongoService):
    """
    Test case to verify that a category does not exist in an empty MongoDB collection.

    This test ensures that when no categories are inserted into the database,
    the check_category_exists function returns False.
    """
    category_id = base_categories[0]["id"]
    assert not mongo_service.check_category_exists(category_id)


def test_check_category_exists_after_insert(mongo_service: MongoService):
    """
    Test case to verify that a category exists after it has been inserted into the MongoDB collection.

    This test first inserts a category into the MongoDB collection and then ensures
    that the check_category_exists function returns True for the inserted category.
    """
    category_data = base_categories[0]
    mongo_service.insert_category(category_data)
    assert mongo_service.check_category_exists(category_data["id"])


def test_insert_category_inserts_only_once(mongo_service: MongoService):
    """
    Test case to verify that insert_category inserts a category only once.

    This test ensures that if a category with the same ID is inserted multiple times,
    it will only be inserted once into the MongoDB collection.
    """
    category_data = base_categories[0]
    mongo_service.insert_category(category_data)
    mongo_service.insert_category(category_data)
    assert mongo_service.db.categories.count_documents({"id": category_data["id"]}) == 1


def test_insert_multiple_categories(mongo_service: MongoService):
    """
    Test case to verify that multiple categories can be inserted and tracked correctly.

    This test inserts multiple categories into the MongoDB collection and ensures that
    each inserted category exists.
    """
    for category in base_categories:
        mongo_service.insert_category(category)
    for category in base_categories:
        assert mongo_service.check_category_exists(category["id"])

    # ----------------------------------------------
    #       category_tracker
    # ----------------------------------------------


def test_insert_new_base_categories_empty_db(mongo_service: MongoService):
    """
    Test case to verify that new base categories are inserted into an empty category_tracker collection.

    This test ensures that when base categories are inserted into an empty category_tracker collection,
    they are correctly added with `last_scraped` initialized to None.
    """
    mongo_service.insert_new_base_categories(base_categories)
    for category in base_categories:
        inserted_category = mongo_service.db.category_tracker.find_one(
            {"id": category["id"]}
        )
        assert inserted_category is not None
        assert inserted_category["last_scraped"] is None


def test_insert_new_base_categories_already_existing(mongo_service: MongoService):
    """
    Test case to verify that already existing base categories are not inserted again.

    This test ensures that if a base category already exists in the category_tracker collection,
    it will not be inserted again.
    """
    mongo_service.insert_new_base_categories([base_categories[0]])
    mongo_service.insert_new_base_categories([base_categories[0]])
    assert (
        mongo_service.db.category_tracker.count_documents(
            {"id": base_categories[0]["id"]}
        )
        == 1
    )


def test_insert_multiple_new_base_categories(mongo_service: MongoService):
    """
    Test case to verify that multiple base categories can be inserted into the category_tracker collection.

    This test inserts multiple base categories and ensures that each category is inserted
    with `last_scraped` initialized to None.
    """
    mongo_service.insert_new_base_categories(base_categories)
    for category in base_categories:
        inserted_category = mongo_service.db.category_tracker.find_one(
            {"id": category["id"]}
        )
        assert inserted_category is not None
        assert inserted_category["last_scraped"] is None


def test_insert_new_base_categories_partial_insert(mongo_service: MongoService):
    """
    Test case to verify that only new categories are inserted into the category_tracker collection.

    This test ensures that if some categories already exist in the category_tracker collection,
    only the new categories are inserted, while the existing ones are not duplicated.
    """
    mongo_service.insert_new_base_categories([base_categories[0]])
    mongo_service.insert_new_base_categories(base_categories)
    assert (
        mongo_service.db.category_tracker.count_documents(
            {"id": base_categories[0]["id"]}
        )
        == 1
    )
    for category in base_categories[1:]:
        inserted_category = mongo_service.db.category_tracker.find_one(
            {"id": category["id"]}
        )
        assert inserted_category is not None
        assert inserted_category["last_scraped"] is None


def test_existing_category_not_overwritten_with_none(mongo_service: MongoService):
    """
    Test case to verify that an existing category with a `last_scraped` date
    is not overwritten with `None` when inserting new base categories.

    This test ensures that when a category already exists in the category_tracker collection
    with a non-`None` `last_scraped` value, it does not get reset to `None`.
    """
    category_with_date = base_categories[0].copy()
    category_with_date["last_scraped"] = "2024-09-28"
    mongo_service.db.category_tracker.insert_one(category_with_date)
    mongo_service.insert_new_base_categories([base_categories[0]])
    inserted_category = mongo_service.db.category_tracker.find_one(
        {"id": category_with_date["id"]}
    )
    assert inserted_category is not None
    assert (
        inserted_category["last_scraped"] == "2024-09-28"
    )  # Ensure the original date was not overwritten


def test_get_untracked_base_categories_empty_tracker(mongo_service: MongoService):
    """
    Test case to verify that all base categories are returned when the category_tracker collection is empty.

    This test ensures that if no categories are being tracked, all base categories provided
    are considered untracked.
    """
    assert mongo_service.db.category_tracker.count_documents({}) == 0
    untracked_categories = mongo_service.get_untracked_base_categories(base_categories)
    assert len(untracked_categories) == len(base_categories)
    assert untracked_categories == base_categories


def test_get_untracked_base_categories_some_tracked(mongo_service: MongoService):
    """
    Test case to verify that only untracked categories are returned when some categories are already tracked.

    This test ensures that if some categories are already being tracked, only the untracked
    categories are returned.
    """
    mongo_service.insert_new_base_categories([base_categories[0]])
    untracked_categories = mongo_service.get_untracked_base_categories(base_categories)
    assert len(untracked_categories) == len(base_categories) - 1


def test_get_untracked_base_categories_all_tracked(mongo_service: MongoService):
    """
    Test case to verify that no categories are returned when all base categories are already tracked.

    This test ensures that if all base categories are already being tracked,
    the function returns an empty list.

    Args:
        mongo_service (MongoService): The MongoService fixture connected to the test DB.
    """
    for category in base_categories:
        mongo_service.db.category_tracker.insert_one({"id": category["id"]})
    untracked_categories = mongo_service.get_untracked_base_categories(base_categories)
    assert len(untracked_categories) == 0


def test_get_unscraped_categories_empty_tracker(mongo_service: MongoService):
    """
    Test case to verify that no categories are returned when the category_tracker is empty.
    """
    assert mongo_service.db.category_tracker.count_documents({}) == 0
    unscraped_categories = mongo_service.get_unscraped_categories()
    assert len(unscraped_categories) == 0


def test_get_unscraped_categories_some_unscraped(mongo_service: MongoService):
    """
    Test case to verify that categories with `last_scraped` set to None are returned.
    """
    mongo_service.db.category_tracker.insert_many(
        [
            {**base_categories[0], "last_scraped": None},  # Unscraped
            {**base_categories[1], "last_scraped": "2024-09-28"},  # Scraped
            {**base_categories[2], "last_scraped": None},  # Unscraped
        ]
    )
    unscraped_categories = mongo_service.get_unscraped_categories()
    assert len(unscraped_categories) == 2
    assert unscraped_categories[0]["id"] == base_categories[0]["id"]
    assert unscraped_categories[1]["id"] == base_categories[2]["id"]


def test_get_unscraped_categories_all_scraped(mongo_service: MongoService):
    """
    Test case to verify that no categories are returned when all categories have been scraped.
    """
    mongo_service.db.category_tracker.insert_many(
        [
            {**base_categories[0], "last_scraped": "2024-09-27"},
            {**base_categories[1], "last_scraped": "2024-09-28"},
        ]
    )
    unscraped_categories = mongo_service.get_unscraped_categories()
    assert len(unscraped_categories) == 0


def test_get_unscraped_categories_mixed(mongo_service: MongoService):
    """
    Test case to verify that only unscraped categories are returned when some are scraped and others are not.
    """
    mongo_service.db.category_tracker.insert_many(
        [
            {**base_categories[0], "last_scraped": None},  # Unscraped
            {**base_categories[1], "last_scraped": "2024-09-28"},  # Scraped
            {**base_categories[2], "last_scraped": None},  # Unscraped
            {**base_categories[3], "last_scraped": "2024-09-29"},  # Scraped
        ]
    )
    unscraped_categories = mongo_service.get_unscraped_categories()
    assert len(unscraped_categories) == 2
    assert unscraped_categories[0]["id"] == base_categories[0]["id"]
    assert unscraped_categories[1]["id"] == base_categories[2]["id"]


def test_mark_category_as_scraped_new_category(mongo_service: MongoService):
    """
    Test case to verify that a new category is inserted and marked as scraped today.

    This test ensures that if the category does not exist in the category_tracker,
    it is inserted with today's date as the `last_scraped` value.
    """
    category_id = base_categories[0]["id"]
    current_day = "2024-09-29"
    mongo_service.mark_category_as_scraped(category_id, current_day)
    tracked_category = mongo_service.db.category_tracker.find_one({"id": category_id})
    assert tracked_category is not None
    assert tracked_category["last_scraped"] == current_day


def test_mark_category_as_scraped_existing_category(mongo_service: MongoService):
    """
    Test case to verify that an existing category is updated with a new `last_scraped` date.

    This test ensures that if a category already exists in the category_tracker,
    its `last_scraped` value is updated to the new date.
    """
    category_id = base_categories[0]["id"]
    old_scraped_date = "2024-09-27"
    new_scraped_date = "2024-09-29"
    mongo_service.db.category_tracker.insert_one(
        {"id": category_id, "last_scraped": old_scraped_date}
    )
    mongo_service.mark_category_as_scraped(category_id, new_scraped_date)
    tracked_category = mongo_service.db.category_tracker.find_one({"id": category_id})
    assert tracked_category is not None
    assert tracked_category["last_scraped"] == new_scraped_date


def test_mark_category_as_scraped_does_not_insert_duplicates(
    mongo_service: MongoService,
):
    """
    Test case to verify that calling `mark_category_as_scraped` multiple times on the same category
    does not create duplicates in the category_tracker.
    """
    category_id = base_categories[0]["id"]
    current_day = "2024-09-29"
    mongo_service.mark_category_as_scraped(category_id, current_day)
    mongo_service.mark_category_as_scraped(category_id, current_day)
    count = mongo_service.db.category_tracker.count_documents({"id": category_id})
    assert count == 1


def test_get_oldest_scraped_category_empty_tracker(mongo_service: MongoService):
    """
    Test case to verify that None is returned when the category_tracker is empty.

    This ensures that if no categories are present in the category_tracker,
    the function returns None.
    """
    assert mongo_service.db.category_tracker.count_documents({}) == 0
    oldest_category = mongo_service.get_oldest_scraped_category()
    assert oldest_category is None


def test_get_oldest_scraped_category_single_category(mongo_service: MongoService):
    """
    Test case to verify that the single existing category is returned as the oldest.

    This test ensures that if there is only one category in the category_tracker,
    it is returned as the oldest.
    """
    mongo_service.db.category_tracker.insert_one(
        {**base_categories[0], "last_scraped": "2024-09-28"}
    )
    oldest_category = mongo_service.get_oldest_scraped_category()
    assert oldest_category is not None
    assert oldest_category["id"] == base_categories[0]["id"]
    assert oldest_category["last_scraped"] == "2024-09-28"


def test_get_oldest_scraped_category_multiple_categories(mongo_service: MongoService):
    """
    Test case to verify that the category with the earliest `last_scraped` date is returned.

    This test ensures that when multiple categories exist, the one with the earliest
    `last_scraped` date is returned as the oldest.
    """
    mongo_service.db.category_tracker.insert_many(
        [
            {**base_categories[0], "last_scraped": "2024-09-27"},
            {**base_categories[1], "last_scraped": "2024-09-28"},
            {**base_categories[2], "last_scraped": "2024-09-26"},
        ]
    )
    oldest_category = mongo_service.get_oldest_scraped_category()
    assert oldest_category is not None
    assert (
        oldest_category["id"] == base_categories[2]["id"]
    )  # This category has "2024-09-26"
    assert oldest_category["last_scraped"] == "2024-09-26"


def test_get_oldest_scraped_category_mixed_unscraped(mongo_service: MongoService):
    """
    Test case to verify that also unscraped categories are considered for the oldest scraped category.
    """
    mongo_service.db.category_tracker.insert_many(
        [
            {**base_categories[0], "last_scraped": None},  # Unscraped
            {**base_categories[1], "last_scraped": "2024-09-28"},
            {**base_categories[2], "last_scraped": "2024-09-26"},
        ]
    )
    oldest_category = mongo_service.get_oldest_scraped_category()
    assert oldest_category is not None
    assert (
        oldest_category["id"] == base_categories[0]["id"]
    )  # This category has "2024-09-26"
    assert oldest_category["last_scraped"] == None

    # ----------------------------------------------
    #       products
    # ----------------------------------------------


def test_check_product_exists_in_empty_db(mongo_service: MongoService):
    """
    Test case to verify that check_product_exists returns False when the products collection is empty.
    """
    migros_id = oliveoil["migrosId"]
    assert mongo_service.db.products.count_documents({}) == 0
    assert not mongo_service.check_product_exists(migros_id)


def test_check_product_exists_after_insertion(mongo_service: MongoService):
    """
    Test case to verify that check_product_exists returns True after the product is inserted into the collection.
    """
    migros_id = oliveoil["migrosId"]
    mongo_service.db.products.insert_one(oliveoil)
    assert mongo_service.check_product_exists(migros_id)


def test_check_product_exists_with_different_migros_id(mongo_service: MongoService):
    """
    Test case to verify that check_product_exists returns False when a product with a different migrosId is checked.
    """
    mongo_service.db.products.insert_one(penne)
    migros_id = oliveoil["migrosId"]
    assert not mongo_service.check_product_exists(migros_id)


def test_check_product_exists_multiple_products(mongo_service: MongoService):
    """
    Test case to verify that check_product_exists works with multiple products in the collection.
    """
    migros_id_oliveoil = oliveoil["migrosId"]
    migros_id_penne = penne["migrosId"]
    mongo_service.db.products.insert_many([oliveoil, penne])
    assert mongo_service.check_product_exists(migros_id_oliveoil)
    assert mongo_service.check_product_exists(migros_id_penne)


def test_insert_new_product(mongo_service: MongoService, caplog):
    """Test case to verify that a new product is inserted when it doesn't exist in the collection."""
    caplog.clear()
    migros_id = oliveoil["migrosId"]
    assert mongo_service.db.products.count_documents({"migrosId": migros_id}) == 0
    mongo_service.insert_product(oliveoil)
    assert mongo_service.db.products.count_documents({"migrosId": migros_id}) == 1
    assert "Inserted new product with migrosId" in caplog.text


def test_insert_product_with_same_price(mongo_service: MongoService, caplog):
    """Test case to verify that no insertion occurs if the product already exists with the same price."""
    caplog.clear()
    migros_id = oliveoil["migrosId"]
    mongo_service.insert_product(oliveoil)
    mongo_service.insert_product(oliveoil)
    assert mongo_service.db.products.count_documents({"migrosId": migros_id}) == 1
    assert "New unit price detected" not in caplog.text
    assert (
        f"Product with migrosId {migros_id} already exists with the same unitPrice"
        in caplog.text
    )


def test_insert_product_missing_migros_id(mongo_service: MongoService, caplog):
    """Test case to verify that the product is not inserted if the `migrosId` is missing, and an error is logged."""
    caplog.clear()
    invalid_product = oliveoil.copy()
    invalid_product.pop("migrosId")
    mongo_service.insert_product(invalid_product)
    assert mongo_service.db.products.count_documents({}) == 0
    assert "Product does not contain migrosId, skipping insertion." in caplog.text


def test_insert_product_with_price_change(mongo_service: MongoService, caplog):
    """Test case to verify that a product is inserted again if the price has changed, and the price change is logged."""
    caplog.clear()
    migros_id = oliveoil["migrosId"]
    mongo_service.insert_product(oliveoil)
    mongo_service.insert_product(oliveoil_price_change)
    assert mongo_service.db.products.count_documents({"migrosId": migros_id}) == 2
    price_history = mongo_service.db.unit_price_history.find_one(
        {"migrosId": migros_id}
    )
    assert price_history["newPrice"]["value"] == 12
    assert "New unit price detected" in caplog.text


def test_insert_product_missing_offer(mongo_service: MongoService, caplog):
    """Test case to verify that the product is not inserted if the `offer` field is missing, and an error is logged."""
    caplog.clear()
    mongo_service.insert_product(oliveoil_offer_missing)
    assert mongo_service.db.products.count_documents({}) == 0
    assert "does not have an offer, skipping insertion." in caplog.text


import time


def test_get_latest_product_entry_single_entry(mongo_service: MongoService):
    """Test case to verify that the latest product entry is returned correctly when only one entry exists."""
    migros_id = oliveoil["migrosId"]
    mongo_service.insert_product(oliveoil)
    latest_product = mongo_service.get_latest_product_entry_by_migros_id(migros_id)
    assert latest_product is not None
    assert latest_product["migrosId"] == migros_id
    assert latest_product["name"] == oliveoil["name"]


def test_get_latest_product_entry_multiple_entries(mongo_service: MongoService):
    """Test case to verify that the latest product entry is returned correctly when multiple entries exist."""
    migros_id = oliveoil["migrosId"]
    mongo_service.insert_product(oliveoil)
    time.sleep(2)
    mongo_service.insert_product(oliveoil_price_change)
    latest_product = mongo_service.get_latest_product_entry_by_migros_id(migros_id)
    assert latest_product is not None
    assert latest_product["migrosId"] == migros_id
    assert (
        latest_product["offer"]["price"]["value"]
        == oliveoil_price_change["offer"]["price"]["value"]
    )
    time.sleep(2)
    mongo_service.insert_product(oliveoil_price_change_2)
    latest_product = mongo_service.get_latest_product_entry_by_migros_id(migros_id)
    assert latest_product is not None
    assert latest_product["migrosId"] == migros_id
    assert (
        latest_product["offer"]["price"]["value"]
        == oliveoil_price_change_2["offer"]["price"]["value"]
    )


def test_get_latest_product_entry_no_entry(mongo_service: MongoService):
    """Test case to verify that None is returned when no product entry exists for the given migrosId."""
    migros_id = oliveoil["migrosId"]
    assert mongo_service.db.products.count_documents({"migrosId": migros_id}) == 0
    latest_product = mongo_service.get_latest_product_entry_by_migros_id(migros_id)
    assert latest_product is None


def test_get_all_known_migros_ids_empty_db(mongo_service: MongoService):
    """Test that get_all_known_migros_ids returns an empty list when the products collection is empty."""
    assert mongo_service.get_all_known_migros_ids() == []


def test_get_all_known_migros_ids_single_product(mongo_service: MongoService):
    """Test that get_all_known_migros_ids returns the correct migrosId when a single product is inserted."""
    mongo_service.insert_product(oliveoil)
    assert mongo_service.get_all_known_migros_ids() == [oliveoil["migrosId"]]


def test_get_all_known_migros_ids_multiple_products(mongo_service: MongoService):
    """Test that get_all_known_migros_ids returns all distinct migrosIds when multiple products are inserted."""
    mongo_service.insert_product(oliveoil)
    mongo_service.insert_product(penne)
    assert set(mongo_service.get_all_known_migros_ids()) == {
        oliveoil["migrosId"],
        penne["migrosId"],
    }


def test_get_all_known_migros_ids_duplicate_inserts(mongo_service: MongoService):
    """Test that get_all_known_migros_ids returns only distinct migrosIds, even if a product is inserted multiple times."""
    mongo_service.insert_product(oliveoil)
    mongo_service.insert_product(oliveoil)  # Inserting the same product twice
    assert mongo_service.get_all_known_migros_ids() == [oliveoil["migrosId"]]


def test_get_all_known_migros_ids_multiple_instances_of_same_product(
    mongo_service: MongoService,
):
    """Test that get_all_known_migros_ids returns only distinct migrosIds, even if the same product is inserted multiple times."""
    mongo_service.insert_product(oliveoil)
    mongo_service.insert_product(oliveoil_price_change)
    mongo_service.insert_product(oliveoil_price_change_2)
    assert mongo_service.get_all_known_migros_ids() == [oliveoil["migrosId"]]


def test_save_scraped_product_id_new_entry(mongo_service: MongoService):
    """Test that a new scraped product ID is saved when it hasn't been scraped on the same day."""
    migros_id = oliveoil["migrosId"]
    date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, date)
    assert (
        mongo_service.db.scraped_ids.count_documents(
            {"migrosId": migros_id, "date": date}
        )
        == 1
    )


def test_save_scraped_product_id_duplicate_entry_same_day(mongo_service: MongoService):
    """Test that duplicate scraped product IDs are not saved on the same day."""
    migros_id = oliveoil["migrosId"]
    date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, date)
    mongo_service.save_scraped_product_id(
        migros_id, date
    )  # Try saving again on the same day
    assert (
        mongo_service.db.scraped_ids.count_documents(
            {"migrosId": migros_id, "date": date}
        )
        == 1
    )


def test_save_scraped_product_id_different_days(mongo_service: MongoService):
    """Test that the same product can be saved as scraped on different days."""
    migros_id = oliveoil["migrosId"]
    date1 = "2024-09-28"
    date2 = "2024-09-29"
    mongo_service.save_scraped_product_id(migros_id, date1)
    mongo_service.save_scraped_product_id(migros_id, date2)
    assert mongo_service.db.scraped_ids.count_documents({"migrosId": migros_id}) == 2


def test_is_product_scraped_today_not_scraped(mongo_service: MongoService):
    """Test that is_product_scraped_today returns False when the product hasn't been scraped on the given day."""
    migros_id = oliveoil["migrosId"]
    date = "2024-09-28"
    assert not mongo_service.is_product_scraped_today(migros_id, date)


def test_is_product_scraped_today_scraped(mongo_service: MongoService):
    """Test that is_product_scraped_today returns True when the product has been scraped on the given day."""
    migros_id = oliveoil["migrosId"]
    date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, date)
    assert mongo_service.is_product_scraped_today(migros_id, date)


def test_is_product_scraped_today_scraped_different_day(mongo_service: MongoService):
    """Test that is_product_scraped_today returns False when the product was scraped on a different day."""
    migros_id = oliveoil["migrosId"]
    date_scraped = "2024-09-27"
    date_today = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, date_scraped)
    assert not mongo_service.is_product_scraped_today(migros_id, date_today)


def test_reset_scraped_ids_no_entries(mongo_service: MongoService, caplog):
    """Test that reset_scraped_ids works with no entries in the collection."""
    caplog.clear()
    current_date = "2024-09-28"
    mongo_service.reset_scraped_ids(current_date)
    assert mongo_service.db.scraped_ids.count_documents({}) == 0
    assert f"Reset scraped IDs not from {current_date}." in caplog.text


def test_reset_scraped_ids_with_old_entries(mongo_service: MongoService, caplog):
    """Test that reset_scraped_ids removes all entries that are not from the current date."""
    caplog.clear()
    migros_id = oliveoil["migrosId"]
    old_date = "2024-09-27"
    current_date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, old_date)
    mongo_service.save_scraped_product_id(migros_id, current_date)
    mongo_service.reset_scraped_ids(current_date)
    assert mongo_service.db.scraped_ids.count_documents({}) == 1
    assert mongo_service.db.scraped_ids.count_documents({"date": current_date}) == 1
    assert mongo_service.db.scraped_ids.count_documents({"date": old_date}) == 0
    assert f"Reset scraped IDs not from {current_date}." in caplog.text


def test_reset_scraped_ids_only_current_date_entries(
    mongo_service: MongoService, caplog
):
    """Test that reset_scraped_ids does not remove entries if all are from the current date."""
    caplog.clear()
    migros_id = oliveoil["migrosId"]
    current_date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id, current_date)
    assert mongo_service.db.scraped_ids.count_documents({}) == 1
    mongo_service.reset_scraped_ids(current_date)
    assert mongo_service.db.scraped_ids.count_documents({}) == 1
    assert mongo_service.db.scraped_ids.count_documents({"date": current_date}) == 1
    assert f"Reset scraped IDs not from {current_date}." in caplog.text


def test_retrieve_todays_scraped_ids_no_entries(mongo_service: MongoService):
    """Test that retrieve_todays_scraped_ids returns an empty list when there are no entries for the current date."""
    current_date = "2024-09-28"
    assert mongo_service.retrieve_todays_scraped_ids(current_date) == []


def test_retrieve_todays_scraped_ids_with_entries(mongo_service: MongoService):
    """Test that retrieve_todays_scraped_ids returns all migrosIds for the current date."""
    migros_id_1 = oliveoil["migrosId"]
    migros_id_2 = penne["migrosId"]
    current_date = "2024-09-28"
    mongo_service.save_scraped_product_id(migros_id_1, current_date)
    mongo_service.save_scraped_product_id(migros_id_2, current_date)
    assert set(mongo_service.retrieve_todays_scraped_ids(current_date)) == {
        migros_id_1,
        migros_id_2,
    }


def test_retrieve_todays_scraped_ids_ignores_other_dates(mongo_service: MongoService):
    """Test that retrieve_todays_scraped_ids does not return migrosIds from other dates."""
    migros_id = oliveoil["migrosId"]
    current_date = "2024-09-28"
    old_date = "2024-09-27"
    mongo_service.save_scraped_product_id(migros_id, old_date)
    assert mongo_service.retrieve_todays_scraped_ids(current_date) == []

    # ----------------------------------------------
    #       request_counts
    # ----------------------------------------------


def test_get_request_count_no_entry(mongo_service: MongoService):
    """Test that get_request_count returns 0 when there is no entry for the current date."""
    current_date = "2024-09-28"
    assert mongo_service.get_request_count(current_date) == 0


def test_get_request_count_with_entry(mongo_service: MongoService):
    """Test that get_request_count returns the correct count for the current date."""
    current_date = "2024-09-28"
    mongo_service.db.request_counts.insert_one({"date": current_date, "count": 5})
    assert mongo_service.get_request_count(current_date) == 5


def test_get_request_count_no_count_field(mongo_service: MongoService):
    """Test that get_request_count returns 0 if the entry exists but has no count field."""
    current_date = "2024-09-28"
    mongo_service.db.request_counts.insert_one({"date": current_date})
    assert mongo_service.get_request_count(current_date) == 0


def test_increment_request_count_no_entry(mongo_service: MongoService):
    """Test that increment_request_count creates a new entry and increments count if no entry exists."""
    current_date = "2024-09-28"
    mongo_service.increment_request_count(current_date, 2)
    result = mongo_service.db.request_counts.find_one({"date": current_date})
    assert result is not None
    assert result["count"] == 2


def test_increment_request_count_existing_entry(mongo_service: MongoService):
    """Test that increment_request_count increments the count for an existing entry."""
    current_date = "2024-09-28"
    mongo_service.db.request_counts.insert_one({"date": current_date, "count": 5})
    mongo_service.increment_request_count(current_date, 3)
    result = mongo_service.db.request_counts.find_one({"date": current_date})
    assert result["count"] == 8


def test_increment_request_count_default_increment(mongo_service: MongoService):
    """Test that increment_request_count increments by the default value of 1 if no count is provided."""
    current_date = "2024-09-28"
    mongo_service.db.request_counts.insert_one({"date": current_date, "count": 5})
    mongo_service.increment_request_count(current_date)
    result = mongo_service.get_request_count(current_date)
    assert result == 6


def test_increment_request_count_default_increment_no_entry(
    mongo_service: MongoService,
):
    """Test that increment_request_count increments by the default value of 1 if no entry exists."""
    current_date = "2024-09-28"
    mongo_service.increment_request_count(current_date)
    result = mongo_service.get_request_count(current_date)
    assert result == 1
    mongo_service.increment_request_count(current_date)
    result = mongo_service.get_request_count(current_date)
    assert result == 2
