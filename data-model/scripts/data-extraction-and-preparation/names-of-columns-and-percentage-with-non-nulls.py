import pandas as pd
from pathlib import Path

base_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_year")

def print_non_null_percentages(df, df_name):
    print(f"\nColumns and non-null percentages in {df_name}:")
    total_rows = len(df)
    for col in df.columns:
        non_null_count = df[col].notna().sum()
        percentage = (non_null_count / total_rows) * 100 if total_rows else 0
        print(f"  - {col}: {non_null_count}/{total_rows} ({percentage:.2f}%)")

for year in range(2016, 2026):
    runners_file = base_path / f"runners_{year}.parquet"
    markets_file = base_path / f"markets_{year}.parquet"

    print(f"\n===== Year: {year} =====")

    if runners_file.exists():
        runners_df = pd.read_parquet(runners_file)
        print_non_null_percentages(runners_df, f"runners_{year}.parquet")
    else:
        print(f"runners_{year}.parquet not found.")

    if markets_file.exists():
        markets_df = pd.read_parquet(markets_file)
        print_non_null_percentages(markets_df, f"markets_{year}.parquet")
    else:
        print(f"markets_{year}.parquet not found.")
