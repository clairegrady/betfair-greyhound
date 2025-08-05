import pandas as pd
from pathlib import Path
from typing import cast

# CONFIG
INPUT_ROOT = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/greyhound_parquet")
OUTPUT_ROOT = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/cleaned_parquet")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

dry_run = False  # Set to False to save cleaned files

# Market critical columns to ensure key data is present
MARKET_CRITICAL_COLS = [
    "marketId",
    "eventId",
    "marketType",
    "marketTime",
    "status",
]

# Runner critical columns for static runner info
RUNNER_STATIC_CRITICAL_COLS = [
    "marketId",
    "runnerId",  # runner ID key from extraction
    "name",
    "status",
]

def clean_markets(df: pd.DataFrame) -> pd.DataFrame:
    allowed_statuses = {"OPEN", "SUSPENDED", "CLOSED"}

    df_dropped = df.dropna(subset=MARKET_CRITICAL_COLS)
    filtered = df_dropped[df_dropped["status"].isin(allowed_statuses)]
    filtered = cast(pd.DataFrame, filtered)
    filtered = filtered.drop_duplicates()

    return filtered

def clean_runners(df: pd.DataFrame) -> pd.DataFrame:
    allowed_runner_statuses = {"ACTIVE", "WINNER", "LOSER", "REMOVED"}
    print("Runner DataFrame columns:", df.columns.tolist())

    static_filter = df.dropna(subset=RUNNER_STATIC_CRITICAL_COLS)
    static_filtered = static_filter[static_filter["status"].isin(allowed_runner_statuses)]
    static_filtered = cast(pd.DataFrame, static_filtered)

    price_col = "lastTradedPrice"
    if price_col in df.columns:
        has_price_data = df[price_col].notnull()
        price_filtered = df[has_price_data]
        price_filtered = cast(pd.DataFrame, price_filtered)
        combined = pd.concat([static_filtered, price_filtered]).drop_duplicates()
    else:
        print(f"No price column '{price_col}' found; skipping price filtering.")
        combined = static_filtered.drop_duplicates()

    return combined


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
