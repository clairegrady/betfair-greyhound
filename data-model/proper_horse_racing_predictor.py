#!/usr/bin/env python3
"""
Proper Horse Racing XGBoost Predictor

This script creates a robust XGBoost model to predict horse racing outcomes
with proper feature engineering, evaluation, and race-level predictions.
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import log_loss, accuracy_score, classification_report
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
import pickle
warnings.filterwarnings('ignore')

class HorseRacingPredictor:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = None
        self.X = None
        self.y = None
        self.model = None
        self.feature_names = None
        
    def load_and_clean_data(self):
        """Load and clean the racing data"""
        print("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_path)
        
        # Remove scratched horses (negative finishing positions: -1, -2)
        original_count = len(self.df)
        self.df = self.df[self.df['finishingPosition'] >= 0].copy()
        scratched_count = original_count - len(self.df)
        
        print(f"✅ Loaded {original_count:,} records")
        print(f"🗑️ Removed {scratched_count:,} scratched horses")
        print(f"📊 Using {len(self.df):,} valid records")
        
        # Convert meetingDate to datetime
        self.df['meetingDate'] = pd.to_datetime(self.df['meetingDate'])
        
    def create_target_variable(self):
        """Create binary win/loss target"""
        print("🎯 Creating target variable...")
        
        # Create binary target: 1 for winner (position 1), 0 for others
        self.df['is_winner'] = (self.df['finishingPosition'] == 1).astype(int)
        
        # Check class distribution
        win_rate = self.df['is_winner'].mean()
        print(f"📈 Win rate: {win_rate:.1%}")
        print(f"📊 Winners: {self.df['is_winner'].sum():,} / {len(self.df):,}")
        
    def select_features(self):
        """Select the most predictive features"""
        print("🔍 Selecting features...")
        
        # Key features for horse racing prediction
        # Note: raceDistance, runnerNumber, FixedWinOpen_Reference, FixedWinClose_Reference 
        # will be replaced with live data during prediction
        feature_columns = [
            # Odds (will be replaced with live data)
            'FixedWinOpen_Reference',
            'FixedWinClose_Reference',
            
            # Runner performance history (historical data)
            'overall_runner_wins',
            'overall_runner_placings', 
            'track_runner_wins',
            'track_runner_placings',
            'distance_runner_wins',
            'distance_runner_placings',
            
            # Trainer performance (historical data)
            'region_trainer_wins',
            'region_trainer_placings',
            'track_trainer_wins',
            'track_trainer_placings',
            
            # Jockey performance (historical data)
            'region_rider_wins',
            'region_rider_placings',
            'track_rider_wins',
            'track_rider_placings',
            
            # Recent form (historical data)
            'last30Days_trainer_wins',
            'last30Days_rider_wins',
            
            # Race conditions (will be replaced with live data)
            'raceDistance',
            'runnerNumber',  # Barrier position
        ]
        
        # Check which features exist in the data
        available_features = [col for col in feature_columns if col in self.df.columns]
        missing_features = [col for col in feature_columns if col not in self.df.columns]
        
        if missing_features:
            print(f"⚠️ Missing features: {missing_features}")
        
        print(f"✅ Using {len(available_features)} features")
        
        # Create feature matrix
        self.X = self.df[available_features].copy()
        self.y = self.df['is_winner'].copy()
        self.feature_names = available_features
        
        # Handle missing values
        self.X = self.X.fillna(0)
        
        # Remove any infinite values
        self.X = self.X.replace([np.inf, -np.inf], 0)
        
        print(f"📊 Feature matrix shape: {self.X.shape}")
        
        # Store original dataframe for race predictions
        self.df_original = self.df.copy()
        
    def train_model(self):
        """Train the XGBoost model with proper parameters"""
        print("🚀 Training XGBoost model...")
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            self.X, self.y, test_size=0.2, random_state=42, stratify=self.y
        )
        
        # Calculate class weights for imbalanced data
        class_counts = y_train.value_counts()
        scale_pos_weight = class_counts[0] / class_counts[1]
        
        print(f"📊 Training set: {len(X_train):,} samples")
        print(f"📊 Test set: {len(X_test):,} samples")
        print(f"⚖️ Class weight ratio: {scale_pos_weight:.2f}")
        
        # Create DMatrix for XGBoost
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dtest = xgb.DMatrix(X_test, label=y_test)
        
        # XGBoost parameters optimized for horse racing
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'max_depth': 6,
            'learning_rate': 0.1,
            'n_estimators': 1000,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'scale_pos_weight': scale_pos_weight,
            'random_state': 42,
            'n_jobs': -1
        }
        
        # Train with early stopping
        evals = [(dtrain, 'train'), (dtest, 'test')]
        self.model = xgb.train(
            params, 
            dtrain, 
            num_boost_round=1000,
            evals=evals,
            early_stopping_rounds=50,
            verbose_eval=100
        )
        
        # Make predictions
        y_pred_proba = self.model.predict(dtest)
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        # Evaluate
        test_accuracy = accuracy_score(y_test, y_pred)
        test_logloss = log_loss(y_test, y_pred_proba)
        
        print(f"✅ Model trained successfully!")
        print(f"📊 Test Accuracy: {test_accuracy:.3f}")
        print(f"📊 Test Log Loss: {test_logloss:.3f}")
        
        return X_test, y_test, y_pred_proba, y_pred
        
    def analyze_feature_importance(self):
        """Analyze and display feature importance"""
        print("🔍 Analyzing feature importance...")
        
        # Get feature importance using different methods
        importance_weight = self.model.get_score(importance_type='weight')
        importance_gain = self.model.get_score(importance_type='gain')
        importance_cover = self.model.get_score(importance_type='cover')
        
        # Create importance dataframe
        importance_data = []
        for i, feature in enumerate(self.feature_names):
            importance_data.append({
                'feature': feature,
                'weight': importance_weight.get(f'f{i}', 0),
                'gain': importance_gain.get(f'f{i}', 0),
                'cover': importance_cover.get(f'f{i}', 0)
            })
        
        importance_df = pd.DataFrame(importance_data).sort_values('weight', ascending=False)
        
        print("\n📊 Top 10 Most Important Features (by weight):")
        print(importance_df.head(10)[['feature', 'weight', 'gain']].to_string(index=False))
        
        # Plot feature importance
        try:
            plt.figure(figsize=(12, 8))
            top_features = importance_df.head(15)
            sns.barplot(data=top_features, x='weight', y='feature')
            plt.title('Top 15 Feature Importance (Weight)')
            plt.xlabel('Importance (Weight)')
            plt.tight_layout()
            plt.savefig('feature_importance.png', dpi=300, bbox_inches='tight')
            print("📊 Feature importance plot saved as 'feature_importance.png'")
        except Exception as e:
            print(f"⚠️ Could not create plot: {e}")
        
        return importance_df
        
    def predict_race_probabilities(self, race_data=None):
        """Predict win probabilities for a specific race"""
        if race_data is None:
            # Use a sample race from the original data
            race_groups = self.df_original.groupby(['meetingName', 'meetingDate', 'raceNumber'])
            sample_race_key = list(race_groups.groups.keys())[0]
            race_data = race_groups.get_group(sample_race_key).copy()
        
        print(f"🏇 Predicting race: {race_data['meetingName'].iloc[0]} - Race {race_data['raceNumber'].iloc[0]}")
        
        # Prepare features
        X_race = race_data[self.feature_names].fillna(0)
        X_race = X_race.replace([np.inf, -np.inf], 0)
        
        # Make predictions
        drace = xgb.DMatrix(X_race)
        win_probabilities = self.model.predict(drace)
        
        # Create results dataframe
        results = pd.DataFrame({
            'Horse': race_data['runnerName'].values,
            'Jockey': race_data['riderName'].values,
            'Odds': race_data['FixedWinClose_Reference'].values,
            'Win_Probability': win_probabilities,
            'Actual_Position': race_data['finishingPosition'].values
        }).sort_values('Win_Probability', ascending=False)
        
        print("\n🏆 Race Predictions:")
        print(results.to_string(index=False, float_format='%.3f'))
        
        return results
        
    def save_model(self, model_path="horse_racing_model.pkl"):
        """Save the trained model and feature names"""
        try:
            model_data = {
                'model': self.model,
                'feature_names': self.feature_names,
                'feature_importance': self.get_feature_importance_dict()
            }
            
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            print(f"✅ Model saved to {model_path}")
            return True
        except Exception as e:
            print(f"❌ Error saving model: {e}")
            return False
            
    def get_feature_importance_dict(self):
        """Get feature importance as dictionary"""
        try:
            importance_weight = self.model.get_score(importance_type='weight')
            importance_gain = self.model.get_score(importance_type='gain')
            
            importance_dict = {}
            for i, feature in enumerate(self.feature_names):
                importance_dict[feature] = {
                    'weight': importance_weight.get(f'f{i}', 0),
                    'gain': importance_gain.get(f'f{i}', 0)
                }
            
            return importance_dict
        except Exception as e:
            print(f"⚠️ Error getting feature importance: {e}")
            return {}
        
    def evaluate_model_performance(self, X_test, y_test, y_pred_proba):
        """Comprehensive model evaluation"""
        print("📊 Evaluating model performance...")
        
        # Basic metrics
        y_pred = (y_pred_proba > 0.5).astype(int)
        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_pred_proba)
        
        print(f"📈 Accuracy: {accuracy:.3f}")
        print(f"📈 Log Loss: {logloss:.3f}")
        
        # Classification report
        print("\n📊 Classification Report:")
        print(classification_report(y_test, y_pred, target_names=['Lose', 'Win']))
        
        # Probability distribution analysis
        print(f"\n📊 Probability Statistics:")
        print(f"   Mean predicted probability: {y_pred_proba.mean():.3f}")
        print(f"   Std predicted probability: {y_pred_proba.std():.3f}")
        print(f"   Min predicted probability: {y_pred_proba.min():.3f}")
        print(f"   Max predicted probability: {y_pred_proba.max():.3f}")
        
        return {
            'accuracy': accuracy,
            'logloss': logloss,
            'mean_prob': y_pred_proba.mean(),
            'std_prob': y_pred_proba.std()
        }
        
    def run_complete_analysis(self):
        """Run the complete analysis pipeline"""
        print("🚀 Starting Horse Racing Prediction Analysis")
        print("=" * 50)
        
        # Load and clean data
        self.load_and_clean_data()
        
        # Create target variable
        self.create_target_variable()
        
        # Select features
        self.select_features()
        
        # Train model
        X_test, y_test, y_pred_proba, y_pred = self.train_model()
        
        # Analyze feature importance
        importance_df = self.analyze_feature_importance()
        
        # Evaluate performance
        metrics = self.evaluate_model_performance(X_test, y_test, y_pred_proba)
        
        # Predict sample race
        print("\n" + "=" * 50)
        print("🏇 SAMPLE RACE PREDICTION")
        print("=" * 50)
        race_predictions = self.predict_race_probabilities()
        
        # Save the trained model
        self.save_model()
        
        print("\n✅ Analysis complete!")
        return {
            'model': self.model,
            'feature_importance': importance_df,
            'metrics': metrics,
            'race_predictions': race_predictions
        }

def main():
    """Main function to run the analysis"""
    csv_path = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    # Create predictor
    predictor = HorseRacingPredictor(csv_path)
    
    # Run complete analysis
    results = predictor.run_complete_analysis()
    
    return results

if __name__ == "__main__":
    results = main()
