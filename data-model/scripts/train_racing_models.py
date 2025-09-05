#!/usr/bin/env python3
"""
Racing Model Training Script
Trains multiple models for win/place/show prediction using engineered features
"""

import pandas as pd
import numpy as np
import sqlite3
import logging
from datetime import datetime
import joblib
import os
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
FEATURE_FILE = 'rpscrape_features.parquet'
MODEL_OUTPUT_DIR = 'trained_models'
TRAIN_START = '2020-01-01'
TRAIN_END = '2023-12-31'
TEST_START = '2024-01-01'
TEST_END = '2025-08-09'

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('train_racing_models.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_output_dir():
    """Create output directory for models"""
    os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)
    os.makedirs(f'{MODEL_OUTPUT_DIR}/plots', exist_ok=True)

def load_features():
    """Load the engineered features"""
    logger.info("📊 Loading engineered features...")
    
    try:
        df = pd.read_parquet(FEATURE_FILE)
        logger.info(f"✅ Loaded {len(df):,} records with {len(df.columns)} columns")
        
        # Convert date column
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    except Exception as e:
        logger.error(f"❌ Error loading features: {e}")
        return None

def prepare_data_splits(df):
    """Split data into train/validation/test sets by date"""
    logger.info("📅 Creating temporal data splits...")
    
    # Create train/test splits based on dates
    train_data = df[
        (df['date'] >= TRAIN_START) & 
        (df['date'] <= TRAIN_END)
    ].copy()
    
    test_data = df[
        (df['date'] >= TEST_START) & 
        (df['date'] <= TEST_END)
    ].copy()
    
    logger.info(f"📊 Data splits:")
    logger.info(f"   Training: {len(train_data):,} records ({TRAIN_START} to {TRAIN_END})")
    logger.info(f"   Testing: {len(test_data):,} records ({TEST_START} to {TEST_END})")
    
    # Show target distributions
    for target in ['target_win', 'target_place', 'target_show']:
        train_rate = train_data[target].mean()
        test_rate = test_data[target].mean()
        logger.info(f"   {target}: Train={train_rate:.3f}, Test={test_rate:.3f}")
    
    return train_data, test_data

def select_features(df):
    """Select features for modeling"""
    logger.info("🎯 Selecting features for modeling...")
    
    # Exclude non-feature columns
    exclude_cols = [
        'date', 'course', 'race_name', 'horse_name', 'jockey', 'trainer', 'finishing_position',
        'target_win', 'target_place', 'target_show'
    ]
    
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    # Remove highly correlated features
    correlation_matrix = df[feature_cols].corr().abs()
    high_corr_pairs = []
    
    for i in range(len(correlation_matrix.columns)):
        for j in range(i+1, len(correlation_matrix.columns)):
            if correlation_matrix.iloc[i, j] > 0.95:  # Very high correlation
                high_corr_pairs.append((correlation_matrix.columns[i], correlation_matrix.columns[j]))
    
    # Remove one feature from each highly correlated pair
    features_to_remove = set()
    for pair in high_corr_pairs:
        features_to_remove.add(pair[1])  # Remove the second feature
    
    final_features = [col for col in feature_cols if col not in features_to_remove]
    
    logger.info(f"📋 Selected {len(final_features)} features (removed {len(features_to_remove)} highly correlated)")
    if features_to_remove:
        logger.info(f"   Removed: {list(features_to_remove)[:5]}...")
    
    return final_features

