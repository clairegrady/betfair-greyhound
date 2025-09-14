import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

def create_comprehensive_place_model():
    """Create an XGBoost model using ALL available columns for place betting"""
    
    print("Loading large dataset...")
    # Load the large CSV file
    df = pd.read_csv('/Users/clairegrady/RiderProjects/betfair/data-model/scripts/Runner_Result_2025-09-07.csv')
    
    print(f"Dataset shape: {df.shape}")
    print(f"All columns: {list(df.columns)}")
    
    # Remove rows with missing finishing positions
    df = df.dropna(subset=['finishingPosition'])
    df['finishingPosition'] = pd.to_numeric(df['finishingPosition'], errors='coerce')
    df = df.dropna(subset=['finishingPosition'])
    
    # Create place target (1 = placed, 0 = not placed)
    df['placed'] = (df['finishingPosition'] >= 1) & (df['finishingPosition'] <= 3)
    df['placed'] = df['placed'].astype(int)
    
    # Remove scratched horses (-2.0) as they can't place
    df = df[df['finishingPosition'] != -2.0]
    
    print(f"After removing scratched horses: {df.shape}")
    print(f"Place rate: {df['placed'].mean():.2%}")
    
    # Use ALL columns except target variables, identifiers, and data leakage features
    exclude_columns = ['finishingPosition', 'placed', 'meetingName', 'meetingDate', 'raceName', 'raceStartTime', 'raceNumber']
    
    # Get all feature columns
    feature_columns = [col for col in df.columns if col not in exclude_columns]
    
    print(f"\nUsing {len(feature_columns)} features:")
    for i, col in enumerate(feature_columns):
        print(f"  {i+1:2d}. {col}")
    
    # Prepare features
    X = df[feature_columns].copy()
    y = df['placed']
    
    # Handle categorical variables
    categorical_columns = X.select_dtypes(include=['object']).columns
    label_encoders = {}
    
    print(f"\nCategorical columns to encode: {list(categorical_columns)}")
    
    for col in categorical_columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le
        print(f"  Encoded {col}: {len(le.classes_)} unique values")
    
    # Handle missing values
    X = X.fillna(0)
    
    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Target shape: {y.shape}")
    
    # Split data 80/20
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\nTraining set: {X_train.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    print(f"Training set place rate: {y_train.mean():.2%}")
    print(f"Test set place rate: {y_test.mean():.2%}")
    
    # Train XGBoost model with optimized parameters
    print("\nTraining XGBoost model...")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    # Make predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print(f"\n=== COMPREHENSIVE PLACE BETTING MODEL PERFORMANCE ===")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    print(f"AUC: {auc:.4f}")
    
    # Check for the probability threshold issue
    print(f"\n=== INVESTIGATING PROBABILITY THRESHOLD ISSUE ===")
    
    # Create detailed results dataframe
    results_df = pd.DataFrame({
        'Actual_Placed': y_test.values,
        'Predicted_Placed': y_pred,
        'Place_Probability': y_pred_proba,
        'Correct': (y_test.values == y_pred)
    })
    
    # Check probability distribution
    print(f"Probability distribution:")
    print(f"  Min: {y_pred_proba.min():.4f}")
    print(f"  Max: {y_pred_proba.max():.4f}")
    print(f"  Mean: {y_pred_proba.mean():.4f}")
    print(f"  Median: {np.median(y_pred_proba):.4f}")
    
    # Check if probabilities are well-calibrated
    print(f"\nProbability calibration check:")
    thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    
    for threshold in thresholds:
        high_conf_predictions = results_df[results_df['Place_Probability'] >= threshold]
        if len(high_conf_predictions) > 0:
            accuracy_at_threshold = high_conf_predictions['Correct'].mean()
            actual_place_rate = high_conf_predictions['Actual_Placed'].mean()
            avg_prob = high_conf_predictions['Place_Probability'].mean()
            print(f"Threshold {threshold:.1f}: {len(high_conf_predictions):5d} predictions, "
                  f"Accuracy: {accuracy_at_threshold:.3f}, "
                  f"Actual Place Rate: {actual_place_rate:.3f}, "
                  f"Avg Predicted Prob: {avg_prob:.3f}")
    
    # XGBoost feature importance
    xgb_importance = pd.DataFrame({
        'feature': feature_columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n=== XGBOOST TOP 20 MOST IMPORTANT FEATURES ===")
    print(xgb_importance.head(20))
    
    # SHAP Analysis (sample for performance)
    print(f"\n=== SHAP ANALYSIS (using sample of 1000 for performance) ===")
    
    # Use a sample for SHAP to avoid memory issues
    sample_size = min(1000, len(X_test))
    X_test_sample = X_test.sample(n=sample_size, random_state=42)
    y_test_sample = y_test.loc[X_test_sample.index]
    
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test_sample)
    
    # SHAP feature importance
    shap_importance = pd.DataFrame({
        'feature': feature_columns,
        'shap_importance': np.abs(shap_values).mean(0)
    }).sort_values('shap_importance', ascending=False)
    
    print(f"\n=== SHAP TOP 20 MOST IMPORTANT FEATURES ===")
    print(shap_importance.head(20))
    
    # Save results
    results_df.to_csv('comprehensive_place_predictions.csv', index=False)
    xgb_importance.to_csv('comprehensive_xgb_importance.csv', index=False)
    shap_importance.to_csv('comprehensive_shap_importance.csv', index=False)
    
    # Save the trained model
    import pickle
    with open('comprehensive_place_model.pkl', 'wb') as f:
        pickle.dump(model, f)
    print("✅ Model saved as comprehensive_place_model.pkl")
    
    print(f"\nResults saved to:")
    print(f"- comprehensive_place_predictions.csv")
    print(f"- comprehensive_xgb_importance.csv")
    print(f"- comprehensive_shap_importance.csv")
    print(f"- comprehensive_place_model.pkl")
    
    return model, results_df, xgb_importance, shap_importance

if __name__ == "__main__":
    model, results, xgb_importance, shap_importance = create_comprehensive_place_model()
