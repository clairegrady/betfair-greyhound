"""
NCAA Basketball Paper Trading Script
- Fetches upcoming games from backend
- Updates lineups before prediction
- Loads trained models (XGBoost + Multi-task Neural Network)
- Makes predictions with confidence intervals
- Simulates paper trades with Kelly Criterion bet sizing
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import sqlite3
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import logging
import pickle
import torch
import json
from sklearn.preprocessing import StandardScaler

# Import our models
from models.multitask_model import create_model
from pipelines.feature_engineering_v2 import build_features_for_game

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "ncaa_basketball.db"
PAPER_TRADES_DB = PROJECT_ROOT / "paper_trades_ncaa.db"
BACKEND_URL = "http://localhost:5000"


def create_paper_trades_db():
    """Create database for paper trades if it doesn't exist"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            game_date TEXT NOT NULL,
            predicted_winner TEXT NOT NULL,
            predicted_margin REAL,
            predicted_total REAL,
            win_probability REAL,
            margin_confidence REAL,
            total_confidence REAL,
            margin_lower REAL,
            margin_upper REAL,
            total_lower REAL,
            total_upper REAL,
            home_odds REAL,
            away_odds REAL,
            stake_amount REAL,
            bet_type TEXT,
            model_version TEXT,
            actual_winner TEXT,
            actual_margin REAL,
            actual_total REAL,
            profit_loss REAL,
            is_settled INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_date 
        ON paper_trades(game_date)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_is_settled 
        ON paper_trades(is_settled)
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Paper trades database initialized")


def get_upcoming_games_from_backend(hours_ahead=8):
    """Fetch upcoming NCAA games from the C# backend"""
    try:
        endpoint = f"{BACKEND_URL}/api/ncaa/upcoming"
        params = {'hoursAhead': hours_ahead}
        
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        
        games = response.json()
        logger.info(f"✅ Fetched {len(games)} upcoming games from backend")
        return games
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to fetch games from backend: {e}")
        return []


def fetch_betfair_odds(game_id):
    """Fetch odds from Betfair via backend"""
    try:
        endpoint = f"{BACKEND_URL}/api/ncaa/odds/{game_id}"
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        
        odds_data = response.json()
        return {
            'home_odds': odds_data.get('homeOdds', 2.0),
            'away_odds': odds_data.get('awayOdds', 2.0),
            'has_odds': odds_data.get('hasOdds', False)
        }
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Could not fetch odds for game {game_id}: {e}")
        return {'home_odds': 2.0, 'away_odds': 2.0, 'has_odds': False}


def update_lineups_for_game(game_id, home_team, away_team, season):
    """Update lineup for a specific game from ESPN API"""
    from pipelines.update_live_lineups import fetch_espn_lineup
    
    try:
        players_count = fetch_espn_lineup(game_id, home_team, away_team, season)
        if players_count > 0:
            logger.info(f"✅ Updated lineup for {game_id}: {players_count} players")
            return True
        else:
            logger.debug(f"No lineup data available yet for {game_id}")
            return False
    except Exception as e:
        logger.debug(f"Failed to update lineup for {game_id}: {e}")
        return False


def load_models():
    """Load trained models (XGBoost and Multi-task Neural Network)"""
    models = {}
    
    # Load XGBoost model
    xgb_path = PROJECT_ROOT / 'models' / 'xgboost_winner.pkl'
    if xgb_path.exists():
        with open(xgb_path, 'rb') as f:
            models['xgboost'] = pickle.load(f)
        logger.info("✅ Loaded XGBoost model")
    else:
        logger.warning("⚠️ XGBoost model not found")
    
    # Load Multi-task Neural Network
    multitask_path = PROJECT_ROOT / 'models' / 'multitask_model_best.pth'
    if multitask_path.exists():
        checkpoint = torch.load(multitask_path, map_location='cpu', weights_only=False)
        
        # Get input dimension from checkpoint
        feature_cols = checkpoint.get('feature_cols', [])
        input_dim = len(feature_cols)
        
        model, _ = create_model(input_dim, device='cpu')
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        # Create scaler from saved parameters
        scaler = StandardScaler()
        scaler.mean_ = checkpoint['scaler_mean']
        scaler.scale_ = checkpoint['scaler_scale']
        
        models['multitask'] = {
            'model': model,
            'scaler': scaler,
            'feature_cols': feature_cols
        }
        logger.info("✅ Loaded Multi-task Neural Network")
    else:
        logger.warning("⚠️ Multi-task model not found")
    
    return models


