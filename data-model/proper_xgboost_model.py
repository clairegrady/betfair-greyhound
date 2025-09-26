#!/usr/bin/env python3
"""
Proper XGBoost Model for Horse Racing Prediction
Using top 5 features with native XGBoost API, cross-validation, and early stopping
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import warnings
warnings.filterwarnings('ignore')

class ProperXGBoostModel:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = None
        self.model = None
        self.cv_results = None
        
        # Top 5 features from previous analysis
        self.top_features = [
            'FixedWinClose_Reference',
            'region_trainer_placings', 
            'track_rider_placings',
            'jockey_trainer_placings',
            'region_trainer_wins'
        ]
        
    def load_and_clean_data(self):
        """Load and clean the dataset"""
        print("📊 Loading horse racing data...")
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} records")
        
        # Remove scratched horses (negative finishing positions)
        original_count = len(self.df)
        self.df = self.df[self.df['finishingPosition'] > 0].copy()
        removed_scratched = original_count - len(self.df)
        print(f"   - Removed {removed_scratched:,} scratched horses")
        
        # Remove invalid odds
        original_count = len(self.df)
        self.df = self.df[self.df['FixedWinClose_Reference'] > 0].copy()
        removed_invalid_odds = original_count - len(self.df)
        print(f"   - Removed {removed_invalid_odds:,} records with invalid odds")
        
        # Create binary target: 1 if horse wins (finishingPosition = 1), 0 otherwise
        self.df['target'] = (self.df['finishingPosition'] == 1).astype(int)
        
        print(f"   - Final dataset: {len(self.df):,} records")
        print(f"   - Win rate: {self.df['target'].mean():.1%}")
        
        return self.df
    
    def prepare_features(self):
        """Prepare the top 5 features"""
        print("\n🔧 Preparing top 5 features...")
        
        # Check if all features exist
        missing_features = [f for f in self.top_features if f not in self.df.columns]
        if missing_features:
            print(f"❌ Missing features: {missing_features}")
            return None, None
        
        # Select only the top 5 features
        X = self.df[self.top_features].copy()
        y = self.df['target'].copy()
        
        # Handle missing values
        X = X.fillna(0)
        
        # Remove any infinite values
        X = X.replace([np.inf, -np.inf], 0)
        
        print(f"   - Feature matrix shape: {X.shape}")
        print(f"   - Target distribution: {y.value_counts().to_dict()}")
        
        return X, y
    
    def train_with_cross_validation(self, X, y):
        """Train XGBoost model with proper cross-validation and early stopping"""
        print("\n🚀 Training XGBoost with cross-validation...")
        
        # Create DMatrix
        dtrain = xgb.DMatrix(X, y)
        
        # Set parameters for binary classification
        params = {
            "objective": "binary:logistic",
            "tree_method": "hist",  # Use hist for CPU, gpu_hist for GPU
            "eval_metric": "auc",
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42
        }
        
        # Cross-validation with early stopping
        print("   - Running 5-fold cross-validation...")
        self.cv_results = xgb.cv(
            params=params,
            dtrain=dtrain,
            num_boost_round=1000,
            nfold=5,
            early_stopping_rounds=50,
            verbose_eval=50
        )
        
        # Get best number of rounds
        best_rounds = self.cv_results['test-auc-mean'].idxmax()
        best_auc = self.cv_results['test-auc-mean'].max()
        
        print(f"   - Best AUC: {best_auc:.4f} at round {best_rounds}")
        print(f"   - Training AUC: {self.cv_results['train-auc-mean'].iloc[best_rounds]:.4f}")
        
        # Train final model with best number of rounds
        print(f"   - Training final model with {best_rounds} rounds...")
        self.model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=best_rounds
        )
        
        return self.model
    
    def evaluate_model(self, X, y):
        """Evaluate the trained model"""
        print("\n📊 Evaluating model...")
        
        # Split data for evaluation
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Create DMatrices
        dtrain = xgb.DMatrix(X_train, y_train)
        dtest = xgb.DMatrix(X_test, y_test)
        
        # Train model
        params = {
            "objective": "binary:logistic",
            "tree_method": "hist",
            "eval_metric": "auc",
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42
        }
        
        model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=1000,
            early_stopping_rounds=50,
            evals=[(dtrain, "train"), (dtest, "test")],
            verbose_eval=False
        )
        
        # Make predictions
        y_pred_proba = model.predict(dtest)
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_pred_proba)
        
        print(f"   - Test Accuracy: {accuracy:.4f}")
        print(f"   - Test AUC: {auc:.4f}")
        
        # Print classification report
        print(f"\n📋 Classification Report:")
        print(classification_report(y_test, y_pred))
        
        return {
            'accuracy': accuracy,
            'auc': auc,
            'model': model,
            'predictions': y_pred_proba
        }
    
    def analyze_feature_importance(self):
        """Analyze feature importance"""
        print("\n📊 Analyzing feature importance...")
        
        if self.model is None:
            print("❌ No model trained yet")
            return None
        
        # Get feature importance
        importance = self.model.get_score(importance_type='weight')
        
        # Create importance dataframe
        importance_df = pd.DataFrame([
            {'feature': feature, 'importance': importance.get(feature, 0)}
            for feature in self.top_features
        ]).sort_values('importance', ascending=False)
        
        print("\n🏆 Feature Importance:")
        for i, (_, row) in enumerate(importance_df.iterrows(), 1):
            print(f"   {i}. {row['feature']:<25} {row['importance']:.4f}")
        
        return importance_df
    
    def run_complete_analysis(self):
        """Run the complete analysis"""
        print("🏇 Starting Proper XGBoost Analysis")
        print("=" * 50)
        
        # Load and clean data
        self.load_and_clean_data()
        
        # Prepare features
        X, y = self.prepare_features()
        if X is None:
            print("❌ Failed to prepare features")
            return None
        
        # Train with cross-validation
        self.train_with_cross_validation(X, y)
        
        # Evaluate model
        results = self.evaluate_model(X, y)
        
        # Analyze feature importance
        importance_df = self.analyze_feature_importance()
        
        print("\n✅ Analysis complete!")
        print(f"📊 Final Results:")
        print(f"   - Best CV AUC: {self.cv_results['test-auc-mean'].max():.4f}")
        print(f"   - Test AUC: {results['auc']:.4f}")
        print(f"   - Test Accuracy: {results['accuracy']:.4f}")
        
        return {
            'model': self.model,
            'cv_results': self.cv_results,
            'test_results': results,
            'feature_importance': importance_df
        }

def main():
    """Main function"""
    csv_path = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    model = ProperXGBoostModel(csv_path)
    results = model.run_complete_analysis()
    
    if results:
        print(f"\n🎯 Model Performance Summary:")
        print(f"   - Cross-validation AUC: {results['cv_results']['test-auc-mean'].max():.4f}")
        print(f"   - Test AUC: {results['test_results']['auc']:.4f}")
        print(f"   - Test Accuracy: {results['test_results']['accuracy']:.4f}")
        print(f"   - Top Feature: {results['feature_importance'].iloc[0]['feature']}")

if __name__ == "__main__":
    main()
