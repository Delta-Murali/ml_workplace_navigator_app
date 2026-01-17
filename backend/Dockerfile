# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PostGIS/GDAL
RUN apt-get update && apt-get install -y \
    libpq-dev \
    libgdal-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY app ./app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
