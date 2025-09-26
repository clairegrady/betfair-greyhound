#!/usr/bin/env python3
"""
Betfair Results Fetcher
Gets horse racing results from Betfair API and stores them in the database
"""

import requests
import sqlite3
import pandas as pd
from datetime import datetime, date
import time
import logging
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BetfairResultsFetcher:
    def __init__(self, db_path: str = "betting_simulation.sqlite", api_base_url: str = "http://localhost:5173"):
        self.db_path = db_path
        self.api_base_url = api_base_url.rstrip('/')
        
        # Initialize database
        self.init_database()
    
    def init_database(self):
        """Initialize database tables for storing results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create race results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS race_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_date DATE,
                venue TEXT,
                race_number INTEGER,
                race_name TEXT,
                race_time TEXT,
                distance TEXT,
                track_condition TEXT,
                weather TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create horse results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS horse_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id INTEGER,
                finishing_position INTEGER,
                horse_name TEXT,
                starting_price REAL,
                jockey TEXT,
                trainer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (race_id) REFERENCES race_results (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    def get_settled_markets(self, market_ids: List[str]) -> List[Dict]:
        """Get settled market results from Betfair API"""
        try:
            # Call the new results API endpoint
            url = f"{self.api_base_url}/api/results/settled"
            
            logger.info(f"🌐 Fetching settled results for {len(market_ids)} markets")
            response = requests.post(url, json=market_ids, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get('settledMarkets', [])
            
        except Exception as e:
            logger.error(f"❌ Error fetching settled markets: {e}")
            return []
    
    def parse_market_results(self, market_data: Dict) -> Optional[Dict]:
        """Parse market results from Betfair API response"""
        try:
            market_id = market_data.get('marketId')
            runners = market_data.get('runners', [])
            
            if not runners:
                logger.warning(f"⚠️ No runners data for market {market_id}")
                return None
            
            # Parse settled market results
            horses = []
            for runner in runners:
                selection_id = runner.get('selectionId')
                status = runner.get('status', '')
                adjustment_factor = runner.get('adjustmentFactor', 0)
                
                # Determine finishing position based on status
                if status == 'WINNER':
                    finishing_position = 1
                elif status == 'LOSER':
                    finishing_position = 2  # All losers are position 2+
                else:
                    finishing_position = 0  # REMOVED or other status
                
                horses.append({
                    'selection_id': selection_id,
                    'finishing_position': finishing_position,
                    'status': status,
                    'adjustment_factor': adjustment_factor
                })
            
            # Sort by finishing position (winner first)
            horses.sort(key=lambda x: x['finishing_position'] if x['finishing_position'] > 0 else 999)
            
            # Assign proper positions
            position = 1
            for horse in horses:
                if horse['finishing_position'] > 0:
                    horse['finishing_position'] = position
                    position += 1
            
            return {
                'market_id': market_id,
                'horses': horses
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing market results: {e}")
            return None
    
    def store_results(self, results: List[Dict]) -> int:
        """Store race results in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stored_count = 0
        
        try:
            for result in results:
                market_id = result.get('market_id')
                horses = result.get('horses', [])
                
                # Get race info from simulation results
                cursor.execute('''
                    SELECT DISTINCT venue, race_number, race_date 
                    FROM simulation_results 
                    WHERE market_id = ?
                    LIMIT 1
                ''', (market_id,))
                
                race_info = cursor.fetchone()
                if not race_info:
                    logger.warning(f"⚠️ No race info found for market {market_id}")
                    continue
                
                venue, race_number, race_date = race_info
                
                # Insert race data
                cursor.execute('''
                    INSERT OR REPLACE INTO race_results 
                    (race_date, venue, race_number, race_name, race_time, distance, track_condition, weather)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    race_date,
                    venue,
                    race_number,
                    f"Race {race_number}",
                    '',
                    '',
                    '',
                    ''
                ))
                
                race_id = cursor.lastrowid
                
                # Insert horse data
                for horse in horses:
                    cursor.execute('''
                        INSERT OR REPLACE INTO horse_results 
                        (race_id, finishing_position, horse_name, starting_price, jockey, trainer)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        race_id,
                        horse.get('finishing_position', 0),
                        f"Horse {horse.get('selection_id', '')}",
                        horse.get('adjustment_factor', 0.0),
                        '',
                        ''
                    ))
                
                stored_count += 1
            
            conn.commit()
            return stored_count
            
        except Exception as e:
            logger.error(f"❌ Error storing results: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    def fetch_results(self, market_ids: List[str]) -> List[Dict]:
        """Main method to fetch and store results from Betfair API"""
        try:
            logger.info("🚀 Starting Betfair results fetching...")
            
            if not market_ids:
                logger.warning("⚠️ No market IDs provided")
                return []
            
            # Get settled market data
            settled_markets = self.get_settled_markets(market_ids)
            if not settled_markets:
                logger.warning("⚠️ No settled markets found")
                return []
            
            # Parse results
            results = []
            for market_data in settled_markets:
                result = self.parse_market_results(market_data)
                if result:
                    results.append(result)
            
            logger.info(f"📊 Found {len(results)} race results")
            
            # Store results in database
            stored_count = self.store_results(results)
            logger.info(f"💾 Stored {stored_count} race results")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in fetch_results: {e}")
            return []
    
    def get_results_for_simulation(self, venue: str, race_number: int, race_date: str = None) -> List[Dict]:
        """Get results for a specific race to update simulation results"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT hr.finishing_position, hr.horse_name, hr.starting_price
            FROM horse_results hr
            JOIN race_results rr ON hr.race_id = rr.id
            WHERE rr.venue = ? AND rr.race_number = ?
        """
        
        if race_date:
            query += " AND rr.race_date = ?"
            params = (venue, race_number, race_date)
        else:
            params = (venue, race_number)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df.to_dict('records')

def main():
    """Test the results fetcher"""
    fetcher = BetfairResultsFetcher()
    
    # Test with actual market IDs from simulation
    test_market_ids = ["1.248194824", "1.248195256"]  # Real market IDs from simulation
    
    results = fetcher.fetch_results(test_market_ids)
    print(f"Fetched {len(results)} results")

if __name__ == "__main__":
    main()
