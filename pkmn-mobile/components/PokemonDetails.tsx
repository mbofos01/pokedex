import React from "react";
import { View, Text, Image, TouchableOpacity, ScrollView } from "react-native";
import { styles } from "../styles";

interface PokemonDetailsProps {
  pokemon: {
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
  };
  confidence?: number;
  onBack: () => void;
}

export const PokemonDetails: React.FC<PokemonDetailsProps> = ({
  pokemon,
  confidence,
  onBack,
}) => {
  return (
    <ScrollView
      style={styles.mainBody}
      contentContainerStyle={styles.scrollContent}
    >
      <View style={styles.detailsImageContainer}>
        <Image
          source={{ uri: pokemon.official_artwork }}
          style={styles.detailsImage}
        />
      </View>

      <View style={styles.detailsHeader}>
        <Text style={styles.pokemonNumber}>
          #{pokemon.id.toString().padStart(3, "0")}
        </Text>
        <Text style={styles.detailsPokemonName}>
          {pokemon.name.toUpperCase()}
        </Text>
        {confidence && (
          <Text style={styles.confidenceBadge}>
            {(confidence * 100).toFixed(1)}% MATCH
          </Text>
        )}
      </View>

      <View style={styles.typesContainer}>
        {pokemon.types.map((type, index) => (
          <View key={index} style={styles.typeBadge}>
            <Text style={styles.typeText}>{type.toUpperCase()}</Text>
          </View>
        ))}
      </View>

      <View style={styles.infoGrid}>
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>HEIGHT</Text>
          <Text style={styles.infoValue}>
            {(pokemon.height / 10).toFixed(1)}m
          </Text>
        </View>
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>WEIGHT</Text>
          <Text style={styles.infoValue}>
            {(pokemon.weight / 10).toFixed(1)}kg
          </Text>
        </View>
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>BASE EXP</Text>
          <Text style={styles.infoValue}>{pokemon.base_experience}</Text>
        </View>
      </View>

      <View style={styles.statsSection}>
        <Text style={styles.sectionTitle}>BASE STATS</Text>
        {Object.entries(pokemon.stats).map(([statName, value]) => (
          <View key={statName} style={styles.statRow}>
            <Text style={styles.statName}>
              {statName.toUpperCase().replace("-", " ")}
            </Text>
            <View style={styles.statBarContainer}>
              <View
                style={[
                  styles.statBarFill,
                  { width: `${(value / 255) * 100}%` },
                ]}
              />
            </View>
            <Text style={styles.statValueText}>{value}</Text>
          </View>
        ))}
      </View>

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

      <TouchableOpacity style={styles.backButton} onPress={onBack}>
        <Text style={styles.backButtonText}>← SCAN NEW POKÉMON</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};
