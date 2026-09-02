FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY consumer/requirements.txt consumer/requirements.txt
RUN pip install --no-cache-dir -r consumer/requirements.txt

COPY consumer/consumer.py consumer/consumer.py

CMD ["python", "consumer/consumer.py"]
