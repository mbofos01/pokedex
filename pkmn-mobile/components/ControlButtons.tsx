import React from 'react';
import { View, TouchableOpacity, Text } from 'react-native';
import { styles } from '../styles';

interface ControlButtonsProps {
  onCamera: () => void;
  onGallery: () => void;
  onAnalyze: () => void;
  showAnalyze: boolean;
}

export const ControlButtons: React.FC<ControlButtonsProps> = ({
  onCamera,
  onGallery,
  onAnalyze,
  showAnalyze,
}) => {
  return (
    <View style={styles.controls}>
      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.pokeButton} onPress={onCamera}>
          <Text style={styles.pokeButtonText}>CAMERA</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.pokeButton} onPress={onGallery}>
          <Text style={styles.pokeButtonText}>GALLERY</Text>
        </TouchableOpacity>
      </View>

      {showAnalyze && (
        <TouchableOpacity style={styles.analyzeButton} onPress={onAnalyze}>
          <Text style={styles.analyzeButtonText}>⚡ ANALYZE</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};
