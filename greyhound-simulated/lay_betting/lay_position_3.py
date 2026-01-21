"""
Greyhound Lay Betting - Position 1 (Favorite)
Lays the FAVORITE in every greyhound race (odds ≤ 500)
Bets placed 5 seconds before race start
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
POSITION_TO_LAY = 3  # Laying the FAVORITE
MAX_ODDS = 500
SECONDS_BEFORE_RACE = 5
FLAT_STAKE = 10


RACE_TIMES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db"
BACKEND_URL = "http://localhost:5173"

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for troubleshooting
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/Users/clairegrady/RiderProjects/betfair/greyhound-simulated/logs/lay_position_{POSITION_TO_LAY}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GreyhoundLayBetting:
    """Lay betting on specific market position"""
    
    def __init__(self):
        self.processed_markets = set()
        self.session = requests.Session()
        self.session.timeout = 10
    
    @staticmethod
    def parse_event_name(event_name: str) -> Dict:
        """Parse venue and date from EventName field
        Example: 'Murray Bridge Straight (AUS) 13th Jan' -> {'venue': 'Murray Bridge Straight', 'country': 'AUS', 'date': '13th Jan'}
        """
        import re
        match = re.match(r'^(.+?)\s+\(([A-Z]+)\)\s+(.+)$', event_name)
        if match:
            return {
                'venue': match.group(1),
                'country': match.group(2),
                'date': match.group(3)
            }
        return {'venue': event_name, 'country': 'Unknown', 'date': 'Unknown'}
        
    def get_upcoming_races(self) -> List[Dict]:
        """Get greyhound races within betting window"""
        try:
            # Get races from database (include today and tomorrow for cross-midnight races)
            conn = get_db_connection("/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db")
            query = """
                SELECT venue, race_number, race_time, race_date, country
                FROM greyhound_race_times
                WHERE race_date::date >= CURRENT_DATE
                AND race_date::date <= CURRENT_DATE + INTERVAL '1 day'
                ORDER BY race_date, race_time
            """
            df = pd.read_sql(query, conn)
            conn.close()
            
            # Log total races once at startup
            if not self.logged_initial_races:
                logger.info(f"📊 Found {len(df)} total races in database for today/tomorrow")
                self.logged_initial_races = True
            if df.empty:
                logger.debug("No races found in database for today")
                return []
            
            
            # Filter races within time window
            aest_tz = pytz.timezone('Australia/Sydney')
            now_aest = datetime.now(aest_tz)
            
            upcoming_races = []
            for _, row in df.iterrows():
                # Use the actual timezone from the database (e.g. Australia/Perth, Australia/Sydney)
                race_tz_name = row.get('timezone', 'Australia/Sydney')
                race_tz = pytz.timezone(race_tz_name)
                
                race_datetime_str = f"{row['race_date']} {row['race_time']}"
                # Localize in the race's actual timezone, then convert to AEST for comparison
                race_datetime_local = race_tz.localize(datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M'))
                race_datetime = race_datetime_local.astimezone(aest_tz)
                
                seconds_until = (race_datetime - now_aest).total_seconds()
                
                # Only bet if within time window
                if -5 <= seconds_until <= SECONDS_BEFORE_RACE:
                    # Match to market in Betfair DB
                    market_id = self.find_market_id(row['venue'], row['race_number'])
                    if market_id:
                        upcoming_races.append({
                            'venue': row['venue'],
                            'country': row.get('country', 'AUS'),
                            'race_number': row['race_number'],
                            'market_id': market_id,
                            'seconds_until': seconds_until,
                            'race_datetime': race_datetime
                        })
                        logger.debug(f"Added {row['venue']} R{row['race_number']} ({seconds_until:.0f}s)")
                    else:
                        logger.debug(f"No market found for {row['venue']} R{row['race_number']}")
            
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
            
            # Match the specific race number (e.g. "R1 ", "R10 ")
            race_pattern = f'R{race_number} %'
            venue_pattern = f'%{venue}%{today_str}%'
            
            cursor.execute(query, (venue_pattern, race_pattern))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error finding market: {e}")
            return None
    
    def get_odds_from_db(self, market_id: str) -> Optional[Dict]:
        """Fallback: Get odds directly from GreyhoundMarketBook table"""
        try:
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            # FOR LAY BETTING: Get ONLY LAY odds for this market
            # NO FALLBACK TO BACK PRICES
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
                logger.warning(f"❌ No lay prices in DB for market {market_id}")
                return None
            
            # Group by selectionid and take best (lowest) lay price
            import re
            runners_dict = {}
            
            for sel_id, price, runner_name, box in results:
                if sel_id not in runners_dict:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name) if runner_name else f'Dog {sel_id}'
                    runners_dict[sel_id] = {
                        'selection_id': sel_id,
                        'odds': price,
                        'dog_name': clean_name,
                        'box': box if box else None
                    }
            
            odds_map = list(runners_dict.values())
            return {'runners': odds_map} if odds_map else None
            
        except Exception as e:
            logger.error(f"Error getting odds from DB: {e}")
            return None
    
    def get_odds_and_runners(self, market_id: str) -> Optional[Dict]:
        """Get current odds for all runners (tries API first, then DB fallback)"""
        try:
            url = f"{BACKEND_URL}/api/GreyhoundMarketBook/market/{market_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"API returned {response.status_code}, trying DB fallback")
                return self.get_odds_from_db(market_id)
            
            data = response.json()
            # The API returns 'odds' not 'runners'
            odds_data = data.get('odds', [])
            
            if not odds_data:
                logger.warning(f"❌ No odds data returned from API for market {market_id}")
                return self.get_odds_from_db(market_id)
            
            # Get runner names from database
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT selectionid, runnername, box
                FROM greyhoundmarketbook
                WHERE marketid = %s
            """, (market_id,))
            
            import re
            runner_names = {}
            box_numbers = {}
            for sel_id, runner_name, box in cursor.fetchall():
                if runner_name:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    runner_names[sel_id] = clean_name
                if box:
                    box_numbers[sel_id] = box
            conn.close()
            
            # Build odds map from the 'odds' array, grouping by selectionid
            # FOR LAY BETTING: Use the best (lowest) lay price available
            # NO FALLBACK TO BACK PRICES - if no lay prices, skip this market
            selection_lay_odds = {}
            
            for odd in odds_data:
                sel_id = odd.get('selectionid')
                price = odd.get('price')
                pricetype = odd.get('pricetype')
                
                if sel_id and price and price > 0 and pricetype == 'AvailableToLay':
                    # For lay betting, take the LOWEST lay price (best price to lay at)
                    if sel_id not in selection_lay_odds or price < selection_lay_odds[sel_id]:
                        selection_lay_odds[sel_id] = price
            
            # Only proceed if we have lay prices
            if not selection_lay_odds:
                logger.warning(f"❌ No lay prices available for market {market_id} - skipping")
                return None
            
            selection_odds = selection_lay_odds
            
            # Build final odds map
            odds_map = []
            for sel_id, odds in selection_odds.items():
                odds_map.append({
                    'selection_id': sel_id,
                    'odds': odds,
                    'dog_name': runner_names.get(sel_id, f'Dog {sel_id}'),
                    'box': box_numbers.get(sel_id)
                })
            
            return {'runners': odds_map}
            
        except Exception as e:
            logger.warning(f"API error: {e}, trying DB fallback")
            return self.get_odds_from_db(market_id)
    
    def place_lay_bet(self, race_info: Dict, dog: Dict, position: int):
        """Record a lay bet"""
        try:
            # Get total matched from MarketCatalogue
            total_matched = None
            try:
                betfair_conn = get_db_connection('betfairmarket')
                betfair_cursor = betfair_conn.cursor()
                betfair_cursor.execute("""
                    SELECT totalmatched FROM marketcatalogue WHERE marketid = %s
                """, (race_info['market_id'],))
                result = betfair_cursor.fetchone()
                if result:
                    total_matched = result[0]
                betfair_conn.close()
            except Exception as e:
                logger.debug(f"Could not fetch TotalMatched: {e}")
            
            conn = get_db_connection('betfair_trades')
            cursor = conn.cursor()
            
            liability = FLAT_STAKE * (dog['odds'] - 1)
            
            cursor.execute("""
                INSERT INTO paper_trades_greyhounds
                (date, venue, country, race_number, market_id, selection_id, dog_name, box_number,
                 position_in_market, odds, stake, liability, finishing_position, result, total_matched, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                race_info['venue'],
                race_info['country'],
                race_info['race_number'],
                race_info['market_id'],
                dog['selection_id'],
                dog['dog_name'],
                dog.get('box'),  # Get box number from dog data
                position,
                dog['odds'],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending',
                total_matched,
                datetime.now()  # created_at timestamp
            ))
            
            conn.commit()
            conn.close()
            
            box_info = f" [Box {dog.get('box')}]" if dog.get('box') else ""
            logger.info(f"✅ LAY BET: {dog['dog_name']}{box_info} (ID: {dog['selection_id']}) @ {dog['odds']} (Position {position}) - Liability: ${liability:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            return False
    
    def process_race(self, race_info: Dict):
        """Process a single race"""
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"🎯 {race_info['venue']} ({race_info['country']}) - Race {race_info['race_number']}")
            logger.info(f"   {race_info['seconds_until']:.1f}s until race")
            logger.info(f"{'='*70}")
            
            # Get odds
            odds_data = self.get_odds_and_runners(race_info['market_id'])
            if not odds_data:
                logger.warning("❌ Could not get odds")
                return
            
            runners = odds_data['runners']
            if len(runners) < POSITION_TO_LAY:
                logger.warning(f"❌ Not enough runners (need {POSITION_TO_LAY}, have {len(runners)})")
                return
            
            
            # Sort by odds (ascending) to get favorites
            # Use selection_id as tie-breaker when odds are equal (lower ID = earlier favorite)
            sorted_runners = sorted(runners, key=lambda x: (x['odds'], x['selection_id']))
            
            # Get the dog at our position
            target_dog = sorted_runners[POSITION_TO_LAY - 1]
            
            # Check for zero or invalid odds - DO NOT BET!

            
            if target_dog['odds'] <= 0:

            
                logger.error(f"❌ SKIPPING - Invalid odds {target_dog['odds']} for {target_dog.get('dog_name', target_dog.get('horse_name', 'Unknown'))} (Position {POSITION_TO_LAY})")

            
                return

            
            

            
            # Check max odds
            if target_dog['odds'] > MAX_ODDS:
                logger.info(f"⏭️  Skipping - odds {target_dog['odds']} > {MAX_ODDS}")
                return
            
            # Place lay bet
            self.place_lay_bet(race_info, target_dog, POSITION_TO_LAY)
            
        except Exception as e:
            logger.error(f"Error processing race: {e}")
    
    def run(self):
        self.logged_initial_races = False
        self.last_next_race_info = None  # Track last logged race info
        """Main monitoring loop"""
        logger.info("=" * 70)
        logger.info(f"🐕 GREYHOUND LAY BETTING - POSITION {POSITION_TO_LAY}")
        logger.info("=" * 70)
        logger.info(f"   Max odds: {MAX_ODDS}")
        logger.info(f"   Stake: ${FLAT_STAKE}")
        logger.info(f"   Betting window: {SECONDS_BEFORE_RACE} seconds before race")
        logger.info("\n⏰ Monitoring races...\n")
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                upcoming = self.get_upcoming_races()
                
                # Show next race info every 5 seconds (but only if it changes)
                if upcoming:
                    next_race = upcoming[0]
                    
                    # Calculate time until race (use the race_datetime that's already in the dict)
                    now = datetime.now(pytz.timezone('Australia/Sydney'))
                    race_datetime = next_race['race_datetime']
                    time_until = race_datetime - now
                    
                    minutes = int(time_until.total_seconds() // 60)
                    seconds = int(time_until.total_seconds() % 60)
                    
                    current_info = f"{next_race['venue']} R{next_race['race_number']} - {minutes}m {seconds}s"
                    
                    # Only log if the info changed
                    if current_info != self.last_next_race_info:
                        logger.info(f"⏱️  Next race: {current_info}")
                        self.last_next_race_info = current_info
                
                # Group races by venue to ensure we only bet on the next race at each venue
                venue_races = {}
                for race in upcoming:
                    venue = race['venue']
                    if venue not in venue_races:
                        venue_races[venue] = []
                    venue_races[venue].append(race)
                
                # For each venue, only process the race with the lowest race number
                for venue, races in venue_races.items():
                    # Sort by race number to get the earliest race
                    races_sorted = sorted(races, key=lambda x: x['race_number'])
                    next_race = races_sorted[0]
                    
                    market_id = next_race['market_id']
                    
                    if market_id in self.processed_markets:
                        continue
                    
                    self.processed_markets.add(market_id)
                    self.process_race(next_race)
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Stopped")
            logger.info(f"   Processed {len(self.processed_markets)} races")


if __name__ == "__main__":
    betting = GreyhoundLayBetting()
    betting.run()
