import React, { useState } from "react";
import { View, Alert, ScrollView } from "react-native";
import * as ImagePicker from "expo-image-picker";
import axios from "axios";
import { StatusBar } from "expo-status-bar";
import { styles } from "./styles";
import { PokedexHeader } from "./components/PokedexHeader";
import { ScreenDisplay } from "./components/ScreenDisplay";
import { ControlButtons } from "./components/ControlButtons";
import { ResultDisplay } from "./components/ResultDisplay";
import { PokemonDetails } from "./components/PokemonDetails";

// Replace with YOUR ngrok URL from the terminal output
const API_URL = "https://gaugeable-arlyne-rewarding.ngrok-free.dev/pkmn-api/";

interface PokemonDetails {
  id: number;
  name: string;
  height: number;
  weight: number;
  types: string[];
  abilities: string[];
  base_experience: number;
  stats: {
    hp: number;
    attack: number;
    defense: number;
    "special-attack": number;
    "special-defense": number;
    speed: number;
  };
  official_artwork: string;
}

interface ClassificationResult {
  status: string;
  request_id: string;
  prediction?: string;
  filename?: string;
  confidence?: number;
  pokemon_details?: PokemonDetails;
  error?: string;
}

export default function App() {
  const [image, setImage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [showDetails, setShowDetails] = useState<boolean>(false);

  const testConnection = async (): Promise<void> => {
    try {
      console.log("Testing connection to:", `${API_URL}/health`);
      const response = await axios.get(`${API_URL}/health`, {
        timeout: 5000,
        headers: {
          "ngrok-skip-browser-warning": "true",
        },
      });
      console.log("Response:", response.data);
      Alert.alert(
        "Success!",
        `Connected to API\n\nResponse: ${JSON.stringify(response.data)}`
      );
    } catch (error) {
      console.error("Connection test failed:", error);
      if (axios.isAxiosError(error)) {
        Alert.alert(
          "Connection Failed",
          `Error: ${error.code}\n\nURL: ${API_URL}/health\n\nMake sure:\n1. Docker is running\n2. ngrok is running\n3. Visit ${API_URL}/docs in browser first`
        );
      }
    }
  };

  const pickImage = async (): Promise<void> => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"], // Changed from ImagePicker.MediaTypeOptions.Images
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setResult(null);
    }
  };

  const takePhoto = async (): Promise<void> => {
    // Request camera permissions
    const permissionResult = await ImagePicker.requestCameraPermissionsAsync();

    if (!permissionResult.granted) {
      Alert.alert(
        "Permission Denied",
        "You need to grant camera permissions to take photos"
      );
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5, // Lower quality for camera
    });

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setResult(null);
    }
  };

  const classifyPokemon = async (): Promise<void> => {
    if (!image) {
      Alert.alert("Error", "Please select an image first");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Test API connection first
      console.log("Testing connection to:", API_URL);
      const healthCheck = await axios.get(`${API_URL}/health`, {
        timeout: 5000,
        headers: {
          "ngrok-skip-browser-warning": "true",
        },
      });
      console.log("Health check:", healthCheck.data);

      // Upload image
      const formData = new FormData();
      const filename = image.split("/").pop() || "camera-photo.jpg";
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : "image/jpeg";

      console.log("Image info:", { filename, type, uri: image });

      formData.append("file", {
        uri: image,
        name: "photo.jpg", // Force consistent naming
        type: "image/jpeg", // Force JPEG
      } as any);

      console.log("Uploading image to:", `${API_URL}/classify-pokemon/`);
      const uploadResponse = await axios.post<ClassificationResult>(
        `${API_URL}/classify-pokemon/`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
            "ngrok-skip-browser-warning": "true",
          },
          timeout: 30000, // Longer timeout
        }
      );

      console.log("Upload response:", uploadResponse.data);
      const reqId = uploadResponse.data.request_id;

      // Poll for result
      let attempts = 0;
      const maxAttempts = 30;

      const pollInterval = setInterval(async () => {
        attempts++;

        try {
          const resultResponse = await axios.get<ClassificationResult>(
            `${API_URL}/result/${reqId}`,
            {
              timeout: 5000,
              headers: {
                "ngrok-skip-browser-warning": "true",
              },
            }
          );

          if (resultResponse.data.status === "completed") {
            setResult(resultResponse.data);
            setLoading(false);
            clearInterval(pollInterval);
            // Show details page if we have Pokemon details
            if (resultResponse.data.pokemon_details) {
              setShowDetails(true);
            }
          } else if (attempts >= maxAttempts) {
            setResult({
              status: "error",
              request_id: reqId,
              error: "Timeout waiting for classification",
            });
            setLoading(false);
            clearInterval(pollInterval);
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, 2000);
    } catch (error) {
      console.error("Full error:", error);
      let errorMessage = "Failed to classify image";

      if (axios.isAxiosError(error)) {
        if (error.code === "ECONNABORTED") {
          errorMessage = "Request timeout - image too large or slow connection";
        } else if (error.code === "ERR_NETWORK") {
          errorMessage = `Cannot reach API at ${API_URL}`;
        } else if (error.response) {
          // Show detailed server error
          const serverError =
            error.response.data?.detail || JSON.stringify(error.response.data);
          errorMessage = `Server error ${error.response.status}:\n${serverError}`;
          console.error("Server response:", error.response.data);
        }
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      Alert.alert("Network Error", errorMessage);
      setLoading(false);
    }
  };

  const resetToHome = () => {
    setShowDetails(false);
    setImage(null);
    setResult(null);
  };

  // Details Page
  if (showDetails && result?.pokemon_details) {
    return (
      <View style={styles.pokedex}>
        <StatusBar style="light" />
        <PokedexHeader />
        <PokemonDetails
          pokemon={result.pokemon_details}
          confidence={result.confidence}
          onBack={resetToHome}
        />
      </View>
    );
  }

  // Home Page
  return (
    <View style={styles.pokedex}>
      <StatusBar style="light" />
      <PokedexHeader />

      <ScrollView
        style={styles.mainBody}
        contentContainerStyle={styles.scrollContent}
      >
        <ScreenDisplay image={image} />

        <ControlButtons
          onCamera={takePhoto}
          onGallery={pickImage}
          onAnalyze={classifyPokemon}
          showAnalyze={image !== null && !loading}
        />

        <ResultDisplay loading={loading} result={result} />
      </ScrollView>
    </View>
  );
}
