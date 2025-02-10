# Use Python 3.11 slim as base image for better performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y

# Create necessary directories
RUN mkdir -p /tmp/docsapp/logs /tmp/docsapp/data /tmp/docsapp/db /etc/secrets

# Copy the rest of the application
COPY . .

# Create config.py from example
RUN cp -v config.example.py config.py && \
    ls -la config.py && \
    echo "Config file created successfully"

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Healthcheck command
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

# Start command
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--worker-class", "aiohttp.worker.GunicornWebWorker", "--log-level", "debug", "app:app"] 