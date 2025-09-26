#!/usr/bin/env python3
"""
Load trained model and make real predictions
"""

import pandas as pd
import numpy as np
import sqlite3
import xgboost as xgb
import pickle
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class ModelPredictor:
    def __init__(self, betting_db_path="betting_history.sqlite", csv_path="/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"):
        self.betting_db_path = betting_db_path
        self.csv_path = csv_path
        self.model = None
        self.historical_data = None
        self.top_features = [
            'FixedWinClose_Reference',
            'region_trainer_placings', 
            'track_rider_placings',
            'jockey_trainer_placings',
            'region_trainer_wins'
        ]
        
    def load_historical_data(self):
        """Load historical data from CSV for feature lookup"""
        print("📊 Loading historical data...")
        
        try:
            self.historical_data = pd.read_csv(self.csv_path)
            print(f"   - Loaded {len(self.historical_data):,} historical records")
            return True
        except Exception as e:
            print(f"❌ Error loading historical data: {e}")
            return False
    
    def train_and_save_model(self):
        """Train the model and save it"""
        print("🚀 Training model...")
        
        # Load and clean data
        df = self.historical_data.copy()
        
        # Remove scratched horses
        df = df[df['finishingPosition'] > 0].copy()
        df = df[df['FixedWinClose_Reference'] > 0].copy()
        
        # Create multi-class target
        def create_position_target(pos):
            if pos == 1:
                return 0  # Win
            elif pos in [2, 3]:
                return 1  # Place
            else:
                return 2  # Unplaced
        
        df['position_target'] = df['finishingPosition'].apply(create_position_target)
        
        # Prepare features
        X = df[self.top_features].copy()
        y = df['position_target'].copy()
        
        # Handle missing values
        X = X.fillna(0)
        X = X.replace([np.inf, -np.inf], 0)
        
        print(f"   - Training on {len(X):,} records")
        
        # Create DMatrix
        dtrain = xgb.DMatrix(X, y)
        
        # Set parameters
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
        
        # Train model
        self.model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=100
        )
        
        # Save model
        self.model.save_model('trained_model.json')
        print("   - Model saved as trained_model.json")
        
        return True
    
    def load_model(self):
        """Load the trained model"""
        print("🔄 Loading trained model...")
        
        try:
            self.model = xgb.Booster()
            self.model.load_model('trained_model.json')
            print("   - Model loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def get_todays_races(self):
        """Get today's races from the database"""
        print("🏇 Getting today's races...")
        
        try:
            conn = sqlite3.connect(self.betting_db_path)
            
            # Get races for today
            today = datetime.now().strftime('%Y-%m-%d')
            
            query = """
            SELECT DISTINCT venue, race_number, race_time, race_date
            FROM scraped_odds 
            WHERE race_date = ?
            ORDER BY race_time
            """
            
            races_df = pd.read_sql_query(query, conn, params=[today])
            conn.close()
            
            print(f"   - Found {len(races_df)} races for today")
            return races_df
            
        except Exception as e:
            print(f"❌ Error getting today's races: {e}")
            return pd.DataFrame()
    
    def get_race_horses_with_odds(self, venue, race_number):
        """Get horses with odds for a specific race"""
        print(f"🐎 Getting horses for {venue} R{race_number}...")
        
        try:
            conn = sqlite3.connect(self.betting_db_path)
            
            # Get horses with their average odds (excluding BetfairLay)
            query = """
            SELECT 
                horse_name, 
                horse_number,
                AVG(odds) as avg_odds,
                COUNT(*) as bookmaker_count
            FROM scraped_odds 
            WHERE venue = ? AND race_number = ? AND bookmaker != 'BetfairLay'
            GROUP BY horse_name, horse_number
            HAVING bookmaker_count >= 5
            ORDER BY avg_odds
            """
            
            horses_df = pd.read_sql_query(query, conn, params=[venue, race_number])
            conn.close()
            
            print(f"   - Found {len(horses_df)} horses with odds")
            return horses_df
            
        except Exception as e:
            print(f"❌ Error getting race horses: {e}")
            return pd.DataFrame()
    
    def lookup_historical_features(self, horses_df):
        """Look up historical features for each horse from the CSV"""
        print("🔍 Looking up historical features...")
        
        if self.historical_data is None:
            print("❌ No historical data loaded")
            return None
        
        race_data = horses_df.copy()
        
        # Initialize feature columns
        for feature in self.top_features[1:]:  # Skip FixedWinClose_Reference
            race_data[feature] = 0
        
        # Look up features for each horse
        for i, (_, horse) in enumerate(race_data.iterrows()):
            horse_name = horse['horse_name']
            
            # Find historical records for this horse
            horse_records = self.historical_data[
                self.historical_data['runnerName'].str.contains(horse_name, case=False, na=False)
            ]
            
            if not horse_records.empty:
                # Get the most recent record for this horse
                latest_record = horse_records.iloc[-1]
                
                # Extract features
                race_data.loc[i, 'region_trainer_placings'] = latest_record.get('region_trainer_placings', 0)
                race_data.loc[i, 'track_rider_placings'] = latest_record.get('track_rider_placings', 0)
                race_data.loc[i, 'jockey_trainer_placings'] = latest_record.get('jockey_trainer_placings', 0)
                race_data.loc[i, 'region_trainer_wins'] = latest_record.get('region_trainer_wins', 0)
            else:
                print(f"   - No historical data found for {horse_name}")
        
        # Set the odds feature
        race_data['FixedWinClose_Reference'] = race_data['avg_odds']
        
        print(f"   - Created features for {len(race_data)} horses")
        return race_data
    
    def predict_race_positions(self, race_data):
        """Predict positions for all horses in a race using the trained model"""
        print("🔮 Making ML predictions...")
        
        if self.model is None:
            print("❌ No model available")
            return None
        
        try:
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
            
            return results
            
        except Exception as e:
            print(f"❌ Error making predictions: {e}")
            return None
    
    def display_race_predictions(self, predictions):
        """Display race predictions in a nice format"""
        print(f"\n🏁 ML Race Predictions:")
        print("=" * 80)
        
        for i, (_, horse) in enumerate(predictions.iterrows(), 1):
            print(f"{i:2d}. {horse['horse_name']} (#{horse['horse_number']})")
            print(f"    💰 Odds: {horse['avg_odds']:.2f}")
            print(f"    🏆 Win: {horse['win_prob']:.1%} | Place: {horse['place_prob']:.1%} | Unplaced: {horse['unplaced_prob']:.1%}")
            print(f"    🎯 Predicted: {horse['predicted_label']}")
            
            # Show historical features
            print(f"    📊 Features: region_trainer_placings={horse['region_trainer_placings']:.0f}, "
                  f"track_rider_placings={horse['track_rider_placings']:.0f}, "
                  f"jockey_trainer_placings={horse['jockey_trainer_placings']:.0f}, "
                  f"region_trainer_wins={horse['region_trainer_wins']:.0f}")
            print()
    
    def test_todays_races(self):
        """Test predictions on today's races"""
        print("🏇 Testing ML Race Predictions")
        print("=" * 50)
        
        # Load historical data
        if not self.load_historical_data():
            return
        
        # Train and save model
        if not self.train_and_save_model():
            return
        
        # Load model
        if not self.load_model():
            return
        
        # Get today's races
        races_df = self.get_todays_races()
        
        if races_df.empty:
            print("❌ No races found for today")
            return
        
        # Test on first few races
        for i, (_, race) in enumerate(races_df.head(3).iterrows()):
            venue = race['venue']
            race_number = race['race_number']
            race_time = race['race_time']
            
            print(f"\n🏁 {venue} R{race_number} at {race_time}")
            print("-" * 50)
            
            # Get horses for this race
            horses_df = self.get_race_horses_with_odds(venue, race_number)
            
            if horses_df.empty:
                print(f"   - No horses found for {venue} R{race_number}")
                continue
            
            # Look up historical features
            race_data = self.lookup_historical_features(horses_df)
            
            if race_data is None:
                continue
            
            # Make ML predictions
            predictions = self.predict_race_positions(race_data)
            
            if predictions is not None:
                # Display results
                self.display_race_predictions(predictions)

def main():
    """Main function"""
    predictor = ModelPredictor()
    predictor.test_todays_races()

if __name__ == "__main__":
    main()
