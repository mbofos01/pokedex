import os
import signal

from dotenv import load_dotenv
from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC = os.getenv("TOPIC", "demo-messages")
GROUP_ID = os.getenv("GROUP_ID", "demo-consumer-group")
SECURITY_PROTOCOL = os.getenv("SECURITY_PROTOCOL", "plaintext").lower()
SSL_CA_LOCATION = os.getenv("SSL_CA_LOCATION")
SSL_CERTIFICATE_LOCATION = os.getenv("SSL_CERTIFICATE_LOCATION")
SSL_KEY_LOCATION = os.getenv("SSL_KEY_LOCATION")

running = True


def _stop(*_args):
    global running
    running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def from_dict(data, _ctx):
    return data


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
    avro_deserializer = AvroDeserializer(schema_registry_client, None, from_dict)

    consumer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "key.deserializer": StringDeserializer("utf_8"),
        "value.deserializer": avro_deserializer,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        # fail-proofing: only advance offsets after successful processing
        "enable.auto.commit": False,
    }
    if SECURITY_PROTOCOL == "ssl":
        # mTLS: present our client cert and verify the broker's cert against our CA
        consumer_conf.update(
            {
                "security.protocol": "SSL",
                "ssl.ca.location": SSL_CA_LOCATION,
                "ssl.certificate.location": SSL_CERTIFICATE_LOCATION,
                "ssl.key.location": SSL_KEY_LOCATION,
            }
        )
    consumer = DeserializingConsumer(consumer_conf)

    consumer.subscribe([TOPIC])
    print(f"Consuming from topic '{TOPIC}' on {BOOTSTRAP_SERVERS}...")

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"✗ Consumer error: {msg.error()}")
                continue

            value = msg.value()
            try:
                print(f"✓ Received: key={msg.key()} value={value}")
                # commit only after the message has been fully handled
                consumer.commit(message=msg, asynchronous=False)
            except Exception as e:
                print(f"✗ Failed to process message, not committing offset: {e}")
    finally:
        print("Closing consumer...")
        consumer.close()


if __name__ == "__main__":
    main()
