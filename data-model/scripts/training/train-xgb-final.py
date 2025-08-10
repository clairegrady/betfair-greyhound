import pandas as pd
import xgboost as xgb
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score, f1_score, classification_report
import numpy as np
import gc

# --- CONFIG ---
# Directory with cleaned daily parquet files
cleaned_dir = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_cleaned_parquet_by_day")

# Years for each split
train_years = set(str(y) for y in range(2016, 2024))  # 2016-2023 inclusive
backtest_years = set(["2023", "2024"])            # 2023-2024
predict_years = set(["2025"])                      # 2025

# Features to use (replace with your selected features after SHAP analysis)
selected_features = None  # e.g. ['feature1', 'feature2', ...]

# Columns to drop (if present)
features_to_drop = [
    'status', 'name_runner', 'name_market', 'id', 'marketId', 'ltp_dt', 'ltp_pt', 'target_place_or_win'
]

# --- LOAD DATA ---
def load_data(years):
    dfs = []
    for f in sorted(cleaned_dir.glob("combined_*.parquet")):
        # Extract year from filename (expects 'combined_YYYY_MMM_DD.parquet' or similar)
        parts = f.stem.split('_')
        if len(parts) < 2:
            continue
        year = parts[1]
        if year in years:
            df = pd.read_parquet(f)
            df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)
            dfs.append(df)
            del df
            gc.collect()
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    else:
        return pd.DataFrame()

print("Loading training data (2016-2023)...")
df_train = load_data(train_years)
print(f"Training rows: {len(df_train)}")

print("Loading backtest data (2023-2024)...")
df_backtest = load_data(backtest_years)
print(f"Backtest rows: {len(df_backtest)}")

print("Loading prediction data (2025)...")
df_predict = load_data(predict_years)
print(f"Prediction rows: {len(df_predict)}")

# --- FEATURE SELECTION ---
if selected_features is None:
    # Use all columns except drops if not specified
    selected_features = [c for c in df_train.columns if c not in features_to_drop + ['target_place_or_win']]

# --- PREPARE DATA ---
X_train = df_train[selected_features]
y_train = df_train['target_place_or_win']
X_back = df_backtest[selected_features]
y_back = df_backtest['target_place_or_win']
X_pred = df_predict[selected_features] if not df_predict.empty else None


del df_train, df_backtest, df_predict
gc.collect()

# --- TRAIN FINAL MODEL ---
print("Training final XGBoost model...")
model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    use_label_encoder=False,
    eval_metric='logloss',
    n_jobs=4
)
from sklearn.model_selection import cross_val_score
print("Performing 5-fold cross-validation on training set...")
cv_scores = cross_val_score(
    model,
    X_train,
    y_train,
    cv=5,
    scoring='roc_auc',
    n_jobs=1  # Set to 1 for lower memory usage; increase if you have more RAM/cores
)
print(f"5-fold CV ROC AUC scores: {cv_scores}")
print(f"Mean CV ROC AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

# Fit on full training set after CV
model.fit(X_train, y_train)

# --- BACKTEST ---
print("Evaluating on backtest set...")
y_pred = model.predict(X_back)
y_pred_proba = model.predict_proba(X_back)[:, 1]

print(classification_report(y_back, y_pred))
print(f"AUC: {roc_auc_score(y_back, y_pred_proba):.4f}")
print(f"Accuracy: {accuracy_score(y_back, y_pred):.4f}")
print(f"Precision: {precision_score(y_back, y_pred):.4f}")
print(f"Recall: {recall_score(y_back, y_pred):.4f}")
print(f"F1: {f1_score(y_back, y_pred):.4f}")

# --- PREDICT ON 2025 ---
if X_pred is not None:
    print("Predicting on 2025 data...")
    y_pred_2025 = model.predict(X_pred)
    y_pred_2025_proba = model.predict_proba(X_pred)[:, 1]
    # Save or analyze predictions as needed
    np.save("predictions_2025.npy", y_pred_2025)
    np.save("predictions_2025_proba.npy", y_pred_2025_proba)
    print("2025 predictions saved.")
else:
    print("No 2025 data found for prediction.")

# --- (OPTIONAL) DASK/OUT-OF-CORE TEMPLATE ---
# For very large data, see XGBoost Dask or external memory docs:
# https://xgboost.readthedocs.io/en/stable/tutorials/dask.html
# https://xgboost.readthedocs.io/en/stable/tutorials/external_memory.html
# You can adapt the above to use Dask DataFrames or XGBoost's DMatrix with external memory.

print("All done!")
