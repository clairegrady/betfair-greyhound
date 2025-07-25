import pandas as pd
from pathlib import Path

# Paths
merged_chunks_path = Path("/home/ec2-user/processed/merged_chunks")
cleaned_chunks_path = Path("/home/ec2-user/processed/cleaned_chunks")
cleaned_chunks_path.mkdir(parents=True, exist_ok=True)

# Critical columns to check
critical_columns = ["marketId", "eventId", "runnerName", "startTime", "price"]

# Process each merged chunk
for chunk_file in sorted(merged_chunks_path.glob("*.parquet")):
    cleaned_file = cleaned_chunks_path / f"cleaned_{chunk_file.name}"

    if cleaned_file.exists():
        print(f"Skipping {chunk_file.name}, already cleaned.")
        continue

    print(f"Processing {chunk_file.name}...")

    try:
        df = pd.read_parquet(chunk_file, engine="fastparquet")
    except Exception as e:
        print(f"❌ Error reading {chunk_file.name}: {e}")
        continue

    initial_len = len(df)

    # Cleaning
    df_clean = df.dropna(subset=critical_columns).copy()
    df_clean["startTime"] = pd.to_datetime(df_clean["startTime"], errors="coerce")
    df_clean = df_clean.dropna(subset=["startTime"])
    df_clean = df_clean[df_clean["price"] > 1.0]
    df_clean = df_clean.drop_duplicates()

    print(f"🧼 Cleaned {chunk_file.name}: {initial_len} → {len(df_clean)} rows")

    # Save cleaned chunk
    df_clean.to_parquet(cleaned_file, index=False, engine="fastparquet")
    print(f"✅ Saved cleaned chunk to: {cleaned_file}")
