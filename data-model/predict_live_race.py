#!/usr/bin/env python3
"""
Predict on actual race data from the database
Uses the last 15 rows from HorseMarketBook table
"""

import sqlite3
import pandas as pd
import requests
import json
from typing import List, Dict

def get_last_race_from_db() -> Dict:
    """Get the last race data from the database"""
    
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get the last 15 rows (which should be one complete race)
        query = """
        SELECT MarketId, MarketName, EventName, SelectionId, RUNNER_NAME, 
               JOCKEY_NAME, TRAINER_NAME, AGE, WEIGHT_VALUE, STALL_DRAW, 
               FORM, SIRE_NAME, DAM_NAME, SEX_TYPE, DAYS_SINCE_LAST_RUN,
               OFFICIAL_RATING, JOCKEY_CLAIM, COLOURS_DESCRIPTION, Status
        FROM HorseMarketBook 
        ORDER BY Id DESC 
        LIMIT 15
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            print("❌ No data found in database")
            return None
            
        print(f"✅ Found {len(df)} horses from database")
        
        # Group by market (should be one race)
        markets = df['MarketId'].unique()
        if len(markets) > 1:
            print(f"⚠️ Found {len(markets)} different markets, using the first one")
        
        # Filter to just the first market
        race_df = df[df['MarketId'] == markets[0]]
        
        # Filter out REMOVED horses
        active_horses = race_df[race_df['Status'] == 'ACTIVE']
        
        print(f"📊 Market: {active_horses.iloc[0]['MarketName']}")
        print(f"📍 Event: {active_horses.iloc[0]['EventName']}")
        print(f"🏇 Active horses: {len(active_horses)}")
        
        # Convert to API format
        horses = []
        for _, row in active_horses.iterrows():
            horse = {
                "horse_name": row['RUNNER_NAME'] or "Unknown",
                "jockey_name": row['JOCKEY_NAME'] or "Unknown",
                "trainer_name": row['TRAINER_NAME'] or "Unknown", 
                "age": int(row['AGE']) if pd.notna(row['AGE']) and row['AGE'] > 0 else 3,
                "weight_value": float(row['WEIGHT_VALUE']) if pd.notna(row['WEIGHT_VALUE']) and row['WEIGHT_VALUE'] > 0 else 55.0,
                "stall_draw": int(row['STALL_DRAW']) if pd.notna(row['STALL_DRAW']) and row['STALL_DRAW'] > 0 else 1,
                "form": str(row['FORM']) if pd.notna(row['FORM']) else "0",
                "sire_name": str(row['SIRE_NAME']) if pd.notna(row['SIRE_NAME']) else "Unknown",
                "dam_name": str(row['DAM_NAME']) if pd.notna(row['DAM_NAME']) else "Unknown",
                "sex_type": str(row['SEX_TYPE']) if pd.notna(row['SEX_TYPE']) else "m",
                "days_since_last_run": int(row['DAYS_SINCE_LAST_RUN']) if pd.notna(row['DAYS_SINCE_LAST_RUN']) and row['DAYS_SINCE_LAST_RUN'] > 0 else 14,
                "official_rating": float(row['OFFICIAL_RATING']) if pd.notna(row['OFFICIAL_RATING']) else 50.0,
                "jockey_claim": float(row['JOCKEY_CLAIM']) if pd.notna(row['JOCKEY_CLAIM']) else 0.0,
                "colours_description": str(row['COLOURS_DESCRIPTION']) if pd.notna(row['COLOURS_DESCRIPTION']) else "Unknown"
            }
            horses.append(horse)
        
        race_data = {
            "market_id": str(active_horses.iloc[0]['MarketId']),
            "market_name": str(active_horses.iloc[0]['MarketName']),
            "event_name": str(active_horses.iloc[0]['EventName']),
            "horses": horses,
            "race_date": "2025-08-18"
        }
        
        return race_data
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None

def predict_race(race_data: Dict) -> None:
    """Send race data to prediction API and display results"""
    
    try:
        print(f"\n🤖 Sending race data to ML API...")
        print(f"📊 Market: {race_data['market_name']}")
        print(f"📍 Event: {race_data['event_name']}")
        print(f"🏇 Horses: {len(race_data['horses'])}")
        
        # Send to API
        response = requests.post(
            "http://localhost:8000/predict/place",
            json=race_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n🎯 === PLACE BET PREDICTIONS ===")
            print(f"Market ID: {result['market_id']}")
            print(f"Model Confidence: {result['model_confidence']:.1%}")
            print(f"Timestamp: {result['timestamp']}")
            
            print(f"\n🏁 FULL FIELD PREDICTIONS:")
            print(f"{'Rank':<4} {'Horse':<25} {'Jockey':<20} {'Place%':<8} {'Barrier':<7}")
            print("-" * 70)
            
            for i, pred in enumerate(result['predictions'], 1):
                print(f"{i:<4} {pred['horse_name']:<25} {pred['jockey']:<20} {pred['place_percentage']:>6.1f}% {pred['barrier']:<7}")
            
            # Betting recommendations
            print(f"\n💰 === BETTING RECOMMENDATIONS ===")
            
            # High confidence bets (>70%)
            high_conf = [p for p in result['predictions'] if p['place_probability'] > 0.70]
            if high_conf:
                print(f"🎯 HIGH CONFIDENCE PLACE BETS (>70%):")
                for bet in high_conf:
                    print(f"   💎 {bet['horse_name']} - {bet['place_percentage']:.1f}% - Barrier {bet['barrier']}")
            
            # Medium confidence bets (50-70%)
            med_conf = [p for p in result['predictions'] if 0.50 <= p['place_probability'] <= 0.70]
            if med_conf:
                print(f"\n⚖️ MEDIUM CONFIDENCE PLACE BETS (50-70%):")
                for bet in med_conf:
                    print(f"   📊 {bet['horse_name']} - {bet['place_percentage']:.1f}% - Barrier {bet['barrier']}")
            
            # Top 3 selections for trifecta
            print(f"\n🥇 TOP 3 FOR TRIFECTA/EXACTA:")
            for i, pred in enumerate(result['predictions'][:3], 1):
                print(f"   {i}. {pred['horse_name']} ({pred['place_percentage']:.1f}%)")
            
            if not high_conf:
                print(f"\n⚠️ No horses meet the 70% confidence threshold")
                print(f"💡 Consider smaller stakes or avoid this race")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to API. Is it running on http://localhost:8000?")
    except Exception as e:
        print(f"❌ Prediction error: {e}")

def main():
    """Main function"""
    print("🏇 === LIVE RACE PREDICTION ===")
    print("Fetching latest race from database...")
    
    # Get race data from database
    race_data = get_last_race_from_db()
    
    if not race_data:
        return
    
    # Check if API is running
    try:
        health_check = requests.get("http://localhost:8000/health", timeout=5)
        if health_check.status_code == 200:
            health_data = health_check.json()
            print(f"✅ API Status: {health_data['status']}")
            print(f"✅ Model Loaded: {health_data['model_loaded']}")
        else:
            print("❌ API health check failed")
            return
    except:
        print("❌ API not running. Start it with: python ml_prediction_api.py")
        return
    
    # Display race info
    print(f"\n📋 RACE DETAILS:")
    for i, horse in enumerate(race_data['horses'], 1):
        print(f"{i:2d}. {horse['horse_name']:<25} - {horse['jockey_name']:<20} (Age: {horse['age']}, Barrier: {horse['stall_draw']})")
    
    # Get predictions
    predict_race(race_data)

if __name__ == "__main__":
    main()
