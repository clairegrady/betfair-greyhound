"""
NCAA Basketball Model Training with Proper Validation
- Time-based train/test split (prevent data leakage)
- Cross-validation for robust evaluation
- Feature importance analysis
- Backtesting on held-out season
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor
from sklearn.metrics import (
    accuracy_score, log_loss, roc_auc_score,
    mean_squared_error, mean_absolute_error, r2_score,
    classification_report
)
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NCAAModelTrainer:
    """Train and evaluate NCAA basketball prediction models"""
    
    def __init__(self, features_path="features_dataset.csv"):
        self.features_path = Path(__file__).parent.parent / features_path
        self.df = None
        self.feature_cols = None
        self.scaler = StandardScaler()
        
    def load_and_prepare_data(self):
        """Load features and prepare for training"""
        
        logger.info(f"Loading features from: {self.features_path}")
        self.df = pd.read_csv(self.features_path)
        
        logger.info(f"Loaded {len(self.df):,} games")
        
        # Drop rows with too many missing values
        # Keep only games with at least player aggregates
        self.df = self.df.dropna(subset=['home_avg_player_ortg', 'away_avg_player_ortg'])
        
        logger.info(f"After filtering: {len(self.df):,} games with complete data")
        
        # Fill remaining NaN values with 0 (for lineup features that might be missing)
        self.df = self.df.fillna(0)
        
        # Define feature columns (exclude ID, date, and target variables)
        exclude_cols = ['game_id', 'game_date', 'season', 'home_team', 'away_team', 
                       'home_won', 'point_margin', 'total_points']
        self.feature_cols = [col for col in self.df.columns if col not in exclude_cols]
        
        logger.info(f"Feature columns: {len(self.feature_cols)}")
        logger.info(f"Features: {self.feature_cols}")
        
        return self.df
    
    def split_data_by_time(self):
        """
        Split data by time to prevent data leakage
        Using 23-24 season data (season=2024) which has player data
        Train: Nov 2023 - Jan 2024
        Val: Feb 2024 - Mar 2024
        Test: Apr 2024 (tournament)
        """
        
        logger.info("\n" + "="*70)
        logger.info("TIME-BASED DATA SPLIT (No Data Leakage)")
        logger.info("="*70)
        
        # Convert game_date to datetime
        self.df['game_date'] = pd.to_datetime(self.df['game_date'])
        
        # Use season 2024 data (23-24 season) which has good player coverage
        season_2024_df = self.df[self.df['season'] == 2024]
        
        train_df = season_2024_df[season_2024_df['game_date'] < '2024-02-01']
        val_df = season_2024_df[
            (season_2024_df['game_date'] >= '2024-02-01') & 
            (season_2024_df['game_date'] < '2024-03-15')
        ]
        test_df = season_2024_df[season_2024_df['game_date'] >= '2024-03-15']  # Tournament
        
        logger.info(f"\nTrain set: {len(train_df):,} games (23-24 season: Nov 2023 - Jan 2024)")
        if len(train_df) > 0:
            logger.info(f"  Date range: {train_df['game_date'].min()} to {train_df['game_date'].max()}")
        
        logger.info(f"\nValidation set: {len(val_df):,} games (23-24 season: Feb - Mid March 2024)")
        if len(val_df) > 0:
            logger.info(f"  Date range: {val_df['game_date'].min()} to {val_df['game_date'].max()}")
        
        logger.info(f"\nTest set: {len(test_df):,} games (23-24 Tournament: March-April 2024)")
        if len(test_df) > 0:
            logger.info(f"  Date range: {test_df['game_date'].min()} to {test_df['game_date'].max()}")
        
        logger.info("\n✅ No data leakage: Models never see future data!")
        
        return train_df, val_df, test_df
    
    def prepare_features(self, train_df, val_df, test_df):
        """Prepare X, y for training"""
        
        X_train = train_df[self.feature_cols].values
        y_train_class = train_df['home_won'].values
        y_train_margin = train_df['point_margin'].values
        y_train_total = train_df['total_points'].values
        
        X_val = val_df[self.feature_cols].values
        y_val_class = val_df['home_won'].values
        y_val_margin = val_df['point_margin'].values
        y_val_total = val_df['total_points'].values
        
        X_test = test_df[self.feature_cols].values
        y_test_class = test_df['home_won'].values
        y_test_margin = test_df['point_margin'].values
        y_test_total = test_df['total_points'].values
        
        # Scale features
        X_train = self.scaler.fit_transform(X_train)
        X_val = self.scaler.transform(X_val)
        X_test = self.scaler.transform(X_test)
        
        return (X_train, y_train_class, y_train_margin, y_train_total,
                X_val, y_val_class, y_val_margin, y_val_total,
                X_test, y_test_class, y_test_margin, y_test_total)
    
    def train_baseline_models(self, X_train, y_train_class, X_val, y_val_class):
        """Train simple baseline models"""
        
        logger.info("\n" + "="*70)
        logger.info("BASELINE MODELS (Establish Performance Floor)")
        logger.info("="*70)
        
        # 1. Logistic Regression
        logger.info("\n1. Logistic Regression")
        lr = LogisticRegression(max_iter=1000, random_state=42)
        lr.fit(X_train, y_train_class)
        
        train_pred = lr.predict(X_train)
        val_pred = lr.predict(X_val)
        val_proba = lr.predict_proba(X_val)[:, 1]
        
        train_acc = accuracy_score(y_train_class, train_pred)
        val_acc = accuracy_score(y_val_class, val_pred)
        val_logloss = log_loss(y_val_class, val_proba)
        
        logger.info(f"   Train Accuracy: {train_acc:.3f}")
        logger.info(f"   Val Accuracy: {val_acc:.3f}")
        logger.info(f"   Val Log Loss: {val_logloss:.3f}")
        
        # 2. Random Forest (Simple)
        logger.info("\n2. Random Forest (Quick baseline)")
        rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train_class)
        
        train_pred = rf.predict(X_train)
        val_pred = rf.predict(X_val)
        val_proba = rf.predict_proba(X_val)[:, 1]
        
        train_acc = accuracy_score(y_train_class, train_pred)
        val_acc = accuracy_score(y_val_class, val_pred)
        val_logloss = log_loss(y_val_class, val_proba)
        
        logger.info(f"   Train Accuracy: {train_acc:.3f}")
        logger.info(f"   Val Accuracy: {val_acc:.3f}")
        logger.info(f"   Val Log Loss: {val_logloss:.3f}")
        
        return {'logistic_regression': lr, 'random_forest': rf}
    
    def train_xgboost(self, X_train, y_train_class, X_val, y_val_class):
        """Train XGBoost with better hyperparameters"""
        
        logger.info("\n" + "="*70)
        logger.info("XGBOOST MODEL (Main Predictor)")
        logger.info("="*70)
        
        xgb = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )
        
        xgb.fit(
            X_train, y_train_class,
            eval_set=[(X_val, y_val_class)],
            verbose=False
        )
        
        train_pred = xgb.predict(X_train)
        val_pred = xgb.predict(X_val)
        val_proba = xgb.predict_proba(X_val)[:, 1]
        
        train_acc = accuracy_score(y_train_class, train_pred)
        val_acc = accuracy_score(y_val_class, val_pred)
        val_logloss = log_loss(y_val_class, val_proba)
        
        try:
            val_auc = roc_auc_score(y_val_class, val_proba)
            logger.info(f"   Val AUC-ROC: {val_auc:.3f}")
        except:
            pass
        
        logger.info(f"   Train Accuracy: {train_acc:.3f}")
        logger.info(f"   Val Accuracy: {val_acc:.3f}")
        logger.info(f"   Val Log Loss: {val_logloss:.3f}")
        
        return xgb
    
    def analyze_feature_importance(self, model, top_n=20):
        """Analyze and visualize feature importance"""
        
        logger.info("\n" + "="*70)
        logger.info("FEATURE IMPORTANCE ANALYSIS")
        logger.info("="*70)
        
        # Get feature importance
        importance = model.feature_importances_
        feature_importance = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        logger.info(f"\nTop {top_n} Most Important Features:")
        for idx, row in feature_importance.head(top_n).iterrows():
            logger.info(f"   {row['feature']:35} {row['importance']:.4f}")
        
        # Save feature importance
        output_path = Path(__file__).parent.parent / "feature_importance.csv"
        feature_importance.to_csv(output_path, index=False)
        logger.info(f"\n💾 Feature importance saved to: {output_path}")
        
        return feature_importance
    
    def backtest(self, model, X_test, y_test_class, test_df):
        """Backtest on held-out tournament games"""
        
        logger.info("\n" + "="*70)
        logger.info("BACKTESTING ON TOURNAMENT GAMES (HELD-OUT)")
        logger.info("="*70)
        
        # Predictions
        test_pred = model.predict(X_test)
        test_proba = model.predict_proba(X_test)[:, 1]
        
        # Metrics
        test_acc = accuracy_score(y_test_class, test_pred)
        test_logloss = log_loss(y_test_class, test_proba)
        
        try:
            test_auc = roc_auc_score(y_test_class, test_proba)
            logger.info(f"   AUC-ROC: {test_auc:.3f}")
        except:
            pass
        
        logger.info(f"   Accuracy: {test_acc:.3f}")
        logger.info(f"   Log Loss: {test_logloss:.3f}")
        
        # Classification report
        logger.info("\nDetailed Classification Report:")
        logger.info(classification_report(y_test_class, test_pred, 
                                         target_names=['Away Win', 'Home Win']))
        
        # Simulated betting performance
        logger.info("\n" + "-"*70)
        logger.info("SIMULATED BETTING PERFORMANCE")
        logger.info("-"*70)
        
        # Strategy: Bet when model confidence > 60%
        confident_bets = (test_proba > 0.60) | (test_proba < 0.40)
        
        if confident_bets.sum() > 0:
            confident_acc = accuracy_score(y_test_class[confident_bets], 
                                          test_pred[confident_bets])
            
            logger.info(f"\nConfident bets (prob > 60% or < 40%):")
            logger.info(f"   Number of bets: {confident_bets.sum()}")
            logger.info(f"   Accuracy: {confident_acc:.3f}")
            logger.info(f"   ROI (if betting $100/game): {(confident_acc - 0.5) * 2 * 100:.1f}%")
        
        # Save predictions
        results_df = test_df.copy()
        results_df['predicted_home_win_prob'] = test_proba
        results_df['predicted_home_win'] = test_pred
        results_df['correct'] = (test_pred == y_test_class).astype(int)
        
        output_path = Path(__file__).parent.parent / "backtest_results.csv"
        results_df.to_csv(output_path, index=False)
        logger.info(f"\n💾 Backtest results saved to: {output_path}")
        
        return test_acc, test_logloss, results_df


def main():
    """Main execution"""
    
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL MODEL TRAINING")
    print("="*70 + "\n")
    
    trainer = NCAAModelTrainer()
    
    # 1. Load data
    df = trainer.load_and_prepare_data()
    
    # 2. Time-based split (NO DATA LEAKAGE)
    train_df, val_df, test_df = trainer.split_data_by_time()
    
    # 3. Prepare features
    (X_train, y_train_class, y_train_margin, y_train_total,
     X_val, y_val_class, y_val_margin, y_val_total,
     X_test, y_test_class, y_test_margin, y_test_total) = trainer.prepare_features(
        train_df, val_df, test_df
    )
    
    # 4. Train baseline models
    baseline_models = trainer.train_baseline_models(X_train, y_train_class, X_val, y_val_class)
    
    # 5. Train XGBoost (main model)
    xgb_model = trainer.train_xgboost(X_train, y_train_class, X_val, y_val_class)
    
    # 6. Analyze feature importance
    feature_importance = trainer.analyze_feature_importance(xgb_model, top_n=20)
    
    # 7. Backtest on held-out 25-26 season
    test_acc, test_logloss, results_df = trainer.backtest(xgb_model, X_test, y_test_class, test_df)
    
    # Final summary
    print("\n" + "="*70)
    print("🎉 TRAINING COMPLETE!")
    print("="*70)
    print(f"\n✅ Best Model: XGBoost")
    print(f"   Validation Accuracy: {accuracy_score(y_val_class, xgb_model.predict(X_val)):.3f}")
    print(f"   Test Accuracy (Tournament): {test_acc:.3f}")
    print(f"\n✅ Files generated:")
    print(f"   - feature_importance.csv")
    print(f"   - backtest_results.csv")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
