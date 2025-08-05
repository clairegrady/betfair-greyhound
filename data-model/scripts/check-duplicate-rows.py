import pandas as pd
from pathlib import Path
import hashlib

def hash_row(row):
    """Create a consistent hash of a row's content"""
    row_bytes = pd.util.hash_pandas_object(row, index=False).values
    return hashlib.sha256(row_bytes.tobytes()).hexdigest()

data_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")

for parquet_file in sorted(data_dir.glob("*.parquet")):
    try:
        df = pd.read_parquet(parquet_file)

        # Generate row-wise hashes
        hashes = pd.util.hash_pandas_object(df, index=False)
        duplicate_mask = hashes.duplicated(keep='first')
        duplicate_rows = duplicate_mask.sum()
        total_rows = len(df)
        pct_duplicates = (duplicate_rows / total_rows) * 100 if total_rows > 0 else 0

        print(f"{parquet_file.name}: {duplicate_rows} truly duplicate rows out of {total_rows} rows ({pct_duplicates:.2f}%)")

        # Print a few for visual inspection
        if duplicate_rows > 0:
            print("Sample truly duplicate rows:")
            print(df[duplicate_mask].head(10))
            print("-" * 80)

    except Exception as e:
        print(f"Failed to process {parquet_file.name}: {e}")
