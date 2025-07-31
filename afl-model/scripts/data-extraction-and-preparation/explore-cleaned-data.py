import pandas as pd
import matplotlib.pyplot as plt

def main():
    # Update these paths to your actual cleaned parquet files
    markets_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_combined_parquet/markets.parquet"
    runners_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_combined_parquet/runners.parquet"

    # Load data
    markets_df = pd.read_parquet(markets_path)
    runners_df = pd.read_parquet(runners_path)

    # Basic info and stats
    print("Markets data shape:", markets_df.shape)
    print("Markets columns:", markets_df.columns.tolist())
    print("\nMarkets first 5 rows:\n", markets_df.head())
    print("\nMarkets summary statistics:\n", markets_df.describe())
    print("\nMarkets missing values:\n", markets_df.isna().sum())
    print("\nMarkets 'marketType' value counts:\n", markets_df['marketType'].value_counts())

    print("\nRunners 'status' value counts:\n", runners_df['status'].value_counts())

    # Histogram of numberOfWinners
    markets_df['numberOfWinners'].hist()
    plt.title("Distribution of numberOfWinners")
    plt.xlabel("numberOfWinners")
    plt.ylabel("Frequency")
    plt.show()

    # Describe lastTradedPrice for runners
    print("\nRunners lastTradedPrice stats:\n", runners_df['lastTradedPrice'].describe())

    # Correlation matrix of numeric columns in markets_df
    numeric_cols = markets_df.select_dtypes(include=['float', 'int'])
    print("\nMarkets correlation matrix (numeric columns only):\n", numeric_cols.corr())


if __name__ == "__main__":
    main()
