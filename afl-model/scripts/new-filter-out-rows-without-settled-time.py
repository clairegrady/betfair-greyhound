import pandas as pd
from pathlib import Path

# Input files
market_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/combined/markets.parquet")
runner_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/combined/runners.parquet")

# Output files
market_final_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/final/market_filtered.parquet")
runner_final_path = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/final/runner_filtered.parquet")

# Load data
print("🔄 Loading data...")
markets_df = pd.read_parquet(market_path)
runners_df = pd.read_parquet(runner_path)

# Track original counts
original_market_rows = len(markets_df)
original_runner_rows = len(runners_df)

# Filter markets with valid settledTime
print("🧹 Filtering market data...")
filtered_markets = markets_df[
    (markets_df['settledTime'].notnull()) &
    (markets_df['settledTime'] >= markets_df['marketStartTime'])
]

# Get final snapshot per market (latest by timestamp)
final_markets = (
    filtered_markets
    .sort_values(by=['marketId', 'timestamp'], ascending=[True, False])  # type: ignore
    .drop_duplicates(subset='marketId', keep='first')
)


# Log market filtering
print(f"\n📊 Market Stats:")
print(f"• Original rows:       {original_market_rows:,}")
print(f"• After filtering:     {len(filtered_markets):,}")
print(f"• Final snapshots:     {len(final_markets):,}")
print(f"• Markets dropped:     {original_market_rows - len(final_markets):,}")

# Filter runners to only include those linked to remaining marketIds
print("🧹 Filtering runner data...")
final_runners = runners_df[runners_df['marketId'].isin(final_markets['marketId'])]

# Log runner filtering
print(f"\n📊 Runner Stats:")
print(f"• Original rows:       {original_runner_rows:,}")
print(f"• After filtering:     {len(final_runners):,}")
print(f"• Runners dropped:     {original_runner_rows - len(final_runners):,}")

# Save filtered data
print("\n💾 Saving filtered parquet files...")
final_markets.to_parquet(market_final_path, index=False)
final_runners.to_parquet(runner_final_path, index=False)

print("✅ Done!")
