"""
🚨 REAL MONEY Greyhound Lay Betting - Position 1 (Favorite) 🚨
⚠️  WARNING: THIS PLACES REAL BETS WITH REAL MONEY ⚠️

3-BET LADDER STRATEGY:
T-45s: Bet 1 - LIMIT at 10% UNDER current odds (lapses if not matched)
T-20s: Bet 2 - LIMIT at 5% UNDER current odds (lapses if not matched)
T+10s: Bet 3 - LIMIT_ON_CLOSE (accepts BSP up to maxOdds) - ONLY if Bet 1 & 2 unmatched
"""

import pandas as pd
import sqlite3
import requests
import time
import pytz
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import sys
import os
import json

# Add utilities to path
sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/utilities')
from db_connection_helper import get_db_connection

def round_to_valid_betfair_odds(odds: float) -> float:
    """Round odds to valid Betfair tick size"""
    if odds < 2:
        result = round(odds / 0.01) * 0.01
    elif odds < 3:
        result = round(odds / 0.02) * 0.02
    elif odds < 4:
        result = round(odds / 0.05) * 0.05
    elif odds < 6:
        result = round(odds / 0.1) * 0.1
    elif odds < 10:
        result = round(odds / 0.2) * 0.2
    elif odds < 20:
        result = round(odds / 0.5) * 0.5
    elif odds < 30:
        result = round(odds / 1) * 1
    elif odds < 50:
        result = round(odds / 2) * 2
    elif odds < 100:
        result = round(odds / 5) * 5
    else:
        result = round(odds / 10) * 10
    
    # Clean up floating point errors by rounding to 2 decimal places
    return round(result, 2)

# Load risk limits
RISK_LIMITS_PATH = "/Users/clairegrady/RiderProjects/betfair/greyhound-live/RISK_LIMITS.json"
with open(RISK_LIMITS_PATH, 'r') as f:
    RISK_LIMITS = json.load(f)

# Configuration from risk limits
POSITION_TO_LAY = 1  # Laying the FAVORITE
MAX_ODDS = RISK_LIMITS['maxOdds']
MIN_ODDS = RISK_LIMITS['minOdds']
FLAT_STAKE = RISK_LIMITS['stakePerBet']

# Database paths
LIVE_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/live_trades_greyhounds.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
RACE_TIMES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db"
BACKEND_URL = "http://localhost:5173"  # Backend runs on port 5173

