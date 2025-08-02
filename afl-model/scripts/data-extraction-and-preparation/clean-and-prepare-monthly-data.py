import pandas as pd
from pathlib import Path

# Define input/output directories
input_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_parquet_by_month")
temp_cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_month/tmp")
final_output_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_month")
failed_log = Path("failed_months.txt")
current_processing_file = Path("currently_processing.txt")

temp_cleaned_dir.mkdir(parents=True, exist_ok=True)
final_output_dir.mkdir(parents=True, exist_ok=True)

# Columns to retain
runners_cols = [
    "status", "sortPriority", "adjustmentFactor", "ltp", "ltp_pt", "ltp_dt", "pt_runner",
    "marketId", "id", "name"
]

markets_cols = [
    "bspMarket", "turnInPlayEnabled", "persistenceEnabled", "marketBaseRate",
    "eventId", "eventTypeId", "marketTime", "openDate", "numberOfWinners",
    "numberOfActiveRunners", "bettingType", "marketType", "status", "venue", "countryCode",
    "timezone", "eventName", "name", "pt", "suspendTime", "bspReconciled", "complete",
    "inPlay", "crossMatching", "runnersVoidable", "betDelay", "discountAllowed", "version", "marketId"
]

def write_current_month(month_str):
    with current_processing_file.open("w") as f:
        f.write(month_str)

def clear_current_month():
    if current_processing_file.exists():
        current_processing_file.unlink()

def log_failed_month(month_str):
    with failed_log.open("a") as f:
        f.write(month_str + "\n")

# On startup: detect if script was previously killed during processing a month
if current_processing_file.exists():
    stuck_month = current_processing_file.read_text().strip()
    if stuck_month:
        print(f"⚠️ Previous run was interrupted during {stuck_month}, logging as failed.")
        log_failed_month(stuck_month)
    clear_current_month()

# Load previously failed months from file (if exists)
if failed_log.exists():
    failed_months = set(failed_log.read_text().splitlines())
else:
    failed_months = set()

# Combine manually excluded months and failed months for skipping
manual_exclude = {"2017-Jul", "2017-Oct", "2021-Apr", "2021-Mar"}
skip_months = manual_exclude.union(failed_months)

for month_folder in sorted(input_dir.iterdir()):
    if not month_folder.is_dir():
        continue

    month_str = month_folder.name  # e.g., "2016-Dec"

    if month_str in skip_months:
        print(f"⏭️ Skipping {month_str} — excluded due to manual exclude or previous failure.")
        continue

    year, month = month_str.split("-")

    runners_filename = f"runners_{year}_{month}.parquet"
    markets_filename = f"markets_{year}_{month}.parquet"
    combined_filename = f"combined_{year}_{month}.parquet"

    runners_path = month_folder / runners_filename
    markets_path = month_folder / markets_filename
    combined_path = final_output_dir / combined_filename

    # Skip if combined output already exists
    if combined_path.exists():
        print(f"⏭️ Skipping {month_str} — already cleaned and combined.")
        continue

    cleaned_runners_path = temp_cleaned_dir / runners_filename
    cleaned_markets_path = temp_cleaned_dir / markets_filename

    try:
        # Mark current processing month
        write_current_month(month_str)

        # Load runners
        if not runners_path.exists():
            print(f"❌ Missing {runners_filename}")
            clear_current_month()
            continue
        print(f"🧼 Cleaning {runners_filename}")
        runners_df = pd.read_parquet(runners_path)
        runners_df = runners_df[[col for col in runners_cols if col in runners_df.columns]]
        # No dropna on ltp as requested
        runners_df.to_parquet(cleaned_runners_path, index=False)

        # Load markets
        if not markets_path.exists():
            print(f"❌ Missing {markets_filename}")
            clear_current_month()
            continue
        print(f"🧼 Cleaning {markets_filename}")
        markets_df = pd.read_parquet(markets_path)
        markets_df = markets_df[[col for col in markets_cols if col in markets_df.columns]]
        markets_df.to_parquet(cleaned_markets_path, index=False)

        # Merge
        print(f"\n🔗 Merging cleaned files for {month_str}")
        print(f"📊 Runners rows: {len(runners_df)}, columns: {list(runners_df.columns)}")
        print(f"📊 Markets rows: {len(markets_df)}, columns: {list(markets_df.columns)}")

        if "marketId" not in runners_df.columns or "marketId" not in markets_df.columns:
            print("❌ 'marketId' column missing from one of the DataFrames.")
            clear_current_month()
            continue

        combined_df = pd.merge(runners_df, markets_df, on="marketId", how="inner")
        print(f"✅ Merged rows: {len(combined_df)}")
        combined_df.to_parquet(combined_path, index=False)

        # Clean up temp files
        cleaned_runners_path.unlink(missing_ok=True)
        cleaned_markets_path.unlink(missing_ok=True)

        # Clear current processing after success
        clear_current_month()

    except Exception as e:
        print(f"❌ Failed to process {month_str} due to error: {e}")
        log_failed_month(month_str)
        clear_current_month()

print("\n✅ All monthly files cleaned and combined.")
