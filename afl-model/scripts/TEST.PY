import pandas as pd
from pathlib import Path

month_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_parquet_by_month/2022-Sep")
runners_file = month_path / "runners_2022_Sep.parquet"

df = pd.read_parquet(runners_file)
print("Columns in runners_2022_Sep.parquet:", df.columns.tolist())
print("Number of rows:", len(df))
