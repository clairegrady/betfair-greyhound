#!/usr/bin/env python3
"""
ML Prediction API for Horse Racing Place Bets
FastAPI service that loads our trained XGBoost model and provides place predictions
"""

import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import os
from datetime import datetime
from prediction_tracker import PredictionTracker

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Horse Racing ML Prediction API",
    description="XGBoost model for predicting place bets (top 3 finish)",
    version="1.0.0"
)

# Global variables for loaded models
place_model = None
model_features = None
prediction_tracker = None
real_data_connector = None

class HorseData(BaseModel):
    """Input data for a single horse"""
    horse_name: str
    jockey_name: str
    trainer_name: str
    age: int
    weight_value: float
    stall_draw: int
    form: Optional[str] = "0"
    sire_name: Optional[str] = "Unknown"
    dam_name: Optional[str] = "Unknown"
    sex_type: Optional[str] = "F"
    days_since_last_run: Optional[int] = 14
    official_rating: Optional[float] = 50.0
    jockey_claim: Optional[float] = 0.0
    colours_description: Optional[str] = "Unknown"

class RaceData(BaseModel):
    """Input data for a complete race"""
    market_id: str
    market_name: str
    event_name: str
    horses: List[HorseData]
    race_date: Optional[str] = None

class PredictionResponse(BaseModel):
    """Response with place predictions"""
    market_id: str
    predictions: List[Dict[str, object]]
    model_confidence: float
    timestamp: str

def load_models():
    """Load the trained XGBoost place model"""
    global place_model, model_features, prediction_tracker, real_data_connector
    
    try:
        model_path = "/Users/clairegrady/RiderProjects/betfair/data-model/trained_models/target_place_xgb_model.joblib"
        
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False
            
        place_model = joblib.load(model_path)
        logger.info("✅ Successfully loaded XGBoost place model")
        
        # Get the exact features our model expects
        model_features = place_model.get_booster().feature_names
        
        logger.info(f"✅ Loaded model expecting {len(model_features)} features")
        
        # Initialize prediction tracker
        prediction_tracker = PredictionTracker()
        logger.info("✅ Initialized prediction tracker")
        
        # Initialize real data connector
        from fix_prediction_features import RealDataConnector
        real_data_connector = RealDataConnector()
        logger.info("✅ Initialized real data connector")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading model: {e}")
        return False

