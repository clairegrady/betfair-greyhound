import numbers
import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np
from pathlib import Path
import gc
import s3fs
import datetime
import argparse

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

# Print features that will be used for training (after dropping features_to_drop)
def print_training_features_example():
    # Try to load a sample file to show columns, or print a message if not possible
    import glob
    import os
    try:
        # Try to find a local or S3 parquet file
        local_files = glob.glob("*.parquet")
        if local_files:
            df = pd.read_parquet(local_files[0])
        else:
            print("No local parquet file found to show feature columns.")
            return
        X = df.drop(columns=features_to_drop, errors='ignore')
        print("\n[INFO] Example features used for training (after dropping features_to_drop):")
        print(list(X.columns))
    except Exception as e:
        print(f"[INFO] Could not print training features example: {e}")

print_training_features_example()


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
    # Use 'status_x' as main status column, fallback to 'status_y' if needed
    if 'status_x' in df.columns:
        df['status'] = df['status_x']
    elif 'status_y' in df.columns:
        df['status'] = df['status_y']
    else:
        raise KeyError("Missing both 'status_x' and 'status_y' columns")
    df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)
    X = df.drop(columns=features_to_drop, errors='ignore')
    # Remove all columns with zero variance (all values the same) or all NaN
    zero_var_cols = [col for col in X.columns if X[col].nunique(dropna=False) <= 1]
    X = X.drop(columns=zero_var_cols, errors='ignore')
    # Remove all columns with all zero SHAP importance (after model fit)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=str, required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, required=True, help='End date YYYY-MM-DD')
    args = parser.parse_args()
    start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
    delta = datetime.timedelta(days=1)
    expected_s3_paths = []
    date = start_date
    while date <= end_date:
        s3_name = f"combined_{date.year}_{date.strftime('%b')}_{date.day}.parquet"
        s3_path = f"{s3_bucket}/{s3_daily_prefix}{s3_name}"
        expected_s3_paths.append(s3_path)
        date += delta
    existing_s3_paths = [p for p in expected_s3_paths if s3.exists(p)]
    print(f"Found {len(existing_s3_paths)} S3 files to process out of {len(expected_s3_paths)} expected.")
    # --- Monthly checkpointing ---
    from collections import defaultdict
    import calendar

    # Helper to get (year, month) from s3_path
    def get_year_month_from_path(s3_path):
        # expects .../combined_YYYY_Mmm_DD.parquet
        fname = s3_path.split('/')[-1]
        parts = fname.replace('combined_', '').replace('.parquet', '').split('_')
        year = parts[0]
        month = parts[1]
        return year, month

    # Group s3 paths by (year, month)
    month_groups = defaultdict(list)
    for p in existing_s3_paths:
        year, month = get_year_month_from_path(p)
        month_groups[(year, month)].append(p)

    for (year, month) in sorted(month_groups.keys()):
        print(f"\nProcessing {calendar.month_name[list(calendar.month_abbr).index(month)]} {year}...")
        results = []
        for p in month_groups[(year, month)]:
            res = process_file(p)
            if res is not None:
                results.append(res)
        if not results:
            print(f"No results for {month} {year}, skipping aggregation.")
            continue
        try:
            X_month = pd.concat([r['X_test_sample'] for r in results], ignore_index=True)
            shap_month = np.vstack([r['shap_values'] for r in results])
            assert X_month.shape[0] == shap_month.shape[0], f"Mismatch for {year}-{month}"
            # Save SHAP summary plot
            plot_path = shap_plot_dir / f"shap_summary_plot_{year}_{month}.png"
            plt.figure()
            shap.summary_plot(shap_month, X_month, show=False)
            plt.savefig(plot_path)
            plt.close()
            print(f"Saved SHAP summary plot for {year}-{month} at {plot_path}")
            # Save mean absolute SHAP values (feature importance) as CSV
            mean_abs_shap = np.abs(shap_month).mean(axis=0)
            feature_names = X_month.columns
            importance_df = pd.DataFrame({
                'feature': feature_names,
                'mean_abs_shap': mean_abs_shap
            }).sort_values('mean_abs_shap', ascending=False)
            csv_path = shap_plot_dir / f"shap_feature_importance_{year}_{month}.csv"
            importance_df.to_csv(csv_path, index=False)
            print(f"Saved SHAP feature importance CSV for {year}-{month} at {csv_path}")
            # Upload to S3 in a subfolder for each year/month
            s3_plot_path = f"{s3_bucket}/{s3_output_prefix}{year}/{month}/shap_summary_plot_{year}_{month}.png"
            s3_csv_path = f"{s3_bucket}/{s3_output_prefix}{year}/{month}/shap_feature_importance_{year}_{month}.csv"
            try:
                print(f"Uploading plot to S3: {s3_plot_path}")
                s3.put(plot_path.as_posix(), s3_plot_path)
                print(f"Plot uploaded successfully.")
            except Exception as e:
                print(f"❌ Failed to upload plot for {year}-{month} to S3: {e}")
                with skipped_log.open("a") as f:
                    f.write(f"UPLOAD_PLOT {year}-{month}: {e}\n")
            try:
                print(f"Uploading CSV to S3: {s3_csv_path}")
                s3.put(csv_path.as_posix(), s3_csv_path)
                print(f"CSV uploaded successfully.")
            except Exception as e:
                print(f"❌ Failed to upload CSV for {year}-{month} to S3: {e}")
                with skipped_log.open("a") as f:
                    f.write(f"UPLOAD_CSV {year}-{month}: {e}\n")
            print(f"Completed S3 upload for {year}-{month}.")
        except Exception as e:
            print(f"❌ Could not aggregate or plot for {year}-{month}: {e}")
            with skipped_log.open("a") as f:
                f.write(f"AGGREGATION {year}-{month}: {e}\n")
