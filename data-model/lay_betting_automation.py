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
        self.api_base_url = api_base_url.rstrip('/')
        self.strategy = LayBettingStrategy(std_threshold, max_odds)
        self.place_order_url = f"{self.api_base_url}/api/PlaceOrder"
        self.min_minutes_before_race = min_minutes_before_race
        self.placed_bets = set()  # Track placed bets to prevent duplicates
        self._create_race_times_table()
        self._create_betting_history_table()
    
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS betting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                selection_id INTEGER NOT NULL,
                horse_name TEXT,
                lay_price REAL,
                stake REAL,
                placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            m.OpenDate,
            datetime('now', 'localtime') as current_time,
            (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 as minutes_until_start
        FROM race_times rt
        JOIN HorseMarketBook h ON h.EventName LIKE '%' || rt.venue || '%'
        JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
        WHERE CAST(SUBSTR(h.MarketName, 2, 1) AS INTEGER) = rt.race_number
        AND h.MarketName != 'To Be Placed'
        AND rt.race_date = date('now', 'localtime')
        AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 <= ?
        AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 >= ?
        ORDER BY rt.race_time
        """
        
        races_df = pd.read_sql_query(query, conn, params=[max_minutes_ahead, -self.min_minutes_before_race])
        conn.close()
        
        logger.info(f"Found {len(races_df)} races within betting window ({self.min_minutes_before_race}-{max_minutes_ahead} minutes)")
        
        if len(races_df) > 0:
            for _, race in races_df.head(3).iterrows():
                minutes_until = race['minutes_until_start']
                if minutes_until < 0:
                    logger.info(f"  {race['venue']} R{race['race_number']}: Started {abs(minutes_until):.1f} minutes ago")
                else:
                    logger.info(f"  {race['venue']} R{race['race_number']}: Starts in {minutes_until:.1f} minutes")
        
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
        conn = sqlite3.connect(self.db_path)
        
        # Get ALL horses with their best lay odds (no filtering by max_odds yet)
        # For lay betting, we want the LOWEST lay price available (best odds for the layer)
        all_horses_query = """
        SELECT 
            h.SelectionId,
            COALESCE(h.RUNNER_NAME, 'Unknown') as runner_name,
            COALESCE(h.CLOTH_NUMBER, 0) as cloth_number,
            MIN(l.Price) as best_lay_price,
            MAX(l.Size) as max_available_size,
            l.LastPriceTraded,
            l.TotalMatched
        FROM HorseMarketBook h
        LEFT JOIN MarketBookLayPrices l ON h.SelectionId = l.SelectionId AND h.MarketId = l.MarketId
        WHERE h.MarketId = ?
        AND l.Price > 0
        AND l.Price <= 100
        GROUP BY h.SelectionId, h.RUNNER_NAME, h.CLOTH_NUMBER
        ORDER BY best_lay_price
        """
        
        result_df = pd.read_sql_query(all_horses_query, conn, params=[market_id])
        conn.close()
        
        return result_df
    
    def has_bet_been_placed(self, market_id: str, selection_id: int):
        """Check if a bet has already been placed on this horse in this market"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM betting_history 
            WHERE market_id = ? AND selection_id = ?
        """, (market_id, selection_id))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def record_bet_placed(self, market_id: str, selection_id: int, horse_name: str, lay_price: float, stake: float):
        """Record that a bet has been placed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO betting_history 
                (market_id, selection_id, horse_name, lay_price, stake, placed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (market_id, selection_id, horse_name, lay_price, stake))
            
            conn.commit()
            logger.info(f"Recorded bet: {horse_name} @ {lay_price} in market {market_id}")
        except Exception as e:
            logger.error(f"Error recording bet: {e}")
        finally:
            conn.close()
    
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
            
        for opp in opportunities:
            instruction = {
                "selectionId": int(opp['selection_id']),
                "handicap": 0,
                "side": "LAY",  # LAY = Lay
                "orderType": "LIMIT",  # LIMIT = Limit
                "limitOrder": {
                    "size": float(stake_per_bet),
                    "price": float(opp['lay_price']),
                    "persistenceType": "LAPSE"
                },
                "persistenceType": "LAPSE",  # Required at instruction level
                "timeInForce": "FILL_OR_KILL",  # Required field
                "minFillSize": 0,  # Required field
                "marketOnCloseOrder": {  # Required field - provide empty object instead of null
                    "liability": 0
                }
            }
            instructions.append(instruction)
        
        place_order_request = {
            "marketId": market_id,
            "instructions": instructions,
            "customerRef": f"lay_betting_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "stake": float(stake_per_bet)  # Required top-level stake field
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
        
        # Filter out horses we've already bet on
        new_opportunities = []
        for opp in opportunities:
            if not self.has_bet_been_placed(market_id, opp['selection_id']):
                new_opportunities.append(opp)
            else:
                logger.info(f"⏭️ Skipping {opp['runner_name']} - bet already placed")
        
        if not new_opportunities:
            logger.info("All opportunities already bet on - no new bets to place")
            return {"status": "all_bets_already_placed"}
        
        logger.info(f"Filtered to {len(new_opportunities)} new opportunities (removed {len(opportunities) - len(new_opportunities)} duplicates)")
        
        # Create the place order request with filtered opportunities
        place_order_request = self.create_place_order_request(market_id, new_opportunities, stake_per_bet)
        
        if dry_run:
            logger.info("🔍 DRY RUN - Would place the following bets:")
            total_liability = 0
            for i, opp in enumerate(new_opportunities):
                liability = (opp['lay_price'] - 1) * stake_per_bet
                total_liability += liability
                logger.info(f"  {i+1}. {opp['cloth_number']}. {opp['runner_name']} - Lay @ {opp['lay_price']:.2f} (Liability: ${liability:.2f})")
            
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
                
                # Record the bets in our history
                for opp in new_opportunities:
                    self.record_bet_placed(
                        market_id, 
                        opp['selection_id'], 
                        opp['runner_name'], 
                        opp['lay_price'], 
                        stake_per_bet
                    )
                
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
            event_name = race['EventName']
            market_name = race['MarketName']
            market_id = race['MarketId']
            open_date = race['OpenDate']
            
            logger.info(f"\n🎯 Analyzing: {event_name} - {market_name}")
            logger.info(f"Start Time: {open_date}")
            
            # Get race odds
            race_odds = self.get_race_odds(market_id)
            
            if len(race_odds) == 0:
                logger.info("  ❌ No horses found for this race")
                continue
            
            # Use shared strategy to analyze race opportunity
            is_eligible, reason, eligible_horses = self.strategy.analyze_race_eligibility(
                race_odds, 'best_lay_price'
            )
            
            if not is_eligible:
                logger.info(f"  ❌ Not eligible: {reason}")
                continue
            
            # Found an opportunity - prepare betting data
            opportunities = []
            for _, horse in eligible_horses.iterrows():
                opportunity = {
                    'selection_id': horse['SelectionId'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['best_lay_price']
                }
                opportunities.append(opportunity)
            
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
