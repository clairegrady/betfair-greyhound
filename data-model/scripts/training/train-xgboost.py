import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
import joblib  # for saving model if needed

# Create DMatrix for training and evaluation
dtrain = xgb.DMatrix(X_train, label=y_train)
dtest = xgb.DMatrix(X_test, label=y_test)

# Define training parameters
params = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "eta": 0.05,
    "max_depth": 6,
    "scale_pos_weight": (len(y_train) - y_train.sum()) / y_train.sum(),
    "seed": 42,
    "verbosity": 1,
    "nthread": 4  # You can increase depending on your EC2 instance cores
}

# Train the model with early stopping
watchlist = [(dtrain, "train"), (dtest, "eval")]
model = xgb.train(
    params,
    dtrain,
    num_boost_round=200,
    early_stopping_rounds=20,
    evals=watchlist
)

# Predict on test data
y_pred = model.predict(dtest)
y_pred_label = (y_pred > 0.5).astype(int)

# Output classification results
print(classification_report(y_test, y_pred_label))
print("AUC:", roc_auc_score(y_test, y_pred))

# (Optional) Save model to file
model.save_model("xgb_model.json")