def train_model(X_train, y_train, X_test, y_test, target_name, model_type='rf'):
    """Train a single model"""
    logger.info(f"🤖 Training {model_type.upper()} model for {target_name}...")
    
    # Initialize model
    if model_type == 'rf':
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1
        )
    elif model_type == 'gbm':
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42
        )
    elif model_type == 'xgb':
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss',
            n_jobs=-1
        )
    elif model_type == 'lr':
        # Scale features for logistic regression
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        model = LogisticRegression(
            max_iter=1000,
            random_state=42
        )
        
        # Train and predict
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)
        y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
        
        # Save scaler
        scaler_path = f'{MODEL_OUTPUT_DIR}/{target_name}_{model_type}_scaler.joblib'
        joblib.dump(scaler, scaler_path)
        
        # Calculate metrics
        auc_score = roc_auc_score(y_test, y_pred_proba)
        
        # Save model
        model_path = f'{MODEL_OUTPUT_DIR}/{target_name}_{model_type}_model.joblib'
        joblib.dump(model, model_path)
        
        logger.info(f"   ✅ {model_type.upper()} AUC: {auc_score:.4f}")
        
        return model, auc_score, y_pred, y_pred_proba
    
    # For tree-based models (including XGBoost)
    if model_type == 'xgb':
        # XGBoost with early stopping
        eval_set = [(X_test, y_test)]
        model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
    else:
        model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    # Calculate metrics
    auc_score = roc_auc_score(y_test, y_pred_proba)
    
    # Save model
    model_path = f'{MODEL_OUTPUT_DIR}/{target_name}_{model_type}_model.joblib'
    joblib.dump(model, model_path)
    
    logger.info(f"   ✅ {model_type.upper()} AUC: {auc_score:.4f}")
    
    return model, auc_score, y_pred, y_pred_proba

def evaluate_model(y_test, y_pred, y_pred_proba, target_name, model_type):
    """Evaluate model performance"""
    logger.info(f"📊 Evaluating {model_type.upper()} model for {target_name}...")
    
    # Classification metrics
    auc_score = roc_auc_score(y_test, y_pred_proba)
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    
    # Classification report
    report = classification_report(y_test, y_pred, output_dict=True)
    
    logger.info(f"   AUC Score: {auc_score:.4f}")
    logger.info(f"   Precision: {report['1']['precision']:.4f}")
    logger.info(f"   Recall: {report['1']['recall']:.4f}")
    logger.info(f"   F1-Score: {report['1']['f1-score']:.4f}")
    
    # Save detailed results
    results = {
        'target': target_name,
        'model_type': model_type,
        'auc_score': auc_score,
        'precision': report['1']['precision'],
        'recall': report['1']['recall'],
        'f1_score': report['1']['f1-score'],
        'confusion_matrix': cm.tolist()
    }
    
    return results

