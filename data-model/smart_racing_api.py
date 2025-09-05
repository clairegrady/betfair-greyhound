#!/usr/bin/env python3
"""
Smart Racing Prediction API with Live Polling
- Polls database every 2 minutes for new races
- Automatically detects race status and switches to next race
- Maintains prediction history
- Provides live race updates
"""

import joblib
import pandas as pd
import numpy as np
import sqlite3
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Smart Racing Prediction API",
    description="Live polling horse racing predictions with race status detection",
    version="3.0.0"
)

# Global state
live_model = None
feature_list = None
current_race_data = None
race_history = []
last_poll_time = None
POLL_INTERVAL = 120  # 2 minutes

class RaceStatus:
    UPCOMING = "UPCOMING"
    LIVE = "LIVE" 
    FINISHED = "FINISHED"
    UNKNOWN = "UNKNOWN"

class SmartPredictionResponse(BaseModel):
    """Enhanced response with race status and polling info"""
    race_status: str
    market_id: str
    market_name: str
    event_name: str
    event_time: Optional[str] = None
    total_horses: int
    active_horses: int
    predictions: List[Dict]
    betting_recommendations: List[Dict]
    filtered_horses: List[str]
    last_updated: str
    next_poll_in: int
    race_history_count: int

def extract_form_features(form_str):
    """Extract features from form string"""
    if pd.isna(form_str) or form_str == '':
        return {
            'recent_wins_3': 0,
            'recent_places_3': 0,
            'last_3_avg': 9,
            'form_consistency': 0,
            'dnf_count': 0
        }
    
    form_str = str(form_str).upper()
    positions = []
    dnf_count = 0
    
    for char in form_str:
        if char.isdigit() and char != '0':
            positions.append(int(char))
        elif char in ['X', 'F', 'U', 'P']:
            dnf_count += 1
            positions.append(9)
    
    if not positions:
        positions = [9]
    
    recent_3 = positions[:3]
    recent_wins_3 = sum(1 for p in recent_3 if p == 1)
    recent_places_3 = sum(1 for p in recent_3 if p <= 3)
    last_3_avg = np.mean(recent_3)
    
    if len(recent_3) > 1:
        form_consistency = 1 / (1 + np.std(recent_3))
    else:
        form_consistency = 0.5
    
    return {
        'recent_wins_3': recent_wins_3,
        'recent_places_3': recent_places_3,
        'last_3_avg': last_3_avg,
        'form_consistency': form_consistency,
        'dnf_count': dnf_count
    }

def load_live_model():
    """Load the live data optimized model"""
    global live_model, feature_list
    
    try:
        model_path = "trained_models/live_data_place_model.joblib"
        features_path = "trained_models/live_data_features.txt"
        
        live_model = joblib.load(model_path)
        
        with open(features_path, 'r') as f:
            feature_list = [line.strip() for line in f.readlines()]
        
        logger.info(f"✅ Loaded live model with {len(feature_list)} features")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading live model: {e}")
        return False

def detect_race_status(race_df, market_name):
    """Detect if race is upcoming, live, or finished"""
    try:
        # Check for obvious finished indicators
        if 'REMOVED' in race_df['Status'].values:
            removed_count = len(race_df[race_df['Status'] == 'REMOVED'])
            active_count = len(race_df[race_df['Status'] == 'ACTIVE'])
            
            # If more than half are removed, likely finished
            if removed_count > active_count:
                return RaceStatus.FINISHED
        
        # Check market name for time indicators
        current_time = datetime.now()
        
        # Look for time patterns in market name (if available)
        if any(keyword in market_name.lower() for keyword in ['result', 'finished', 'winner']):
            return RaceStatus.FINISHED
        
        # If we have active horses, assume upcoming or live
        active_horses = len(race_df[race_df['Status'] == 'ACTIVE'])
        if active_horses > 0:
            return RaceStatus.UPCOMING  # Default to upcoming for betting
        else:
            return RaceStatus.FINISHED
            
    except Exception as e:
        logger.warning(f"Could not determine race status: {e}")
        return RaceStatus.UNKNOWN

