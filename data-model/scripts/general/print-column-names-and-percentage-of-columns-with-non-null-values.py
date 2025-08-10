
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Setup for cleaned daily parquet files
base_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_day")

column_counts = defaultdict(int)
column_totals = defaultdict(int)
total_files = 0
skipped_files = 0

import traceback

# Option: Only read the first N rows to avoid memory issues (set to None to read all rows)
N_ROWS = None  # Always read all rows

# Traverse all combined_*.parquet files in the directory
for file in base_path.glob("combined_*.parquet"):
    print(f"\nProcessing file: {file.name}")
    try:
        if N_ROWS is not None:
            df = pd.read_parquet(file, engine='pyarrow').head(N_ROWS)
        else:
            df = pd.read_parquet(file, engine='pyarrow')
    except Exception as e:
        print(f"❌ Failed to load {file.name}: {e}")
        traceback.print_exc()
        skipped_files += 1
        continue
    if df.empty:
        print(f"⚠️ {file.name} is empty, skipping.")
        continue
    total_files += 1
    for col in df.columns:
        column_counts[col] += df[col].notna().sum()
        column_totals[col] += len(df)

# Final report
print(f"\n📊 Column Coverage Report (across {total_files} files, {skipped_files} skipped):\n{'-'*50}")
coverage = {
    col: (column_counts[col] / column_totals[col]) * 100
    for col in column_counts
}

for col, pct in sorted(coverage.items(), key=lambda x: -x[1]):
    print(f"{col:40}: {pct:6.2f}% non-null")
