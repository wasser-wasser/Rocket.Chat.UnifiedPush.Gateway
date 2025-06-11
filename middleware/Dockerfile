# Use an official Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies needed by pywebpush and others
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set the environment variables
ENV FLASK_APP=UP_middleware.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production
ENV vapid_private_key=wwwwwwwwwwwwwwwwwwwww
ENV vapid_public_key=wwwwwwwwwwwwwwwwwwwww
ENV NTFY_AUTH_TOKEN=cccccccccccccccccccccccccccccccc
ENV REDIS_HOST=localhost
ENV REDIS_PORT=6379


# Expose the Flask port
EXPOSE 5001

# Run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
