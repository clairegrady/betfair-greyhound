import json
import pandas as pd
from pathlib import Path

data_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/jsonl_files")
output_file = Path("afl_data.csv")

# If output file exists, remove it to start fresh
if output_file.exists():
    output_file.unlink()

for file in data_dir.rglob("*.jsonl"):
    try:
        df = pd.read_json(file, lines=True)
        print(f"Loaded {len(df)} rows from {file.name}")

        # Append to CSV, create file if it doesn't exist
        df.to_csv(output_file, mode='a', header=not output_file.exists(), index=False)

    except Exception as e:
        print(f"Failed to process {file}: {e}")