def get_available_races():
    """Get all available races with status detection"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get distinct races ordered by latest entries
        query = """
        SELECT MarketId, MarketName, EventName, 
               COUNT(*) as total_horses,
               SUM(CASE WHEN Status = 'ACTIVE' THEN 1 ELSE 0 END) as active_horses,
               MAX(Id) as latest_id
        FROM HorseMarketBook 
        GROUP BY MarketId, MarketName, EventName
        HAVING active_horses > 0  -- Only races with active horses
        ORDER BY latest_id DESC
        LIMIT 10
        """
        
        races_df = pd.read_sql(query, conn)
        conn.close()
        
        races_with_status = []
        for _, race in races_df.iterrows():
            # Get full race data for status detection
            conn = sqlite3.connect(db_path)
            race_query = f"""
            SELECT Status FROM HorseMarketBook 
            WHERE MarketId = '{race['MarketId']}'
            """
            race_data = pd.read_sql(race_query, conn)
            conn.close()
            
            status = detect_race_status(race_data, race['MarketName'])
            
            races_with_status.append({
                'market_id': race['MarketId'],
                'market_name': race['MarketName'],
                'event_name': race['EventName'],
                'total_horses': int(race['total_horses']),
                'active_horses': int(race['active_horses']),
                'status': status
            })
        
        return races_with_status
        
    except Exception as e:
        logger.error(f"Database error getting races: {e}")
        return []

def get_best_race_for_betting():
    """Get the best race for betting (upcoming with most active horses)"""
    races = get_available_races()
    
    if not races:
        return None
    
    # Prioritize: UPCOMING > LIVE > others, then by active horse count
    upcoming_races = [r for r in races if r['status'] == RaceStatus.UPCOMING]
    live_races = [r for r in races if r['status'] == RaceStatus.LIVE]
    
    if upcoming_races:
        # Get upcoming race with most active horses
        best_race = max(upcoming_races, key=lambda x: x['active_horses'])
        logger.info(f"🎯 Selected UPCOMING race: {best_race['event_name']} - {best_race['market_name']}")
        return best_race
    elif live_races:
        # Get live race with most active horses
        best_race = max(live_races, key=lambda x: x['active_horses'])
        logger.info(f"🔴 Selected LIVE race: {best_race['event_name']} - {best_race['market_name']}")
        return best_race
    else:
        # Fallback to any race
        best_race = max(races, key=lambda x: x['active_horses'])
        logger.info(f"⚠️ Selected FALLBACK race: {best_race['event_name']} - {best_race['market_name']}")
        return best_race

def get_race_data(market_id):
    """Get full race data for a specific market"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        query = f"""
        SELECT MarketId, MarketName, EventName, SelectionId, RUNNER_NAME, 
               JOCKEY_NAME, TRAINER_NAME, AGE, WEIGHT_VALUE, STALL_DRAW, 
               FORM, SIRE_NAME, DAM_NAME, SEX_TYPE, DAYS_SINCE_LAST_RUN,
               Status
        FROM HorseMarketBook 
        WHERE MarketId = '{market_id}'
        ORDER BY RUNNER_NAME
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df
        
    except Exception as e:
        logger.error(f"Database error getting race data: {e}")
        return pd.DataFrame()

