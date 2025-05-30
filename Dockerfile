FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements_graphrag.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_graphrag.txt

# Copy application files
COPY . .

# Create a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port 80 for Streamlit
EXPOSE 80

# Command to run Streamlit on port 80
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=80", "--server.address=0.0.0.0", "--server.headless=true"] 