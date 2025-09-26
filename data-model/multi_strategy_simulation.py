#!/usr/bin/env python3
"""
Multi-Strategy Horse Racing Simulation

This script loads a trained ML model and simulates 3 different betting strategies
on live Australian horse races for analysis and comparison.
"""

import pandas as pd
import numpy as np
import xgboost as xgb
import sqlite3
import pickle
import requests
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class MultiStrategySimulator:
        
    def load_model(self):
        """Load the trained model and feature names"""
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.feature_names = model_data['feature_names']
            self.feature_importance = model_data.get('feature_importance', {})
            
            print(f"✅ Model loaded from {self.model_path}")
            print(f"📊 Features: {len(self.feature_names)}")
            return True
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def get_todays_races(self):
        """Get all Australian races for today from race_times table"""
        try:
            conn = sqlite3.connect(self.betting_db_path)
            
            # Find all Australian races for today
            query = """
            SELECT venue, race_number, race_time, race_date
            FROM race_times 
            WHERE country = 'AUS'
            AND date(race_date) = date('now', 'localtime')
            ORDER BY venue, race_number
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            print(f"🏇 Found {len(df)} Australian races for today")
            if len(df) > 0:
                print("📍 Venues found:")
                for venue in df['venue'].unique():
                    print(f"   - {venue}")
            
            return df
        except Exception as e:
            print(f"❌ Error getting today's races: {e}")
            return pd.DataFrame()
    
    def get_race_horses(self, venue, race_number):
        """Get horses for a specific race from Betfair database"""
        try:
            conn = sqlite3.connect(self.betfair_db_path)
            
            query = """
            SELECT MarketId, MarketName, RUNNER_NAME, STALL_DRAW, JOCKEY_NAME, TRAINER_NAME
            FROM HorseMarketBook 
            WHERE EventName LIKE ? 
            AND MarketName LIKE ?
            """
            
            venue_pattern = f"%{venue}%"
            race_pattern = f"R{race_number}%"
            
            df = pd.read_sql_query(query, conn, params=[venue_pattern, race_pattern])
            conn.close()
            
            return df
        except Exception as e:
            print(f"⚠️ Error getting race horses for {venue} R{race_number}: {e}")
            return pd.DataFrame()
    
    def get_scraped_odds(self, venue, race_number):
        """Get scraped opening odds for a race"""
        try:
            conn = sqlite3.connect(self.betting_db_path)
            
            # Get the schema first to understand the table structure
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(scraped_odds)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Check what columns are available
            print(f"📊 Available columns in scraped_odds: {columns}")
            
            # Look for horse name and odds columns
            horse_col = None
            odds_cols = []
            
            for col in columns:
                if 'horse' in col.lower() and 'name' in col.lower():
                    horse_col = col
                elif 'odds' in col.lower() and col != 'horse_name':
                    odds_cols.append(col)
            
            if not horse_col or not odds_cols:
                print(f"⚠️ Cannot find horse name or odds columns in scraped_odds table")
                conn.close()
                return pd.DataFrame()
            
            # Build query to get horse names and odds
            select_cols = [horse_col] + odds_cols
            query = f"SELECT {', '.join(select_cols)} FROM scraped_odds WHERE venue = ? AND race_number = ?"
            
            df = pd.read_sql_query(query, conn, params=[venue, race_number])
            
            if not df.empty:
                # Calculate average odds from all odds columns
                odds_data = df[odds_cols].replace([np.inf, -np.inf], np.nan)
                df['avg_odds'] = odds_data.mean(axis=1)
                df['horse_name'] = df[horse_col]  # Standardize column name
                
                # Return only the columns we need
                result_df = df[['horse_name', 'avg_odds']].copy()
            else:
                result_df = pd.DataFrame()
            
            conn.close()
            return result_df
            
        except Exception as e:
            print(f"⚠️ Error getting scraped odds for {venue} R{race_number}: {e}")
            return pd.DataFrame()
    
    def get_bsp_estimate(self, market_id, opening_odds):
        """Get BSP estimate from Stream API with improved fallback logic"""
        try:
            # Try to get BSP projections from Stream API
            response = requests.get(f"{self.backend_url}/api/streamapi/bsp/{market_id}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Check if we have BSP projections data
                bsp_projections = data.get('bspProjections', [])
                if bsp_projections:
                    valid_bsps = []
                    for projection in bsp_projections:
                        average = projection.get('average')
                        if average and average > 0:
                            valid_bsps.append(average)
                    
                    if valid_bsps:
                        market_bsp = sum(valid_bsps) / len(valid_bsps)
                        print(f"✅ Got Stream API BSP projections for market {market_id}: {market_bsp:.2f}")
                        return market_bsp
                
                print(f"⚠️ No valid BSP projections found for market {market_id}")
                # Try Exchange API fallback
                return self._get_exchange_bsp_estimate(market_id, opening_odds)
            else:
                print(f"⚠️ Failed to get BSP projections for market {market_id}: {response.status_code}")
                # Try Exchange API fallback
                return self._get_exchange_bsp_estimate(market_id, opening_odds)
        except Exception as e:
            print(f"⚠️ Error getting BSP projections for market {market_id}: {e}")
            # Try Exchange API fallback
            return self._get_exchange_bsp_estimate(market_id, opening_odds)
    
    def _get_exchange_bsp_estimate(self, market_id, opening_odds):
        """Fallback to Exchange API for BSP projections"""
        try:
            response = requests.get(f"{self.backend_url}/api/odds/bsp/{market_id}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                bsp_projections = data.get('bspProjections', [])
                
                if bsp_projections:
                    valid_bsps = []
                    for projection in bsp_projections:
                        average = projection.get('average')
                        if average and average > 0:
                            valid_bsps.append(average)
                    
                    if valid_bsps:
                        market_bsp = sum(valid_bsps) / len(valid_bsps)
                        print(f"✅ Got Exchange API BSP projections for market {market_id}: {market_bsp:.2f}")
                        return market_bsp
                
                print(f"⚠️ No valid Exchange API BSP projections found for market {market_id}")
                # Final fallback to opening odds calculation
                return self._calculate_fallback_bsp(opening_odds)
            else:
                print(f"⚠️ Failed to get Exchange API BSP projections for market {market_id}: {response.status_code}")
                # Final fallback to opening odds calculation
                return self._calculate_fallback_bsp(opening_odds)
        except Exception as e:
            print(f"⚠️ Error getting Exchange API BSP projections for market {market_id}: {e}")
            # Final fallback to opening odds calculation
            return self._calculate_fallback_bsp(opening_odds)
    
    def _calculate_fallback_bsp(self, opening_odds):
        """Calculate BSP estimate using opening odds with realistic adjustments"""
        if opening_odds and opening_odds > 0:
            # More realistic BSP calculation based on typical market movements
            if opening_odds < 2.0:
                # Short odds tend to drift slightly
                bsp_estimate = opening_odds * 1.05
            elif opening_odds < 5.0:
                # Medium odds tend to drift more
                bsp_estimate = opening_odds * 1.1
            else:
                # Long odds can drift significantly
                bsp_estimate = opening_odds * 1.15
            
            print(f"🧮 FALLBACK: Calculated BSP estimate from opening odds {opening_odds:.2f} → {bsp_estimate:.2f}")
            return bsp_estimate
        else:
            print(f"⚠️ No opening odds available for BSP calculation")
            return None
    
    def extract_distance_from_market_name(self, market_name):
        """Extract race distance from MarketName like 'R1 2000m Mdn'"""
        if pd.isna(market_name):
            return None
        match = re.search(r'(\d+)m', str(market_name))
        return int(match.group(1)) if match else None
    
    def __init__(self, model_path="horse_racing_model.pkl", dry_run=True):
        self.model_path = model_path
        self.model = None
        self.feature_names = None
        self.feature_importance = None
        self.betfair_db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
        self.betting_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/live_betting.sqlite"
        self.historical_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/runner_history.sqlite"
        self.backend_url = "http://localhost:5173"
        self.dry_run = dry_run
        
        # Australian venues to simulate
        # Will be populated dynamically from database
        self.target_venues = []
        
        # Check BSP data availability
        self.check_bsp_availability()
        
        # Test BSP API endpoints
        self.test_bsp_endpoints()
        
        # No need to pre-load data - we'll query the database directly
    
    def check_bsp_availability(self):
        """Check if BSP data is available in the database"""
        try:
            conn = sqlite3.connect(self.betfair_db_path)
            cursor = conn.cursor()
            
            # Check if StreamBspProjections table exists and has data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='StreamBspProjections'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM StreamBspProjections")
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"✅ BSP data available: {count} projections in StreamBspProjections table")
                else:
                    print("⚠️ StreamBspProjections table exists but is empty")
            else:
                print("⚠️ StreamBspProjections table not found - BSP data not available")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Error checking BSP availability: {e}")
    
    def test_bsp_endpoints(self):
        """Test BSP API endpoints to see what's available"""
        try:
            # Test Stream API BSP endpoint
            print("🔍 Testing BSP API endpoints...")
            
            # Try to get a sample market ID from the database
            conn = sqlite3.connect(self.betfair_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT MarketId FROM HorseMarketBook LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                test_market_id = result[0]
                print(f"🧪 Testing with market ID: {test_market_id}")
                
                # Test Stream API
                try:
                    response = requests.get(f"{self.backend_url}/api/streamapi/bsp/{test_market_id}", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        bsp_count = len(data.get('bspProjections', []))
                        print(f"✅ Stream API BSP endpoint working: {bsp_count} projections found")
                    else:
                        print(f"⚠️ Stream API BSP endpoint returned status {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Stream API BSP endpoint error: {e}")
                
                # Test Exchange API
                try:
                    response = requests.get(f"{self.backend_url}/api/odds/bsp/{test_market_id}", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        bsp_count = len(data.get('bspProjections', []))
                        print(f"✅ Exchange API BSP endpoint working: {bsp_count} projections found")
                    else:
                        print(f"⚠️ Exchange API BSP endpoint returned status {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Exchange API BSP endpoint error: {e}")
            else:
                print("⚠️ No market IDs found in database for testing")
                
        except Exception as e:
            print(f"⚠️ Error testing BSP endpoints: {e}")
    
    def get_historical_features(self, horse_name, jockey_name, trainer_name):
        """Get historical features for a horse from database"""
        try:
            # Clean horse name - remove number and period, then capitalize (e.g., "8. Lady Shenanigans" -> "LADY SHENANIGANS")
            clean_horse_name = horse_name
            if horse_name and '.' in horse_name:
                parts = horse_name.split('.', 1)
                if len(parts) > 1:
                    clean_horse_name = parts[1].strip().upper()
            
            # Create normalized version for matching (remove apostrophes, hyphens, etc.)
            normalized_name = clean_horse_name.replace("'", "").replace("-", " ").replace(".", "").strip()
            
            conn = sqlite3.connect(self.historical_db_path)
            
            # First try exact match
            query = """
            SELECT * FROM runner_history 
            WHERE runnerName = ? 
            ORDER BY meetingDate DESC 
            LIMIT 1
            """
            
            df = pd.read_sql_query(query, conn, params=[clean_horse_name])
            
            # If no exact match, try normalized matching (remove apostrophes from both sides)
            if df.empty:
                query = """
                SELECT * FROM runner_history 
                WHERE REPLACE(REPLACE(REPLACE(runnerName, '''', ''), '-', ' '), '.', '') = ?
                ORDER BY meetingDate DESC 
                LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=[normalized_name])
            
            # If still no match, try partial matching (contains)
            if df.empty:
                query = """
                SELECT * FROM runner_history 
                WHERE runnerName LIKE ? 
                ORDER BY meetingDate DESC 
                LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=[f'%{clean_horse_name}%'])
            
            # If still no match, try reverse partial matching (horse name contains database name)
            if df.empty:
                query = """
                SELECT * FROM runner_history 
                WHERE ? LIKE '%' || runnerName || '%'
                ORDER BY meetingDate DESC 
                LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=[clean_horse_name])
            
            conn.close()
            
            if df.empty:
                print(f"⚠️ No historical data found for {horse_name}")
                return None
            
            # Get the record
            record = df.iloc[0]
            
            # Extract historical features
            features = {}
            for feature in self.feature_names:
                if feature in ['raceDistance', 'runnerNumber', 'FixedWinOpen_Reference', 'FixedWinClose_Reference']:
                    # These will be replaced with live data
                    features[feature] = 0
                else:
                    # Use real historical data
                    if feature in record:
                        value = record[feature]
                        if pd.isna(value):
                            features[feature] = 0
                        else:
                            features[feature] = float(value)
                    else:
                        features[feature] = 0
            
            return features
            
        except Exception as e:
            print(f"⚠️ Error getting historical features for {horse_name}: {e}")
            return None
    
    def predict_horse_probability(self, horse_data, opening_odds, bsp_estimate):
        """Predict win probability for a horse"""
        try:
            # Get historical features
            historical_features = self.get_historical_features(
                horse_data['RUNNER_NAME'], 
                horse_data.get('JOCKEY_NAME', ''), 
                horse_data.get('TRAINER_NAME', '')
            )
            
            if historical_features is None:
                print(f"⚠️ No historical data for {horse_data['RUNNER_NAME']} - skipping prediction")
                return 0.0
            
            # Extract race distance
            race_distance = self.extract_distance_from_market_name(horse_data['MarketName'])
            
            # Combine features
            features = historical_features.copy()
            features['raceDistance'] = race_distance if race_distance else 0
            features['runnerNumber'] = horse_data.get('STALL_DRAW', 0) if pd.notna(horse_data.get('STALL_DRAW')) else 0
            features['FixedWinOpen_Reference'] = opening_odds if opening_odds else 0
            features['FixedWinClose_Reference'] = bsp_estimate if bsp_estimate else 0
            
            # Ensure all required features are present
            for feature in self.feature_names:
                if feature not in features:
                    features[feature] = 0
            
            # Prepare feature vector
            feature_vector = [features.get(f, 0) for f in self.feature_names]
            feature_vector = np.array(feature_vector).reshape(1, -1)
            
            # Make prediction using native XGBoost
            import xgboost as xgb
            dmatrix = xgb.DMatrix(feature_vector, feature_names=self.feature_names)
            win_probability = self.model.predict(dmatrix)[0]
            
            return win_probability
        except Exception as e:
            print(f"⚠️ Error predicting for {horse_data.get('RUNNER_NAME', 'Unknown')}: {e}")
            return 0.0
    
    def strategy_a_value_betting(self, horses_data):
        """Strategy A: Value Betting - bet when model probability > implied probability"""
        bets = []
        
        for horse in horses_data:
            model_prob = horse['win_probability']
            opening_odds = horse['opening_odds']
            
            if opening_odds and opening_odds > 1:
                implied_prob = 1 / opening_odds
                if model_prob > implied_prob * 1.1:  # 10% edge required
                    bets.append({
                        'horse': horse['name'],
                        'strategy': 'Value Betting',
                        'model_prob': model_prob,
                        'implied_prob': implied_prob,
                        'odds': opening_odds,
                        'edge': model_prob - implied_prob,
                        'stake': 20  # Fixed stake
                    })
        
        return bets
    
    def strategy_b_top_probability(self, horses_data):
        """Strategy B: Top Probability - bet on highest model probability"""
        if not horses_data:
            return []
        
        # Find horse with highest probability
        best_horse = max(horses_data, key=lambda x: x['win_probability'])
        
        return [{
            'horse': best_horse['name'],
            'strategy': 'Top Probability',
            'model_prob': best_horse['win_probability'],
            'odds': best_horse['opening_odds'],
            'stake': 20  # Fixed stake
        }]
    
    def strategy_c_lay_betting(self, horses_data):
        """Strategy C: Lay Betting - lay horses with high model probability but long odds"""
        lay_bets = []
        
        for horse in horses_data:
            model_prob = horse['win_probability']
            opening_odds = horse['opening_odds']
            
            # Lay if model says high probability but odds are long
            # More realistic criteria: lay favorites with decent odds
            if opening_odds and opening_odds > 2.0 and model_prob > 0.4:
                lay_bets.append({
                    'horse': horse['name'],
                    'strategy': 'Lay Betting',
                    'model_prob': model_prob,
                    'odds': opening_odds,
                    'lay_price': opening_odds * 0.9,  # Lay at 90% of back odds
                    'stake': 20  # Fixed stake
                })
        
        return lay_bets
    
    def simulate_race(self, venue, race_number, race_time):
        """Simulate all strategies for a single race"""
        print(f"\n🏇 Simulating {venue} R{race_number} at {race_time}")
        
        # Get race data
        horses_df = self.get_race_horses(venue, race_number)
        if horses_df.empty:
            print(f"❌ No horses found for {venue} R{race_number}")
            return None
        
        # Get scraped odds
        odds_df = self.get_scraped_odds(venue, race_number)
        
        # Get BSP estimates (using opening odds + 2 for testing)
        market_ids = horses_df['MarketId'].unique()
        bsp_estimates = {}
        for market_id in market_ids:
            # Get average opening odds for this market
            market_horses = horses_df[horses_df['MarketId'] == market_id]
            market_opening_odds = []
            for _, horse in market_horses.iterrows():
                horse_name = horse['RUNNER_NAME']
                if not odds_df.empty:
                    # Clean horse name for matching (remove number prefix like "1. ")
                    clean_horse_name = horse_name
                    if horse_name and '.' in horse_name:
                        parts = horse_name.split('.', 1)
                        if len(parts) > 1:
                            clean_horse_name = parts[1].strip()
                    
                    horse_odds = odds_df[odds_df['horse_name'] == clean_horse_name]
                    if not horse_odds.empty:
                        avg_odds = horse_odds['avg_odds'].iloc[0]
                        if avg_odds and avg_odds > 0:
                            market_opening_odds.append(avg_odds)
            
            # Use average opening odds for BSP estimate
            if market_opening_odds:
                avg_opening = sum(market_opening_odds) / len(market_opening_odds)
                bsp_estimates[market_id] = self.get_bsp_estimate(market_id, avg_opening)
            else:
                bsp_estimates[market_id] = None
        
        # Prepare horse data with predictions
        horses_data = []
        for _, horse in horses_df.iterrows():
            horse_name = horse['RUNNER_NAME']
            market_id = horse['MarketId']
            
            # Get opening odds
            opening_odds = None
            if not odds_df.empty:
                # Clean horse name for matching (remove number prefix like "1. ")
                clean_horse_name = horse_name
                if horse_name and '.' in horse_name:
                    parts = horse_name.split('.', 1)
                    if len(parts) > 1:
                        clean_horse_name = parts[1].strip()
                
                horse_odds = odds_df[odds_df['horse_name'] == clean_horse_name]
                if not horse_odds.empty:
                    opening_odds = horse_odds['avg_odds'].iloc[0]
            
            # Get BSP estimate
            bsp_estimate = bsp_estimates.get(market_id)
            
            # Predict win probability
            win_probability = self.predict_horse_probability(horse, opening_odds, bsp_estimate)
            
            horses_data.append({
                'name': horse_name,
                'stall': horse.get('STALL_DRAW', 0),
                'jockey': horse.get('JOCKEY_NAME', ''),
                'trainer': horse.get('TRAINER_NAME', ''),
                'opening_odds': opening_odds,
                'bsp_estimate': bsp_estimate,
                'win_probability': win_probability
            })
        
        # Run all strategies
        strategy_a_bets = self.strategy_a_value_betting(horses_data)
        strategy_b_bets = self.strategy_b_top_probability(horses_data)
        strategy_c_bets = self.strategy_c_lay_betting(horses_data)
        
        # Combine all bets
        all_bets = strategy_a_bets + strategy_b_bets + strategy_c_bets
        
        # Display results
        print(f"📊 Horses: {len(horses_data)}")
        print(f"🎯 Strategy A (Value): {len(strategy_a_bets)} bets")
        print(f"🎯 Strategy B (Top Prob): {len(strategy_b_bets)} bets")
        print(f"🎯 Strategy C (Lay): {len(strategy_c_bets)} bets")
        
        if all_bets:
            print("\n💰 BETS PLACED:")
            for bet in all_bets:
                print(f"  {bet['strategy']}: {bet['horse']} @ {bet.get('odds', 'N/A')} (Prob: {bet['model_prob']:.3f})")
        
        return {
            'venue': venue,
            'race_number': race_number,
            'race_time': race_time,
            'horses': horses_data,
            'bets': all_bets,
            'strategy_a_bets': strategy_a_bets,
            'strategy_b_bets': strategy_b_bets,
            'strategy_c_bets': strategy_c_bets
        }
    
    def run_simulation(self):
        """Run simulation for all today's races"""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        print(f"🚀 Starting Multi-Strategy Simulation ({mode})")
        print("=" * 60)
        
        # Load model
        if not self.load_model():
            return None
        
        # Get today's races
        races_df = self.get_todays_races()
        if races_df.empty:
            print("❌ No races found for today")
            return None
        
        # Simulate each race
        results = []
        total_bets = 0
        
        for _, race in races_df.iterrows():
            race_result = self.simulate_race(
                race['venue'], 
                race['race_number'], 
                race['race_time']
            )
            
            if race_result:
                results.append(race_result)
                total_bets += len(race_result['bets'])
        
        # Summary
        print(f"\n📊 SIMULATION SUMMARY")
        print("=" * 60)
        print(f"Races processed: {len(results)}")
        print(f"Total bets placed: {total_bets}")
        
        strategy_a_total = sum(len(r['strategy_a_bets']) for r in results)
        strategy_b_total = sum(len(r['strategy_b_bets']) for r in results)
        strategy_c_total = sum(len(r['strategy_c_bets']) for r in results)
        
        print(f"Strategy A (Value): {strategy_a_total} bets")
        print(f"Strategy B (Top Prob): {strategy_b_total} bets")
        print(f"Strategy C (Lay): {strategy_c_total} bets")
        
        return results

def main():
    """Main function to run the simulation"""
    simulator = MultiStrategySimulator()
    results = simulator.run_simulation()
    
    if results:
        print("\n✅ Simulation completed successfully!")
        return results
    else:
        print("\n❌ Simulation failed!")
        return None

if __name__ == "__main__":
    results = main()
