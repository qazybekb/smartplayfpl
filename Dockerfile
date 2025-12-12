# Dockerfile for Railway backend deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt .
COPY backend/runtime.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Expose port (Railway will set $PORT)
EXPOSE 8000

# Start the FastAPI application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
