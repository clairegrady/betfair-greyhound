import numbers
import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np
from pathlib import Path
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
import s3fs
import datetime

# Directory for SHAP plots (local output)
shap_plot_dir = Path("./models")
shap_plot_dir.mkdir(parents=True, exist_ok=True)

# S3 bucket and prefix for daily parquet files
s3_bucket = "betfair-clairegrady"
s3_daily_prefix = "betfair-historical-data/horseracing_cleaned_parquet_by_day/"
s3_output_prefix = "shap-feature-importance-2025/"
s3 = s3fs.S3FileSystem(anon=False)

features_to_drop = [
    'status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt', 'target_place_or_win',
    'name_x', 'marketBaseRate', 'marketTime', 'eventTypeId', 'numberOfActiveRunners', 'persistenceEnabled',
    'bettingType', 'status_y', 'countryCode', 'venue', 'timezone', 'eventName', 'pt', 'suspendTime',
    'bspReconciled', 'complete', 'inPlay', 'crossMatching', 'runnersVoidable', 'betDelay', 'discountAllowed'
]

sample_size = 5000  # SHAP sample size per day
skipped_log = Path("skipped_days.txt")


def process_file(s3_path):
    skipped_log = Path("skipped_days.txt")
    day_str = s3_path.split('/')[-1].replace("combined_", "").replace(".parquet", "")
    try:
        year = day_str.split('_')[0]
    except Exception:
        year = "unknown_year"
    yearly_plot_path = shap_plot_dir / f"shap_summary_plot_{year}.png"
    if yearly_plot_path.exists():
        return None
    print(f"\nProcessing file: {s3_path}")
    df = pd.read_parquet(f's3://{s3_path}', filesystem=s3)
    if 'status' not in df.columns:
        if 'status_x' in df.columns and 'status_y' in df.columns:
            df['status'] = df['status_x'].combine_first(df['status_y'])
        elif 'status_x' in df.columns:
            df['status'] = df['status_x']
        elif 'status_y' in df.columns:
            df['status'] = df['status_y']
        else:
            raise KeyError("Missing 'status', 'status_x', and 'status_y' columns")
    df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)
    X = df.drop(columns=features_to_drop, errors='ignore')
    y = df['target_place_or_win']
    for col in X.columns:
        try:
            col_data = X[col]
            types_in_col = set(type(x) for x in col_data.dropna())
            has_str = any(issubclass(t, str) for t in types_in_col)
            has_num = any(issubclass(t, numbers.Number) for t in types_in_col)
            if col_data.dtype == 'object' or (has_str and has_num):
                X[col] = X[col].astype(str).astype('category')
        except Exception as e:
            print(f"⚠️ Could not convert column {col} in {s3_path}: {e}")
            with skipped_log.open("a") as f:
                f.write(f"{s3_path} (column {col}): {e}\n")
            X = X.drop(columns=[col])
    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    except Exception as e:
        print(f"❌ Skipping {s3_path} due to train_test_split error: {e}")
        with skipped_log.open("a") as f:
            f.write(f"{s3_path} (train_test_split): {e}\n")
        return None
    try:
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric='logloss',
            enable_categorical=True
        )
        model.fit(X_train, y_train)
    except Exception as e:
        print(f"❌ Skipping {s3_path} due to XGBoost error: {e}")
        with skipped_log.open("a") as f:
            f.write(f"{s3_path} (XGBoost): {e}\n")
        return None
    try:
        explainer = shap.TreeExplainer(model)
        if len(X_test) > sample_size:
            X_test_sample = X_test.sample(sample_size, random_state=42)
        else:
            X_test_sample = X_test
        shap_values = explainer.shap_values(X_test_sample)
    except Exception as e:
        print(f"❌ Skipping {s3_path} due to SHAP error: {e}")
        with skipped_log.open("a") as f:
            f.write(f"{s3_path} (SHAP): {e}\n")
        return None
    gc.collect()
    return {
        'year': year,
        'shap_values': shap_values,
        'X_test_sample': X_test_sample
    }

# Generate all expected S3 paths for your date range
start_date = datetime.date(2016, 10, 1)
end_date = datetime.date(2025, 7, 31)
delta = datetime.timedelta(days=1)
expected_s3_paths = []
date = start_date
while date <= end_date:
    s3_name = f"combined_{date.year}_{date.strftime('%b')}_{date.day}.parquet"
    s3_path = f"{s3_bucket}/{s3_daily_prefix}{s3_name}"
    expected_s3_paths.append(s3_path)
    date += delta

# Only process files that exist in S3
existing_s3_paths = [p for p in expected_s3_paths if s3.exists(p)]
print(f"Found {len(existing_s3_paths)} S3 files to process out of {len(expected_s3_paths)} expected.")

# ThreadPoolExecutor parallel processing
results = []
max_workers = 4  # Adjust based on your EC2 memory/CPU
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_file, p) for p in existing_s3_paths]
    for fut in as_completed(futures):
        res = fut.result()
        if res is not None:
            results.append(res)

# Yearly SHAP aggregation and plotting
yearly_shap_values = {}
yearly_X_samples = {}
all_shap_values = []
all_X_samples = []
for res in results:
    year = res['year']
    shap_values = res['shap_values']
    X_test_sample = res['X_test_sample']
    if year not in yearly_shap_values:
        yearly_shap_values[year] = []
        yearly_X_samples[year] = []
    yearly_shap_values[year].append(shap_values)
    yearly_X_samples[year].append(X_test_sample)
    all_shap_values.append(shap_values)
    all_X_samples.append(X_test_sample)

print("\nAggregating SHAP values by year...")
for year in sorted(yearly_shap_values.keys()):
    try:
        X_year = pd.concat(yearly_X_samples[year], ignore_index=True)
        shap_year = np.vstack(yearly_shap_values[year])
        assert X_year.shape[0] == shap_year.shape[0], f"Mismatch for {year}"
        # Save SHAP summary plot
        plot_path = shap_plot_dir / f"shap_summary_plot_{year}.png"
        plt.figure()
        shap.summary_plot(shap_year, X_year, show=False)
        plt.savefig(plot_path)
        plt.close()
        print(f"Saved SHAP summary plot for {year}")
        # Save mean absolute SHAP values (feature importance) as CSV
        mean_abs_shap = np.abs(shap_year).mean(axis=0)
        feature_names = X_year.columns
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'mean_abs_shap': mean_abs_shap
        }).sort_values('mean_abs_shap', ascending=False)
        csv_path = shap_plot_dir / f"shap_feature_importance_{year}.csv"
        importance_df.to_csv(csv_path, index=False)
        print(f"Saved SHAP feature importance CSV for {year}")
        # Upload to S3 in a subfolder for each year
        s3_plot_path = f"{s3_bucket}/{s3_output_prefix}{year}/shap_summary_plot_{year}.png"
        s3_csv_path = f"{s3_bucket}/{s3_output_prefix}{year}/shap_feature_importance_{year}.csv"
        s3.put(plot_path.as_posix(), s3_plot_path)
        s3.put(csv_path.as_posix(), s3_csv_path)
        print(f"Uploaded SHAP plot and CSV for {year} to S3 subfolder {year}.")
    except Exception as e:
        print(f"❌ Could not aggregate or plot for {year}: {e}")
        with skipped_log.open("a") as f:
            f.write(f"AGGREGATION {year}: {e}\n")
