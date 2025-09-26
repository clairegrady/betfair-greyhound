#!/usr/bin/env python3
"""
Horse Racing ML Analysis with XGBoost and SHAP
Analyzes the most important features for horse racing prediction
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import shap
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

class HorseRacingMLAnalyzer:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = None
        self.X = None
        self.y = None
        self.model = None
        self.feature_names = None
        self.explainer = None
        
    def load_and_prepare_data(self):
        """Load and prepare the dataset"""
        print("📊 Loading horse racing data...")
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} records with {len(self.df.columns)} features")
        
        # Display basic info
        print(f"\n📈 Dataset Info:")
        print(f"   - Total records: {len(self.df):,}")
        print(f"   - Features: {len(self.df.columns)}")
        print(f"   - Date range: {self.df['meetingDate'].min()} to {self.df['meetingDate'].max()}")
        
        return self.df
    
    def create_target_variable(self):
        """Create target variable for prediction"""
        print("\n🎯 Creating target variable...")
        
        # Remove scratched horses (negative finishing positions)
        original_count = len(self.df)
        self.df = self.df[self.df['finishingPosition'] > 0].copy()
        removed_scratched = original_count - len(self.df)
        print(f"   - Removed {removed_scratched:,} scratched horses")
        
        # Remove invalid odds (negative or zero)
        original_count = len(self.df)
        self.df = self.df[self.df['FixedWinClose_Reference'] > 0].copy()
        removed_invalid_odds = original_count - len(self.df)
        print(f"   - Removed {removed_invalid_odds:,} records with invalid odds")
        
        # Create binary target: 1 if horse wins (finishingPosition = 1), 0 otherwise
        self.df['target'] = (self.df['finishingPosition'] == 1).astype(int)
        
        # Also create a multi-class target for more nuanced analysis
        # 1=Win, 2=Place (2nd-3rd), 3=Unplaced (4th+)
        def create_place_target(pos):
            if pos == 1:
                return 1  # Win
            elif pos in [2, 3]:
                return 2  # Place
            else:
                return 3  # Unplaced
        
        self.df['place_target'] = self.df['finishingPosition'].apply(create_place_target)
        
        win_rate = self.df['target'].mean()
        print(f"   - Final dataset: {len(self.df):,} records")
        print(f"   - Win rate: {win_rate:.1%}")
        print(f"   - Place rate: {(self.df['place_target'] <= 2).mean():.1%}")
        
        return self.df
    
    def prepare_features(self):
        """Prepare features for ML model"""
        print("\n🔧 Preparing features...")
        
        # Remove non-predictive columns
        exclude_cols = [
            'finishingPosition', 'meetingName', 'meetingDate', 'raceNumber', 
            'runnerNumber', 'runnerName', 'riderName', 'location', 
            'weatherCondition', 'trackCondition', 'raceName', 'raceStartTime',
            'raceDistance', 'trackDirection', 'raceClassConditions',
            'runner_scratched', 'race_abandoned', 'target', 'place_target'
        ]
        
        # Get feature columns
        feature_cols = [col for col in self.df.columns if col not in exclude_cols]
        print(f"   - Using {len(feature_cols)} features")
        
        # Handle missing values
        self.df[feature_cols] = self.df[feature_cols].fillna(0)
        
        # Remove any infinite values
        self.df[feature_cols] = self.df[feature_cols].replace([np.inf, -np.inf], 0)
        
        # Create feature matrix
        self.X = self.df[feature_cols].copy()
        self.y = self.df['target'].copy()
        self.feature_names = feature_cols
        
        print(f"   - Feature matrix shape: {self.X.shape}")
        print(f"   - Target distribution: {self.y.value_counts().to_dict()}")
        
        return self.X, self.y
    
    def train_xgboost_model(self):
        """Train XGBoost model"""
        print("\n🚀 Training XGBoost model...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            self.X, self.y, test_size=0.2, random_state=42, stratify=self.y
        )
        
        # Train XGBoost with better parameters for imbalanced data
        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            random_state=42,
            eval_metric='logloss',
            scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1])  # Handle class imbalance
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate model
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        accuracy = accuracy_score(y_test, y_pred)
        
        # Calculate baseline accuracy
        baseline_accuracy = max(y_test.mean(), 1 - y_test.mean())
        improvement = accuracy - baseline_accuracy
        
        print(f"   - Training accuracy: {accuracy:.3f}")
        print(f"   - Baseline accuracy: {baseline_accuracy:.3f}")
        print(f"   - Improvement: {improvement:.3f}")
        
        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='accuracy')
        print(f"   - CV accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")
        
        # Print detailed metrics
        print(f"\n📊 Detailed Performance:")
        from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
        print(f"   - ROC AUC: {roc_auc_score(y_test, y_pred_proba):.3f}")
        print(f"   - Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
        print(f"   - Classification Report:")
        print(classification_report(y_test, y_pred))
        
        return self.model, X_test, y_test
    
    def analyze_feature_importance(self):
        """Analyze feature importance"""
        print("\n📊 Analyzing feature importance...")
        
        # Get feature importance from XGBoost
        importance_scores = self.model.feature_importances_
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance_scores
        }).sort_values('importance', ascending=False)
        
        print("\n🏆 Top 20 Most Important Features:")
        for i, (_, row) in enumerate(feature_importance.head(20).iterrows(), 1):
            print(f"   {i:2d}. {row['feature']:<30} {row['importance']:.4f}")
        
        return feature_importance
    
    def perform_shap_analysis(self, X_sample=None):
        """Perform SHAP analysis"""
        print("\n🔍 Performing SHAP analysis...")
        
        # Use sample for SHAP (it can be slow with large datasets)
        if X_sample is None:
            X_sample = self.X.sample(n=min(1000, len(self.X)), random_state=42)
        
        # Create SHAP explainer
        self.explainer = shap.TreeExplainer(self.model)
        shap_values = self.explainer.shap_values(X_sample)
        
        print(f"   - SHAP values computed for {len(X_sample)} samples")
        
        return shap_values, X_sample
    
    def create_visualizations(self, feature_importance, shap_values, X_sample):
        """Create visualization plots"""
        print("\n📈 Creating visualizations...")
        
        # Set up the plotting style
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Horse Racing ML Analysis', fontsize=16, fontweight='bold')
        
        # 1. Feature Importance
        top_features = feature_importance.head(15)
        axes[0, 0].barh(range(len(top_features)), top_features['importance'])
        axes[0, 0].set_yticks(range(len(top_features)))
        axes[0, 0].set_yticklabels(top_features['feature'], fontsize=8)
        axes[0, 0].set_xlabel('Importance Score')
        axes[0, 0].set_title('Top 15 Feature Importance (XGBoost)')
        axes[0, 0].invert_yaxis()
        
        # 2. SHAP Summary Plot (simplified)
        try:
            shap.summary_plot(shap_values, X_sample, show=False, ax=axes[0, 1])
            axes[0, 1].set_title('SHAP Summary Plot')
        except:
            # Fallback: simple bar plot of mean SHAP values
            mean_shap = np.abs(shap_values).mean(0)
            top_shap_idx = np.argsort(mean_shap)[-10:]
            axes[0, 1].barh(range(len(top_shap_idx)), mean_shap[top_shap_idx])
            axes[0, 1].set_yticks(range(len(top_shap_idx)))
            axes[0, 1].set_yticklabels([X_sample.columns[i] for i in top_shap_idx], fontsize=8)
            axes[0, 1].set_title('Top 10 SHAP Features')
            axes[0, 1].invert_yaxis()
        
        # 3. Feature Importance Distribution
        axes[1, 0].hist(feature_importance['importance'], bins=20, alpha=0.7, color='skyblue')
        axes[1, 0].set_xlabel('Importance Score')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].set_title('Distribution of Feature Importance')
        
        # 4. Top 10 Features Bar Chart
        top_10 = feature_importance.head(10)
        axes[1, 1].bar(range(len(top_10)), top_10['importance'], color='lightcoral')
        axes[1, 1].set_xticks(range(len(top_10)))
        axes[1, 1].set_xticklabels(top_10['feature'], rotation=45, ha='right', fontsize=8)
        axes[1, 1].set_ylabel('Importance Score')
        axes[1, 1].set_title('Top 10 Most Important Features')
        
        plt.tight_layout()
        plt.savefig('horse_racing_ml_analysis.png', dpi=300, bbox_inches='tight')
        print("   - Saved visualization: horse_racing_ml_analysis.png")
        
        return fig
    
    def generate_feature_report(self, feature_importance):
        """Generate detailed feature report"""
        print("\n📋 Generating feature report...")
        
        # Categorize features
        runner_features = [f for f in feature_importance['feature'] if 'runner_' in f]
        trainer_features = [f for f in feature_importance['feature'] if 'trainer_' in f]
        rider_features = [f for f in feature_importance['feature'] if 'rider_' in f]
        odds_features = [f for f in feature_importance['feature'] if 'FixedWin' in f]
        
        print(f"\n📊 Feature Categories:")
        print(f"   - Runner features: {len(runner_features)}")
        print(f"   - Trainer features: {len(trainer_features)}")
        print(f"   - Rider features: {len(rider_features)}")
        print(f"   - Odds features: {len(odds_features)}")
        
        # Top features by category
        print(f"\n🏆 Top Runner Features:")
        runner_importance = feature_importance[feature_importance['feature'].isin(runner_features)].head(5)
        for _, row in runner_importance.iterrows():
            print(f"   - {row['feature']}: {row['importance']:.4f}")
        
        print(f"\n🏆 Top Trainer Features:")
        trainer_importance = feature_importance[feature_importance['feature'].isin(trainer_features)].head(5)
        for _, row in trainer_importance.iterrows():
            print(f"   - {row['feature']}: {row['importance']:.4f}")
        
        print(f"\n🏆 Top Rider Features:")
        rider_importance = feature_importance[feature_importance['feature'].isin(rider_features)].head(5)
        for _, row in rider_importance.iterrows():
            print(f"   - {row['feature']}: {row['importance']:.4f}")
        
        # Save detailed report
        feature_importance.to_csv('feature_importance_ranking.csv', index=False)
        print("   - Saved feature ranking: feature_importance_ranking.csv")
        
        return feature_importance
    
    def run_complete_analysis(self):
        """Run the complete ML analysis"""
        print("🏇 Starting Horse Racing ML Analysis")
        print("=" * 50)
        
        # Load and prepare data
        self.load_and_prepare_data()
        self.create_target_variable()
        self.prepare_features()
        
        # Train model
        model, X_test, y_test = self.train_xgboost_model()
        
        # Analyze features
        feature_importance = self.analyze_feature_importance()
        
        # SHAP analysis
        shap_values, X_sample = self.perform_shap_analysis()
        
        # Create visualizations
        self.create_visualizations(feature_importance, shap_values, X_sample)
        
        # Generate report
        self.generate_feature_report(feature_importance)
        
        print("\n✅ Analysis complete!")
        print("📁 Output files:")
        print("   - horse_racing_ml_analysis.png")
        print("   - feature_importance_ranking.csv")
        
        return {
            'model': model,
            'feature_importance': feature_importance,
            'shap_values': shap_values,
            'accuracy': accuracy_score(y_test, model.predict(X_test))
        }

def main():
    """Main function"""
    csv_path = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    analyzer = HorseRacingMLAnalyzer(csv_path)
    results = analyzer.run_complete_analysis()
    
    print(f"\n🎯 Final Results:")
    print(f"   - Model Accuracy: {results['accuracy']:.3f}")
    print(f"   - Top Feature: {results['feature_importance'].iloc[0]['feature']}")
    print(f"   - Total Features Analyzed: {len(results['feature_importance'])}")

if __name__ == "__main__":
    main()
