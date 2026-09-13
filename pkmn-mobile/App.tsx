import React, { useEffect, useRef, useState } from "react";
import {
  Alert,
  ScrollView,
  View,
} from "react-native";

import * as ImagePicker from "expo-image-picker";
import axios from "axios";
import { StatusBar } from "expo-status-bar";

import { styles } from "./styles";

import { PokedexHeader } from "./components/PokedexHeader";
import { ScreenDisplay } from "./components/ScreenDisplay";
import { ControlButtons } from "./components/ControlButtons";
import { ResultDisplay } from "./components/ResultDisplay";
import { PokemonDetails } from "./components/PokemonDetails";


// ============================================================
// API configuration
// ============================================================

const API_URL =
  "https://gaugeable-arlyne-rewarding.ngrok-free.dev/pkmn-api";


// ============================================================
// Types
// ============================================================

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

  message?: string;
}


interface WebSocketMessage
  extends ClassificationResult {
  type?: string;
}


// ============================================================
// App
// ============================================================

export default function App() {

  // ----------------------------------------------------------
  // State
  // ----------------------------------------------------------

  const [image, setImage] =
    useState<string | null>(null);

  const [loading, setLoading] =
    useState<boolean>(false);

  const [result, setResult] =
    useState<ClassificationResult | null>(null);

  const [showDetails, setShowDetails] =
    useState<boolean>(false);


  // ----------------------------------------------------------
  // Keep WebSocket reference so we can close it when needed.
  // ----------------------------------------------------------

  const socketRef =
    useRef<WebSocket | null>(null);


  // ----------------------------------------------------------
  // Cleanup WebSocket when component unmounts.
  // ----------------------------------------------------------

  useEffect(() => {

    return () => {

      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }

    };

  }, []);


  // ==========================================================
  // Test API connection
  // ==========================================================

  const testConnection = async (): Promise<void> => {

    try {

      console.log(
        "Testing connection to:",
        `${API_URL}/health`
      );

      const response =
        await axios.get(
          `${API_URL}/health`,
          {
            timeout: 5000,

            headers: {
              "ngrok-skip-browser-warning": "true",
            },
          }
        );

      console.log(
        "Health response:",
        response.data
      );

      Alert.alert(
        "Success!",
        `Connected to API\n\n${JSON.stringify(
          response.data,
          null,
          2
        )}`
      );

    } catch (error) {

      console.error(
        "Connection test failed:",
        error
      );

      if (axios.isAxiosError(error)) {

        Alert.alert(
          "Connection Failed",
          [
            `Error: ${error.code}`,
            "",
            `URL: ${API_URL}/health`,
            "",
            "Make sure:",
            "1. Docker is running",
            "2. FastAPI is running",
            "3. ngrok is running",
          ].join("\n")
        );

      } else {

        Alert.alert(
          "Connection Failed",
          "Could not connect to the API."
        );

      }

    }

  };


  // ==========================================================
  // Pick image from gallery
  // ==========================================================

  const pickImage = async (): Promise<void> => {

    try {

      const permission =
        await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (!permission.granted) {

        Alert.alert(
          "Permission Denied",
          "Please allow access to your photo library."
        );

        return;
      }


      const pickerResult =
        await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ["images"],
          allowsEditing: true,
          aspect: [1, 1],
          quality: 0.8,
        });


      if (!pickerResult.canceled) {

        const selectedImage =
          pickerResult.assets[0].uri;

        setImage(selectedImage);
        setResult(null);
        setShowDetails(false);

      }

    } catch (error) {

      console.error(
        "Image picker error:",
        error
      );

      Alert.alert(
        "Error",
        "Could not select image."
      );

    }

  };


  // ==========================================================
  // Take photo
  // ==========================================================

  const takePhoto = async (): Promise<void> => {

    try {

      const permissionResult =
        await ImagePicker.requestCameraPermissionsAsync();


      if (!permissionResult.granted) {

        Alert.alert(
          "Permission Denied",
          "You need to grant camera permissions to take photos."
        );

        return;
      }


      const pickerResult =
        await ImagePicker.launchCameraAsync({
          allowsEditing: true,
          aspect: [1, 1],
          quality: 0.5,
        });


      if (!pickerResult.canceled) {

        const selectedImage =
          pickerResult.assets[0].uri;

        setImage(selectedImage);
        setResult(null);
        setShowDetails(false);

      }

    } catch (error) {

      console.error(
        "Camera error:",
        error
      );

      Alert.alert(
        "Error",
        "Could not take photo."
      );

    }

  };


  // ==========================================================
  // Wait for WebSocket connection
  // ==========================================================

  const connectWebSocket = (
    requestId: string
  ): Promise<WebSocket> => {

    return new Promise(
      (resolve, reject) => {

        const socketUrl =
          `${API_URL.replace(
            "https://",
            "wss://"
          )}/ws/${requestId}`;


        console.log(
          "Connecting WebSocket:",
          socketUrl
        );


        const socket =
          new WebSocket(socketUrl);


        socketRef.current =
          socket;


        let settled = false;


        // ----------------------------------------------------
        // Connection opened
        // ----------------------------------------------------

        socket.onopen = () => {

          console.log(
            "WebSocket connected:",
            requestId
          );

          if (!settled) {

            settled = true;

            resolve(socket);

          }

        };


        // ----------------------------------------------------
        // Connection error
        // ----------------------------------------------------

        socket.onerror = (event) => {

          console.error(
            "WebSocket error:",
            event
          );

          if (!settled) {

            settled = true;

            reject(
              new Error(
                "Could not connect to result stream."
              )
            );

          }

        };


        // ----------------------------------------------------
        // Connection closed before upload/result
        // ----------------------------------------------------

        socket.onclose = (event) => {

          console.log(
            "WebSocket closed:",
            {
              code: event.code,
              reason: event.reason,
            }
          );

          if (!settled) {

            settled = true;

            reject(
              new Error(
                "WebSocket closed before connection was established."
              )
            );

          }

        };

      }
    );

  };


  // ==========================================================
  // Classify Pokemon
  // ==========================================================

  const classifyPokemon = async (): Promise<void> => {

    if (!image) {

      Alert.alert(
        "Error",
        "Please select an image first."
      );

      return;
    }


    setLoading(true);
    setResult(null);
    setShowDetails(false);


    // --------------------------------------------------------
    // Generate request ID.
    //
    // This SAME ID is:
    //
    // React Native
    //     ↓
    // WebSocket URL
    //     ↓
    // HTTP X-Request-ID
    //     ↓
    // Kafka key
    //     ↓
    // Kafka request_id
    //     ↓
    // WebSocket result
    // --------------------------------------------------------

    const requestId =
      `${Date.now()}-${Math.random()
        .toString(36)
        .slice(2)}`;


    let socket: WebSocket | null = null;


    try {

      // ======================================================
      // 1. Connect WebSocket FIRST
      // ======================================================

      socket =
        await connectWebSocket(
          requestId
        );


      // ------------------------------------------------------
      // Listen for result BEFORE uploading.
      // ------------------------------------------------------

      const resultPromise =
        new Promise<WebSocketMessage>(
          (resolve, reject) => {

            if (!socket) {

              reject(
                new Error(
                  "WebSocket is not available."
                )
              );

              return;
            }


            socket.onmessage =
              (event) => {

                try {

                  console.log(
                    "WebSocket message:",
                    event.data
                  );


                  const message =
                    JSON.parse(
                      event.data
                    ) as WebSocketMessage;


                  console.log(
                    "Parsed classification result:",
                    message
                  );


                  if (
                    message.type ===
                    "classification-complete"
                  ) {

                    resolve(message);

                  }

                } catch (error) {

                  console.error(
                    "Failed to parse WebSocket message:",
                    error
                  );

                  reject(
                    new Error(
                      "Invalid result received from server."
                    )
                  );

                }

              };


            socket.onerror =
              (event) => {

                console.error(
                  "WebSocket error while waiting for result:",
                  event
                );

                reject(
                  new Error(
                    "Result stream failed."
                  )
                );

              };


            socket.onclose =
              (event) => {

                console.log(
                  "WebSocket closed while waiting:",
                  event
                );

              };

          }
        );


      // ======================================================
      // 2. Prepare image upload
      // ======================================================

      const formData =
        new FormData();


      formData.append(
        "file",
        {
          uri: image,
          name: "photo.jpg",
          type: "image/jpeg",
        } as any
      );


      console.log(
        "Uploading image:",
        {
          requestId,
          url: `${API_URL}/classify-pokemon/`,
        }
      );


      // ======================================================
      // 3. Upload image to FastAPI
      // ======================================================

      const uploadResponse =
        await axios.post<ClassificationResult>(
          `${API_URL}/classify-pokemon/`,
          formData,
          {
            headers: {
              "Content-Type":
                "multipart/form-data",

              "X-Request-ID":
                requestId,

              "ngrok-skip-browser-warning":
                "true",
            },

            timeout: 30000,
          }
        );


      console.log(
        "Upload response:",
        uploadResponse.data
      );


      // ======================================================
      // 4. Wait for Kafka → WebSocket result
      // ======================================================

      const classification =
        await resultPromise;


      console.log(
        "Classification complete:",
        classification
      );


      // ======================================================
      // 5. Update UI
      // ======================================================

      setResult(
        classification
      );

      setLoading(false);


      if (
        classification.pokemon_details
      ) {

        setShowDetails(true);

      }


      // ======================================================
      // 6. Close WebSocket
      // ======================================================

      socket.close();

      socketRef.current = null;


    } catch (error) {

      console.error(
        "Classification error:",
        error
      );


      // ------------------------------------------------------
      // Close WebSocket
      // ------------------------------------------------------

      if (socket) {

        socket.close();

      }

      socketRef.current = null;


      // ------------------------------------------------------
      // Error message
      // ------------------------------------------------------

      let errorMessage =
        "Failed to classify image.";


      if (
        axios.isAxiosError(error)
      ) {

        if (
          error.code ===
          "ECONNABORTED"
        ) {

          errorMessage =
            "Request timed out. The image may be too large or the server may be unavailable.";

        } else if (
          error.code ===
          "ERR_NETWORK"
        ) {

          errorMessage =
            `Cannot reach API at ${API_URL}`;

        } else if (
          error.response
        ) {

          const serverError =
            error.response.data?.detail ||
            error.response.data?.message ||
            JSON.stringify(
              error.response.data
            );


          errorMessage =
            `Server error ${error.response.status}:\n${serverError}`;


          console.error(
            "Server response:",
            error.response.data
          );

        }

      } else if (
        error instanceof Error
      ) {

        errorMessage =
          error.message;

      }


      setResult({
        status: "error",
        request_id: requestId,
        error: errorMessage,
      });


      Alert.alert(
        "Classification Error",
        errorMessage
      );


      setLoading(false);

    }

  };


  // ==========================================================
  // Return to home
  // ==========================================================

  const resetToHome = (): void => {

    if (socketRef.current) {

      socketRef.current.close();

      socketRef.current = null;

    }


    setShowDetails(false);
    setImage(null);
    setResult(null);
    setLoading(false);

  };


  // ==========================================================
  // Pokemon details screen
  // ==========================================================

  if (
    showDetails &&
    result?.pokemon_details
  ) {

    return (

      <View style={styles.pokedex}>

        <StatusBar style="light" />

        <PokedexHeader />

        <PokemonDetails
          pokemon={
            result.pokemon_details
          }
          confidence={
            result.confidence
          }
          onBack={
            resetToHome
          }
        />

      </View>

    );

  }


  // ==========================================================
  // Main screen
  // ==========================================================

  return (

    <View style={styles.pokedex}>

      <StatusBar style="light" />


      <PokedexHeader />


      <ScrollView
        style={styles.mainBody}
        contentContainerStyle={
          styles.scrollContent
        }
      >

        <ScreenDisplay
          image={image}
        />


        <ControlButtons
          onCamera={
            takePhoto
          }

          onGallery={
            pickImage
          }

          onAnalyze={
            classifyPokemon
          }

          showAnalyze={
            image !== null &&
            !loading
          }
        />


        <ResultDisplay
          loading={loading}
          result={result}
        />

      </ScrollView>

    </View>

  );

}