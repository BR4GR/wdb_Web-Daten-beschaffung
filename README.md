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
The **Migros Scraper Project** is a web scraping and data processing application designed to collect product information from the Migros online store. The project saves the scraped data in both MongoDB (NoSQL) and PostgreSQL (SQL). Saving it to SQL is benefitial because then we already have parsed and filered information. Saving it to mongoDB is an easy way to save all available information, this way we can later add any information we want to our parsed data.

---

## Features

- Scrapes product categories and detailed product data from Migros.
- Saves data in MongoDB for flexible NoSQL operations.
- Saves data in PostgreSQL for structured SQL analysis. (tbd)
- Supports running multiple database containers (e.g., development and testing).
- Includes robust error handling with detailed logging.
- Unit-tested for reliability.
- Dockerized for easy deployment and testing.

---

## Prerequisites
Ensure the following software is installed on your system:

- [Docker](https://docs.docker.com/get-docker/) (latest version recommended)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Poetry](https://python-poetry.org/) for dependency management
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
To run the scraper:
```bash
docker compose run --rm scraper
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
│   ├── data/                # Example JSON data for testing
│   ├── services/            # MongoDB service and database helpers
│   ├── utils/               # Helper utilities (e.g., Yeeter
logging)
│   ├── models.py            # SQLAlchemy models for PostgreSQL
│   ├── migros_scraper.py    # Main scraper script
│   ├── sql_db.py            # PostgreSQL database connection
│   └── tests/               # Unit and integration tests
├── tests/                   # Unit and integration tests
├── Dockerfile               # Dockerfile for the scraper
├── docker-compose.yml       # Docker Compose configuration
├── .env.example             # Example environment variables
├── pyproject.toml           # Poetry configuration file
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
for a specific test:
```bash
docker compose run --rm test pytest -k test_handle_unexpected_error
```
for only scraper tests:
```bash
docker-compose run --rm test pytest -v -s tests/test_migros_scraper.py
```
Where -v stands for verbose output and -s also displays the logs.
Both are optional.

---

## Development Notes

### Adding Dependencies
Use Poetry to manage Python dependencies. Inside the container, you can add new libraries like this:
```bash
poetry add <package_name>
```

### Debugging
- **MongoDB Connection Issues**: Ensure the `MONGO_URI` in the `.env` file matches the container’s IP/hostname and port.
- **Web Scraping Errors**: Logs will be available in the `logs/` directory or directly in the console during runtime.

### Persistent Storage
- Production MongoDB uses a persistent volume (`mongo_data`).
- Test MongoDB uses temporary storage to ensure fresh data each run.