# Set up logging
logging.basicConfig(
    level=logging.INFO,  # Changed back to INFO - DEBUG is too verbose
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/Users/clairegrady/RiderProjects/betfair/greyhound-live/logs/lay_position_{POSITION_TO_LAY}_REAL.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RealGreyhoundLayBetting:
    """Real money lay betting on greyhound favorites"""
    
    def __init__(self):
        self.processed_markets = set()
        self.session = requests.Session()
        self.session.timeout = 10
        self.logged_initial_races = False
        self.next_race_info = None
    
    def check_daily_limits(self) -> tuple[bool, str]:
        """Check if we've hit daily risk limits. Returns (can_bet, reason)"""
        try:
            conn = get_db_connection(LIVE_TRADES_DB)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Check daily bets and NET P&L (not just losses)
            cursor.execute("""
                SELECT 
                    COUNT(*) as bets_today,
                    COALESCE(SUM(profit_loss), 0) as net_pnl_today
                FROM live_trades
                WHERE date = ? AND status != 'FAILED'
            """, (today,))
            
            bets_today, net_pnl_today = cursor.fetchone()
            
            # Check daily bet limit
            if bets_today >= RISK_LIMITS['maxDailyBets']:
                conn.close()
                return False, f"Daily bet limit reached: {bets_today}/{RISK_LIMITS['maxDailyBets']}"
            
            # Check daily LOSS limit (only stop if NET P&L is negative and exceeds limit)
            if net_pnl_today < 0 and abs(net_pnl_today) >= RISK_LIMITS['maxDailyLoss']:
                conn.close()
                return False, f"Daily loss limit reached: ${net_pnl_today:.2f} (limit: -${RISK_LIMITS['maxDailyLoss']:.2f})"
            
            # Check emergency stop loss (total P&L)
            if 'emergencyStopLoss' in RISK_LIMITS:
                cursor.execute("""
                    SELECT COALESCE(SUM(profit_loss), 0) FROM live_trades WHERE result IN ('won', 'lost')
                """)
                total_pl = cursor.fetchone()[0]
                
                if total_pl <= -RISK_LIMITS['emergencyStopLoss']:
                    conn.close()
                    return False, f"EMERGENCY STOP: Total loss ${abs(total_pl):.2f} >= ${RISK_LIMITS['emergencyStopLoss']:.2f}"
            
            conn.close()
            return True, ""
            
        except Exception as e:
            logger.error(f"Error checking daily limits: {e}")
            return True, ""  # Default to allowing bet if check fails
    
    def get_account_balance(self) -> Optional[float]:
        """Get current Betfair account balance"""
        try:
            url = f"{BACKEND_URL}/api/account/funds"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'availableToBetBalance' in data:
                    balance = data['availableToBetBalance']
                    logger.info(f"💰 Account Balance: ${balance:.2f}")
                    return float(balance)
            
            logger.warning(f"Could not get account balance: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return None
    
    def cancel_bet(self, market_id: str, bet_id: str) -> bool:
        """Cancel an existing bet"""
        try:
            url = f"{BACKEND_URL}/api/CancelOrder"
            
            payload = {
                "marketId": market_id,
                "betId": bet_id
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error cancelling bet: {e}")
            return False
    
    def place_limit_bet(self, market_id: str, selection_id: int, odds: float, stake: float) -> Optional[Dict]:
        """
        Place a simple LIMIT order with LAPSE persistence
        Tries to match at specified odds, lapses if not matched
        
        Returns:
            Dict with 'betId', 'status', 'sizeMatched', 'avgpriceMatched' if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/PlaceOrder"
            
            payload = {
                "marketId": market_id,
                "selectionId": selection_id,
                "stake": stake,
                "side": "L",
                "orderType": "LIMIT",
                "price": odds,
                "persistenceType": "LAPSE",
                "timeInForce": "",
                "customerRef": f"LIMIT-{market_id}-{int(datetime.now().timestamp())}",
                "instructions": [
                    {
                        "selectionId": selection_id,
                        "handicap": 0,
                        "side": "LAY",
                        "orderType": "LIMIT",
                        "persistenceType": "LAPSE",
                        "timeInForce": "",
                        "limitOrder": {
                            "size": stake,
                            "price": odds,
                            "persistenceType": "LAPSE"
                        }
                    }
                ]
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', data)
                
                if result.get('status') == 'SUCCESS':
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        
                        if report.get('status') == 'SUCCESS':
                            bet_id = report.get('betId')
                            size_matched = report.get('sizeMatched', 0)
                            avg_price = report.get('averagepriceMatched', odds)
                            
                            return {
                                'betId': bet_id,
                                'status': 'MATCHED' if size_matched > 0 else 'UNMATCHED',
                                'sizeMatched': size_matched,
                                'avgpriceMatched': avg_price
                            }
                
                logger.error(f"Limit bet placement failed: {data}")
                return None
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception placing limit bet: {e}")
            return None
    
    def replace_bet(self, market_id: str, old_bet_id: str, selection_id: int, new_odds: float, stake: float) -> Optional[Dict]:
        """
        REPLACE an existing bet (atomic cancel + place using replaceOrders endpoint)
        
        Args:
            market_id: Market ID
            old_bet_id: Existing bet ID to replace
            selection_id: Runner selection ID (not used by replaceOrders, but kept for consistency)
            new_odds: New odds to place at
            stake: Stake amount
        
        Returns:
            Dict with new 'betId', 'status', 'sizeMatched', 'avgpriceMatched' if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/ManageOrders/replace"
            
            # ✅ CORRECT replaceOrders schema (ONLY these 3 fields allowed!)
            payload = {
                "marketId": market_id,
                "instructions": [
                    {
                        "betId": old_bet_id,
                        "newprice": new_odds,
                        "newSize": stake
                    }
                ],
                "customerRef": f"REPLACE-{market_id}-{int(datetime.now().timestamp())}"
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Handle JSON-RPC wrapper
                result = data.get('result', data)
                
                if result.get('status') == 'SUCCESS':
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        
                        if report.get('status') == 'SUCCESS':
                            # Get place instruction report (new bet)
                            place_report = report.get('placeInstructionReport', {})
                            bet_id = place_report.get('betId')
                            size_matched = place_report.get('sizeMatched', 0)
                            avg_price = place_report.get('averagepriceMatched', new_odds)
                            
                            return {
                                'betId': bet_id,
                                'status': 'MATCHED' if size_matched > 0 else 'UNMATCHED',
                                'sizeMatched': size_matched,
                                'avgpriceMatched': avg_price
                            }
                
                logger.error(f"Replace bet failed: {data}")
                return None
            else:
                logger.error(f"Replace bet HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception replacing bet: {e}")
            return None
    
    def check_bet_status(self, market_id: str, bet_id: str) -> Optional[Dict]:
        """
        Check if a bet is matched or unmatched
        
        Returns:
            Dict with 'status', 'sizeMatched', 'avgpriceMatched' if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/ManageOrders/list"
            
            payload = {
                "marketId": market_id,
                "betIds": [bet_id]
            }
            
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', data)
                
                if isinstance(result, list) and len(result) > 0:
                    bet = result[0]
                    size_matched = bet.get('sizeMatched', 0)
                    avg_price = bet.get('averagepriceMatched', 0)
                    bet_status = bet.get('status', 'UNKNOWN')
                    
                    # CRITICAL: If sizeMatched > 0, bet is MATCHED (full or partial) regardless of 'status' field
                    # Betfair sometimes lags on updating 'status' but 'sizeMatched' is always accurate
                    # IMPORTANT: Partial matches should NOT be replaced (would cancel matched portion)
                    if size_matched > 0:
                        # Check if fully or partially matched
                        stake_requested = bet.get('sizeRemaining', 0) + size_matched  # Total original stake
                        if size_matched >= stake_requested * 0.99:  # 99% threshold for rounding
                            logger.info(f"✅ Bet {bet_id}: FULLY matched {size_matched:.2f} @ {avg_price:.2f}")
                        else:
                            logger.warning(f"⚠️  Bet {bet_id}: PARTIALLY matched {size_matched:.2f}/{stake_requested:.2f} @ {avg_price:.2f} - stopping cascade")
                        
                        return {
                            'status': 'MATCHED',
                            'sizeMatched': size_matched,
                            'avgpriceMatched': avg_price
                        }
                    else:
                        logger.info(f"⏳ Bet {bet_id}: Unmatched (status={bet_status})")
                        return {
                            'status': 'UNMATCHED',
                            'sizeMatched': 0,
                            'avgpriceMatched': None
                        }
                
                logger.warning(f"Bet status check returned empty result for {bet_id}")
                return None
            else:
                logger.warning(f"Bet status check HTTP {response.status_code} for {bet_id}: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.warning(f"Exception checking bet status for {bet_id}: {e}")
            return None
    
    def place_bsp_bet(self, market_id: str, selection_id: int, max_bsp_price: float, stake: float) -> Optional[Dict]:
        """
        Place a pure LIMIT_ON_CLOSE order (BSP only with max price limit)
        
        Args:
            max_bsp_price: Maximum BSP price willing to accept (for LAY, this is worst-case odds)
        
        Returns:
            Dict with 'betId', 'status', etc. if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/PlaceOrder"
            
            # Pure LIMIT_ON_CLOSE order - ONLY accepts BSP up to max_bsp_price
            # Use 'size' for fixed stake, not 'liability'
            payload = {
                "marketId": market_id,
                "selectionId": selection_id,
                "stake": stake,
                "side": "L",
                "orderType": "LIMIT_ON_CLOSE",
                "persistenceType": "LAPSE",
                "timeInForce": "",
                "customerRef": f"BSP-{market_id}-{int(datetime.now().timestamp())}",
                "instructions": [
                    {
                        "selectionId": selection_id,
                        "handicap": 0,
                        "side": "LAY",
                        "orderType": "LIMIT_ON_CLOSE",
                        "persistenceType": "LAPSE",
                        "timeInForce": "",
                        "limitOnCloseOrder": {
                            "price": max_bsp_price,
                            "liability": stake
                        }
                    }
                ]
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', data)
                
                if result.get('status') == 'SUCCESS':
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        
                        if report.get('status') == 'SUCCESS':
                            bet_id = report.get('betId')
                            
                            return {
                                'betId': bet_id,
                                'status': 'BSP_PENDING',
                                'sizeMatched': 0,
                                'avgpriceMatched': None
                            }
                
                logger.error(f"BSP bet placement failed: {data}")
                return None
            else:
                logger.error(f"BSP bet HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception placing BSP bet: {e}")
            return None
    
    def place_market_on_close_bet(self, market_id: str, selection_id: int, stake: float) -> Optional[Dict]:
        """
        Place a MARKET_ON_CLOSE order (accepts BSP at ANY price - no limit)
        Use this as last resort when Bet 1 & 2 have failed
        
        Returns:
            Dict with 'betId', 'status', etc. if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/PlaceOrder"
            
            # MARKET_ON_CLOSE - accepts BSP up to MAX_ODDS
            max_liability = round(stake * (MAX_ODDS - 1), 2)  # Use MAX_ODDS from RISK_LIMITS
            
            payload = {
                "marketId": market_id,
                "selectionId": selection_id,
                "stake": stake,
                "side": "L",
                "orderType": "MARKET_ON_CLOSE",
                "persistenceType": "LAPSE",
                "timeInForce": "",
                "customerRef": f"MOC-{market_id}-{int(datetime.now().timestamp())}",
                "instructions": [
                    {
                        "selectionId": selection_id,
                        "handicap": 0,
                        "side": "LAY",
                        "orderType": "MARKET_ON_CLOSE",
                        "persistenceType": "LAPSE",
                        "timeInForce": "",
                        "marketOnCloseOrder": {
                            "liability": max_liability
                        }
                    }
                ]
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', data)
                
                if result.get('status') == 'SUCCESS':
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        
                        if report.get('status') == 'SUCCESS':
                            bet_id = report.get('betId')
                            
                            return {
                                'betId': bet_id,
                                'status': 'BSP_PENDING',
                                'sizeMatched': 0,
                                'avgpriceMatched': None
                            }
                
                logger.error(f"MARKET_ON_CLOSE bet placement failed: {data}")
                return None
            else:
                logger.error(f"MARKET_ON_CLOSE bet HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception placing MARKET_ON_CLOSE bet: {e}")
            return None
    
    def save_live_trade(self, race_info: Dict, dog_info: Dict, bet_result: Optional[Dict], limit_on_close: float):
        """Save real trade to database"""
        try:
            conn = get_db_connection(LIVE_TRADES_DB)
            cursor = conn.cursor()
            
            liability = FLAT_STAKE * (dog_info['odds'] - 1)
            
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            matched_str = now_str if (bet_result and bet_result.get('sizeMatched', 0) > 0) else None
            
            cursor.execute("""
                INSERT INTO live_trades (
                    date, venue, country, race_number, market_id,
                    dog_name, box_number, position_in_market, selection_id,
                    initial_odds_requested, final_odds_matched, stake, liability,
                    betfair_bet_id, status, total_matched, placement_time, matched_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                race_info['race_datetime'].strftime('%Y-%m-%d'),
                race_info['venue'],
                race_info['country'],
                race_info['race_number'],
                race_info['market_id'],
                dog_info['dog_name'],
                dog_info.get('box'),
                POSITION_TO_LAY,
                dog_info['selection_id'],
                dog_info['odds'],  # initial_odds_requested
                bet_result.get('avgpriceMatched') if bet_result else None,  # final_odds_matched
                FLAT_STAKE,
                liability,
                bet_result['betId'] if bet_result else None,
                bet_result['status'] if bet_result else 'FAILED',
                dog_info.get('total_matched'),
                now_str,  # placement_time
                matched_str  # matched_time
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"💾 Saved bet to DB: {race_info['venue']} R{race_info['race_number']} - {dog_info['dog_name']} @ {dog_info['odds']:.2f}")
            
        except sqlite3.Error as db_error:
            logger.error(f"❌ DATABASE ERROR saving live trade: {db_error}")
            logger.error(f"   Race: {race_info.get('venue')} R{race_info.get('race_number')}")
            logger.error(f"   Market ID: {race_info.get('market_id')}")
        except Exception as e:
            logger.error(f"❌ EXCEPTION saving live trade: {e}")
            logger.error(f"   Race: {race_info.get('venue')} R{race_info.get('race_number')}")
            import traceback
            logger.error(traceback.format_exc())
    
    def has_already_bet_on_race(self, market_id: str) -> bool:
        """Check if we've already placed a bet on this race (database check)"""
        try:
            conn = get_db_connection(LIVE_TRADES_DB)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM live_trades 
                WHERE market_id = ? AND status != 'FAILED'
            """, (market_id,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking if already bet: {e}")
            return False  # Default to allowing bet if check fails
    
    def get_upcoming_races(self) -> List[Dict]:
        """Get greyhound races within betting window (5-50 seconds before race time)"""
        try:
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db", timeout=30)
            # Don't filter by date - calculate time differences for all races
            # This handles cross-midnight races (e.g. Perth races after midnight)
            query = """
                SELECT venue, race_number, race_time, race_date, country
                FROM greyhound_race_times
                WHERE race_date >= date('now', 'localtime')
                AND race_date <= date('now', 'localtime', '+1 day')
                ORDER BY race_date, race_time
            """
            df = pd.read_sql(query, conn)
            conn.close()
            
            if not self.logged_initial_races:
                logger.info(f"📊 Found {len(df)} total races in database for today/tomorrow")
                self.logged_initial_races = True
            
            if df.empty:
                return []
            
            aest_tz = pytz.timezone('Australia/Sydney')
            now_aest = datetime.now(aest_tz)
            
            upcoming_races = []
            next_race_info = None
            min_seconds_until = float('inf')
            
            for _, row in df.iterrows():
                # Use the actual timezone from the database (e.g. Australia/Perth, Australia/Sydney)
                race_tz_name = row.get('timezone', 'Australia/Sydney')
                race_tz = pytz.timezone(race_tz_name)
                
                race_datetime_str = f"{row['race_date']} {row['race_time']}"
                # Localize in the race's actual timezone, then convert to AEST for comparison
                race_datetime_local = race_tz.localize(datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M'))
                race_datetime = race_datetime_local.astimezone(aest_tz)
                
                seconds_until = (race_datetime - now_aest).total_seconds()
                
                # Track next upcoming race for logging
                if 0 < seconds_until < min_seconds_until:
                    min_seconds_until = seconds_until
                    next_race_info = (row['venue'], row['race_number'], seconds_until)
                
                # Betting window: 5-50 seconds before race
                # Markets are typically open up to 60s before official time
                # Script will determine which stage to start at based on time remaining
                if 5 <= seconds_until <= 50:
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
                    else:
                        logger.error(f"❌ NO MARKET FOUND: {row['venue']} R{row['race_number']} (in {seconds_until:.0f}s)")
            
            # Store next race info for periodic logging
            self.next_race_info = next_race_info
            
            return upcoming_races
            
        except Exception as e:
            logger.error(f"Error getting upcoming races: {e}")
            return []
    
    def find_market_id(self, venue: str, race_number: int) -> Optional[str]:
        """Find market ID in Betfair database"""
        try:
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
            cursor = conn.cursor()
            
            aest_tz = pytz.timezone('Australia/Sydney')
            today_str = datetime.now(aest_tz).strftime("%-d")
            
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
    
    def get_current_favorite(self, market_id: str) -> Optional[Dict]:
        """
        Get current favorite (lowest odds runner) via LIVE API call
        
        Args:
            market_id: Betfair market ID
        """
        try:
            # Call backend API for LIVE odds from Betfair
            url = f"{BACKEND_URL}/api/GreyhoundMarketBook/market/{market_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"API call failed: {response.status_code}")
                return None
            
            data = response.json()
            runners = data.get('runners', [])
            
            if not runners:
                logger.error(f"No runners in API response for {market_id}")
                return None
            
            logger.info(f"📡 API returned {len(runners)} runners for {market_id}")
            
            # Build odds map - USE LAY ODDS FOR LAY BETTING
            odds_map = []
            for runner in runners:
                selection_id = runner.get('selectionId')
                runner_name = runner.get('runnerName', f'Runner {selection_id}')
                box = runner.get('box')
                ex = runner.get('ex', {})
                available_to_lay = ex.get('availableToLay', [])
                
                if available_to_lay and len(available_to_lay) > 0:
                    best_lay = available_to_lay[0]
                    odds = best_lay.get('price')
                    size = best_lay.get('size', 0)
                    
                    # Include all runners with valid odds > 0
                    if odds and odds > 0 and selection_id:
                        # Clean runner name (remove box number prefix if present)
                        import re
                        clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                        
                        odds_map.append({
                            'selection_id': selection_id,
                            'odds': odds,
                            'size_available': size,
                            'dog_name': clean_name,
                            'box': box
                        })
                else:
                    logger.warning(f"⚠️  {runner_name}: No lay odds available")
            
            logger.info(f"📊 Built odds_map with {len(odds_map)} runners having valid lay odds")
            
            # CRITICAL: If no valid odds, market not active yet - SKIP THIS RACE
            if len(odds_map) == 0:
                logger.info(f"⏰ Waiting for {market_id} market to open...")
                return None
            
            if not odds_map:
                return None
            
            # Sort by odds to find favorite
            odds_map.sort(key=lambda x: x['odds'])
            
            # LOG ALL DOGS AND THEIR ODDS FOR DEBUGGING
            logger.info(f"📋 All dogs sorted by lay odds:")
            for i, dog in enumerate(odds_map[:10]):  # Show top 10
                logger.info(f"   {i+1}. {dog['dog_name']} @ {dog['odds']:.2f}")
            
            favorite = odds_map[0]
            
            # LOG THE FAVORITE FOR DEBUGGING
            logger.info(f"🔍 Favorite found: {favorite['dog_name']} @ {favorite['odds']} (MAX_ODDS={MAX_ODDS})")
            
            # Get total_matched
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite", timeout=30)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TotalMatched FROM MarketCatalogue WHERE MarketId = ?
            """, (market_id,))
            
            total_matched_row = cursor.fetchone()
            total_matched = total_matched_row[0] if total_matched_row else None
            conn.close()
            
            return {
                'selection_id': favorite['selection_id'],
                'dog_name': favorite['dog_name'],
                'box': favorite.get('box'),
                'odds': favorite['odds'],
                'total_matched': total_matched
            }
            
        except Exception as e:
            logger.error(f"Error getting favorite: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def execute_betting_strategy(self, race_info: Dict):
        """
        Execute 3-stage strategy, starting at appropriate stage based on time remaining:
        - Stage 1 (T-45s to T-20s): LIMIT at 5% below current
        - Stage 2 (T-20s to T+10s): REPLACE to current odds (atomic)
        - Stage 3 (T+10s to race start): LIMIT_ON_CLOSE (BSP with fixed $1 stake)
        
        If script starts late, it will skip to the appropriate stage.
        """
        market_id = race_info['market_id']
        seconds_until_race = race_info['seconds_until']
        
        # Determine which stage to start at
        if seconds_until_race >= 40:
            start_stage = 1
        elif seconds_until_race >= 15:
            start_stage = 2
        else:
            start_stage = 3
        
        if start_stage > 1:
            logger.info(f"⏱️  Starting at Stage {start_stage} (race in {seconds_until_race:.0f}s)")
        
        # Keep trying to get favorite until market opens or we're too late
        max_attempts = 50  # Try for up to 50 seconds (covers T-45s to race start)
        favorite = None
        for attempt in range(max_attempts):
            favorite = self.get_current_favorite(market_id)
            
            if not favorite:
                if attempt == 0:
                    logger.info(f"⏰ Waiting for {race_info['venue']} R{race_info['race_number']} market to open...")
                time.sleep(1)
                continue
            
            # Check if odds are valid
            if favorite['odds'] > 0 and favorite['odds'] <= MAX_ODDS and favorite['odds'] >= MIN_ODDS:
                logger.info(f"✅ Market ready after {attempt+1} attempts")
                break  # Got valid odds!
            else:
                logger.warning(f"⚠️  Favorite odds {favorite['odds']:.2f} out of range (MIN={MIN_ODDS}, MAX={MAX_ODDS})")
            
            # Odds out of range - wait and retry
            time.sleep(1)
        else:
            # Exhausted retries
            logger.warning(f"⚠️  Market never opened or odds out of range: {race_info['venue']} R{race_info['race_number']}")
            return
        
        if not favorite:
            logger.error(f"❌ No favorite found: {race_info['venue']} R{race_info['race_number']}")
            return
        
        current_best = favorite['odds']
        logger.info(f"🎯 {race_info['venue']} R{race_info['race_number']}: {favorite['dog_name']} @ {current_best:.2f}")
        
        bet1_id = None
        
        # STAGE 1: Place initial LIMIT bet (if time allows)
        if start_stage == 1:
            bet1_odds = round_to_valid_betfair_odds(max(current_best * 0.95, MIN_ODDS))  # 5% below
            logger.info(f"   Stage 1 (T-45s): LIMIT @ {bet1_odds:.2f} (5% below)")
            
            bet1 = self.place_limit_bet(
                market_id=market_id,
                selection_id=favorite['selection_id'],
                odds=bet1_odds,
                stake=FLAT_STAKE
            )
            
            if not bet1:
                logger.error(f"❌ Stage 1 failed: {race_info['venue']} R{race_info['race_number']}")
                # Continue to Stage 2 anyway
                start_stage = 2
            else:
                bet1_id = bet1['betId']
                logger.info(f"✅ Stage 1: Bet {bet1_id} placed @ {bet1_odds:.2f}")
                self.save_live_trade(race_info, favorite, bet1, current_best)
                
                # Wait for T-20s (25 seconds)
                logger.info(f"⏰ Waiting 25s for Stage 2...")
                time.sleep(25)
                
                # Check if bet already matched
                bet1_status = self.check_bet_status(market_id, bet1_id)
                if bet1_status is None:
                    logger.warning(f"⚠️  Could not check bet status - proceeding with Stage 2 replacement")
                elif bet1_status['status'] == 'MATCHED':
                    logger.info(f"✅ Stage 1 bet matched @ {bet1_status['avgpriceMatched']:.2f} - strategy complete!")
                    return
        
        # STAGE 2: REPLACE to current odds (or place new bet if starting here)
        if start_stage <= 2:
            logger.info(f"🔄 Stage 2: Getting current favorite...")
            current_favorite_t20 = self.get_current_favorite(market_id)
            if not current_favorite_t20:
                logger.warning(f"⚠️  Could not get current favorite at Stage 2")
                return
            
            # If we don't have a bet yet (started at Stage 2), place one now
            if bet1_id is None:
                logger.info(f"   Stage 2 (direct): LIMIT @ current odds")
                bet2_odds = round_to_valid_betfair_odds(max(current_favorite_t20['odds'], MIN_ODDS))
                bet2 = self.place_limit_bet(
                    market_id=market_id,
                    selection_id=current_favorite_t20['selection_id'],
                    odds=bet2_odds,
                    stake=FLAT_STAKE
                )
                if not bet2:
                    logger.error(f"❌ Stage 2 (direct) failed")
                    start_stage = 3  # Skip to Stage 3
                else:
                    bet1_id = bet2['betId']
                    logger.info(f"✅ Stage 2: Bet {bet1_id} placed @ {bet2_odds:.2f}")
                    self.save_live_trade(race_info, current_favorite_t20, bet2, current_favorite_t20['odds'])
                    favorite = current_favorite_t20
            else:
                # We have a bet from Stage 1 - replace or cancel+place based on if favorite changed
                if current_favorite_t20['selection_id'] != favorite['selection_id']:
                    logger.warning(f"⚠️  Favorite changed! Was {favorite['dog_name']}, now {current_favorite_t20['dog_name']}")
                    logger.info(f"🔄 Cancelling old bet, placing new bet on new favorite")
                    self.cancel_bet(market_id, bet1_id)
                    favorite = current_favorite_t20
                    bet2_odds = round_to_valid_betfair_odds(max(favorite['odds'], MIN_ODDS))
                    bet2 = self.place_limit_bet(
                        market_id=market_id,
                        selection_id=favorite['selection_id'],
                        odds=bet2_odds,
                        stake=FLAT_STAKE
                    )
                    if not bet2:
                        logger.error(f"❌ Stage 2 (new favorite) failed")
                        return
                    bet1_id = bet2['betId']
                    logger.info(f"✅ Stage 2: New bet {bet1_id} @ {bet2_odds:.2f} on {favorite['dog_name']}")
                else:
                    # REPLACE existing bet to current odds (atomic operation!)
                    logger.info(f"✅ Favorite unchanged: {favorite['dog_name']}")
                    bet2_odds = round_to_valid_betfair_odds(max(current_favorite_t20['odds'], MIN_ODDS))
                    bet2 = self.replace_bet(
                        market_id=market_id,
                        old_bet_id=bet1_id,
                        selection_id=favorite['selection_id'],
                        new_odds=bet2_odds,
                        stake=FLAT_STAKE
                    )
                    if not bet2:
                        logger.error(f"❌ Stage 2 (replace) failed")
                        return
                    bet1_id = bet2['betId']
                    logger.info(f"✅ Stage 2: REPLACED bet {bet1_id} @ {bet2_odds:.2f}")
            
            # If we placed/replaced a bet, wait before Stage 3
            if start_stage == 2 and bet1_id:
                logger.info(f"⏰ Waiting 20s for Stage 3...")
                time.sleep(20)
                
                # Check if Stage 2 bet already matched
                bet_status = self.check_bet_status(market_id, bet1_id)
                if bet_status and bet_status['status'] == 'MATCHED':
                    logger.info(f"✅ Stage 2 bet matched @ {bet_status['avgpriceMatched']:.2f} - strategy complete!")
                    return
        
        # STAGE 3: BSP fallback (if still unmatched or starting here)
        if bet1_id:
            # Cancel any existing LIMIT bet before placing BSP
            logger.info(f"🔄 Stage 3: Cancelling LIMIT bet, placing BSP bet...")
            self.cancel_bet(market_id, bet1_id)
        else:
            logger.info(f"⏱️  Stage 3 (direct): Placing BSP bet...")
        
        # Get current favorite for BSP bet
        current_favorite_t10 = self.get_current_favorite(market_id)
        if current_favorite_t10:
            favorite = current_favorite_t10
        
        # Place BSP bet with FIXED $1 stake
        # Calculate max BSP price: 2x current odds (100% drift protection)
        max_bsp_odds = round_to_valid_betfair_odds(min(favorite['odds'] * 2.00, MAX_ODDS))
        
        # CRITICAL: Calculate liability for FIXED $1 stake
        # For LAY bets: liability = stake * (odds - 1)
        # So: stake = liability / (odds - 1)
        # We want stake = $1, so: liability = $1 * (max_bsp_odds - 1)
        max_liability = round(FLAT_STAKE * (max_bsp_odds - 1), 2)
        
        bet3 = self.place_bsp_bet(
            market_id=market_id,
            selection_id=favorite['selection_id'],
            max_bsp_price=max_bsp_odds,
            stake=FLAT_STAKE  # This ensures fixed $1 stake
        )
        
        if bet3:
            logger.info(f"✅ Stage 3 (BSP): Bet {bet3['betId']} - FIXED $1 stake, max BSP {max_bsp_odds:.2f}, max liability ${max_liability:.2f}")
            if not bet1_id:  # Only save if we didn't already save in Stage 1/2
                # Create a bet dict for saving
                bet_dict = {'betId': bet3['betId'], 'avgPriceMatched': 0, 'sizeMatched': 0}
                self.save_live_trade(race_info, favorite, bet_dict, favorite['odds'])
        else:
            logger.warning(f"⚠️  Stage 3 (BSP) failed - no coverage")
        
        logger.info(f"🏁 Betting strategy complete for {race_info['venue']} R{race_info['race_number']}.")
        
    def run(self):
        """Main betting loop"""
        logger.info(f"🚨 REAL BETTING STARTED - ${FLAT_STAKE}/bet, Max odds {MAX_ODDS}")
        
        cycle_count = 0
        last_log_time = datetime.now() - timedelta(seconds=31)  # Force immediate log on first cycle
        last_balance_check = datetime.now()
        
        while True:
            try:
                cycle_count += 1
                now = datetime.now()
                
                # Check account balance every 30 minutes
                if (now - last_balance_check).total_seconds() >= 1800:
                    balance = self.get_account_balance()
                    if balance is not None and balance < FLAT_STAKE * 10:
                        logger.warning(f"LOW BALANCE: ${balance:.2f}")
                    last_balance_check = now
                
                # Get upcoming races (T-20s window)
                races = self.get_upcoming_races()
                
                # Log status every 30 seconds
                if (now - last_log_time).total_seconds() >= 30:
                    if len(races) > 0:
                        logger.info(f"🎯 {len(races)} race(s) in betting window")
                    else:
                        if hasattr(self, 'next_race_info') and self.next_race_info:
                            venue, race_num, secs = self.next_race_info
                            mins = int(secs // 60)
                            logger.info(f"⏳ Monitoring... Next: {venue} R{race_num} in {mins}m {int(secs % 60)}s")
                        else:
                            logger.info(f"⏳ Monitoring... No races in 40-50s window")
                    last_log_time = now
                
                # Process each race
                for race in races:
                    # DUPLICATE PROTECTION 1: In-memory check (this session)
                    if race['market_id'] in self.processed_markets:
                        continue
                    
                    # DUPLICATE PROTECTION 2: Database check (all sessions)
                    if self.has_already_bet_on_race(race['market_id']):
                        self.processed_markets.add(race['market_id'])  # Don't check again
                        continue
                    
                    # CHECK DAILY LIMITS BEFORE BETTING
                    can_bet, reason = self.check_daily_limits()
                    if not can_bet:
                        logger.error(f"🛑 STOPPED: {reason}")
                        return  # Exit entirely
                    
                    # Execute 3-stage betting strategy
                    self.execute_betting_strategy(race)
                    
                    # Mark as processed
                    self.processed_markets.add(race['market_id'])
                
                # Sleep between cycles
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping real betting script...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)


if __name__ == "__main__":
    # SAFETY CHECK: Confirm real trading
    print("")
    print("="*80)
    print("🚨 WARNING: REAL MONEY TRADING MODE 🚨")
    print("="*80)
    print(f"This script will place REAL lay bets on Betfair Exchange.")
    print(f"Stake per bet: ${FLAT_STAKE}")
    print(f"Target: Greyhound favorites (Position 1)")
    print(f"Strategy: 3-stage aggressive match + BSP 50% limit")
    print("")
    print("Type 'START REAL TRADING' to continue (case sensitive): ")
    response = input()
    
    if response == "START REAL TRADING":
        print("✅ Starting real trading...")
        print("")
        betting = RealGreyhoundLayBetting()
        betting.run()
    else:
        print("❌ Real trading cancelled")
        print(f"   You typed: '{response}'")
        print(f"   Required: 'START REAL TRADING'")
