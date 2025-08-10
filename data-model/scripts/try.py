
import pandas as pd
from pathlib import Path

# Path to the combined parquet file you want to check
combined_file = Path("//Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_day/combined_2025_May_11.parquet")

df = pd.read_parquet(combined_file)

print(f"Columns in {combined_file.name}:")
print(df.columns.tolist())

has_status_x = 'status_x' in df.columns
has_status_y = 'status_y' in df.columns

print(f"\nHas status_x: {has_status_x}")
print(f"Has status_y: {has_status_y}")

if not has_status_x and not has_status_y:
    print("No status_x or status_y columns found.")
elif has_status_x and has_status_y:
    print("Both status_x and status_y columns found.")
elif has_status_x:
    print("Only status_x found.")
elif has_status_y:
    print("Only status_y found.")