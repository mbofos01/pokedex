FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install curl for uv
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

# Install dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy source code
COPY src/ ./src/

# Default command to run your consumer
CMD ["python", "src/main.py"]
