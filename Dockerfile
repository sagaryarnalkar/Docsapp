# Use Python 3.9 slim as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /tmp/docsapp/logs /tmp/docsapp/data /tmp/docsapp/db

# Expose port
EXPOSE 8080

# Healthcheck command
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1

# Start command
CMD ["python", "app.py"] 