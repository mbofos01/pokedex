import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Image, ActivityIndicator, Alert, ScrollView } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { StatusBar } from 'expo-status-bar';

// Replace with YOUR ngrok URL from the terminal output
const API_URL = 'https://gaugeable-arlyne-rewarding.ngrok-free.dev';

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
    'special-attack': number;
    'special-defense': number;
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
      console.log('Testing connection to:', `${API_URL}/health`);
      const response = await axios.get(`${API_URL}/health`, { 
        timeout: 5000,
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      });
      console.log('Response:', response.data);
      Alert.alert('Success!', `Connected to API\n\nResponse: ${JSON.stringify(response.data)}`);
    } catch (error) {
      console.error('Connection test failed:', error);
      if (axios.isAxiosError(error)) {
        Alert.alert('Connection Failed', `Error: ${error.code}\n\nURL: ${API_URL}/health\n\nMake sure:\n1. Docker is running\n2. ngrok is running\n3. Visit ${API_URL}/docs in browser first`);
      }
    }
  };

  const pickImage = async (): Promise<void> => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'], // Changed from ImagePicker.MediaTypeOptions.Images
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
      Alert.alert('Permission Denied', 'You need to grant camera permissions to take photos');
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
      Alert.alert('Error', 'Please select an image first');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Test API connection first
      console.log('Testing connection to:', API_URL);
      const healthCheck = await axios.get(`${API_URL}/health`, { 
        timeout: 5000,
        headers: {
          'ngrok-skip-browser-warning': 'true'
        }
      });
      console.log('Health check:', healthCheck.data);

      // Upload image
      const formData = new FormData();
      const filename = image.split('/').pop() || 'camera-photo.jpg';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : 'image/jpeg';

      console.log('Image info:', { filename, type, uri: image });

      formData.append('file', {
        uri: image,
        name: 'photo.jpg', // Force consistent naming
        type: 'image/jpeg', // Force JPEG
      } as any);

      console.log('Uploading image to:', `${API_URL}/classify-pokemon/`);
      const uploadResponse = await axios.post<ClassificationResult>(
        `${API_URL}/classify-pokemon/`, 
        formData, 
        {
          headers: { 
            'Content-Type': 'multipart/form-data',
            'ngrok-skip-browser-warning': 'true'
          },
          timeout: 30000, // Longer timeout
        }
      );

      console.log('Upload response:', uploadResponse.data);
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
                'ngrok-skip-browser-warning': 'true'
              }
            }
          );
          
          if (resultResponse.data.status === 'completed') {
            setResult(resultResponse.data);
            setLoading(false);
            clearInterval(pollInterval);
            // Show details page if we have Pokemon details
            if (resultResponse.data.pokemon_details) {
              setShowDetails(true);
            }
          } else if (attempts >= maxAttempts) {
            setResult({ 
              status: 'error', 
              request_id: reqId, 
              error: 'Timeout waiting for classification' 
            });
            setLoading(false);
            clearInterval(pollInterval);
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);

    } catch (error) {
      console.error('Full error:', error);
      let errorMessage = 'Failed to classify image';
      
      if (axios.isAxiosError(error)) {
        if (error.code === 'ECONNABORTED') {
          errorMessage = 'Request timeout - image too large or slow connection';
        } else if (error.code === 'ERR_NETWORK') {
          errorMessage = `Cannot reach API at ${API_URL}`;
        } else if (error.response) {
          // Show detailed server error
          const serverError = error.response.data?.detail || JSON.stringify(error.response.data);
          errorMessage = `Server error ${error.response.status}:\n${serverError}`;
          console.error('Server response:', error.response.data);
        }
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      Alert.alert('Network Error', errorMessage);
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
    const pokemon = result.pokemon_details;
    
    return (
      <View style={styles.pokedex}>
        <StatusBar style="light" />
        
        {/* Top Red Section */}
        <View style={styles.topSection}>
          <View style={styles.topBar}>
            <View style={styles.blueLightOuter}>
              <View style={styles.blueLightInner} />
            </View>
            <View style={styles.smallLights}>
              <View style={[styles.smallLight, { backgroundColor: '#EF5350' }]} />
              <View style={[styles.smallLight, { backgroundColor: '#FDD835' }]} />
              <View style={[styles.smallLight, { backgroundColor: '#66BB6A' }]} />
            </View>
          </View>
        </View>

        <ScrollView style={styles.mainBody} contentContainerStyle={styles.scrollContent}>
          {/* Pokemon Image */}
          <View style={styles.detailsImageContainer}>
            <Image 
              source={{ uri: pokemon.official_artwork }} 
              style={styles.detailsImage}
            />
          </View>

          {/* Pokemon Name & Number */}
          <View style={styles.detailsHeader}>
            <Text style={styles.pokemonNumber}>#{pokemon.id.toString().padStart(3, '0')}</Text>
            <Text style={styles.detailsPokemonName}>{pokemon.name.toUpperCase()}</Text>
            {result.confidence && (
              <Text style={styles.confidenceBadge}>
                {(result.confidence * 100).toFixed(1)}% MATCH
              </Text>
            )}
          </View>

          {/* Types */}
          <View style={styles.typesContainer}>
            {pokemon.types.map((type, index) => (
              <View key={index} style={styles.typeBadge}>
                <Text style={styles.typeText}>{type.toUpperCase()}</Text>
              </View>
            ))}
          </View>

          {/* Physical Info */}
          <View style={styles.infoGrid}>
            <View style={styles.infoCard}>
              <Text style={styles.infoLabel}>HEIGHT</Text>
              <Text style={styles.infoValue}>{(pokemon.height / 10).toFixed(1)}m</Text>
            </View>
            <View style={styles.infoCard}>
              <Text style={styles.infoLabel}>WEIGHT</Text>
              <Text style={styles.infoValue}>{(pokemon.weight / 10).toFixed(1)}kg</Text>
            </View>
            <View style={styles.infoCard}>
              <Text style={styles.infoLabel}>BASE EXP</Text>
              <Text style={styles.infoValue}>{pokemon.base_experience}</Text>
            </View>
          </View>

          {/* Stats */}
          <View style={styles.statsSection}>
            <Text style={styles.sectionTitle}>BASE STATS</Text>
            {Object.entries(pokemon.stats).map(([statName, value]) => (
              <View key={statName} style={styles.statRow}>
                <Text style={styles.statName}>{statName.toUpperCase().replace('-', ' ')}</Text>
                <View style={styles.statBarContainer}>
                  <View style={[styles.statBarFill, { width: `${(value / 255) * 100}%` }]} />
                </View>
                <Text style={styles.statValueText}>{value}</Text>
              </View>
            ))}
          </View>

          {/* Abilities */}
          <View style={styles.abilitiesSection}>
            <Text style={styles.sectionTitle}>ABILITIES</Text>
            <View style={styles.abilitiesList}>
              {pokemon.abilities.map((ability, index) => (
                <View key={index} style={styles.abilityBadge}>
                  <Text style={styles.abilityText}>{ability.toUpperCase()}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Back Button */}
          <TouchableOpacity style={styles.backButton} onPress={resetToHome}>
            <Text style={styles.backButtonText}>← SCAN NEW POKÉMON</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  }

  // Home Page
  return (
    <View style={styles.pokedex}>
      <StatusBar style="light" />
      
      {/* Top Red Section */}
      <View style={styles.topSection}>
        <View style={styles.topBar}>
          <View style={styles.blueLightOuter}>
            <View style={styles.blueLightInner} />
          </View>
          <View style={styles.smallLights}>
            <View style={[styles.smallLight, { backgroundColor: '#EF5350' }]} />
            <View style={[styles.smallLight, { backgroundColor: '#FDD835' }]} />
            <View style={[styles.smallLight, { backgroundColor: '#66BB6A' }]} />
          </View>
        </View>
      </View>

      {/* Main Screen */}
      <ScrollView style={styles.mainBody} contentContainerStyle={styles.scrollContent}>
        <View style={styles.screenContainer}>
          <View style={styles.screenBezel}>
            <View style={styles.screen}>
              {!image ? (
                <View style={styles.emptyScreen}>
                  <Text style={styles.screenText}>SELECT A POKÉMON</Text>
                  <Text style={styles.screenSubtext}>TO IDENTIFY</Text>
                </View>
              ) : (
                <Image source={{ uri: image }} style={styles.screenImage} />
              )}
            </View>
          </View>
          
          {/* Small indicators */}
          <View style={styles.indicators}>
            <View style={styles.redIndicator} />
            <View style={styles.redIndicator} />
          </View>
        </View>

        {/* Control Buttons */}
        <View style={styles.controls}>
          <View style={styles.buttonRow}>
            <TouchableOpacity style={styles.pokeButton} onPress={takePhoto}>
              <Text style={styles.pokeButtonText}>CAMERA</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.pokeButton} onPress={pickImage}>
              <Text style={styles.pokeButtonText}>GALLERY</Text>
            </TouchableOpacity>
          </View>

          {image && !loading && (
            <TouchableOpacity style={styles.analyzeButton} onPress={classifyPokemon}>
              <Text style={styles.analyzeButtonText}>⚡ ANALYZE</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Results Display */}
        {loading && (
          <View style={styles.resultBox}>
            <ActivityIndicator size="large" color="#C62828" />
            <Text style={styles.resultText}>ANALYZING...</Text>
          </View>
        )}

        {result && !loading && (
          <View style={styles.resultBox}>
            {result.prediction && result.prediction !== 'Unknown' ? (
              <>
                <Text style={styles.resultLabel}>IDENTIFIED:</Text>
                <Text style={styles.pokemonName}>{result.prediction.toUpperCase()}</Text>
                {result.confidence && (
                  <View style={styles.statsContainer}>
                    <Text style={styles.statLabel}>CONFIDENCE</Text>
                    <View style={styles.statBar}>
                      <View 
                        style={[styles.statFill, { width: `${result.confidence * 100}%` }]} 
                      />
                    </View>
                    <Text style={styles.statValue}>{(result.confidence * 100).toFixed(0)}%</Text>
                  </View>
                )}
              </>
            ) : (
              <>
                <Text style={styles.errorLabel}>UNKNOWN</Text>
                <Text style={styles.resultText}>NOT IN DATABASE</Text>
              </>
            )}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  pokedex: {
    flex: 1,
    backgroundColor: '#C62828',
  },
  topSection: {
    backgroundColor: '#C62828',
    paddingTop: 50,
    paddingBottom: 20,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    gap: 15,
  },
  blueLightOuter: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#1976D2',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#0D47A1',
  },
  blueLightInner: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#42A5F5',
    shadowColor: '#2196F3',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 10,
    elevation: 5,
  },
  smallLights: {
    flexDirection: 'row',
    gap: 10,
  },
  smallLight: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#000',
  },
  mainBody: {
    flex: 1,
    backgroundColor: '#F5F5F5',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  scrollContent: {
    padding: 20,
  },
  screenContainer: {
    backgroundColor: '#2C2C2C',
    borderRadius: 15,
    padding: 15,
    marginBottom: 20,
  },
  screenBezel: {
    backgroundColor: '#1A1A1A',
    borderRadius: 10,
    padding: 10,
  },
  screen: {
    backgroundColor: '#9CCC65',
    borderRadius: 8,
    height: 300,
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  emptyScreen: {
    alignItems: 'center',
  },
  screenText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1B5E20',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  screenSubtext: {
    fontSize: 16,
    color: '#33691E',
    fontFamily: 'monospace',
    marginTop: 10,
  },
  screenImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'contain',
  },
  indicators: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
  redIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#EF5350',
  },
  controls: {
    marginBottom: 20,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 15,
    marginBottom: 15,
  },
  pokeButton: {
    flex: 1,
    backgroundColor: '#424242',
    paddingVertical: 15,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 2,
    borderBottomWidth: 4,
    borderColor: '#212121',
  },
  pokeButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  analyzeButton: {
    backgroundColor: '#FDD835',
    paddingVertical: 18,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 2,
    borderBottomWidth: 4,
    borderColor: '#F57F17',
  },
  analyzeButtonText: {
    color: '#000',
    fontSize: 18,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  resultBox: {
    backgroundColor: '#2C2C2C',
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
  },
  resultLabel: {
    color: '#FDD835',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  pokemonName: {
    color: '#FFF',
    fontSize: 28,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 15,
  },
  resultText: {
    color: '#FFF',
    fontSize: 16,
    fontFamily: 'monospace',
    marginTop: 10,
  },
  errorLabel: {
    color: '#EF5350',
    fontSize: 24,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 10,
  },
  statsContainer: {
    width: '100%',
    marginTop: 10,
  },
  statLabel: {
    color: '#FDD835',
    fontSize: 10,
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  statBar: {
    height: 8,
    backgroundColor: '#1A1A1A',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 5,
  },
  statFill: {
    height: '100%',
    backgroundColor: '#66BB6A',
  },
  statValue: {
    color: '#FFF',
    fontSize: 14,
    fontFamily: 'monospace',
    textAlign: 'right',
  },

  // Details Page Styles
  detailsImageContainer: {
    backgroundColor: '#FFF',
    borderRadius: 15,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
  },
  detailsImage: {
    width: 200,
    height: 200,
    resizeMode: 'contain',
  },
  detailsHeader: {
    alignItems: 'center',
    marginBottom: 20,
  },
  pokemonNumber: {
    color: '#666',
    fontSize: 16,
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  detailsPokemonName: {
    color: '#2C2C2C',
    fontSize: 32,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 10,
  },
  confidenceBadge: {
    backgroundColor: '#66BB6A',
    paddingHorizontal: 15,
    paddingVertical: 5,
    borderRadius: 15,
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  typesContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 20,
  },
  typeBadge: {
    backgroundColor: '#424242',
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 20,
  },
  typeText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  infoGrid: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 20,
  },
  infoCard: {
    flex: 1,
    backgroundColor: '#2C2C2C',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
  },
  infoLabel: {
    color: '#FDD835',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  infoValue: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  statsSection: {
    backgroundColor: '#2C2C2C',
    padding: 15,
    borderRadius: 10,
    marginBottom: 20,
  },
  sectionTitle: {
    color: '#FDD835',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 15,
  },
  statRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  statName: {
    color: '#FFF',
    fontSize: 10,
    fontFamily: 'monospace',
    width: 100,
  },
  statBarContainer: {
    flex: 1,
    height: 6,
    backgroundColor: '#1A1A1A',
    borderRadius: 3,
    marginHorizontal: 10,
    overflow: 'hidden',
  },
  statBarFill: {
    height: '100%',
    backgroundColor: '#66BB6A',
  },
  statValueText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    width: 30,
    textAlign: 'right',
  },
  abilitiesSection: {
    backgroundColor: '#2C2C2C',
    padding: 15,
    borderRadius: 10,
    marginBottom: 20,
  },
  abilitiesList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  abilityBadge: {
    backgroundColor: '#424242',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 15,
  },
  abilityText: {
    color: '#FFF',
    fontSize: 12,
    fontFamily: 'monospace',
  },
  backButton: {
    backgroundColor: '#C62828',
    paddingVertical: 18,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 2,
    borderBottomWidth: 4,
    borderColor: '#B71C1C',
    marginBottom: 20,
  },
  backButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
});
