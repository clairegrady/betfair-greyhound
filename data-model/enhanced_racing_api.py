#!/usr/bin/env python3
"""
Enhanced Racing API - Complete Betting Integration
- HorseMarketBook: Horse info and form
- MarketBookBackPrices: Back betting odds
- MarketBookLayPrices: Lay betting odds  
- ML predictions with market odds comparison
"""

import joblib
import pandas as pd
import numpy as np
import sqlite3
import math
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def safe_json_encoder(obj):
    """Custom JSON encoder that handles NaN and numpy types"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, 'dict') and callable(obj.dict):
        # Handle Pydantic models
        return obj.dict()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced Racing Prediction API",
    description="Complete betting integration with ML predictions and market odds",
    version="4.0.0"
)

# Global variables
live_model = None
feature_list = None

class BettingOdds(BaseModel):
    """Betting odds information"""
    lowest_back_price: Optional[float] = None  # Best for bettor (lowest odds)
    lowest_back_size: Optional[float] = None
    highest_back_price: Optional[float] = None  # Worst for bettor (highest odds)
    highest_back_size: Optional[float] = None
    lowest_lay_price: Optional[float] = None  # Best for layer (lowest odds)
    lowest_lay_size: Optional[float] = None
    last_price_traded: Optional[float] = None
    total_matched: Optional[float] = None
    # All available odds
    all_back_prices: List[Dict] = []
    all_lay_prices: List[Dict] = []
    market_depth: Optional[str] = None  # "SHALLOW", "MODERATE", "DEEP"

class HorsePrediction(BaseModel):
    """Enhanced horse prediction with betting odds"""
    horse_name: str
    selection_id: str
    jockey: str
    form: str
    days_off: int
    place_probability: float
    place_percentage: float
    recent_wins: int
    recent_places: int
    form_avg: float
    betting_odds: BettingOdds
    market_position: Optional[str] = None  # "FAVOURITE", "SECOND FAV", etc.

class RaceInfo(BaseModel):
    """Enhanced race information"""
    market_id: str
    market_name: str
    event_name: str
    total_horses: int
    active_horses: int
    status: str

class EnhancedPredictionResponse(BaseModel):
    """Enhanced response with betting odds"""
    race_info: RaceInfo
    active_horses: int
    predictions: List[HorsePrediction]
    betting_recommendations: List[Dict]
    filtered_horses: List[str]
    timestamp: str
    market_summary: Dict

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
        elif char.lower() == 'x':  # Spell (long break)
            continue
        elif char in ['F', 'FF', 'P', 'L', 'U', 'B', 'R', 'S', 'T', 'V']:
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

def get_betting_odds(market_id, selection_id):
    """Get betting odds for a specific horse"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get ALL back prices
        back_query = f"""
        SELECT Price, Size, LastPriceTraded, TotalMatched
        FROM MarketBookBackPrices 
        WHERE MarketId = '{market_id}' AND SelectionId = '{selection_id}' AND Status = 'ACTIVE'
        ORDER BY Price ASC
        """
        back_df = pd.read_sql(back_query, conn)
        
        # Get ALL lay prices
        lay_query = f"""
        SELECT Price, Size
        FROM MarketBookLayPrices 
        WHERE MarketId = '{market_id}' AND SelectionId = '{selection_id}' AND Status = 'ACTIVE'
        ORDER BY Price ASC
        """
        lay_df = pd.read_sql(lay_query, conn)
        
        conn.close()
        
        # Extract price values and clean NaN
        lowest_back_price = back_df['Price'].iloc[0] if not back_df.empty else None
        lowest_back_size = back_df['Size'].iloc[0] if not back_df.empty else None
        highest_back_price = back_df['Price'].iloc[-1] if not back_df.empty else None
        highest_back_size = back_df['Size'].iloc[-1] if not back_df.empty else None
        
        # Clean NaN values for traded data
        last_traded_raw = back_df['LastPriceTraded'].iloc[0] if not back_df.empty else None
        last_price_traded = None if pd.isna(last_traded_raw) else last_traded_raw
        
        total_matched_raw = back_df['TotalMatched'].iloc[0] if not back_df.empty else None
        total_matched = 0.0 if pd.isna(total_matched_raw) else total_matched_raw
        
        lowest_lay_price = lay_df['Price'].iloc[0] if not lay_df.empty else None
        lowest_lay_size = lay_df['Size'].iloc[0] if not lay_df.empty else None
        
        # Convert all prices to list of dicts
        all_back_prices = []
        for _, row in back_df.iterrows():
            all_back_prices.append({
                "price": float(row['Price']),
                "size": float(row['Size'])
            })
        
        all_lay_prices = []
        for _, row in lay_df.iterrows():
            all_lay_prices.append({
                "price": float(row['Price']),
                "size": float(row['Size'])
            })
        
        # Determine market depth
        market_depth = "SHALLOW"
        if len(all_back_prices) >= 3:
            market_depth = "DEEP"
        elif len(all_back_prices) >= 2:
            market_depth = "MODERATE"
        
        return BettingOdds(
            lowest_back_price=lowest_back_price,
            lowest_back_size=lowest_back_size,
            highest_back_price=highest_back_price,
            highest_back_size=highest_back_size,
            lowest_lay_price=lowest_lay_price,
            lowest_lay_size=lowest_lay_size,
            last_price_traded=last_price_traded,
            total_matched=total_matched,
            all_back_prices=all_back_prices,
            all_lay_prices=all_lay_prices,
            market_depth=market_depth
        )
        
    except Exception as e:
        logger.warning(f"Could not get betting odds for {selection_id}: {e}")
        return BettingOdds()

