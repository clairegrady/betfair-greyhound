import pandas as pd
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster
from xgboost.dask import DaskXGBClassifier
from dask.diagnostics import ProgressBar
from pathlib import Path

def load_combined_data(base_path: Path, filename: str) -> dd.DataFrame:
    all_dfs = []
    for year_dir in sorted(base_path.iterdir()):
        file_path = year_dir / filename
        if file_path.exists():
            df = dd.read_parquet(file_path)
            df["year"] = int(year_dir.name)
            all_dfs.append(df)
    return dd.concat(all_dfs)

def train_model_for_year(df: dd.DataFrame, year: int, client: Client) -> None:
    print(f"\nTraining model for year {year}...")

    # Filter for target year
    ddf = df[df['year'] == year]

    # Sample 30% of data to reduce memory load
    ddf = ddf.sample(frac=0.3, random_state=42)

    # Persist to memory for efficiency
    ddf = ddf.persist()

    # Define features
    feature_columns = [
        'day', 'numberOfRunners', 'marketStartTime_unix', 'marketStartTime_unix_sin', 
        'marketStartTime_unix_cos', 'countryCode_AU', 'countryCode_GB', 'venue_encoded',
        'runner_win_percent', 'runner_avg_sp', 'runner_prev_places'
    ]

    # Ensure required columns exist
    missing = [col for col in feature_columns + ['target_place_or_win'] if col not in ddf.columns]
    if missing:
        raise ValueError(f"Missing columns in data for year {year}: {missing}")

    X_ddf = ddf[feature_columns]
    y_ddf = ddf["target_place_or_win"]

    # Define a small model for testing
    model = DaskXGBClassifier(
        n_estimators=50,
        max_depth=4,
        learning_rate=0.2,
        eval_metric="logloss",
        tree_method="hist"
    )
    model.client = client

    with ProgressBar():
        model.fit(X_ddf, y_ddf)

    print(f"✅ Model training complete for year {year}")

def main():
    # Setup Dask cluster with limited memory per worker
    cluster = LocalCluster(
        n_workers=2,
        threads_per_worker=1,
        memory_limit='4GB'
    )
    client = Client(cluster)

    print("🖥️ Dask cluster created")

    # Base directory
    base_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_year")
    filename = "combined.parquet"

    print("📂 Loading data...")
    combined_ddf = load_combined_data(base_path, filename)

    # Train models for each year
    for year in range(2016, 2026):
        try:
            train_model_for_year(combined_ddf, year, client)
        except Exception as e:
            print(f"⚠️ Failed to train model for year {year}: {e}")

    print("🎉 All done!")

if __name__ == "__main__":
    main()
