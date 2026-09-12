-- Analytics Database Schema for Real-time Pokemon Scan Data

CREATE TABLE IF NOT EXISTS pokemon (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Sentinel row for classifications that couldn't be identified
INSERT INTO pokemon (id, name)
VALUES (-1, 'Unknown')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS api_requests (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL UNIQUE,
    endpoint VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filename VARCHAR(255) NOT NULL,
    image_bytes NUMERIC DEFAULT 0,
    client_ip VARCHAR(45),
    user_agent TEXT,
    forwarded_for VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS pokemon_scans (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) REFERENCES api_requests(request_id),
    pokemon_id INTEGER NOT NULL REFERENCES pokemon(id),
    pokemon_name VARCHAR(100) NOT NULL,
    confidence_score FLOAT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100),
    source VARCHAR(50) DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS popular_pokemon (
    pokemon_id INTEGER PRIMARY KEY REFERENCES pokemon(id),
    pokemon_name VARCHAR(100) NOT NULL,
    total_scans INTEGER DEFAULT 0,
    last_scanned_at TIMESTAMP,
    first_scanned_at TIMESTAMP,
    avg_confidence FLOAT
);

CREATE INDEX IF NOT EXISTS idx_pokemon_scans_pokemon_id ON pokemon_scans(pokemon_id);
CREATE INDEX IF NOT EXISTS idx_pokemon_scans_scanned_at ON pokemon_scans(scanned_at);
CREATE INDEX IF NOT EXISTS idx_api_requests_timestamp ON api_requests(timestamp);

CREATE OR REPLACE FUNCTION update_popular_pokemon()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO popular_pokemon (pokemon_id, pokemon_name, total_scans, last_scanned_at, first_scanned_at, avg_confidence)
    VALUES (NEW.pokemon_id, NEW.pokemon_name, 1, NEW.scanned_at, NEW.scanned_at, NEW.confidence_score)
    ON CONFLICT (pokemon_id) DO UPDATE
    SET total_scans = popular_pokemon.total_scans + 1,
        last_scanned_at = NEW.scanned_at,
        avg_confidence = (popular_pokemon.avg_confidence * popular_pokemon.total_scans + NEW.confidence_score) / (popular_pokemon.total_scans + 1);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_popular_pokemon ON pokemon_scans;
CREATE TRIGGER trigger_update_popular_pokemon
AFTER INSERT ON pokemon_scans
FOR EACH ROW EXECUTE FUNCTION update_popular_pokemon();