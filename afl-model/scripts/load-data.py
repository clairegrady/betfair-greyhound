import os
import pandas as pd

# Directory where decompressed files are stored
data_dir = 'extracted_files/'  
loaded_data_dir = 'loaded_data/'

os.makedirs(loaded_data_dir, exist_ok=True)

# Load each file into pandas DataFrame
def load_data(file_path):
try:
if file_path.endswith('.json'):
df = pd.read_json(file_path, lines=True)  # use lines=True for JSONLines format
return df
elif file_path.endswith('.csv'):
df = pd.read_csv(file_path)
return df
except Exception as e:
print(f"Could not load {file_path}: {e}")

# Process all files
dataframes = []
for filename in os.listdir(data_dir):
file_path = os.path.join(data_dir, filename)
df = load_data(file_path)
if df is not None:
df.to_csv(os.path.join(loaded_data_dir, filename.replace('.json', '.csv').replace('.txt', '.csv')), index=False)
dataframes.append(df)
print(f"Loaded and saved: {filename}")

# Optionally combine all DataFrames into one
if dataframes:
combined_df = pd.concat(dataframes, ignore_index=True)
print(f"Combined DataFrame shape: {combined_df.shape}")
else:
print("No data loaded.")