import pyarrow.parquet as pq
from pathlib import Path

def print_parquet_sample(file_path: Path, n=5):
    print(f"Reading from {file_path} with increased thrift size limits...")
    table = pq.read_table(
        file_path,
        thrift_string_size_limit=2**31 - 1,
        thrift_container_size_limit=2**31 - 1
    )
    # Convert only first n rows to pandas DataFrame
    df_sample = table.slice(0, n).to_pandas()
    print(f"Columns: {table.schema.names}")
    print(f"Showing first {n} rows:\n")
    print(df_sample)
    print("\n" + "="*40 + "\n")

def main():
    runner_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/runner_level_data.parquet")
    market_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/selected_afl_features.parquet")

    print_parquet_sample(runner_path)
    print_parquet_sample(market_path)

if __name__ == "__main__":
    main()
