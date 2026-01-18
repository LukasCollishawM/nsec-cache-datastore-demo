FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install DNS tools for debugging
RUN apt-get update && apt-get install -y \
    dnsutils \
    ldnsutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir dnspython pytest click

# Copy application code
COPY nsecchain/ ./nsecchain/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Make scripts executable
RUN chmod +x scripts/*.py

# Default command
CMD ["tail", "-f", "/dev/null"]
