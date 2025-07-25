import pandas as pd
from pathlib import Path

def split_data_by_year(input_dir: Path, output_dir: Path, date_col='openDate'):
    all_files = list(input_dir.glob("runner_chunk_*.parquet"))
    if not all_files:
        print(f"No chunk files found in {input_dir}")
        return

    print(f"Reading {len(all_files)} chunk files...")
    df = pd.concat((pd.read_parquet(f) for f in all_files), ignore_index=True)

    # Ensure date column is datetime
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])  # Drop rows where date parsing failed

    # Extract year
    df['year'] = df[date_col].dt.year

    # Define splits
    train_years = list(range(2017, 2023))     # 2017-2022 inclusive
    backtest_years = [2023, 2024]
    predict_years = [2025]

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter and save
    train_df = df[df['year'].isin(train_years)]
    backtest_df = df[df['year'].isin(backtest_years)]
    predict_df = df[df['year'].isin(predict_years)]

    train_path = output_dir / 'train.parquet'
    backtest_path = output_dir / 'backtest.parquet'
    predict_path = output_dir / 'predict.parquet'

    train_df.to_parquet(train_path, index=False)
    backtest_df.to_parquet(backtest_path, index=False)
    predict_df.to_parquet(predict_path, index=False)

    print(f"Saved training data: {len(train_df)} records to {train_path}")
    print(f"Saved backtesting data: {len(backtest_df)} records to {backtest_path}")
    print(f"Saved prediction data: {len(predict_df)} records to {predict_path}")

def main():
    input_dir = Path("/home/ec2-user/betfair/afl-model/historical-data/processed/runner_level_chunks")
    output_dir = input_dir.parent / "splits"
    split_data_by_year(input_dir, output_dir)

if __name__ == "__main__":
    main()
