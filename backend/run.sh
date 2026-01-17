#!/bin/bash

# Simple run script for the backend

# Set default environment variables if not already set
export DEBUG="${DEBUG:-true}"
export CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:5173\",\"http://localhost:3000\",\"http://localhost\"]}"

echo "Starting Workplace Navigator Backend..."

# Run the application
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
