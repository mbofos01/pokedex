import asyncio
import io
import os
import threading
import time
import uuid

from confluent_kafka import KafkaError
from confluent_kafka.error import ConsumeError
from confluent_kafka import DeserializingConsumer, SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import StringDeserializer, StringSerializer

from fastapi import FastAPI, File, Header, Request, UploadFile, WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from PIL import Image

from shared.logging import get_logger


# ============================================================
# Configuration
# ============================================================

MAX_IMAGE_DIMENSION = 800

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
IMAGE_TOPIC = os.getenv("KAFKA_INPUT_TOPIC")
RESULT_TOPIC = os.getenv("KAFKA_RESULT_TOPIC")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")


# ============================================================
# Logging
# ============================================================

logger = get_logger("pokemon-api")


# ============================================================
# Helpers
# ============================================================


def identity(value, _context):
    return value


# ============================================================
# Load schemas
# ============================================================

with open(
    "/app/schemas/pokemon-image.avsc",
    encoding="utf-8",
) as schema_file:
    IMAGE_SCHEMA = schema_file.read()


with open(
    "/app/schemas/pokemon-enriched.avsc",
    encoding="utf-8",
) as schema_file:
    RESULT_SCHEMA = schema_file.read()


# ============================================================
# FastAPI
# ============================================================

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


# ============================================================
# Schema Registry
# ============================================================

schema_registry = SchemaRegistryClient(
    {
        "url": SCHEMA_REGISTRY_URL,
    }
)


# ============================================================
# Kafka Producer
# ============================================================

producer = SerializingProducer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "key.serializer": StringSerializer("utf_8"),
        "value.serializer": AvroSerializer(
            schema_registry,
            IMAGE_SCHEMA,
            identity,
        ),
        "acks": "all",
        "enable.idempotence": True,
        "retries": 10,
        "retry.backoff.ms": 500,
    }
)


# ============================================================
# Application state
# ============================================================

running = True


# ============================================================
# WebSocket Connection Manager
# ============================================================


class ConnectionManager:
    """
    Keeps track of WebSocket connections by request_id.

    Example:

        request_id = "abc-123"

        connections["abc-123"] = websocket
    """

    def __init__(self):
        self.connections: dict[str, WebSocket] = {}
        self.lock = threading.Lock()

    async def connect(
        self,
        request_id: str,
        websocket: WebSocket,
    ):
        await websocket.accept()

        with self.lock:
            self.connections[request_id] = websocket

        logger.info(f"WebSocket connected: request_id={request_id}")

    def disconnect(self, request_id: str):
        with self.lock:
            self.connections.pop(request_id, None)

        logger.info(f"WebSocket disconnected: request_id={request_id}")

    def get(self, request_id: str):
        with self.lock:
            return self.connections.get(request_id)

    async def send_result(
        self,
        request_id: str,
        result: dict,
    ) -> bool:

        websocket = self.get(request_id)

        if websocket is None:
            logger.warning(f"No WebSocket connection found for request_id={request_id}")
            return False

        try:
            await websocket.send_json(
                {
                    "type": "classification-complete",
                    **result,
                }
            )

            logger.info(
                f"Classification result sent over WebSocket: request_id={request_id}"
            )

            return True

        except Exception as error:
            logger.error(
                f"Failed to send WebSocket result: "
                f"request_id={request_id}, "
                f"error={error}"
            )

            self.disconnect(request_id)

            return False


manager = ConnectionManager()


# ============================================================
# Kafka delivery callback
# ============================================================


def delivery_report(error, message):
    if error is not None:
        logger.error(f"Kafka delivery failed for key={message.key()}: {error}")
    else:
        logger.info(
            f"Kafka message delivered: "
            f"topic={message.topic()}, "
            f"partition={message.partition()}, "
            f"offset={message.offset()}, "
            f"key={message.key()}"
        )


# ============================================================
# Kafka Result Consumer
# ============================================================


def consume_results(loop: asyncio.AbstractEventLoop):
    """
    Runs in a background thread.

    Consumes enriched Pokemon classification results from Kafka
    and forwards them to the appropriate WebSocket based on
    request_id.
    """

    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": AvroDeserializer(
                schema_registry,
                RESULT_SCHEMA,
                identity,
            ),
            "group.id": "pokedex-gateway",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "allow.auto.create.topics": True,
        }
    )

    consumer.subscribe([RESULT_TOPIC])

    logger.info(f"Gateway consuming results from Kafka topic: {RESULT_TOPIC}")

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

            if not result:
                logger.warning("Received empty Kafka result")
                continue

            request_id = result.get("request_id")

            prediction = result.get("prediction")

            confidence = result.get("confidence")

            logger.info(
                f"Received enriched result: "
                f"request_id={request_id}, "
                f"prediction={prediction}, "
                f"confidence={confidence}"
            )

            if not request_id:
                logger.error("Kafka result has no request_id")

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

                continue

            # ------------------------------------------------
            # Send Kafka result to WebSocket.
            #
            # Kafka consumer runs in another thread, so we
            # schedule the coroutine on FastAPI's event loop.
            # ------------------------------------------------

            future = asyncio.run_coroutine_threadsafe(
                manager.send_result(
                    request_id,
                    result,
                ),
                loop,
            )

            try:
                delivered = future.result(timeout=10)

                if delivered:
                    logger.info(
                        f"Successfully delivered result: request_id={request_id}"
                    )
                else:
                    logger.warning(
                        f"Could not deliver result because "
                        f"WebSocket was not connected: "
                        f"request_id={request_id}"
                    )

            except Exception as error:
                logger.error(
                    f"Error delivering WebSocket result: "
                    f"request_id={request_id}, "
                    f"error={error}"
                )

            # ------------------------------------------------
            # Commit only after we've attempted delivery.
            # ------------------------------------------------

            consumer.commit(
                message=message,
                asynchronous=False,
            )

    finally:
        consumer.close()

        logger.info("Kafka result consumer stopped")


