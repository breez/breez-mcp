FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install system build dependencies required by breez-sdk-spark
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (only what we need at runtime)
COPY src ./src
COPY entrypoint.sh ./entrypoint.sh

# Create non-root user and ensure directories exist
RUN useradd --create-home --shell /bin/bash breez && \
    mkdir -p /app/data /app/logs && \
    chown -R breez:breez /app && \
    chmod +x /app/entrypoint.sh

USER breez

# Expose HTTP port for API access
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
