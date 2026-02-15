FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY e2e-tests/requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV TEST_MODE=true

# Default command
CMD ["pytest"]