def make_prediction(game, models):
    """
    Make prediction for a game using ensemble of models.
    Returns dict with predictions and confidence levels.
    """
    try:
        # Build features for the game
        features = build_features_for_game(
            game['game_id'],
            game['home_team_name'],
            game['away_team_name'],
            game['game_date'],
            game['season']
        )
        
        if features is None:
            logger.warning(f"Could not build features for game {game['game_id']}")
            return None
        
        predictions = {
            'game_id': game['game_id'],
            'home_team': game['home_team_name'],
            'away_team': game['away_team_name'],
            'game_date': game['game_date']
        }
        
        # XGBoost prediction (winner only)
        if 'xgboost' in models:
            xgb_model = models['xgboost']
            xgb_prob = xgb_model.predict_proba([features])[0][1]  # Probability of home win
            predictions['xgb_win_prob'] = float(xgb_prob)
        
        # Multi-task Neural Network prediction
        if 'multitask' in models:
            mt_model = models['multitask']['model']
            scaler = models['multitask']['scaler']
            feature_cols = models['multitask']['feature_cols']
            
            # Ensure features are in correct order
            features_array = np.array([features[col] if col in features else 0.0 
                                       for col in feature_cols]).reshape(1, -1)
            features_scaled = scaler.transform(features_array)
            features_tensor = torch.FloatTensor(features_scaled)
            
            with torch.no_grad():
                mt_predictions = mt_model.predict_with_confidence(features_tensor)
                
                predictions['mt_win_prob'] = float(mt_predictions['winner_prob'][0][0])
                predictions['margin_pred'] = float(mt_predictions['margin_pred'][0])
                predictions['margin_lower'] = float(mt_predictions['margin_lower'][0])
                predictions['margin_upper'] = float(mt_predictions['margin_upper'][0])
                predictions['margin_confidence'] = float(mt_predictions['margin_confidence'][0])
                predictions['total_pred'] = float(mt_predictions['totals_pred'][0])
                predictions['total_lower'] = float(mt_predictions['totals_lower'][0])
                predictions['total_upper'] = float(mt_predictions['totals_upper'][0])
                predictions['total_confidence'] = float(mt_predictions['totals_confidence'][0])
        
        # Ensemble: average XGBoost and Multi-task win probabilities
        if 'xgb_win_prob' in predictions and 'mt_win_prob' in predictions:
            predictions['win_prob'] = (predictions['xgb_win_prob'] + predictions['mt_win_prob']) / 2
        elif 'mt_win_prob' in predictions:
            predictions['win_prob'] = predictions['mt_win_prob']
        elif 'xgb_win_prob' in predictions:
            predictions['win_prob'] = predictions['xgb_win_prob']
        else:
            logger.warning("No valid predictions available")
            return None
        
        # Determine predicted winner
        predictions['predicted_winner'] = (
            game['home_team_name'] if predictions['win_prob'] > 0.5 
            else game['away_team_name']
        )
        
        return predictions
        
    except Exception as e:
        logger.error(f"Error making prediction for game {game['game_id']}: {e}")
        return None


