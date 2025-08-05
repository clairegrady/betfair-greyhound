import pandas as pd
from pathlib import Path

base_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_year")

def count_keyword_percentages(df, df_name):
    total_rows = len(df)
    print(f"\n📊 Analyzing {df_name}:")
    print(f"   → Total rows: {total_rows}")

    for keyword in ['WINNER', 'LOSER']:
        mask = df.apply(lambda col: col.astype(str).str.upper().str.contains(keyword, na=False))
        matched_rows = mask.any(axis=1)
        count = matched_rows.sum()
        percentage = (count / total_rows) * 100 if total_rows else 0
        print(f"   • '{keyword}' appears in {count} rows ({percentage:.2f}%)")

for year in range(2016, 2026):
    runners_file = base_path / f"runners_{year}.parquet"
    markets_file = base_path / f"markets_{year}.parquet"

    print(f"\n===== Year: {year} =====")

    if runners_file.exists():
        runners_df = pd.read_parquet(runners_file)
        count_keyword_percentages(runners_df, f"runners_{year}.parquet")
    else:
        print(f"Runners file for {year} not found.")

    if markets_file.exists():
        markets_df = pd.read_parquet(markets_file)
        count_keyword_percentages(markets_df, f"markets_{year}.parquet")
    else:
        print(f"Markets file for {year} not found.")
