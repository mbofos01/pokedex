FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY producer/requirements.txt producer/requirements.txt
RUN pip install --no-cache-dir -r producer/requirements.txt

COPY schemas/ schemas/
COPY producer/producer.py producer/producer.py

CMD ["python", "producer/producer.py"]
