import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss, accuracy_score

# --------------------------
# 1. Load your data
# --------------------------
df = pd.read_csv(
    "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
)

# --------------------------
# 2. Identify target and features
# --------------------------
target_col = "finishingPosition"
X = df.drop(columns=[target_col])
y = df[target_col]

# --------------------------
# 3. Handle categorical columns
# --------------------------
categorical_cols = [
    "meetingName",
    "runnerName",
    "riderName",
    "weatherCondition",
    "trackCondition",
    "raceName",
    "raceClassConditions"
]

for col in categorical_cols:
    X[col] = X[col].astype("category")
    # Fill missing values with a placeholder
    X[col] = X[col].cat.add_categories("Unknown").fillna("Unknown")

# --------------------------
# 4. Fill missing numerical values
# --------------------------
numerical_cols = X.select_dtypes(include=["float64", "int64"]).columns
X[numerical_cols] = X[numerical_cols].fillna(0)

# --------------------------
# 5. Remap target to start at 0
# --------------------------
unique_vals = sorted(y.unique())
val_map = {old: new for new, old in enumerate(unique_vals)}
y = y.map(val_map)

# --------------------------
# 6. Train/test split
# --------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# --------------------------
# 7. Train XGBoost model
# --------------------------
model = xgb.XGBClassifier(
    tree_method="hist",
    enable_categorical=True,
    eval_metric="mlogloss",
    use_label_encoder=False
)

model.fit(X_train, y_train)

# --------------------------
# 8. Predictions
# --------------------------
y_pred_prob = model.predict_proba(X_test)
y_pred = model.predict(X_test)

# --------------------------
# 9. Evaluation
# --------------------------
print("Log Loss:", log_loss(y_test, y_pred_prob))
print("Accuracy:", accuracy_score(y_test, y_pred))
