# Project Documentation

This project is a web scraper designed to extract product information from a supermarket's website (Migros). The scraper navigates the website using Selenium, retrieves product and category data from the site's network requests, and stores the scraped data into both a MongoDB database and, in the future, a PostgreSQL database using the data models and factories provided.

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Data Storage](#data-storage)
   - [MongoDB](#mongodb)
   - [PostgreSQL (Planned)](#postgresql-planned)
4. [Code Documentation](#code-documentation)
   - [migros_scraper.py](#migros_scraperpy)
     - [Purpose](#purpose)
     - [Key Responsibilities](#key-responsibilities)
     - [Key Methods](#key-methods)
     - [Flow of Operations](#flow-of-operations)
     - [Error Handling and Debugging](#error-handling-and-debugging)
   - [mongo_service.py](#mongo_servicepy)
     - [Purpose](#purpose-1)
     - [Key Responsibilities](#key-responsibilities-1)
     - [Collections and Their Roles](#collections-and-their-roles)
     - [Key Methods](#key-methods-1)
     - [Flow of Operations](#flow-of-operations-1)
     - [Error Handling and Debugging](#error-handling-and-debugging-1)
   - [ProductFactory](#productfactory)
     - [Purpose](#purpose-2)
     - [Key Responsibilities](#key-responsibilities-2)
     - [Data Classes Used](#data-classes-used)
     - [Key Methods](#key-methods-2)
     - [Logic and Flow](#logic-and-flow)
     - [Error Handling and Edge Cases](#error-handling-and-edge-cases)
     - [Future Improvements](#future-improvements)
   - [yeeter.py](#yeeterpy)
     - [Purpose](#purpose-3)
     - [Key Responsibilities](#key-responsibilities-3)
     - [How It Works](#how-it-works)
     - [Additional Utilities](#additional-utilities)
     - [Use Cases](#use-cases)

---

## Overview

This scraper automates the extraction of product data from Migros, a Swiss supermarket chain. It uses Selenium WebDriver for navigation, capturing network requests to fetch product details, prices, categories, and nutritional information. The captured data is stored in MongoDB, and there's ongoing development to store it also in a PostgreSQL database for more robust querying and integration with downstream systems.

## Project Structure

- `src/migros_scraper.py`: Main scraper logic.
- `src/services/mongo_service.py`: Interactions with MongoDB.
- `src/models/`: Data classes and factories (e.g., `product_factory.py`) for processing and saving products.
- `src/utils/yeeter.py`: Logging and output utilities.
- `docker-compose.yml`: Setup for running MongoDB, PostgreSQL, and the scraper/test environments.
- `pyproject.toml` & `poetry.lock`: Python package management configuration via Poetry.
- `tests/`: Contains tests for product parsing, nutrients extraction, and database operations.

## Data Storage

### MongoDB

The scraper primarily stores data in MongoDB:
- **products** collection: Holds product data, including offers, ingredients, and nutritional info.
- **categories**: Stores category hierarchy and metadata.
- **id_scraped_at**: Tracks when each product was last scraped.
- **request_counts**: Logs how many requests were made on each day.
- **unit_price_history**: Tracks changes in product prices over time.

### PostgreSQL (Planned)

The project includes some models (`Product`, `Offer`, `Nutrition`) and a `ProductFactory` for saving data to PostgreSQL. Full integration is still in progress, and SQL storage is not yet fully implemented.

## Code Documentation

### migros_scraper.py

**Location:** `src/migros_scraper.py`

#### Purpose

`migros_scraper.py` contains the main scraping logic. It uses Selenium WebDriver to navigate the Migros website, making use of the Selenium Wire plugin to capture and process network requests. The scraper identifies URLs that return product and category data, parses the responses, and stores the results in MongoDB.

#### Key Responsibilities

- Initialize and manage a Selenium WebDriver session.
- Traverse the main Migros website page and other category or product pages.
- Capture network requests and parse JSON responses for categories, products, and product cards.
- call the mogo service to save products, request additional imformation, log request counts ...
- Avoid re-scraping products too frequently by checking `id_scraped_at` collection.
- Log scraper activity and handle errors gracefully.

#### Key Methods

- **`__init__`**: Sets up the driver, MongoDB service, and logging. Loads known product IDs to prevent duplicates.
- **`load_main_page`**: Navigates to the Migros homepage.
- **`get_and_store_base_categories`**: Retrieves the top-level categories from the storemap API, stores them in MongoDB, and initiates scraping of categories and subcategories.
- **`scrape_categories_from_base`**: Iterates through base categories and their subcategories to capture product listings. for now only up to the second level, this because deeper scraping would not yeald additional product numbers.
- **`scrape_category_via_url`**: Given a category URL, it retrieves products and nested categories.
- **`scrape_product_by_id`**: Given a product `migros_id`, navigates to the product page, captures details, and inserts them into MongoDB if the offer has changed.
- **`check_for_product_cards`**: Occasionally checks network requests for product cards and scrapes newly discovered products. this is because almost every request we make will ome with a response that contains a list of 100 product ids, this is a good oportunity to check if one of them is unknown to us.
- **`make_request_and_validate`**: Central method for navigating to a URL with the driver and handling potential errors (like HTTP 429 or 4xx/5xx responses). This function also implements random delays, otherwise we could only scrape about a minute untill gettig blocked.

#### Flow of Operations

1. **Initialization**: The scraper sets up the Selenium driver and connects to MongoDB.
2. **Load Main Page**: Fetch the main Migros page and retrieve base categories.
3. **Categories**: The scraper navigates through categories and subcategories, identifying products. every unknown id imediately gets scraped.
4. **Products**: For each product or product card, the scraper fetches the product detail page, extracts data, and stores it in MongoDB. This is done after categories are traversed. here is where products periodically get checked. Each producht gets checked every 5 days for price updates. 5 days because there are many products and i do not want to spam MIgros to much.
5. **Periodic Checks**: The scraper logs request counts, checks if products are already scraped to avoid duplicates, and respects server limits by sleeping between requests.
6. **Completion**: After processing the specified categories and products, it closes the driver and ends the session.

#### Error Handling and Debugging

- When errors occur (network issues, JSON decode errors, or database problems), the scraper logs them using the `Yeeter` utility.
- If `DEBUG_MODE` is set to true in the environment, the scraper will launch `pdb` (Python debugger) on exceptions, enabling interactive debugging.
- Retries are implemented for certain HTTP status codes (e.g., HTTP 429).

---
## mongo_service.py

**Location:** `src/services/mongo_service.py`

### Purpose

`mongo_service.py` manages all interactions with the MongoDB database used by the scraper. It provides high-level methods to insert, query, and update product and category data, maintain scraping timestamps, log request counts, and keep track of price history changes.


By centralizing all MongoDB operations in `mongo_service.py`, the codebase achieves cleaner separation of concerns. Other parts of the scraper interact with a well-defined interface rather than dealing with raw database calls directly.

### Key Responsibilities

- Establish and maintain a MongoDB client connection.
- Ensure required collections (`products`, `categories`, `id_scraped_at`, `unit_price_history`, `request_counts`) exist.
- Insert and update category information, including tracking when categories were last scraped.
- Insert new products or record changes in product prices over time.
- Keep track of when each product was last scraped to prevent redundant scraping.
- Retrieve sets of products to scrape based on how long ago they were last updated.
- Handle errors and log debug information to aid troubleshooting.

### Collections and Their Roles

- **`products`**: Stores product details, including offers, nutritional info, and other metadata. Products may appear multiple times with different `dateAdded` fields if prices change over time.
- **`categories`**: Stores category data (ID, slug, name, etc.) and their hierarchy as provided by Migros.
- **`category_tracker`**: Tracks when each category was last scraped to prioritize which categories need updates.
- **`id_scraped_at`**: Records the `migrosId` of a product along with the last time it was scraped. Used to prevent re-scraping too frequently.
- **`unit_price_history`**: Logs changes in product prices over time, allowing historical price analysis.
- **`request_counts`**: Counts daily requests made by the scraper, useful for monitoring scraper activity and respecting rate limits.

### Key Methods

- **Category Management**:
  - `insert_category(category_data)`: Inserts a category if it doesn't already exist.
  - `get_untracked_base_categories(base_categories)`: Identifies categories not yet tracked.
  - `mark_category_as_scraped(category_id, current_day)`: Updates the category_tracker to note when a category was last scraped.

- **Product Management**:
  - `insert_product(product_data)`: Inserts a product if new or price-changed; logs price changes in `unit_price_history`.
  - `check_product_exists(migros_id)`: Verifies if a product is already known.
  - `get_latest_product_entry_by_migros_id(migros_id)`: Retrieves the most recent entry for a given product.
  - `get_all_known_migros_ids()`: Lists all known product IDs.

- **Scraping Time Management**:
  - `save_scraped_product_id(migros_id)`: Records the current timestamp of scraping a product.
  - `is_product_scraped_last_24_hours(migros_id)`: Checks if a product was scraped within the last 24 hours.
  - `retrieve_id_scraped_at_last_24_hours()`: Retrieves product IDs scraped within the last 24 hours.

- **Price History**:
  - `get_price_history(migros_id)`: Fetches the recorded price changes for a product over time.

- **Request Counts**:
  - `increment_request_count(date, count)`: Increments the number of requests made on a given date.
  - `get_request_count(date)`: Retrieves how many requests were made on a specific day.

- **Product Retrieval by Date**:
  - `get_products_not_scraped_in_days(days, limit, only_edible)`: Returns products that haven't been scraped for `days` or more, optionally filtering by products that contain nutritional information.

### Flow of Operations

1. **Initialization**: On creation, `MongoService` connects to the MongoDB instance, verifies collections, and logs the connection status.
2. **Insertion and Updates**:
   - When the scraper finds a new product or category, `MongoService` inserts it if it's new.
   - When prices change, the new product entry is inserted, and price changes are logged.
3. **Data Retrieval**:
   - Before scraping, the scraper calls methods like `get_products_not_scraped_in_days` to find targets.
   - It uses `is_product_scraped_last_24_hours` or `retrieve_id_scraped_at_last_24_hours` to avoid scraping too frequently.
4. **Error Handling**:
   - Errors are caught, logged, and can trigger debug info, including stack traces.
   - If connection or queries fail, appropriate messages are printed for easier troubleshooting.

### Error Handling and Debugging

- On encountering database connection issues or MongoDB errors, `MongoService` logs detailed error messages.
- The `log_debug_info()` method can output stack traces and local variables, aiding in diagnosing complex issues.
- `PyMongoError` exceptions are caught to prevent the scraper from crashing unexpectedly, and debugging can be enabled with `DEBUG_MODE`.


---


## ProductFactory

**Location:** `src/models/product_factory.py`

### Purpose

`ProductFactory` is responsible for parsing raw JSON product data into structured Python data classes (`Product`, `Offer`, `Nutrition`) for later saving the resulting objects to a SQL database. It acts as a bridge between the scraped JSON (obtained from the Migros website) and the database models that store product details in a relational format.

### Key Responsibilities

- Parse and clean raw JSON product data retrieved from the scraper.
- Extract nutritional information and convert it into a `Nutrition` object.
- Extract pricing and promotional details to create an `Offer` object.
- Build a `Product` object that incorporates both `Offer`, `Nutrition`, and other metadata.
- Save these objects into a SQL database (via a provided database cursor), integrating with `Product`, `Offer`, and `Nutrition` ORM or custom insert logic.

### Data Classes Used

- **`Product`**: Represents a product with fields like `migros_id`, `name`, `brand`, `title`, `description`, `ingredients`, `gtins`, `scraped_at`, and references to `Nutrition` and `Offer`.
- **`Offer`**: Represents pricing information, including `price`, `promotion_price`, `unit_price`, `promotion_unit_price`, and `quantity`.
- **`Nutrition`**: Represents nutritional facts per 100g/ml (or per unit). Includes fields like `kJ`, `kcal`, `fat`, `saturates`, `carbohydrate`, `sugars`, `fibre`, `protein`, and `salt`.

### Key Methods

- **`create_product_from_json(product_json, cursor)`**:
  The main entry point for converting JSON data into `Product`, `Offer`, and `Nutrition` objects and saving them to the database. Steps include:
  1. **Extract Nutrients**: Uses `extract_nutrients()` to parse the `nutrientsInformation` section of the JSON.
  2. **Extract Offer**: Calls `extract_offer()` to parse pricing details, including promotions and quantity-based unit prices.
  3. **Construct Product**: Gathers basic product info like `name`, `brand`, `title`, `description`, and `ingredients`.
  4. **Save to DB**: Once the `Product` is fully assembled, calls methods like `product.save_to_db(cursor)` to insert the product and related entities into SQL tables.
  5. Handles date parsing from the `dateAdded` field or sets a fallback to the current date if not provided.

- **`extract_nutrients(product_json)`**:
  Parses nutrient tables from the JSON `productInformation.nutrientsInformation.nutrientsTable`. It identifies the appropriate 100g/ml column, extracts values like `kJ`, `kcal`, `fat`, `saturates`, etc., and returns a `Nutrition` instance.

- **`extract_offer(product_json)`**:
  Parses the `offer` section, handling normal and promotional prices. It uses utility methods (like `parse_quantity_price`) and logic to determine `unit_price` and `promotion_unit_price` from `quantityPrice`, `promotionPrice`, and/or `unitPrice` fields.

- **`parse_quantity_price(quantity_price_str)`**:
  A helper function to parse strings like `"0.85/100g"` into structured numeric values `(value=0.85, quantity=100, unit='g')`. This is crucial for converting textual price/quantity formats into numeric forms.

### Logic and Flow

1. **Input**: The scraper passes a JSON object representing a product's details, this is the raw information from the website.
2. **Nutrients Extraction**:
   `extract_nutrients()` identifies the correct column (often per 100g/ml) and scrapes nutrient values. The resulting `Nutrition` object includes standardized numeric fields.
3. **Offer Extraction**:
   `extract_offer()` parses various price fields. It tries to determine:
   - Regular `price`
   - Promotion `promotion_price`
   - `unit_price` and `promotion_unit_price` (using `quantityPrice` or `promotionPrice.unitPrice`)
   - `quantity` (e.g., "2x250g" might become total quantity 500g)
4. **Product Construction**:
   With `Nutrition` and `Offer` objects ready, `create_product_from_json()` gathers the product name, brand, title, ingredients, and `gtins`. It sets `scraped_at` to either the provided `dateAdded` or the current timestamp.
5. **Saving to Database**:
   Calls `product.save_to_db(cursor)` to insert the product, offer, and nutrient records into the SQL database. This step may use prepared statements or ORM methods.

### Error Handling and Edge Cases

- If nutrients are missing or malformed, `extract_nutrients()` returns `None`, and the product may be saved without nutrition data.
- If offer parsing fails or is incomplete, the `Offer` object may have partial or `None` fields.
- The code logs warnings or errors when encountering invalid data, such as non-numeric values where numbers are expected.
- Date parsing for `scraped_at` handles invalid formats gracefully by falling back to the current timestamp.

### Future Improvements

- More robust handling of various formats in `offer` and `nutrition` data.
- Expanded logging and validation to handle new product fields.
- Integration with complete SQL models and migrations to ensure data integrity.

---

By encapsulating all parsing and object construction logic in `ProductFactory`, the project maintains a clean separation between raw data handling and database interactions. This allows for easier testing, debugging, and future extensions (e.g., integrating with other data sources or adjusting the database schema).

---

## yeeter.py

**Location:** `src/utils/yeeter.py`

### Purpose

`yeeter.py` provides a unified, color-coded logging interface wrapped around Python's standard `logging` library. It simplifies message logging throughout the scraper by offering convenient shorthand methods for different log levels (info, warning, error, debug) and automatically manages log formatting, file rotation, and timestamps.

### Key Responsibilities

- Initialize a logger with both console and file handlers.
- Format log messages with timestamps converted to a specific time zone (Berlin time).
- Assign colors to different log levels when logging to the console for easy readability.
- Provide simple helper methods for logging at various severity levels (`yeet` for info, `error`, `alarm` for warnings, `bugreport` for debug).
- Automatically rotate and manage log files to prevent unbounded growth.
- Allow for quick cleanup of old log files.

### How It Works

1. **Initialization**:
   When an instance of `Yeeter` is created, it:
   - Ensures the log directory exists.
   - Sets up a `RotatingFileHandler` to manage log files.
   - Configures a `StreamHandler` for console output.
   - Uses a custom `CustomFormatter` that converts timestamps to Berlin time and applies color coding for console messages.

2. **Logging Methods**:
   - `yeet(message: str)`: Logs an informational message (`INFO` level).
   - `error(message: str)`: Logs an error message (`ERROR` level).
   - `alarm(message: str)`: Logs a warning message (`WARNING` level).
   - `bugreport(message: str)`: Logs a debug message (`DEBUG` level).

   Each of these methods routes through the `logger` instance, ensuring consistent formatting.

3. **Log Rotation**:
   The `RotatingFileHandler` ensures that once a log file reaches a defined maximum size, it's rotated. Old log files are kept up to a certain `backup_count`.

4. **Timezone and Formatting**:
   `CustomFormatter` overrides the default time formatting:
   - Fetches the log record's timestamp in UTC.
   - Converts it to Berlin time (Europe/Berlin).
   - Formats it without milliseconds, making log times consistent and human-readable.

5. **Color Coding (Console Only)**:
   - **ERROR**: Red
   - **WARNING**: Yellow
   - **DEBUG**: Cyan
   - **INFO**: Default (no extra color)

   This helps quickly identify the severity of messages in the console at a glance.

### Additional Utilities

- `clear_log_files()`: Deletes all log files in the configured log directory. Useful for resetting logs between runs, tests, or environments.
- `log_scraper_state(url, request, scraped_product_ids, base_categories)`: Provides a snapshot of the scraper’s current state (e.g., the last scraped product, how many products were scraped, details of the last request and response).

### Use Cases

- Throughout the scraper (e.g., `migros_scraper.py`, `mongo_service.py`), calls to `yeet()`, `error()`, `alarm()`, and `bugreport()` replace direct `print()` statements.
- Ensures consistent, timestamped, and color-coded log messages, improving readability and traceability.
- Helps developers diagnose issues by providing debug messages (`bugreport`) and logs of failed operations (`error`) without mixing unformatted prints.

### Example

```python
from src.utils.yeeter import Yeeter

yeeter = Yeeter()
yeeter.yeet("Scraping started.")
yeeter.bugreport("Debugging some minor issue.")
yeeter.alarm("Received unexpected status code, retrying...")
yeeter.error("Failed to scrape product details due to timeout.")
```
---

### MongoToPostgresSync

**Location:** `src/sync/mongo_to_postgres_sync.py` (Adjust the path based on your actual directory structure.)

**Description:**
`MongoToPostgresSync` is a synchronization utility that fetches product data from a MongoDB database and ensures that the corresponding records in a PostgreSQL database remain consistent and up-to-date. It checks for existing products, inserts new products that are not yet in the PostgreSQL database, and updates any products that have changed since their last synchronization.

**Key Functions:**

- **`sync_products()`**
  Fetches products from MongoDB, compares them with their PostgreSQL counterparts, and then:
  - Inserts new products if they don't exist in PostgreSQL.
  - Updates products that have changed.
  - Skips products that are already up-to-date.

- **`close_connections()`**
  Closes the MongoDB and PostgreSQL connections cleanly after synchronization is complete.

**Dependencies:**

- **MongoDB**: The service queries the `products` collection of the specified MongoDB database for product data.
- **PostgreSQL**: The synchronization requires a PostgreSQL database with corresponding tables and schema defined. It uses `Product` models and factories (defined in `src/models/product.py` and `src/models/product_factory.py`) to represent and manipulate product records.
- **Python Packages**:
  - `pymongo` for MongoDB interactions.
  - `psycopg2` for PostgreSQL interactions.
  - Custom model classes `Product` and `ProductFactory`.

**Configuration:**

- **MongoDB**:
  Set `MONGO_URI` and `MONGO_DB_NAME` environment variables (or hardcode them in the script, as shown in the example).
  Example:
  ```python
  MONGO_URI = "mongodb://mongo:27017"
  MONGO_DB_NAME = "productsandcategories"
  ```

- **PostgreSQL**:
  Define `POSTGRES_CONFIG` to specify `dbname`, `user`, `password`, `host`, and `port`.
  Example:
  ```python
  POSTGRES_CONFIG = {
      "dbname": "postgres_db",
      "user": "postgres",
      "password": "password",
      "host": "postgres",
      "port": 5432,
  }
  ```

**Usage Example:**

To run the synchronization, make sure that both MongoDB and PostgreSQL services are available, and then execute:

```python
docker compose run --rm sync
```

**Error Handling:**

The script logs any issues encountered during the synchronization process. If it fails to locate a product or encounters unexpected data issues, it logs warnings or errors and continues processing the next product. Any database exceptions are caught and logged.