def create_features_from_live_data(race_df):
    """Create features from live race data - same as before"""
    if race_df.empty:
        return pd.DataFrame()
    
    # Extract form features for each horse
    form_features_list = []
    for _, row in race_df.iterrows():
        form_features = extract_form_features(row.get('FORM', ''))
        form_features_list.append(form_features)
    
    form_df = pd.DataFrame(form_features_list)
    
    # Basic features with NaN handling
    features_df = pd.DataFrame({
        'age': pd.to_numeric(race_df['AGE'], errors='coerce').fillna(5),
        'days_since_last_race': pd.to_numeric(race_df['DAYS_SINCE_LAST_RUN'], errors='coerce').fillna(14),
        'barrier': pd.to_numeric(race_df['STALL_DRAW'], errors='coerce').fillna(5),
        'weight_value': pd.to_numeric(race_df['WEIGHT_VALUE'], errors='coerce').fillna(55.0),
    })
    
    # Combine with form features
    features_df = pd.concat([features_df, form_df], axis=1)
    
    # Field features
    field_size = len(race_df)
    features_df['field_size'] = field_size
    
    # Weight features (relative to field)
    mean_weight = features_df['weight_value'].mean()
    features_df['weight_advantage'] = features_df['weight_value'] - mean_weight
    
    # Derived features to match training
    features_df['career_win_rate'] = features_df['recent_wins_3'] / 10
    features_df['career_place_rate'] = features_df['recent_places_3'] / 5
    
    # Binary features
    features_df['is_young'] = (features_df['age'] <= 4).astype(int)
    features_df['is_veteran'] = (features_df['age'] >= 8).astype(int)
    features_df['has_recent_win'] = (features_df['recent_wins_3'] > 0).astype(int)
    features_df['has_recent_place'] = (features_df['recent_places_3'] > 0).astype(int)
    features_df['good_recent_form'] = (features_df['last_3_avg'] <= 4).astype(int)
    features_df['quick_backup'] = (features_df['days_since_last_race'] <= 7).astype(int)
    
    # Ensure all required features are present
    for feature in feature_list:
        if feature not in features_df.columns:
            features_df[feature] = 0.0
    
    # Select only the features our model expects
    model_features = features_df[feature_list]
    
    # Add horse info for response (reset index to ensure alignment)
    race_df_reset = race_df.reset_index(drop=True)
    model_features = model_features.reset_index(drop=True)
    
    model_features['horse_name'] = race_df_reset['RUNNER_NAME']
    model_features['jockey'] = race_df_reset['JOCKEY_NAME']
    model_features['form'] = race_df_reset['FORM']
    model_features['days_off'] = race_df_reset['DAYS_SINCE_LAST_RUN']
    
    return model_features

