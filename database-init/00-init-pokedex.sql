-- Pokedex Database Schema (matches Python script structure)

CREATE TABLE IF NOT EXISTS pokemon (
    id SERIAL PRIMARY KEY,
    name TEXT,
    height INT,
    weight INT,
    base_experience INT,
    order_num INT,
    is_default BOOLEAN,
    species_name TEXT
);

CREATE TABLE IF NOT EXISTS types (
    pokemon_id INT REFERENCES pokemon(id),
    type_name TEXT,
    PRIMARY KEY (pokemon_id, type_name)
);

CREATE TABLE IF NOT EXISTS abilities (
    pokemon_id INT REFERENCES pokemon(id),
    ability_name TEXT,
    is_hidden BOOLEAN,
    slot INT,
    PRIMARY KEY (pokemon_id, ability_name)
);

CREATE TABLE IF NOT EXISTS stats (
    pokemon_id INT REFERENCES pokemon(id),
    stat_name TEXT,
    base_stat INT,
    effort INT,
    PRIMARY KEY (pokemon_id, stat_name)
);

CREATE TABLE IF NOT EXISTS moves (
    pokemon_id INT REFERENCES pokemon(id),
    move_name TEXT,
    method TEXT,
    level INT,
    version_group TEXT,
    PRIMARY KEY (pokemon_id, move_name, method, version_group)
);

CREATE TABLE IF NOT EXISTS images (
    pokemon_id INT REFERENCES pokemon(id),
    image_type TEXT,
    url TEXT,
    PRIMARY KEY (pokemon_id, image_type)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_pokemon_name ON pokemon(name);
CREATE INDEX IF NOT EXISTS idx_types_type_name ON types(type_name);
CREATE INDEX IF NOT EXISTS idx_abilities_ability_name ON abilities(ability_name);
CREATE INDEX IF NOT EXISTS idx_moves_move_name ON moves(move_name);
CREATE INDEX IF NOT EXISTS idx_images_image_type ON images(image_type);