def kelly_criterion(win_prob, odds, fraction=0.25):
    """
    Calculate optimal bet size using Kelly Criterion.
    
    Args:
        win_prob: Probability of winning (0-1)
        odds: Decimal odds (e.g., 2.5)
        fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
    
    Returns:
        Bet size as fraction of bankroll (0-1)
    """
    if odds <= 1.0:
        return 0.0
    
    # Kelly formula: (bp - q) / b
    # where b = odds - 1, p = win_prob, q = 1 - win_prob
    b = odds - 1
    p = win_prob
    q = 1 - p
    
    kelly = (b * p - q) / b
    
    # Apply fractional Kelly
    kelly = kelly * fraction
    
    # Clamp between 0 and max (never bet more than 10% even with full Kelly)
    return max(0.0, min(kelly, 0.10))


def calculate_stake(prediction, odds_data, bankroll=1000.0, min_edge=0.05, min_confidence=0.6):
    """
    Calculate stake amount based on edge and confidence.
    
    Returns None if no bet should be placed.
    """
    win_prob = prediction['win_prob']
    home_odds = odds_data['home_odds']
    away_odds = odds_data['away_odds']
    
    # Determine which team we're betting on
    betting_home = win_prob > 0.5
    bet_prob = win_prob if betting_home else (1 - win_prob)
    bet_odds = home_odds if betting_home else away_odds
    
    # Calculate edge (difference between our probability and implied probability)
    implied_prob = 1.0 / bet_odds
    edge = bet_prob - implied_prob
    
    # Check minimum edge requirement
    if edge < min_edge:
        logger.debug(f"Edge too small: {edge:.3f} < {min_edge:.3f}")
        return None
    
    # Check confidence requirements
    margin_confidence = prediction.get('margin_confidence', 0.0)
    if margin_confidence < min_confidence:
        logger.debug(f"Confidence too low: {margin_confidence:.3f} < {min_confidence:.3f}")
        return None
    
    # Calculate stake using Kelly Criterion
    kelly_fraction = kelly_criterion(bet_prob, bet_odds, fraction=0.25)
    stake = bankroll * kelly_fraction
    
    # Minimum stake threshold
    if stake < 10.0:
        return None
    
    return {
        'stake': round(stake, 2),
        'bet_team': prediction['predicted_winner'],
        'bet_odds': bet_odds,
        'edge': edge,
        'kelly_fraction': kelly_fraction
    }


