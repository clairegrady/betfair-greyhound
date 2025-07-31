import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split

# File paths
runners_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_split_by_year/runners_train_2019_23.parquet"
markets_path = "/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/processed/horseracing_cleaned_split_by_year/markets_train_2019_23.parquet"

# 1. Load data
runners_df = pd.read_parquet(runners_path)
markets_df = pd.read_parquet(markets_path)

# 2. Merge on marketId (adjust keys if needed)
df = pd.merge(runners_df, markets_df, on="marketId", suffixes=('_runner', '_market'))

# 3. Create binary target: 1 if WINNER or PLACED, else 0
df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)

# 4. Define features to drop - remove columns that leak target or are non-informative
features_to_drop = [
    'status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt',
    'target_place_or_win'  # will separate out target later
]

# 5. Prepare features X and target y
X = df.drop(columns=features_to_drop, errors='ignore')
y = df['target_place_or_win']

# 6. Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 7. Train XGBoost model
model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    use_label_encoder=False,
    eval_metric='logloss'
)
model.fit(X_train, y_train)

# 8. SHAP explainer on test data
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# 9. Summary plot
plt.figure()
shap.summary_plot(shap_values, X_test, show=False)
plt.savefig("shap_summary_plot.png")
plt.close()

# 10. Dependence plots saved for each feature
for feature in X_test.columns:
    plt.figure()
    shap.dependence_plot(feature, shap_values, X_test, show=False)
    plt.savefig(f"shap_dependence_{feature}.png")
    plt.close()

print("SHAP plots saved successfully.")
