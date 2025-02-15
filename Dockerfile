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
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories with correct permissions
RUN mkdir -p /tmp/docsapp/logs /tmp/docsapp/data /tmp/docsapp/db /etc/secrets \
    && chmod -R 755 /tmp/docsapp

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV TEMP_DIR=/tmp/docsapp
ENV LOGS_DIR=/tmp/docsapp/logs
ENV DATA_DIR=/tmp/docsapp/data
ENV DB_DIR=/tmp/docsapp/db

# Expose port
EXPOSE 8080

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

# Start command
CMD ["hypercorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--keep-alive", "120", "--graceful-timeout", "60", "--access-log", "-", "--error-log", "-", "--log-level", "DEBUG", "app:app"] 