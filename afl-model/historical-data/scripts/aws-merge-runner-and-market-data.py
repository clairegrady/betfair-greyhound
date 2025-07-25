from pathlib import Path
import pandas as pd

# Update these paths to your EC2 file locations
runner_chunks_path = Path("/home/ec2-user/processed/runner_level_chunks")
greyhound_file = Path("/home/ec2-user/processed/selected_afl_features.parquet")
merged_chunks_path = Path("/home/ec2-user/processed/merged_chunks")

merged_chunks_path.mkdir(parents=True, exist_ok=True)

# Load Greyhound feature data once
greyhound_df = pd.read_parquet(greyhound_file, engine='fastparquet')  # or engine='pyarrow' if preferred
print(f"Loaded Greyhound feature data: {len(greyhound_df)} records")

for chunk_file in sorted(runner_chunks_path.glob("*.parquet")):
    merged_file = merged_chunks_path / f"merged_{chunk_file.name}"

    if merged_file.exists():
        print(f"Skipping {chunk_file.name} because merged file already exists")
        continue

    print(f"Processing chunk: {chunk_file.name}")

    runner_df = pd.read_parquet(chunk_file, engine='fastparquet')
    print(f"Loaded runner chunk: {len(runner_df)} records")

    merged_df = runner_df.merge(greyhound_df, on=["marketId", "eventId"], how="left")

    merged_df.to_parquet(merged_file, engine='fastparquet', index=False)
    print(f"Saved merged chunk to {merged_file}")