async def poll_for_new_races():
    """Background task to poll for new races"""
    global current_race_data, last_poll_time, race_history
    
    while True:
        try:
            logger.info("🔄 Polling for new races...")
            
            # Get the best race for betting
            best_race = get_best_race_for_betting()
            
            if best_race:
                # Check if this is a different race than current
                if (current_race_data is None or 
                    current_race_data.get('market_id') != best_race['market_id']):
                    
                    # Archive old race if exists
                    if current_race_data:
                        race_history.append({
                            **current_race_data,
                            'archived_at': datetime.now().isoformat()
                        })
                        logger.info(f"📁 Archived race: {current_race_data['event_name']}")
                    
                    # Load new race data
                    race_df = get_race_data(best_race['market_id'])
                    active_horses = race_df[race_df['Status'] == 'ACTIVE']
                    
                    if not active_horses.empty:
                        # Generate predictions
                        features_df = create_features_from_live_data(active_horses)
                        
                        if not features_df.empty:
                            # Apply 120-day filter
                            filtered_out = features_df[features_df['days_off'] > 120]['horse_name'].tolist()
                            eligible_horses = features_df[features_df['days_off'] <= 120]
                            
                            if not eligible_horses.empty:
                                # Get predictions
                                X = eligible_horses[feature_list]
                                place_probabilities = live_model.predict_proba(X)[:, 1]
                                
                                # Create predictions
                                predictions = []
                                for i, (_, row) in enumerate(eligible_horses.iterrows()):
                                    # Handle NaN values safely
                                    days_off = row['days_off'] if not pd.isna(row['days_off']) else 14
                                    recent_wins = row['recent_wins_3'] if not pd.isna(row['recent_wins_3']) else 0
                                    recent_places = row['recent_places_3'] if not pd.isna(row['recent_places_3']) else 0
                                    form_avg = row['last_3_avg'] if not pd.isna(row['last_3_avg']) else 9.0
                                    
                                    predictions.append({
                                        "horse_name": str(row['horse_name']),
                                        "jockey": str(row['jockey']),
                                        "form": str(row['form']),
                                        "days_off": int(days_off),
                                        "place_probability": float(place_probabilities[i]),
                                        "place_percentage": float(place_probabilities[i] * 100),
                                        "recent_wins": int(recent_wins),
                                        "recent_places": int(recent_places),
                                        "form_avg": float(form_avg)
                                    })
                                
                                # Sort by place probability
                                predictions.sort(key=lambda x: x["place_probability"], reverse=True)
                                
                                # Betting recommendations
                                betting_recs = []
                                for pred in predictions:
                                    if pred["place_probability"] > 0.4:
                                        confidence = "HIGH" if pred["place_probability"] > 0.5 else "MEDIUM"
                                        betting_recs.append({
                                            "horse_name": pred["horse_name"],
                                            "place_percentage": pred["place_percentage"],
                                            "confidence": confidence,
                                            "reason": f"Form: {pred['form']}, Recent: {pred['recent_places']}/3 places"
                                        })
                                
                                # Update current race data
                                current_race_data = {
                                    'race_status': best_race['status'],
                                    'market_id': best_race['market_id'],
                                    'market_name': best_race['market_name'],
                                    'event_name': best_race['event_name'],
                                    'event_time': None,  # Add this field
                                    'total_horses': best_race['total_horses'],
                                    'active_horses': len(eligible_horses),
                                    'predictions': predictions,
                                    'betting_recommendations': betting_recs,
                                    'filtered_horses': filtered_out,
                                    'last_updated': datetime.now().isoformat()
                                }
                                
                                logger.info(f"🎯 Updated predictions for: {best_race['event_name']} - {best_race['market_name']}")
                                logger.info(f"   Active horses: {len(eligible_horses)}, Filtered: {len(filtered_out)}")
                                logger.info(f"   Top pick: {predictions[0]['horse_name']} ({predictions[0]['place_percentage']:.1f}%)")
            
            last_poll_time = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Error in polling: {e}")
        
        # Wait for next poll
        await asyncio.sleep(POLL_INTERVAL)

@app.on_event("startup")
async def startup_event():
    """Initialize API and start background polling"""
    logger.info("🚀 Starting Smart Racing Prediction API...")
    
    # Load model
    success = load_live_model()
    if not success:
        logger.error("❌ Failed to load model")
        return
    
    # Start background polling
    asyncio.create_task(poll_for_new_races())
    logger.info(f"🔄 Background polling started (every {POLL_INTERVAL} seconds)")

@app.get("/")
async def root():
    return {
        "message": "Smart Racing Prediction API", 
        "status": "running",
        "polling_interval": POLL_INTERVAL,
        "last_poll": last_poll_time.isoformat() if last_poll_time else None
    }

@app.get("/predict/current")
async def get_current_predictions():
    """Get predictions for the current best race"""
    
    if live_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if current_race_data is None:
        raise HTTPException(status_code=404, detail="No current race data available")
    
    # Calculate time until next poll
    if last_poll_time:
        time_since_poll = (datetime.now() - last_poll_time).total_seconds()
        next_poll_in = max(0, POLL_INTERVAL - int(time_since_poll))
    else:
        next_poll_in = 0
    
    return SmartPredictionResponse(
        **current_race_data,
        next_poll_in=next_poll_in,
        race_history_count=len(race_history)
    )

@app.get("/races/available")
async def get_available_races_endpoint():
    """Get all available races with status"""
    races = get_available_races()
    return {
        "races": races,
        "count": len(races),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/races/history")
async def get_race_history():
    """Get prediction history"""
    return {
        "history": race_history,
        "count": len(race_history),
        "current_race": current_race_data
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Smart Racing Prediction API with live polling...")
    uvicorn.run(app, host="0.0.0.0", port=8002)  # Different port
