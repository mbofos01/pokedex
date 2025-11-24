from kafka import KafkaProducer
from PIL import Image
import json
import io
import sys
import os
import time

def send_pokemon_image(image_path, filename=None):
    """Send a Pokemon image to Kafka topic"""
    
    # Get configuration from environment variables
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
    KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'pokemon-images')
    
    # Connect to Kafka
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    # Load and convert image to hex
    img = Image.open(image_path).convert("RGB")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    hex_string = img_bytes.hex()
    
    # Create message
    message = {
        'request_id': f'test-{int(time.time())}',
        'filename': filename or image_path.split('/')[-1],
        'image_bytes': hex_string
    }
    
    # Send to Kafka
    future = producer.send(KAFKA_INPUT_TOPIC, message)
    result = future.get(timeout=10)
    
    print(f"✓ Message sent successfully!")
    print(f"  Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"  Topic: {result.topic}")
    print(f"  Partition: {result.partition}")
    print(f"  Offset: {result.offset}")
    print(f"  Filename: {message['filename']}")
    
    producer.flush()
    producer.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_test_message.py <image_path> [filename]")
        print("Example: python send_test_message.py pikachu.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else None
    
    send_pokemon_image(image_path, filename)
