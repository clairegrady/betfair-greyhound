import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

def create_place_betting_model():
    """Create a model to predict place finishes (top 2-3 positions)"""
    
    print("Loading CSV data...")
    # Load the CSV file
    df = pd.read_csv('/Users/clairegrady/RiderProjects/betfair/data-model/a32f0fe3-f31e-49fd-99b7-bce6092ed901.csv')
    
    print(f"Dataset shape: {df.shape}")
    
    # Remove rows with missing finishing positions
    df = df.dropna(subset=['finishingPosition'])
    df['finishingPosition'] = pd.to_numeric(df['finishingPosition'], errors='coerce')
    df = df.dropna(subset=['finishingPosition'])
    
    # Create place target (1 = placed, 0 = not placed)
    # For place betting, we consider positions 1, 2, 3 as "placed"
    df['placed'] = (df['finishingPosition'] >= 1) & (df['finishingPosition'] <= 3)
    df['placed'] = df['placed'].astype(int)
    
    # Remove scratched horses (-2.0) as they can't place
    df = df[df['finishingPosition'] != -2.0]
    
    print(f"After removing scratched horses: {df.shape}")
    
    # Show place distribution
    print(f"\nPlace distribution:")
    print(df['placed'].value_counts())
    print(f"Place rate: {df['placed'].mean():.2%}")
    
    # Prepare features (exclude finishingPosition and placed)
    feature_columns = [col for col in df.columns if col not in ['finishingPosition', 'placed', 'id', 'race_id']]
    
    print(f"\nFeature columns ({len(feature_columns)}): {feature_columns}")
    
    # Prepare X (features) and y (target)
    X = df[feature_columns].copy()
    y = df['placed']
    
    # Handle categorical variables
    categorical_columns = X.select_dtypes(include=['object']).columns
    label_encoders = {}
    
    for col in categorical_columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le
    
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
    
    # Train XGBoost model for classification
    print("\nTraining XGBoost classification model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Make predictions on test set
    print("Making predictions on test set...")
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]  # Probability of placing
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    print(f"\n=== PLACE BETTING MODEL PERFORMANCE ===")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion Matrix:")
    print(f"True Negatives (Not Placed, Predicted Not Placed): {cm[0,0]}")
    print(f"False Positives (Not Placed, Predicted Placed): {cm[0,1]}")
    print(f"False Negatives (Placed, Predicted Not Placed): {cm[1,0]}")
    print(f"True Positives (Placed, Predicted Placed): {cm[1,1]}")
    
    # Show some sample predictions with probabilities
    print(f"\n=== SAMPLE PREDICTIONS (Test Set) ===")
    results_df = pd.DataFrame({
        'Actual_Placed': y_test.values,
        'Predicted_Placed': y_pred,
        'Place_Probability': y_pred_proba,
        'Correct': (y_test.values == y_pred)
    })
    
    # Sort by probability to show most confident predictions
    results_df = results_df.sort_values('Place_Probability', ascending=False)
    
    print("\nTop 10 Most Confident Place Predictions:")
    print(results_df.head(10))
    
    print(f"\nTop 10 Least Confident Place Predictions:")
    print(results_df.tail(10))
    
    # Show prediction accuracy by probability threshold
    print(f"\n=== PREDICTION ACCURACY BY PROBABILITY THRESHOLD ===")
    thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    
    for threshold in thresholds:
        high_conf_predictions = results_df[results_df['Place_Probability'] >= threshold]
        if len(high_conf_predictions) > 0:
            accuracy_at_threshold = high_conf_predictions['Correct'].mean()
            print(f"Threshold {threshold:.1f}: {len(high_conf_predictions)} predictions, Accuracy: {accuracy_at_threshold:.3f}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n=== TOP 10 MOST IMPORTANT FEATURES FOR PLACE PREDICTION ===")
    print(feature_importance.head(10))
    
    # Save results
    results_df.to_csv('place_betting_predictions.csv', index=False)
    print(f"\nResults saved to 'place_betting_predictions.csv'")
    
    return model, results_df, feature_importance

if __name__ == "__main__":
    model, results, feature_importance = create_place_betting_model()
