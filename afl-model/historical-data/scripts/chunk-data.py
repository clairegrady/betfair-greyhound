import pandas as pd
from pathlib import Path
import pyarrow.parquet as pq

def read_parquet_with_larger_limits(path: Path) -> pd.DataFrame:
    table = pq.read_table(
        path,
        thrift_string_size_limit=2**31 - 1,
        thrift_container_size_limit=2**31 - 1
    )
    return table.to_pandas()

def merge_runner_and_market_data(runner_path: Path, market_path: Path, output_path: Path):
    runner_df = read_parquet_with_larger_limits(runner_path)
    market_df = read_parquet_with_larger_limits(market_path)

    print(f"Runner-level records: {len(runner_df)}")
    print(f"Market-level records: {len(market_df)}")

    merged_df = pd.merge(runner_df, market_df, on=["marketId", "eventId"], how="left")

    print(f"Merged records: {len(merged_df)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_parquet(output_path, index=False)
    print(f"Saved merged data to {output_path}")

def main():
    runner_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/runner_level_data.parquet")
    market_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/selected_afl_features.parquet")
    output_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/selected_features.parquet")
    merge_runner_and_market_data(runner_path, market_path, output_path)

if __name__ == "__main__":
    main()
