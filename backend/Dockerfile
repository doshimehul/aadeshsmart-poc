
# Use an official Python runtime
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install Python dependencies first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application from the repository's backend directory.
COPY backend/ .

COPY alembic.ini .

# Create directory for uploaded recordings
RUN mkdir -p /app/uploads

# FastAPI application port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
