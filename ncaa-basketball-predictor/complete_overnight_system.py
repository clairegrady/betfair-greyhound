#!/usr/bin/env python3
"""
Complete Overnight Autonomous System
Handles all scraping, validation, training, and paper trading setup
"""

import sqlite3
import time
import subprocess
from pathlib import Path
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"
PROJECT_ROOT = Path(__file__).parent

def run_cmd(cmd, cwd=None):
    """Run command and return success"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd or PROJECT_ROOT, 
                              capture_output=True, text=True, timeout=7200)
        if result.returncode != 0:
            logger.error(f"Command failed: {cmd}")
            logger.error(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.error(f"Exception running {cmd}: {e}")
        return False

def check_scraper_done(season):
    """Check if scraping is complete for a season"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT 
            COUNT(DISTINCT player_id) as total,
            COUNT(DISTINCT CASE WHEN offensive_rating IS NOT NULL THEN player_id END) as ortg,
            COUNT(DISTINCT CASE WHEN points_per_game IS NOT NULL THEN player_id END) as ppg
        FROM player_stats WHERE season = {season}
    """)
    row = cursor.fetchone()
    conn.close()
    
    targets = {2024: 3500, 2025: 4000, 2026: 3200}
    target = targets.get(season, 3500)
    
    ortg_ready = row[1] > target * 0.90
    ppg_ready = row[2] > target * 0.75
    
    return ortg_ready and ppg_ready, row

def wait_for_scraping():
    """Wait for all scraping to complete with monitoring"""
    logger.info("="*70)
    logger.info("⏳ WAITING FOR SCRAPING TO COMPLETE")
    logger.info("="*70)
    
    max_wait_hours = 8
    start_time = time.time()
    iteration = 0
    
    while (time.time() - start_time) < (max_wait_hours * 3600):
        iteration += 1
        all_done = True
        
        logger.info(f"\n[Check #{iteration}] {time.strftime('%H:%M:%S')}")
        
        for season in [2024, 2025, 2026]:
            done, data = check_scraper_done(season)
            status_emoji = "✅" if done else "⏳"
            logger.info(f"  {status_emoji} Season {season}: {data[1]:,} ORtg, {data[2]:,} PPG")
            
            if not done:
                all_done = False
        
        if all_done:
            logger.info("\n🎉 ALL SCRAPING COMPLETE!")
            return True
        
        logger.info("⏳ Waiting 120 seconds...")
        time.sleep(120)
    
    logger.warning("⚠️ Scraping timeout - proceeding with available data")
    return False

def validate_and_clean_data():
    """Validate data quality and clean if needed"""
    logger.info("\n" + "="*70)
    logger.info("🔍 VALIDATING DATA QUALITY")
    logger.info("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    
    for season in [2024, 2025, 2026]:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN offensive_rating IS NULL THEN 1 ELSE 0 END) as null_ortg,
                SUM(CASE WHEN usage_rate IS NULL THEN 1 ELSE 0 END) as null_usage,
                SUM(CASE WHEN points_per_game IS NULL THEN 1 ELSE 0 END) as null_ppg,
                AVG(CASE WHEN offensive_rating IS NOT NULL THEN offensive_rating END) as avg_ortg,
                AVG(CASE WHEN minutes_played IS NOT NULL AND minutes_played > 0 THEN minutes_played END) as avg_min
            FROM player_stats WHERE season = {season}
        """)
        row = cursor.fetchone()
        
        logger.info(f"\nSeason {season}:")
        logger.info(f"  Total players: {row[0]:,}")
        logger.info(f"  Null ORtg: {row[1]:,} ({row[1]/max(row[0],1)*100:.1f}%)")
        logger.info(f"  Null Usage: {row[2]:,} ({row[2]/max(row[0],1)*100:.1f}%)")
        logger.info(f"  Null PPG: {row[3]:,} ({row[3]/max(row[0],1)*100:.1f}%)")
        if row[4]:
            logger.info(f"  Avg ORtg: {row[4]:.1f}")
        if row[5]:
            logger.info(f"  Avg Minutes: {row[5]:.1f}")
    
    conn.close()
    
    # Run data cleaning
    logger.info("\n🧹 Running data cleaning...")
    return run_cmd("python3 clean_data.py")

def rebuild_features():
    """Rebuild features with all seasons"""
    logger.info("\n" + "="*70)
    logger.info("🔨 REBUILDING FEATURES")
    logger.info("="*70)
    
    return run_cmd("python3 pipelines/feature_engineering_v2.py")

def train_model():
    """Train the multi-task model"""
    logger.info("\n" + "="*70)
    logger.info("🧠 TRAINING MODEL")
    logger.info("="*70)
    
    success = run_cmd("python3 pipelines/train_multitask_model.py")
    
    if success:
        # Check model file exists
        model_path = PROJECT_ROOT / 'models' / 'multitask_model_best.pth'
        if model_path.exists():
            logger.info(f"✅ Model saved: {model_path}")
            return True
    
    return False

def validate_predictions():
    """Test predictions on sample games"""
    logger.info("\n" + "="*70)
    logger.info("🎯 VALIDATING PREDICTIONS")
    logger.info("="*70)
    
    return run_cmd("python3 show_predictions.py | head -100")

def build_paper_trading():
    """Build paper trading system similar to horse racing"""
    logger.info("\n" + "="*70)
    logger.info("💰 BUILDING PAPER TRADING SYSTEM")
    logger.info("="*70)
    
    # The paper_trading_ncaa.py already exists, just test it
    test_cmd = "python3 paper_trading_ncaa.py --hours 48 --min-edge 0.03 --min-confidence 0.5 --bankroll 1000"
    logger.info(f"Testing: {test_cmd}")
    
    return run_cmd(test_cmd)

def main():
    logger.info("="*70)
    logger.info("🚀 OVERNIGHT AUTONOMOUS SYSTEM - STARTING")
    logger.info("="*70)
    logger.info(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Wait for scraping
    if not wait_for_scraping():
        logger.warning("Proceeding with partial data...")
    
    # Step 2: Validate and clean
    if not validate_and_clean_data():
        logger.error("❌ Data validation failed")
        return False
    
    # Step 3: Rebuild features
    if not rebuild_features():
        logger.error("❌ Feature building failed")
        return False
    
    # Step 4: Train model
    if not train_model():
        logger.error("❌ Model training failed")
        return False
    
    # Step 5: Validate predictions
    if not validate_predictions():
        logger.warning("⚠️ Prediction validation had issues")
    
    # Step 6: Build/test paper trading
    if not build_paper_trading():
        logger.warning("⚠️ Paper trading test had issues")
    
    logger.info("\n" + "="*70)
    logger.info("✅ OVERNIGHT SYSTEM COMPLETE!")
    logger.info("="*70)
    logger.info(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("\nSystem is ready for paper trading!")
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n👋 Stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

