from kafka import KafkaConsumer, KafkaProducer
from transformers import ViTForImageClassification, ViTImageProcessor
from PIL import Image
import torch
import io
import json
import time
import os

# Kafka connection with retry
bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'pokemon-images')
output_topic = os.getenv('KAFKA_OUTPUT_TOPIC', 'pokemon-results')
consumer_group = os.getenv('KAFKA_CONSUMER_GROUP', 'pokemon-classifier-group')
max_retries = 10

print(f"Connecting to Kafka at {bootstrap_servers}...")
print(f"Input topic: {input_topic}")
print(f"Output topic: {output_topic}")

for attempt in range(max_retries):
    try:
        consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id=consumer_group
        )
        
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("✓ Connected to Kafka successfully!")
        break
    except Exception as e:
        print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(5)
        else:
            raise

print("Loading model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = "skshmjn/Pokemon-classifier-gen9-1025"
model = ViTForImageClassification.from_pretrained(model_id).to(device)
processor = ViTImageProcessor.from_pretrained(model_id)
model.eval()
print(f"✓ Model loaded on {device}")

# Confidence threshold
CONFIDENCE_THRESHOLD = 0.5  # Adjust this value (0.0 to 1.0)

print("Waiting for messages...")
for message in consumer:
    try:
        data = message.value
        request_id = data.get('request_id')
        img_bytes = bytes.fromhex(data['image_bytes'])
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Prediction
        inputs = processor(images=img, return_tensors="pt").to(device)
        outputs = model(**inputs)
        
        # Get probabilities
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        confidence, pred_id = torch.max(probabilities, dim=-1)
        confidence = confidence.item()
        pred_id = pred_id.item()
        
        # Check confidence threshold
        if confidence < CONFIDENCE_THRESHOLD:
            pred_label = "Unknown"
            print(f"Low confidence ({confidence:.2%}): {data['filename']} -> Unknown")
        else:
            pred_label = model.config.id2label[pred_id]
            print(f"Classified ({confidence:.2%}): {data['filename']} -> {pred_label}")

        # Send result back with request_id and confidence
        result = {
            'request_id': request_id,
            'filename': data['filename'],
            'prediction': pred_label,
            'confidence': round(confidence, 4)
        }
        producer.send(output_topic, result)
        producer.flush()
    except Exception as e:
        print(f"Error processing message: {e}")
