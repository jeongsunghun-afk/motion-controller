# Lightweight runtime container for MCX Client App
FROM python:3.10-slim

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy wheels and requirements first for better caching
COPY wheels/ /app/wheels/
RUN if [ -f /app/wheels/requirements.txt ]; then \
    pip install --no-cache-dir --no-index --find-links /app/wheels -r /app/wheels/requirements.txt; \
    fi

# Copy application files
COPY src/ /app/src/
COPY *.py /app/

# Set environment variable to indicate deployment
ENV DEPLOYED=True
ENV PYTHONUNBUFFERED=1

# Default command (will be overridden by systemd)
CMD ["python3", "/app/mcx-client-app.py"]