def get_market_position(back_price, all_back_prices):
    """Determine market position based on back price"""
    if back_price is None:
        return None
    
    # Sort all prices to find position
    sorted_prices = sorted([p for p in all_back_prices if p is not None])
    
    if back_price == sorted_prices[0]:
        return "FAVOURITE"
    elif len(sorted_prices) > 1 and back_price == sorted_prices[1]:
        return "SECOND FAV"
    elif len(sorted_prices) > 2 and back_price == sorted_prices[2]:
        return "THIRD FAV"
    elif back_price <= 3.0:
        return "SHORT PRICE"
    elif back_price <= 10.0:
        return "MIDDLE PRICE"
    else:
        return "LONG SHOT"

def get_all_available_races():
    """Get all available races with betting data"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT MarketId, MarketName, EventName, 
               COUNT(*) as total_horses,
               SUM(CASE WHEN Status = 'ACTIVE' THEN 1 ELSE 0 END) as active_horses,
               MAX(Id) as latest_id
        FROM HorseMarketBook 
        GROUP BY MarketId, MarketName, EventName
        HAVING active_horses > 0
        ORDER BY latest_id DESC
        LIMIT 15
        """
        
        races_df = pd.read_sql(query, conn)
        conn.close()
        
        races = []
        for _, race in races_df.iterrows():
            # Simple status determination
            if race['active_horses'] >= race['total_horses'] * 0.8:
                status = "UPCOMING"
            elif race['active_horses'] > 0:
                status = "LIVE"
            else:
                status = "FINISHED"
                
            races.append(RaceInfo(
                market_id=race['MarketId'],
                market_name=race['MarketName'],
                event_name=race['EventName'],
                total_horses=int(race['total_horses']),
                active_horses=int(race['active_horses']),
                status=status
            ))
        
        return races
        
    except Exception as e:
        logger.error(f"Database error getting races: {e}")
        return []

def get_best_race():
    """Get the best race for betting"""
    races = get_all_available_races()
    
    if not races:
        return None
    
    # Sort by active horses (descending) and prefer upcoming races
    upcoming_races = [r for r in races if r.status == "UPCOMING"]
    if upcoming_races:
        return max(upcoming_races, key=lambda x: x.active_horses)
    else:
        return max(races, key=lambda x: x.active_horses)

