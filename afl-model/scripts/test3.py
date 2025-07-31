import pandas as pd
from pathlib import Path

base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_parquet_by_year")

def non_empty_percentage(series):
    total = len(series)
    non_empty_count = series.dropna().astype(str).map(lambda x: x.strip() != "").sum()
    percent = (non_empty_count / total) * 100 if total > 0 else 0
    return non_empty_count, total, percent

for year in range(2016, 2026):
    runners_file = base_path / f"runners_{year}.parquet"
    print(f"\n===== Year: {year} =====")

    if runners_file.exists():
        df = pd.read_parquet(runners_file)

        if 'status' in df.columns:
            count, total, pct = non_empty_percentage(df['status'])
            print(f"Status column: {count}/{total} rows have a value ({pct:.2f}%)")
            print("Unique values in 'status':", df['status'].dropna().unique().tolist())
        else:
            print("No 'status' column found.")

        if 'name' in df.columns:
            count, total, pct = non_empty_percentage(df['name'])
            print(f"Name column: {count}/{total} rows have a value ({pct:.2f}%)")
        else:
            print("No 'name' column found.")
    else:
        print(f"File runners_{year}.parquet not found.")
