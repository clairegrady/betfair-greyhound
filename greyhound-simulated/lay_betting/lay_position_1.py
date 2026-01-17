"""
Greyhound Lay Betting - Position 1 (Favorite)
Lays the FAVORITE in every greyhound race (odds ≤ 500)
Bets placed 5 seconds before race start
"""

import sys
sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/utilities')

import pandas as pd
import sqlite3
import requests
import time
import pytz
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from db_connection_helper import get_db_connection

# Configuration
POSITION_TO_LAY = 1  # Laying the FAVORITE
MAX_ODDS = 500
SECONDS_BEFORE_RACE = 5
FLAT_STAKE = 10

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
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
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db", timeout=30)
            query = """
                SELECT venue, race_number, race_time, race_date, country
                FROM greyhound_race_times
                WHERE race_date >= date('now', 'localtime')
                AND race_date <= date('now', 'localtime', '+1 day')
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
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
            cursor = conn.cursor()
            
            today_str = datetime.now(pytz.timezone('Australia/Sydney')).strftime("%-d")
            
            query = """
                SELECT MarketId
                FROM MarketCatalogue
                WHERE EventName LIKE ?
                AND MarketName LIKE ?
                AND EventTypeName = 'Greyhound Racing'
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
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
            cursor = conn.cursor()
            
            # Get all back odds for this market - include box number
            query = """
                SELECT DISTINCT selectionid, price, RunnerName, box
                FROM GreyhoundMarketBook
                WHERE MarketId = ?
                AND priceType = 'AvailableToBack'
                AND price IS NOT NULL
                ORDER BY selectionid, price DESC
            """
            
            cursor.execute(query, (market_id,))
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return None
            
            # Group by selectionid and take best (highest) back price
            import re
            runners_dict = {}
            for sel_id, price, runner_name, box in results:
                if sel_id not in runners_dict:
                    # Clean trap number from name
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
            runners = data.get('runners', [])
            
            # GreyhoundMarketBook API now returns runner names and box numbers directly
            runner_names = {}
            box_numbers = {}
            for runner in runners:
                sel_id = runner.get('selectionId')
                if sel_id:
                    name = runner.get('runnerName', '')
                    box = runner.get('box')
                    if name and not name.startswith('Runner '):
                        runner_names[sel_id] = name
                    if box:
                        box_numbers[sel_id] = box
            
            # Fallback: Get names and box numbers from GreyhoundMarketBook table if needed
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT selectionid, RunnerName, box
                FROM GreyhoundMarketBook
                WHERE MarketId = ?
            """, (market_id,))
            
            import re
            box_numbers = {}
            for sel_id, runner_name, box in cursor.fetchall():
                if runner_name and sel_id not in runner_names:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    runner_names[sel_id] = clean_name
                if box:
                    box_numbers[sel_id] = box
            conn.close()
            
            # Build odds map
            odds_map = []
            for runner in runners:
                selection_id = runner.get('selectionId')
                ex = runner.get('ex', {})
                available_to_back = ex.get('availableToBack', [])
                
                if available_to_back and len(available_to_back) > 0:
                    odds = available_to_back[0].get('price')
                    if odds and selection_id:
                        odds_map.append({
                            'selection_id': selection_id,
                            'odds': odds,
                            'dog_name': runner_names.get(selection_id, f'Dog {selection_id}'),
                            'box': box_numbers.get(selection_id)
                        })
            
            return {'runners': odds_map} if odds_map else None
            
        except Exception as e:
            logger.warning(f"API error: {e}, trying DB fallback")
            return self.get_odds_from_db(market_id)
    
    def place_lay_bet(self, race_info: Dict, dog: Dict, position: int):
        """Record a lay bet"""
        try:
            # Get total matched from MarketCatalogue
            total_matched = None
            try:
                betfair_conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
                betfair_cursor = betfair_conn.cursor()
                betfair_cursor.execute("""
                    SELECT TotalMatched FROM MarketCatalogue WHERE MarketId = ?
                """, (race_info['market_id'],))
                result = betfair_cursor.fetchone()
                if result:
                    total_matched = result[0]
                betfair_conn.close()
            except Exception as e:
                logger.debug(f"Could not fetch TotalMatched: {e}")
            
            conn = get_db_connection(DB_PATH)
            cursor = conn.cursor()
            
            liability = FLAT_STAKE * (dog['odds'] - 1)
            
            cursor.execute("""
                INSERT INTO paper_trades
                (date, venue, country, race_number, market_id, selection_id, dog_name, box_number,
                 position_in_market, odds, stake, liability, finishing_position, result, total_matched)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                total_matched
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
                
                if loop_count % 360 == 1:  # Log every 30 minutes
                    logger.info(f"🔍 Checking... Found {len(upcoming)} races in betting window")
                
                for race in upcoming:
                    market_id = race['market_id']
                    
                    if market_id in self.processed_markets:
                        continue
                    
                    self.processed_markets.add(market_id)
                    self.process_race(race)
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Stopped")
            logger.info(f"   Processed {len(self.processed_markets)} races")


if __name__ == "__main__":
    betting = GreyhoundLayBetting()
    betting.run()