def get_enhanced_race_data(market_id):
    """Get comprehensive race data with betting odds"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get horse data
        horse_query = f"""
        SELECT MarketId, MarketName, EventName, SelectionId, RUNNER_NAME, 
               JOCKEY_NAME, TRAINER_NAME, AGE, WEIGHT_VALUE, STALL_DRAW, 
               FORM, SIRE_NAME, DAM_NAME, SEX_TYPE, DAYS_SINCE_LAST_RUN,
               Status
        FROM HorseMarketBook 
        WHERE MarketId = '{market_id}'
        ORDER BY RUNNER_NAME
        """
        
        horse_df = pd.read_sql(horse_query, conn)
        
        # Get all back prices for market position calculation
        back_prices_query = f"""
        SELECT SelectionId, MIN(Price) as lowest_back_price
        FROM MarketBookBackPrices 
        WHERE MarketId = '{market_id}' AND Status = 'ACTIVE'
        GROUP BY SelectionId
        """
        back_prices_df = pd.read_sql(back_prices_query, conn)
        
        conn.close()
        
        return horse_df, back_prices_df
        
    except Exception as e:
        logger.error(f"Database error getting race data: {e}")
        return pd.DataFrame(), pd.DataFrame()

def create_features_from_live_data(race_df):
    """Create features from live race data"""
    if race_df.empty:
        return pd.DataFrame()
    
    # Extract form features
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
    
    # Weight features
    mean_weight = features_df['weight_value'].mean()
    features_df['weight_advantage'] = features_df['weight_value'] - mean_weight
    
    # Derived features
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
    
    # Select features and add horse info
    model_features = features_df[feature_list].copy()
    
    race_df_reset = race_df.reset_index(drop=True)
    model_features = model_features.reset_index(drop=True)
    
    model_features['horse_name'] = race_df_reset['RUNNER_NAME']
    model_features['jockey'] = race_df_reset['JOCKEY_NAME']
    model_features['form'] = race_df_reset['FORM']
    model_features['days_off'] = race_df_reset['DAYS_SINCE_LAST_RUN']
    model_features['selection_id'] = race_df_reset['SelectionId']
    
    return model_features

def predict_enhanced_race(market_id):
    """Generate enhanced predictions with betting odds"""
    if live_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    # Get comprehensive race data
    race_df, back_prices_df = get_enhanced_race_data(market_id)
    if race_df.empty:
        raise HTTPException(status_code=404, detail="Race not found")
    
    # Filter to active horses
    active_horses = race_df[race_df['Status'] == 'ACTIVE']
    if active_horses.empty:
        raise HTTPException(status_code=400, detail="No active horses found")
    
    # Create features
    features_df = create_features_from_live_data(active_horses)
    if features_df.empty:
        raise HTTPException(status_code=400, detail="Could not create features")
    
    # Apply 120-day filter
    filtered_out = features_df[features_df['days_off'] > 120]['horse_name'].tolist()
    eligible_horses = features_df[features_df['days_off'] <= 120]
    
    if eligible_horses.empty:
        raise HTTPException(status_code=400, detail="No horses eligible after 120-day filter")
    
    # Get predictions
    X = eligible_horses[feature_list]
    place_probabilities = live_model.predict_proba(X)[:, 1]
    
        # Get all back prices for market position
    all_back_prices = back_prices_df['lowest_back_price'].tolist() if not back_prices_df.empty else []
    
    # Create enhanced predictions
    predictions = []
    for i, (_, row) in enumerate(eligible_horses.iterrows()):
        # Safe value extraction
        days_off = row['days_off'] if not pd.isna(row['days_off']) else 14
        recent_wins = row['recent_wins_3'] if not pd.isna(row['recent_wins_3']) else 0
        recent_places = row['recent_places_3'] if not pd.isna(row['recent_places_3']) else 0
        form_avg = row['last_3_avg'] if not pd.isna(row['last_3_avg']) else 9.0
        
        # Get betting odds
        selection_id = row['selection_id']
        betting_odds = get_betting_odds(market_id, selection_id)
        
        # Determine market position
        market_position = get_market_position(betting_odds.lowest_back_price, all_back_prices)
        
        # Clean NaN values before creating the object
        clean_prob = place_probabilities[i] if not np.isnan(place_probabilities[i]) else 0.0
        clean_form_avg = form_avg if not np.isnan(form_avg) else 0.0
        clean_recent_wins = recent_wins if not np.isnan(recent_wins) else 0
        clean_recent_places = recent_places if not np.isnan(recent_places) else 0
        
        predictions.append(HorsePrediction(
            horse_name=str(row['horse_name']),
            selection_id=str(selection_id),
            jockey=str(row['jockey']),
            form=str(row['form']),
            days_off=int(days_off),
            place_probability=float(clean_prob),
            place_percentage=float(clean_prob * 100),
            recent_wins=int(clean_recent_wins),
            recent_places=int(clean_recent_places),
            form_avg=float(clean_form_avg),
            betting_odds=betting_odds,
            market_position=market_position
        ))
    
    # Sort by probability
    predictions.sort(key=lambda x: x.place_probability, reverse=True)
    
    # Betting recommendations with odds
    betting_recs = []
    for pred in predictions:
        if pred.place_probability > 0.4:  # 40% threshold
            confidence = "HIGH" if pred.place_probability > 0.5 else "MEDIUM"
            
                        # Add odds analysis
            odds_analysis = ""
            if pred.betting_odds.lowest_back_price:
                odds_analysis = f"Back: {pred.betting_odds.lowest_back_price}"
                if pred.betting_odds.lowest_lay_price:
                    odds_analysis += f", Lay: {pred.betting_odds.lowest_lay_price}"
            
            betting_recs.append({
                "horse_name": pred.horse_name,
                "place_percentage": pred.place_percentage,
                "confidence": confidence,
                "market_position": pred.market_position,
                "odds": odds_analysis,
                "reason": f"Form: {pred.form}, Recent: {pred.recent_places}/3 places"
            })
    
    # Race info
    race_info = RaceInfo(
        market_id=market_id,
        market_name=race_df['MarketName'].iloc[0],
        event_name=race_df['EventName'].iloc[0],
        total_horses=len(race_df),
        active_horses=len(eligible_horses),
        status="ACTIVE"
    )
    
    # Market summary
    logger.info(f"Creating market summary for {len(predictions)} predictions")
    
    # Calculate average back price with NaN handling
    back_prices = [p.betting_odds.lowest_back_price for p in predictions if p.betting_odds.lowest_back_price is not None]
    avg_back_price = float(np.mean(back_prices)) if back_prices else 0.0
    
    logger.info(f"Back prices: {back_prices}")
    logger.info(f"Average back price: {avg_back_price}")
    
    market_summary = {
        "total_horses": len(race_df),
        "active_horses": len(eligible_horses),
        "filtered_horses": len(filtered_out),
        "favorites_count": len([p for p in predictions if p.market_position == "FAVOURITE"]),
        "short_prices_count": len([p for p in predictions if p.market_position in ["FAVOURITE", "SECOND FAV", "THIRD FAV"]]),
        "avg_back_price": avg_back_price
    }
    
    logger.info(f"Market summary created: {market_summary}")
    
    logger.info("Creating EnhancedPredictionResponse")
    try:
        response = EnhancedPredictionResponse(
            race_info=race_info,
            active_horses=len(eligible_horses),
            predictions=predictions,
            betting_recommendations=betting_recs,
            filtered_horses=filtered_out,
            timestamp=datetime.now().isoformat(),
            market_summary=market_summary
        )
        logger.info("Response created successfully")
        return response
    except Exception as e:
        logger.error(f"Error creating response: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """Load model when API starts"""
    logger.info("🚀 Starting Enhanced Racing Prediction API with betting integration...")
    success = load_live_model()
    if not success:
        logger.error("❌ Failed to load model")

@app.get("/")
async def root():
    return {
        "message": "Enhanced Racing Prediction API with Betting Integration", 
        "status": "running",
        "model_loaded": live_model is not None,
        "features": "HorseMarketBook + MarketBookBackPrices + MarketBookLayPrices + ML"
    }

@app.get("/races", response_model=List[RaceInfo])
async def get_available_races():
    """Get all available races"""
    races = get_all_available_races()
    return races

@app.get("/races/best", response_model=RaceInfo)
async def get_best_race_info():
    """Get the best race for betting"""
    best_race = get_best_race()
    if not best_race:
        raise HTTPException(status_code=404, detail="No races available")
    return best_race

@app.get("/predict/{market_id}")
async def predict_specific_race(market_id: str):
    """Get enhanced predictions for a specific race with betting odds"""
    logger.info(f"🏇 Predicting race with betting data: {market_id}")
    result = predict_enhanced_race(market_id)
    # Convert to dict and use custom JSON encoder
    result_dict = result.dict()
    json_str = json.dumps(result_dict, default=safe_json_encoder)
    return JSONResponse(content=json.loads(json_str))

@app.get("/predict/best", response_model=EnhancedPredictionResponse)
async def predict_best_race():
    """Get enhanced predictions for the best available race"""
    best_race = get_best_race()
    if not best_race:
        raise HTTPException(status_code=404, detail="No races available")
    
    logger.info(f"🎯 Predicting best race with betting data: {best_race.event_name} - {best_race.market_name}")
    return predict_enhanced_race(best_race.market_id)

@app.get("/polling/update", response_model=EnhancedPredictionResponse)
async def polling_update():
    """
    Endpoint for C# to call every 2 minutes
    Returns enhanced predictions for the best available race
    """
    logger.info("📡 Enhanced polling update requested")
    return await predict_best_race()

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Enhanced Racing Prediction API with betting integration...")
    uvicorn.run(app, host="0.0.0.0", port=8004)
