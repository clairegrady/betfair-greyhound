import pandas as pd
from pathlib import Path

# Path to your cleaned runners files
cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_year")

print("\n📊 Percentage of missing `ltp` in runners by year:\n")

# Find all runners_*.parquet files
runners_files = sorted(cleaned_dir.glob("runners_*.parquet"))

if not runners_files:
    print("❌ No runners_*.parquet files found.")
else:
    for file_path in runners_files:
        try:
            df = pd.read_parquet(file_path)

            # Check for presence of the 'ltp' column
            if "ltp" not in df.columns:
                print(f"⚠️ {file_path.name} has no 'ltp' column.")
                continue

            total_rows = len(df)
            missing_ltp = df["ltp"].isna().sum()
            percent_missing = (missing_ltp / total_rows) * 100 if total_rows > 0 else 0

            year = file_path.stem.split("_")[1]
            print(f"📅 {year}: {percent_missing:.2f}% missing LTP ({missing_ltp:,}/{total_rows:,})")
        except Exception as e:
            print(f"⚠️ Error reading {file_path.name}: {e}")
