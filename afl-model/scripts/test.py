import pandas as pd
from pathlib import Path

runners_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/raw_parquet/runners_2025.parquet")
df = pd.read_parquet(runners_path)

total = len(df)
missing = df['ltp'].isna().sum()
print(f"Total runners: {total:,}")
print(f"Missing last traded price (ltp): {missing:,} ({100 * missing / total:.2f}%)\n")

print("First few rows with missing last traded price (ltp):")
print(df[df['ltp'].isnull()][['marketId', 'id', 'ltp']].head(10))
