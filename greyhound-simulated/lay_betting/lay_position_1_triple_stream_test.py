"""
TRIPLE BET TEST WITH DIRECT STREAM API
Uses direct Betfair Stream API connection for real-time odds
NO database lag - updates in ~50-100ms
"""

import sys
sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/utilities')

import pandas as pd
import time
import pytz
from datetime import datetime
import logging
from typing import Dict, List, Optional
from db_connection_helper import get_db_connection
from betfair_stream_client import BetfairStreamClient

# Configuration
POSITION_TO_LAY = 1
MAX_ODDS = 6
FLAT_STAKE = 10

BET1_SECONDS = 30
BET2_SECONDS = 5
BET3_SECONDS = -5

# Betfair credentials (from backend config)
APP_KEY = "tjBWsmDXH5zwhfjj"  # From your backend appsettings.json
# You'll need to provide session token

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/Users/clairegrady/RiderProjects/betfair/greyhound-simulated/logs/triple_bet_stream_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TripleBetStreamTest:
    """Test triple bet with direct Stream API"""
    
    def __init__(self, session_token: str):
        self.market_bets = {}
        self.logged_initial = False
        
        # Initialize Stream API client
        self.stream_client = BetfairStreamClient(APP_KEY, session_token)
        
        # Connect and authenticate
        logger.info("🔌 Connecting to Betfair Stream API...")
        if not self.stream_client.connect():
            raise Exception("Failed to connect to Stream API")
        
        if not self.stream_client.authenticate():
            raise Exception("Failed to authenticate")
        
        # Start listening for updates
        self.stream_client.start_listening()
        logger.info("✅ Stream API ready - listening for updates")
    
    def get_upcoming_races(self) -> List[Dict]:
        """Get races from database (schedule only)"""
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
                logger.info(f"📊 Found {len(df)} total races")
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
                
                in_bet1_window = 25 <= seconds_until <= 35
                in_bet2_window = 0 <= seconds_until <= 10
                in_bet3_window = -10 <= seconds_until <= 0
                
                if in_bet1_window or in_bet2_window or in_bet3_window:
                    market_id = self.find_market_id(row['venue'], row['race_number'])
                    if market_id:
                        # Subscribe to this market via Stream API
                        self.stream_client.subscribe_to_market(market_id)
                        
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
            logger.error(f"Error getting races: {e}")
            return []
    
    def find_market_id(self, venue: str, race_number: int) -> Optional[str]:
        """Find market ID from database"""
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
    
    def get_odds_from_stream(self, market_id: str) -> Optional[Dict]:
        """Get REAL-TIME odds from Stream API (in-memory cache)"""
        return self.stream_client.get_market_odds(market_id)
    
    def print_bet(self, race_info: Dict, dog: Dict, bet_number: int, seconds_until: float):
        """Print bet details"""
        liability = FLAT_STAKE * (dog['odds'] - 1)
        
        bet_timing = f"T{'+' if seconds_until < 0 else '-'}{abs(int(seconds_until))}s"
        box_info = f" [Box {dog.get('box')}]" if dog.get('box') else ""
        
        # Show timestamp of odds data
        odds_age = (datetime.now() - dog.get('timestamp', datetime.now())).total_seconds()
        
        print(f"\n{'='*80}")
        print(f"🎯 BET #{bet_number} - {bet_timing} ⚡ DIRECT STREAM")
        print(f"{'='*80}")
        print(f"Race:      {race_info['venue']} R{race_info['race_number']}")
        print(f"Dog:       {dog['dog_name']}{box_info} (ID: {dog['selection_id']})")
        print(f"Position:  {POSITION_TO_LAY} (Favourite)")
        print(f"Lay Odds:  {dog['odds']}")
        print(f"Odds Age:  {odds_age:.2f}s old (Stream API)")
        print(f"Stake:     ${FLAT_STAKE}")
        print(f"Liability: ${liability:.2f}")
        print(f"Timing:    {seconds_until:.1f}s until race")
        if bet_number == 3:
            print(f"⚠️  IN-PLAY BET!")
        print(f"{'='*80}\n")
        
        logger.info(f"✅ Bet #{bet_number} @ {bet_timing}: {dog['dog_name']}{box_info} @ {dog['odds']} (odds {odds_age:.2f}s old)")
    
    def process_race(self, race_info: Dict):
        """Process a race"""
        market_id = race_info['market_id']
        
        if market_id not in self.market_bets:
            self.market_bets[market_id] = {'bet1': False, 'bet2': False, 'bet3': False}
        
        bet_to_place = None
        if race_info['in_bet1_window'] and not self.market_bets[market_id]['bet1']:
            bet_to_place = 1
        elif race_info['in_bet2_window'] and not self.market_bets[market_id]['bet2']:
            bet_to_place = 2
        elif race_info['in_bet3_window'] and not self.market_bets[market_id]['bet3']:
            bet_to_place = 3
        
        if not bet_to_place:
            return
        
        logger.info(f"🔍 Getting REAL-TIME odds from Stream API for Bet #{bet_to_place}...")
        
        # Get odds from STREAM API (real-time, no DB lag)
        odds_data = self.get_odds_from_stream(market_id)
        if not odds_data:
            logger.warning(f"❌ No Stream API data yet for {race_info['venue']} R{race_info['race_number']}")
            return
        
        runners = odds_data['runners']
        if len(runners) < POSITION_TO_LAY:
            logger.warning(f"❌ Not enough runners")
            return
        
        sorted_runners = sorted(runners, key=lambda x: (x['odds'], x['selection_id']))
        target_dog = sorted_runners[POSITION_TO_LAY - 1]
        
        logger.info(f"📊 Stream API favourite: {target_dog['dog_name']} @ {target_dog['odds']}")
        
        if target_dog['odds'] <= 0 or target_dog['odds'] > MAX_ODDS:
            logger.info(f"⏭️  Odds {target_dog['odds']} invalid or > {MAX_ODDS}")
            return
        
        self.print_bet(race_info, target_dog, bet_to_place, race_info['seconds_until'])
        self.market_bets[market_id][f'bet{bet_to_place}'] = True
    
    def run(self):
        logger.info("=" * 80)
        logger.info(f"🐕 TRIPLE BET - DIRECT STREAM API TEST")
        logger.info("=" * 80)
        logger.info(f"   Bet 1: T-{BET1_SECONDS}s")
        logger.info(f"   Bet 2: T-{BET2_SECONDS}s")
        logger.info(f"   Bet 3: T+{abs(BET3_SECONDS)}s (IN-PLAY)")
        logger.info(f"   ⚡ Using DIRECT Stream API (no DB lag)")
        logger.info(f"\n⏰ Monitoring...\n")
        
        try:
            while True:
                upcoming = self.get_upcoming_races()
                
                for race in upcoming:
                    self.process_race(race)
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Stopped")
            self.stream_client.disconnect()


if __name__ == "__main__":
    # YOU NEED TO GET A SESSION TOKEN
    # Run this in terminal to get one:
    # curl -X POST "https://identitysso-cert.betfair.com/api/certlogin" \
    #   --cert /path/to/client-2048.crt --key /path/to/client-2048.key \
    #   -d "username=YOUR_USERNAME&password=YOUR_PASSWORD"
    
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 lay_position_1_triple_stream_test.py <session_token>")
        print("\nGet session token with:")
        print("curl -X POST 'https://identitysso-cert.betfair.com/api/certlogin' \\")
        print("  --cert /path/to/cert.crt --key /path/to/cert.key \\")
        print("  -d 'username=YOUR_USER&password=YOUR_PASS'")
        sys.exit(1)
    
    session_token = sys.argv[1]
    test = TripleBetStreamTest(session_token)
    test.run()
