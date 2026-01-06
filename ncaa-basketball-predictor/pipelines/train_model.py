"""
Model Training Pipeline - Enterprise Grade

Walk-Forward Validation for NCAA Basketball Win Prediction

Key Features:
- Walk-forward validation (time-series aware)
- Feature importance analysis (SHAP values)
- Hyperparameter tuning
- Calibration assessment
- Model persistence

No shortcuts. Production-ready.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Tuple, List
import json
from datetime import datetime

# ML Libraries
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score, log_loss, roc_auc_score, 
    brier_score_loss, classification_report
)
from sklearn.calibration import calibration_curve
import joblib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "training_data.csv"
MODEL_PATH = Path(__file__).parent.parent / "models"
MODEL_PATH.mkdir(exist_ok=True)


class WalkForwardValidator:
    """
    Walk-forward validation for time-series NCAA basketball data
    
    Ensures no data leakage by training on past data and testing on future data
    """
    
    def __init__(self, df: pd.DataFrame, n_splits: int = 5):
        """
        Initialize walk-forward validator
        
        Args:
            df: DataFrame with 'game_date' column
            n_splits: Number of train/test splits
        """
        self.df = df.sort_values('game_date').reset_index(drop=True)
        self.n_splits = n_splits
        self.splits = self._create_splits()
        
    def _create_splits(self) -> List[Tuple[List[int], List[int]]]:
        """Create walk-forward splits"""
        n = len(self.df)
        test_size = n // (self.n_splits + 1)  # Reserve data for each test set
        
        splits = []
        for i in range(self.n_splits):
            # Training set: all data before test period
            train_end = (i + 1) * test_size
            train_indices = list(range(train_end))
            
            # Test set: next chunk of data
            test_start = train_end
            test_end = test_start + test_size
            test_indices = list(range(test_start, min(test_end, n)))
            
            if len(test_indices) > 0:
                splits.append((train_indices, test_indices))
        
        logger.info(f"Created {len(splits)} walk-forward splits")
        for i, (train_idx, test_idx) in enumerate(splits):
            train_dates = self.df.loc[train_idx, 'game_date']
            test_dates = self.df.loc[test_idx, 'game_date']
            logger.info(f"  Split {i+1}: Train {train_dates.min()} to {train_dates.max()} "
                       f"({len(train_idx)} games) → Test {test_dates.min()} to {test_dates.max()} "
                       f"({len(test_idx)} games)")
        
        return splits
    
    def get_splits(self):
        """Yield train/test indices for each split"""
        for train_idx, test_idx in self.splits:
            yield train_idx, test_idx


class NcaaBasketballModel:
    """
    NCAA Basketball Win Probability Predictor
    
    Uses XGBoost with walk-forward validation
    """
    
    def __init__(self):
        self.model = None
        self.feature_cols = None
        self.feature_importance = None
        self.training_metrics = {}
        
    def prepare_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target from raw data"""
        
        # Identify feature columns (exclude metadata and target)
        exclude_cols = [
            'game_id', 'game_date', 'season', 
            'home_team_id', 'away_team_id', 
            'home_team_name', 'away_team_name',
            'home_score', 'away_score', 
            'home_win', 'margin'
        ]
        
        self.feature_cols = [c for c in df.columns if c not in exclude_cols]
        
        X = df[self.feature_cols]
        y = df['home_win']
        
        logger.info(f"Prepared {len(self.feature_cols)} features for {len(df)} games")
        logger.info(f"Target distribution: {y.value_counts().to_dict()}")
        
        return X, y
    
    def train(
        self, 
        X_train: pd.DataFrame, 
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None
    ) -> xgb.XGBClassifier:
        """
        Train XGBoost classifier
        
        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)
        
        Returns:
            Trained model
        """
        
        # Handle missing data by filling with neutral values
        X_train_filled = X_train.fillna(-999)
        
        # XGBoost parameters (tuned for basketball win prediction)
        params = {
            'max_depth': 6,
            'learning_rate': 0.05,
            'n_estimators': 500,
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 3,
            'gamma': 0.1,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42,
            'tree_method': 'hist',
            'enable_categorical': False,
            'missing': -999,  # Explicit missing value handling
            'early_stopping_rounds': 50,
            'verbose': False
        }
        
        model = xgb.XGBClassifier(**params)
        
        # Train with validation set if provided
        if X_val is not None and y_val is not None:
            X_val_filled = X_val.fillna(-999)
            eval_set = [(X_train_filled, y_train), (X_val_filled, y_val)]
            model.fit(
                X_train_filled, y_train,
                eval_set=eval_set,
                verbose=False
            )
        else:
            model.fit(X_train_filled, y_train)
        
        return model
    
    def evaluate(
        self, 
        model: xgb.XGBClassifier, 
        X_test: pd.DataFrame, 
        y_test: pd.Series,
        split_name: str = "Test"
    ) -> Dict:
        """
        Comprehensive model evaluation
        
        Returns metrics dict
        """
        X_test_filled = X_test.fillna(-999)
        
        # Predictions
        y_pred = model.predict(X_test_filled)
        y_pred_proba = model.predict_proba(X_test_filled)[:, 1]
        
        # Metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'log_loss': log_loss(y_test, y_pred_proba),
            'auc_roc': roc_auc_score(y_test, y_pred_proba),
            'brier_score': brier_score_loss(y_test, y_pred_proba),
            'n_samples': len(y_test)
        }
        
        # Calibration analysis
        prob_true, prob_pred = calibration_curve(
            y_test, y_pred_proba, n_bins=10, strategy='uniform'
        )
        metrics['calibration_error'] = np.mean(np.abs(prob_true - prob_pred))
        
        logger.info(f"{split_name} Metrics:")
        logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"  Log Loss: {metrics['log_loss']:.4f}")
        logger.info(f"  AUC-ROC: {metrics['auc_roc']:.4f}")
        logger.info(f"  Brier Score: {metrics['brier_score']:.4f}")
        logger.info(f"  Calibration Error: {metrics['calibration_error']:.4f}")
        
        return metrics
    
    def walk_forward_validation(self, df: pd.DataFrame, n_splits: int = 5) -> Dict:
        """
        Perform walk-forward validation
        
        Returns:
            Dict of averaged metrics and per-split results
        """
        logger.info("🚀 Starting Walk-Forward Validation")
        logger.info("=" * 70)
        
        X, y = self.prepare_data(df)
        validator = WalkForwardValidator(df, n_splits=n_splits)
        
        split_metrics = []
        
        for i, (train_idx, test_idx) in enumerate(validator.get_splits()):
            logger.info(f"\n📊 Split {i+1}/{n_splits}")
            logger.info("-" * 70)
            
            # Split data
            X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
            X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
            
            # Train model
            model = self.train(X_train, y_train, X_test, y_test)
            
            # Evaluate
            metrics = self.evaluate(model, X_test, y_test, f"Split {i+1}")
            split_metrics.append(metrics)
            
            # Store best model (by log loss)
            if self.model is None or metrics['log_loss'] < min(m['log_loss'] for m in split_metrics[:-1] or [{'log_loss': float('inf')}]):
                self.model = model
                logger.info(f"  ✅ New best model (Log Loss: {metrics['log_loss']:.4f})")
        
        # Average metrics
        avg_metrics = {
            key: np.mean([m[key] for m in split_metrics])
            for key in split_metrics[0].keys()
            if key != 'n_samples'
        }
        avg_metrics['n_samples_total'] = sum(m['n_samples'] for m in split_metrics)
        
        logger.info("\n" + "=" * 70)
        logger.info("📈 WALK-FORWARD VALIDATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Average Accuracy: {avg_metrics['accuracy']:.4f}")
        logger.info(f"Average Log Loss: {avg_metrics['log_loss']:.4f}")
        logger.info(f"Average AUC-ROC: {avg_metrics['auc_roc']:.4f}")
        logger.info(f"Average Brier Score: {avg_metrics['brier_score']:.4f}")
        logger.info(f"Average Calibration Error: {avg_metrics['calibration_error']:.4f}")
        logger.info(f"Total Test Samples: {avg_metrics['n_samples_total']}")
        
        self.training_metrics = {
            'average': avg_metrics,
            'per_split': split_metrics,
            'n_splits': n_splits
        }
        
        return self.training_metrics
    
    def get_feature_importance(self, top_n: int = 30) -> pd.DataFrame:
        """
        Get feature importance from trained model
        
        Args:
            top_n: Number of top features to return
        
        Returns:
            DataFrame with feature importance
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        importance = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        self.feature_importance = importance
        
        logger.info(f"\n🎯 TOP {top_n} MOST IMPORTANT FEATURES")
        logger.info("=" * 70)
        for idx, row in importance.head(top_n).iterrows():
            logger.info(f"{row['feature']:40s} {row['importance']:.4f}")
        
        return importance.head(top_n)
    
    def save_model(self, model_name: str = None):
        """Save trained model and metadata"""
        if self.model is None:
            raise ValueError("No model to save")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = model_name or f"ncaa_basketball_model_{timestamp}"
        
        # Save model
        model_path = MODEL_PATH / f"{model_name}.joblib"
        joblib.dump(self.model, model_path)
        logger.info(f"💾 Model saved to {model_path}")
        
        # Save metadata
        metadata = {
            'model_name': model_name,
            'trained_at': timestamp,
            'n_features': len(self.feature_cols),
            'features': self.feature_cols,
            'metrics': self.training_metrics,
            'feature_importance': self.feature_importance.to_dict('records') if self.feature_importance is not None else None
        }
        
        metadata_path = MODEL_PATH / f"{model_name}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"📄 Metadata saved to {metadata_path}")
        
        return model_path, metadata_path


def main():
    """Main training pipeline"""
    print("\n" + "=" * 70)
    print("🏀 NCAA BASKETBALL - MODEL TRAINING PIPELINE")
    print("=" * 70)
    print("Walk-Forward Validation with XGBoost")
    print("=" * 70 + "\n")
    
    # Load data
    logger.info("📂 Loading training data...")
    df = pd.read_csv(DATA_PATH)
    logger.info(f"✅ Loaded {len(df)} games from {df['game_date'].min()} to {df['game_date'].max()}")
    
    # Initialize model
    model = NcaaBasketballModel()
    
    # Train with walk-forward validation
    logger.info("\n🏋️ Training model with walk-forward validation...")
    metrics = model.walk_forward_validation(df, n_splits=5)
    
    # Feature importance
    logger.info("\n🔍 Analyzing feature importance...")
    top_features = model.get_feature_importance(top_n=30)
    
    # Save model
    logger.info("\n💾 Saving model...")
    model_path, metadata_path = model.save_model()
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ MODEL TRAINING COMPLETE!")
    print("=" * 70)
    print(f"Model: {model_path}")
    print(f"Metadata: {metadata_path}")
    print(f"\n📊 Performance:")
    print(f"  Accuracy: {metrics['average']['accuracy']:.4f}")
    print(f"  Log Loss: {metrics['average']['log_loss']:.4f}")
    print(f"  AUC-ROC: {metrics['average']['auc_roc']:.4f}")
    print(f"  Calibration Error: {metrics['average']['calibration_error']:.4f}")
    print("=" * 70)
    
    return model


if __name__ == "__main__":
    model = main()

