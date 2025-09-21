#!/usr/bin/env python3
"""
Automated Lay Betting System with Variable Strategy
Continuously monitors for races and places lay bets using variable max odds and std thresholds
"""

import time
import logging
from datetime import datetime
from lay_betting_automation_variable import LayBettingAutomationVariable

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lay_betting_automation_variable.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main automation loop with variable strategy"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    api_base_url = "http://localhost:5173"
    
    # Create automation instance with variable strategy
    # These are BASE values for 12-horse fields - will scale automatically
    automation = LayBettingAutomationVariable(
        db_path=db_path,
        api_base_url=api_base_url,
        base_std_threshold=1.0,  # Base std threshold for 12-horse field
        base_max_odds=20.0,      # Base max odds for 12-horse field
        min_minutes_before_race=0  # Allow betting right up to race start
    )
    
    logger.info("=== AUTOMATED LAY BETTING (VARIABLE STRATEGY) STARTED ===")
    logger.info(f"Strategy: {automation.strategy.get_strategy_description()}")
    logger.info("Variable scaling: 6 horses = 50% of base, 12 horses = 100%, 18 horses = 150%")
    logger.info("Monitoring for races within 4 minutes of start")
    logger.info("Backend update frequency: 10 seconds")
    logger.info("🔍 DRY RUN MODE - No actual bets will be placed")
    
    cycle_count = 0
    
    # Continuous monitoring loop
    while True:
        try:
            cycle_count += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            
            logger.info(f"--- CYCLE {cycle_count} at {current_time} ---")
            
            # Check for races and place bets
            result = automation.scan_and_bet(
                max_minutes_ahead=3000,  # Monitor races within 300 minutes (5 hours) to include Ayr races
                stake_per_bet=1.0,
                dry_run=True  
            )
            
            # Check status of pending bets
            automation.check_all_pending_bets()
            
            # Pre-race odds check for races starting soon
            automation.pre_race_odds_check_for_imminent_races()
            
            if result.get('status') == 'success':
                logger.info(f"Found {result.get('opportunities', 0)} opportunities with {result.get('total_bets', 0)} total bets")
                logger.info(f"Total liability: ${result.get('total_liability', 0):.2f}")
            elif result.get('status') == 'no_opportunities':
                logger.info("No betting opportunities found with current criteria")
            elif result.get('status') == 'all_bets_already_placed':
                logger.info("All opportunities already bet on - no new bets to place")
            
            logger.info(f"Cycle {cycle_count} completed. Waiting 10 seconds...")
            time.sleep(10)  # Wait 10 seconds (matches original system)
            
        except KeyboardInterrupt:
            logger.info("Automation stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in cycle {cycle_count}: {e}")
            logger.info("Waiting 10 seconds before retry...")
            time.sleep(10)  # Shorter wait on error

if __name__ == "__main__":
    main()
