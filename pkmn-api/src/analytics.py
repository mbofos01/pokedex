from datetime import datetime
import psycopg2

def get_analytics_conn():
    return psycopg2.connect(
        dbname="pokedex",
        user="pkmn",
        password="pkmn",
        host="postgres",
        port=5432
    )

def log_pokemon_scan(pokemon_id, pokemon_name, confidence_score, user_id=None, source="api"):
    conn = get_analytics_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pokemon_scans (pokemon_id, pokemon_name, confidence_score, user_id, source)
        VALUES (%s, %s, %s, %s, %s)
    """, (pokemon_id, pokemon_name, confidence_score, user_id, source))
    conn.commit()
    cur.close()
    conn.close()

def log_api_request(endpoint, method, status_code, response_time_ms, user_agent=None, ip_address=None):
    conn = get_analytics_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO api_requests (endpoint, method, status_code, response_time_ms, user_agent, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (endpoint, method, status_code, response_time_ms, user_agent, ip_address))
    conn.commit()
    cur.close()
    conn.close()
