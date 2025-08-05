import dask.dataframe as dd
from pathlib import Path

def prepare_data_dask(runners_path: Path, markets_path: Path, output_path: Path):
    print("Loading runners data with Dask...")
    runners = dd.read_parquet(str(runners_path))
    print("Loading markets data with Dask...")
    markets = dd.read_parquet(str(markets_path))

    # Select market features to keep
    market_features = [
        'marketId', 'numberOfWinners', 'numberOfActiveRunners', 'marketTime', 'openDate',
        'marketBaseRate', 'bettingType', 'marketType', 'countryCode', 'venue',
        'inPlay', 'complete', 'bspMarket', 'bspReconciled', 'year'
    ]
    markets_sub = markets[market_features]

    print("Merging runners and markets with Dask...")
    df = runners.merge(markets_sub, on='marketId', how='left')

    # Create target column (similar as before)
    placed_statuses = ['winner', 'placed']
    df['target_place_or_win'] = df['status'].map(lambda x: 1 if str(x).lower() in placed_statuses else 0, meta=('status', 'int64'))

    # Datetime conversions (with Dask)
    for col in ['marketTime', 'openDate']:
        df[col] = dd.to_datetime(df[col], errors='coerce')

    # Extract hour from marketTime
    df['market_hour'] = df['marketTime'].dt.hour.fillna(-1).astype('int64')

    # Implied prob from bspMarket
    df['implied_prob'] = 1 / df['bspMarket'].replace(0, None)
    df['implied_prob'] = df['implied_prob'].fillna(0)

    categorical_cols = ['countryCode', 'venue', 'bettingType', 'marketType']

    # Tell Dask to categorize columns first so categories are known globally
    df = df.categorize(columns=categorical_cols)

    # Then replace with category codes
    for col in categorical_cols:
        df[col] = df[col].cat.codes

    # Fill numeric NA with zeros
    numeric_cols = ['numberOfWinners', 'numberOfActiveRunners', 'marketBaseRate', 'inPlay', 'complete', 'bspReconciled', 'market_hour', 'implied_prob']
    for col in numeric_cols:
        df[col] = df[col].fillna(0)

    # Features list (add runner features if present)
    feature_cols = [
        'numberOfWinners', 'numberOfActiveRunners', 'marketBaseRate', 'countryCode',
        'venue', 'bettingType', 'marketType', 'inPlay', 'complete', 'bspReconciled',
        'market_hour', 'implied_prob'
    ]
    runner_features = ['runner_win_percent', 'runner_avg_sp', 'runner_prev_places']
    feature_cols += [c for c in runner_features if c in df.columns]

    # Select features + target
    final_cols = feature_cols + ['target_place_or_win']
    df_final = df[final_cols]

    print("Writing out to parquet...")
    df_final.to_parquet(str(output_path), write_index=False)
    print("Done.")

if __name__ == "__main__":
    prepare_data_dask(
        Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/processed/horseracing_cleaned_split_by_year/runners_train_2019_23.parquet"),
        Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/processed/horseracing_cleaned_split_by_year/markets_train_2019_23.parquet"),
        Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/processed/prepared_horse_data_2019_23_dask.parquet")
    )
