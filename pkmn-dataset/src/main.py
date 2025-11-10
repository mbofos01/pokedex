from datasets import Dataset, Image, ClassLabel
import pandas as pd
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build SQLAlchemy connection string
db_url = (
    f"postgresql+psycopg2://{os.getenv('DB_USER', 'pokemon_user')}:" 
    f"{os.getenv('DB_PASSWORD', 'pokemon_pass')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:" 
    f"{os.getenv('DB_PORT', 5432)}/"
    f"{os.getenv('DB_NAME', 'pokemon_db')}"
)

print(f"Connecting to database: {db_url.split('@')[1]}")

# Create SQLAlchemy engine
engine = create_engine(db_url)

# Query data
df = pd.read_sql_query(
    """
    SELECT DISTINCT
        p.name as label,
        i.image_path
    FROM pokemon p
    LEFT JOIN images i ON p.id = i.pokemon_id
    WHERE i.image_path IS NOT NULL 
    ORDER BY p.name;
    """,
    engine
)

print(f"Found {len(df)} records from database")
print(f"Unique Pokemon: {df['label'].nunique()}")
print(df.head())

# Create Hugging Face dataset
dataset = Dataset.from_pandas(df)

# Cast image_path column to Image feature
dataset = dataset.cast_column("image_path", Image())
dataset = dataset.rename_column("image_path", "image")

# Encode labels as integers
labels = sorted(df["label"].unique())
class_labels = ClassLabel(names=labels)
# Convert string labels to integer indices
dataset = dataset.map(lambda x: {"label": class_labels.str2int(x["label"])}, batched=False)

# Cast the "label" column properly to ClassLabel
dataset = dataset.cast_column("label", class_labels)

print(dataset[0])

# Train/test split
dataset = dataset.train_test_split(test_size=0.2)
train_ds = dataset["train"]
test_ds = dataset["test"]

# Save locally
dataset.save_to_disk("pokemon_dataset_hf")



# reload later
from datasets import load_from_disk
dataset = load_from_disk("pokemon_dataset_hf")

print(dataset)


# Split the training data into train and test (let's say 10% for the test set)
train_test_split = dataset['train'].train_test_split(test_size=0.1)

# Further split the training set to get a validation set (e.g., 10% of the training set)
train_val_split = train_test_split['train'].train_test_split(test_size=0.1)

# Combine the splits into a new DatasetDict
final_dataset = {
    'train': train_val_split['train'],
    'val': train_val_split['test'],  
    'test': train_test_split['test']  
}

train_ds = final_dataset["train"]
val_ds = final_dataset["val"]
test_ds = final_dataset["test"]


import matplotlib.pyplot as plt

shown_labels = set()

plt.figure(figsize=(30, 8))

# Loop through the dataset and plot the first image of each label
for i, sample in enumerate(train_ds):
    label = train_ds.features["label"].names[sample["label"]]
    if label not in shown_labels:
        plt.subplot(1, len(train_ds.features["label"].names), len(shown_labels) + 1)
        plt.imshow(sample["image"])
        plt.title(label)
        plt.axis("off")
        shown_labels.add(label)
        if len(shown_labels) == len(train_ds.features["label"].names):
            break

plt.savefig("/app/src/pokemon_species_examples.png")