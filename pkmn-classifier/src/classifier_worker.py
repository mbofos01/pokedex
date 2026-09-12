import io
import json
import os
import time

import torch
from confluent_kafka import KafkaError
from confluent_kafka.error import ConsumeError

from shared.logging import get_logger
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringDeserializer, StringSerializer
from confluent_kafka import DeserializingConsumer, SerializingProducer
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
TO_BE_CLASSIFIED_TOPIC = os.getenv("KAFKA_INPUT_TOPIC")
TO_BE_ENHANCED_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC")
GROUP_ID = os.getenv("KAFKA_CONSUMER_GROUP")
CONFIDENCE_THRESHOLD = 0.5


def identity(value, _context):
    return value


def main():
    schema_registry = SchemaRegistryClient(
        {"url": os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")}
    )
    with open("/app/schemas/pokemon-image.avsc", encoding="utf-8") as schema_file:
        image_schema = schema_file.read()
    with open("/app/schemas/pokemon-result.avsc", encoding="utf-8") as schema_file:
        result_schema = schema_file.read()
    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry, image_schema, identity
            ),
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            # topic may not exist yet if pkmn-api hasn't produced to it; let the
            # broker (KAFKA_AUTO_CREATE_TOPICS_ENABLE) create it on first metadata request
            "allow.auto.create.topics": True,
        }
    )
    producer = SerializingProducer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "key.serializer": StringSerializer("utf_8"),
            "value.serializer": AvroSerializer(
                schema_registry, result_schema, identity
            ),
            "acks": "all",
            "enable.idempotence": True,
            "retries": 10,
            "retry.backoff.ms": 500,
        }
    )
    consumer.subscribe([TO_BE_CLASSIFIED_TOPIC])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ViTForImageClassification.from_pretrained(
        "skshmjn/Pokemon-classifier-gen9-1025"
    ).to(device)
    processor = ViTImageProcessor.from_pretrained(
        "skshmjn/Pokemon-classifier-gen9-1025"
    )
    model.eval()
    logger = get_logger("pokemon-classifier")
    logger.info(
        f"Classifier consuming {TO_BE_CLASSIFIED_TOPIC}; model running on {device}"
    )

    try:
        while True:
            try:
                message = consumer.poll(1.0)
            except ConsumeError as error:
                # topic not created yet (e.g. pkmn-api hasn't produced its first message) or
                # broker briefly unreachable; back off and retry instead of crashing the loop
                if error.args[0].code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    logger.warning(
                        f"Topic {TO_BE_CLASSIFIED_TOPIC} not available yet, retrying..."
                    )
                else:
                    logger.error(f"Kafka consume error: {error}")
                time.sleep(1.0)
                continue
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(f"Kafka consumer error: {message.error()}")
                continue

            try:
                data = message.value()
                request_id = data["request_id"]
                filename = data.get("filename", "upload.jpg")
                logger.info(
                    f"Received image to classify: request_id={request_id}, filename={filename} - Listening to {TO_BE_CLASSIFIED_TOPIC}"
                )
                image = Image.open(io.BytesIO(data["image_bytes"])).convert("RGB")
                inputs = processor(images=image, return_tensors="pt").to(device)
                with torch.no_grad():
                    probabilities = torch.nn.functional.softmax(
                        model(**inputs).logits, dim=-1
                    )
                confidence, prediction_id = torch.max(probabilities, dim=-1)
                confidence = confidence.item()
                prediction = (
                    "Unknown"
                    if confidence < CONFIDENCE_THRESHOLD
                    else model.config.id2label[prediction_id.item()]
                )
                result = {
                    "request_id": request_id,
                    "filename": data.get("filename", "upload.jpg"),
                    "prediction": prediction,
                    "confidence": round(confidence, 4),
                    "classified_at": int(time.time() * 1000),
                    "schema_version": 1,
                }
                producer.produce(
                    TO_BE_ENHANCED_TOPIC,
                    key=request_id,
                    value=result,
                )
                producer.flush(10)
                consumer.commit(message=message, asynchronous=False)
                logger.info(
                    f"Sent classification result: request_id={request_id}, prediction={prediction}, confidence={confidence:.4f} - Sent to {TO_BE_ENHANCED_TOPIC}"
                )
            except Exception as error:
                logger.error(f"Failed to process message: {error}")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
