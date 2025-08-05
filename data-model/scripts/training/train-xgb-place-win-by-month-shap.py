import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from pathlib import Path

# Directory with combined monthly parquet files
combined_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_month")

for combined_file in sorted(combined_dir.glob("combined_*.parquet")):
    combined_filename = combined_file.name  # e.g. "combined_2016_Dec.parquet"
    month_year = combined_file.stem.replace("combined_", "")  # e.g. "2016_Dec"
    print(f"\nProcessing file: {combined_filename}")

    # 1. Load data
    df = pd.read_parquet(combined_file)

    # 2. Create binary target: 1 if WINNER or PLACED, else 0
    df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)

    # 3. Define features to drop - remove columns that leak target or are non-informative
    features_to_drop = [
        'status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt',
        'target_place_or_win'  # target separate later
    ]

    # 4. Prepare features X and target y
    X = df.drop(columns=features_to_drop, errors='ignore')
    y = df['target_place_or_win']

    # 5. Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 6. Train XGBoost model
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)

    # 7. SHAP explainer on test data
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    # 8. Summary plot
    plt.figure()
    shap.summary_plot(shap_values, X_test, show=False)
    plt.savefig(f"shap_summary_plot_{month_year}.png")
    plt.close()

    # 9. Dependence plots saved for each feature
    for feature in X_test.columns:
        plt.figure()
        shap.dependence_plot(feature, shap_values, X_test, show=False)
        plt.savefig(f"shap_dependence_{feature}_{month_year}.png")
        plt.close()

print("✅ SHAP plots saved successfully for all monthly files.")
