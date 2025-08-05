import pandas as pd
import pyarrow.parquet as pq
import gc
import time
from pathlib import Path
import psutil
import os
from datetime import datetime

def print_memory_usage(label=""):
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 * 1024)
    print(f"[{time.strftime('%H:%M:%S')}] Memory usage {label}: {mem:.2f} MB")

# --- Paths ---
input_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_month")
temp_cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month/tmp")
final_output_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")
chunk_output_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month/merged_chunks_2021_May")

temp_cleaned_dir.mkdir(parents=True, exist_ok=True)
final_output_dir.mkdir(parents=True, exist_ok=True)
chunk_output_dir.mkdir(parents=True, exist_ok=True)

# --- Files for 2021-May ---
year = "2021"
month = "May"
month_str = f"{year}-{month}"

runners_file = f"runners_{year}_{month}.parquet"
markets_file = f"markets_{year}_{month}.parquet"
combined_file = f"combined_{year}_{month}.parquet"

runners_path = input_dir / month_str / runners_file
markets_path = input_dir / month_str / markets_file

cleaned_runners_path = temp_cleaned_dir / runners_file
cleaned_markets_path = temp_cleaned_dir / markets_file

output_file = final_output_dir / combined_file

# Columns to keep during cleaning
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

try:
    print(f"[{time.strftime('%H:%M:%S')}] Starting cleaning runners parquet")
    runners_df = pd.read_parquet(runners_path)
    runners_df = runners_df[[col for col in runners_cols if col in runners_df.columns]]
    runners_df.to_parquet(cleaned_runners_path, index=False)
    print(f"[{time.strftime('%H:%M:%S')}] Cleaned runners saved to {cleaned_runners_path}")
    print_memory_usage("after cleaning runners")

    print(f"[{time.strftime('%H:%M:%S')}] Starting cleaning markets parquet")
    markets_df = pd.read_parquet(markets_path)
    markets_df = markets_df[[col for col in markets_cols if col in markets_df.columns]]
    markets_df.to_parquet(cleaned_markets_path, index=False)
    print(f"[{time.strftime('%H:%M:%S')}] Cleaned markets saved to {cleaned_markets_path}")
    print_memory_usage("after cleaning markets")

    # Reload cleaned data for merging
    runners_df = pd.read_parquet(cleaned_runners_path)
    markets_df = pd.read_parquet(cleaned_markets_path)

    # Clean marketId columns for merge
    runners_df['marketId'] = runners_df['marketId'].astype(str).str.strip()
    markets_df['marketId'] = markets_df['marketId'].astype(str).str.strip()

    print("Unique marketIds in runners:", runners_df['marketId'].nunique())
    print("Unique marketIds in markets:", markets_df['marketId'].nunique())

    print(f"[{time.strftime('%H:%M:%S')}] Starting chunked merge")
    chunk_size = 500_000  # adjust chunk size as needed
    chunk_files = []

    for i in range(0, len(markets_df), chunk_size):
        chunk = markets_df.iloc[i:i+chunk_size].copy()
        market_ids = chunk['marketId'].unique()
        runners_chunk = runners_df[runners_df['marketId'].isin(market_ids)]

        merged_chunk = pd.merge(runners_chunk, chunk, on='marketId', how='inner')

        chunk_file = chunk_output_dir / f"merged_chunk_{i//chunk_size}.parquet"
        merged_chunk.to_parquet(chunk_file)
        chunk_files.append(chunk_file)

        print_memory_usage(f"after merging chunk {i//chunk_size}")
        del chunk, runners_chunk, merged_chunk
        gc.collect()

    print(f"[{time.strftime('%H:%M:%S')}] Chunked merge complete, combining chunks")

    # Load and concatenate all chunks
    merged_chunks = [pd.read_parquet(f) for f in chunk_files]
    merged_all = pd.concat(merged_chunks, ignore_index=True)
    print_memory_usage("after concatenating all chunks")

    # Save final combined parquet
    merged_all.to_parquet(output_file)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Final merged file written to: {output_file}")
    print_memory_usage("after saving final parquet")

    # Cleanup temp files and chunk files
    cleaned_runners_path.unlink(missing_ok=True)
    cleaned_markets_path.unlink(missing_ok=True)
    for f in chunk_files:
        f.unlink()

    del runners_df, markets_df, merged_all
    gc.collect()

    print(f"[{time.strftime('%H:%M:%S')}] Done.")

except Exception as e:
    print(f"❌ Failed processing {month_str}: {e}")