def create_features_from_race_data(race_data: RaceData) -> pd.DataFrame:
    """Convert race data to model features"""
    
    horses = race_data.horses
    field_size = len(horses)
    
    # Parse race date or use today
    try:
        if race_data.race_date:
            race_date = pd.to_datetime(race_data.race_date)
        else:
            race_date = pd.to_datetime('today')
    except:
        race_date = pd.to_datetime('today')
    
    # Extract race number from market name if possible
    race_number = 1
    if 'R' in race_data.market_name:
        try:
            race_number = int(race_data.market_name.split('R')[1].split(' ')[0])
        except:
            race_number = 1
    
    # Create base DataFrame
    df_list = []
    
    for i, horse in enumerate(horses):
        # Get real data for this horse
        real_stats = {}
        real_jockey = {}
        real_trainer = {}
        real_odds = {}
        
        if real_data_connector:
            try:
                # Get real career statistics
                real_stats = real_data_connector.get_horse_career_stats(horse.horse_name)
                
                # Get real jockey performance
                real_jockey = real_data_connector.get_jockey_performance(horse.jockey_name)
                
                # Get real trainer performance
                real_trainer = real_data_connector.get_trainer_performance(horse.trainer_name)
                
                # Get real odds (placeholder for now)
                real_odds = real_data_connector.get_betfair_odds(race_data.market_id, "")
                
            except Exception as e:
                logger.warning(f"Error getting real data for {horse.horse_name}: {e}")
                # Fall back to defaults
                real_stats = real_data_connector._get_default_career_stats()
                real_jockey = real_data_connector._get_default_jockey_stats()
                real_trainer = real_data_connector._get_default_trainer_stats()
                real_odds = real_data_connector._get_default_odds()
        else:
            # Fall back to defaults if connector not available
            real_stats = {'career_starts': 10, 'career_wins': 1, 'career_places': 3, 'career_win_rate': 0.1, 'career_place_rate': 0.3, 'recent_wins_3': 0, 'recent_places_3': 1, 'form_score': 1}
            real_jockey = {'jockey_win_rate': 0.15, 'is_top_jockey': 0}
            real_trainer = {'trainer_win_rate': 0.12, 'is_top_trainer': 0}
            real_odds = {'odds_log': np.log(5.0), 'implied_probability': 0.2, 'is_favourite': 0, 'is_longshot': 0}
        
        horse_features = {
                # Time features
                'year': race_date.year,
                'month': race_date.month,
                'day_of_week': race_date.dayofweek,
                'quarter': race_date.quarter,
                'is_weekend': 1 if race_date.dayofweek >= 5 else 0,
                'is_summer': 1 if race_date.month in [12, 1, 2] else 0,
                'is_autumn': 1 if race_date.month in [3, 4, 5] else 0,
                'is_winter': 1 if race_date.month in [6, 7, 8] else 0,
                'is_spring': 1 if race_date.month in [9, 10, 11] else 0,
                'is_carnival_season': 1 if race_date.month in [10, 11] else 0,
                
                # Race features
                'field_size': field_size,
                'field_size_log': np.log(field_size),
                'field_size_category': 1 if field_size <= 12 else 2,  # medium/large
                'distance_furlongs': 8.0,  # Default ~1600m
                'distance_log': np.log(8.0),
                'distance_category': 1,  # middle distance
                'prize_money_log': np.log(10000),  # Default prize money
                'prize_money_category': 1,  # medium prize
                'class_rating_scaled': 0.5,  # Default class
                'is_high_class': 0,
                
                # Track conditions
                'going_encoded': 2,  # Good going
                'is_firm_track': 1,
                'is_soft_track': 0,
                
                # Horse features
                'age': horse.age,
                'age_category': 1 if horse.age <= 5 else 2,  # young/prime
                'is_prime_age': 1 if horse.age <= 5 else 0,
                'weight_carried': horse.weight_value if horse.weight_value > 0 else 55.0,
                'weight_advantage': 0,  # Will calculate after loading all horses
                'is_topweight': 0,  # Will calculate after loading all horses
                
                # Sex encoding
                'sex_encoded': 0 if horse.sex_type == 'F' else 1,
                'is_male': 0 if horse.sex_type == 'F' else 1,
                'is_female': 1 if horse.sex_type == 'F' else 0,
                
                # Real odds data
                'odds_log': real_odds.get('odds_log', np.log(5.0)),
                'implied_probability': real_odds.get('implied_probability', 0.2),
                'is_favourite': real_odds.get('is_favourite', 0),
                'is_longshot': real_odds.get('is_longshot', 0),
                'odds_rank': i + 1,  # Default ranking by barrier
                'is_race_favourite': 1 if i == 0 else 0,
                'is_top3_choice': 1 if i < 3 else 0,
                'market_share': 1.0 / field_size,
                
                # Real historical features
                'career_starts': real_stats.get('career_starts', 10),
                'career_wins': real_stats.get('career_wins', 1),
                'career_places': real_stats.get('career_places', 3),
                'career_win_rate': real_stats.get('career_win_rate', 0.1),
                'career_place_rate': real_stats.get('career_place_rate', 0.3),
                'recent_wins_3': real_stats.get('recent_wins_3', 0),
                'recent_places_3': real_stats.get('recent_places_3', 1),
                'form_score': real_stats.get('form_score', 1),
                'days_since_last_race': horse.days_since_last_run if horse.days_since_last_run else 14,
                'is_fresh': 1 if (horse.days_since_last_run or 14) > 60 else 0,
                'is_quick_backup': 1 if (horse.days_since_last_run or 14) < 7 else 0,
                
                # Real jockey/trainer features
                'jockey_win_rate': real_jockey.get('jockey_win_rate', 0.15),
                'is_top_jockey': real_jockey.get('is_top_jockey', 0),
                'trainer_win_rate': real_trainer.get('trainer_win_rate', 0.12),
                'is_top_trainer': real_trainer.get('is_top_trainer', 0),
                
                # Venue features (will be updated with real venue data)
                'venue_win_rate': 0.10,
                'venue_avg_field': field_size,
                'venue_size': 1,  # Medium venue
                'is_major_venue': 0,
                
                # Race pattern features
                'race_number': race_number,
                'is_early_race': 1 if race_number <= 3 else 0,
                'is_late_race': 1 if race_number >= 7 else 0,
            }
        
        df_list.append(horse_features)
    
    df = pd.DataFrame(df_list)
    
    # Calculate relative weight features
    mean_weight = df['weight_carried'].mean()
    df['weight_advantage'] = df['weight_carried'] - mean_weight
    df['is_topweight'] = (df['weight_carried'] == df['weight_carried'].max()).astype(int)
    
    # Ensure all required features are present
    for feature in model_features:
        if feature not in df.columns:
            df[feature] = 0.0
            logger.warning(f"Missing feature {feature}, using default value 0.0")
    
    # Select only the features our model expects
    df = df[model_features]
    
    return df

