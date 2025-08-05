import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np

# Years to process
years = range(2019, 2024)  # 2019 to 2023 inclusive

# Base directory for yearly parquet files
base_dir = "/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_year/"

# File path templates
runners_path_template = base_dir + "runners_{}.parquet"
markets_path_template = base_dir + "markets_{}.parquet"

# Columns to drop from feature set
features_to_drop = ['status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt', 'target_place_or_win']

# Lists to collect all SHAP values and feature samples for aggregation
all_shap_values = []
all_X_samples = []

for year in years:
    print(f"Processing year {year}...")

    runners_path = runners_path_template.format(year)
    markets_path = markets_path_template.format(year)

    # Load parquet files for the year
    runners_df = pd.read_parquet(runners_path)
    markets_df = pd.read_parquet(markets_path)

    # Merge runners and markets on marketId
    df = pd.merge(runners_df, markets_df, on="marketId", suffixes=('_runner', '_market'))

    # Create binary target column
    df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)

    # Prepare feature matrix X and target vector y
    X = df.drop(columns=features_to_drop, errors='ignore')
    y = df['target_place_or_win']

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train XGBoost classifier
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)

    # SHAP explainer
    explainer = shap.TreeExplainer(model)

    # Sample from test data if large for faster SHAP calculation
    sample_size = 1000
    if len(X_test) > sample_size:
        X_test_sample = X_test.sample(sample_size, random_state=42)
    else:
        X_test_sample = X_test

    # Calculate SHAP values on sample
    shap_values = explainer.shap_values(X_test_sample)

    # Save per-year SHAP summary plot
    plt.figure()
    shap.summary_plot(shap_values, X_test_sample, show=False)
    plt.savefig(f"shap_summary_plot_{year}.png")
    plt.close()

    # Save per-year SHAP dependence plots for each feature
    for feature in X_test_sample.columns:
        plt.figure()
        shap.dependence_plot(feature, shap_values, X_test_sample, show=False)
        plt.savefig(f"shap_dependence_{feature}_{year}.png")
        plt.close()

    print(f"Saved SHAP plots for year {year}")

    # Collect for aggregation
    all_shap_values.append(shap_values)
    all_X_samples.append(X_test_sample)

print("Aggregating SHAP values across all years...")

# Concatenate all samples and SHAP values across years
X_all = pd.concat(all_X_samples, ignore_index=True)
shap_all = np.vstack(all_shap_values)

# Check matching shapes
assert X_all.shape[0] == shap_all.shape[0], "Mismatch between features and SHAP values sample counts!"

# Save aggregated SHAP summary plot over all years combined
plt.figure()
shap.summary_plot(shap_all, X_all, show=False)
plt.savefig("shap_summary_plot_aggregated_2019_2023.png")
plt.close()

print("Aggregated SHAP summary plot saved as shap_summary_plot_aggregated_2019_2023.png")
print("All done!")
