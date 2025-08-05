import pandas as pd
from pathlib import Path

data_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")

parquet_files = sorted(data_dir.glob("combined_*.parquet"))

for parquet_file in parquet_files:
    try:
        df = pd.read_parquet(parquet_file, columns=["ltp"])
        total_rows = len(df)
        null_count = df["ltp"].isna().sum()
        percent_null = (null_count / total_rows) * 100 if total_rows > 0 else 0
        print(f"{parquet_file.name}: {null_count} nulls out of {total_rows} rows ({percent_null:.2f}%)")
    except Exception as e:
        print(f"Failed to process {parquet_file.name}: {e}")
