from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from kafka import KafkaProducer, KafkaConsumer
import json
import uuid
import os
from typing import Dict
from threading import Thread
import redis
from PIL import Image
import io
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv

app = FastAPI(
    title="Pokemon Classifier API",
    docs_url="/swagger",
    redoc_url="/docs"
)

# Load .env file from same directory
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'pokemon-images')
KAFKA_OUTPUT_TOPIC = os.getenv('KAFKA_OUTPUT_TOPIC', 'pokemon-results')

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_NAME = os.getenv('DB_NAME', 'pokedex')
DB_USER = os.getenv('DB_USER', 'pkmn')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'pkmn')
DB_PORT = os.getenv('DB_PORT', '5432')

# Encryption configuration
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    print("\n" + "="*60)
    print("❌ ERROR: ENCRYPTION_KEY not found!")
    print("="*60)
    print("\nPlease generate an encryption key by running:")
    print("\n  python src/generate_key.py")
    print("\nOr set ENCRYPTION_KEY in your .env file")
    print("="*60 + "\n")
    import sys
    sys.exit(1)  # Graceful exit instead of exception

fernet = Fernet(ENCRYPTION_KEY.encode())

# Initialize Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# Initialize Kafka producer with larger message size
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    max_request_size=10485760  # 10MB max message size
)

