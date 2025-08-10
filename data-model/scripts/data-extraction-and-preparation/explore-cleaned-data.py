import pandas as pd
import matplotlib.pyplot as plt

def main():
    # Set paths to cleaned parquet files
    markets_path = "/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/processed/horseracing_cleaned_combined_parquet/markets.parquet"
    runners_path = "/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/processed/horseracing_cleaned_combined_parquet/runners.parquet"

    # Load data
    markets_df = pd.read_parquet(markets_path)
    runners_df = pd.read_parquet(runners_path)

    # Markets overview
    print("\n🔍 Markets Data Overview")
    print("Shape:", markets_df.shape)
    print("Columns (first 10):", markets_df.columns[:10].tolist())
    print("\nFirst 10 rows:\n", markets_df.head(10))
    print("\nSummary stats (first 10 columns):\n", markets_df.describe().iloc[:, :10])
    print("\nMissing values (first 10 columns):\n", markets_df.isna().sum().head(10))
    print("\n'marketType' value counts (top 10):\n", markets_df['marketType'].value_counts().head(10))

    # Runners overview
    print("\n🏇 Runners 'status' value counts (top 10):\n", runners_df['status'].value_counts().head(10))

    # Plot: numberOfWinners distribution
    markets_df['numberOfWinners'].hist(bins=20)
    plt.title("Distribution of numberOfWinners")
    plt.xlabel("numberOfWinners")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.show()

    # Runners price stats
    if 'lastTradedPrice' in runners_df.columns:
        print("\nRunners 'lastTradedPrice' stats:\n", runners_df['lastTradedPrice'].describe())
    else:
        print("\n⚠️ 'lastTradedPrice' column not found in runners data.")

    # Correlation matrix for numeric market features
    print("\n📊 Correlation matrix (markets_df numeric columns):\n", markets_df.select_dtypes(include=['float', 'int']).corr().round(2).head(10))

if __name__ == "__main__":
    main()