def save_paper_trade(prediction, odds_data, stake_info):
    """Save paper trade to database"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO paper_trades (
            game_id, timestamp, home_team, away_team, game_date,
            predicted_winner, predicted_margin, predicted_total,
            win_probability, margin_confidence, total_confidence,
            margin_lower, margin_upper, total_lower, total_upper,
            home_odds, away_odds, stake_amount, bet_type, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prediction['game_id'],
        datetime.now(timezone.utc).isoformat(),
        prediction['home_team'],
        prediction['away_team'],
        prediction['game_date'],
        prediction['predicted_winner'],
        prediction.get('margin_pred'),
        prediction.get('total_pred'),
        prediction['win_prob'],
        prediction.get('margin_confidence'),
        prediction.get('total_confidence'),
        prediction.get('margin_lower'),
        prediction.get('margin_upper'),
        prediction.get('total_lower'),
        prediction.get('total_upper'),
        odds_data['home_odds'],
        odds_data['away_odds'],
        stake_info['stake'],
        'MONEYLINE',
        'v2_ensemble_multitask'
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"💰 PAPER TRADE SAVED")
    logger.info(f"   {stake_info['bet_team']} @ {stake_info['bet_odds']:.2f}")
    logger.info(f"   Stake: ${stake_info['stake']:.2f}")
    logger.info(f"   Edge: {stake_info['edge']:.1%}")
    logger.info(f"   Win Prob: {prediction['win_prob']:.1%}")


def main(hours_ahead=8, min_edge=0.05, min_confidence=0.6, bankroll=1000.0):
    """Main paper trading loop"""
    logger.info("\n" + "="*70)
    logger.info("NCAA BASKETBALL PAPER TRADING")
    logger.info("="*70)
    logger.info(f"Time window: {hours_ahead} hours")
    logger.info(f"Min edge: {min_edge:.1%}")
    logger.info(f"Min confidence: {min_confidence:.1%}")
    logger.info(f"Bankroll: ${bankroll:.2f}")
    logger.info("="*70)
    
    # Initialize
    create_paper_trades_db()
    
    # Load models
    logger.info("\nLoading models...")
    models = load_models()
    
    if not models:
        logger.error("❌ No models loaded. Cannot make predictions.")
        return
    
    # Fetch upcoming games
    logger.info("\nFetching upcoming games...")
    games = get_upcoming_games_from_backend(hours_ahead)
    
    if not games:
        logger.info("No upcoming games found")
        return
    
    # Process each game
    trades_made = 0
    for game in games:
        logger.info("\n" + "-"*70)
        logger.info(f"Game: {game['away_team_name']} @ {game['home_team_name']}")
        logger.info(f"Date: {game['game_date']}")
        logger.info(f"ID: {game['game_id']}")
        
        # Update lineups
        logger.info("Checking for lineup updates...")
        lineup_updated = update_lineups_for_game(
            game['game_id'],
            game['home_team_name'],
            game['away_team_name'],
            game['season']
        )
        
        # Make prediction
        logger.info("Making prediction...")
        prediction = make_prediction(game, models)
        
        if prediction is None:
            logger.warning("⚠️ Could not make prediction for this game")
            continue
        
        logger.info(f"Predicted winner: {prediction['predicted_winner']} "
                   f"(prob: {prediction['win_prob']:.1%})")
        
        if 'margin_pred' in prediction:
            logger.info(f"Predicted margin: {prediction['margin_pred']:.1f} "
                       f"[{prediction['margin_lower']:.1f}, {prediction['margin_upper']:.1f}] "
                       f"(conf: {prediction['margin_confidence']:.1%})")
        
        if 'total_pred' in prediction:
            logger.info(f"Predicted total: {prediction['total_pred']:.1f} "
                       f"[{prediction['total_lower']:.1f}, {prediction['total_upper']:.1f}] "
                       f"(conf: {prediction['total_confidence']:.1%})")
        
        # Fetch odds
        logger.info("Fetching odds...")
        odds_data = fetch_betfair_odds(game['game_id'])
        
        if not odds_data['has_odds']:
            logger.info("⚠️ No odds available yet")
            continue
        
        logger.info(f"Odds: {game['home_team_name']} @ {odds_data['home_odds']:.2f}, "
                   f"{game['away_team_name']} @ {odds_data['away_odds']:.2f}")
        
        # Calculate stake
        stake_info = calculate_stake(prediction, odds_data, bankroll, min_edge, min_confidence)
        
        if stake_info is None:
            logger.info("❌ No bet: insufficient edge or confidence")
            continue
        
        # Save paper trade
        save_paper_trade(prediction, odds_data, stake_info)
        trades_made += 1
    
    logger.info("\n" + "="*70)
    logger.info(f"✅ Paper trading complete!")
    logger.info(f"   Processed {len(games)} games")
    logger.info(f"   Made {trades_made} paper trades")
    logger.info("="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='NCAA Basketball Paper Trading')
    parser.add_argument('--hours', type=int, default=8, help='Hours ahead to look for games')
    parser.add_argument('--min-edge', type=float, default=0.05, help='Minimum edge required')
    parser.add_argument('--min-confidence', type=float, default=0.6, help='Minimum confidence required')
    parser.add_argument('--bankroll', type=float, default=1000.0, help='Starting bankroll')
    
    args = parser.parse_args()
    
    main(
        hours_ahead=args.hours,
        min_edge=args.min_edge,
        min_confidence=args.min_confidence,
        bankroll=args.bankroll
    )

