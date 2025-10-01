#!/usr/bin/env python3
"""
Greyhound Betting Simulation System

Simulates betting strategies on Australian greyhound races:
1. $1 on favorite to win and place
2. $1 on top 2 to win and place  
3. $1 on top 3 to win and place
4. $1 on top 4 to win and place
5. $10 on favorite if odds <= 60% of 2nd favorite
6. Combined strategy: $1 on favorite to win, $1 on 2nd favorite to place, $1 on 3rd favorite to place
7. Enhanced combined strategy: $1 on favorite to win, $2 on 2nd favorite to place, $2 on 3rd favorite to place
8. Lay $1 on every dog at best lay odds
9. Proportional lay betting: $1 on longest odds, proportional stakes on others

Uses HTTP refresh approach (no Stream API) and processes races within 2 minutes of start.
Records trap positions for greyhound-specific analysis.
"""

import requests
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GreyhoundBettingSimulation:
    def __init__(self, api_base_url="http://localhost:5173"):
        self.api_base_url = api_base_url.rstrip('/')
        self.db_path = "betting_simulation.sqlite"
        self.betting_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/betting_history.sqlite"
        self.australian_timezone = pytz.timezone('Australia/Sydney')
        
        # Initialize database
        self.init_database()
        
    
    def init_database(self):
        """Initialize simulation database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create greyhound simulation results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS valid_greyhound_simulation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_date DATE,
                venue TEXT,
                race_number INTEGER,
                market_id TEXT,
                strategy TEXT,
                dog_name TEXT,
                trap_position INTEGER,
                win_odds REAL,
                place_odds REAL,
                lay_odds REAL,
                stake REAL,
                bet_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add UNIQUE constraint to prevent duplicate bets
        try:
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_greyhound_bet 
                ON valid_greyhound_simulation_results (race_date, venue, race_number, strategy, dog_name, bet_type)
            ''')
        except sqlite3.OperationalError:
            # Index might already exist, ignore
            pass
        
        # Create greyhound race tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS greyhound_race_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT UNIQUE,
                venue TEXT,
                race_number INTEGER,
                race_time DATETIME,
                status TEXT DEFAULT 'pending',
                strategies_applied TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    def get_australian_greyhound_races_today(self):
        """Get Australian greyhound races for today from race_times table"""
        try:
            import sqlite3
            
            # Connect to the live_betting database
            conn = sqlite3.connect('live_betting.sqlite')
            cursor = conn.cursor()
            
            # Get Australian greyhound races from race_times table for today
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            query = """
                SELECT venue, race_number, race_time, race_date
                FROM greyhound_race_times 
                WHERE race_date = ? AND country = 'AUS'
                ORDER BY race_time
            """
            
            cursor.execute(query, (today,))
            rows = cursor.fetchall()
            conn.close()
            
            races = []
            for row in rows:
                venue, race_number, race_time, race_date = row
                
                # Try to find matching market ID from betfairmarket database
                market_id = self.find_market_id_for_race(venue, race_number, race_date)
                if market_id:
                    races.append({
                        'market_id': market_id,
                        'venue': venue,
                        'race_number': race_number,
                        'race_time': race_time,
                        'race_date': race_date
                    })
            
            logger.info(f"🐕 Found {len(races)} Australian greyhound races today")
            return races
            
        except Exception as e:
            logger.error(f"❌ Error getting Australian races: {e}")
            return []
    
    def find_market_id_for_race(self, venue, race_number, race_date):
        """Find market ID for a specific race"""
        try:
            import sqlite3
            from datetime import date, datetime
            
            # Connect to betfairmarket database
            conn = sqlite3.connect('/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite')
            cursor = conn.cursor()
            
            # Format race_date to the EventName style, e.g., "26th Sep"
            def _ordinal(n: int) -> str:
                if 11 <= (n % 100) <= 13:
                    suffix = 'th'
                else:
                    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
                return f"{n}{suffix}"

            def _format_event_date(d) -> str:
                # Accepts date, datetime, or ISO string
                if isinstance(d, str):
                    try:
                        d_parsed = datetime.fromisoformat(d).date()
                    except ValueError:
                        # Best effort: try plain YYYY-MM-DD
                        d_parsed = datetime.strptime(d, '%Y-%m-%d').date()
                elif isinstance(d, datetime):
                    d_parsed = d.date()
                elif isinstance(d, date):
                    d_parsed = d
                else:
                    d_parsed = datetime.now().date()
                day_str = _ordinal(d_parsed.day)
                month_str = d_parsed.strftime('%b')
                return f"{day_str} {month_str}"

            event_date_token = _format_event_date(race_date)

            # Match by venue, race number, and event date token inside EventName
            query = """
                SELECT DISTINCT MarketId 
                FROM GreyhoundMarketBook 
                WHERE (EventName LIKE ? OR MarketName LIKE ?)
                AND (MarketName LIKE ? OR MarketName LIKE ?)
                AND EventName LIKE ?
                LIMIT 1
            """

            cursor.execute(query, (
                f'%{venue}%', f'%{venue}%',
                f'R{race_number}%', f'Race {race_number}%',
                f'%{event_date_token}%'
            ))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.warning(f"⚠️ Error finding market ID for {venue} R{race_number}: {e}")
            return None
    
    def refresh_odds(self, market_id):
        """Refresh odds for a market using HTTP request"""
        try:
            refresh_url = f"{self.api_base_url}/api/odds/refresh/{market_id}"
            response = requests.get(refresh_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"🔄 Refreshed odds for market {market_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to refresh odds: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Error refreshing odds: {e}")
            return False
    
    def get_current_odds(self, market_id):
        """Get current odds for a market using CurrentOdds table (like lay_betting_automation.py)"""
        try:
            import sqlite3
            import pandas as pd
            import requests
            
            # Connect to betting database (same as lay_betting_automation.py)
            betting_conn = sqlite3.connect(self.betting_db_path)
            
            # Get best back and lay odds for greyhounds (for both back and lay betting)
            current_odds_query = """
            SELECT 
                SelectionId,
                COALESCE(RunnerName, 'Dog ' || SelectionId) as runner_name,
                best_back_price,
                best_back_size,
                best_lay_price,
                best_lay_size,
                LastPriceTraded,
                TotalMatched,
                0 as cloth_number
            FROM CurrentWinOdds
            WHERE MarketId = ? AND (best_back_price IS NOT NULL OR best_lay_price IS NOT NULL)
            ORDER BY best_back_price
            """
            
            result_df = pd.read_sql_query(current_odds_query, betting_conn, params=[market_id])
            betting_conn.close()
            
            if result_df.empty:
                logger.warning(f"⚠️ No CurrentOdds data for market {market_id}, attempting refresh...")
                try:
                    import requests
                    refresh_url = f"{self.api_base_url}/api/odds/refresh/{market_id}"
                    response = requests.get(refresh_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"🔄 Refresh successful, retrying CurrentOdds query...")
                        # Retry the CurrentOdds query with fresh connection
                        betting_conn_retry = sqlite3.connect(self.betting_db_path)
                        result_df = pd.read_sql_query(current_odds_query, betting_conn_retry, params=[market_id])
                        betting_conn_retry.close()
                        if not result_df.empty:
                            logger.info(f"📊 Using refreshed CurrentOdds data for market {market_id} ({len(result_df)} horses)")
                        else:
                            logger.warning(f"⚠️ Still no CurrentOdds data after refresh for market {market_id}")
                            return []
                    else:
                        logger.warning(f"⚠️ Refresh failed with status {response.status_code}")
                        return []
                except Exception as e:
                    logger.warning(f"⚠️ Refresh failed: {e}")
                    return []
            
            # Get horse statuses from HorseMarketBook to check for scratched horses
            market_conn = sqlite3.connect('/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite')
            status_query = """
                SELECT SelectionId, Status 
                FROM GreyhoundMarketBook 
                WHERE MarketId = ?
            """
            status_df = pd.read_sql_query(status_query, market_conn, params=[market_id])
            market_conn.close()
            
            # Create a status lookup dictionary
            horse_status = {}
            for _, status_row in status_df.iterrows():
                horse_status[status_row['SelectionId']] = status_row['Status']
            
            horses = []
            for _, row in result_df.iterrows():
                selection_id = int(row['SelectionId'])
                
                # Check if horse is scratched/removed by checking HorseMarketBook status
                horse_status_value = horse_status.get(selection_id, 'UNKNOWN')
                if horse_status_value != 'ACTIVE':
                    logger.warning(f"⚠️ Skipping scratched horse {selection_id} ({row['runner_name']}) - status: {horse_status_value}")
                    continue
                
                # Check if horse has valid odds (back or lay)
                back_price = row['best_back_price']
                lay_price = row['best_lay_price']
                
                if (not back_price or back_price <= 0) and (not lay_price or lay_price <= 0):
                    logger.warning(f"⚠️ Skipping horse {selection_id} ({row['runner_name']}) - no valid odds")
                    continue
                
                # Use best back price as win odds (for betting on horses to win)
                win_odds = back_price if back_price and back_price > 0 else 0
                
                # Get lay odds for lay betting
                lay_odds = lay_price if lay_price and lay_price > 0 else 0
                
                # Get real place odds from place market
                place_odds = self.get_place_odds_for_horse(market_id, selection_id)
                
                # NO ESTIMATION - only use real place odds
                if place_odds == 0:
                    logger.warning(f"⚠️ No place odds for horse {selection_id} - will skip place bets")
                    place_odds = 0  # This will prevent place betting
                
                # Extract trap position from runner name (e.g., "1. Dog Name" -> trap 1)
                trap_position = self.extract_trap_position(row['runner_name'])
                
                horses.append({
                    'selection_id': selection_id,
                    'dog_name': row['runner_name'],
                    'trap_position': trap_position,
                    'win_odds': win_odds,
                    'place_odds': place_odds,
                    'lay_odds': lay_odds
                })
            
            # Sort by win odds (favorite first)
            horses.sort(key=lambda x: x['win_odds'] if x['win_odds'] > 0 else 999)
            logger.info(f"📊 Got {len(horses)} dogs with odds for market {market_id}")
            return horses
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting odds from database: {e}")
            return []
    
    def extract_trap_position(self, runner_name):
        """Extract trap position from greyhound runner name (e.g., '1. Dog Name' -> 1)"""
        try:
            import re
            # Look for pattern like "1. Dog Name" or "Trap 1: Dog Name"
            match = re.match(r'^(\d+)\.', runner_name)
            if match:
                return int(match.group(1))
            
            # Alternative pattern: "Trap 1: Dog Name"
            match = re.match(r'^Trap\s+(\d+):', runner_name)
            if match:
                return int(match.group(1))
            
            # If no pattern matches, return 0 (unknown)
            return 0
        except:
            return 0
    
    def get_place_odds_for_horse(self, win_market_id, selection_id):
        """Get real place odds for a horse from place market"""
        try:
            import sqlite3
            import requests
            
            # First, try to get place market ID from the API
            place_market_id = self.get_place_market_id(win_market_id)
            if not place_market_id:
                logger.warning(f"⚠️ No place market found for win market {win_market_id}")
                return 0
            
            # Get place odds from the place market
            betting_conn = sqlite3.connect(self.betting_db_path)
            cursor = betting_conn.cursor()
            
            cursor.execute('''
                SELECT best_back_price 
                FROM CurrentPlaceOdds 
                WHERE MarketId = ? AND SelectionId = ? AND best_back_price IS NOT NULL
            ''', (place_market_id, selection_id))
            
            result = cursor.fetchone()
            betting_conn.close()
            
            if result and result[0]:
                return float(result[0])
            else:
                logger.warning(f"⚠️ No place odds found for horse {selection_id} in place market {place_market_id}")
                return 0
                
        except Exception as e:
            logger.warning(f"⚠️ Error getting place odds: {e}")
            return 0
    
    def get_place_market_id(self, win_market_id):
        """Get place market ID for a win market"""
        # Place markets have the last decimal digit incremented by 1
        # Win market: 1.248273740 -> Place market: 1.248273741
        
        # Convert to float, add 0.000000001, then back to string
        win_id_float = float(win_market_id)
        place_id_float = win_id_float + 0.000000001
        place_market_id = f"{place_id_float:.9f}"
        
        logger.info(f"🔄 Place market ID: {place_market_id} (from win market: {win_market_id})")
        return place_market_id
    
    
    def simulate_strategy_1(self, horses, market_id, venue, race_number):
        """Strategy 1: $1 on favorite to win and place"""
        if len(horses) == 0:
            return []
        
        favorite = horses[0]
        bets = []
        
        # Check if favorite has valid odds (not scratched)
        if favorite['win_odds'] <= 0:
            logger.warning(f"⚠️ Skipping Strategy 1 for {venue} R{race_number} - favorite has invalid odds (scratched?)")
            return []
        
        # Win bet
        bets.append({
            'strategy': 'Strategy 1 - Favorite Win',
            'horse_name': favorite['horse_name'],
            'win_odds': favorite['win_odds'],
            'place_odds': favorite['place_odds'],
            'stake': 1.0,
            'bet_type': 'win'
        })
        
        # Place bet (only if real place odds available)
        if favorite['place_odds'] > 0:
            bets.append({
                'strategy': 'Strategy 1 - Favorite Place',
                'horse_name': favorite['horse_name'],
                'win_odds': favorite['win_odds'],
                'place_odds': favorite['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        else:
            logger.warning(f"⚠️ Skipping place bet for {favorite['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_2(self, horses, market_id, venue, race_number):
        """Strategy 2: $1 on top 2 to win and place"""
        if len(horses) < 2:
            return []
        
        bets = []
        for i in range(2):
            horse = horses[i]
            
            # Win bet
            bets.append({
                'strategy': f'Strategy 2 - Top 2 Win (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': horse['win_odds'],
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet (only if real place odds available)
            if horse['place_odds'] > 0:
                bets.append({
                    'strategy': f'Strategy 2 - Top 2 Place (Position {i+1})',
                    'horse_name': horse['horse_name'],
                    'win_odds': horse['win_odds'],
                    'place_odds': horse['place_odds'],
                    'stake': 1.0,
                    'bet_type': 'place'
                })
            else:
                logger.warning(f"⚠️ Skipping place bet for {horse['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_3(self, horses, market_id, venue, race_number):
        """Strategy 3: $1 on top 3 to win and place"""
        if len(horses) < 3:
            return []
        
        bets = []
        for i in range(3):
            horse = horses[i]
            
            # Win bet
            bets.append({
                'strategy': f'Strategy 3 - Top 3 Win (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': horse['win_odds'],
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet (only if real place odds available)
            if horse['place_odds'] > 0:
                bets.append({
                    'strategy': f'Strategy 3 - Top 3 Place (Position {i+1})',
                    'horse_name': horse['horse_name'],
                    'win_odds': horse['win_odds'],
                    'place_odds': horse['place_odds'],
                    'stake': 1.0,
                    'bet_type': 'place'
                })
            else:
                logger.warning(f"⚠️ Skipping place bet for {horse['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_4(self, horses, market_id, venue, race_number):
        """Strategy 4: $1 on top 4 to win and place"""
        if len(horses) < 4:
            return []
        
        bets = []
        for i in range(4):
            horse = horses[i]
            
            # Win bet
            bets.append({
                'strategy': f'Strategy 4 - Top 4 Win (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': horse['win_odds'],
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet (only if real place odds available)
            if horse['place_odds'] > 0:
                bets.append({
                    'strategy': f'Strategy 4 - Top 4 Place (Position {i+1})',
                    'horse_name': horse['horse_name'],
                    'win_odds': horse['win_odds'],
                    'place_odds': horse['place_odds'],
                    'stake': 1.0,
                    'bet_type': 'place'
                })
            else:
                logger.warning(f"⚠️ Skipping place bet for {horse['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_5(self, horses, market_id, venue, race_number):
        """Strategy 5: $10 on favorite if odds <= 50% of 2nd favorite"""
        if len(horses) < 2:
            return []
        
        favorite = horses[0]
        second_favorite = horses[1]
        
        # Check if favorite odds <= 50% of 2nd favorite odds
        if favorite['win_odds'] > 0 and second_favorite['win_odds'] > 0:
            threshold = second_favorite['win_odds'] * 0.5
            if favorite['win_odds'] <= threshold:
                return [{
                    'strategy': 'Strategy 5 - Favorite Value Bet',
                    'horse_name': favorite['horse_name'],
                    'win_odds': favorite['win_odds'],
                    'place_odds': favorite['place_odds'],
                    'stake': 10.0,
                    'bet_type': 'win'
                }]
        
        return []
    
    def simulate_strategy_6(self, horses, market_id, venue, race_number):
        """Strategy 6: Combined strategy - $1 on favorite to win, $1 on 2nd favorite to place, $1 on 3rd favorite to place"""
        if len(horses) < 3:
            return []
        
        bets = []
        
        # Check if we have at least 3 horses with valid odds
        if horses[0]['win_odds'] <= 0 or horses[1]['win_odds'] <= 0 or horses[2]['win_odds'] <= 0:
            logger.warning(f"⚠️ Skipping Strategy 6 for {venue} R{race_number} - not enough horses with valid odds")
            return []
        
        # $1 on favorite to win
        bets.append({
            'strategy': 'Strategy 6 - Combined (Favorite Win)',
            'dog_name': horses[0]['dog_name'],
            'trap_position': horses[0]['trap_position'],
            'win_odds': horses[0]['win_odds'],
            'place_odds': horses[0]['place_odds'],
            'stake': 1.0,
            'bet_type': 'win'
        })
        
        # $1 on 2nd favorite to place (only if real place odds available)
        if horses[1]['place_odds'] > 0:
            bets.append({
                'strategy': 'Strategy 6 - Combined (2nd Favorite Place)',
                'dog_name': horses[1]['dog_name'],
                'trap_position': horses[1]['trap_position'],
                'win_odds': horses[1]['win_odds'],
                'place_odds': horses[1]['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        else:
            logger.warning(f"⚠️ Skipping 2nd favorite place bet for {horses[1]['horse_name']} - no real place odds available")
        
        # $1 on 3rd favorite to place (only if real place odds available)
        if horses[2]['place_odds'] > 0:
            bets.append({
                'strategy': 'Strategy 6 - Combined (3rd Favorite Place)',
                'dog_name': horses[2]['dog_name'],
                'trap_position': horses[2]['trap_position'],
                'win_odds': horses[2]['win_odds'],
                'place_odds': horses[2]['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        else:
            logger.warning(f"⚠️ Skipping 3rd favorite place bet for {horses[2]['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_7(self, horses, market_id, venue, race_number):
        """Strategy 7: Enhanced combined strategy - $1 on favorite to win, $2 on 2nd favorite to place, $2 on 3rd favorite to place"""
        if len(horses) < 3:
            return []
        
        bets = []
        
        # Check if we have at least 3 horses with valid odds
        if horses[0]['win_odds'] <= 0 or horses[1]['win_odds'] <= 0 or horses[2]['win_odds'] <= 0:
            logger.warning(f"⚠️ Skipping Strategy 7 for {venue} R{race_number} - not enough horses with valid odds")
            return []
        
        # $1 on favorite to win
        bets.append({
            'strategy': 'Strategy 7 - Enhanced Combined (Favorite Win)',
            'dog_name': horses[0]['dog_name'],
            'trap_position': horses[0]['trap_position'],
            'win_odds': horses[0]['win_odds'],
            'place_odds': horses[0]['place_odds'],
            'stake': 1.0,
            'bet_type': 'win'
        })
        
        # $2 on 2nd favorite to place (only if real place odds available)
        if horses[1]['place_odds'] > 0:
            bets.append({
                'strategy': 'Strategy 7 - Enhanced Combined (2nd Favorite Place)',
                'dog_name': horses[1]['dog_name'],
                'trap_position': horses[1]['trap_position'],
                'win_odds': horses[1]['win_odds'],
                'place_odds': horses[1]['place_odds'],
                'stake': 2.0,
                'bet_type': 'place'
            })
        else:
            logger.warning(f"⚠️ Skipping 2nd favorite place bet for {horses[1]['horse_name']} - no real place odds available")
        
        # $2 on 3rd favorite to place (only if real place odds available)
        if horses[2]['place_odds'] > 0:
            bets.append({
                'strategy': 'Strategy 7 - Enhanced Combined (3rd Favorite Place)',
                'dog_name': horses[2]['dog_name'],
                'trap_position': horses[2]['trap_position'],
                'win_odds': horses[2]['win_odds'],
                'place_odds': horses[2]['place_odds'],
                'stake': 2.0,
                'bet_type': 'place'
            })
        else:
            logger.warning(f"⚠️ Skipping 3rd favorite place bet for {horses[2]['horse_name']} - no real place odds available")
        
        return bets
    
    def simulate_strategy_8(self, horses, market_id, venue, race_number):
        """Strategy 8: Lay $1 on every horse at the best available lay odds"""
        if len(horses) == 0:
            return []
        
        bets = []
        
        for horse in horses:
            # Only lay if we have valid lay odds
            if horse['lay_odds'] > 0:
                bets.append({
                    'strategy': 'Strategy 8 - Lay All Horses',
                    'horse_name': horse['horse_name'],
                    'win_odds': horse['win_odds'],
                    'place_odds': horse['place_odds'],
                    'lay_odds': horse['lay_odds'],
                    'stake': 1.0,
                    'bet_type': 'lay'
                })
            else:
                logger.warning(f"⚠️ Skipping lay bet for {horse['horse_name']} - no valid lay odds available")
        
        return bets
    
    def simulate_strategy_9(self, horses, market_id, venue, race_number):
        """Strategy 9: Proportional lay betting - $1 on longest odds, proportional on others"""
        if len(horses) < 2:
            return []
        
        # Sort by lay odds (longest odds first for lay betting)
        horses_with_lay_odds = [h for h in horses if h['lay_odds'] > 0]
        if len(horses_with_lay_odds) < 2:
            logger.warning(f"⚠️ Skipping Strategy 9 for {venue} R{race_number} - not enough horses with lay odds")
            return []
        
        # Sort by lay odds (highest lay odds first - these are the longest odds horses)
        horses_with_lay_odds.sort(key=lambda x: x['lay_odds'], reverse=True)
        
        bets = []
        
        # Find the longest odds horse (highest lay odds)
        longest_odds_horse = horses_with_lay_odds[0]
        longest_odds = longest_odds_horse['lay_odds']
        
        # Lay $1 on the longest odds horse
        bets.append({
            'strategy': 'Strategy 9 - Proportional Lay (Longest Odds)',
            'horse_name': longest_odds_horse['horse_name'],
            'win_odds': longest_odds_horse['win_odds'],
            'place_odds': longest_odds_horse['place_odds'],
            'lay_odds': longest_odds_horse['lay_odds'],
            'stake': 1.0,
            'bet_type': 'lay'
        })
        
        # Calculate proportional stakes for other horses
        for horse in horses_with_lay_odds[1:]:
            if horse['lay_odds'] > 0:
                # Calculate proportional stake: (longest_odds / current_odds) * 1.0
                proportional_stake = (longest_odds / horse['lay_odds']) * 1.0
                
                # Cap the stake at a reasonable maximum (e.g., $100)
                proportional_stake = min(proportional_stake, 100.0)
                
                bets.append({
                    'strategy': 'Strategy 9 - Proportional Lay (Proportional)',
                    'horse_name': horse['horse_name'],
                    'win_odds': horse['win_odds'],
                    'place_odds': horse['place_odds'],
                    'lay_odds': horse['lay_odds'],
                    'stake': round(proportional_stake, 2),
                    'bet_type': 'lay'
                })
        
        return bets
    
    def save_simulation_results(self, bets, venue, race_number, market_id):
        """Save simulation results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        for bet in bets:
            cursor.execute('''
                INSERT OR IGNORE INTO valid_greyhound_simulation_results 
                (race_date, venue, race_number, market_id, strategy, dog_name, trap_position,
                 win_odds, place_odds, lay_odds, stake, bet_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, venue, race_number, market_id, bet['strategy'], bet['dog_name'], bet.get('trap_position', 0),
                bet['win_odds'], bet['place_odds'], bet.get('lay_odds', 0), bet['stake'], bet['bet_type']
            ))
        
        conn.commit()
        conn.close()
    
    def is_race_already_processed(self, venue, race_number, race_date):
        """Check if race was already processed (persistent check)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if race_date column exists
            cursor.execute('PRAGMA table_info(race_tracking)')
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'race_date' in columns:
                # Use race_date column
                cursor.execute('''
                    SELECT COUNT(*) FROM race_tracking 
                    WHERE venue = ? AND race_number = ? AND race_date = ?
                ''', (venue, race_number, race_date))
            else:
                # Fallback to venue and race_number only (for today's races)
                cursor.execute('''
                    SELECT COUNT(*) FROM race_tracking 
                    WHERE venue = ? AND race_number = ?
                ''', (venue, race_number))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.warning(f"⚠️ Error checking race processing status: {e}")
            return False
    
    def mark_race_as_processed(self, venue, race_number, race_date, market_id, bets):
        """Mark race as processed in race_tracking table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get strategies applied
            strategies = list(set([bet['strategy'] for bet in bets]))
            strategies_str = ', '.join(strategies)
            
            # Check if race_date column exists
            cursor.execute('PRAGMA table_info(race_tracking)')
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'race_date' in columns:
                # Use race_date column
                cursor.execute('''
                    INSERT OR REPLACE INTO race_tracking 
                    (market_id, venue, race_number, race_date, status, strategies_applied)
                    VALUES (?, ?, ?, ?, 'processed', ?)
                ''', (market_id, venue, race_number, race_date, strategies_str))
            else:
                # Fallback without race_date column
                cursor.execute('''
                    INSERT OR REPLACE INTO race_tracking 
                    (market_id, venue, race_number, status, strategies_applied)
                    VALUES (?, ?, ?, 'processed', ?)
                ''', (market_id, venue, race_number, strategies_str))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.warning(f"⚠️ Error marking race as processed: {e}")
    
    def run_simulation(self):
        """Run the complete simulation with continuous monitoring"""
        logger.info("🚀 Starting betting simulation...")
        
        # Get Australian greyhound races for today
        races = self.get_australian_greyhound_races_today()
        if not races:
            logger.warning("⚠️ No Australian greyhound races found for today")
            return
        
        logger.info(f"🐕 Found {len(races)} Australian greyhound races to simulate")
        
        # Track processed races to avoid duplicates
        processed_races = set()
        
        # Continuous monitoring loop
        while True:
            current_time = datetime.now(pytz.UTC)
            races_processed_this_cycle = 0
            
            for race in races:
                market_id = race['market_id']
                venue = race['venue']
                race_number = race['race_number']
                race_time_str = race['race_time']
                
                # Create unique race identifier
                race_id = f"{venue}_{race_number}_{race['race_date']}"
                
                # Skip if already processed in memory
                if race_id in processed_races:
                    continue
                
                # Check if race was already processed (persistent check)
                if self.is_race_already_processed(venue, race_number, race['race_date']):
                    logger.info(f"⏭️ Race {venue} R{race_number} already processed - skipping")
                    processed_races.add(race_id)
                    continue
                
                try:
                    # Parse race time (handle both full datetime and time-only strings)
                    if 'T' in race_time_str or ' ' in race_time_str:
                        # Full datetime string
                        race_time = datetime.fromisoformat(race_time_str.replace('Z', '+00:00'))
                    else:
                        # Time-only string, combine with today's date
                        today = datetime.now().date()
                        race_time = datetime.combine(today, datetime.strptime(race_time_str, '%H:%M').time())
                        # Convert to UTC (assuming Australian timezone)
                        race_time = self.australian_timezone.localize(race_time).astimezone(pytz.UTC)
                    
                    # Check if race is within betting window (1 minute before to 2 minutes after start)
                    time_diff = (race_time - current_time).total_seconds() / 60  # minutes
                    
                    # Process races within betting window (1 minute before to 2 minutes after start)
                    if -1 <= time_diff <= 1:  # Within greyhound betting window (1 minute before to 1 minute after)
                        if time_diff > 0:
                            logger.info(f"⏰ Race {venue} R{race_number} starts in {time_diff:.1f} minutes")
                            logger.info(f"🎯 Simulating greyhound bets for {venue} R{race_number} (within 1 minute of start)")
                        else:
                            logger.info(f"⏰ Race {venue} R{race_number} started {abs(time_diff):.1f} minutes ago")
                            logger.info(f"🎯 Simulating greyhound bets for {venue} R{race_number} (within 1 minute after start)")
                        
                        logger.info(f"📊 Market ID: {market_id}")
                        
                        horses = self.get_current_odds(market_id)
                        if not horses:
                            logger.warning(f"⚠️ No odds data for {venue} R{race_number} (Market: {market_id})")
                            processed_races.add(race_id)  # Mark as processed even if no odds
                            continue
                        
                        logger.info(f"✅ Got {len(horses)} horses with odds for {venue} R{race_number}")
                        
                        # Run all strategies
                        all_bets = []
                        all_bets.extend(self.simulate_strategy_1(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_2(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_3(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_4(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_5(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_6(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_7(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_8(horses, market_id, venue, race_number))
                        all_bets.extend(self.simulate_strategy_9(horses, market_id, venue, race_number))
                        
                        if all_bets:
                            self.save_simulation_results(all_bets, venue, race_number, market_id)
                            logger.info(f"✅ Simulated {len(all_bets)} bets for {venue} R{race_number}")
                            
                            # Mark race as processed in database
                            self.mark_race_as_processed(venue, race_number, race['race_date'], market_id, all_bets)
                        else:
                            logger.warning(f"⚠️ No bets generated for {venue} R{race_number}")
                        
                        # Mark race as processed
                        processed_races.add(race_id)
                        races_processed_this_cycle += 1
                        
                    elif time_diff < -2:
                        # Race started more than 2 minutes ago, mark as processed
                        logger.info(f"⏰ Race {venue} R{race_number} started {abs(time_diff):.1f} minutes ago - marking as processed")
                        processed_races.add(race_id)
                
                except Exception as e:
                    logger.error(f"❌ Error processing race {venue} R{race_number}: {e}")
                    processed_races.add(race_id)  # Mark as processed to avoid retry
            
            # Check if all races have been processed
            if len(processed_races) >= len(races):
                logger.info("🏁 All races have been processed. Simulation complete!")
                break
            
            # Log progress
            if races_processed_this_cycle > 0:
                logger.info(f"📊 Processed {races_processed_this_cycle} races this cycle. Total processed: {len(processed_races)}/{len(races)}")
            
            # Wait 30 seconds before next check
            logger.info("⏳ Waiting 30 seconds before next check...")
            time.sleep(30)

def main():
    """Main function for greyhound simulation"""
    simulation = GreyhoundBettingSimulation()
    simulation.run_simulation()

if __name__ == "__main__":
    main()
