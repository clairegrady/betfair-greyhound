#!/usr/bin/env python3
"""
Automated Lay Betting System
Continuously monitors for races within 10 minutes and places lay bets
"""

import time
import logging
from datetime import datetime
from lay_betting_automation import LayBettingAutomation

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lay_betting_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main automation loop"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    api_base_url = "http://localhost:5173"
    
    # Create automation instance
    automation = LayBettingAutomation(
        db_path=db_path,
        api_base_url=api_base_url,
        std_threshold=1.5,
        max_odds=20.0,
        min_minutes_before_race=-6  # Allow betting from 1 minute before to 2 minutes after
    )
    
    logger.info("=== AUTOMATED LAY BETTING STARTED ===")
    logger.info(f"Strategy: {automation.strategy.get_strategy_description()}")
    logger.info("Monitoring for races within 15 minutes of start")
    logger.info("Backend update frequency: 2 minutes")
    logger.info("🔍 DRY RUN MODE - No actual bets will be placed")
    
    cycle_count = 0
    
    # Continuous monitoring loop
    while True:
        try:
            cycle_count += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            
            logger.info(f"--- CYCLE {cycle_count} at {current_time} ---")
            
            # Check for races and place bets
            automation.scan_and_bet(
                max_minutes_ahead=300,  
                stake_per_bet=1.0,
                dry_run=True  
            )
            
            # Check status of pending bets
            automation.check_all_pending_bets()
            
            # Pre-race odds check for races starting soon
            automation.pre_race_odds_check_for_imminent_races()
            
            # Clean up old odds data (every 10 cycles to avoid overhead)
            if cycle_count % 10 == 0:
                automation.cleanup_old_odds()
            
            logger.info(f"Cycle {cycle_count} completed. Waiting 10 seconds...")
            time.sleep(10)  # Wait 30 seconds (matches backend)
            
        except KeyboardInterrupt:
            logger.info("Automation stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in cycle {cycle_count}: {e}")
            logger.info("Waiting 10 seconds before retry...")
            time.sleep(10)  # Shorter wait on error

if __name__ == "__main__":
    main()
