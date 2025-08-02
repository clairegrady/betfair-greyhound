import pandas as pd
from pathlib import Path
import json
from collections import defaultdict

# Setup
base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/extracted-horseracing/BASIC/decompressed_files")
years = range(2016, 2026)
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
days = range(1, 32)

# Accumulators
column_counts = defaultdict(int)
column_totals = defaultdict(int)
total_files = 0
skipped_files = 0

# Traverse directories
for year in years:
    for month in months:
        for day in days:
            day_path = base_path / str(year) / month / str(day)
            if not day_path.exists():
                continue
            for file in day_path.iterdir():
                if file.is_dir():
                    continue  # skip directories
                try:
                    df = pd.read_json(file, lines=True)
                except ValueError:
                    try:
                        with open(file) as f:
                            data = json.load(f)
                        df = pd.DataFrame(data)
                    except Exception:
                        skipped_files += 1
                        continue

                if df.empty:
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
