import json
import pandas as pd
from pathlib import Path
import time
import bz2  # To handle .bz2 compressed files if your JSONL are inside them
import tarfile  # To handle .tar.bz2 archives if your JSONL are inside them

def extract_event_type_id(obj):
    """
    Extracts the eventTypeId from a Betfair stream API JSON object.
    """
    if obj.get("op") == "mcm":
        # Check 'mc' (market changes) list; it can sometimes be empty or missing
        if "mc" in obj and obj["mc"]:
            # Iterate through markets as marketDefinition might be in any of them
            for market in obj["mc"]:
                market_def = market.get("marketDefinition", {})
                event_type_id = market_def.get("eventTypeId")
                if event_type_id is not None:
                    return str(event_type_id)
    return None

def process_jsonl_files(jsonl_dir: Path, afl_event_type_id="4339"):
    """
    Processes JSONL files from Betfair historical data, extracting records
    for a specified AFL event type ID.

    Args:
        jsonl_dir (Path): The directory containing the JSONL files.
        afl_event_type_id (str): The string representation of the AFL event type ID.
                                 Defaults to "4339".

    Returns:
        pd.DataFrame: A DataFrame containing the extracted AFL market records.
    """
    if not jsonl_dir.exists():
        raise FileNotFoundError(f"Directory not found: {jsonl_dir}")

    # Look for .jsonl files, and also .bz2 or .tar.bz2 if they contain jsonl
    jsonl_files = []
    for ext in ["*.jsonl", "*.jsonl.bz2", "*.jsonl.gz", "*.tar.bz2"]:  # Added common compression extensions
        jsonl_files.extend(list(jsonl_dir.rglob(ext)))

    print(f"\n📁 Found {len(jsonl_files)} files (including compressed) in {jsonl_dir}")

    records = []
    skipped_lines = 0
    total_lines = 0
    start_time = time.time()

    for file_path in jsonl_files:
        print(f"\n📄 Processing file: {file_path.name}")

        # Determine how to open the file based on its extension
        open_func = open
        mode = "r"
        if file_path.suffix == ".bz2":
            open_func = bz2.open
            mode = "rt"  # read text mode for bz2
        elif file_path.suffix == ".gz":
            import gzip
            open_func = gzip.open
            mode = "rt"
        elif file_path.suffix == ".tar":  # Handles tar.bz2 and tar.gz
            # Skip .tar files - user should extract manually
            print(f"⚠️ Skipping .tar file for direct processing. Please extract JSONL files from {file_path.name} first if they are archived.")
            continue

        try:
            with open_func(file_path, mode) as f:
                for line_number, line in enumerate(f, 1):
                    total_lines += 1
                    try:
                        obj = json.loads(line)
                        event_type_id = extract_event_type_id(obj)

                        # Filter by AFL event type ID
                        if event_type_id != afl_event_type_id:
                            continue

                        # Extract data from each market in mc array
                        for market in obj.get("mc", []):
                            market_def = market.get("marketDefinition", {})

                            # Skip if marketDefinition is empty or missing essential IDs
                            if not market_def:
                                continue

                            open_date_str = market_def.get("openDate")
                            open_date_utc = pd.to_datetime(open_date_str).tz_convert('UTC').isoformat() if open_date_str else None

                            market_time_str = market_def.get("marketTime")
                            market_time_utc = pd.to_datetime(market_time_str).tz_convert('UTC').isoformat() if market_time_str else None

                            record = {
                                "marketId": market.get("id"),
                                "marketName": market_def.get("name"),
                                "totalMatched": obj.get("tv", market.get("tv", None)),
                                "eventId": market_def.get("eventId"),
                                "eventName": market_def.get("eventName"),
                                "countryCode": market_def.get("countryCode"),
                                "timezone": market_def.get("timezone"),
                                "venue": market_def.get("venue"),
                                "openDate_utc": open_date_utc,
                                "marketStartTime_utc": market_time_utc,
                            }

                            if record["marketId"] and record["eventId"]:
                                records.append(record)

                    except json.JSONDecodeError:
                        skipped_lines += 1
                    except Exception:
                        skipped_lines += 1

        except FileNotFoundError:
            print(f"❌ File not found or accessible: {file_path.name}")
        except Exception as e:
            print(f"❌ Could not open/process file {file_path.name}: {e}")

    elapsed = time.time() - start_time
    print(f"\n✅ Finished processing {len(jsonl_files)} files in {elapsed:.2f} seconds")
    print(f"📊 Total lines read: {total_lines}")
    print(f"✅ AFL records kept: {len(records)}")
    print(f"⚠️ Lines skipped (malformed/error): {skipped_lines}")

    return pd.DataFrame(records)

def main():
    jsonl_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/jsonl_files")
    output_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/selected_afl_features.parquet")

    if output_path.exists():
        print(f"⚠️ Output file {output_path} already exists. Skipping processing.")
        return

    df = process_jsonl_files(jsonl_dir, afl_event_type_id="4339")

    if not df.empty:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        print(f"\n💾 Saved {len(df)} records to {output_path}")
    else:
        print("\n⚠️ No AFL data saved — DataFrame is empty.")

if __name__ == "__main__":
    main()
