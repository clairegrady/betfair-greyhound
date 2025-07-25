import pandas as pd
from pathlib import Path

cleaned_chunks_path = Path("/home/ec2-user/processed/cleaned_chunks")
output_file = Path("/home/ec2-user/processed/selected_features.parquet")

# Columns we want to keep
selected_columns = [
    "marketId", "eventId", "runnerName", "marketName", "venue", "status",
    "bsp", "handicap", "adjustmentFactor", "marketStartTime"
]

# To hold all valid rows
all_rows = []

for file in sorted(cleaned_chunks_path.glob("cleaned_*.parquet")):
    print(f"Reading {file.name}")
    try:
        df = pd.read_parquet(file, engine="fastparquet")
        df = df[selected_columns].dropna()
        all_rows.append(df)
    except Exception as e:
        print(f"⚠️ Skipping {file.name}: {e}")

# Combine all selected data
combined_df = pd.concat(all_rows, ignore_index=True)
combined_df.to_parquet(output_file, index=False, engine="fastparquet")

print(f"✅ Selected features saved to: {output_file}")
print(combined_df.info())
