FROM python:3.12

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    build-essential \
    curl \
    unzip \
    wget \
    gnupg \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*


# Install Poetry
ENV POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Set the working directory
WORKDIR /app

# Copy the Poetry configuration files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi

# The application code will be mounted via volumes, so no need to copy it


# Set environment variables
ENV PYTHONUNBUFFERED=1
