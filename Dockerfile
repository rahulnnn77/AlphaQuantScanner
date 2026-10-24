# AlphaQuant Production Multi-Stage Container
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application backend and built static frontend
COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/
COPY .env.example /app/.env

# Create data directories
RUN mkdir -p /app/backend/data

EXPOSE 8080

WORKDIR /app/backend
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