@app.on_event("startup")
async def startup_event():
    """Load models when API starts"""
    logger.info("🚀 Starting ML Prediction API...")
    success = load_models()
    if not success:
        logger.error("❌ Failed to load models - API will not work properly")
    else:
        logger.info("✅ API ready to serve predictions")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Horse Racing ML Prediction API",
        "status": "running",
        "model_loaded": place_model is not None
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "model_loaded": place_model is not None,
        "expected_features": len(model_features) if model_features else 0,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/performance")
async def get_model_performance():
    """Get model performance metrics"""
    if prediction_tracker is None:
        raise HTTPException(status_code=500, detail="Prediction tracker not initialized")
    
    try:
        performance = prediction_tracker.get_performance_summary()
        accuracy = prediction_tracker.calculate_accuracy(confidence_threshold=0.6, days=7)
        
        return {
            "performance_summary": performance,
            "recent_accuracy": accuracy,
            "model_status": "TRACKING_ENABLED" if prediction_tracker else "TRACKING_DISABLED",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")

@app.post("/log-result")
async def log_race_result(market_id: str, horse_name: str, selection_id: str, actual_position: int):
    """Log actual race result for validation"""
    if prediction_tracker is None:
        raise HTTPException(status_code=500, detail="Prediction tracker not initialized")
    
    try:
        prediction_tracker.log_result(
            market_id=market_id,
            horse_name=horse_name,
            selection_id=selection_id,
            actual_position=actual_position
        )
        
        return {
            "status": "success",
            "message": f"Logged result for {horse_name} - Position {actual_position}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error logging result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log result: {str(e)}")

@app.post("/predict/place", response_model=PredictionResponse)
async def predict_place(race_data: RaceData):
    """Predict place probabilities for horses in a race"""
    
    if place_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not race_data.horses:
        raise HTTPException(status_code=400, detail="No horses provided")
    
    try:
        # Convert race data to features
        logger.info(f"🏇 Processing race {race_data.market_id} with {len(race_data.horses)} horses")
        features_df = create_features_from_race_data(race_data)
        
        # Get predictions
        place_probabilities = place_model.predict_proba(features_df)[:, 1]  # Probability of place (class 1)
        
        # Create response
        predictions = []
        for i, horse in enumerate(race_data.horses):
            predictions.append({
                "horse_name": horse.horse_name,
                "place_probability": float(place_probabilities[i]),
                "place_percentage": float(place_probabilities[i] * 100),
                "barrier": horse.stall_draw,
                "jockey": horse.jockey_name,
                "trainer": horse.trainer_name
            })
        
        # Sort by place probability (highest first)
        predictions.sort(key=lambda x: x["place_probability"], reverse=True)
        
        # Calculate model confidence (average of top 3 predictions)
        top3_probs = [p["place_probability"] for p in predictions[:3]]
        model_confidence = float(np.mean(top3_probs))
        
        # Log predictions for tracking
        if prediction_tracker:
            for i, pred in enumerate(predictions):
                confidence_level = "HIGH" if pred["place_probability"] >= 0.6 else "MEDIUM" if pred["place_probability"] >= 0.4 else "LOW"
                prediction_tracker.log_prediction(
                    market_id=race_data.market_id,
                    horse_name=pred["horse_name"],
                    selection_id="",  # TODO: Get from race data
                    predicted_prob=pred["place_probability"],
                    predicted_rank=i+1,
                    confidence_level=confidence_level
                )
        
        logger.info(f"✅ Generated predictions for {len(predictions)} horses")
        logger.info(f"📊 Top 3: {predictions[0]['horse_name']} ({predictions[0]['place_percentage']:.1f}%), "
                   f"{predictions[1]['horse_name']} ({predictions[1]['place_percentage']:.1f}%), "
                   f"{predictions[2]['horse_name']} ({predictions[2]['place_percentage']:.1f}%)")
        
        return PredictionResponse(
            market_id=race_data.market_id,
            predictions=predictions,
            model_confidence=model_confidence,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Horse Racing ML Prediction API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
