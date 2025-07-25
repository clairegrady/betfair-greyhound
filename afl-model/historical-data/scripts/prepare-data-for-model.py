import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import matplotlib.pyplot as plt
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold

# Load selected features
data_path = "/home/ec2-user/processed/selected_features.parquet"
print(f"📥 Loading data from {data_path}")
df = pd.read_parquet(data_path)

# Keep only placing markets
df = df[df["marketName"] == "To Be Placed"].copy()

# Create binary label for "placed"
df["placed"] = (df["status"] == "WINNER").astype(int)

# Feature engineering
df = df.dropna(subset=["bsp", "handicap", "adjustmentFactor"])
df["bsp_log"] = np.log(df["bsp"] + 0.01)
df["hour"] = pd.to_datetime(df["marketStartTime"]).dt.hour
df["weekday"] = pd.to_datetime(df["marketStartTime"]).dt.dayofweek

# Encode categories
for cat in ["venue", "runnerName", "marketId"]:
    df[cat] = df[cat].astype("category").cat.codes

# Select features and target
feature_cols = ["bsp_log", "handicap", "adjustmentFactor", "hour", "weekday", "venue", "runnerName"]
X = df[feature_cols]
y = df["placed"]

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# -----------------------------------------------
# 📍 1. BSP Benchmark — Compare to simple strategy
# -----------------------------------------------
best_bsp_acc = []
for mid, group in df.groupby("marketId"):
    idx_min = group["bsp"].idxmin()
    best_bsp_acc.append(group.loc[idx_min, "placed"])

benchmark = sum(best_bsp_acc) / len(best_bsp_acc)
print(f"\n⚖️ Benchmark (lowest BSP is placed): {benchmark:.4f}")

# -----------------------------------------------
# 📍 2. Train XGBoost (raw probabilities)
# -----------------------------------------------
params = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "eta": 0.05,
    "max_depth": 6,
    "scale_pos_weight": (len(y_train) - y_train.sum()) / y_train.sum(),
    "seed": 42
}

dtrain = xgb.DMatrix(X_train, label=y_train)
dtest = xgb.DMatrix(X_test, label=y_test)

watchlist = [(dtrain, "train"), (dtest, "eval")]
model = xgb.train(params, dtrain, num_boost_round=200, early_stopping_rounds=20, evals=watchlist)

# -----------------------------------------------
# 📍 3. Feature Importance (optional)
# -----------------------------------------------
xgb.plot_importance(model, max_num_features=10)
plt.title("XGBoost Feature Importance")
plt.tight_layout()
plt.show()

# -----------------------------------------------
# 📍 4. Calibrate model with sklearn (recommended)
# -----------------------------------------------
xgb_sklearn_model = xgb.XGBClassifier(**params, use_label_encoder=False, eval_metric='auc')
calibrator = CalibratedClassifierCV(
    base_estimator=xgb_sklearn_model,
    cv=StratifiedKFold(n_splits=5)
)

calibrator.fit(X_train, y_train)

# Predict calibrated probabilities
probs = calibrator.predict_proba(X_test)[:, 1]
y_pred_label = (probs > 0.5).astype(int)

# Evaluate
print("\n✅ Calibrated Model Performance:")
print(classification_report(y_test, y_pred_label))
print("🎯 Calibrated AUC:", roc_auc_score(y_test, probs))
