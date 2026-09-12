import asyncio
import io
import os
import threading
import time
import uuid

from confluent_kafka import KafkaError
from confluent_kafka.error import ConsumeError
from fastapi import Request

from shared.logging import get_logger
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringDeserializer, StringSerializer
from confluent_kafka import DeserializingConsumer, SerializingProducer
from fastapi import FastAPI, File, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

MAX_IMAGE_DIMENSION = 800


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
IMAGE_TOPIC = os.getenv("KAFKA_INPUT_TOPIC")
RESULT_TOPIC = os.getenv("KAFKA_RESULT_TOPIC")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")


def identity(value, _context):
    return value


with open("/app/schemas/pokemon-image.avsc", encoding="utf-8") as schema_file:
    IMAGE_SCHEMA = schema_file.read()

app = FastAPI(
    title="Pokemon Classifier Gateway",
    docs_url="/swagger",
    redoc_url="/docs",
    openapi_url="/openapi.json",
    root_path="/pkmn-api",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

schema_registry = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
producer = SerializingProducer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "key.serializer": StringSerializer("utf_8"),
        "value.serializer": AvroSerializer(schema_registry, IMAGE_SCHEMA, identity),
        "acks": "all",
        "enable.idempotence": True,
        "retries": 10,
        "retry.backoff.ms": 500,
    }
)

running = True

logger = get_logger("pokemon-api")


def delivery_report(error, message):
    if error is not None:
        logger.error(f"Kafka delivery failed for key={message.key()}: {error}")


def consume_results(loop: asyncio.AbstractEventLoop):
    with open("/app/schemas/pokemon-enriched.avsc", encoding="utf-8") as schema_file:
        result_schema = schema_file.read()
    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry, result_schema, identity
            ),
            "group.id": "pokedex-gateway",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            # pokemon-enriched only exists once pkmn-enhancement has produced its first message;
            # let the broker (KAFKA_AUTO_CREATE_TOPICS_ENABLE) create it on first metadata request
            "allow.auto.create.topics": True,
        }
    )
    consumer.subscribe([RESULT_TOPIC])
    logger.info(f"Gateway consuming from {RESULT_TOPIC}")

    try:
        while running:
            try:
                message = consumer.poll(1.0)
            except ConsumeError as error:
                logger.warning(f"Kafka topic not ready, retrying: {error}")
                time.sleep(1.0)
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
                f"Received enriched result: request_id={request_id}, prediction={prediction}, confidence={confidence} - Listening to {RESULT_TOPIC}"
            )
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()


@app.on_event("startup")
async def startup_event():
    thread = threading.Thread(
        target=consume_results,
        args=(asyncio.get_running_loop(),),
        daemon=True,
    )
    thread.start()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "kafka": KAFKA_BOOTSTRAP_SERVERS}


@app.post("/classify-pokemon/")
async def classify_pokemon(
    request: Request,
    file: UploadFile = File(...),
    x_request_id: str | None = Header(default=None),
):

    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    forwarded_for = request.headers.get("x-forwarded-for", "unknown")
    request_id = x_request_id or str(uuid.uuid4())
    contents = await file.read()
    if not contents:
        return {"status": "error", "request_id": request_id, "message": "Empty file"}

    # downsize oversized uploads so the encoded message stays under Kafka's message size limit
    image = Image.open(io.BytesIO(contents))
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail(
            (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS
        )
    if image.mode != "RGB":
        image = image.convert("RGB")
    compressed = io.BytesIO()
    image.save(compressed, format="JPEG", quality=85)
    contents = compressed.getvalue()

    event = {
        "request_id": request_id,
        "endpoint": "/classify-pokemon/",
        "timestamp": int(time.time() * 1000),
        "client_ip": client_ip,
        "user_agent": user_agent,
        "forwarded_for": forwarded_for,
        "filename": file.filename or "upload.jpg",
        "image_bytes": contents.hex(),
        "schema_version": 1,
    }
    producer.produce(
        IMAGE_TOPIC,
        key=request_id,
        value={**event, "image_bytes": contents},
        on_delivery=delivery_report,
    )
    logger.info(
        f"Produced image event: request_id={request_id} - Sent to {IMAGE_TOPIC}"
    )
    producer.poll(0)
    producer.flush(10)
    return {"status": "processing", "request_id": request_id}


@app.on_event("shutdown")
async def shutdown_event():
    global running
    running = False
    producer.flush(10)
