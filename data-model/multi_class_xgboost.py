#!/usr/bin/env python3
"""
Multi-class XGBoost Model for Horse Racing Position Prediction
Predicts Win/Place/Unplaced for all horses in a race
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

class MultiClassXGBoostModel:
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
        
        # Create multi-class target: 0=Win, 1=Place, 2=Unplaced
        def create_position_target(pos):
            if pos == 1:
                return 0  # Win
            elif pos in [2, 3]:
                return 1  # Place
            else:
                return 2  # Unplaced
        
        self.df['position_target'] = self.df['finishingPosition'].apply(create_position_target)
        
        print(f"   - Final dataset: {len(self.df):,} records")
        print(f"   - Win rate: {(self.df['position_target'] == 0).mean():.1%}")
        print(f"   - Place rate: {(self.df['position_target'] == 1).mean():.1%}")
        print(f"   - Unplaced rate: {(self.df['position_target'] == 2).mean():.1%}")
        
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
        y = self.df['position_target'].copy()
        
        # Handle missing values
        X = X.fillna(0)
        
        # Remove any infinite values
        X = X.replace([np.inf, -np.inf], 0)
        
        print(f"   - Feature matrix shape: {X.shape}")
        print(f"   - Target distribution: {y.value_counts().to_dict()}")
        
        return X, y
    
    def train_with_cross_validation(self, X, y):
        """Train XGBoost model with proper cross-validation and early stopping"""
        print("\n🚀 Training Multi-class XGBoost with cross-validation...")
        
        # Create DMatrix
        dtrain = xgb.DMatrix(X, y)
        
        # Set parameters for multi-class classification
        params = {
            "objective": "multi:softprob",
            "num_class": 3,  # 3 classes: Win, Place, Unplaced
            "tree_method": "hist",
            "eval_metric": "mlogloss",
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
        best_rounds = self.cv_results['test-mlogloss-mean'].idxmin()
        best_mlogloss = self.cv_results['test-mlogloss-mean'].min()
        
        print(f"   - Best mlogloss: {best_mlogloss:.4f} at round {best_rounds}")
        print(f"   - Training mlogloss: {self.cv_results['train-mlogloss-mean'].iloc[best_rounds]:.4f}")
        
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
            "objective": "multi:softprob",
            "num_class": 3,
            "tree_method": "hist",
            "eval_metric": "mlogloss",
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
        y_pred = np.argmax(y_pred_proba, axis=1)
        
        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"   - Test Accuracy: {accuracy:.4f}")
        
        # Print classification report
        print(f"\n📋 Classification Report:")
        print(classification_report(y_test, y_pred, target_names=['Win', 'Place', 'Unplaced']))
        
        # Print confusion matrix
        print(f"\n📊 Confusion Matrix:")
        cm = confusion_matrix(y_test, y_pred)
        print("     Predicted")
        print("     Win  Place  Unplaced")
        print(f"Win  {cm[0,0]:4d}  {cm[0,1]:4d}  {cm[0,2]:4d}")
        print(f"Place {cm[1,0]:4d}  {cm[1,1]:4d}  {cm[1,2]:4d}")
        print(f"Unplaced {cm[2,0]:4d}  {cm[2,1]:4d}  {cm[2,2]:4d}")
        
        return {
            'accuracy': accuracy,
            'model': model,
            'predictions': y_pred_proba,
            'y_test': y_test,
            'y_pred': y_pred
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
    
    def predict_race_positions(self, race_data):
        """Predict positions for all horses in a race"""
        print("\n🏁 Predicting race positions...")
        
        if self.model is None:
            print("❌ No model trained yet")
            return None
        
        # Create DMatrix for race data
        dtest = xgb.DMatrix(race_data[self.top_features])
        
        # Get predictions
        predictions = self.model.predict(dtest)
        
        # Create results dataframe
        results = race_data.copy()
        results['win_prob'] = predictions[:, 0]
        results['place_prob'] = predictions[:, 1]
        results['unplaced_prob'] = predictions[:, 2]
        results['predicted_position'] = np.argmax(predictions, axis=1)
        
        # Map predicted positions to labels
        position_labels = {0: 'Win', 1: 'Place', 2: 'Unplaced'}
        results['predicted_label'] = results['predicted_position'].map(position_labels)
        
        # Sort by win probability (most likely to win first)
        results = results.sort_values('win_prob', ascending=False)
        
        print(f"   - Predicted {len(results)} horses")
        print(f"   - Win predictions: {(results['predicted_position'] == 0).sum()}")
        print(f"   - Place predictions: {(results['predicted_position'] == 1).sum()}")
        print(f"   - Unplaced predictions: {(results['predicted_position'] == 2).sum()}")
        
        return results
    
    def run_complete_analysis(self):
        """Run the complete analysis"""
        print("🏇 Starting Multi-class XGBoost Analysis")
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
        print(f"   - Best CV mlogloss: {self.cv_results['test-mlogloss-mean'].min():.4f}")
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
    
    model = MultiClassXGBoostModel(csv_path)
    results = model.run_complete_analysis()
    
    if results:
        print(f"\n🎯 Model Performance Summary:")
        print(f"   - Cross-validation mlogloss: {results['cv_results']['test-mlogloss-mean'].min():.4f}")
        print(f"   - Test Accuracy: {results['test_results']['accuracy']:.4f}")
        print(f"   - Top Feature: {results['feature_importance'].iloc[0]['feature']}")

if __name__ == "__main__":
    main()
