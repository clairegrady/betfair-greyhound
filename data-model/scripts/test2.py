import pandas as pd
from pathlib import Path
import os
import psutil
import time
import gc

# --- Paths ---
input_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_month")
temp_cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month/tmp")
final_output_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")
failed_log = Path("failed_months.txt")
current_processing_file = Path("currently_processing.txt")

# --- Setup ---
temp_cleaned_dir.mkdir(parents=True, exist_ok=True)
final_output_dir.mkdir(parents=True, exist_ok=True)

runners_cols = ["status", "sortPriority", "adjustmentFactor", "ltp", "ltp_pt", "ltp_dt", "pt_runner", "marketId", "id", "name"]
markets_cols = ["bspMarket", "turnInPlayEnabled", "persistenceEnabled", "marketBaseRate", "eventId", "eventTypeId", "marketTime", "openDate", "numberOfWinners", "numberOfActiveRunners", "bettingType", "marketType", "status", "venue", "countryCode", "timezone", "eventName", "name", "pt", "suspendTime", "bspReconciled", "complete", "inPlay", "crossMatching", "runnersVoidable", "betDelay", "discountAllowed", "version", "marketId"]

def print_memory_usage(stage=""):
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024**2
    print(f"[{time.strftime('%H:%M:%S')}] Memory usage after {stage}: {mem_mb:.2f} MB")

def write_current_month(month_str):
    with current_processing_file.open("w") as f:
        f.write(month_str)

def clear_current_month():
    if current_processing_file.exists():
        current_processing_file.unlink()

def log_failed_month(month_str):
    with failed_log.open("a") as f:
        f.write(month_str + "\n")

# --- Process all available months ---
for month_folder in sorted(input_dir.iterdir()):
    if not month_folder.is_dir():
        continue

    month_str = month_folder.name
    print(f"\n📅 Processing {month_str}")

    try:
        year, month = month_str.split("-")
    except ValueError:
        print(f"⚠️ Skipping invalid folder name: {month_str}")
        continue

    runners_file = f"runners_{year}_{month}.parquet"
    markets_file = f"markets_{year}_{month}.parquet"
    combined_file = f"combined_{year}_{month}.parquet"
    combined_file_v2 = f"combined_{year}_{month}_v2.parquet"

    runners_path = month_folder / runners_file
    markets_path = month_folder / markets_file
    combined_path_v2 = final_output_dir / combined_file_v2

    if combined_path_v2.exists():
        print(f"⏭️ Skipping {month_str} — already processed.")
        continue

    cleaned_runners_path = temp_cleaned_dir / runners_file
    cleaned_markets_path = temp_cleaned_dir / markets_file

    try:
        write_current_month(month_str)

        print(f"🧼 Cleaning {runners_file}")
        runners_df = pd.read_parquet(runners_path)
        runners_df = runners_df[[col for col in runners_cols if col in runners_df.columns]]
        runners_df.to_parquet(cleaned_runners_path, index=False)

        print(f"🧼 Cleaning {markets_file}")
        markets_df = pd.read_parquet(markets_path)
        markets_df = markets_df[[col for col in markets_cols if col in markets_df.columns]]
        markets_df.to_parquet(cleaned_markets_path, index=False)

        print(f"🔗 Chunked merge for {month_str}")
        print_memory_usage("start")

        runners_df = pd.read_parquet(cleaned_runners_path)
        markets_df = pd.read_parquet(cleaned_markets_path)

        runners_df['marketId'] = runners_df['marketId'].astype(str).str.strip()
        markets_df['marketId'] = markets_df['marketId'].astype(str).str.strip()

        print("Unique marketIds in runners:", runners_df['marketId'].nunique())
        print("Unique marketIds in markets:", markets_df['marketId'].nunique())

        chunk_size = 1_000_000
        merged_chunks = []
        for i in range(0, len(runners_df), chunk_size):
            chunk = runners_df.iloc[i:i+chunk_size]
            merged_chunk = pd.merge(chunk, markets_df, on="marketId", how="inner")
            merged_chunks.append(merged_chunk)
            print_memory_usage(f"merging chunk {i//chunk_size}")
            del chunk, merged_chunk
            gc.collect()

        merged_all = pd.concat(merged_chunks, ignore_index=True)

        merged_all.to_parquet(combined_path_v2)
        print(f"✅ Saved combined parquet: {combined_path_v2}")

        del runners_df, markets_df, merged_all
        gc.collect()
        print_memory_usage("after cleanup")

        cleaned_runners_path.unlink(missing_ok=True)
        cleaned_markets_path.unlink(missing_ok=True)
        clear_current_month()

    except Exception as e:
        print(f"❌ Failed to process {month_str}: {e}")
        log_failed_month(month_str)
        clear_current_month()
