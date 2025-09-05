#!/usr/bin/env python3
"""
Horse Racing Prediction Model using XGBoost
Uses the comprehensive racing dataset to predict finishing positions
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

class RacingPredictionModel:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.target_column = 'finishingPosition'
        
    def load_data(self, file_path):
        """Load and prepare the racing data."""
        print("📊 Loading racing data...")
        self.df = pd.read_csv(file_path)
        print(f"✅ Loaded {len(self.df):,} records with {len(self.df.columns)} features")
        return self.df
    
    def explore_data(self):
        """Explore the dataset structure and quality."""
        print("\n🔍 DATA EXPLORATION:")
        print(f"Shape: {self.df.shape}")
        print(f"Date range: {self.df.meetingDate.min()} to {self.df.meetingDate.max()}")
        
        print(f"\n🏆 TARGET VARIABLE (finishingPosition):")
        print(self.df[self.target_column].value_counts().sort_index())
        
        print(f"\n🏇 UNIQUE VALUES:")
        print(f"Meetings: {self.df.meetingName.nunique()}")
        print(f"Horses: {self.df.runnerName.nunique()}")
        print(f"Jockeys: {self.df.riderName.nunique()}")
        print(f"Races: {self.df.groupby(['meetingName', 'meetingDate', 'raceNumber']).ngroups}")
        
        print(f"\n💰 ODDS ANALYSIS:")
        print(f"Opening odds - Mean: {self.df.FixedWinOpen_Reference.mean():.2f}, Range: {self.df.FixedWinOpen_Reference.min():.2f} - {self.df.FixedWinOpen_Reference.max():.2f}")
        print(f"Closing odds - Mean: {self.df.FixedWinClose_Reference.mean():.2f}, Range: {self.df.FixedWinClose_Reference.min():.2f} - {self.df.FixedWinClose_Reference.max():.2f}")
        
        # Check for missing values
        missing_data = self.df.isnull().sum()
        if missing_data.sum() > 0:
            print(f"\n⚠️ MISSING VALUES:")
            print(missing_data[missing_data > 0])
    
    def preprocess_data(self):
        """Preprocess the data for model training."""
        print("\n🔧 PREPROCESSING DATA...")
        
        # Create a copy for preprocessing
        df_processed = self.df.copy()
        
        # Handle missing values
        numeric_columns = df_processed.select_dtypes(include=[np.number]).columns
        df_processed[numeric_columns] = df_processed[numeric_columns].fillna(0)
        
        # Encode categorical variables
        categorical_columns = ['meetingName', 'runnerName', 'riderName', 'location', 
                             'weatherCondition', 'trackCondition', 'raceName', 
                             'trackDirection', 'raceClassConditions']
        
        for col in categorical_columns:
            if col in df_processed.columns:
                le = LabelEncoder()
                df_processed[col + '_encoded'] = le.fit_transform(df_processed[col].astype(str))
                self.label_encoders[col] = le
        
        # Create feature columns (exclude target and original categorical columns)
        exclude_columns = [self.target_column, 'meetingDate', 'raceStartTime'] + categorical_columns
        self.feature_columns = [col for col in df_processed.columns if col not in exclude_columns]
        
        print(f"✅ Created {len(self.feature_columns)} feature columns")
        print(f"Features: {self.feature_columns[:10]}...")  # Show first 10 features
        
        return df_processed
    
    def prepare_features(self, df_processed):
        """Prepare features and target for model training."""
        print("\n🎯 PREPARING FEATURES...")
        
        # Prepare features and target
        X = df_processed[self.feature_columns]
        y = df_processed[self.target_column]
        
        # Remove any infinite values
        X = X.replace([np.inf, -np.inf], 0)
        
        print(f"Feature matrix shape: {X.shape}")
        print(f"Target distribution: {y.value_counts().sort_index().to_dict()}")
        
        return X, y
    
    def train_model(self, X, y, test_size=0.2, random_state=42):
        """Train the XGBoost model."""
        print("\n🚀 TRAINING XGBOOST MODEL...")
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=None
        )
        
        # Initialize XGBoost model
        self.model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=random_state,
            eval_metric='rmse',
            early_stopping_rounds=10
        )
        
        # Train the model
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        # Make predictions
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)
        
        # Calculate metrics
        train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
        test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
        train_mae = mean_absolute_error(y_train, y_pred_train)
        test_mae = mean_absolute_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)
        
        print(f"\n📈 MODEL PERFORMANCE:")
        print(f"Training RMSE: {train_rmse:.3f}")
        print(f"Test RMSE: {test_rmse:.3f}")
        print(f"Training MAE: {train_mae:.3f}")
        print(f"Test MAE: {test_mae:.3f}")
        print(f"Training R²: {train_r2:.3f}")
        print(f"Test R²: {test_r2:.3f}")
        
        # Cross-validation (without early stopping)
        cv_model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=random_state,
            eval_metric='rmse'
        )
        cv_scores = cross_val_score(cv_model, X, y, cv=5, scoring='neg_mean_squared_error')
        cv_rmse = np.sqrt(-cv_scores.mean())
        print(f"Cross-validation RMSE: {cv_rmse:.3f} (+/- {np.sqrt(-cv_scores.var()) * 2:.3f})")
        
        return X_test, y_test, y_pred_test
    
    def analyze_feature_importance(self):
        """Analyze and display feature importance."""
        print("\n🔍 FEATURE IMPORTANCE ANALYSIS:")
        
        if self.model is None:
            print("❌ Model not trained yet!")
            return
        
        # Get feature importance
        importance = self.model.feature_importances_
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        print("\n🏆 TOP 20 MOST IMPORTANT FEATURES:")
        print(feature_importance_df.head(20))
        
        # Plot feature importance
        plt.figure(figsize=(12, 8))
        top_features = feature_importance_df.head(15)
        plt.barh(range(len(top_features)), top_features['importance'])
        plt.yticks(range(len(top_features)), top_features['feature'])
        plt.xlabel('Feature Importance')
        plt.title('Top 15 Feature Importance')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig('feature_importance.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        return feature_importance_df
    
    def predict_race(self, race_data):
        """Predict finishing positions for a new race."""
        if self.model is None:
            print("❌ Model not trained yet!")
            return None
        
        # Preprocess the race data (same as training data)
        race_processed = self.preprocess_race_data(race_data)
        
        # Make predictions
        predictions = self.model.predict(race_processed[self.feature_columns])
        
        # Add predictions to race data
        race_data['predicted_position'] = predictions
        
        return race_data.sort_values('predicted_position')
    
    def preprocess_race_data(self, race_data):
        """Preprocess new race data using the same transformations as training."""
        race_processed = race_data.copy()
        
        # Handle missing values
        numeric_columns = race_processed.select_dtypes(include=[np.number]).columns
        race_processed[numeric_columns] = race_processed[numeric_columns].fillna(0)
        
        # Encode categorical variables using the same encoders
        categorical_columns = ['meetingName', 'runnerName', 'riderName', 'location', 
                             'weatherCondition', 'trackCondition', 'raceName', 
                             'trackDirection', 'raceClassConditions']
        
        for col in categorical_columns:
            if col in race_processed.columns and col in self.label_encoders:
                le = self.label_encoders[col]
                # Handle unseen categories
                race_processed[col + '_encoded'] = race_processed[col].astype(str).map(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )
        
        # Remove infinite values
        race_processed = race_processed.replace([np.inf, -np.inf], 0)
        
        return race_processed
    
    def save_model(self, filepath='racing_model.pkl'):
        """Save the trained model."""
        import pickle
        model_data = {
            'model': self.model,
            'label_encoders': self.label_encoders,
            'feature_columns': self.feature_columns,
            'target_column': self.target_column
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"✅ Model saved to {filepath}")
    
    def load_model(self, filepath='racing_model.pkl'):
        """Load a trained model."""
        import pickle
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.label_encoders = model_data['label_encoders']
        self.feature_columns = model_data['feature_columns']
        self.target_column = model_data['target_column']
        print(f"✅ Model loaded from {filepath}")

def main():
    """Main function to train the racing prediction model."""
    # Initialize the model
    racing_model = RacingPredictionModel()
    
    # Load data
    df = racing_model.load_data('a32f0fe3-f31e-49fd-99b7-bce6092ed901.csv')
    
    # Explore data
    racing_model.explore_data()
    
    # Preprocess data
    df_processed = racing_model.preprocess_data()
    
    # Prepare features
    X, y = racing_model.prepare_features(df_processed)
    
    # Train model
    X_test, y_test, y_pred_test = racing_model.train_model(X, y)
    
    # Analyze feature importance
    feature_importance = racing_model.analyze_feature_importance()
    
    # Save model
    racing_model.save_model()
    
    print("\n🎉 MODEL TRAINING COMPLETE!")
    print("The model is ready to predict race outcomes.")
    print("Use racing_model.predict_race(race_data) to make predictions on new races.")
    
    return racing_model

if __name__ == "__main__":
    racing_model = main()
