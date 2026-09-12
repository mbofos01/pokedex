import json
import os
import signal
import time

import psycopg2
from confluent_kafka import KafkaError
from confluent_kafka.error import ConsumeError

from shared.logging import get_logger
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringDeserializer, StringSerializer
from confluent_kafka import DeserializingConsumer, SerializingProducer
from psycopg2.extras import RealDictCursor


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
CLASSIFIED_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC")
OUTPUT_TOPIC = os.getenv("KAFKA_RESULT_TOPIC")
GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP")
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT"),
}
running = True


def identity(value, _context):
    return value


def stop(*_args):
    global running
    running = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def get_pokemon_details(pokemon_name):
    with psycopg2.connect(**DB_CONFIG) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, name, height, weight, base_experience
                FROM pokemon
                WHERE LOWER(REGEXP_REPLACE(
                    REPLACE(REPLACE(REPLACE(name, '♂', 'm'), '♀', 'f'), '''', ''),
                    E'[^a-z0-9]', '', 'g'
                )) = LOWER(REGEXP_REPLACE(
                    REPLACE(REPLACE(REPLACE(LOWER(%s), '♂', 'm'), '♀', 'f'), '''', ''),
                    E'[^a-z0-9]', '', 'g'
                ))
                """,
                (pokemon_name,),
            )
            pokemon = cursor.fetchone()
            if not pokemon:
                return None

            pokemon_id = pokemon["id"]
            cursor.execute(
                "SELECT type_name FROM types WHERE pokemon_id = %s", (pokemon_id,)
            )
            types = [row["type_name"] for row in cursor.fetchall()]
            cursor.execute(
                "SELECT stat_name, base_stat FROM stats WHERE pokemon_id = %s",
                (pokemon_id,),
            )
            stats = {row["stat_name"]: row["base_stat"] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT ability_name FROM abilities WHERE pokemon_id = %s AND is_hidden = false",
                (pokemon_id,),
            )
            abilities = [row["ability_name"] for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT url FROM images
                WHERE pokemon_id = %s AND image_type = 'other_official-artwork'
                LIMIT 1
                """,
                (pokemon_id,),
            )
            image = cursor.fetchone()

            return {
                **dict(pokemon),
                "types": types,
                "stats": stats,
                "abilities": abilities,
                "official_artwork": image["url"] if image else None,
            }


def main():
    schema_registry = SchemaRegistryClient(
        {"url": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")}
    )
    with open("/app/schemas/pokemon-result.avsc", encoding="utf-8") as schema_file:
        result_schema = schema_file.read()
    with open("/app/schemas/pokemon-enriched.avsc", encoding="utf-8") as schema_file:
        enriched_schema = schema_file.read()
    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry, result_schema, identity
            ),
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    producer = SerializingProducer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.serializer": StringSerializer("utf_8"),
            "value.serializer": AvroSerializer(
                schema_registry, enriched_schema, identity
            ),
            "acks": "all",
            "enable.idempotence": True,
            "retries": 10,
            "retry.backoff.ms": 500,
        }
    )
    consumer.subscribe([CLASSIFIED_TOPIC])
    logger = get_logger("pokemon-enhancement")
    logger.info(f"Enhancement service consuming from {CLASSIFIED_TOPIC}")

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

            result = message.value()
            request_id = result.get("request_id")
            prediction = result.get("prediction")
            confidence = result.get("confidence")
            logger.info(
                f"Received classification result: request_id={request_id}, prediction={prediction}, confidence={confidence} - Listening to {CLASSIFIED_TOPIC}"
            )
            started = time.perf_counter()
            details = (
                None
                if prediction in (None, "Unknown")
                else get_pokemon_details(prediction)
            )
            if details:
                logger.info(
                    f"Enriched with pokemon details: request_id={request_id}, pokemon_id={details['id']}, pokemon_name={details['name']}"
                )
            else:
                logger.info(
                    f"No pokemon details found for prediction: request_id={request_id}, prediction={prediction}"
                )
            enriched = {
                **result,
                "pokemon_details": details,
                "enriched_at": int(time.time() * 1000),
                "pipeline_duration_ms": int((time.perf_counter() - started) * 1000),
                "schema_version": 1,
            }
            request_id = result["request_id"]
            producer.produce(
                OUTPUT_TOPIC,
                key=request_id,
                value=enriched,
            )
            producer.flush(10)
            consumer.commit(message=message, asynchronous=False)
            logger.debug(
                f"Sent enriched event: request_id={request_id}, pipeline_duration_ms={enriched['pipeline_duration_ms']}ms - Sent to {OUTPUT_TOPIC}"
            )
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
