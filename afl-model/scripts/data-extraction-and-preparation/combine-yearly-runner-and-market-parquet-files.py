import pandas as pd
from pathlib import Path
import re

def load_and_combine_parquet_files(base_path: Path, prefix: str) -> pd.DataFrame:
    all_dfs = []
    for file_path in base_path.glob(f"{prefix}_*.parquet"):
        year_match = re.search(r'(\d{4})', file_path.name)
        year = year_match.group(1) if year_match else None
        df = pd.read_parquet(file_path)
        if year:
            df["year"] = int(year)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

def save_combined(df: pd.DataFrame, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

def main():
    base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_year")
    output_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_combined_parquet")

    for prefix in ["markets", "runners"]:
        df = load_and_combine_parquet_files(base_path, prefix)
        save_combined(df, output_dir / f"{prefix}.parquet")
        print(f"Combined {prefix}: {len(df)} rows")

if __name__ == "__main__":
    main()
