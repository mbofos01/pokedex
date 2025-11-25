import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'pokedex')
DB_USER = os.getenv('DB_USER', 'pkmn')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'pkmn')
DB_PORT = os.getenv('DB_PORT', '5432')

def test_pokemon_lookup(pokemon_name: str):
    """Test Pokemon lookup by name"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print(f"\n{'='*60}")
        print(f"🔍 Looking up: {pokemon_name}")
        print(f"{'='*60}\n")
        
        # Get basic info
        cur.execute("""
            SELECT id, name, height, weight, base_experience
            FROM pokemon
            WHERE LOWER(
                    REGEXP_REPLACE(
                        REPLACE(REPLACE(REPLACE(name, '♂', 'm'), '♀', 'f'), '''', ''),
                        E'[^a-z0-9]', '', 'g'
                    )
                ) = LOWER(
                    REGEXP_REPLACE(
                        REPLACE(REPLACE(REPLACE(LOWER(%s), '♂', 'm'), '♀', 'f'), '''', ''),
                        E'[^a-z0-9]', '', 'g'
                    )
                )
        """, (pokemon_name,))
        pokemon = cur.fetchone()
        
        if not pokemon:
            print(f"❌ Pokemon '{pokemon_name}' not found in database\n")
            cur.close()
            conn.close()
            return
        
        print(f"✅ Found Pokemon:")
        print(f"   ID: {pokemon['id']}")
        print(f"   Name: {pokemon['name']}")
        print(f"   Height: {pokemon['height']} dm")
        print(f"   Weight: {pokemon['weight']} hg")
        print(f"   Base XP: {pokemon['base_experience']}")
        
        pokemon_id = pokemon['id']
        
        # Get types
        cur.execute("""
            SELECT type_name FROM types WHERE pokemon_id = %s
        """, (pokemon_id,))
        types = [row['type_name'] for row in cur.fetchall()]
        print(f"\n🏷️  Types: {', '.join(types)}")
        
        # Get stats
        cur.execute("""
            SELECT stat_name, base_stat FROM stats WHERE pokemon_id = %s ORDER BY stat_name
        """, (pokemon_id,))
        stats = cur.fetchall()
        print(f"\n📊 Stats:")
        for stat in stats:
            print(f"   {stat['stat_name']:20s}: {stat['base_stat']}")
        
        # Get abilities
        cur.execute("""
            SELECT ability_name, is_hidden FROM abilities WHERE pokemon_id = %s
        """, (pokemon_id,))
        abilities = cur.fetchall()
        print(f"\n⚡ Abilities:")
        for ability in abilities:
            hidden = " (Hidden)" if ability['is_hidden'] else ""
            print(f"   • {ability['ability_name']}{hidden}")
        
        # Get official artwork
        cur.execute("""
            SELECT url FROM images 
            WHERE pokemon_id = %s 
            AND image_type = 'other_official-artwork'
            LIMIT 1
        """, (pokemon_id,))
        image_row = cur.fetchone()
        if image_row:
            print(f"\n🎨 Official Artwork: {image_row['url']}")
        
        print(f"\n{'='*60}\n")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\nUsage: python test_pokemon_lookup.py <pokemon_name>")
        print("\nExamples:")
        print("  python test_pokemon_lookup.py pikachu")
        print("  python test_pokemon_lookup.py charizard")
        print("  python test_pokemon_lookup.py mr-mime")
        print()
        sys.exit(1)
    
    pokemon_name = sys.argv[1]
    test_pokemon_lookup(pokemon_name)
