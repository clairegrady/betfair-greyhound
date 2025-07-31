import pandas as pd
from pathlib import Path
import re

def load_and_combine_parquet_files(base_path: Path, prefix: str) -> pd.DataFrame:
    all_dfs = []
    for file_path in base_path.glob(f"{prefix}_*.parquet"):
        year_match = re.search(r'(\d{4})', file_path.name)
        year = int(year_match.group(1)) if year_match else None
        df = pd.read_parquet(file_path)
        if year:
            df["year"] = year
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

def save_subset(df: pd.DataFrame, output_dir: Path, prefix: str, label: str):
    path = output_dir / f"{prefix}_{label}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"Saved {prefix} subset '{label}' with {len(df)} rows")

def main():
    base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_year")
    output_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_split_by_year")

    for prefix in ["markets", "runners"]:
        df = load_and_combine_parquet_files(base_path, prefix)

        # Training: years 2019-2023 inclusive
        train_df = df[df["year"].between(2019, 2023)]
        save_subset(train_df, output_dir, prefix, "train_2019_23")

        # Backtesting: year 2024
        backtest_df = df[df["year"] == 2024]
        save_subset(backtest_df, output_dir, prefix, "backtest_2024")

        # Prediction: year 2025
        predict_df = df[df["year"] == 2025]
        save_subset(predict_df, output_dir, prefix, "predict_2025")

if __name__ == "__main__":
    main()
