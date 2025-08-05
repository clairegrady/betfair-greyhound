import pandas as pd
from pathlib import Path

# Define input/output directories
input_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_month")
temp_cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month/tmp")
final_output_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")
failed_log = Path("failed_months.txt")
current_processing_file = Path("currently_processing.txt")

temp_cleaned_dir.mkdir(parents=True, exist_ok=True)
final_output_dir.mkdir(parents=True, exist_ok=True)

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

# Resume detection
if current_processing_file.exists():
    stuck_month = current_processing_file.read_text().strip()
    if stuck_month:
        print(f"⚠️ Previous run was interrupted during {stuck_month}, logging as failed.")
        log_failed_month(stuck_month)
    clear_current_month()

# Skip failed or manually excluded months
failed_months = set(failed_log.read_text().splitlines()) if failed_log.exists() else set()
manual_exclude = {"2017-Jul", "2017-Oct", "2021-Apr", "2021-Mar"}
skip_months = manual_exclude.union(failed_months)

# Main loop
for month_folder in sorted(input_dir.iterdir()):
    if not month_folder.is_dir():
        continue

    month_str = month_folder.name
    if month_str in skip_months:
        print(f"⏭️ Skipping {month_str} — excluded.")
        continue

    year, month = month_str.split("-")
    runners_filename = f"runners_{year}_{month}.parquet"
    markets_filename = f"markets_{year}_{month}.parquet"
    combined_filename = f"combined_{year}_{month}.parquet"

    runners_path = month_folder / runners_filename
    markets_path = month_folder / markets_filename
    combined_path = final_output_dir / combined_filename

    if combined_path.exists():
        print(f"⏭️ Skipping {month_str} — already cleaned and combined.")
        continue

    if not runners_path.exists() or not markets_path.exists():
        print(f"⚠️ Missing runners or markets file for {month_str}, skipping.")
        continue

    try:
        write_current_month(month_str)

        print(f"🧼 Cleaning {runners_filename}")
        runners_df = pd.read_parquet(runners_path)
        runners_df = runners_df[[col for col in runners_cols if col in runners_df.columns]]
        runners_df['marketId'] = runners_df['marketId'].astype(str).str.strip()
        runners_df.to_parquet(temp_cleaned_dir / runners_filename, index=False)

        print(f"🧼 Cleaning {markets_filename}")
        markets_df = pd.read_parquet(markets_path)
        markets_df = markets_df[[col for col in markets_cols if col in markets_df.columns]]
        markets_df['marketId'] = markets_df['marketId'].astype(str).str.strip()
        markets_df.to_parquet(temp_cleaned_dir / markets_filename, index=False)

        print(f"\n🔗 Merging cleaned files for {month_str}")
        combined_df = pd.merge(runners_df, markets_df, on="marketId", how="inner")
        print(f"✅ Merged rows: {len(combined_df)}")
        combined_df.to_parquet(combined_path, index=False)

        # Cleanup
        (temp_cleaned_dir / runners_filename).unlink(missing_ok=True)
        (temp_cleaned_dir / markets_filename).unlink(missing_ok=True)
        clear_current_month()

    except Exception as e:
        print(f"❌ Failed to process {month_str} due to error: {e}")
        log_failed_month(month_str)
        clear_current_month()

print("\n✅ All monthly files cleaned and combined.")
