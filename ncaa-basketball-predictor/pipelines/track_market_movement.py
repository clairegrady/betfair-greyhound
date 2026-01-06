"""
Market Movement Tracker - Enterprise Grade

Tracks odds movements from The Odds API:
- Historical odds storage
- Line movement detection  
- Sharp money indicators
- Betting percentage tracking
- Steam move detection

Design Principles:
- Scheduled polling (multiple times per day)
- Efficient storage
- Movement analysis
- Alert triggers
- Comprehensive logging
"""

import requests
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from tqdm import tqdm
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


class MarketMovementTracker:
    """Tracks odds movements for NCAA basketball"""
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        api_key: Optional[str] = None
    ):
        self.db_path = db_path
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        self.conn = None
        
        if not self.api_key:
            raise ValueError("Odds API key required. Set ODDS_API_KEY environment variable.")
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def create_odds_tables(self):
        """Create comprehensive odds tracking tables"""
        cursor = self.conn.cursor()
        
        # Historical odds snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_history (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                market_type TEXT NOT NULL,  -- h2h, spreads, totals
                home_odds FLOAT,
                away_odds FLOAT,
                home_spread FLOAT,
                spread_odds FLOAT,
                total_points FLOAT,
                over_odds FLOAT,
                under_odds FLOAT,
                snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)
        
        # Create index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_odds_game_time 
            ON odds_history(game_id, snapshot_time)
        """)
        
        # Line movements (calculated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS line_movements (
                movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                market_type TEXT NOT NULL,
                previous_value FLOAT NOT NULL,
                new_value FLOAT NOT NULL,
                movement_size FLOAT NOT NULL,
                movement_pct FLOAT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                movement_type TEXT,  -- STEAM, SHARP, REVERSE, NORMAL
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)
        
        # Market consensus (aggregated across bookmakers)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_consensus (
                consensus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                avg_home_odds FLOAT,
                avg_away_odds FLOAT,
                avg_spread FLOAT,
                avg_total FLOAT,
                num_bookmakers INTEGER,
                snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)
        
        self.conn.commit()
        logger.info("✅ Odds tracking tables created/verified")
    
    def fetch_current_odds(self) -> List[Dict]:
        """Fetch current odds from The Odds API"""
        url = f"{ODDS_API_BASE}/sports/basketball_ncaab/odds"
        
        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'oddsFormat': 'american'
        }
        
        try:
            logger.info("📡 Fetching odds from The Odds API...")
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Fetched odds for {len(data)} games")
                
                # Log API usage
                remaining = response.headers.get('x-requests-remaining')
                used = response.headers.get('x-requests-used')
                if remaining:
                    logger.info(f"📊 API Usage: {used} used, {remaining} remaining")
                
                return data
            else:
                logger.error(f"❌ API returned status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching odds: {e}")
            return []
    
    def store_odds_snapshot(self, games_odds: List[Dict]) -> int:
        """Store current odds snapshot"""
        cursor = self.conn.cursor()
        inserted = 0
        snapshot_time = datetime.now()
        
        for game in games_odds:
            game_id = game.get('id')
            
            if not game.get('bookmakers'):
                continue
            
            for bookmaker in game['bookmakers']:
                bookmaker_name = bookmaker.get('title')
                
                for market in bookmaker.get('markets', []):
                    market_type = market.get('key')  # h2h, spreads, totals
                    
                    try:
                        if market_type == 'h2h':
                            # Moneyline odds
                            outcomes = {o['name']: o['price'] for o in market.get('outcomes', [])}
                            home_team = game.get('home_team')
                            away_team = game.get('away_team')
                            
                            cursor.execute("""
                                INSERT INTO odds_history (
                                    game_id, bookmaker, market_type,
                                    home_odds, away_odds, snapshot_time
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                game_id, bookmaker_name, market_type,
                                outcomes.get(home_team),
                                outcomes.get(away_team),
                                snapshot_time
                            ))
                            inserted += 1
                            
                        elif market_type == 'spreads':
                            # Spread odds
                            for outcome in market.get('outcomes', []):
                                if outcome['name'] == game.get('home_team'):
                                    cursor.execute("""
                                        INSERT INTO odds_history (
                                            game_id, bookmaker, market_type,
                                            home_spread, spread_odds, snapshot_time
                                        ) VALUES (?, ?, ?, ?, ?, ?)
                                    """, (
                                        game_id, bookmaker_name, market_type,
                                        outcome.get('point'),
                                        outcome.get('price'),
                                        snapshot_time
                                    ))
                                    inserted += 1
                                    break
                                    
                        elif market_type == 'totals':
                            # Over/Under
                            outcomes = {o['name']: (o.get('point'), o.get('price')) 
                                       for o in market.get('outcomes', [])}
                            
                            over_data = outcomes.get('Over', (None, None))
                            under_data = outcomes.get('Under', (None, None))
                            
                            cursor.execute("""
                                INSERT INTO odds_history (
                                    game_id, bookmaker, market_type,
                                    total_points, over_odds, under_odds,
                                    snapshot_time
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                game_id, bookmaker_name, market_type,
                                over_data[0],  # total points
                                over_data[1],  # over odds
                                under_data[1],  # under odds
                                snapshot_time
                            ))
                            inserted += 1
                            
                    except Exception as e:
                        logger.debug(f"Error storing odds for {game_id}/{bookmaker_name}: {e}")
                        continue
        
        self.conn.commit()
        logger.info(f"✅ Stored {inserted} odds snapshots")
        return inserted
    
    def detect_line_movements(self, lookback_hours: int = 24) -> int:
        """Detect significant line movements"""
        cursor = self.conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        # Get games with recent odds
        query = """
            SELECT DISTINCT game_id, bookmaker, market_type
            FROM odds_history
            WHERE snapshot_time >= ?
            ORDER BY game_id, bookmaker, market_type
        """
        
        games_markets = cursor.execute(query, (cutoff_time,)).fetchall()
        movements_detected = 0
        
        for game_id, bookmaker, market_type in games_markets:
            try:
                # Get last two snapshots
                snapshots = cursor.execute("""
                    SELECT home_odds, away_odds, home_spread, total_points, snapshot_time
                    FROM odds_history
                    WHERE game_id = ? AND bookmaker = ? AND market_type = ?
                    ORDER BY snapshot_time DESC
                    LIMIT 2
                """, (game_id, bookmaker, market_type)).fetchall()
                
                if len(snapshots) < 2:
                    continue
                
                current, previous = snapshots[0], snapshots[1]
                
                # Check for movements based on market type
                if market_type == 'h2h' and current[0] and previous[0]:
                    # Moneyline movement
                    home_movement = abs(current[0] - previous[0])
                    if home_movement >= 20:  # Significant if 20+ points
                        movement_pct = (home_movement / abs(previous[0])) * 100
                        movement_type = self._classify_movement(home_movement, movement_pct)
                        
                        cursor.execute("""
                            INSERT INTO line_movements (
                                game_id, bookmaker, market_type,
                                previous_value, new_value, movement_size,
                                movement_pct, movement_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            game_id, bookmaker, market_type,
                            previous[0], current[0], home_movement,
                            movement_pct, movement_type
                        ))
                        movements_detected += 1
                        
                elif market_type == 'spreads' and current[2] and previous[2]:
                    # Spread movement
                    spread_movement = abs(current[2] - previous[2])
                    if spread_movement >= 1.0:  # Significant if 1+ point
                        movement_pct = (spread_movement / abs(previous[2])) * 100 if previous[2] != 0 else 0
                        movement_type = self._classify_movement(spread_movement, movement_pct)
                        
                        cursor.execute("""
                            INSERT INTO line_movements (
                                game_id, bookmaker, market_type,
                                previous_value, new_value, movement_size,
                                movement_pct, movement_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            game_id, bookmaker, market_type,
                            previous[2], current[2], spread_movement,
                            movement_pct, movement_type
                        ))
                        movements_detected += 1
                        
            except Exception as e:
                logger.debug(f"Error detecting movement for {game_id}: {e}")
                continue
        
        self.conn.commit()
        logger.info(f"✅ Detected {movements_detected} line movements")
        return movements_detected
    
    def _classify_movement(self, movement_size: float, movement_pct: float) -> str:
        """Classify type of line movement"""
        # STEAM: Large, rapid movement (>10%)
        if movement_pct > 10:
            return 'STEAM'
        # SHARP: Moderate but significant (5-10%)
        elif movement_pct > 5:
            return 'SHARP'
        # NORMAL: Small adjustments
        else:
            return 'NORMAL'
    
    def calculate_consensus(self, games_odds: List[Dict]) -> int:
        """Calculate market consensus across bookmakers"""
        cursor = self.conn.cursor()
        inserted = 0
        snapshot_time = datetime.now()
        
        # Group by game
        games_dict = {}
        for game in games_odds:
            game_id = game.get('id')
            if game_id not in games_dict:
                games_dict[game_id] = []
            games_dict[game_id].append(game)
        
        for game_id, game_list in games_dict.items():
            try:
                home_odds_list = []
                away_odds_list = []
                spread_list = []
                total_list = []
                
                for game in game_list:
                    for bookmaker in game.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                for outcome in market.get('outcomes', []):
                                    if outcome['name'] == game.get('home_team'):
                                        home_odds_list.append(outcome.get('price'))
                                    else:
                                        away_odds_list.append(outcome.get('price'))
                                        
                            elif market['key'] == 'spreads':
                                for outcome in market.get('outcomes', []):
                                    if outcome['name'] == game.get('home_team'):
                                        spread_list.append(outcome.get('point'))
                                        break
                                        
                            elif market['key'] == 'totals':
                                for outcome in market.get('outcomes', []):
                                    if outcome['name'] == 'Over':
                                        total_list.append(outcome.get('point'))
                                        break
                
                if home_odds_list or spread_list or total_list:
                    cursor.execute("""
                        INSERT INTO market_consensus (
                            game_id, avg_home_odds, avg_away_odds,
                            avg_spread, avg_total, num_bookmakers,
                            snapshot_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        sum(home_odds_list) / len(home_odds_list) if home_odds_list else None,
                        sum(away_odds_list) / len(away_odds_list) if away_odds_list else None,
                        sum(spread_list) / len(spread_list) if spread_list else None,
                        sum(total_list) / len(total_list) if total_list else None,
                        len(set(g.get('bookmakers', [{}])[0].get('title') for g in game_list)),
                        snapshot_time
                    ))
                    inserted += 1
                    
            except Exception as e:
                logger.debug(f"Error calculating consensus for {game_id}: {e}")
                continue
        
        self.conn.commit()
        logger.info(f"✅ Calculated consensus for {inserted} games")
        return inserted
    
    def run(self) -> Dict[str, int]:
        """Main execution - fetch, store, analyze"""
        logger.info("Starting Market Movement Tracking")
        
        # Create tables
        self.create_odds_tables()
        
        # Fetch current odds
        games_odds = self.fetch_current_odds()
        
        if not games_odds:
            logger.warning("⚠️  No odds data fetched")
            return {
                'odds_stored': 0,
                'movements_detected': 0,
                'consensus_calculated': 0
            }
        
        # Store snapshot
        odds_stored = self.store_odds_snapshot(games_odds)
        
        # Detect movements
        movements_detected = self.detect_line_movements(lookback_hours=24)
        
        # Calculate consensus
        consensus_calculated = self.calculate_consensus(games_odds)
        
        results = {
            'games_tracked': len(games_odds),
            'odds_stored': odds_stored,
            'movements_detected': movements_detected,
            'consensus_calculated': consensus_calculated
        }
        
        logger.info(f"✅ Market tracking complete: {results}")
        return results


def main():
    """Entry point"""
    # Load environment variables
    load_dotenv(Path(__file__).parent.parent / 'config.env')
    
    print("\n" + "="*70)
    print("📈 NCAA BASKETBALL - MARKET MOVEMENT TRACKER")
    print("="*70)
    
    try:
        with MarketMovementTracker() as tracker:
            results = tracker.run()
        
        print("\n" + "="*70)
        print("📊 RESULTS")
        print("="*70)
        print(f"🎮 Games Tracked: {results['games_tracked']}")
        print(f"💾 Odds Stored: {results['odds_stored']}")
        print(f"📊 Movements Detected: {results['movements_detected']}")
        print(f"🎯 Consensus Calculated: {results['consensus_calculated']}")
        print("="*70)
        
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("💡 Set ODDS_API_KEY in config.env")


if __name__ == "__main__":
    main()

