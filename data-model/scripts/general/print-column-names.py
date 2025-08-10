import pandas as pd

# Replace this path with your actual file path
file_path1 = '/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_day/combined_2016_Dec_1.parquet'
file_path2 = '/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_day/combined_2016_Dec_5.parquet'

# Load the data
df1 = pd.read_parquet(file_path1)
df2 = pd.read_parquet(file_path2)

# Print all column names in the DataFrame
print("Columns in the market dataset:")
print(df1.columns.tolist())
print("Columns in the runner dataset:")
print(df2.columns.tolist())
