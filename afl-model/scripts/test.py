import pandas as pd

# Replace this path with your actual file path
file_path = '/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_combined_parquet/runners.parquet'

# Load the data
df = pd.read_parquet(file_path)

# Print all column names in the DataFrame
print("Columns in the dataset:")
print(df.columns.tolist())
