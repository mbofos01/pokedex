import React from 'react';
import { View, Text, Image } from 'react-native';
import { styles } from '../styles';

interface ScreenDisplayProps {
  image: string | null;
}

export const ScreenDisplay: React.FC<ScreenDisplayProps> = ({ image }) => {
  return (
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
      
      <View style={styles.indicators}>
        <View style={styles.redIndicator} />
        <View style={styles.redIndicator} />
      </View>
    </View>
  );
};
