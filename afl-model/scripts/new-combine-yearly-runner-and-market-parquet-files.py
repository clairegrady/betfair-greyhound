import pandas as pd
from pathlib import Path

def load_and_combine_parquet_files(base_path: Path, filename: str) -> pd.DataFrame:
    all_dfs = []
    for year_dir in sorted(base_path.iterdir()):
        file_path = year_dir / filename
        if file_path.exists():
            df = pd.read_parquet(file_path)
            df["year"] = year_dir.name  # optionally add year info
            all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)

def save_combined(df: pd.DataFrame, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

def main():
    base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet")
    processed_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_combined_parquet")

    # Combine and save markets
    markets_df = load_and_combine_parquet_files(base_path, "markets.parquet")
    save_combined(markets_df, processed_path / "markets.parquet")
    print(f"Combined markets: {len(markets_df)} rows")

    # Combine and save runners
    runners_df = load_and_combine_parquet_files(base_path, "runners.parquet")
    save_combined(runners_df, processed_path / "runners.parquet")
    print(f"Combined runners: {len(runners_df)} rows")


if __name__ == "__main__":
    main()
