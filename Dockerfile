# Use official Python slim image
FROM python:3.11-slim

# Install ffmpeg and other system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
