import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

def train_and_test_model():
    """Train model on 80% of data and test predictions on 20%"""
    
    print("Loading CSV data...")
    # Load the CSV file
    df = pd.read_csv('/Users/clairegrady/RiderProjects/betfair/data-model/a32f0fe3-f31e-49fd-99b7-bce6092ed901.csv')
    
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    
    # Check if finishingPosition exists
    if 'finishingPosition' not in df.columns:
        print("ERROR: 'finishingPosition' column not found!")
        print(f"Available columns: {list(df.columns)}")
        return
    
    # Remove rows with missing finishing positions
    df = df.dropna(subset=['finishingPosition'])
    print(f"After removing missing finishing positions: {df.shape}")
    
    # Convert finishingPosition to numeric, handling non-numeric values
    df['finishingPosition'] = pd.to_numeric(df['finishingPosition'], errors='coerce')
    df = df.dropna(subset=['finishingPosition'])
    print(f"After converting to numeric: {df.shape}")
    
    # Show finishing position distribution
    print(f"\nFinishing position distribution:")
    print(df['finishingPosition'].value_counts().sort_index().head(10))
    
    # Prepare features (exclude finishingPosition and any other target-related columns)
    feature_columns = [col for col in df.columns if col not in ['finishingPosition', 'id', 'race_id']]
    
    print(f"\nFeature columns ({len(feature_columns)}): {feature_columns}")
    
    # Prepare X (features) and y (target)
    X = df[feature_columns].copy()
    y = df['finishingPosition']
    
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
        X, y, test_size=0.2, random_state=42, stratify=None
    )
    
    print(f"\nTraining set: {X_train.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    
    # Train XGBoost model
    print("\nTraining XGBoost model...")
    model = xgb.XGBRegressor(
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
    
    # Calculate metrics
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"\n=== MODEL PERFORMANCE ===")
    print(f"Mean Squared Error: {mse:.4f}")
    print(f"Mean Absolute Error: {mae:.4f}")
    print(f"R² Score: {r2:.4f}")
    
    # Show some sample predictions
    print(f"\n=== SAMPLE PREDICTIONS (Test Set) ===")
    results_df = pd.DataFrame({
        'Actual_Position': y_test.values,
        'Predicted_Position': y_pred,
        'Error': np.abs(y_test.values - y_pred)
    })
    
    # Sort by error to show worst predictions first
    results_df = results_df.sort_values('Error', ascending=False)
    
    print("\nTop 10 Worst Predictions:")
    print(results_df.head(10))
    
    print(f"\nTop 10 Best Predictions:")
    print(results_df.tail(10))
    
    # Show prediction accuracy by position
    print(f"\n=== PREDICTION ACCURACY BY POSITION ===")
    position_accuracy = results_df.groupby('Actual_Position').agg({
        'Error': ['mean', 'std', 'count']
    }).round(3)
    print(position_accuracy.head(10))
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': feature_columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n=== TOP 10 MOST IMPORTANT FEATURES ===")
    print(feature_importance.head(10))
    
    # Save results
    results_df.to_csv('model_predictions_results.csv', index=False)
    print(f"\nResults saved to 'model_predictions_results.csv'")
    
    return model, results_df, feature_importance

if __name__ == "__main__":
    model, results, feature_importance = train_and_test_model()
