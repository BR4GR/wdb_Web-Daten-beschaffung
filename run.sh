#!/usr/bin/env bash
set -e

# Check for uv first, fall back to poetry
if command -v uv &> /dev/null; then
    echo "Using uv..."
    uv run python -m src.playwright_scraper --two-phase --days 5 --headless
elif command -v poetry &> /dev/null; then
    echo "Using poetry..."
    poetry run python -m src.playwright_scraper --two-phase --days 5 --headless
else
    echo "Error: Neither uv nor poetry found. Please install one of them."
    exit 1
fi
