#!/usr/bin/env python3
"""
Betting Simulation System

Simulates betting strategies on Australian horse races:
1. $1 on favorite to win and place
2. $1 on top 2 to win and place  
3. $1 on top 3 to win and place
4. $1 on top 4 to win and place
5. $10 on favorite if odds <= 60% of 2nd favorite

Uses HTTP refresh approach (no Stream API) and waits until 1 minute before race start.
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

class BettingSimulation:
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
        
        # Create simulation results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS simulation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_date DATE,
                venue TEXT,
                race_number INTEGER,
                market_id TEXT,
                strategy TEXT,
                horse_name TEXT,
                win_odds REAL,
                place_odds REAL,
                stake REAL,
                bet_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add UNIQUE constraint to prevent duplicate bets
        try:
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_bet 
                ON simulation_results (race_date, venue, race_number, strategy, horse_name, bet_type)
            ''')
        except sqlite3.OperationalError:
            # Index might already exist, ignore
            pass
        
        # Create race tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS race_tracking (
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
    
    def get_australian_races_today(self):
        """Get Australian races for today from race_times table"""
        try:
            import sqlite3
            
            # Connect to the live_betting database
            conn = sqlite3.connect('live_betting.sqlite')
            cursor = conn.cursor()
            
            # Get Australian races from race_times table for today
            query = """
                SELECT venue, race_number, race_time, race_date
                FROM race_times 
                WHERE race_date = date('now') AND country = 'AUS'
                ORDER BY race_time
            """
            
            cursor.execute(query)
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
            
            logger.info(f"🏇 Found {len(races)} Australian races today")
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
                FROM HorseMarketBook 
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
            
            # Connect to betting database (same as lay_betting_automation.py)
            betting_conn = sqlite3.connect(self.betting_db_path)
            
            # Get best back odds (for betting on horses to win)
            current_odds_query = """
            SELECT 
                SelectionId,
                COALESCE(RunnerName, 'Horse ' || SelectionId) as runner_name,
                best_back_price,
                best_back_size,
                LastPriceTraded,
                TotalMatched,
                0 as cloth_number
            FROM CurrentOdds
            WHERE MarketId = ? AND best_back_price IS NOT NULL
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
            
            horses = []
            for _, row in result_df.iterrows():
                # Use best back price as win odds (for betting on horses to win)
                back_price = row['best_back_price']
                win_odds = back_price if back_price and back_price > 0 else 0
                place_odds = self.estimate_place_odds(win_odds)
                
                horses.append({
                    'selection_id': int(row['SelectionId']),
                    'horse_name': row['runner_name'],
                    'win_odds': win_odds,
                    'place_odds': place_odds
                })
            
            # Sort by win odds (favorite first)
            horses.sort(key=lambda x: x['win_odds'] if x['win_odds'] > 0 else 999)
            logger.info(f"📊 Got {len(horses)} horses with odds for market {market_id}")
            return horses
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting odds from database: {e}")
            return []
    
    def estimate_place_odds(self, win_odds):
        """Estimate place odds from win odds"""
        if win_odds <= 0:
            return 0
        
        # Simple place odds estimation
        if win_odds <= 2.0:
            return round(win_odds * 0.7, 2)
        elif win_odds <= 4.0:
            return round(win_odds * 0.75, 2)
        elif win_odds <= 8.0:
            return round(win_odds * 0.8, 2)
        else:
            return round(win_odds * 0.85, 2)
    
    
    def simulate_strategy_1(self, horses, market_id, venue, race_number):
        """Strategy 1: $1 on favorite to win and place"""
        if len(horses) == 0:
            return []
        
        favorite = horses[0]
        bets = []
        
        # Win bet
        bets.append({
            'strategy': 'Strategy 1 - Favorite Win',
            'horse_name': favorite['horse_name'],
            'win_odds': favorite['win_odds'],
            'place_odds': 0,
            'stake': 1.0,
            'bet_type': 'win'
        })
        
        # Place bet
        bets.append({
            'strategy': 'Strategy 1 - Favorite Place',
            'horse_name': favorite['horse_name'],
            'win_odds': 0,
            'place_odds': favorite['place_odds'],
            'stake': 1.0,
            'bet_type': 'place'
        })
        
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
                'place_odds': 0,
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet
            bets.append({
                'strategy': f'Strategy 2 - Top 2 Place (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': 0,
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        
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
                'place_odds': 0,
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet
            bets.append({
                'strategy': f'Strategy 3 - Top 3 Place (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': 0,
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        
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
                'place_odds': 0,
                'stake': 1.0,
                'bet_type': 'win'
            })
            
            # Place bet
            bets.append({
                'strategy': f'Strategy 4 - Top 4 Place (Position {i+1})',
                'horse_name': horse['horse_name'],
                'win_odds': 0,
                'place_odds': horse['place_odds'],
                'stake': 1.0,
                'bet_type': 'place'
            })
        
        return bets
    
    def simulate_strategy_5(self, horses, market_id, venue, race_number):
        """Strategy 5: $10 on favorite if odds <= 60% of 2nd favorite"""
        if len(horses) < 2:
            return []
        
        favorite = horses[0]
        second_favorite = horses[1]
        
        # Check if favorite odds <= 60% of 2nd favorite odds
        if favorite['win_odds'] > 0 and second_favorite['win_odds'] > 0:
            threshold = second_favorite['win_odds'] * 0.6
            if favorite['win_odds'] <= threshold:
                return [{
                    'strategy': 'Strategy 5 - Favorite Value Bet',
                    'horse_name': favorite['horse_name'],
                    'win_odds': favorite['win_odds'],
                    'place_odds': 0,
                    'stake': 10.0,
                    'bet_type': 'win'
                }]
        
        return []
    
    
    def save_simulation_results(self, bets, venue, race_number, market_id):
        """Save simulation results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        for bet in bets:
            cursor.execute('''
                INSERT OR IGNORE INTO simulation_results 
                (race_date, venue, race_number, market_id, strategy, horse_name,
                 win_odds, place_odds, stake, bet_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, venue, race_number, market_id, bet['strategy'], bet['horse_name'],
                bet['win_odds'], bet['place_odds'], bet['stake'], bet['bet_type']
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
        
        # Get Australian races for today
        races = self.get_australian_races_today()
        if not races:
            logger.warning("⚠️ No Australian races found for today")
            return
        
        logger.info(f"🏇 Found {len(races)} Australian races to simulate")
        
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
                    if -2 <= time_diff <= 1:  # Within betting window
                        if time_diff > 0:
                            logger.info(f"⏰ Race {venue} R{race_number} starts in {time_diff:.1f} minutes")
                            logger.info(f"🎯 Simulating bets for {venue} R{race_number} (1 minute before start)")
                        else:
                            logger.info(f"⏰ Race {venue} R{race_number} started {abs(time_diff):.1f} minutes ago")
                            logger.info(f"🎯 Simulating bets for {venue} R{race_number} (within 2 minutes after start)")
                        
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
    """Main function"""
    simulation = BettingSimulation()
    simulation.run_simulation()

if __name__ == "__main__":
    main()
