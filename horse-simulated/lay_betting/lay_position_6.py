"""
Horse Racing Lay Betting - Position 1 (Favorite)
Lays the FAVORITE in every horse race (odds ≤ 500)
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
POSITION_TO_LAY = 6  # Laying the FAVORITE
MAX_ODDS = 500
SECONDS_BEFORE_RACE = 5
FLAT_STAKE = 10

BACKEND_URL = "http://localhost:5173"

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/Users/clairegrady/RiderProjects/betfair/horse-simulated/logs/lay_position_{POSITION_TO_LAY}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HorseLayBetting:
    """Lay betting on specific market position"""
    
    def __init__(self):
        self.processed_markets = set()
        self.session = requests.Session()
        self.session.timeout = 10
    
    @staticmethod
    def parse_event_name(event_name: str) -> Dict:
        """Parse venue and date from EventName field
        Example: 'Randwick (AUS) 13th Jan' -> {'venue': 'Randwick', 'country': 'AUS', 'date': '13th Jan'}
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
        """Get horse races within betting window"""
        try:
            # Get races from database
            conn = get_db_connection('betfair_races')
            query = """
                SELECT venue, race_number, race_time, race_date, country
                FROM horse_race_times
                WHERE race_date::date >= CURRENT_DATE
                ORDER BY race_time
            """
            df = pd.read_sql(query, conn)
            conn.close()
            
            # Log total races once at startup
            if not self.logged_initial_races:
                logger.info(f"📊 Found {len(df)} total races in database for today")
                self.logged_initial_races = True
            if df.empty:
                return []
            
            # Filter races within time window
            aest_tz = pytz.timezone('Australia/Sydney')
            now_aest = datetime.now(aest_tz)
            
            upcoming_races = []
            for _, row in df.iterrows():
                race_datetime_str = f"{row['race_date']} {row['race_time']}"
                race_datetime = aest_tz.localize(datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M'))
                
                seconds_until = (race_datetime - now_aest).total_seconds()
                
                # Only bet if within 30 seconds window (5 seconds margin)
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
            
            return upcoming_races
            
        except Exception as e:
            logger.error(f"Error getting upcoming races: {e}")
            return []
    
    def find_market_id(self, venue: str, race_number: int) -> Optional[str]:
        """Find Win market ID for this race"""
        try:
            conn = get_db_connection("betfairmarket")
            cursor = conn.cursor()
            
            today_str = datetime.now(pytz.timezone('Australia/Sydney')).strftime("%-d")
            
            query = """
                SELECT marketid
                FROM marketcatalogue
                WHERE LOWER(eventname) LIKE LOWER(%s)
                AND LOWER(marketname) LIKE LOWER(%s)
                AND eventtypename = 'Horse Racing'
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
        """Fallback: Get lay odds from MarketBookLayprices (Stream API data)"""
        try:
            conn = get_db_connection("betfairmarket")
            cursor = conn.cursor()
            
            # Get lay prices from Stream API data
            query = """
                SELECT DISTINCT selectionid, price
                FROM horsemarketbook
                WHERE marketid = %s
                AND pricetype = 'AvailableToLay'
                AND price IS NOT NULL
                ORDER BY price ASC
            """
            
            cursor.execute(query, (market_id,))
            price_results = cursor.fetchall()
            
            if not price_results:
                return None
            
            # Get runner names and barriers
            cursor.execute("""
                SELECT DISTINCT selectionid, runner_name, stall_draw
                FROM horsemarketbook
                WHERE marketid = %s
                AND runner_name IS NOT NULL
            """, (market_id,))
            runner_results = cursor.fetchall()
            
            conn.close()
            
            # Build lookups
            import re
            runner_names = {}
            barrier_numbers = {}
            for sel_id, runner_name, barrier in runner_results:
                clean_name = re.sub(r'^\d+\.\s*', '', runner_name) if runner_name else f'Horse {sel_id}'
                runner_names[sel_id] = clean_name
                if barrier:
                    barrier_numbers[sel_id] = barrier
            
            # Build odds map - take best (lowest) lay price per selection
            runners_dict = {}
            for sel_id, price in price_results:
                if sel_id not in runners_dict:
                    runners_dict[sel_id] = {
                        'selection_id': sel_id,
                        'odds': price,
                        'horse_name': runner_names.get(sel_id, f'Horse {sel_id}'),
                        'barrier': barrier_numbers.get(sel_id)
                    }
            
            odds_map = list(runners_dict.values())
            return {'runners': odds_map} if odds_map else None
            
        except Exception as e:
            logger.error(f"Error getting odds from DB: {e}")
            return None
    
    def get_odds_and_runners(self, market_id: str) -> Optional[Dict]:
        """Get current odds for all runners (tries API first, then MarketBookLayprices fallback)"""
        try:
            url = f"{BACKEND_URL}/api/horse-racing/market-book/{market_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"API returned {response.status_code}, trying MarketBookLayprices fallback")
                return self.get_odds_from_db(market_id)
            
            data = response.json()
            runners = data.get('runners', [])
            
            if not runners:
                logger.debug("No runners from API, trying MarketBookLayprices fallback")
                return self.get_odds_from_db(market_id)
            
            # Get runner names and barriers from HorseMarketBook table
            conn = get_db_connection("betfairmarket")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT selectionid, runner_name, stall_draw
                FROM horsemarketbook
                WHERE marketid = %s
            """, (market_id,))
            
            import re
            runner_names = {}
            barrier_numbers = {}
            for sel_id, runner_name, barrier in cursor.fetchall():
                if runner_name:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    runner_names[sel_id] = clean_name
                if barrier:
                    barrier_numbers[sel_id] = barrier
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
                            'horse_name': runner_names.get(selection_id, f'Horse {selection_id}'),
                            'barrier': barrier_numbers.get(selection_id)
                        })
            
            return {'runners': odds_map} if odds_map else None
            
        except Exception as e:
            logger.warning(f"API error: {e}, trying MarketBookLayprices fallback")
            return self.get_odds_from_db(market_id)
    
    def place_lay_bet(self, race_info: Dict, horse: Dict, position: int):
        """Record a lay bet"""
        try:
            # Get total matched from MarketCatalogue
            total_matched = None
            try:
                betfair_conn = get_db_connection("betfairmarket")
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
            
            liability = FLAT_STAKE * (horse['odds'] - 1)
            
            cursor.execute("""
                INSERT INTO paper_trades_horses
                (date, venue, country, race_number, market_id, selection_id, horse_name, barrier_number,
                 position_in_market, odds, stake, liability, finishing_position, result, total_matched)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                race_info['venue'],
                race_info['country'],
                race_info['race_number'],
                race_info['market_id'],
                horse['selection_id'],
                horse['horse_name'],
                horse.get('barrier'),  # Get barrier number from horse data
                position,
                horse['odds'],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending',
                total_matched
            ))
            
            conn.commit()
            conn.close()
            
            barrier_info = f" [Barrier {horse.get('barrier')}]" if horse.get('barrier') else ""
            logger.info(f"✅ LAY BET: {horse['horse_name']}{barrier_info} (ID: {horse['selection_id']}) @ {horse['odds']} (Position {position}) - Liability: ${liability:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error placing bet: {e}")
            return False
    
    def process_race(self, race_info: Dict):
        """Process a single race"""
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"🏇 {race_info['venue']} ({race_info['country']}) - Race {race_info['race_number']}")
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
            sorted_runners = sorted(runners, key=lambda x: (x["odds"], x["selection_id"]))
            
            # Get the horse at our position
            target_horse = sorted_runners[POSITION_TO_LAY - 1]

            # Check for zero or invalid odds - DO NOT BET!
            if target_horse['odds'] <= 0:
                logger.error(f"❌ SKIPPING - Invalid odds {target_horse['odds']} for {target_horse.get('horse_name', 'Unknown')} (Position {POSITION_TO_LAY})")
                return
            
            # Check max odds
            if target_horse['odds'] > MAX_ODDS:
                logger.info(f"⏭️  Skipping - odds {target_horse['odds']} > {MAX_ODDS}")
                return
            
            # Place lay bet
            self.place_lay_bet(race_info, target_horse, POSITION_TO_LAY)
            
        except Exception as e:
            logger.error(f"Error processing race: {e}")
    
    def run(self):
        self.logged_initial_races = False
        """Main monitoring loop"""
        logger.info("=" * 70)
        logger.info(f"🏇 HORSE RACING LAY BETTING - POSITION {POSITION_TO_LAY}")
        logger.info("=" * 70)
        logger.info(f"   Max odds: {MAX_ODDS}")
        logger.info(f"   Stake: ${FLAT_STAKE}")
        logger.info(f"   Betting window: {SECONDS_BEFORE_RACE} seconds before race")
        logger.info("\n⏰ Monitoring races...\n")
        
        try:
            while True:
                upcoming = self.get_upcoming_races()
                
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
    betting = HorseLayBetting()
    betting.run()
