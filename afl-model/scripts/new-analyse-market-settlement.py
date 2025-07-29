import pandas as pd

def analyze_market_settlement(markets_path):
    # Load the markets parquet data
    markets_df = pd.read_parquet(markets_path)
    
    print(f"Total rows in markets data: {len(markets_df)}")
    print(f"Total unique marketIds: {markets_df['marketId'].nunique()}\n")
    
    # Check for multiple records per marketId
    counts = markets_df['marketId'].value_counts()
    multiple_records = counts[counts > 1]
    print(f"Number of marketIds with multiple records: {len(multiple_records)}")
    print(f"Example marketIds with multiple records (count of snapshots):\n{multiple_records.head()}\n")
    
    # Filter markets where settledTime is not null
    settled_markets = markets_df[markets_df['settledTime'].notna()]
    print(f"Markets with non-null settledTime: {len(settled_markets)}")
    print(f"Unique marketIds with settledTime: {settled_markets['marketId'].nunique()}\n")
    
    # Distribution of status values
    print("Market status value counts:")
    print(markets_df['status'].value_counts())
    print()
    
    # Convert datetime columns to pandas datetime type if not already
    markets_df['marketTime'] = pd.to_datetime(markets_df['marketTime'])
    markets_df['settledTime'] = pd.to_datetime(markets_df['settledTime'], errors='coerce')  # coerce errors to NaT
    
    # Calculate time difference between settlement and marketTime (only for settled markets)
    settled_markets = markets_df[markets_df['settledTime'].notna()].copy()
    settled_markets['time_to_settlement'] = settled_markets['settledTime'] - settled_markets['marketTime']
    
    print("Time to settlement (for markets with settledTime):")
    print(settled_markets['time_to_settlement'].describe())
    
    # Optional: show some examples where marketTime is after settledTime (data error?)
    anomalies = settled_markets[settled_markets['marketTime'] > settled_markets['settledTime']]
    if not anomalies.empty:
        print("\nWarning: Found records where marketTime is after settledTime (possible data issue):")
        print(anomalies[['marketId', 'marketTime', 'settledTime']].head())
    else:
        print("\nNo records found where marketTime is after settledTime.")
    
if __name__ == "__main__":
    # Replace with your path
    markets_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/combined/markets.parquet"
    analyze_market_settlement(markets_path)