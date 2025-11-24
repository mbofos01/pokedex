from cryptography.fernet import Fernet
import os

# Generate encryption key
key = Fernet.generate_key().decode()

# Path to .env file (same directory as this script)
env_file = os.path.join(os.path.dirname(__file__), '.env')

# Read existing .env file
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        lines = f.readlines()
else:
    lines = []

# Check if ENCRYPTION_KEY already exists
key_exists = any(line.startswith('ENCRYPTION_KEY=') for line in lines)

if key_exists:
    print("⚠️  ENCRYPTION_KEY already exists in .env file")
    response = input("Do you want to generate a new key? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Key generation cancelled")
        exit(0)
    # Remove old key
    lines = [line for line in lines if not line.startswith('ENCRYPTION_KEY=')]

# Add new key
lines.append(f'ENCRYPTION_KEY={key}\n')

# Write back to .env file
with open(env_file, 'w') as f:
    f.writelines(lines)

print(f"✅ Generated new encryption key and saved to {env_file}")
print(f"🔑 Key: {key}")
