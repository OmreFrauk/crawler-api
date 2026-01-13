FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright and build tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run crawl4ai setup (this handles Playwright browser installation)
RUN crawl4ai-setup
RUN playwright install chromium

# Copy the rest of the application code
COPY app.py .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