# ============================================================
# Startup
# ============================================================


@app.on_event("startup")
async def startup_event():

    global running

    running = True

    loop = asyncio.get_running_loop()

    thread = threading.Thread(
        target=consume_results,
        args=(loop,),
        daemon=True,
        name="pokemon-result-consumer",
    )

    thread.start()

    logger.info("Pokemon API started")

    logger.info(f"Kafka bootstrap servers: {KAFKA_BOOTSTRAP_SERVERS}")

    logger.info(f"Image topic: {IMAGE_TOPIC}")

    logger.info(f"Result topic: {RESULT_TOPIC}")


# ============================================================
# WebSocket endpoint
# ============================================================


@app.websocket("/ws/{request_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    request_id: str,
):
    """
    React Native connects here before uploading the image.

    Example:

        wss://your-ngrok-url/pkmn-api/ws/abc123
    """

    await manager.connect(
        request_id,
        websocket,
    )

    try:
        while True:
            # ------------------------------------------------
            # We don't actually need messages from the client.
            #
            # receive_text() simply keeps the connection alive
            # and allows FastAPI to detect a disconnected client.
            # ------------------------------------------------

            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(request_id)

    except Exception as error:
        logger.error(f"WebSocket error: request_id={request_id}, error={error}")

        manager.disconnect(request_id)


# ============================================================
# Health check
# ============================================================


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "kafka": KAFKA_BOOTSTRAP_SERVERS,
        "image_topic": IMAGE_TOPIC,
        "result_topic": RESULT_TOPIC,
    }


# ============================================================
# Image classification endpoint
# ============================================================


@app.post("/classify-pokemon/")
async def classify_pokemon(
    request: Request,
    file: UploadFile = File(...),
    x_request_id: str | None = Header(default=None),
):

    # --------------------------------------------------------
    # Request metadata
    # --------------------------------------------------------

    client_ip = request.client.host if request.client else "unknown"

    user_agent = request.headers.get(
        "user-agent",
        "unknown",
    )

    forwarded_for = request.headers.get(
        "x-forwarded-for",
        "unknown",
    )

    request_id = x_request_id or str(uuid.uuid4())

    logger.info(
        f"Received classification request: "
        f"request_id={request_id}, "
        f"filename={file.filename}"
    )

    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    contents = await file.read()

    if not contents:
        logger.warning(f"Empty image upload: request_id={request_id}")

        return {
            "status": "error",
            "request_id": request_id,
            "message": "Empty file",
        }

    # --------------------------------------------------------
    # Open image
    # --------------------------------------------------------

    try:
        image = Image.open(io.BytesIO(contents))

        image.load()

    except Exception as error:
        logger.error(f"Invalid image: request_id={request_id}, error={error}")

        return {
            "status": "error",
            "request_id": request_id,
            "message": "Invalid image file",
        }

    # --------------------------------------------------------
    # Resize large images
    # --------------------------------------------------------

    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail(
            (
                MAX_IMAGE_DIMENSION,
                MAX_IMAGE_DIMENSION,
            ),
            Image.Resampling.LANCZOS,
        )

    # --------------------------------------------------------
    # Convert to RGB
    # --------------------------------------------------------

    if image.mode != "RGB":
        image = image.convert("RGB")

    # --------------------------------------------------------
    # Compress to JPEG
    # --------------------------------------------------------

    compressed = io.BytesIO()

    image.save(
        compressed,
        format="JPEG",
        quality=85,
        optimize=True,
    )

    contents = compressed.getvalue()

    # --------------------------------------------------------
    # Kafka event
    # --------------------------------------------------------

    event = {
        "request_id": request_id,
        "endpoint": "/classify-pokemon/",
        "timestamp": int(time.time() * 1000),
        "client_ip": client_ip,
        "user_agent": user_agent,
        "forwarded_for": forwarded_for,
        "filename": file.filename or "upload.jpg",
        "image_bytes": contents,
        "schema_version": 1,
    }

    # --------------------------------------------------------
    # Produce Kafka message
    # --------------------------------------------------------

    try:
        producer.produce(
            IMAGE_TOPIC,
            key=request_id,
            value=event,
            on_delivery=delivery_report,
        )

        # Give confluent-kafka a chance to process callbacks.
        producer.poll(0)

        # Wait for delivery.
        producer.flush(10)

    except Exception as error:
        logger.error(f"Kafka produce failed: request_id={request_id}, error={error}")

        return {
            "status": "error",
            "request_id": request_id,
            "message": "Failed to send image for processing",
        }

    logger.info(f"Produced image event: request_id={request_id}, topic={IMAGE_TOPIC}")

    # --------------------------------------------------------
    # Return immediately.
    #
    # The actual result comes through WebSocket.
    # --------------------------------------------------------

    return {
        "status": "processing",
        "request_id": request_id,
    }


# ============================================================
# Shutdown
# ============================================================


@app.on_event("shutdown")
async def shutdown_event():

    global running

    running = False

    logger.info("Shutting down Pokemon API...")

    try:
        producer.flush(10)
    except Exception as error:
        logger.error(f"Kafka producer shutdown error: {error}")

    logger.info("Pokemon API shutdown complete")
