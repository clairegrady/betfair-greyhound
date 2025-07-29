import pandas as pd
from typing import cast
from pathlib import Path

# CONFIG
INPUT_ROOT = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/greyhound_parquet")
OUTPUT_ROOT = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/cleaned_parquet")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

dry_run = False  # Set to False to save cleaned files

MARKET_CRITICAL_COLS = [
    "marketId",
    "eventId",
    "marketType",
    "marketTime",
    "status",
]

RUNNER_CRITICAL_COLS = [
    "marketId",
    "runnerId",
    "name",
    "status",
]

def clean_markets(df: pd.DataFrame) -> pd.DataFrame:
    allowed_statuses = {"OPEN", "SUSPENDED", "CLOSED"}
    filtered = df.loc[df["status"].isin(allowed_statuses)]
    df = cast(pd.DataFrame, filtered.copy())
    df = df.drop_duplicates()
    return df

def clean_runners(df: pd.DataFrame) -> pd.DataFrame:
    allowed_runner_statuses = {"ACTIVE", "WINNER", "LOSER", "REMOVED"}
    df = df.dropna(subset=RUNNER_CRITICAL_COLS)
    filtered = df.loc[df["status"].isin(allowed_runner_statuses)]
    df = cast(pd.DataFrame, filtered.copy())
    return df

def process_year(year: int):
    input_dir = INPUT_ROOT / str(year)
    output_dir = OUTPUT_ROOT / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)

    markets_file = input_dir / "markets.parquet"
    runners_file = input_dir / "runners.parquet"

    if not markets_file.exists() or not runners_file.exists():
        print(f"⚠️ Missing parquet files for {year}. Skipping.")
        return

    print(f"Processing year {year}...")

    markets_df = pd.read_parquet(markets_file)
    runners_df = pd.read_parquet(runners_file)

    cleaned_markets = clean_markets(markets_df)
    cleaned_runners = clean_runners(runners_df)

    print(f"Year {year} cleaning summary:")
    print(f"  Markets: {len(markets_df)} → {len(cleaned_markets)} rows")
    print(f"  Runners: {len(runners_df)} → {len(cleaned_runners)} rows")

    if not dry_run:
        cleaned_markets.to_parquet(output_dir / "markets.parquet", index=False)
        cleaned_runners.to_parquet(output_dir / "runners.parquet", index=False)
        print(f"  Saved cleaned data for year {year}\n")
    else:
        print(f"  Dry run enabled, no files saved.\n")

if __name__ == "__main__":
    for y in range(2017, 2026):
        process_year(y)
