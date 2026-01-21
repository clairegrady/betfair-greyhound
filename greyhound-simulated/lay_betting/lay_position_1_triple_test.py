"""
TRIPLE BET TEST - Greyhound Lay Betting - Position 1
Tests placing 3 bets at different times:
- Bet 1: T-30s (30 seconds before race)
- Bet 2: T-5s (5 seconds before race)  
- Bet 3: T+5s (5 seconds after race starts - IN-PLAY!)

This version PRINTS bets instead of storing them in DB for testing
"""

import sys
sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/utilities')

import pandas as pd
import requests
import time
import pytz
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from db_connection_helper import get_db_connection

# Configuration
POSITION_TO_LAY = 1  # Laying the FAVORITE
MAX_ODDS = 6
FLAT_STAKE = 10

# BET TIMING WINDOWS
BET1_SECONDS = 30  # First bet 30s before
BET2_SECONDS = 5   # Second bet 5s before
BET3_SECONDS = -5  # Third bet 5s AFTER race start (in-play)

BACKEND_URL = "http://localhost:5173"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/Users/clairegrady/RiderProjects/betfair/greyhound-simulated/logs/triple_bet_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TripleBetTest:
    """Test triple bet placement"""
    
    def __init__(self):
        # Track which bets have been placed for each market
        # {market_id: {'bet1': False, 'bet2': False, 'bet3': False}}
        self.market_bets = {}
        self.session = requests.Session()
        self.session.timeout = 10
    
    def get_upcoming_races(self) -> List[Dict]:
        """Get greyhound races for any timing window"""
        try:
            conn = get_db_connection('betfair_races')
            query = """
                SELECT venue, race_number, race_time, race_date, country, timezone
                FROM greyhound_race_times
                WHERE race_date::date >= CURRENT_DATE
                AND race_date::date <= CURRENT_DATE + INTERVAL '1 day'
                ORDER BY race_date, race_time
            """
            df = pd.read_sql(query, conn)
            conn.close()
            
            if not self.logged_initial:
                logger.info(f"📊 Found {len(df)} total races in database")
                self.logged_initial = True
                
            if df.empty:
                return []
            
            aest_tz = pytz.timezone('Australia/Sydney')
            now_aest = datetime.now(aest_tz)
            
            upcoming_races = []
            for _, row in df.iterrows():
                race_tz_name = row.get('timezone', 'Australia/Sydney')
                race_tz = pytz.timezone(race_tz_name)
                
                race_datetime_str = f"{row['race_date']} {row['race_time']}"
                race_datetime_local = race_tz.localize(datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M'))
                race_datetime = race_datetime_local.astimezone(aest_tz)
                
                seconds_until = (race_datetime - now_aest).total_seconds()
                
                # Check if this race is in ANY betting window
                # Bet 1: 25-35s before (5s window around T-30s)
                # Bet 2: 0-10s before (5s window around T-5s)
                # Bet 3: -10s to 0s (5s window around T+5s)
                in_bet1_window = 25 <= seconds_until <= 35
                in_bet2_window = 0 <= seconds_until <= 10
                in_bet3_window = -10 <= seconds_until <= 0
                
                if in_bet1_window or in_bet2_window or in_bet3_window:
                    market_id = self.find_market_id(row['venue'], row['race_number'])
                    if market_id:
                        upcoming_races.append({
                            'venue': row['venue'],
                            'country': row.get('country', 'AUS'),
                            'race_number': row['race_number'],
                            'market_id': market_id,
                            'seconds_until': seconds_until,
                            'race_datetime': race_datetime,
                            'in_bet1_window': in_bet1_window,
                            'in_bet2_window': in_bet2_window,
                            'in_bet3_window': in_bet3_window
                        })
            
            return upcoming_races
            
        except Exception as e:
            logger.error(f"Error getting upcoming races: {e}")
            return []
    
    def find_market_id(self, venue: str, race_number: int) -> Optional[str]:
        """Find Win market ID for this race"""
        try:
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            today_str = datetime.now(pytz.timezone('Australia/Sydney')).strftime("%-d")
            
            query = """
                SELECT marketid
                FROM marketcatalogue
                WHERE eventname ILIKE %s
                AND marketname ILIKE %s
                AND eventtypename = 'Greyhound Racing'
                LIMIT 1
            """
            
            race_pattern = f'R{race_number} %'
            venue_pattern = f'%{venue}%{today_str}%'
            
            cursor.execute(query, (venue_pattern, race_pattern))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error finding market: {e}")
            return None
    
    def get_odds_and_runners(self, market_id: str) -> Optional[Dict]:
        """Get current LAY odds"""
        try:
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            # Add timestamp to see when we're querying
            from datetime import datetime
            logger.debug(f"📥 Querying DB for market {market_id} at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            
            query = """
                SELECT DISTINCT selectionid, price, runnername, box
                FROM greyhoundmarketbook
                WHERE marketid = %s
                AND pricetype = 'AvailableToLay'
                AND price IS NOT NULL
                AND price > 0
                ORDER BY selectionid, price ASC
            """
            
            cursor.execute(query, (market_id,))
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return None
            
            # Group by selectionid, take best lay price
            import re
            runners_dict = {}
            for sel_id, price, runner_name, box in results:
                if sel_id not in runners_dict:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name) if runner_name else f'Dog {sel_id}'
                    runners_dict[sel_id] = {
                        'selection_id': sel_id,
                        'odds': price,
                        'dog_name': clean_name,
                        'box': box
                    }
            
            return {'runners': list(runners_dict.values())} if runners_dict else None
            
        except Exception as e:
            logger.error(f"Error getting odds: {e}")
            return None
    
    def print_bet(self, race_info: Dict, dog: Dict, bet_number: int, seconds_until: float):
        """Print bet details instead of storing"""
        liability = FLAT_STAKE * (dog['odds'] - 1)
        
        bet_timing = f"T{'+' if seconds_until < 0 else '-'}{abs(int(seconds_until))}s"
        box_info = f" [Box {dog.get('box')}]" if dog.get('box') else ""
        
        print(f"\n{'='*80}")
        print(f"🎯 BET #{bet_number} - {bet_timing}")
        print(f"{'='*80}")
        print(f"Race:      {race_info['venue']} R{race_info['race_number']}")
        print(f"Dog:       {dog['dog_name']}{box_info} (ID: {dog['selection_id']})")
        print(f"Position:  {POSITION_TO_LAY} (Favourite)")
        print(f"Lay Odds:  {dog['odds']}")
        print(f"Stake:     ${FLAT_STAKE}")
        print(f"Liability: ${liability:.2f}")
        print(f"Timing:    {seconds_until:.1f}s until race")
        if bet_number == 3:
            print(f"⚠️  IN-PLAY BET!")
        print(f"{'='*80}\n")
        
        logger.info(f"✅ Bet #{bet_number} @ {bet_timing}: {dog['dog_name']}{box_info} @ {dog['odds']} - Liability ${liability:.2f}")
    
    def process_race(self, race_info: Dict):
        """Process a race and place appropriate bet(s)"""
        market_id = race_info['market_id']
        
        # Initialize bet tracking for this market
        if market_id not in self.market_bets:
            self.market_bets[market_id] = {'bet1': False, 'bet2': False, 'bet3': False}
        
        # Determine which bet to place
        bet_to_place = None
        if race_info['in_bet1_window'] and not self.market_bets[market_id]['bet1']:
            bet_to_place = 1
        elif race_info['in_bet2_window'] and not self.market_bets[market_id]['bet2']:
            bet_to_place = 2
        elif race_info['in_bet3_window'] and not self.market_bets[market_id]['bet3']:
            bet_to_place = 3
        
        if not bet_to_place:
            return  # Already placed this bet
        
        logger.info(f"🔍 Fetching FRESH odds for Bet #{bet_to_place} at T{'+' if race_info['seconds_until'] < 0 else '-'}{abs(int(race_info['seconds_until']))}s...")
        
        # Get odds
        odds_data = self.get_odds_and_runners(market_id)
        if not odds_data:
            logger.warning(f"❌ No odds available for {race_info['venue']} R{race_info['race_number']}")
            return
        
        runners = odds_data['runners']
        if len(runners) < POSITION_TO_LAY:
            logger.warning(f"❌ Not enough runners (need {POSITION_TO_LAY}, have {len(runners)})")
            return
        
        # Sort by odds to get favourite
        sorted_runners = sorted(runners, key=lambda x: (x['odds'], x['selection_id']))
        target_dog = sorted_runners[POSITION_TO_LAY - 1]
        
        logger.info(f"📊 Current favourite: {target_dog['dog_name']} @ {target_dog['odds']}")
        
        # Check odds validity
        if target_dog['odds'] <= 0:
            logger.error(f"❌ Invalid odds {target_dog['odds']}")
            return
        
        if target_dog['odds'] > MAX_ODDS:
            logger.info(f"⏭️  Odds {target_dog['odds']} > {MAX_ODDS} - skipping")
            return
        
        # PRINT the bet (instead of storing)
        self.print_bet(race_info, target_dog, bet_to_place, race_info['seconds_until'])
        
        # Mark bet as placed
        self.market_bets[market_id][f'bet{bet_to_place}'] = True
    
    def run(self):
        self.logged_initial = False
        logger.info("=" * 80)
        logger.info(f"🐕 TRIPLE BET TEST - Position {POSITION_TO_LAY}")
        logger.info("=" * 80)
        logger.info(f"   Bet 1: T-{BET1_SECONDS}s (30 seconds before)")
        logger.info(f"   Bet 2: T-{BET2_SECONDS}s (5 seconds before)")
        logger.info(f"   Bet 3: T+{abs(BET3_SECONDS)}s (5 seconds after - IN-PLAY!)")
        logger.info(f"   Max odds: {MAX_ODDS}")
        logger.info(f"   Stake: ${FLAT_STAKE}/bet")
        logger.info(f"\n⏰ Monitoring races...\n")
        
        try:
            while True:
                upcoming = self.get_upcoming_races()
                
                for race in upcoming:
                    self.process_race(race)
                
                time.sleep(2)  # Check every 2 seconds for tighter timing
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Test stopped")
            total_bets = sum(
                sum(1 for bet in bets.values() if bet)
                for bets in self.market_bets.values()
            )
            logger.info(f"   Total bets placed: {total_bets}")
            logger.info(f"   Markets processed: {len(self.market_bets)}")


if __name__ == "__main__":
    test = TripleBetTest()
    test.run()