def plot_feature_importance(model, feature_names, target_name, model_type, X_test=None):
    """Plot feature importance using both built-in and SHAP methods"""
    
    # Built-in feature importance for tree-based models
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        
        # Create feature importance dataframe
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        # Plot top 20 features
        plt.figure(figsize=(12, 8))
        top_features = importance_df.head(20)
        sns.barplot(data=top_features, x='importance', y='feature', palette='viridis')
        plt.title(f'Built-in Feature Importance - {target_name.upper()} ({model_type.upper()})')
        plt.xlabel('Importance')
        plt.tight_layout()
        
        # Save plot
        plot_path = f'{MODEL_OUTPUT_DIR}/plots/{target_name}_{model_type}_builtin_importance.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"   📊 Built-in importance plot saved: {plot_path}")
        
        # Save importance data
        importance_path = f'{MODEL_OUTPUT_DIR}/{target_name}_{model_type}_builtin_importance.csv'
        importance_df.to_csv(importance_path, index=False)
    
    # SHAP analysis for tree-based models
    if model_type in ['rf', 'gbm', 'xgb'] and X_test is not None:
        try:
            logger.info(f"   🧠 Computing SHAP values for {model_type.upper()}...")
            
            # Sample data for SHAP (computationally intensive)
            sample_size = min(1000, len(X_test))
            X_sample = X_test.sample(n=sample_size, random_state=42)
            
            # Create SHAP explainer
            if model_type == 'xgb':
                explainer = shap.TreeExplainer(model)
            else:
                explainer = shap.TreeExplainer(model)
            
            # Calculate SHAP values
            shap_values = explainer.shap_values(X_sample)
            
            # For binary classification, use the positive class SHAP values
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Positive class
            
            # SHAP summary plot
            plt.figure(figsize=(12, 8))
            shap.summary_plot(shap_values, X_sample, feature_names=feature_names, 
                            show=False, max_display=20)
            plt.title(f'SHAP Feature Importance - {target_name.upper()} ({model_type.upper()})')
            plt.tight_layout()
            
            # Save SHAP summary plot
            shap_plot_path = f'{MODEL_OUTPUT_DIR}/plots/{target_name}_{model_type}_shap_summary.png'
            plt.savefig(shap_plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # SHAP bar plot (mean absolute SHAP values)
            plt.figure(figsize=(12, 8))
            shap.summary_plot(shap_values, X_sample, feature_names=feature_names, 
                            plot_type="bar", show=False, max_display=20)
            plt.title(f'SHAP Mean Importance - {target_name.upper()} ({model_type.upper()})')
            plt.tight_layout()
            
            shap_bar_path = f'{MODEL_OUTPUT_DIR}/plots/{target_name}_{model_type}_shap_bar.png'
            plt.savefig(shap_bar_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # Calculate mean absolute SHAP values for ranking
            shap_importance = np.abs(shap_values).mean(0)
            shap_df = pd.DataFrame({
                'feature': feature_names,
                'shap_importance': shap_importance
            }).sort_values('shap_importance', ascending=False)
            
            # Save SHAP importance data
            shap_path = f'{MODEL_OUTPUT_DIR}/{target_name}_{model_type}_shap_importance.csv'
            shap_df.to_csv(shap_path, index=False)
            
            logger.info(f"   📊 SHAP plots saved: {shap_plot_path}, {shap_bar_path}")
            logger.info(f"   📊 SHAP importance data saved: {shap_path}")
            
            return shap_df
            
        except Exception as e:
            logger.warning(f"   ⚠️ SHAP analysis failed for {model_type}: {e}")
            return None
    
    return importance_df if hasattr(model, 'feature_importances_') else None

def train_all_models():
    """Train models for all targets"""
    logger.info("🚀 Starting comprehensive model training...")
    
    create_output_dir()
    
    # Load data
    df = load_features()
    if df is None:
        return
    
    # Prepare data splits
    train_data, test_data = prepare_data_splits(df)
    
    # Select features
    feature_cols = select_features(train_data)
    
    # Prepare feature matrices
    X_train = train_data[feature_cols].fillna(0)
    X_test = test_data[feature_cols].fillna(0)
    
    logger.info(f"📊 Feature matrix: {X_train.shape}")
    
    # Train models for each target
    targets = ['target_win', 'target_place', 'target_show']
    model_types = ['rf', 'gbm', 'xgb', 'lr']
    
    all_results = []
    
    for target in targets:
        logger.info(f"\n🎯 === Training models for {target.upper()} ===")
        
        y_train = train_data[target]
        y_test = test_data[target]
        
        logger.info(f"📊 Target distribution: Train={y_train.mean():.3f}, Test={y_test.mean():.3f}")
        
        target_results = []
        
        for model_type in model_types:
            # Train model
            model, auc_score, y_pred, y_pred_proba = train_model(
                X_train, y_train, X_test, y_test, target, model_type
            )
            
            # Evaluate model
            results = evaluate_model(y_test, y_pred, y_pred_proba, target, model_type)
            target_results.append(results)
            all_results.append(results)
            
            # Plot feature importance (for tree-based models)
            if model_type in ['rf', 'gbm', 'xgb']:
                importance_df = plot_feature_importance(model, feature_cols, target, model_type, X_test)
        
        # Find best model for this target
        best_result = max(target_results, key=lambda x: x['auc_score'])
        logger.info(f"🏆 Best model for {target}: {best_result['model_type'].upper()} (AUC: {best_result['auc_score']:.4f})")
    
    # Save overall results
    results_df = pd.DataFrame(all_results)
    results_path = f'{MODEL_OUTPUT_DIR}/model_results_summary.csv'
    results_df.to_csv(results_path, index=False)
    
    # Create results summary
    logger.info("\n🎉 === TRAINING COMPLETE ===")
    logger.info("📊 Model Performance Summary:")
    
    for target in targets:
        target_results = results_df[results_df['target'] == target]
        best_model = target_results.loc[target_results['auc_score'].idxmax()]
        
        logger.info(f"\n🎯 {target.upper()}:")
        logger.info(f"   🏆 Best: {best_model['model_type'].upper()} (AUC: {best_model['auc_score']:.4f})")
        logger.info(f"   📊 All models:")
        for _, row in target_results.iterrows():
            logger.info(f"      {row['model_type'].upper()}: AUC={row['auc_score']:.4f}, F1={row['f1_score']:.4f}")
    
    logger.info(f"\n💾 Models saved to: {MODEL_OUTPUT_DIR}/")
    logger.info(f"📈 Results summary: {results_path}")
    
    return results_df

def create_prediction_pipeline():
    """Create a prediction pipeline script"""
    logger.info("🔮 Creating prediction pipeline...")
    
    pipeline_code = '''#!/usr/bin/env python3
"""
Racing Prediction Pipeline
Uses trained models to make predictions on new data
"""

import pandas as pd
import numpy as np
import joblib
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_models():
    """Load all trained models"""
    models = {}
    
    targets = ['target_win', 'target_place', 'target_show']
    model_types = ['rf', 'gbm', 'xgb', 'lr']
    
    for target in targets:
        models[target] = {}
        for model_type in model_types:
            try:
                model_path = f'trained_models/{target}_{model_type}_model.joblib'
                models[target][model_type] = joblib.load(model_path)
                
                # Load scaler for logistic regression
                if model_type == 'lr':
                    scaler_path = f'trained_models/{target}_{model_type}_scaler.joblib'
                    models[target][f'{model_type}_scaler'] = joblib.load(scaler_path)
                    
                logger.info(f"✅ Loaded {target} {model_type} model")
            except Exception as e:
                logger.warning(f"⚠️ Could not load {target} {model_type} model: {e}")
    
    return models

def predict_race(race_data, models, feature_cols):
    """Predict outcomes for a single race"""
    
    # Prepare features
    X = race_data[feature_cols].fillna(0)
    
    predictions = {}
    
    for target in ['target_win', 'target_place', 'target_show']:
        predictions[target] = {}
        
        # Random Forest predictions
        if 'rf' in models[target]:
            rf_probs = models[target]['rf'].predict_proba(X)[:, 1]
            predictions[target]['rf'] = rf_probs
        
        # Gradient Boosting predictions  
        if 'gbm' in models[target]:
            gbm_probs = models[target]['gbm'].predict_proba(X)[:, 1]
            predictions[target]['gbm'] = gbm_probs
        
        # XGBoost predictions
        if 'xgb' in models[target]:
            xgb_probs = models[target]['xgb'].predict_proba(X)[:, 1]
            predictions[target]['xgb'] = xgb_probs
        
        # Logistic Regression predictions
        if 'lr' in models[target] and 'lr_scaler' in models[target]:
            X_scaled = models[target]['lr_scaler'].transform(X)
            lr_probs = models[target]['lr'].predict_proba(X_scaled)[:, 1]
            predictions[target]['lr'] = lr_probs
    
    return predictions

def create_race_card(race_data, predictions):
    """Create a formatted race card with predictions"""
    
    race_card = race_data[['horse_name', 'jockey', 'trainer', 'odds_decimal']].copy()
    
    # Add predictions
    for target in predictions:
        for model_type in predictions[target]:
            col_name = f'{target}_{model_type}_prob'
            race_card[col_name] = predictions[target][model_type]
    
    # Calculate ensemble predictions (average of all models)
    for target in ['target_win', 'target_place', 'target_show']:
        model_cols = [col for col in race_card.columns if col.startswith(f'{target}_') and col.endswith('_prob')]
        if model_cols:
            race_card[f'{target}_ensemble'] = race_card[model_cols].mean(axis=1)
    
    # Sort by win probability
    race_card = race_card.sort_values('target_win_ensemble', ascending=False)
    
    return race_card

if __name__ == "__main__":
    # Example usage
    logger.info("🔮 Loading prediction models...")
    models = load_models()
    
    # Load feature columns (you would need to save this during training)
    # feature_cols = [...] # Load from saved file
    
    logger.info("🏇 Ready for predictions!")
    print("Use predict_race(race_data, models, feature_cols) to make predictions")
'''
    
    with open(f'{MODEL_OUTPUT_DIR}/prediction_pipeline.py', 'w') as f:
        f.write(pipeline_code)
    
    logger.info(f"✅ Prediction pipeline created: {MODEL_OUTPUT_DIR}/prediction_pipeline.py")

if __name__ == "__main__":
    # Train all models
    results = train_all_models()
    
    # Create prediction pipeline
    create_prediction_pipeline()
    
    logger.info("\n🎉 === ALL COMPLETE ===")
    logger.info("✅ Models trained and saved")
    logger.info("✅ Prediction pipeline created")
    logger.info("✅ Ready for racing predictions!")