def get_pokemon_details(pokemon_name: str):
    """Fetch Pokemon details from database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get basic info
        cur.execute("""
            SELECT id, name, height, weight, base_experience
            FROM pokemon
            WHERE LOWER(
                    REGEXP_REPLACE(
                        REPLACE(REPLACE(REPLACE(name, '♂', 'm'), '♀', 'f'), '''', ''),
                        E'[^a-z0-9]', '', 'g'
                    )
                ) = LOWER(
                    REGEXP_REPLACE(
                        REPLACE(REPLACE(REPLACE(LOWER(%s), '♂', 'm'), '♀', 'f'), '''', ''),
                        E'[^a-z0-9]', '', 'g'
                    )
                )
        """, (pokemon_name,))
        pokemon = cur.fetchone()
        
        if not pokemon:
            return None
        
        pokemon_id = pokemon['id']
        
        # Get types
        cur.execute("""
            SELECT type_name FROM types WHERE pokemon_id = %s
        """, (pokemon_id,))
        types = [row['type_name'] for row in cur.fetchall()]
        
        # Get stats
        cur.execute("""
            SELECT stat_name, base_stat FROM stats WHERE pokemon_id = %s
        """, (pokemon_id,))
        stats = {row['stat_name']: row['base_stat'] for row in cur.fetchall()}
        
        # Get abilities
        cur.execute("""
            SELECT ability_name, is_hidden FROM abilities WHERE pokemon_id = %s
        """, (pokemon_id,))
        abilities = [row['ability_name'] for row in cur.fetchall() if not row['is_hidden']]
        
        # Get official artwork image
        cur.execute("""
            SELECT url FROM images 
            WHERE pokemon_id = %s 
            AND image_type = 'other_official-artwork'
            LIMIT 1
        """, (pokemon_id,))
        image_row = cur.fetchone()
        official_artwork = image_row['url'] if image_row else None
        
        cur.close()
        conn.close()
        
        return {
            'id': pokemon['id'],
            'name': pokemon['name'],
            'height': pokemon['height'],
            'weight': pokemon['weight'],
            'types': types,
            'stats': stats,
            'abilities': abilities,
            'base_experience': pokemon['base_experience'],
            'official_artwork': official_artwork
        }
        
    except Exception as e:
        print(f"Database error: {e}")
        return None

def encrypt_data(data: str) -> str:
    """Encrypt data before storing in Redis"""
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt data from Redis"""
    return fernet.decrypt(encrypted_data.encode()).decode()

# Background consumer for results
def consume_results():
    """Background thread to consume classification results from Kafka"""
    consumer = KafkaConsumer(
        KAFKA_OUTPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest',
        group_id='api-result-consumer'
    )
    
    print(f"✓ Started consuming from {KAFKA_OUTPUT_TOPIC}")
    
    for message in consumer:
        data = message.value
        request_id = data.get('request_id')
        if request_id:
            # Fetch Pokemon details from database
            pokemon_name = data.get('prediction')
            pokemon_details = None
            
            if pokemon_name and pokemon_name != 'Unknown':
                pokemon_details = get_pokemon_details(pokemon_name)
            
            # Store result with Pokemon details in Redis (encrypted)
            result_data = {
                **data,
                'pokemon_details': pokemon_details
            }
            
            encrypted_result = encrypt_data(json.dumps(result_data))
            redis_client.setex(
                f"result:{request_id}",
                3600,
                encrypted_result
            )
            print(f"✓ Received result for request_id: {request_id}")

# Start consumer thread on startup
@app.on_event("startup")
async def startup_event():
    """Start background consumer thread"""
    consumer_thread = Thread(target=consume_results, daemon=True)
    consumer_thread.start()
    print("✓ API started, consumer thread running")

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to ReDoc documentation"""
    return RedirectResponse(url="/swagger")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except:
        return {"status": "degraded", "redis": "disconnected"}

@app.post("/classify-pokemon/")
async def classify_pokemon(file: UploadFile = File(...)):
    """
    Upload a Pokemon image for classification
    
    Returns request_id to track the classification result
    """
    try:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Read image bytes
        contents = await file.read()
        
        # Log file details
        print(f"Received file: {file.filename}, size: {len(contents)} bytes, type: {file.content_type}")
        
        # Validate it's an image
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Empty file received")
        
        # Resize/compress image if too large
        img = Image.open(io.BytesIO(contents))
        
        # Resize if larger than 800x800
        max_size = 800
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            print(f"Resized image to: {img.size}")
        
        # Convert to JPEG with quality 85
        img_byte_arr = io.BytesIO()
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(img_byte_arr, format='JPEG', quality=85)
        compressed_bytes = img_byte_arr.getvalue()
        
        print(f"Compressed size: {len(compressed_bytes)} bytes (from {len(contents)})")
        
        # Convert to hex string
        hex_string = compressed_bytes.hex()
        
        # Create Kafka message
        message = {
            'request_id': request_id,
            'filename': file.filename,
            'image_bytes': hex_string
        }
        
        # Send to Kafka
        print(f"Sending to Kafka: request_id={request_id}, hex_size={len(hex_string)}")
        future = producer.send(KAFKA_INPUT_TOPIC, message)
        future.get(timeout=10)  # Wait for confirmation
        
        return {
            "status": "processing",
            "request_id": request_id,
            "filename": file.filename,
            "message": "Image sent for classification. Use /result/{request_id} to get the prediction."
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error processing image: {e}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

@app.get("/result/{request_id}")
async def get_result(request_id: str):
    """
    Get classification result by request_id
    
    Poll this endpoint to check if classification is complete
    """
    result_key = f"result:{request_id}"
    encrypted_result = redis_client.get(result_key)
    
    if encrypted_result:
        # Decrypt and parse result
        result_json = decrypt_data(encrypted_result)
        result = json.loads(result_json)
        redis_client.delete(result_key)  # Remove after retrieval
        
        response = {
            "status": "completed",
            "request_id": request_id,
            "prediction": result.get('prediction'),
            "confidence": result.get('confidence')
            # "filename": result.get('filename')
        }
        
        # Add Pokemon details if available
        if result.get('pokemon_details'):
            details = result['pokemon_details']
            response['pokemon_details'] = {
                'id': details['id'],
                'name': details['name'],
                'height': details['height'],
                'weight': details['weight'],
                'types': details['types'],
                'abilities': details['abilities'],
                'base_experience': details['base_experience'],
                'stats': details['stats'],
                'official_artwork': details.get('official_artwork')
            }
        
        return response
    
    return {
        "status": "processing",
        "request_id": request_id,
        "message": "Classification in progress or request_id not found"
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Close Kafka producer on shutdown"""
    producer.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
