from psycopg2.extras import execute_values
import psycopg2
import re
import pokebase as pb
import requests
import os
from urllib.parse import urlparse
import time


def get_all_images(p):
    images = {}

    # Standard sprites
    sprites = p.sprites
    images['front_default'] = sprites.front_default
    images['back_default'] = sprites.back_default
    images['front_shiny'] = sprites.front_shiny
    images['back_shiny'] = sprites.back_shiny
    images['front_female'] = getattr(sprites, 'front_female', None)
    images['back_female'] = getattr(sprites, 'back_female', None)
    images['front_shiny_female'] = getattr(sprites, 'front_shiny_female', None)
    images['back_shiny_female'] = getattr(sprites, 'back_shiny_female', None)

    # "Other" artwork
    if hasattr(sprites, 'other'):
        other = sprites.other
        for key in other.__dict__:
            obj = getattr(other, key)
            if hasattr(obj, 'front_default'):
                images[f'other_{key}'] = obj.front_default

    # Animated sprites from versions (if available)
    if hasattr(sprites, 'versions'):
        versions = sprites.versions
        for gen_name, gen_data in versions.__dict__.items():
            for game_name, game_data in gen_data.__dict__.items():
                for anim_key in ['front_default', 'back_default', 'front_shiny', 'back_shiny']:
                    url = getattr(game_data, anim_key, None)
                    if url:
                        images[f"{gen_name}_{game_name}_{anim_key}"] = url

    # Filter out None values
    images = {k: v for k, v in images.items() if v is not None}
    return images


def get_all_moves(p):
    moves = []

    for move_entry in p.moves:
        move_name = move_entry.move.name
        # Each move can be learned in multiple versions or by multiple methods
        for detail in move_entry.version_group_details:
            method = detail.move_learn_method.name
            level = detail.level_learned_at
            version_group = detail.version_group.name
            moves.append({
                "name": move_name,
                "method": method,
                "level": level,
                "version_group": version_group
            })

    return moves


def get_abilities(p):
    abilities = []
    for a in p.abilities:
        abilities.append({
            "name": a.ability.name,
            "is_hidden": a.is_hidden,
            "slot": a.slot
        })
    return abilities


def get_stats(p):
    stats = []
    for s in p.stats:
        stats.append({
            "stat_name": s.stat.name,
            "base_stat": s.base_stat,
            "effort": s.effort
        })
    return stats


def get_basic_info(p):
    return {
        "id": p.id,
        "name": p.name,
        "height": p.height,
        "weight": p.weight,
        "base_experience": p.base_experience,
        "order_num": p.order,
        "is_default": p.is_default,
        "species_name": p.species.name
    }


def download_image(url, pokemon_id, image_type, images_dir="/app/images"):
    """Download an image and return the local file path"""
    try:
        # Create images directory if it doesn't exist
        os.makedirs(images_dir, exist_ok=True)
        
        # Create subdirectory for this pokemon
        pokemon_dir = os.path.join(images_dir, str(pokemon_id))
        os.makedirs(pokemon_dir, exist_ok=True)
        
        # Get file extension from URL
        parsed_url = urlparse(url)
        file_ext = os.path.splitext(parsed_url.path)[1] or '.png'
        
        # Create filename
        filename = f"{image_type}{file_ext}"
        file_path = os.path.join(pokemon_dir, filename)
        
        # Skip if file already exists
        if os.path.exists(file_path):
            return file_path
        
        # Download the image
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Save the image
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        # print(f"  Downloaded: {image_type}")
        return file_path
        
    except Exception as e:
        print(f"  Failed to download {image_type}: {e}")
        return None


def download_all_images(p):
    """Download all images for a pokemon and return a dict with local paths"""
    images_urls = get_all_images(p)
    local_images = {}
    
    # print(f"  Downloading {len(images_urls)} images...")
    
    for image_type, url in images_urls.items():
        if url:
            local_path = download_image(url, p.id, image_type)
            if local_path:
                local_images[image_type] = local_path
            # Small delay to be nice to the server
            time.sleep(0.1)
    
    print(f"  Successfully downloaded {len(local_images)} images")
    return local_images


