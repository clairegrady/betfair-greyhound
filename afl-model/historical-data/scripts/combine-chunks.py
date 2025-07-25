import pandas as pd
from pathlib import Path

# Load and concatenate all chunk files
chunk_dir = Path("historical-data/processed/cleaned_runner_chunks")
df = pd.concat([pd.read_parquet(p) for p in chunk_dir.glob("*.parquet")], ignore_index=True)

# Basic example of split (replace with your actual feature/target logic)
X = df.drop(columns=["target_column"])
y = df["target_column"]

from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, test_size=0.2, random_state=42)
