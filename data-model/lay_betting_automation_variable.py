"""
Lay Betting Automation with Variable Strategy - Connects variable lay betting strategy to PlaceOrder API
"""
import requests
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from shared_lay_betting_variable import LayBettingStrategyVariable, LayBettingResults
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingAutomationVariable:
    """
    Automates lay betting with variable strategy by connecting to PlaceOrder API
    """
    
    def __init__(self, db_path: str, api_base_url: str, base_std_threshold: float = 1.0, base_max_odds: float = 30.0,
                 min_minutes_before_race: int = 10):
        self.db_path = db_path
        self.api_base_url = api_base_url.rstrip('/')
        self.strategy = LayBettingStrategyVariable(base_std_threshold, base_max_odds)
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
    
    def _create_betting_history_table(self):
        """Create betting_history table to track placed bets"""
        # Use the betting history database, not the main database
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
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
    
    def get_races_within_betting_window(self, max_minutes_ahead: int = 20):
        """
        Get races that are within the betting window (not too close to start)
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get races from race_times table that are starting soon (same as original system)
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
        
        races_df = pd.read_sql_query(query, conn, params=[max_minutes_ahead, self.min_minutes_before_race])
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
    
    def get_race_odds(self, market_id: str):
        """Get all lay odds for a specific race, with best odds per horse"""
        conn = sqlite3.connect(self.db_path)
        
        # Get ALL horses with their best lay odds (no filtering by max_odds yet)
        # For lay betting, we want the LOWEST lay price available (best odds for the layer)
        all_horses_query = """
        SELECT 
            h.SelectionId,
            COALESCE(h.RUNNER_NAME, 'Unknown') as runner_name,
            COALESCE(h.CLOTH_NUMBER, 0) as cloth_number
        FROM HorseMarketBook h
        WHERE h.MarketId = ?
        """
        
        all_horses_df = pd.read_sql_query(all_horses_query, conn, params=[market_id])
        
        # Then get lay odds for horses that have them
        odds_query = """
        SELECT 
            h.SelectionId,
            MIN(l.Price) as best_lay_price,
            MAX(l.Size) as max_available_size,
            l.LastPriceTraded,
            l.TotalMatched
        FROM HorseMarketBook h
        JOIN MarketBookLayPrices l ON h.SelectionId = l.SelectionId AND h.MarketId = l.MarketId
        WHERE h.MarketId = ?
        AND l.Price > 0
        GROUP BY h.SelectionId
        ORDER BY best_lay_price
        """
        
        odds_df = pd.read_sql_query(odds_query, conn, params=[market_id])
        conn.close()
        
        # Merge to get all horses with their odds (if available)
        result_df = all_horses_df.merge(odds_df, on='SelectionId', how='left')
        
        return result_df
    
    def has_bet_been_placed(self, market_id: str, selection_id: int):
        """Check if a bet has already been placed on this horse in this market"""
        # Use the betting history database, not the main database
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM betting_history 
            WHERE market_id = ? AND selection_id = ?
        """, (market_id, selection_id))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def check_bet_status(self, market_id: str, selection_id: int):
        """Check the current status of a bet via API"""
        try:
            # Get current orders for this market
            response = requests.get(f"{self.api_base_url}/api/orders/{market_id}")
            response.raise_for_status()
            
            orders_data = response.json()
            
            if 'result' in orders_data and orders_data['result']:
                for order in orders_data['result']:
                    if order.get('selectionId') == selection_id:
                        status = order.get('status', 'UNKNOWN')
                        matched_amount = order.get('sizeMatched', 0.0)
                        return status, matched_amount
            
            return "NOT_FOUND", 0.0
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking bet status: {e}")
            return "API_ERROR", 0.0
    
    def update_bet_status(self, market_id: str, selection_id: int, new_status: str, matched_amount: float = 0.0):
        """Update the status of a bet"""
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
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
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current best lay price for this horse
            cursor.execute("""
                SELECT MIN(Price) as current_lay_price
                FROM MarketBookLayPrices 
                WHERE MarketId = ? AND SelectionId = ? AND Price > 0 AND Status = 'ACTIVE'
            """, (market_id, selection_id))
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                current_lay_price = result[0]
                odds_movement = current_lay_price - original_lay_price
                
                # Positive movement = odds went up (good for us)
                # Negative movement = odds went down (bad for us)
                return current_lay_price, odds_movement
            else:
                return None, None
                
        except Exception as e:
            logger.error(f"Error checking odds movement: {e}")
            return None, None
        finally:
            conn.close()
    
    def update_bet_odds(self, market_id: str, selection_id: int, bet_id: str, new_odds: float):
        """Update bet odds using backend ManageOrders controller"""
        try:
            # Create update instruction
            update_instruction = {
                "betId": bet_id,
                "newPrice": new_odds
            }
            
            update_request = {
                "marketId": market_id,
                "instructions": [update_instruction]
            }
            
            response = requests.post(f"{self.api_base_url}/api/manage-orders", json=update_request)
            response.raise_for_status()
            
            result = response.json()
            if result.get('status') == 'SUCCESS':
                logger.info(f"Successfully updated bet {bet_id} to {new_odds}: {result}")
                return True
            else:
                logger.error(f"Failed to update bet {bet_id}: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update bet {bet_id}: {response.status_code} - {response.text}")
            return False
    
    def update_bet_odds_in_db(self, market_id: str, selection_id: int, new_odds: float):
        """Update bet odds in database"""
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE betting_history 
                SET lay_price = ?
                WHERE market_id = ? AND selection_id = ?
            """, (new_odds, market_id, selection_id))
            
            conn.commit()
            logger.info(f"Updated bet odds in database: {selection_id} -> {new_odds}")
        except Exception as e:
            logger.error(f"Error updating bet odds in database: {e}")
        finally:
            conn.close()
    
    def cancel_bet(self, market_id: str, selection_id: int):
        """Cancel an unmatched bet using backend ManageOrders controller"""
        try:
            # Get bet ID from database
            betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
            conn = sqlite3.connect(betting_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bet_id FROM betting_history 
                WHERE market_id = ? AND selection_id = ? AND bet_status = 'PENDING'
            """, (market_id, selection_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.warning(f"No pending bet found for {selection_id}")
                return False
            
            bet_id = result[0]
            
            # Create cancel instruction
            cancel_instruction = {
                "betId": bet_id
            }
            
            cancel_request = {
                "marketId": market_id,
                "instructions": [cancel_instruction]
            }
            
            response = requests.post(f"{self.api_base_url}/api/manage-orders", json=cancel_request)
            response.raise_for_status()
            
            result = response.json()
            if result.get('status') == 'SUCCESS':
                logger.info(f"Successfully cancelled bet {bet_id}")
                return True
            else:
                logger.error(f"Failed to cancel bet {bet_id}: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel bet: {e}")
            return False
    
    def pre_race_odds_check(self, market_id: str):
        """Check odds movement for all pending bets and update orders when favorable"""
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
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
                    # Get variable max odds for this market (need to determine field size)
                    # For now, use base max odds - this could be improved to get actual field size
                    variable_max_odds = self.strategy.base_max_odds
                    
                    # Check if current odds are still within our criteria
                    if current_lay_price <= variable_max_odds:
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
                        logger.info(f"❌ Cancelling bet: {horse_name} @ {original_lay_price} (odds now {current_lay_price:.2f}, exceeds max {variable_max_odds})")
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
            WHERE CAST(SUBSTR(h.MarketName, 2, 1) AS INTEGER) = rt.race_number
            AND h.MarketName != 'To Be Placed'
            AND rt.race_date = date('now', 'localtime')
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 <= 5
            AND (julianday(rt.race_date || ' ' || rt.race_time) - julianday('now', 'localtime')) * 24 * 60 >= 0
            """
            
            races_df = pd.read_sql_query(query, main_conn)
            
            if len(races_df) > 0:
                # Check which of these races have pending bets in betting database
                betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
                betting_conn = sqlite3.connect(betting_db_path)
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
            "stake": float(stake_per_bet)
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
                
            # Check if we've already bet on this horse (database-only check - no cache issues)
            if not self.has_bet_been_placed(market_id, opp['selection_id']):
                new_opportunities.append(opp)
            else:
                logger.info(f"🚫 DUPLICATE PREVENTED: {opp['runner_name']} - bet already placed")
        
        if not new_opportunities:
            logger.info("All opportunities already bet on or invalid - no new bets to place")
            return {"status": "all_bets_already_placed_or_invalid"}
        
        logger.info(f"Filtered to {len(new_opportunities)} new opportunities (removed {len(opportunities) - len(new_opportunities)} duplicates)")
        
        # Create the place order request with filtered opportunities
        place_order_request = self.create_place_order_request(market_id, new_opportunities, stake_per_bet)
        
        if dry_run:
            logger.info("🔍 DRY RUN - Would place the following bets:")
            total_liability = 0
            for i, opp in enumerate(new_opportunities):
                # Use the pre-calculated liability from the opportunity
                liability = opp['liability']
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
                
                # Check if any bets were actually successful
                successful_bets = []
                if 'instructionReports' in result:
                    for i, report in enumerate(result['instructionReports']):
                        if i < len(new_opportunities):
                            if report.get('status') == 'SUCCESS':
                                # Extract bet ID if available
                                bet_id = report.get('betId')
                                selection_id = new_opportunities[i]['selection_id']
                                logger.info(f"✅ Bet successful: {selection_id} -> {bet_id}")
                                
                                # Record the successful bet
                                if self.record_bet_placed(
                                    market_id, 
                                    selection_id, 
                                    new_opportunities[i]['runner_name'], 
                                    new_opportunities[i]['lay_price'], 
                                    stake_per_bet,
                                    bet_id
                                ):
                                    successful_bets.append(new_opportunities[i])
                                    logger.info(f"✅ Recorded bet for {new_opportunities[i]['runner_name']} in database")
                                else:
                                    logger.error(f"❌ Failed to record bet for {new_opportunities[i]['runner_name']} - database write failed")
                            else:
                                # Bet failed - log the error
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
                logger.error(f"❌ API request failed with status {response.status_code}: {response.text}")
                return {
                    "status": "api_error",
                    "error": f"API returned status {response.status_code}",
                    "response": response.text
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ API request timed out")
            return {
                "status": "timeout",
                "error": "API request timed out"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request failed: {e}")
            return {
                "status": "request_error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error placing bets: {e}")
            return {
                "status": "unexpected_error",
                "error": str(e)
            }
    
    def record_bet_placed(self, market_id: str, selection_id: int, horse_name: str, lay_price: float, stake: float, bet_id: str = None):
        """Record that a bet has been placed"""
        # Use the same database path as the original system
        betting_db_path = self.db_path.replace('betfairmarket.sqlite', 'betting_history.sqlite')
        conn = sqlite3.connect(betting_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO betting_history 
                (market_id, selection_id, horse_name, lay_price, stake, bet_id, bet_status, matched_amount, placed_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0.0, CURRENT_TIMESTAMP)
            """, (market_id, selection_id, horse_name, lay_price, stake, bet_id))
            
            conn.commit()
            logger.info(f"Recorded bet: {horse_name} @ {lay_price} in market {market_id} (Status: PENDING)")
            return True
        except Exception as e:
            logger.error(f"Failed to record bet: {e}")
            return False
        finally:
            conn.close()
    
    def scan_and_bet(self, max_minutes_ahead: int = 60, stake_per_bet: float = 1.0, dry_run: bool = True):
        """
        Scan for betting opportunities and place bets
        
        Args:
            max_minutes_ahead: Maximum minutes ahead to look for races
            stake_per_bet: Amount to stake per bet
            dry_run: If True, don't actually place bets, just log what would be placed
        """
        logger.info("=== LAY BETTING AUTOMATION (VARIABLE STRATEGY) ===")
        logger.info(f"Strategy: {self.strategy.get_strategy_description()}")
        logger.info(f"Stake per bet: ${stake_per_bet}")
        logger.info(f"Betting window: {self.min_minutes_before_race} minutes before race start")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE BETTING'}")
        
        # Get races within betting window
        races_df = self.get_races_within_betting_window(max_minutes_ahead)
        
        if len(races_df) == 0:
            logger.info("No races found for the specified criteria")
            return {"status": "no_races_found"}
        
        opportunities = []
        
        for _, race in races_df.iterrows():
            event_name = race['EventName']
            market_name = race['MarketName']
            market_id = race['MarketId']
            start_time = race['OpenDate']
            
            logger.info(f"\n🎯 Analyzing: {event_name} - {market_name}")
            logger.info(f"Start Time: {start_time}")
            
            # Get race odds
            race_odds = self.get_race_odds(market_id)
            
            if len(race_odds) == 0:
                logger.info("  ❌ No horses found for this race")
                continue
            
            # Log horse details
            logger.info(f"  🐎 Found {len(race_odds)} horses:")
            for _, horse in race_odds.iterrows():
                logger.info(f"    ID {horse['SelectionId']}: {horse['runner_name']} - Lay: {horse['best_lay_price']:.2f}")
            
            # Use variable strategy to analyze race opportunity
            is_eligible, reason, eligible_horses, variable_max_odds, variable_std_threshold = self.strategy.analyze_race_eligibility(
                race_odds, 'best_lay_price'
            )
            
            if not is_eligible:
                logger.info(f"  ❌ Not eligible: {reason}")
                continue
            
            # Found an opportunity
            logger.info(f"  ✅ OPPORTUNITY FOUND: {reason}")
            logger.info(f"  🎯 Eligible horses ({len(eligible_horses)}):")
            for _, horse in eligible_horses.iterrows():
                logger.info(f"    ID {horse['SelectionId']}: {horse['runner_name']} - Lay: {horse['best_lay_price']:.2f}")
            
            race_opportunities = []
            for _, horse in eligible_horses.iterrows():
                # Calculate bet details using variable strategy
                bet_details = self.strategy.calculate_lay_bet_details(
                    horse['best_lay_price'], stake_per_bet
                )
                
                horse_info = {
                    'selection_id': horse['SelectionId'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['best_lay_price'],
                    'stake': bet_details['stake'],
                    'liability': bet_details['liability'],
                    'potential_profit': bet_details['potential_profit'],
                    'variable_max_odds': variable_max_odds,
                    'variable_std_threshold': variable_std_threshold
                }
                
                race_opportunities.append(horse_info)
            
            # Store opportunity
            opportunity = {
                'event_name': event_name,
                'market_name': market_name,
                'market_id': market_id,
                'start_time': start_time,
                'horses': race_opportunities,
                'total_horses': len(race_odds),
                'eligible_horses': len(eligible_horses),
                'variable_max_odds': variable_max_odds,
                'variable_std_threshold': variable_std_threshold
            }
            
            opportunities.append(opportunity)
        
        if not opportunities:
            logger.info("No betting opportunities found")
            return {"status": "no_opportunities"}
        
        # Filter out horses we've already bet on
        new_opportunities = []
        for opp in opportunities:
            opp['horses'] = [horse for horse in opp['horses'] 
                           if not self.has_bet_been_placed(opp['market_id'], horse['selection_id'])]
            if opp['horses']:  # Only include if there are new horses to bet on
                new_opportunities.append(opp)
        
        if not new_opportunities:
            logger.info("All opportunities already bet on - no new bets to place")
            return {"status": "all_bets_already_placed"}
        
        logger.info(f"Filtered to {len(new_opportunities)} new opportunities (removed {len(opportunities) - len(new_opportunities)} duplicates)")
        
        # Place bets for each opportunity
        total_bets = 0
        total_liability = 0
        successful_opportunities = 0
        
        for opp in new_opportunities:
            logger.info(f"\n🎯 Processing opportunity: {opp['event_name']} - {opp['market_name']}")
            logger.info(f"📊 Total horses: {len(opp['horses'])}")
            logger.info(f"💰 Total liability: ${sum(horse['liability'] for horse in opp['horses']):.2f}")
            logger.info(f"🎯 Market: {opp['market_id']}")
            
            # Place bets for this opportunity
            result = self.place_lay_bets(
                market_id=opp['market_id'],
                opportunities=opp['horses'],
                stake_per_bet=stake_per_bet,
                dry_run=dry_run
            )
            
            if result.get('status') == 'success' or result.get('status') == 'dry_run':
                successful_opportunities += 1
                total_bets += result.get('total_bets', 0)
                total_liability += result.get('total_liability', 0)
                logger.info(f"✅ Successfully processed opportunity: {result.get('total_bets', 0)} bets")
            else:
                logger.error(f"❌ Failed to process opportunity: {result.get('error', 'Unknown error')}")
        
        logger.info(f"\n📊 Summary:")
        logger.info(f"  Opportunities processed: {successful_opportunities}/{len(new_opportunities)}")
        logger.info(f"  Total bets: {total_bets}")
        logger.info(f"  Total liability: ${total_liability:.2f}")
        
        return {
            "status": "success",
            "opportunities": len(new_opportunities),
            "successful_opportunities": successful_opportunities,
            "total_bets": total_bets,
            "total_liability": total_liability
        }
