"""
Quick demo: Get tomorrow's games and show predictions
(Without requiring backend to be running)
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import sqlite3
import pandas as pd
import numpy as np
import torch
from datetime import datetime, timedelta
import logging

from models.multitask_model import create_model
from pipelines.feature_engineering_v2 import build_features_for_game

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "ncaa_basketball.db"


def get_upcoming_games_from_db(hours_ahead=48):
    """Get upcoming games directly from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow()
    cutoff = now + timedelta(hours=hours_ahead)
    
    cursor.execute("""
        SELECT 
            game_id, 
            home_team_name, 
            away_team_name, 
            game_date, 
            season
        FROM games
        WHERE game_date BETWEEN ? AND ?
        ORDER BY game_date
        LIMIT 20
    """, (now.isoformat(), cutoff.isoformat()))
    
    games = cursor.fetchall()
    conn.close()
    
    return [
        {
            'game_id': g[0],
            'home_team_name': g[1],
            'away_team_name': g[2],
            'game_date': g[3],
            'season': g[4]
        }
        for g in games
    ]


def load_multitask_model():
    """Load the trained multi-task model"""
    multitask_path = PROJECT_ROOT / 'models' / 'multitask_model_best.pth'
    
    if not multitask_path.exists():
        logger.error("Multi-task model not found!")
        return None
    
    checkpoint = torch.load(multitask_path, map_location='cpu', weights_only=False)
    
    feature_cols = checkpoint.get('feature_cols', [])
    input_dim = len(feature_cols)
    
    model, _ = create_model(input_dim, device='cpu')
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    # Create scaler
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaler.mean_ = checkpoint['scaler_mean']
    scaler.scale_ = checkpoint['scaler_scale']
    
    return {
        'model': model,
        'scaler': scaler,
        'feature_cols': feature_cols
    }


def make_prediction(game, model_info):
    """Make prediction for a single game"""
    try:
        # Build features
        features = build_features_for_game(
            game['game_id'],
            game['home_team_name'],
            game['away_team_name'],
            game['game_date'],
            game['season']
        )
        
        if features is None:
            return None
        
        # Prepare features for model
        model = model_info['model']
        scaler = model_info['scaler']
        feature_cols = model_info['feature_cols']
        
        # Ensure features match model's expected columns
        features_array = np.array([
            features.get(col, 0.0) for col in feature_cols
        ]).reshape(1, -1)
        
        features_scaled = scaler.transform(features_array)
        features_tensor = torch.FloatTensor(features_scaled)
        
        # Get predictions
        with torch.no_grad():
            predictions = model.predict_with_confidence(features_tensor)
        
        return {
            'win_prob': float(predictions['winner_prob'][0][0]),
            'margin_pred': float(predictions['margin_pred'][0]),
            'margin_lower': float(predictions['margin_lower'][0]),
            'margin_upper': float(predictions['margin_upper'][0]),
            'margin_confidence': float(predictions['margin_confidence'][0]),
            'total_pred': float(predictions['totals_pred'][0]),
            'total_lower': float(predictions['totals_lower'][0]),
            'total_upper': float(predictions['totals_upper'][0]),
            'total_confidence': float(predictions['totals_confidence'][0])
        }
        
    except Exception as e:
        logger.error(f"Error making prediction: {e}")
        return None


def main():
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL - TOMORROW'S GAMES PREDICTIONS")
    print("="*70 + "\n")
    
    # Load model
    print("Loading model...")
    model_info = load_multitask_model()
    
    if model_info is None:
        print("❌ Could not load model")
        return
    
    print(f"✅ Model loaded ({len(model_info['feature_cols'])} features)\n")
    
    # Get upcoming games
    print("Fetching upcoming games from database...")
    games = get_upcoming_games_from_db(hours_ahead=48)
    
    if not games:
        print("❌ No upcoming games found in the next 48 hours")
        return
    
    print(f"✅ Found {len(games)} upcoming games\n")
    
    # Make predictions for each game
    print("="*70)
    print("PREDICTIONS")
    print("="*70 + "\n")
    
    predictions_made = 0
    
    for i, game in enumerate(games, 1):
        print(f"Game {i}: {game['away_team_name']} @ {game['home_team_name']}")
        print(f"  Date: {game['game_date']}")
        print(f"  ID: {game['game_id']}")
        
        pred = make_prediction(game, model_info)
        
        if pred is None:
            print(f"  ⚠️ Could not make prediction (missing data)\n")
            continue
        
        # Determine predicted winner
        if pred['win_prob'] > 0.5:
            winner = game['home_team_name']
            winner_prob = pred['win_prob']
        else:
            winner = game['away_team_name']
            winner_prob = 1 - pred['win_prob']
        
        print(f"  🏆 Predicted Winner: {winner} ({winner_prob:.1%})")
        print(f"  📊 Margin: {pred['margin_pred']:.1f} points "
              f"[{pred['margin_lower']:.1f}, {pred['margin_upper']:.1f}] "
              f"(confidence: {pred['margin_confidence']:.0%})")
        print(f"  🎯 Total: {pred['total_pred']:.1f} points "
              f"[{pred['total_lower']:.1f}, {pred['total_upper']:.1f}] "
              f"(confidence: {pred['total_confidence']:.0%})")
        print()
        
        predictions_made += 1
    
    print("="*70)
    print(f"✅ Made predictions for {predictions_made}/{len(games)} games")
    print("="*70)
    
    if predictions_made < len(games):
        print(f"\n⚠️ Note: {len(games) - predictions_made} games had insufficient data for prediction")
        print("   (This is normal - player data may not be available for all teams)")


if __name__ == '__main__':
    main()

