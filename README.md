# Pokédex – AI Pokémon Classifier

Full-stack Pokémon identification system with mobile app, ML classifier, and complete Pokédex data.

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)

## 🎯 What It Does

Point your phone camera at any Pokémon → instantly get identification with stats, types, abilities, artwork, and more.

## 🏗️ Architecture

A microservices-based system designed for scalability and maintainability.

- **📱 Mobile App** – React Native (iOS + Android)
- **🌐 Backend API** – FastAPI
- **🧠 ML Classifier** – ViT (Vision Transformer) via Transformers & PyTorch
- **🗄️ Database** – PostgreSQL
- **⚡ Message Broker** – Kafka
- **🔥 Cache** – Redis
- **📊 Monitoring** – Kafka UI

## 📦 Components

| Component       | Technology                 | Port | Status |
|----------------|----------------------------|------|--------|
| Mobile App     | React Native + Expo        | –    | ✅     |
| API Gateway    | FastAPI                    | 8000 | ✅     |
| ML Classifier  | Transformers (ViT)         | –    | ✅     |
| Message Broker | Kafka                      | 29092| ✅     |
| Database       | PostgreSQL                 | 5432 | ✅     |
| Cache          | Redis                      | 6379 | ✅     |
| Monitoring     | Kafka UI                   | 8080 | ✅     |

## 🎮 Features

- 📸 Camera & gallery photo upload  
- 🤖 98% accuracy ML classification  
- 📊 Full Pokémon stats (types, abilities, height, weight)  
- 🎨 Official artwork display  
- ⚡ Real-time processing with Kafka  
- 🔒 50% confidence threshold  
- 🧭 Classic Pokédex-style UI  

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 24+ (for mobile app)
- ngrok (for mobile connectivity)
- Expo Go app on your phone

### 1. Setup Database & Fetch Pokémon Data

```bash
# Start PostgreSQL and fetch Pokemon data (~30-45 min)
docker-compose --profile setup up
```

This will create database tables and fetch 1000+ Pokémon from PokeAPI with sprites and metadata.

### 2. Start Backend Services

```bash
# Start all backend services
docker-compose --profile classifier up

# Services started:
# ✓ PostgreSQL (5432)
# ✓ Zookeeper (2181)
# ✓ Kafka (29092)
# ✓ Redis (6379)
# ✓ FastAPI (8000)
# ✓ ML Classifier
# ✓ Kafka UI (8080)
```

### 3. Expose API with ngrok

```bash
# In a new terminal
npx ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc-123.ngrok-free.app)
```

### 4. Setup & Run Mobile App

```bash
cd pkmn-mobile

# Install dependencies
npm install --legacy-peer-deps

# Update API_URL in App.tsx with your ngrok URL

# Start Expo
npx expo start -c --tunnel

# Scan QR code with Expo Go app on your phone
```

## 📱 Mobile App

The mobile application is built with React Native + Expo.

### Features

- Camera integration
- Real-time image recognition
- Detailed Pokémon info pages

## 🌐 API

Backend built with FastAPI.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | /classify-pokemon/ | Upload image for classification |
| GET    | /result/{request_id} | Retrieve classification result |
| GET    | /pokemon/{id} | Pokémon details |
| GET    | /types | All Pokémon types |
| GET    | /abilities | All Pokémon abilities |
| GET    | /health | Health check |

Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## 🧠 Machine Learning Classifier

Powered by Transformers ViT.

### Model Architecture

- Vision Transformer encoder
- Dense layers for classification
- Softmax output across Pokémon species

Trained on a curated Pokémon dataset.

## 📊 Database

PostgreSQL, with tables for:

- users
- pokemon
- stats
- requests (classification jobs)

Caching via Redis.

## 🔧 Development Tools

- Docker for containerization
- Docker Compose for local orchestration
- ngrok for exposing API to the mobile app
- Kafka for distributing classification tasks

## 🐛 Common Issues

- Mobile won't connect → Update the ngrok URL in `App.tsx`  
- Model slow first time → Downloads ~400 MB model cache  
- Expo errors → Use Node 24+, run `npm install --legacy-peer-deps`  
- Image too large → Auto-compressed to 800×800  

## 📄 License

See LICENSE.

## 🙏 Credits

- **PokeAPI** – Pokémon data and stats  
- **ML Model** – [skshmjn/Pokemon-classifier-gen9-1025](https://huggingface.co/skshmjn/Pokemon-classifier-gen9-1025) (Vision Transformer fine-tuned for Gen 9 Pokémon, Apache-2.0 License)
