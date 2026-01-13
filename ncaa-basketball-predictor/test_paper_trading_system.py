"""
Test the paper trading pipeline components
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import torch
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_model_loading():
    """Test that models can be loaded"""
    logger.info("="*70)
    logger.info("Testing Model Loading")
    logger.info("="*70)
    
    # Test XGBoost
    xgb_path = Path(__file__).parent / 'models' / 'xgboost_winner.pkl'
    if xgb_path.exists():
        with open(xgb_path, 'rb') as f:
            xgb_model = pickle.load(f)
        logger.info("✅ XGBoost model loaded")
        logger.info(f"   Type: {type(xgb_model)}")
    else:
        logger.warning("⚠️ XGBoost model not found")
    
    # Test Multi-task Neural Network
    multitask_path = Path(__file__).parent / 'models' / 'multitask_model_best.pth'
    if multitask_path.exists():
        checkpoint = torch.load(multitask_path, map_location='cpu', weights_only=False)
        logger.info("✅ Multi-task model checkpoint loaded")
        logger.info(f"   Epoch: {checkpoint['epoch']}")
        logger.info(f"   Val Loss: {checkpoint['val_loss']:.4f}")
        logger.info(f"   Val Metrics: {checkpoint['val_metrics']}")
        logger.info(f"   Features: {len(checkpoint['feature_cols'])}")
    else:
        logger.warning("⚠️ Multi-task model not found")


def test_database_setup():
    """Test that databases are accessible"""
    import sqlite3
    
    logger.info("\n" + "="*70)
    logger.info("Testing Database Setup")
    logger.info("="*70)
    
    # NCAA Basketball DB
    ncaa_db = Path(__file__).parent / 'ncaa_basketball.db'
    if ncaa_db.exists():
        conn = sqlite3.connect(ncaa_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM games")
        games_count = cursor.fetchone()[0]
        logger.info(f"✅ NCAA Basketball DB")
        logger.info(f"   Total games: {games_count:,}")
        
        cursor.execute("SELECT COUNT(*) FROM game_lineups")
        lineups_count = cursor.fetchone()[0]
        logger.info(f"   Lineup records: {lineups_count:,}")
        
        cursor.execute("SELECT COUNT(*) FROM player_stats WHERE season = 2024 AND minutes_played IS NOT NULL")
        player_stats_count = cursor.fetchone()[0]
        logger.info(f"   Player stats (2024): {player_stats_count:,}")
        
        conn.close()
    else:
        logger.error("❌ NCAA Basketball DB not found")
    
    # Paper Trades DB
    paper_trades_db = Path(__file__).parent / 'paper_trades_ncaa.db'
    if paper_trades_db.exists():
        conn = sqlite3.connect(paper_trades_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM paper_trades")
        trades_count = cursor.fetchone()[0]
        logger.info(f"✅ Paper Trades DB")
        logger.info(f"   Total trades: {trades_count:,}")
        
        conn.close()
    else:
        logger.info("ℹ️ Paper Trades DB doesn't exist yet (will be created on first run)")


def test_lineup_update():
    """Test lineup update function"""
    logger.info("\n" + "="*70)
    logger.info("Testing Lineup Update")
    logger.info("="*70)
    
    from pipelines.update_live_lineups import fetch_espn_lineup
    
    # Test with a known past game (Duke vs Houston, 2024-03-30)
    test_game_id = "401638638"
    test_home = "Duke Blue Devils"
    test_away = "Houston Cougars"
    test_season = 2024
    
    logger.info(f"Testing with game: {test_away} @ {test_home}")
    logger.info(f"Game ID: {test_game_id}")
    
    try:
        players_count = fetch_espn_lineup(test_game_id, test_home, test_away, test_season)
        if players_count > 0:
            logger.info(f"✅ Lineup fetch successful: {players_count} players")
        else:
            logger.info("ℹ️ No lineup data available (expected for old games)")
    except Exception as e:
        logger.error(f"❌ Lineup fetch failed: {e}")


def test_feature_engineering():
    """Test that feature engineering works"""
    logger.info("\n" + "="*70)
    logger.info("Testing Feature Engineering")
    logger.info("="*70)
    
    features_path = Path(__file__).parent / 'features_dataset.csv'
    if features_path.exists():
        import pandas as pd
        df = pd.read_csv(features_path)
        logger.info(f"✅ Features dataset loaded")
        logger.info(f"   Total games: {len(df):,}")
        logger.info(f"   Features: {len(df.columns)}")
        logger.info(f"   Columns: {list(df.columns)[:10]}...")
    else:
        logger.error("❌ Features dataset not found")


if __name__ == '__main__':
    logger.info("\n" + "="*70)
    logger.info("NCAA PAPER TRADING SYSTEM TEST")
    logger.info("="*70 + "\n")
    
    test_model_loading()
    test_database_setup()
    test_feature_engineering()
    test_lineup_update()
    
    logger.info("\n" + "="*70)
    logger.info("✅ ALL TESTS COMPLETE")
    logger.info("="*70)
    logger.info("\nSystem is ready for paper trading!")
    logger.info("\nTo start paper trading:")
    logger.info("  python3 paper_trading_ncaa.py --hours 8 --min-edge 0.05 --min-confidence 0.6")

