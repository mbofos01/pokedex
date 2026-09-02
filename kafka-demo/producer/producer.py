import os
import time
import uuid
import signal
import sys

from dotenv import load_dotenv
from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC = os.getenv("TOPIC", "demo-messages")
SECURITY_PROTOCOL = os.getenv("SECURITY_PROTOCOL", "plaintext").lower()
SSL_CA_LOCATION = os.getenv("SSL_CA_LOCATION")
SSL_CERTIFICATE_LOCATION = os.getenv("SSL_CERTIFICATE_LOCATION")
SSL_KEY_LOCATION = os.getenv("SSL_KEY_LOCATION")
MESSAGE_COUNT = int(os.getenv("MESSAGE_COUNT", "10"))

SCHEMA_PATH = os.getenv(
    "SCHEMA_PATH",
    os.path.join(os.path.dirname(__file__), "..", "schemas", "message.avsc"),
)
with open(SCHEMA_PATH, "r") as f:
    MESSAGE_SCHEMA = f.read()

running = True


def _stop(*_args):
    global running
    running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def delivery_report(err, msg):
    if err is not None:
        print(f"✗ Delivery failed for key={msg.key()}: {err}")
    else:
        print(
            f"✓ Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}"
        )


def to_dict(message_obj, _ctx):
    return message_obj


def main():
    schema_registry_conf = {"url": SCHEMA_REGISTRY_URL}
    if SECURITY_PROTOCOL == "ssl":
        # mTLS: authenticate to the registry with our client cert too
        schema_registry_conf.update(
            {
                "ssl.ca.location": SSL_CA_LOCATION,
                "ssl.certificate.location": SSL_CERTIFICATE_LOCATION,
                "ssl.key.location": SSL_KEY_LOCATION,
            }
        )
    schema_registry_client = SchemaRegistryClient(schema_registry_conf)
    avro_serializer = AvroSerializer(schema_registry_client, MESSAGE_SCHEMA, to_dict)

    producer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "key.serializer": StringSerializer("utf_8"),
        "value.serializer": avro_serializer,
        # fail-proofing: wait for all in-sync replicas and retry transient errors
        "acks": "all",
        "enable.idempotence": True,
        "retries": 10,
        "retry.backoff.ms": 500,
    }
    if SECURITY_PROTOCOL == "ssl":
        # mTLS: present our client cert and verify the broker's cert against our CA
        producer_conf.update(
            {
                "security.protocol": "SSL",
                "ssl.ca.location": SSL_CA_LOCATION,
                "ssl.certificate.location": SSL_CERTIFICATE_LOCATION,
                "ssl.key.location": SSL_KEY_LOCATION,
            }
        )
    producer = SerializingProducer(producer_conf)

    print(
        f"Producing {MESSAGE_COUNT} message(s) to topic '{TOPIC}' on {BOOTSTRAP_SERVERS}..."
    )
    counter = 0
    while running and counter < MESSAGE_COUNT:
        counter += 1
        message = {
            "id": str(uuid.uuid4()),
            "message": f"Hello Kafka #{counter}",
            "timestamp": int(time.time() * 1000),
        }
        try:
            print(f"[{counter}/{MESSAGE_COUNT}] Producing: {message}")
            producer.produce(
                topic=TOPIC,
                key=message["id"],
                value=message,
                on_delivery=delivery_report,
            )
        except BufferError:
            print("✗ Local producer queue is full, waiting for free space...")
            producer.poll(1)
            counter -= 1
            continue

        producer.poll(0)
        if counter < MESSAGE_COUNT:
            time.sleep(2)

    print(f"Produced {counter}/{MESSAGE_COUNT} message(s). Flushing before shutdown...")
    producer.flush(10)
    print("Done.")


if __name__ == "__main__":
    main()
