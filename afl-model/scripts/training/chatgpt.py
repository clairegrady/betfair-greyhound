import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np
import gc

# Years to process
years = range(2019, 2024)

# Base directory
base_dir = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_parquet_by_year/"

# Path templates
runners_path_template = base_dir + "runners_{}.parquet"
markets_path_template = base_dir + "markets_{}.parquet"

# Features to drop
features_to_drop = ['status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt', 'target_place_or_win']

# Max rows to sample from test set
sample_size = 1000

# Number of top features for dependence plots
top_n_features = 5

for year in years:
    print(f"\nProcessing year {year}...")

    try:
        # Load data
        runners_df = pd.read_parquet(runners_path_template.format(year))
        markets_df = pd.read_parquet(markets_path_template.format(year))
        df = pd.merge(runners_df, markets_df, on="marketId", suffixes=('_runner', '_market'))

        # Create binary target
        df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)

        # Prepare features/target
        X = df.drop(columns=features_to_drop, errors='ignore')
        y = df['target_place_or_win']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train model
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        model.fit(X_train, y_train)

        # Sample test set
        X_sample = X_test.sample(n=min(sample_size, len(X_test)), random_state=42)

        # SHAP Explainer (TreeExplainer is okay for XGBoost)
        explainer = shap.Explainer(model, X_train)
        shap_values = explainer(X_sample)

        # Summary plot
        shap.plots.beeswarm(shap_values, show=False)
        plt.savefig(f"shap_summary_plot_{year}.png")
        plt.close()

        # Top N features by mean absolute SHAP value
        mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
        top_indices = np.argsort(mean_abs_shap)[-top_n_features:]
        top_features = [X_sample.columns[i] for i in top_indices]

        # Dependence plots
        for feature in top_features:
            shap.plots.scatter(shap_values[:, feature], color=shap_values, show=False)
            plt.savefig(f"shap_dependence_{feature}_{year}.png")
            plt.close()

        print(f"Saved SHAP plots for year {year}.")

    except Exception as e:
        print(f"Error processing year {year}: {e}")

    # Clean up to free memory
    plt.close('all')
    del df, X, y, X_train, X_test, y_train, y_test, model, explainer, shap_values, X_sample
    gc.collect()

print("\n✅ All done! SHAP plots saved per year.")
