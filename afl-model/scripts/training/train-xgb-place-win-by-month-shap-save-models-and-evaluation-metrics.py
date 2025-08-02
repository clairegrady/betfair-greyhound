import pandas as pd
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score, f1_score
from pathlib import Path

# Directory with combined monthly parquet files
combined_dir = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/horseracing_cleaned_parquet_by_month")
models_dir = combined_dir / "xgb_models"
metrics_path = combined_dir / "metrics_summary.csv"

models_dir.mkdir(exist_ok=True)

# Prepare a list to collect metrics
metrics_list = []

for combined_file in sorted(combined_dir.glob("combined_*.parquet")):
    combined_filename = combined_file.name  # e.g. "combined_2016_Dec.parquet"
    month_year = combined_file.stem.replace("combined_", "")  # e.g. "2016_Dec"
    print(f"\nProcessing file: {combined_filename}")

    # 1. Load data
    df = pd.read_parquet(combined_file)

    # 2. Create binary target: 1 if WINNER or PLACED, else 0
    df['target_place_or_win'] = df['status'].apply(lambda x: 1 if x in ['WINNER', 'PLACED'] else 0)

    # 3. Define features to drop
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

    # Save the model
    model_save_path = models_dir / f"xgb_model_{month_year}.json"
    model.save_model(model_save_path)
    print(f"Model saved to {model_save_path}")

    # 7. Evaluate
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"Metrics for {month_year}: Accuracy={acc:.4f}, ROC AUC={roc_auc:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}")

    metrics_list.append({
        "month_year": month_year,
        "accuracy": acc,
        "roc_auc": roc_auc,
        "precision": precision,
        "recall": recall,
        "f1_score": f1
    })

    # 8. SHAP explainer on test data
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)

    # 9. Summary plot
    plt.figure()
    shap.summary_plot(shap_values, X_test, show=False)
    plt.savefig(f"shap_summary_plot_{month_year}.png")
    plt.close()

    # 10. Dependence plots saved for each feature
    for feature in X_test.columns:
        plt.figure()
        shap.dependence_plot(feature, shap_values, X_test, show=False)
        plt.savefig(f"shap_dependence_{feature}_{month_year}.png")
        plt.close()

# Save all metrics to CSV
metrics_df = pd.DataFrame(metrics_list)
metrics_df.to_csv(metrics_path, index=False)
print(f"\n✅ All SHAP plots, models, and metrics saved successfully.")
