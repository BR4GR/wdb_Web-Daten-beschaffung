# Migros Scraper Project

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Development Notes](#development-notes)
---

## Overview
The **Migros Scraper Project** is a web scraping and data processing application designed to collect product information from the Migros online store. The project saves the scraped data in both MongoDB (NoSQL) and PostgreSQL (SQL). Saving it to SQL is beneficial because then we already have parsed and filtered information. Saving it to MongoDB is an easy way to save all available information, this way we can later add any information we want to our parsed data.

---

## Features

- Scrapes product categories and detailed product data from Migros using Playwright
- Three-phase scraping: edible products (with nutrition), newly discovered IDs, then non-edibles
- Batched processing to manage memory usage
- Saves data in MongoDB for flexible NoSQL operations
- Saves data in PostgreSQL for structured SQL analysis
- Supports running multiple database containers (e.g., development and testing)
- Includes robust error handling with detailed logging
- Unit-tested for reliability
- Dockerized for easy deployment and testing

---

## Prerequisites
Ensure the following software is installed on your system:

- [Docker](https://docs.docker.com/get-docker/) (latest version recommended)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Poetry](https://python-poetry.org/) or [uv](https://docs.astral.sh/uv/) for dependency management
- Python 3.12+ (if running outside Docker)

---

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/migros-scraper.git
   cd migros-scraper
   ```

2. Create a `.env` file for environment variables. Use the provided `.env.example` as a template:
   ```bash
   cp .env.example .env
   ```

3. Build the Docker containers:
   ```bash
   docker compose build
   ```


---

## Usage

### Running the Scraper
To run the scraper via Docker:
```bash
docker compose run --rm scraper
```

To run locally (auto-detects uv or poetry):
```bash
./run.sh
```

Or manually with CLI options:
```bash
# With uv
uv run python -m src.playwright_scraper --two-phase --days 5 --headless

# With poetry
poetry run python -m src.playwright_scraper --two-phase --days 5 --headless
```

CLI options:
- `--two-phase`: Run three-phase scraping (edibles → new IDs → non-edibles)
- `--days N`: Re-scrape products not updated in N days (default: 5)
- `--headless`: Run browser in headless mode

### Running the Sync
To sync data from MongoDB to PostgreSQL:
```bash
docker compose run --rm sync
```

### Running Tests
To execute the test suite:
```bash
docker compose run --rm test
```

---

## Project Structure

```
migros-scraper/
├── src/
│   ├── models/              # Data models and factories
│   │   ├── product.py       # Product ORM model
│   │   ├── product_factory.py  # JSON → dataclass transformer
│   │   ├── offer.py         # Pricing model
│   │   ├── nutrition.py     # Nutritional info model
│   │   └── category.py      # Category model
│   ├── services/            # Database services
│   │   ├── mongo_service.py # MongoDB persistence layer
│   │   └── mongo_sql_sync.py  # MongoDB → PostgreSQL sync
│   ├── utils/               # Helper utilities
│   │   └── yeeter.py        # Color-coded logger
│   └── playwright_scraper.py  # Main scraper script
├── tests/                   # Unit and integration tests
├── docs/                    # Additional documentation
├── Dockerfile               # Dockerfile for the scraper
├── docker-compose.yml       # Docker Compose configuration
├── .env.example             # Example environment variables
├── pyproject.toml           # Poetry/uv configuration file
├── run.sh                   # Local run script (uv/poetry)
└── README.md                # Project documentation
```

---

## Testing

This project includes comprehensive unit and integration tests.

### Test Databases

- A **temporary MongoDB container** is spun up for each test run.
- Ensure the test-specific MongoDB is configured in the `.env` file under `TEST_MONGO_URI`.

### Run Tests
```bash
docker compose run --rm test
```

For a specific test:
```bash
docker compose run --rm test pytest -k test_name
```

For verbose output with logs:
```bash
docker compose run --rm test pytest -v -s
```

---

## Development Notes

### Adding Dependencies
Use Poetry or uv to manage Python dependencies:
```bash
# With poetry
poetry add <package_name>

# With uv
uv add <package_name>
```

### Debugging
- **MongoDB Connection Issues**: Ensure the `MONGO_URI` in the `.env` file matches the container's IP/hostname and port.
- **Web Scraping Errors**: Logs will be available in the `logs/` directory or directly in the console during runtime.

### Persistent Storage
- Production MongoDB uses a persistent volume (`mongo_data`).
- Test MongoDB uses temporary storage to ensure fresh data each run.
