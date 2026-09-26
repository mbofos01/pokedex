import json
import os
import signal
import time
from threading import Thread

import psycopg2
from psycopg2.extras import RealDictCursor

from confluent_kafka import KafkaError
from confluent_kafka.error import ConsumeError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer
from confluent_kafka import DeserializingConsumer
from prometheus_client import Counter, Histogram, Gauge, start_http_server

from shared.logging import get_logger

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC")  # pokemon-image.avsc -> api_requests
RESULT_TOPIC = os.getenv(
    "KAFKA_RESULT_TOPIC"
)  # pokemon-result.avsc -> metrics + pokemon_scans
GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP")
METRICS_PORT = int(os.getenv("METRICS_PORT"))
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT"),
}

running = True

# Prometheus metrics
classification_total = Counter(
    "pokemon_classifications_total",
    "Total number of Pokemon classifications processed",
    ["status"],
)

classification_confidence = Histogram(
    "pokemon_classification_confidence",
    "Distribution of confidence scores for classifications",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

unknown_classifications_total = Counter(
    "pokemon_unknown_classifications_total",
    "Total number of unknown Pokemon classifications",
)

pokemon_prediction_count = Gauge(
    "pokemon_prediction_count",
    "Count of predictions for each Pokemon (sampled at collection time)",
    ["pokemon_name"],
)

processing_duration_ms = Histogram(
    "pokemon_classification_processing_duration_ms",
    "Processing time for each classification in milliseconds",
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000),
)

user_classifications_total = Counter(
    "pokemon_user_classifications_total",
    "Total classifications per user",
    ["user_id"],
)


def identity(value, _context):
    return value


def stop(*_args):
    global running
    running = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def update_metrics(result):
    """Update Prometheus metrics from a classification result"""
    prediction = result.get("prediction", "Unknown")
    confidence = result.get("confidence", 0)
    user_id = result.get("user_id", "unknown")

    if prediction == "Unknown":
        classification_total.labels(status="unknown").inc()
        unknown_classifications_total.inc()
    else:
        classification_total.labels(status="success").inc()

    if confidence is not None:
        classification_confidence.observe(float(confidence))

    pokemon_prediction_count.labels(pokemon_name=prediction).inc()

    if user_id != "unknown":
        user_classifications_total.labels(user_id=user_id).inc()


def log_scan(result):
    request_id = result.get("request_id")
    details = result.get("pokemon_details")
    pokemon_id = details["id"] if details else -1
    pokemon_name = details["name"] if details else "Unknown"
    try:
        with psycopg2.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pokemon_scans
                        (request_id, pokemon_id, pokemon_name, confidence_score, user_id, source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        request_id,
                        pokemon_id,
                        pokemon_name,
                        result.get("confidence"),
                        result.get("user_id"),
                        "classifier",
                    ),
                )
    except psycopg2.Error as error:
        logger.error(f"Failed to log pokemon scan: {error}")


def log_api_request(result):
    try:
        with psycopg2.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO api_requests
                        (request_id, endpoint, filename, image_bytes,
                         client_ip, user_agent, forwarded_for)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        result.get("request_id"),
                        result.get("endpoint"),
                        result.get("filename"),
                        len(result.get("image_bytes", b"")),
                        result.get("client_ip"),
                        result.get("user_agent"),
                        result.get("forwarded_for"),
                    ),
                )
    except psycopg2.Error as error:
        logger.error(f"Failed to log api request: {error}")


def results_consumer():
    """Consumes enriched classification results from RESULT_TOPIC, updates metrics + pokemon_scans"""
    schema_registry = SchemaRegistryClient(
        {"url": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")}
    )

    try:
        with open(
            "/app/schemas/pokemon-enriched.avsc", encoding="utf-8"
        ) as schema_file:
            result_schema = schema_file.read()
    except FileNotFoundError:
        logger.error("Schema file not found at /app/schemas/pokemon-enriched.avsc")
        raise

    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry, result_schema, identity
            ),
            "group.id": f"{GROUP_ID}-results",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([RESULT_TOPIC])
    logger.info(f"Results consumer consuming from {RESULT_TOPIC}")

    try:
        while running:
            try:
                message = consumer.poll(1.0)
            except ConsumeError as error:
                logger.warning(f"Kafka topic not ready, retrying: {error}")
                continue

            if message is None:
                continue

            if message.error():
                if message.error().code() != KafkaError._PARTITION_EOF:
                    logger.error(f"Kafka consumer error: {message.error()}")
                continue

            try:
                result = message.value()
                request_id = result.get("request_id")
                prediction = result.get("prediction")
                confidence = result.get("confidence")
                processing_time = result.get("pipeline_duration_ms", 0)

                logger.info(
                    f"Recording metrics: request_id={request_id}, prediction={prediction}, confidence={confidence} - Listening to {RESULT_TOPIC}"
                )

                update_metrics(result)

                if processing_time:
                    processing_duration_ms.observe(float(processing_time))

                log_scan(result)

                consumer.commit(message=message, asynchronous=False)

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                consumer.commit(message=message, asynchronous=False)

    finally:
        consumer.close()
        logger.info("Results consumer closed")


def requests_consumer():
    """Consumes raw PokemonImage events from INPUT_TOPIC, logs to api_requests"""
    schema_registry = SchemaRegistryClient(
        {"url": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")}
    )

    try:
        with open("/app/schemas/pokemon-image.avsc", encoding="utf-8") as schema_file:
            image_schema = schema_file.read()
    except FileNotFoundError:
        logger.error("Schema file not found at /app/schemas/pokemon-image.avsc")
        raise

    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry, image_schema, identity
            ),
            "group.id": f"{GROUP_ID}-requests",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([INPUT_TOPIC])
    logger.info(f"Requests consumer consuming from {INPUT_TOPIC}")

    try:
        while running:
            try:
                message = consumer.poll(1.0)
            except ConsumeError as error:
                logger.warning(f"Kafka topic not ready, retrying: {error}")
                continue

            if message is None:
                continue

            if message.error():
                if message.error().code() != KafkaError._PARTITION_EOF:
                    logger.error(f"Kafka consumer error: {message.error()}")
                continue

            try:
                log_api_request(message.value())
                consumer.commit(message=message, asynchronous=False)
            except Exception as e:
                logger.error(f"Error logging api request: {e}", exc_info=True)
                consumer.commit(message=message, asynchronous=False)

    finally:
        consumer.close()
        logger.info("Requests consumer closed")


def main():
    global logger
    logger = get_logger("pokemon-metrics")
    logger.info("Starting Pokemon Metrics Service")

    logger.info(f"Starting Prometheus metrics server on port {METRICS_PORT}")
    start_http_server(METRICS_PORT)

    results_thread = Thread(target=results_consumer, daemon=False)
    requests_thread = Thread(target=requests_consumer, daemon=False)
    results_thread.start()
    requests_thread.start()

    try:
        results_thread.join()
        requests_thread.join()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        stop()
        results_thread.join(timeout=10)
        requests_thread.join(timeout=10)


if __name__ == "__main__":
    main()
