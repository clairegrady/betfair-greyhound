import pandas as pd
from pathlib import Path

# Define paths
input_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_parquet_by_year")
output_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_year")
output_dir.mkdir(parents=True, exist_ok=True)

years = range(2016, 2026)

# Columns to keep in runners
runners_cols = [
    "status", "sortPriority", "adjustmentFactor", "ltp", "ltp_pt", "ltp_dt", "pt_runner",
    "marketId", "id", "name"
]

# Columns to keep in markets
markets_cols = [
    "bspMarket", "turnInPlayEnabled", "persistenceEnabled", "marketBaseRate",
    "eventId", "eventTypeId", "marketTime", "openDate", "numberOfWinners",
    "numberOfActiveRunners", "bettingType", "marketType", "status", "venue", "countryCode",
    "timezone", "eventName", "name", "pt", "suspendTime", "bspReconciled", "complete",
    "inPlay", "crossMatching", "runnersVoidable", "betDelay", "discountAllowed", "version", "marketId"
]

for year in years:
    print(f"Processing year {year}...")

    # Load runners parquet
    runners_path = input_dir / f"runners_{year}.parquet"
    runners_df = pd.read_parquet(runners_path)

    # Keep only desired columns (if any missing columns, they will be ignored)
    runners_df = runners_df[[col for col in runners_cols if col in runners_df.columns]]

    # Drop rows where ltp is missing
    runners_df = runners_df.dropna(subset=["ltp"])

    # adjustmentFactor: keep, missing values remain NaN

    # Save cleaned runners parquet
    runners_df.to_parquet(output_dir / f"runners_{year}.parquet", index=False)

    # Load markets parquet
    markets_path = input_dir / f"markets_{year}.parquet"
    markets_df = pd.read_parquet(markets_path)

    # Keep only desired columns (ignore missing columns)
    markets_df = markets_df[[col for col in markets_cols if col in markets_df.columns]]

    # Save cleaned markets parquet
    markets_df.to_parquet(output_dir / f"markets_{year}.parquet", index=False)

print("Cleaning complete.")
