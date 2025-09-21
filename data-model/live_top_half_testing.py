"""
Live Top Half Strategy Testing - Uses real Betfair odds
Tests the strategy with real market data without placing actual bets
"""
import sqlite3
import time
import logging
from datetime import datetime
import requests
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveTopHalfTester:
    """
    Live testing of the top-half lay betting strategy using real Betfair odds
    """
    
    def __init__(self, backend_url: str = "http://localhost:5000", 
                 max_minutes_ahead: int = 10, min_minutes_before: int = -3,
                 betting_window_start: int = 2, betting_window_end: int = -2,
                 max_odds_to_lay: float = 10.0, min_odds_to_lay: float = 2.0):
        self.backend_url = backend_url
        self.betting_db_path = "betting_history.sqlite"
        self.market_db_path = "betfairmarket.sqlite"
        self.test_results = []
        self.max_minutes_ahead = max_minutes_ahead
        self.min_minutes_before = min_minutes_before
        self.betting_window_start = betting_window_start  # Start betting 2 min before
        self.betting_window_end = betting_window_end      # Stop betting 2 min after
        self.max_odds_to_lay = max_odds_to_lay            # Don't lay above this odds
        self.min_odds_to_lay = min_odds_to_lay            # Don't lay below this odds
    
    def get_current_races(self) -> List[Dict]:
        """Get current races from the race_times table"""
        conn = sqlite3.connect(self.market_db_path)
        cursor = conn.cursor()
        
        try:
            # Get races starting within the configured time window
            cursor.execute('''
                SELECT venue, race_number, race_time, race_date
                FROM race_times 
                WHERE datetime(race_date || ' ' || race_time) BETWEEN 
                    datetime('now', 'localtime', '+{} minutes') AND 
                    datetime('now', 'localtime', '+{} minutes')
                ORDER BY race_time
            '''.format(self.min_minutes_before, self.max_minutes_ahead))
            
            races = []
            for row in cursor.fetchall():
                races.append({
                    'venue': row[0],
                    'race_number': row[1],
                    'race_time': row[2],
                    'race_date': row[3]
                })
            
            return races
            
        except Exception as e:
            logger.error(f"Error getting current races: {str(e)}")
            return []
        finally:
            conn.close()
    
    def is_in_betting_window(self, race_time: str, race_date: str) -> bool:
        """Check if we're in the betting window for this race"""
        try:
            from datetime import datetime
            
            # Parse race time
            race_datetime = datetime.strptime(f"{race_date} {race_time}", "%Y-%m-%d %H:%M")
            
            # Get current time
            now = datetime.now()
            
            # Calculate minutes until race
            minutes_until_race = (race_datetime - now).total_seconds() / 60
            
            # Check if we're in the betting window
            in_window = (minutes_until_race <= self.betting_window_start and 
                        minutes_until_race >= self.betting_window_end)
            
            logger.debug(f"Race in {minutes_until_race:.1f} minutes, betting window: {in_window}")
            return in_window
            
        except Exception as e:
            logger.error(f"Error checking betting window: {str(e)}")
            return False
    
    def get_race_odds(self, venue: str, race_number: int) -> Optional[Dict]:
        """Get current odds for a specific race from CurrentOdds table"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get odds from CurrentOdds table
            cursor.execute('''
                SELECT MarketId, SelectionId, RunnerName, Price, Size, Status
                FROM CurrentOdds 
                WHERE MarketId IN (
                    SELECT h.MarketId 
                    FROM HorseMarketBook h 
                    WHERE h.EventName LIKE ? 
                    AND h.MarketName LIKE ?
                )
                ORDER BY Price
            ''', (f'%{venue}%', f'R{race_number}%'))
            
            odds_data = cursor.fetchall()
            
            if not odds_data:
                logger.warning(f"No odds found for {venue} R{race_number}")
                return None
            
            # Group by selection
            runners = {}
            for row in odds_data:
                market_id, selection_id, runner_name, price, size, status = row
                
                if selection_id not in runners:
                    runners[selection_id] = {
                        'market_id': market_id,
                        'selection_id': selection_id,
                        'runner_name': runner_name or f'Horse {selection_id}',
                        'best_lay_price': price,
                        'size': size,
                        'status': status
                    }
                else:
                    # Keep the best (lowest) lay price
                    if price < runners[selection_id]['best_lay_price']:
                        runners[selection_id]['best_lay_price'] = price
                        runners[selection_id]['size'] = size
            
            return {
                'market_id': odds_data[0][0],  # Use first market_id
                'runners': list(runners.values())
            }
            
        except Exception as e:
            logger.error(f"Error getting race odds: {str(e)}")
            return None
        finally:
            conn.close()
    
    def refresh_odds(self, market_id: str) -> bool:
        """Refresh odds for a specific market via backend API"""
        try:
            response = requests.get(
                f"{self.backend_url}/api/odds/refresh/{market_id}",
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Refreshed odds for market {market_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing odds for market {market_id}: {str(e)}")
            return False
    
    def analyze_race_with_strategy(self, race_data: Dict) -> Optional[Dict]:
        """Analyze a race using the top-half strategy"""
        venue = race_data['venue']
        race_number = race_data['race_number']
        race_time = race_data['race_time']
        race_date = race_data['race_date']
        
        logger.info(f"Analyzing {venue} R{race_number}")
        
        # Check if we're in the betting window
        if not self.is_in_betting_window(race_time, race_date):
            logger.info(f"Not in betting window for {venue} R{race_number}")
            return None
        
        # Get current odds
        odds_data = self.get_race_odds(venue, race_number)
        if not odds_data:
            return None
        
        # Refresh odds to get latest data
        self.refresh_odds(odds_data['market_id'])
        time.sleep(2)  # Wait for refresh
        
        # Get updated odds
        updated_odds = self.get_race_odds(venue, race_number)
        if not updated_odds:
            return None
        
        runners = updated_odds['runners']
        
        # Check if we have enough horses (minimum 4)
        if len(runners) < 4:
            logger.info(f"Not enough horses: {len(runners)}")
            return None
        
        # Sort by odds (lowest first)
        runners.sort(key=lambda x: x['best_lay_price'])
        
        # Calculate top half
        total_horses = len(runners)
        top_half_count = total_horses // 2
        
        # For odd numbers, bet on the greater half
        if total_horses % 2 == 1:
            top_half_count += 1
        
        top_half = runners[:top_half_count]
        
        # Calculate odds variance in top half
        import numpy as np
        top_half_odds = [r['best_lay_price'] for r in top_half]
        odds_std = np.std(top_half_odds)
        
        # Strategy criteria (you can adjust these)
        min_std_threshold = 1.0  # Minimum standard deviation
        max_odds_threshold = 20.0  # Maximum odds to bet on
        
        if odds_std < min_std_threshold:
            logger.info(f"Top half odds too similar (std: {odds_std:.2f})")
            return None
        
        # Filter top half horses by your odds limits
        eligible_horses = []
        for horse in top_half:
            odds = horse['best_lay_price']
            if self.min_odds_to_lay <= odds <= self.max_odds_to_lay:
                eligible_horses.append(horse)
        
        # If we have very few horses in range, be more flexible
        if len(eligible_horses) < 2:
            logger.info(f"Only {len(eligible_horses)} horses in odds range {self.min_odds_to_lay}-{self.max_odds_to_lay}")
            
            # Try expanding the odds range slightly
            expanded_eligible = []
            for horse in top_half:
                odds = horse['best_lay_price']
                if (self.min_odds_to_lay - 0.5) <= odds <= (self.max_odds_to_lay + 1.0):
                    expanded_eligible.append(horse)
            
            if len(expanded_eligible) >= 2:
                logger.info(f"Expanded range found {len(expanded_eligible)} horses")
                eligible_horses = expanded_eligible
            else:
                logger.info("Not enough horses even with expanded range - skipping race")
                return None
        
        if not eligible_horses:
            logger.info(f"No eligible horses in top half (odds range: {self.min_odds_to_lay}-{self.max_odds_to_lay})")
            return None
        
        # Create strategy decision
        strategy_decision = {
            'venue': venue,
            'race_number': race_number,
            'race_time': race_data['race_time'],
            'total_horses': total_horses,
            'top_half_count': top_half_count,
            'eligible_horses': len(eligible_horses),
            'odds_std': round(odds_std, 2),
            'horses_to_lay': eligible_horses,
            'strategy': 'top_half_lay',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Strategy decision: {len(eligible_horses)} horses to lay, std: {odds_std:.2f}")
        
        return strategy_decision
    
    def store_test_result(self, result: Dict):
        """Store test result in database"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS top_half_test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venue TEXT NOT NULL,
                    race_number INTEGER NOT NULL,
                    race_time TEXT,
                    total_horses INTEGER,
                    top_half_count INTEGER,
                    eligible_horses INTEGER,
                    odds_std REAL,
                    strategy TEXT,
                    timestamp DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert result
            cursor.execute('''
                INSERT INTO top_half_test_results 
                (venue, race_number, race_time, total_horses, top_half_count, 
                 eligible_horses, odds_std, strategy, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result['venue'],
                result['race_number'],
                result['race_time'],
                result['total_horses'],
                result['top_half_count'],
                result['eligible_horses'],
                result['odds_std'],
                result['strategy'],
                result['timestamp']
            ))
            
            # Store individual horse decisions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS top_half_horse_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_result_id INTEGER,
                    selection_id INTEGER,
                    runner_name TEXT,
                    odds REAL,
                    size REAL,
                    decision TEXT,
                    FOREIGN KEY (test_result_id) REFERENCES top_half_test_results (id)
                )
            ''')
            
            # Get the test result ID
            test_result_id = cursor.lastrowid
            
            # Insert horse decisions
            for horse in result['horses_to_lay']:
                cursor.execute('''
                    INSERT INTO top_half_horse_decisions 
                    (test_result_id, selection_id, runner_name, odds, size, decision)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    test_result_id,
                    horse['selection_id'],
                    horse['runner_name'],
                    horse['best_lay_price'],
                    horse['size'],
                    'LAY'
                ))
            
            conn.commit()
            logger.info(f"Stored test result for {result['venue']} R{result['race_number']}")
            
        except Exception as e:
            logger.error(f"Error storing test result: {str(e)}")
        finally:
            conn.close()
    
    def run_live_test(self):
        """Run live testing on current races"""
        logger.info("Starting live top-half strategy testing...")
        
        # Get current races
        races = self.get_current_races()
        if not races:
            logger.info("No races found for testing")
            return
        
        logger.info(f"Found {len(races)} races to test")
        
        for race in races:
            try:
                # Analyze race with strategy
                result = self.analyze_race_with_strategy(race)
                
                if result:
                    # Store the result
                    self.store_test_result(result)
                    
                    # Log the decision
                    logger.info(f"✅ {result['venue']} R{result['race_number']}: "
                              f"{result['eligible_horses']} horses to lay, "
                              f"std: {result['odds_std']}")
                    
                    # Show horses to lay
                    for horse in result['horses_to_lay']:
                        logger.info(f"  🐎 {horse['runner_name']} @ {horse['best_lay_price']:.2f}")
                
                else:
                    logger.info(f"❌ {race['venue']} R{race['race_number']}: No strategy decision")
                
                # Wait between races
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error testing race {race['venue']} R{race['race_number']}: {str(e)}")
    
    def get_test_summary(self) -> Dict:
        """Get summary of test results"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_tests,
                    COUNT(CASE WHEN eligible_horses > 0 THEN 1 END) as successful_tests,
                    AVG(odds_std) as avg_std,
                    AVG(eligible_horses) as avg_horses,
                    SUM(eligible_horses) as total_horses_to_lay
                FROM top_half_test_results
            ''')
            
            result = cursor.fetchone()
            
            return {
                'total_tests': result[0] or 0,
                'successful_tests': result[1] or 0,
                'avg_std': round(result[2] or 0, 2),
                'avg_horses': round(result[3] or 0, 2),
                'total_horses_to_lay': result[4] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting test summary: {str(e)}")
            return {}
        finally:
            conn.close()


def main():
    """Main function to run live testing"""
    # Realistic timing: Monitor 10 minutes ahead, but only bet 2 minutes before to 2 minutes after
    # Accounts for races starting late and betting being available past start time
    tester = LiveTopHalfTester(
        max_minutes_ahead=10,  # Look up to 10 minutes ahead
        min_minutes_before=-3,  # Allow betting up to 3 minutes after start time
        betting_window_start=2,  # Start betting 2 minutes before race
        betting_window_end=-2,   # Stop betting 2 minutes after race
        max_odds_to_lay=8.0,     # Don't lay above 8.0 odds (reasonable limit)
        min_odds_to_lay=2.5      # Don't lay below 2.5 odds (avoid favorites)
    )
    
    try:
        # Run live test
        tester.run_live_test()
        
        # Get summary
        summary = tester.get_test_summary()
        logger.info(f"Test Summary: {summary}")
        
    except KeyboardInterrupt:
        logger.info("Testing stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")


if __name__ == "__main__":
    main()
