# Pokemon Classifier Mobile App

React Native Expo app for Pokemon classification with a classic Pokédex design.

## Prerequisites

- **Node.js 24+** required
- Expo Go app installed on your phone ([iOS](https://apps.apple.com/app/expo-go/id982107779) | [Android](https://play.google.com/store/apps/details?id=host.exp.exponent))
- Docker running backend services

## Setup

1. **Install dependencies:**
   ```bash
   npm install --legacy-peer-deps
   ```

2. **Start Expo dev server:**
   ```bash
   npx expo start -c --tunnel
   ```

3. **Scan QR code:**
   - Open Expo Go on your phone
   - Scan the QR code displayed in terminal
   - Make sure your backend is running

## Backend Setup

Make sure the backend services are running:

```bash
# From project root
docker-compose --profile classifier up
```

And ngrok is exposing the API:

```bash
npx ngrok http 8000
```

Update the API URL in `App.tsx` with your ngrok URL.
