import json
from pathlib import Path

def load_missing_pairs_from_parquet(parquet_path):
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    missing_df = df[df['lastTradedPrice'].isnull()]
    # Return list of tuples (marketId, runnerId)
    return list(missing_df[['marketId', 'runnerId']].itertuples(index=False, name=None))

def check_pairs_in_json_files(missing_pairs, json_dir):
    found_pairs = set()
    missing_pairs = set(missing_pairs)

    # Recursively iterate all files under json_dir
    for file in json_dir.rglob('*'):
        if not file.is_file():
            continue

        with file.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get('op') != 'mcm':
                    continue
                for market in obj.get('mc', []):
                    market_id = market.get('id')
                    for rc in market.get('rc', []):
                        runner_id = rc.get('id')
                        ltp = rc.get('ltp')
                        if (market_id, runner_id) in missing_pairs and ltp is not None:
                            found_pairs.add((market_id, runner_id))

                # Early exit optimization if all found
                if found_pairs == missing_pairs:
                    return found_pairs, missing_pairs - found_pairs

    return found_pairs, missing_pairs - found_pairs

if __name__ == '__main__':
    parquet_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/combined/runners.parquet")
    json_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/extracted/BASIC/decompressed_files")

    missing_pairs = load_missing_pairs_from_parquet(parquet_path)
    print(f"Checking {len(missing_pairs)} missing pairs against all JSON files in {json_dir}...")

    found, not_found = check_pairs_in_json_files(missing_pairs, json_dir)

    print(f"LTP found for {len(found)} missing pairs")
    print(f"LTP not found for {len(not_found)} missing pairs")

    if not_found:
        print("Some missing pairs never found in the scanned files:")
        for market_id, runner_id in list(not_found)[:20]:  # show first 20
            print(f"Market {market_id}, Runner {runner_id}")

    print("Done.")