def get_types(p):
    return [t.type.name for t in p.types]


# -----------------------
# Database connection
# -----------------------
conn = psycopg2.connect(
    dbname="pokedex",
    user="pkmn",
    password="pkmn",
    host="postgres",
    port=5432
)
cur = conn.cursor()

# -----------------------
# Create tables
# -----------------------
cur.execute("""
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
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS types (
    pokemon_id INT REFERENCES pokemon(id),
    type_name TEXT,
    PRIMARY KEY (pokemon_id, type_name)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS abilities (
    pokemon_id INT REFERENCES pokemon(id),
    ability_name TEXT,
    is_hidden BOOLEAN,
    slot INT,
    PRIMARY KEY (pokemon_id, ability_name)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    pokemon_id INT REFERENCES pokemon(id),
    stat_name TEXT,
    base_stat INT,
    effort INT,
    PRIMARY KEY (pokemon_id, stat_name)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS moves (
    pokemon_id INT REFERENCES pokemon(id),
    move_name TEXT,
    method TEXT,
    level INT,
    version_group TEXT,
    PRIMARY KEY (pokemon_id, move_name, method, version_group)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS images (
    pokemon_id INT REFERENCES pokemon(id),
    image_type TEXT,
    url TEXT,
    image_path TEXT,
    PRIMARY KEY (pokemon_id, image_type)
);
""")
conn.commit()


def insert_pokemon(p):
    info = get_basic_info(p)
    try:
        cur.execute("""
            INSERT INTO pokemon (id, name, height, weight, base_experience, order_num, is_default, species_name)
            VALUES (%(id)s, %(name)s, %(height)s, %(weight)s, %(base_experience)s, %(order_num)s, %(is_default)s, %(species_name)s)
            ON CONFLICT (id) DO NOTHING
        """, info)

        # Types
        for t in get_types(p):
            cur.execute("""
                INSERT INTO types (pokemon_id, type_name)
                VALUES (%s, %s)
                ON CONFLICT (pokemon_id, type_name) DO NOTHING
            """, (p.id, t))

        # Abilities
        for a in get_abilities(p):
            cur.execute("""
                INSERT INTO abilities (pokemon_id, ability_name, is_hidden, slot)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (pokemon_id, ability_name) DO NOTHING
            """, (p.id, a["name"], a["is_hidden"], a["slot"]))

        # Stats
        for s in get_stats(p):
            cur.execute("""
                INSERT INTO stats (pokemon_id, stat_name, base_stat, effort)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (pokemon_id, stat_name) DO NOTHING
            """, (p.id, s["stat_name"], s["base_stat"], s["effort"]))

        # Moves
        for m in get_all_moves(p):
            cur.execute("""
                INSERT INTO moves (pokemon_id, move_name, method, level, version_group)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pokemon_id, move_name, method, version_group) DO NOTHING
            """, (p.id, m["name"], m["method"], m["level"], m["version_group"]))



        # Images - Download and save locally
        local_images = download_all_images(p)
        for image_type, local_path in local_images.items():
            # Get original URL for reference
            original_urls = get_all_images(p)
            original_url = original_urls.get(image_type)
            
            cur.execute("""
                INSERT INTO images (pokemon_id, image_type, url, image_path)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (pokemon_id, image_type) DO NOTHING
            """, (p.id, image_type, original_url, local_path))

        conn.commit()
        print(f"Inserted {p.name}")
    except Exception as e:
        conn.rollback()
        print(f"Failed {p.name}: {e}")


# -----------------------
# Fetch all Pokémon
# -----------------------
pokemon_list = list(pb.APIResourceList('pokemon'))

print(f"Total Pokémon to process: {len(pokemon_list)}")

pokemon_list = pokemon_list[:10]

for idx, res in enumerate(pokemon_list, 1):
    p = pb.pokemon(res['name'])
    print(f"[{idx}/{len(pokemon_list)}] Processing {p.name}")
    insert_pokemon(p)


cur.close()
conn.close()
print("Done!")
