import json
import pandas as pd
from pathlib import Path
import time
import pyarrow.parquet as pq
import pyarrow as pa

def extract_event_type_id(obj, event_type_id="4339"):  # Greyhounds
    if obj.get("op") == "mcm":
        for market in obj.get("mc", []):
            market_def = market.get("marketDefinition", {})
            if str(market_def.get("eventTypeId")) == event_type_id:
                return event_type_id
    return None

def extract_runner_level_data_from_file(file_path: Path, event_type_id="4339"):
    runner_records = []
    with open(file_path, "r") as f:
        for line_number, line in enumerate(f, 1):
            try:
                obj = json.loads(line)
                if extract_event_type_id(obj, event_type_id) != event_type_id:
                    continue

                for market in obj.get("mc", []):
                    market_def = market.get("marketDefinition", {})
                    if str(market_def.get("eventTypeId")) != event_type_id:
                        continue

                    for runner in market_def.get("runners", []):
                        runner_record = {
                            "marketId": market.get("id"),
                            "eventId": market_def.get("eventId"),
                            "marketStartTime": market_def.get("marketTime"),
                            "marketName": market_def.get("name"),
                            "runnerId": runner.get("id"),
                            "runnerName": runner.get("name"),
                            "status": runner.get("status"),
                            "bsp": runner.get("bsp"),
                            "handicap": runner.get("hc"),
                            "adjustmentFactor": runner.get("adjustmentFactor"),
                            "removalDate": runner.get("removalDate"),
                        }
                        if runner_record["runnerId"] and runner_record["runnerName"]:
                            runner_records.append(runner_record)
            except json.JSONDecodeError:
                print(f"⚠️ Skipping malformed JSON line {line_number} in {file_path.name}")
            except Exception as e:
                print(f"❌ Error on line {line_number} in {file_path.name}: {e}")
    return runner_records
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

def combine_parquet_chunks_recursive(chunk_root_dir: Path, output_path: Path):
    chunk_files = list(chunk_root_dir.rglob("*.parquet"))
    if not chunk_files:
        print("⚠️ No .parquet chunk files found.")
        return

    print(f"\n📦 Found {len(chunk_files)} chunk files to combine...")

    # Define a consistent schema
    expected_schema = pa.schema([
        ("marketId", pa.string()),
        ("eventId", pa.string()),
        ("marketStartTime", pa.string()),
        ("marketName", pa.string()),
        ("runnerId", pa.int64()),
        ("runnerName", pa.string()),
        ("status", pa.string()),
        ("bsp", pa.float64()),
        ("handicap", pa.null()),
        ("adjustmentFactor", pa.null()),
        ("removalDate", pa.string()),
    ])

    writer = None
    total_rows = 0

    for i, file in enumerate(chunk_files, 1):
        print(f"📄 [{i}/{len(chunk_files)}] Adding {file.relative_to(chunk_root_dir)}")

        try:
            table = pq.read_table(file)

            # Force schema match (e.g., for nullable vs non-nullable string mismatch)
            table = table.cast(expected_schema, safe=False)

            if writer is None:
                writer = pq.ParquetWriter(output_path, expected_schema)

            writer.write_table(table)
            total_rows += table.num_rows

        except Exception as e:
            print(f"❌ Skipping {file.name}: {e}")

    if writer:
        writer.close()
        print(f"\n✅ Combined {total_rows} rows into {output_path}")

def main():
    chunk_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/runner_level_chunks")
    final_output = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/runner_level_data.parquet")

    combine_parquet_chunks_recursive(chunk_dir, final_output)

if __name__ == "__main__":
    main()
