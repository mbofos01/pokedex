FROM python:3.11-slim

WORKDIR /app

# Install curl for uv
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

# Install dependencies
COPY pkmn-api/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Expose port
EXPOSE 8000

# Copy shared modules
COPY shared/ ./shared/

# Run FastAPI
CMD ["uvicorn", "src.router:app", "--host", "0.0.0.0", "--port", "8000"]
