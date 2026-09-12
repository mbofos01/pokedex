FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && mv /root/.local/bin/uv /usr/local/bin/uv

COPY pkmn-enhancement/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY pkmn-enhancement/src/ ./src/
COPY shared/ ./shared/

CMD ["python", "src/main.py"]