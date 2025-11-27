import React from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import { styles } from '../styles';

interface ClassificationResult {
  status: string;
  prediction?: string;
  confidence?: number;
}

interface ResultDisplayProps {
  loading: boolean;
  result: ClassificationResult | null;
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ loading, result }) => {
  if (loading) {
    return (
      <View style={styles.resultBox}>
        <ActivityIndicator size="large" color="#C62828" />
        <Text style={styles.resultText}>ANALYZING...</Text>
      </View>
    );
  }

  if (result) {
    return (
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
    );
  }

  return null;
};
