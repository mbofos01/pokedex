import React from 'react';
import { View } from 'react-native';
import { styles } from '../styles';

export const PokedexHeader: React.FC = () => {
  return (
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
  );
};
