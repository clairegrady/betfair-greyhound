"""
Lay Betting Automation - Connects lay betting strategy to PlaceOrder API
"""
import requests
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from shared_lay_betting import LayBettingStrategy, LayBettingResults
import logging
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingAutomation:
    """
    Automates lay betting by connecting strategy to PlaceOrder API
    """
    
    def __init__(self, db_path: str, api_base_url: str, std_threshold: float = 2.5, max_odds: float = 20.0,
                 min_minutes_before_race: int = 10):
        self.db_path = db_path
        self.betting_db_path = '/Users/clairegrady/RiderProjects/betfair/data-model/betting_history.sqlite'
        self.api_base_url = api_base_url.rstrip('/')
        self.strategy = LayBettingStrategy(std_threshold, max_odds)
        
        # Set your local timezone (AEST/AEDT)
        self.local_timezone = pytz.timezone('Australia/Sydney')
        self.place_order_url = f"{self.api_base_url}/api/placeorder"
    
    def calculate_stake(self, odds: float) -> float:
        """Calculate stake based on odds: $2 for odds <= 15, $1 for odds 16-30"""
        if odds <= 15:
            return 2.0
        elif odds <= 30:
            return 1.0
        else:
            return 1.0  # Default for odds > 30
    
    def __init__(self, db_path: str, api_base_url: str, std_threshold: float = 2.5, max_odds: float = 20.0,
                 min_minutes_before_race: int = 10):
        self.db_path = db_path
        self.betting_db_path = '/Users/clairegrady/RiderProjects/betfair/data-model/betting_history.sqlite'
        self.api_base_url = api_base_url.rstrip('/')
        self.strategy = LayBettingStrategy(std_threshold, max_odds)
        
        # Set your local timezone (AEST/AEDT)
        self.local_timezone = pytz.timezone('Australia/Sydney')
        self.place_order_url = f"{self.api_base_url}/api/placeorder"
        self.min_minutes_before_race = min_minutes_before_race
        self.placed_bets = set()  # Track placed bets to prevent duplicates
        self.race_splits_cache = {}  # Cache for top/bottom splits by market
        self._create_race_times_table()
        self._create_betting_history_table()
    
    def utc_to_local_time(self, utc_date: str, utc_time: str) -> str:
        """
        Convert UTC date and time to local time for display
        
        Args:
            utc_date: Date in YYYY-MM-DD format
            utc_time: Time in HH:MM format
            
        Returns:
            Local time string in HH:MM format
        """
        try:
            # Create UTC datetime
            utc_datetime_str = f"{utc_date} {utc_time}"
            utc_datetime = datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M')
            utc_datetime = pytz.UTC.localize(utc_datetime)
            
            # Convert to local timezone
            local_datetime = utc_datetime.astimezone(self.local_timezone)
            
            return local_datetime.strftime('%H:%M')
        except Exception as e:
            logger.warning(f"Error converting UTC time {utc_date} {utc_time} to local: {e}")
            return utc_time  # Fallback to UTC time
    
    def _create_race_times_table(self):
        """Create race_times table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS race_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venue TEXT NOT NULL,
                race_number INTEGER NOT NULL,
                race_time TEXT NOT NULL,
                race_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(venue, race_number, race_date)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Race times table created/verified")
    
    def _create_betting_history_table(self):
        """Create betting_history table to track placed bets"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS betting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                selection_id INTEGER NOT NULL,
                horse_name TEXT,
                lay_price REAL,
                stake REAL,
                bet_id TEXT,
                bet_status TEXT DEFAULT 'PENDING',
                matched_amount REAL DEFAULT 0.0,
                placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(market_id, selection_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Betting history table created/verified")
    
    def update_race_times_from_csv(self, csv_file: str):
        """Update race times from CSV file (from race_times_scraper.py)"""
        try:
            df = pd.read_csv(csv_file)
            conn = sqlite3.connect(self.db_path)
            
            for _, row in df.iterrows():
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO race_times 
                    (venue, race_number, race_time, race_date, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (row['venue'], row['race_number'], row['race_time_24h'], row['date']))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated {len(df)} race times from {csv_file}")
            
        except Exception as e:
            logger.error(f"Error updating race times from CSV: {e}")
    
    def get_races_within_betting_window(self, max_minutes_ahead: int = 60):
        """
        Get races that are within the betting window (10 minutes or less before start)
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get races from race_times table that are starting soon
        query = """
        SELECT DISTINCT
            rt.venue,
            rt.race_number,
            rt.race_time,
            rt.race_date,
            h.EventName,
            h.MarketName,
            h.MarketId,
            COALESCE(m.OpenDate, '') as OpenDate,
            datetime('now', 'localtime') as current_local_time,
            (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 as minutes_until_start
        FROM race_times rt
        JOIN HorseMarketBook h ON ((h.EventName LIKE '%' || rt.venue || '%' 
            AND h.EventName LIKE '%' || strftime('%d', rt.race_date) || CASE 
                WHEN strftime('%d', rt.race_date) IN ('01', '21', '31') THEN 'st'
                WHEN strftime('%d', rt.race_date) IN ('02', '22') THEN 'nd'
                WHEN strftime('%d', rt.race_date) IN ('03', '23') THEN 'rd'
                ELSE 'th'
            END || '%')
            OR (rt.venue = "Le Lion D''angers" AND h.EventName LIKE '%Le Lion D''angers%'))
        LEFT JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
        WHERE (h.MarketName LIKE 'R%' AND CAST(SUBSTR(h.MarketName, 2) AS INTEGER) = rt.race_number)
           OR (rt.venue = "Le Lion D''angers" AND h.EventName LIKE '%Le Lion D''angers%' 
               AND h.MarketName = (SELECT MIN(MarketName) FROM HorseMarketBook h2 
                                  WHERE h2.EventName = h.EventName AND h2.MarketName != 'To Be Placed'))
        AND h.MarketName != 'To Be Placed'
            AND rt.race_date = date('now', 'localtime')
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 <= ?
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 >= ?
        GROUP BY rt.venue, rt.race_number, rt.race_time, rt.race_date
        ORDER BY rt.race_time
        """
        
        races_df = pd.read_sql_query(query, conn, params=[max_minutes_ahead, self.min_minutes_before_race])
        conn.close()
        
        logger.info(f"Found {len(races_df)} races within betting window ({self.min_minutes_before_race}-{max_minutes_ahead} minutes)")
        
        # Debug: Print all races found
        if len(races_df) > 0:
            logger.info("DEBUG: All races found:")
            for _, race in races_df.iterrows():
                logger.info(f"  {race['venue']} R{race['race_number']}: {race['minutes_until_start']:.1f} minutes away")
        
        if len(races_df) > 0:
            for _, race in races_df.head(3).iterrows():
                minutes_until = race['minutes_until_start']
                # Times are already in AEST, no conversion needed
                local_time = f"{race['race_date']} {race['race_time']}"
                if minutes_until < 0:
                    logger.info(f"  {race['venue']} R{race['race_number']}: Started {abs(minutes_until):.1f} minutes ago (was at {local_time})")
                else:
                    logger.info(f"  {race['venue']} R{race['race_number']}: Starts in {minutes_until:.1f} minutes (at {local_time})")
        
        return races_df
    
    def get_live_races(self, hours_ahead: int = 2, demo_mode: bool = False):
        """
        Get races that are starting soon (markets opening within the next few hours)
        
        Note: We use market OpenDate as a proxy for race start time.
        Most betting happens in the final minutes before race start.
        """
        conn = sqlite3.connect(self.db_path)
        
        if demo_mode:
            # Get any races from today (for testing)
            query = """
            SELECT DISTINCT 
                h.EventName,
                h.MarketName,
                h.MarketId,
                m.OpenDate,
                datetime('now') as current_time,
                (julianday(m.OpenDate) - julianday('now')) * 24 as hours_until_start
            FROM HorseMarketBook h
            JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
            WHERE h.MarketName != 'To Be Placed'
            AND m.OpenDate IS NOT NULL
            AND date(m.OpenDate) = date('now')
            ORDER BY m.OpenDate
            """
        else:
            # Get races with markets that are open and likely to have races starting soon
            # Since OpenDate is when the venue's markets open (not individual race times),
            # we'll look for venues where markets opened recently and are likely still active
            query = """
            SELECT DISTINCT 
                h.EventName,
                h.MarketName,
                h.MarketId,
                m.OpenDate,
                datetime('now') as current_time,
                (julianday('now') - julianday(m.OpenDate)) * 24 as hours_since_market_open
            FROM HorseMarketBook h
            JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
            WHERE h.MarketName != 'To Be Placed'
            AND m.OpenDate IS NOT NULL
            AND date(m.OpenDate) = date('now')
            AND (julianday('now') - julianday(m.OpenDate)) * 24 <= ?
            AND (julianday('now') - julianday(m.OpenDate)) * 24 >= -2
            ORDER BY m.OpenDate
            """.format(hours_ahead)
        
        races_df = pd.read_sql_query(query, conn, params=[hours_ahead] if not demo_mode else [])
        conn.close()
        
        if demo_mode:
            logger.info(f"Found {len(races_df)} races for today (demo mode)")
        else:
            logger.info(f"Found {len(races_df)} races with active markets")
            if len(races_df) > 0:
                logger.info("Note: Markets are open, races may be starting soon")
                # Show timing info
                for _, race in races_df.head(3).iterrows():
                    hours_since = race['hours_since_market_open']
                    if hours_since < 0:
                        logger.info(f"  {race['EventName']} - {race['MarketName']}: Market opens in {abs(hours_since):.1f} hours")
                    else:
                        logger.info(f"  {race['EventName']} - {race['MarketName']}: Market opened {hours_since:.1f} hours ago")
        
        return races_df
    
    def get_race_odds(self, market_id: str):
        """Get all lay odds for a specific race, with best odds per horse"""
        # First try to get odds from CurrentOdds table (real-time data)
        betting_conn = sqlite3.connect(self.betting_db_path)
        
        current_odds_query = """
        SELECT 
            SelectionId,
            COALESCE(RunnerName, 'Horse ' || SelectionId) as runner_name,
            MIN(Price) as best_lay_price,
            MAX(Size) as max_available_size,
            LastPriceTraded,
            TotalMatched,
            0 as cloth_number
        FROM CurrentOdds
        WHERE MarketId = ?
        GROUP BY SelectionId
        ORDER BY best_lay_price
        """
        
        result_df = pd.read_sql_query(current_odds_query, betting_conn, params=[market_id])
        betting_conn.close()
        
        # If we have current odds data, use it
        if not result_df.empty:
            logger.info(f"📊 Using CurrentOdds data for market {market_id} ({len(result_df)} horses)")
            return result_df
        
        # No CurrentOdds data - try to refresh and retry once
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
                    return result_df
            else:
                logger.warning(f"⚠️ Refresh failed with status {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Refresh failed: {e}")
        
        # Fallback to main database if still no current odds available
        logger.warning(f"⚠️ No CurrentOdds data after refresh for market {market_id}, falling back to main database")
        conn = sqlite3.connect(self.db_path)
        
        # Get ALL horses with their best lay odds (no filtering by max_odds yet)
        # For lay betting, we want the LOWEST lay price available (best odds for the layer)
        all_horses_query = """
        SELECT 
            h.SelectionId,
            CASE 
                WHEN h.RUNNER_NAME IS NOT NULL AND h.RUNNER_NAME != '' THEN h.RUNNER_NAME
                WHEN h.CLOTH_NUMBER IS NOT NULL AND h.CLOTH_NUMBER > 0 THEN 'Horse ' || h.CLOTH_NUMBER || ' (' || h.SelectionId || ')'
                ELSE 'Horse ' || h.SelectionId
            END as runner_name,
            COALESCE(h.CLOTH_NUMBER, 0) as cloth_number,
            MIN(l.Price) as best_lay_price,
            MAX(l.Size) as max_available_size,
            l.LastPriceTraded,
            l.TotalMatched
        FROM HorseMarketBook h
        LEFT JOIN MarketBookLayPrices l ON h.SelectionId = l.SelectionId AND h.MarketId = l.MarketId
        WHERE h.MarketId = ?
        GROUP BY h.SelectionId, h.RUNNER_NAME, h.CLOTH_NUMBER
        ORDER BY best_lay_price
        """
        
        result_df = pd.read_sql_query(all_horses_query, conn, params=[market_id])
        conn.close()
        
        if not result_df.empty:
            logger.info(f"📊 Using fallback data for market {market_id} ({len(result_df)} horses)")
            # Log sample odds to check for staleness
            if len(result_df) > 0:
                sample_odds = result_df['best_lay_price'].head(3).tolist()
                logger.info(f"📊 Sample fallback odds: {sample_odds}")
        else:
            logger.warning(f"⚠️ No odds data found for market {market_id} in either database")
        
        return result_df
    
    def get_or_create_race_split(self, market_id: str, race_odds: pd.DataFrame):
        """
        Get cached top/bottom split or create it on first call
        This ensures the split doesn't change with real-time odds fluctuations
        """
        cache_key = f"{market_id}_split"
        
        # Check if we already have a cached split for this market
        if cache_key in self.race_splits_cache:
            logger.info(f"📊 Using cached top/bottom split for market {market_id}")
            return self.race_splits_cache[cache_key]
        
        # First call - calculate and cache the split
        logger.info(f"📊 Calculating top/bottom split for market {market_id} (first call)")
        
        # Try to get BSP projections from the dedicated BSP table
        bsp_data = self._get_bsp_projections(market_id)
        
        if bsp_data is not None and len(bsp_data) >= 4:
            # Use BSP projections for stable classification
            logger.info(f"📊 Using BSP projections for stable classification ({len(bsp_data)} horses)")
            horses_with_odds = bsp_data.sort_values('Average')
        else:
            # No BSP data available - retry once more
            logger.warning(f"⚠️ BSP projections not available, retrying...")
            bsp_data_retry = self._get_bsp_projections(market_id)
            
            if bsp_data_retry is not None and len(bsp_data_retry) >= 4:
                logger.info(f"📊 BSP projections found on retry ({len(bsp_data_retry)} horses)")
                horses_with_odds = bsp_data_retry.sort_values('Average')
            else:
                # No BSP data available after retry - do not bet
                logger.warning(f"❌ No BSP projections available after retry - skipping race to prevent betting on favorites")
                return None
        
        # Calculate top half (favorites) and bottom half (longshots)
        top_half_count = len(horses_with_odds) // 2
        top_half_ids = set(horses_with_odds.head(top_half_count)['SelectionId'].tolist())
        bottom_half_ids = set(horses_with_odds.iloc[top_half_count:]['SelectionId'].tolist())
        
        # Cache the split
        split_data = {
            'top_half_ids': top_half_ids,
            'bottom_half_ids': bottom_half_ids,
            'top_half_count': top_half_count,
            'total_horses': len(horses_with_odds)
        }
        self.race_splits_cache[cache_key] = split_data
        
        logger.info(f"📊 Cached split: {len(top_half_ids)} favorites, {len(bottom_half_ids)} longshots")
        return split_data
    
    def _get_bsp_projections(self, market_id: str):
        """
        Get BSP projections from the dedicated BSP table
        """
        try:
            conn = sqlite3.connect(self.betting_db_path)
            query = """
            SELECT 
                SelectionId,
                RunnerName,
                NearPrice,
                FarPrice,
                CASE 
                    WHEN Average IS NOT NULL THEN Average
                    WHEN NearPrice IS NOT NULL AND FarPrice IS NOT NULL THEN (NearPrice + FarPrice) / 2.0
                    WHEN NearPrice IS NOT NULL THEN NearPrice
                    WHEN FarPrice IS NOT NULL THEN FarPrice
                    ELSE NULL
                END as Average
            FROM BSPProjections
            WHERE MarketId = ?
            AND (NearPrice IS NOT NULL OR FarPrice IS NOT NULL)
            ORDER BY CASE 
                WHEN Average IS NOT NULL THEN Average
                WHEN NearPrice IS NOT NULL AND FarPrice IS NOT NULL THEN (NearPrice + FarPrice) / 2.0
                WHEN NearPrice IS NOT NULL THEN NearPrice
                WHEN FarPrice IS NOT NULL THEN FarPrice
                ELSE NULL
            END
            """
            df = pd.read_sql_query(query, conn, params=[market_id])
            conn.close()
            return df if len(df) > 0 else None
        except Exception as e:
            logger.warning(f"⚠️ Failed to get BSP projections for market {market_id}: {e}")
            return None
    
    def analyze_race_with_cached_split(self, market_id: str, race_odds: pd.DataFrame):
        """
        Analyze race eligibility using cached top/bottom split
        This prevents the split from changing with real-time odds fluctuations
        """
        # Get or create the cached split
        split_data = self.get_or_create_race_split(market_id, race_odds)
        if not split_data:
            return False, "No cached split available", None
        
        # Filter to only bottom half horses (longshots)
        bottom_half_odds = race_odds[race_odds['SelectionId'].isin(split_data['bottom_half_ids'])]
        
        if len(bottom_half_odds) == 0:
            return False, "No bottom half horses found", None
        
        # Apply max_odds filter to bottom half only
        eligible_horses = bottom_half_odds[bottom_half_odds['best_lay_price'] <= self.strategy.max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No bottom half horses with odds <= {self.strategy.max_odds}:1", None
        
        return True, f"Eligible - {len(eligible_horses)} bottom half horses to lay", eligible_horses
    
    def has_bet_been_placed(self, market_id: str, selection_id: int):
        """Check if a bet has already been placed on this horse in this market"""
        # Check in-memory cache first (fastest)
        bet_key = f"{market_id}_{selection_id}"
        if bet_key in self.placed_bets:
            logger.info(f"🚫 DUPLICATE PREVENTED: Found bet in cache: {bet_key}")
            return True
        
        # Check betting database (where live betting records are stored)
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM betting_history 
            WHERE market_id = ? AND selection_id = ?
        """, (market_id, selection_id))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            logger.info(f"🚫 DUPLICATE PREVENTED: Found existing bet in betting database: {market_id}_{selection_id}")
            # Add to cache for future checks
            self.placed_bets.add(bet_key)
            return True
        
        return False
    
    def load_current_market_bets(self, current_market_id: str):
        """Load current market bets into cache to prevent duplicates"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get all bets for this market
            cursor.execute("SELECT selection_id FROM betting_history WHERE market_id = ?", (current_market_id,))
            current_selections = [row[0] for row in cursor.fetchall()]
            
            # Add current market bets to cache
            for selection_id in current_selections:
                current_key = f"{current_market_id}_{selection_id}"
                self.placed_bets.add(current_key)
            
            logger.info(f"Loaded {len(current_selections)} current market bets into cache")
            
        except Exception as e:
            logger.error(f"Error loading current market bets: {e}")
        finally:
            conn.close()
    
    def clear_old_bets(self, current_market_id: str):
        """Clear old bets from different markets to prevent false duplicates"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get all unique market IDs
            cursor.execute("SELECT DISTINCT market_id FROM betting_history")
            all_markets = [row[0] for row in cursor.fetchall()]
            
            # Remove old markets from cache
            for market_id in all_markets:
                if market_id != current_market_id:
                    # Remove all bets from this old market from cache
                    cursor.execute("SELECT selection_id FROM betting_history WHERE market_id = ?", (market_id,))
                    old_selections = [row[0] for row in cursor.fetchall()]
                    
                    for selection_id in old_selections:
                        old_key = f"{market_id}_{selection_id}"
                        self.placed_bets.discard(old_key)
            
            # Also add current market bets to cache to prevent duplicates within same market
            cursor.execute("SELECT selection_id FROM betting_history WHERE market_id = ?", (current_market_id,))
            current_selections = [row[0] for row in cursor.fetchall()]
            
            for selection_id in current_selections:
                current_key = f"{current_market_id}_{selection_id}"
                self.placed_bets.add(current_key)
            
            logger.info(f"Cleared old bets from cache, added {len(current_selections)} current market bets to cache")
            
        except Exception as e:
            logger.error(f"Error clearing old bets: {e}")
        finally:
            conn.close()
    
    def record_bet_placed(self, market_id: str, selection_id: int, horse_name: str, lay_price: float, stake: float, bet_id: str = None):
        """Record that a bet has been placed with retry logic"""
        import time
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔍 Attempting to connect to database: {self.betting_db_path}")
                conn = sqlite3.connect(self.betting_db_path, timeout=10.0)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO betting_history 
                    (market_id, selection_id, horse_name, lay_price, stake, bet_id, bet_status, matched_amount, placed_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0.0, CURRENT_TIMESTAMP)
                """, (market_id, selection_id, horse_name, lay_price, stake, bet_id))
                
                conn.commit()
                conn.close()
                logger.info(f"Recorded bet: {horse_name} @ {lay_price} in market {market_id} (Status: PENDING)")
                return True
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    logger.error(f"Failed to record bet after {max_retries} attempts: {e}")
                    return False
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to record bet: {e}")
                logger.error(f"❌ Database path: {self.betting_db_path}")
                logger.error(f"❌ Market ID: {market_id}, Selection ID: {selection_id}")
                return False
        
        return False
    
    def check_bet_status(self, market_id: str, selection_id: int):
        """Check if a bet has been matched using Betfair listCurrentOrders API"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get the bet details
            cursor.execute("""
                SELECT bet_id, lay_price, bet_status FROM betting_history 
                WHERE market_id = ? AND selection_id = ?
            """, (market_id, selection_id))
            
            bet_row = cursor.fetchone()
            if not bet_row:
                return "NOT_FOUND", 0.0
            
            bet_id, bet_lay_price, current_status = bet_row
            
            # If we don't have a bet_id, we can't check via API
            if not bet_id:
                logger.warning(f"No bet_id found for selection {selection_id} - cannot check status via API")
                return "UNKNOWN", 0.0
            
            # Use Betfair listCurrentOrders API to check actual bet status
            return self._check_bet_status_via_api(market_id, bet_id)
                
        except Exception as e:
            logger.error(f"Error checking bet status: {e}")
            return "ERROR", 0.0
        finally:
            conn.close()
    
    def _check_bet_status_via_api(self, market_id: str, bet_id: str):
        """Check bet status using backend ManageOrders controller"""
        try:
            # Use the new backend endpoint
            current_orders_url = f"{self.api_base_url}/api/manageorders/current"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.get(
                current_orders_url,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse the response to find our bet
                if 'currentOrders' in result and result['currentOrders']:
                    for order in result['currentOrders']:
                        if order.get('betId') == bet_id:
                            # Check the order status
                            status = order.get('status', 'UNKNOWN')
                            size_matched = float(order.get('sizeMatched', 0))
                            size_remaining = float(order.get('sizeRemaining', 0))
                            
                            if status == 'EXECUTABLE' and size_remaining > 0:
                                return "PENDING", size_matched
                            elif status == 'EXECUTION_COMPLETE' or size_remaining == 0:
                                return "MATCHED", size_matched
                            elif status == 'CANCELLED':
                                return "CANCELLED", size_matched
                            else:
                                return "UNMATCHED", size_matched
                
                # If bet not found in current orders, it might be settled
                logger.info(f"Bet {bet_id} not found in current orders - may be settled")
                return "SETTLED", 0.0
                
            else:
                logger.error(f"Backend API error checking bet status: {response.status_code} - {response.text}")
                return "API_ERROR", 0.0
                
        except Exception as e:
            logger.error(f"Error calling backend ManageOrders API: {e}")
            return "API_ERROR", 0.0
    
    def update_bet_status(self, market_id: str, selection_id: int, new_status: str, matched_amount: float = 0.0):
        """Update the status of a bet"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE betting_history 
                SET bet_status = ?, matched_amount = ?
                WHERE market_id = ? AND selection_id = ?
            """, (new_status, matched_amount, market_id, selection_id))
            
            conn.commit()
            logger.info(f"Updated bet status: {selection_id} -> {new_status} (matched: {matched_amount})")
        except Exception as e:
            logger.error(f"Error updating bet status: {e}")
        finally:
            conn.close()
    
    def check_all_pending_bets(self):
        """Check and update status of all pending bets"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get all pending bets
            cursor.execute("""
                SELECT market_id, selection_id, horse_name, lay_price, bet_status
                FROM betting_history 
                WHERE bet_status = 'PENDING'
                ORDER BY placed_at DESC
            """)
            
            pending_bets = cursor.fetchall()
            logger.info(f"Checking {len(pending_bets)} pending bets...")
            
            for market_id, selection_id, horse_name, lay_price, current_status in pending_bets:
                # Check current status
                status, matched_amount = self.check_bet_status(market_id, selection_id)
                
                if status != current_status:
                    self.update_bet_status(market_id, selection_id, status, matched_amount)
                    logger.info(f"Bet status updated: {horse_name} @ {lay_price} -> {status}")
                else:
                    logger.debug(f"Bet status unchanged: {horse_name} @ {lay_price} -> {status}")
                    
        except Exception as e:
            logger.error(f"Error checking pending bets: {e}")
        finally:
            conn.close()
    
    def check_odds_movement(self, market_id: str, selection_id: int, original_lay_price: float):
        """Check if odds have moved in our favor since bet was placed"""
        try:
            # Use API instead of direct database access
            url = f"{self.api_base_url}/api/odds/current/{market_id}/{selection_id}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                current_lay_price = data.get('bestLayPrice')
                
                if current_lay_price is not None:
                    odds_movement = current_lay_price - original_lay_price
                    
                    # Positive movement = odds went up (good for us)
                    # Negative movement = odds went down (bad for us)
                    logger.info(f"📊 Current odds: {current_lay_price:.2f}, Original: {original_lay_price:.2f}, Movement: {odds_movement:.2f}")
                    return current_lay_price, odds_movement
                else:
                    logger.warning(f"⚠️ No active prices found for {selection_id}")
                    return None, None
            else:
                logger.error(f"❌ API error getting odds: {response.status_code} - {response.text}")
                return None, None
                
        except Exception as e:
            logger.error(f"Error checking odds movement via API: {e}")
            return None, None
    
    def update_bet_odds(self, market_id: str, selection_id: int, bet_id: str, new_odds: float):
        """Update bet odds using backend ManageOrders controller"""
        try:
            # Create update instruction
            update_instruction = {
                "betId": bet_id,
                "newPrice": new_odds
            }
            
            # Use the backend endpoint
            update_url = f"{self.api_base_url}/api/manageorders/update"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                update_url,
                json=[update_instruction],  # Backend expects a list
                headers=headers,
                params={'marketId': market_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully updated bet {bet_id} to {new_odds}: {result}")
                return True
            else:
                logger.error(f"Failed to update bet {bet_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating bet {selection_id}: {e}")
            return False
    
    def update_bet_odds_in_db(self, market_id: str, selection_id: int, new_odds: float):
        """Update the odds in the database after successful API update"""
        try:
            conn = sqlite3.connect(self.betting_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE betting_history 
                SET lay_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE market_id = ? AND selection_id = ?
            """, (new_odds, market_id, selection_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated database: {selection_id} odds changed to {new_odds}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating database for {selection_id}: {e}")
            return False

    def cancel_bet(self, market_id: str, selection_id: int):
        """Cancel an unmatched bet using backend ManageOrders controller"""
        try:
            # Get the bet_id from database
            conn = sqlite3.connect(self.betting_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bet_id FROM betting_history 
                WHERE market_id = ? AND selection_id = ?
            """, (market_id, selection_id))
            
            bet_row = cursor.fetchone()
            conn.close()
            
            if not bet_row or not bet_row[0]:
                logger.warning(f"No bet_id found for selection {selection_id}")
                return False
            
            bet_id = bet_row[0]
            
            # Create cancel instruction
            cancel_instruction = {
                "betId": bet_id,
                "sizeReduction": None  # Cancel entire bet
            }
            
            # Use the backend endpoint
            cancel_url = f"{self.api_base_url}/api/manageorders/cancel"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                cancel_url,
                json=[cancel_instruction],  # Backend expects a list
                headers=headers,
                params={'marketId': market_id},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully cancelled bet {bet_id}: {result}")
                return True
            else:
                logger.error(f"Failed to cancel bet {bet_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling bet {selection_id}: {e}")
            return False
    
    def pre_race_odds_check(self, market_id: str):
        """Check odds movement for all pending bets and update orders when favorable"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            # Get all pending bets for this market
            cursor.execute("""
                SELECT selection_id, horse_name, lay_price, bet_status, bet_id
                FROM betting_history 
                WHERE market_id = ? AND bet_status = 'PENDING'
            """, (market_id,))
            
            pending_bets = cursor.fetchall()
            logger.info(f"Pre-race odds check for {len(pending_bets)} pending bets in market {market_id}")
            
            for selection_id, horse_name, original_lay_price, bet_status, bet_id in pending_bets:
                current_lay_price, odds_movement = self.check_odds_movement(
                    market_id, selection_id, original_lay_price
                )
                
                if current_lay_price is not None:
                    # Check if current odds are still within our criteria
                    if current_lay_price <= self.strategy.max_odds:
                        if odds_movement > 0:
                            # Odds went up - update to better odds to increase match chance
                            logger.info(f"📈 Updating bet: {horse_name} from {original_lay_price} to {current_lay_price:.2f} (+{odds_movement:.2f}) - better odds for matching")
                            if self.update_bet_odds(market_id, selection_id, bet_id, current_lay_price):
                                # Update database with new odds
                                self.update_bet_odds_in_db(market_id, selection_id, current_lay_price)
                            else:
                                logger.warning(f"Failed to update bet for {horse_name}")
                        elif odds_movement < 0:
                            # Odds went down - still within criteria, update to current odds for better match chance
                            logger.info(f"📉 Updating bet: {horse_name} from {original_lay_price} to {current_lay_price:.2f} ({odds_movement:.2f}) - still within criteria, updating for better match chance")
                            if self.update_bet_odds(market_id, selection_id, bet_id, current_lay_price):
                                # Update database with new odds
                                self.update_bet_odds_in_db(market_id, selection_id, current_lay_price)
                            else:
                                logger.warning(f"Failed to update bet for {horse_name}")
                        else:
                            # Odds stayed the same - keep the bet
                            logger.info(f"⏸️ Keeping bet: {horse_name} @ {original_lay_price} (odds unchanged)")
                    else:
                        # Current odds exceed our criteria - cancel the bet
                        logger.info(f"❌ Cancelling bet: {horse_name} @ {original_lay_price} (odds now {current_lay_price:.2f}, exceeds max {self.strategy.max_odds})")
                        self.cancel_bet(market_id, selection_id)
                        # Update status to cancelled
                        self.update_bet_status(market_id, selection_id, "CANCELLED", 0.0)
                else:
                    logger.warning(f"⚠️ Could not check odds for {horse_name} - keeping bet")
                    
        except Exception as e:
            logger.error(f"Error in pre-race odds check: {e}")
        finally:
            conn.close()
    
    def pre_race_odds_check_for_imminent_races(self):
        """Check odds for races starting within 5 minutes"""
        # Get races starting within 5 minutes from main database
        main_conn = sqlite3.connect(self.db_path)
        
        try:
            # Get races starting within 5 minutes
            query = """
            SELECT DISTINCT h.MarketId, h.EventName, h.MarketName
            FROM HorseMarketBook h
            JOIN race_times rt ON h.EventName LIKE '%' || rt.venue || '%'
            WHERE ((h.MarketName LIKE 'R%' AND CAST(SUBSTR(h.MarketName, 2, 1) AS INTEGER) = rt.race_number)
               OR (rt.venue = "Le Lion D''angers" AND h.EventName LIKE '%Le Lion D''angers%' 
                   AND h.MarketName = (SELECT MIN(MarketName) FROM HorseMarketBook h2 
                                      WHERE h2.EventName = h.EventName AND h2.MarketName != 'To Be Placed')))
            AND h.MarketName != 'To Be Placed'
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 <= 5
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 >= 0
            """
            
            races_df = pd.read_sql_query(query, main_conn)
            
            if len(races_df) > 0:
                # Check which of these races have pending bets in betting database
                betting_conn = sqlite3.connect(self.betting_db_path)
                betting_cursor = betting_conn.cursor()
                
                races_with_pending_bets = []
                for _, race in races_df.iterrows():
                    market_id = race['MarketId']
                    betting_cursor.execute("""
                        SELECT COUNT(*) FROM betting_history 
                        WHERE market_id = ? AND bet_status = 'PENDING'
                    """, (market_id,))
                    
                    pending_count = betting_cursor.fetchone()[0]
                    if pending_count > 0:
                        races_with_pending_bets.append(race)
                
                betting_conn.close()
                
                if len(races_with_pending_bets) > 0:
                    logger.info(f"Pre-race odds check for {len(races_with_pending_bets)} imminent races with pending bets")
                    for race in races_with_pending_bets:
                        self.pre_race_odds_check(race['MarketId'])
                else:
                    logger.debug("No imminent races with pending bets")
            else:
                logger.debug("No imminent races found")
                
        except Exception as e:
            logger.error(f"Error checking imminent races: {e}")
        finally:
            main_conn.close()
    
    def create_place_order_request(self, market_id: str, opportunities: list, stake_per_bet: float = 1.0):
        """
        Create a PlaceOrderRequest for multiple lay bets
        
        Args:
            market_id: The market ID
            opportunities: List of betting opportunities from strategy
            stake_per_bet: Amount to stake per bet
            
        Returns:
            dict: PlaceOrderRequest ready for API
        """
        instructions = []
        
        # Ensure stake is greater than 0.01 (API requirement)
        if stake_per_bet <= 0.01:
            stake_per_bet = 1.0
            
        total_stake = 0
        
        for opp in opportunities:
            # Calculate dynamic stake based on odds
            dynamic_stake = self.calculate_stake(opp['lay_price'])
            total_stake += dynamic_stake
            
            instruction = {
                "selectionId": int(opp['selection_id']),
                "handicap": 0,
                "side": "LAY",
                "orderType": "LIMIT",
                "timeInForce": "FILL_OR_KILL",
                "persistenceType": "LAPSE",
                "limitOrder": {
                    "size": float(dynamic_stake),
                    "price": float(opp['lay_price']),
                    "persistenceType": "LAPSE"
                },
                "marketOnCloseOrder": {
                    "liability": 0
                }
            }
            instructions.append(instruction)
        
        place_order_request = {
            "marketId": market_id,
            "instructions": instructions,
            "customerRef": f"lay_betting_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stake": float(total_stake)
        }
        
        return place_order_request
    
    def place_lay_bets(self, market_id: str, opportunities: list, stake_per_bet: float = 1.0, dry_run: bool = True):
        """
        Place lay bets via the PlaceOrder API
        
        Args:
            market_id: The market ID
            opportunities: List of betting opportunities
            stake_per_bet: Amount to stake per bet
            dry_run: If True, don't actually place bets, just log what would be placed
            
        Returns:
            dict: API response or dry run summary
        """
        if not opportunities:
            logger.info("No opportunities to bet on")
            return {"status": "no_opportunities"}
        
        # Filter out horses we've already bet on and validate selection IDs
        new_opportunities = []
        current_selection_ids = set()
        
        # Get current valid selection IDs for this market
        try:
            current_odds = self.get_race_odds(market_id)
            current_selection_ids = set(current_odds['SelectionId'].tolist())
            logger.info(f"Valid selection IDs for market {market_id}: {sorted(current_selection_ids)}")
        except Exception as e:
            logger.error(f"Failed to get current selection IDs: {e}")
            return {"status": "error", "error": "Cannot validate selection IDs"}
        
        for opp in opportunities:
            # Check if selection ID is valid for current market
            if opp['selection_id'] not in current_selection_ids:
                logger.warning(f"⚠️ Skipping {opp['runner_name']} - selection ID {opp['selection_id']} not valid for current market")
                continue
                
            # Check if we've already bet on this horse
            if not self.has_bet_been_placed(market_id, opp['selection_id']):
                # Double-check cache before adding to opportunities
                bet_key = f"{market_id}_{opp['selection_id']}"
                if bet_key not in self.placed_bets:
                    new_opportunities.append(opp)
                else:
                    logger.info(f"🚫 DUPLICATE PREVENTED: {opp['runner_name']} already in cache")
            else:
                logger.info(f"🚫 DUPLICATE PREVENTED: {opp['runner_name']} - bet already placed")
        
        if not new_opportunities:
            logger.info("All opportunities already bet on or invalid - no new bets to place")
            return {"status": "all_bets_already_placed_or_invalid"}
        
        logger.info(f"Filtered to {len(new_opportunities)} new opportunities (removed {len(opportunities) - len(new_opportunities)} duplicates)")
        
        # Add bets to cache IMMEDIATELY to prevent race conditions
        for opp in new_opportunities:
            bet_key = f"{market_id}_{opp['selection_id']}"
            self.placed_bets.add(bet_key)
            logger.info(f"🔒 Added {opp['runner_name']} to cache to prevent duplicates")
        
        # Create the place order request with filtered opportunities
        place_order_request = self.create_place_order_request(market_id, new_opportunities, stake_per_bet)
        
        if dry_run:
            logger.info("🔍 DRY RUN - Would place the following bets:")
            total_liability = 0
            for i, opp in enumerate(new_opportunities):
                dynamic_stake = self.calculate_stake(opp['lay_price'])
                liability = (opp['lay_price'] - 1) * dynamic_stake
                total_liability += liability
                logger.info(f"  {i+1}. {opp['cloth_number']}. {opp['runner_name']} - Lay @ {opp['lay_price']:.2f} (Stake: ${dynamic_stake:.2f}, Liability: ${liability:.2f})")
            
            logger.info(f"📊 Total bets: {len(new_opportunities)}")
            logger.info(f"💰 Total liability: ${total_liability:.2f}")
            logger.info(f"🎯 Market: {market_id}")
            
            return {
                "status": "dry_run",
                "total_bets": len(new_opportunities),
                "total_liability": total_liability,
                "market_id": market_id,
                "request": place_order_request
            }
        
        # Actually place the bets
        try:
            logger.info(f"🎯 Placing {len(new_opportunities)} lay bets on market {market_id}")
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.place_order_url,
                json=place_order_request,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Successfully placed bets: {result}")
                
                # Check if any bets were actually successful
                successful_bets = []
                if 'result' in result and 'instructionReports' in result['result']:
                    for i, report in enumerate(result['result']['instructionReports']):
                        if i < len(new_opportunities):
                            if report.get('status') == 'SUCCESS':
                                # Extract bet ID if available
                                bet_id = report.get('betId')
                                selection_id = new_opportunities[i]['selection_id']
                                logger.info(f"✅ Bet successful: {selection_id} -> {bet_id}")
                                
                                # Record the successful bet
                                logger.info(f"🔍 Attempting to record bet for {new_opportunities[i]['runner_name']} in database...")
                                if self.record_bet_placed(
                                    market_id, 
                                    selection_id, 
                                    new_opportunities[i]['runner_name'], 
                                    new_opportunities[i]['lay_price'], 
                                    stake_per_bet,
                                    bet_id
                                ):
                                    # ONLY add to cache if database write succeeds
                                    bet_key = f"{market_id}_{selection_id}"
                                    self.placed_bets.add(bet_key)
                                    successful_bets.append(new_opportunities[i])
                                    logger.info(f"✅ Added {selection_id} to placed bets cache")
                                else:
                                    logger.error(f"❌ CRITICAL: Failed to record bet for {new_opportunities[i]['runner_name']} - database write failed")
                                    logger.error(f"❌ This will cause duplicate bets on next cycle!")
                            else:
                                # Bet failed - log the error but DON'T add to cache
                                error_code = report.get('errorCode', 'UNKNOWN_ERROR')
                                logger.error(f"❌ Bet failed for {new_opportunities[i]['runner_name']}: {error_code}")
                
                if len(successful_bets) == 0:
                    logger.warning("⚠️ No bets were successfully placed")
                    return {
                        "status": "all_bets_failed",
                        "error": "All bets failed due to API errors"
                    }
                
                if len(successful_bets) != len(new_opportunities):
                    logger.warning(f"⚠️ Only {len(successful_bets)}/{len(new_opportunities)} bets recorded in database")
                
                return {
                    "status": "success",
                    "response": result,
                    "total_bets": len(new_opportunities)
                }
            else:
                logger.error(f"❌ Failed to place bets: {response.status_code} - {response.text}")
                return {
                    "status": "error",
                    "error": f"{response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ Exception placing bets: {str(e)}")
            return {
                "status": "exception",
                "error": str(e)
            }
    
    def scan_and_bet(self, max_minutes_ahead: int = 60, stake_per_bet: float = 1.0, dry_run: bool = True, demo_mode: bool = False):
        """
        Scan for opportunities and place bets automatically
        Only places bets within 10 minutes of race start
        
        Args:
            max_minutes_ahead: Maximum minutes ahead to look for races
            stake_per_bet: Amount to stake per bet
            dry_run: If True, don't actually place bets
            demo_mode: If True, get any available races for demonstration
        """
        logger.info("=== LAY BETTING AUTOMATION ===")
        logger.info(f"Strategy: {self.strategy.get_strategy_description()}")
        logger.info(f"Stake per bet: ${stake_per_bet}")
        logger.info(f"Betting window: {self.min_minutes_before_race} minutes before race start")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE BETTING'}")
        
        # Clear the placed bets cache at the start of each scan cycle
        # This prevents stale cache entries from previous cycles
        self.placed_bets.clear()
        logger.info(f"Cleared placed bets cache (was {len(self.placed_bets)} entries)")
        
        if demo_mode:
            races_df = self.get_live_races(hours_ahead=2, demo_mode=True)
        else:
            races_df = self.get_races_within_betting_window(max_minutes_ahead)
        
        if len(races_df) == 0:
            logger.info("No races found for the specified criteria")
            return
        
        total_opportunities = 0
        total_liability = 0
        results = []
        
        for _, race in races_df.iterrows():
            # Safety check: Skip races that are too far in the future or too long after start
            minutes_until_start = race.get('minutes_until_start', 0)
            if minutes_until_start > max_minutes_ahead:
                # Skip races outside betting window (no logging)
                continue
            if minutes_until_start < -2:  # Allow betting up to 2 minutes after race starts
                # Skip races that started too long ago (no logging)
                continue
            
            event_name = race['EventName']
            market_name = race['MarketName']
            market_id = race['MarketId']
            open_date = race['OpenDate']
            
            logger.info(f"\n🎯 Analyzing: {event_name} - {market_name}")
            if open_date:
                logger.info(f"Start Time: {open_date}")
            else:
                # Calculate start time from race_times data
                race_time = race.get('race_time', '')
                race_date = race.get('race_date', '')
                if race_time and race_date:
                    logger.info(f"Start Time: {race_date} {race_time}")
                else:
                    logger.info(f"Start Time: Unknown")
            
            # Get odds before refresh for comparison
            odds_before = self.get_race_odds(market_id)
            odds_before_count = len(odds_before) if odds_before is not None else 0
            
            # Try to refresh odds for this market (non-blocking)
            try:
                import requests
                refresh_url = f"{self.api_base_url}/api/odds/refresh/{market_id}"
                response = requests.get(refresh_url, timeout=3)  # Very short timeout
                if response.status_code == 200:
                    result = response.json()
                    # Get odds after refresh for comparison
                    odds_after = self.get_race_odds(market_id)
                    odds_after_count = len(odds_after) if odds_after is not None else 0
                    
                    logger.info(f"✅ Refreshed odds: {result.get('layPricesCount', 0)} lay prices updated")
                    logger.info(f"📊 Odds comparison: {odds_before_count} → {odds_after_count} horses")
                    
                    # Show sample odds before/after if available
                    if odds_before_count > 0 and odds_after_count > 0:
                        sample_before = odds_before.head(2)[['runner_name', 'best_lay_price']].to_dict('records')
                        sample_after = odds_after.head(2)[['runner_name', 'best_lay_price']].to_dict('records')
                        logger.info(f"📈 Sample odds before: {sample_before}")
                        logger.info(f"📈 Sample odds after:  {sample_after}")
                else:
                    logger.info(f"ℹ️ Refresh skipped: {response.status_code}")
            except Exception as e:
                logger.info(f"ℹ️ Using existing odds data: {e}")
                # Continue with existing odds data if refresh fails
            
            # Load current market bets into cache to prevent duplicates
            self.load_current_market_bets(market_id)
            
            # Get race odds
            race_odds = self.get_race_odds(market_id)
            
            if len(race_odds) == 0:
                logger.info("  ❌ No horses found for this race")
                continue
            
            # Use cached split to analyze race opportunity
            # This ensures the top/bottom split doesn't change with real-time odds
            is_eligible, reason, eligible_horses = self.analyze_race_with_cached_split(
                market_id, race_odds
            )
            
            if not is_eligible:
                logger.info(f"  ❌ Not eligible: {reason}")
                continue
            
            # Found an opportunity - prepare betting data
            # Use BSP-based prices for betting to ensure we're betting on longshots, not favorites
            opportunities = []
            
            # Get BSP data for this market to use for betting prices
            bsp_data = self._get_bsp_projections(market_id)
            if bsp_data is None:
                logger.warning(f"⚠️ No BSP data available for betting prices - skipping race")
                continue
                
            for _, horse in eligible_horses.iterrows():
                selection_id = horse['SelectionId']
                
                # Find BSP price for this horse
                bsp_row = bsp_data[bsp_data['SelectionId'] == selection_id]
                if len(bsp_row) == 0:
                    logger.warning(f"⚠️ Skipping {horse['runner_name']}: No BSP data available")
                    continue
                    
                bsp_price = bsp_row['Average'].iloc[0]
                
                # Use BSP price for betting (this ensures we're betting on longshots)
                if pd.isna(bsp_price) or bsp_price <= 0:
                    logger.warning(f"⚠️ Skipping {horse['runner_name']}: Invalid BSP price ({bsp_price})")
                    continue
                
                # Get current market price for betting
                current_price = horse.get('best_lay_price', 0)
                if current_price <= 0:
                    logger.warning(f"⚠️ Skipping {horse['runner_name']}: No current market price available")
                    continue
                
                # Debug logging to track odds mismatch
                logger.info(f"🔍 DEBUG: {horse['runner_name']} - Current market price: {current_price:.2f}, BSP price: {bsp_price:.2f}")
                
                # Use current market price for betting (BSP was only used for classification)
                opportunity = {
                    'selection_id': selection_id,
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': current_price  # Use exact current market price
                }
                opportunities.append(opportunity)
            
            if len(opportunities) == 0:
                logger.info("  ❌ No valid opportunities after odds validation")
                continue
            
            logger.info(f"  ✅ OPPORTUNITY FOUND: {reason}")
            
            # Place bets for this race
            result = self.place_lay_bets(market_id, opportunities, stake_per_bet, dry_run)
            results.append({
                'market_id': market_id,
                'event_name': event_name,
                'market_name': market_name,
                'opportunities': len(opportunities),
                'result': result
            })
            
            total_opportunities += len(opportunities)
            if 'total_liability' in result:
                total_liability += result['total_liability']
        
        logger.info(f"\n=== AUTOMATION COMPLETE ===")
        logger.info(f"Races analyzed: {len(races_df)}")
        logger.info(f"Races with opportunities: {len([r for r in results if r['opportunities'] > 0])}")
        logger.info(f"Total bets: {total_opportunities}")
        logger.info(f"Total liability: ${total_liability:.2f}")
        
        return results

    def cleanup_old_odds(self):
        """Clean up old odds data from CurrentOdds table"""
        try:
            betting_conn = sqlite3.connect(self.betting_db_path)
            
            # Delete odds older than 2 hours
            cleanup_query = """
            DELETE FROM CurrentOdds 
            WHERE UpdatedAt < datetime('now', '-2 hours')
            """
            
            cursor = betting_conn.cursor()
            cursor.execute(cleanup_query)
            deleted_count = cursor.rowcount
            
            betting_conn.commit()
            betting_conn.close()
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old odds records")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old odds: {e}")


def main():
    """Main function for testing"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    api_base_url = "http://localhost:5173"  # C# backend runs on port 5173
    
    # Create automation instance
    automation = LayBettingAutomation(
        db_path=db_path,
        api_base_url=api_base_url,
        std_threshold=1.5,
        max_odds=25.0
    )
    
    # Run automation (dry run first)
    results = automation.scan_and_bet(
        hours_ahead=8,
        stake_per_bet=1.0,
        dry_run=True,  # Set to False for live betting
        demo_mode=True
    )
    
    return results


if __name__ == "__main__":
    main()
