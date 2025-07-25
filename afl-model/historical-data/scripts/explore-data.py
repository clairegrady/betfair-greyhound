import fastparquet

parquet_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/runner_level_data.parquet"

try:
    pf = fastparquet.ParquetFile(parquet_path)
    print("Schema:")
    print(pf.schema)
    print("\nFirst 5 rows:")
    print(pf.head(5))
except Exception as e:
    print(f"Failed to read parquet file: {e}")
