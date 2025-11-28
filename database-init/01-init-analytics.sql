-- Analytics Database Schema for Real-time Pokemon Scan Data

CREATE TABLE IF NOT EXISTS pokemon_scans (
    id SERIAL PRIMARY KEY,
    pokemon_id INTEGER NOT NULL,
    pokemon_name VARCHAR(100) NOT NULL,
    confidence_score FLOAT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100),
    source VARCHAR(50) DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS api_requests (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT,
    ip_address VARCHAR(45)
);

CREATE TABLE IF NOT EXISTS popular_pokemon (
    pokemon_id INTEGER PRIMARY KEY,
    pokemon_name VARCHAR(100) NOT NULL,
    total_scans INTEGER DEFAULT 0,
    last_scanned_at TIMESTAMP,
    first_scanned_at TIMESTAMP,
    avg_confidence FLOAT
);

CREATE INDEX IF NOT EXISTS idx_pokemon_scans_pokemon_id ON pokemon_scans(pokemon_id);
CREATE INDEX IF NOT EXISTS idx_pokemon_scans_scanned_at ON pokemon_scans(scanned_at);
CREATE INDEX IF NOT EXISTS idx_api_requests_requested_at ON api_requests(requested_at);

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

-- Sample data
-- INSERT INTO pokemon_scans (pokemon_id, pokemon_name, confidence_score, user_id) VALUES
-- (25, 'pikachu', 0.98, 'user_001'),
-- (1, 'bulbasaur', 0.95, 'user_002'),
-- (25, 'pikachu', 0.97, 'user_001'),
-- (4, 'charmander', 0.92, 'user_003'),
-- (25, 'pikachu', 0.99, 'user_004');

-- INSERT INTO api_requests (endpoint, method, status_code, response_time_ms) VALUES
-- ('/api/classify', 'POST', 200, 145),
-- ('/api/health', 'GET', 200, 5);
