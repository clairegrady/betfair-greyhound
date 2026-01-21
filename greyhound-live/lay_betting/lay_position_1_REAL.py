"""
🚨 REAL MONEY Greyhound Lay Betting - Position 1 (Favorite) 🚨
⚠️  WARNING: THIS PLACES REAL BETS WITH REAL MONEY ⚠️

2-STAGE ADAPTIVE STRATEGY:

NORMAL ENTRY (30-60s before race):
- Stage 1 (T-30s): Place LIMIT bet at current odds
- Stage 2 (T-0s): Check match status:
  → Fully matched: Done
  → Partially matched: Place BSP for remainder
  → Unmatched: Place aggressive bet at current +2%

LATE ENTRY (5-29s before race):
- Stage 2 only: Place aggressive bet at current +2% immediately
- Skip Stage 1 (not enough time)

CONCURRENT MODE:
- Can process multiple races simultaneously
- Each race gets its own async task
- No more missed races!

BETTING WINDOW: 5-60 seconds before race start
"""

import pandas as pd
import requests
import time
import pytz
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import sys
import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

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

def add_ticks_to_odds(odds: float, num_ticks: int) -> float:
    """
    Add a specific number of Betfair ticks to the odds.
    For lay betting, adding ticks means HIGHER odds (worse for us, better for matching).
    
    Args:
        odds: Current odds
        num_ticks: Number of ticks to add (typically 2-3 for aggressive matching)
    
    Returns:
        New odds with ticks added
    """
    # Determine tick size based on odds range
    if odds < 2:
        tick_size = 0.01
    elif odds < 3:
        tick_size = 0.02
    elif odds < 4:
        tick_size = 0.05
    elif odds < 6:
        tick_size = 0.1
    elif odds < 10:
        tick_size = 0.2
    elif odds < 20:
        tick_size = 0.5
    elif odds < 30:
        tick_size = 1
    elif odds < 50:
        tick_size = 2
    elif odds < 100:
        tick_size = 5
    else:
        tick_size = 10
    
    # Add the ticks
    new_odds = odds + (tick_size * num_ticks)
    
    # Ensure it's a valid tick (should already be, but just in case)
    return round_to_valid_betfair_odds(new_odds)

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
        self.next_race_info = None  # Store (venue, race_num, race_datetime) for logging
        self.active_tasks = {}  # Track concurrent betting tasks by market_id
        self.task_lock = asyncio.Lock()  # Protect active_tasks dict
        self.logged_initial_races = False
        self.next_race_info = None
        self.no_runners_logged = set()  # Track markets we've already logged "no runners" for
    
    def check_daily_limits(self) -> tuple[bool, str]:
        """Check if we've hit daily risk limits. Returns (can_bet, reason)"""
        try:
            conn = get_db_connection('betfair_trades')
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Check daily bets and NET P&L (not just losses)
            cursor.execute("""
                SELECT 
                    COUNT(*) as bets_today,
                    COALESCE(SUM(profit_loss), 0) as net_pnl_today
                FROM live_trades
                WHERE date = %s AND status != 'FAILED'
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
    
    def get_bet_status(self, bet_id: str, market_id: str) -> Optional[Dict]:
        """
        Get the current status of a bet using listCurrentOrders.
        Returns dict with: sizePlaced, sizeMatched, sizeRemaining, status
        """
        try:
            # Correct endpoint: GET /api/ManageOrders/current
            url = f"{BACKEND_URL}/api/ManageOrders/current"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ listCurrentOrders HTTP {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            # Backend returns raw Betfair response structure
            result = data.get('result', data)
            orders = result.get('currentOrders', [])
            
            if not orders:
                logger.warning(f"⚠️  No current orders found (all may be matched/settled)")
                return None
            
            # Find our specific bet by betId
            order = None
            for o in orders:
                if o.get('betId') == bet_id:
                    order = o
                    break
            
            if not order:
                logger.warning(f"⚠️  Bet {bet_id} not in current orders (likely fully matched or settled)")
                # If bet is not in current orders, it's either fully matched or settled
                # Return a "fully matched" status as best guess
                return {
                    'betId': bet_id,
                    'sizePlaced': 1.0,  # Our standard stake
                    'sizeMatched': 1.0,  # Assume fully matched
                    'sizeRemaining': 0.0,
                    'status': 'EXECUTION_COMPLETE',
                    'averagePriceMatched': 0.0
                }
            
            # Calculate sizePlaced from sizeRemaining + sizeMatched
            size_remaining = order.get('sizeRemaining', 0)
            size_matched = order.get('sizeMatched', 0)
            size_placed = size_remaining + size_matched
            
            return {
                'betId': order.get('betId'),
                'sizePlaced': size_placed,
                'sizeMatched': size_matched,
                'sizeRemaining': size_remaining,
                'status': order.get('status'),
                'averagePriceMatched': order.get('averagePriceMatched', 0)
            }
            
        except Exception as e:
            logger.error(f"❌ Exception in get_bet_status: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def cancel_bet(self, market_id: str, bet_id: str) -> bool:
        """Cancel an existing bet"""
        try:
            logger.info(f"🔍 CANCEL DEBUG → marketId={market_id}, betId={bet_id}")
            
            # Correct endpoint: /api/ManageOrders/cancel with marketId as query param
            url = f"{BACKEND_URL}/api/ManageOrders/cancel?marketId={market_id}"
            
            # Body should be a list of CancelInstruction objects
            payload = [
                {
                    "betId": bet_id
                }
            ]
            
            response = self.session.post(url, json=payload, timeout=15)
            
            logger.info(f"🔍 CANCEL RESPONSE → HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"🔍 CANCEL DATA → {data}")
                result = data.get('result', data)
                
                # Check if cancel was successful
                if result.get('status') == 'SUCCESS':
                    logger.info(f"✅ Cancelled bet {bet_id} - bet was UNMATCHED")
                    return True
                else:
                    # Cancel failed - check the specific error
                    cancel_error = result.get('errorCode', 'UNKNOWN')
                    
                    # INVALID_BET_ID or BET_TAKEN_OR_LAPSED = already matched/settled
                    if cancel_error in ['INVALID_BET_ID', 'BET_TAKEN_OR_LAPSED', 'BET_IN_PROGRESS']:
                        logger.info(f"🎯 CANCEL FAILED → Bet {bet_id} is MATCHED ✅ (errorCode={cancel_error})")
                        return False
                    else:
                        # Other error - might not be matched
                        logger.error(f"❌ CANCEL FAILED with unexpected error: {cancel_error}")
                        logger.error(f"   Full response: {result}")
                        return False
            else:
                logger.error(f"❌ CANCEL HTTP {response.status_code} → {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Exception cancelling bet: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def place_limit_bet(self, market_id: str, selection_id: int, odds: float, stake: float, persistence: str = "LAPSE") -> Optional[Dict]:
        """
        Place a simple LIMIT order
        
        Args:
            persistence: "LAPSE" (cancel if unmatched) or "MARKET_ON_CLOSE" (settle at BSP if unmatched)
        
        Returns:
            Dict with 'betId', 'status', 'sizeMatched', 'avgpriceMatched' if successful, None if failed
        """
        try:
            url = f"{BACKEND_URL}/api/PlaceOrder"
            
            # Log the exact market ID being sent
            logger.info(f"🔍 PLACE BET DEBUG → marketId='{market_id}' (type: {type(market_id).__name__}), selectionId={selection_id}, odds={odds}, stake={stake}, persistence={persistence}")
            
            payload = {
                "marketId": market_id,
                "selectionId": selection_id,
                "stake": stake,
                "side": "L",
                "orderType": "LIMIT",
                "price": odds,
                "persistenceType": persistence,
                "timeInForce": "",
                "customerRef": f"LIMIT-{market_id}-{int(datetime.now().timestamp())}",
                "instructions": [
                    {
                        "selectionId": selection_id,
                        "handicap": 0,
                        "side": "LAY",
                        "orderType": "LIMIT",
                        "persistenceType": persistence,
                        "timeInForce": "",
                        "limitOrder": {
                            "size": stake,
                            "price": odds,
                            "persistenceType": persistence
                        }
                    }
                ]
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if it's an error response (has 'error' key)
                if 'error' in data:
                    error_data = data.get('error', {}).get('data', {}).get('APINGException', {})
                    error_code = error_data.get('errorCode', 'UNKNOWN')
                    error_msg = error_data.get('errorDetails', 'unknown error')
                    
                    if error_code == 'INVALID_INPUT_DATA' and 'invalid' in error_msg.lower():
                        logger.warning(f"⚠️  Market {market_id} is CLOSED/SUSPENDED - Betfair: {error_msg}")
                    else:
                        logger.error(f"❌ BETFAIR API ERROR: {error_code} - {error_msg}")
                    
                    logger.error(f"Full error response: {data}")
                    return None
                
                result = data.get('result', data)
                
                if result.get('status') == 'SUCCESS':
                    instruction_reports = result.get('instructionReports', [])
                    if instruction_reports:
                        report = instruction_reports[0]
                        
                        if report.get('status') == 'SUCCESS':
                            bet_id = report.get('betId')
                            size_matched = report.get('sizeMatched', 0)
                            avg_price = report.get('averagePriceMatched', odds)
                            
                            return {
                                'betId': bet_id,
                                'status': 'MATCHED' if size_matched > 0 else 'UNMATCHED',
                                'sizeMatched': size_matched,
                                'avgpriceMatched': avg_price
                            }
                        else:
                            # Instruction failed
                            logger.error(f"❌ BET INSTRUCTION FAILED: status={report.get('status')}, errorCode={report.get('errorCode')}, {report}")
                            return None
                    else:
                        logger.error(f"❌ NO INSTRUCTION REPORTS in response: {result}")
                        return None
                else:
                    logger.error(f"❌ API STATUS != SUCCESS: {result.get('status')}, errorCode={result.get('errorCode')}")
                    logger.error(f"Full response: {data}")
                    return None
            else:
                logger.error(f"❌ HTTP {response.status_code}: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception placing limit bet: {e}")
            return None
    
    def cancel_and_place_bet(self, market_id: str, old_bet_id: str, selection_id: int, new_odds: float, stake: float) -> Optional[Dict]:
        """
        CANCEL existing bet and PLACE new bet (safer than replaceOrders for greyhounds)
        
        This avoids DSC-0018 errors caused by:
        - Partially matched bets (replaceOrders rejects these)
        - Market timing issues (greyhounds freeze replacements close to start)
        - Invalid tick sizes
        
        Args:
            market_id: Market ID
            old_bet_id: Existing bet ID to cancel
            selection_id: Runner selection ID for new bet
            new_odds: New odds to place at (must be valid Betfair tick)
            stake: Stake amount
        
        Returns:
            Dict with new 'betId', 'status', 'sizeMatched', 'avgpriceMatched' if successful, None if failed
        """
        try:
            # STEP 1: Cancel the old bet using the correct endpoint
            cancel_url = f"{BACKEND_URL}/api/ManageOrders/cancel?marketId={market_id}"
            
            # Body should be a list of CancelInstruction objects
            cancel_payload = [
                {
                    "betId": old_bet_id
                }
            ]
            
            logger.info(f"🔍 CANCEL DEBUG → marketId={market_id}, betId={old_bet_id}")
            cancel_response = self.session.post(cancel_url, json=cancel_payload, timeout=10)
            
            if cancel_response.status_code != 200:
                logger.info(f"🎯 CANCEL FAILED → Bet {old_bet_id} is MATCHED ✅ (no replacement needed)")
                return None  # Don't place new bet if cancel failed
            
            cancel_data = cancel_response.json()
            cancel_result = cancel_data.get('result', cancel_data)
            
            if cancel_result.get('status') != 'SUCCESS':
                logger.info(f"🎯 CANCEL FAILED → Bet {old_bet_id} is MATCHED ✅ (no replacement needed)")
                return None
            
            logger.info(f"✅ Cancelled bet {old_bet_id} (was UNMATCHED)")
            
            # STEP 2: Place new bet at updated odds
            # Snap odds to valid Betfair tick
            snapped_odds = round_to_valid_betfair_odds(new_odds)
            if snapped_odds != new_odds:
                logger.info(f"📊 Snapped {new_odds:.2f} → {snapped_odds:.2f} (valid tick)")
            
            place_result = self.place_limit_bet(market_id, selection_id, snapped_odds, stake)
            
            if place_result:
                logger.info(f"✅ Placed new bet {place_result['betId']} @ {snapped_odds:.2f}")
                return place_result
            else:
                logger.error("❌ Failed to place new bet after cancel")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception in cancel_and_place: {e}")
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
                
                # Check if it's an error response (has 'error' key)
                if 'error' in data:
                    error_data = data.get('error', {}).get('data', {}).get('APINGException', {})
                    error_code = error_data.get('errorCode', 'UNKNOWN')
                    error_msg = error_data.get('errorDetails', 'unknown error')
                    
                    logger.error(f"❌ BSP BETFAIR API ERROR: {error_code} - {error_msg}")
                    logger.error(f"Full error response: {data}")
                    return None
                
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
                        else:
                            logger.error(f"❌ BSP INSTRUCTION FAILED: status={report.get('status')}, errorCode={report.get('errorCode')}, {report}")
                            return None
                    else:
                        logger.error(f"❌ NO INSTRUCTION REPORTS in BSP response: {result}")
                        return None
                else:
                    logger.error(f"❌ BSP API STATUS != SUCCESS: {result.get('status')}, errorCode={result.get('errorCode')}")
                    logger.error(f"Full response: {data}")
                    return None
            else:
                logger.error(f"BSP bet HTTP {response.status_code}: {response.text[:500]}")
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
            conn = get_db_connection('betfair_trades')
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            
        except Exception as db_error:
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
            conn = get_db_connection('betfair_trades')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM live_trades 
                WHERE market_id = %s AND status != 'FAILED'
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
            conn = get_db_connection('betfair_races')
            cursor = conn.cursor()
            
            # Use cursor instead of pandas to avoid SQLAlchemy warning
            query = """
                SELECT venue, race_number, race_time, race_date, country, timezone
                FROM greyhound_race_times
                WHERE race_date::date >= CURRENT_DATE
                AND race_date::date <= CURRENT_DATE + INTERVAL '1 day'
                ORDER BY race_date, race_time
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            if not self.logged_initial_races:
                logger.info(f"📊 Found {len(rows)} total races in database for today/tomorrow")
                self.logged_initial_races = True
            
            if not rows:
                return []
            
            aest_tz = pytz.timezone('Australia/Sydney')
            now_aest = datetime.now(aest_tz)
            
            upcoming_races = []
            next_race_info = None
            min_seconds_until = float('inf')
            
            for row in rows:
                venue, race_number, race_time, race_date, country, timezone_str = row
                
                # IMPORTANT: DB stores ALL times in AEST (converted by scraper)
                # Parse as naive datetime, then localize to AEST
                aest_tz = pytz.timezone('Australia/Sydney')
                
                race_datetime_str = f"{race_date} {race_time}"
                race_datetime_naive = datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M')
                race_datetime = aest_tz.localize(race_datetime_naive)
                
                seconds_until = (race_datetime - now_aest).total_seconds()
                
                # Track next upcoming race for logging (within 20 minutes, not 16 hours!)
                if 0 < seconds_until < min_seconds_until and seconds_until <= 1200:  # Max 20 minutes
                    min_seconds_until = seconds_until
                    next_race_info = (venue, race_number, race_datetime)  # Store race_datetime instead of seconds
                
                # Betting window: 5-60 seconds before race time
                # 30-60s: Full strategy (Stage 1 + Stage 2)
                # 5-29s: Late entry (Stage 2 only - aggressive bet)
                if 5 <= seconds_until <= 60:
                    market_id = self.find_market_id(venue, race_number)
                    if market_id:
                        upcoming_races.append({
                            'venue': venue,
                            'country': country or 'AUS',
                            'race_number': race_number,
                            'market_id': market_id,
                            'seconds_until': seconds_until,
                            'race_datetime': race_datetime
                        })
                    else:
                        logger.error(f"❌ NO MARKET FOUND: {venue} R{race_number} (in {seconds_until:.0f}s)")
            
            # Store next race info for periodic logging
            self.next_race_info = next_race_info
            
            return upcoming_races
            
        except Exception as e:
            logger.error(f"Error getting upcoming races: {e}")
            return []
    
    def find_market_id(self, venue: str, race_number: int) -> Optional[str]:
        """Find market ID in Betfair database"""
        try:
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            aest_tz = pytz.timezone('Australia/Sydney')
            today_str = datetime.now(aest_tz).strftime("%-d")
            
            query = """
                SELECT marketid
                FROM marketcatalogue
                WHERE eventname ILIKE %s
                AND marketname ILIKE %s
                AND eventtypename = 'Greyhound Racing'
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
    
    def check_market_status(self, market_id: str) -> Optional[Dict]:
        """
        Check actual market status from Betfair (OPEN/SUSPENDED/CLOSED)
        Returns: {
            'status': 'OPEN'|'SUSPENDED'|'CLOSED'|'NOT_FOUND',
            'inplay': True/False,
            'betDelay': int (seconds),
            'numberOfActiveRunners': int
        }
        """
        try:
            url = f"{BACKEND_URL}/api/GreyhoundMarketBook/status/{market_id}"
            response = self.session.get(url, timeout=5)
            
            if response.status_code == 404:
                logger.debug(f"Market {market_id} not yet available (404)")
                return {'status': 'NOT_FOUND'}
            
            if response.status_code != 200:
                logger.warning(f"⚠️  Cannot check market status (HTTP {response.status_code})")
                return None
            
            data = response.json()
            return {
                'status': data.get('status'),
                'inplay': data.get('inplay', False),
                'betDelay': data.get('betDelay', 0),
                'numberOfActiveRunners': data.get('numberOfActiveRunners', 0)
            }
            
        except Exception as e:
            logger.warning(f"Exception checking market status: {e}")
            return None
    
    def get_odds_from_db(self, market_id: str) -> Optional[Dict]:
        """Fallback: Get odds directly from greyhoundmarketbook table"""
        try:
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            # First, get runner names from marketcatalogue_runners (more reliable)
            cursor.execute("""
                SELECT selectionid, runnername, sortpriority
                FROM marketcatalogue_runners
                WHERE marketid = %s
            """, (market_id,))
            
            name_map = {}
            box_map = {}
            for sel_id, name, sort in cursor.fetchall():
                if name:
                    name_map[sel_id] = name
                if sort:
                    box_map[sel_id] = sort
            
            # FOR LAY BETTING: Get ONLY LAY odds for this market
            query = """
                SELECT DISTINCT selectionid, price, runnername, box
                FROM greyhoundmarketbook
                WHERE marketid = %s
                AND pricetype = 'AvailableToLay'
                AND price IS NOT NULL
                AND price > 0
                ORDER BY selectionid, price ASC
            """
            
            cursor.execute(query, (market_id,))
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                logger.warning(f"❌ No lay prices in DB for market {market_id}")
                return None
            
            # Group by selectionid and take best (lowest) lay price
            import re
            runners_dict = {}
            
            for sel_id, price, runner_name, box in results:
                if sel_id not in runners_dict:
                    # Prioritize name from marketcatalogue_runners
                    if sel_id in name_map:
                        clean_name = name_map[sel_id]
                    elif runner_name:
                        clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    else:
                        clean_name = f'Dog {sel_id}'
                    
                    # Prioritize box from marketcatalogue_runners
                    final_box = box_map.get(sel_id) or box
                    
                    runners_dict[sel_id] = {
                        'selection_id': sel_id,
                        'odds': price,
                        'dog_name': clean_name,
                        'box': final_box,
                        'size_available': 0
                    }
            
            odds_map = list(runners_dict.values())
            if not odds_map:
                return None
            
            # Sort by odds to find favorite
            odds_map.sort(key=lambda x: x['odds'])
            
            logger.info(f"📊 DB Fallback: Found {len(odds_map)} runners with lay odds")
            logger.warning(f"⚠️  USING DB FALLBACK (may be stale)")
            logger.info(f"📋 Top 5 from DB:")
            for i, dog in enumerate(odds_map[:5]):
                logger.info(f"   {i+1}. {dog['dog_name']} @ {dog['odds']:.2f}")
            
            favorite = odds_map[0]
            
            # Get total_matched
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT totalmatched FROM marketcatalogue WHERE marketid = %s
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
            logger.error(f"Error getting odds from DB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_current_favorite(self, market_id: str) -> Optional[Dict]:
        """
        Get current favorite (lowest odds runner) via LIVE API call
        Falls back to DB if API fails
        
        Args:
            market_id: Betfair market ID
        """
        try:
            # Call backend API for LIVE odds from Betfair
            url = f"{BACKEND_URL}/api/GreyhoundMarketBook/market/{market_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"⚠️  API returned {response.status_code}, trying DB fallback")
                return self.get_odds_from_db(market_id)
            
            data = response.json()
            
            # DEBUG: Log what the API actually returns
            logger.info(f"🔍 API Response keys: {list(data.keys())}")
            
            # GreyhoundMarketBookController returns 'odds' as flat array
            odds_data = data.get('odds', [])
            
            if not odds_data:
                # Try DB fallback
                if market_id not in self.no_runners_logged:
                    logger.warning(f"⚠️  No odds data in API response, trying DB fallback")
                    self.no_runners_logged.add(market_id)
                return self.get_odds_from_db(market_id)
            
            logger.info(f"📡 API returned {len(odds_data)} price points for {market_id}")
            logger.info(f"✅ USING API ODDS (real-time)")
            
            # Get runner names from database - prioritize marketcatalogue_runners
            conn = get_db_connection('betfairmarket')
            cursor = conn.cursor()
            
            # First get from marketcatalogue_runners (more reliable)
            cursor.execute("""
                SELECT selectionid, runnername, sortpriority
                FROM marketcatalogue_runners
                WHERE marketid = %s
            """, (market_id,))
            
            runner_names = {}
            box_numbers = {}
            for sel_id, name, sort in cursor.fetchall():
                if name:
                    runner_names[sel_id] = name
                if sort:
                    box_numbers[sel_id] = sort
            
            # Fallback to greyhoundmarketbook if needed
            cursor.execute("""
                SELECT DISTINCT selectionid, runnername, box
                FROM greyhoundmarketbook
                WHERE marketid = %s
            """, (market_id,))
            
            import re
            for sel_id, runner_name, box in cursor.fetchall():
                # Only use if not already in runner_names
                if sel_id not in runner_names and runner_name:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    runner_names[sel_id] = clean_name
                # Only use box if not already set
                if sel_id not in box_numbers and box:
                    box_numbers[sel_id] = box
            
            # Build odds map from the 'odds' array, grouping by selectionid
            # FOR LAY BETTING: Use the best (lowest) lay price available
            selection_lay_odds = {}
            
            for odd in odds_data:
                sel_id = odd.get('selectionid')
                price = odd.get('price')
                pricetype = odd.get('pricetype')
                
                if sel_id and price and price > 0 and pricetype == 'AvailableToLay':
                    # For lay betting, take the LOWEST lay price (best price to lay at)
                    if sel_id not in selection_lay_odds or price < selection_lay_odds[sel_id]:
                        selection_lay_odds[sel_id] = price
            
            # Only proceed if we have lay prices
            if not selection_lay_odds:
                logger.warning(f"❌ No lay prices available for market {market_id}")
                if market_id not in self.no_runners_logged:
                    logger.info(f"⏰ Waiting for {market_id} market to open...")
                    self.no_runners_logged.add(market_id)
                return None
            
            # Build odds map
            odds_map = []
            for sel_id, odds in selection_lay_odds.items():
                odds_map.append({
                    'selection_id': sel_id,
                    'odds': odds,
                    'dog_name': runner_names.get(sel_id, f'Dog {sel_id}'),
                    'box': box_numbers.get(sel_id)
                })
            
            if not odds_map:
                return None
            
            # Sort by odds to find favorite
            odds_map.sort(key=lambda x: x['odds'])
            
            if len(odds_map) < 2:
                logger.warning(f"⚠️  Only {len(odds_map)} runner(s) - skipping race (need at least 2)")
                return None
            
            favorite = odds_map[0]
            second_favorite = odds_map[1]
            
            # RISK CHECK: Skip if 2nd favorite odds > 3x favorite odds
            # This indicates a VERY dominant favorite with high risk
            odds_ratio = second_favorite['odds'] / favorite['odds']
            if odds_ratio > 4.0:
                logger.warning(f"⚠️  SKIPPING RACE - Favorite too dominant!")
                logger.warning(f"   1st: {favorite['dog_name']} @ {favorite['odds']:.2f}")
                logger.warning(f"   2nd: {second_favorite['dog_name']} @ {second_favorite['odds']:.2f}")
                logger.warning(f"   Ratio: {odds_ratio:.2f}x (limit: 4.0x)")
                return {'dominant_favorite': True}  # Return flag instead of None
            
            logger.debug(f"✅ Odds spread OK: 1st={favorite['odds']:.2f}, 2nd={second_favorite['odds']:.2f}, ratio={odds_ratio:.2f}x")
            
            # Get total_matched
            cursor.execute("""
                SELECT totalmatched FROM marketcatalogue WHERE marketid = %s
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
        Execute 2-stage strategy with partial match detection:
        - Stage 1 (T-30s): LIMIT at current -3% (aggressive, tries to get matched early)
        - Stage 2 (T-0s):  Check for partial match:
            - If FULLY matched → done
            - If PARTIALLY matched → place BSP for remainder
            - If UNMATCHED → skip (too late for BSP)
        
        Timing:
        - 30 seconds between Stage 1 and Stage 2 (T-30s to T-0s)
        
        If script starts late, it will skip to the appropriate stage.
        """
        market_id = race_info['market_id']
        seconds_until_race = race_info['seconds_until']
        
        # Determine which stage to start at
        if seconds_until_race >= 28:  # T-30s window (28-60s before)
            start_stage = 1
        elif seconds_until_race >= 5:  # Late entry (5-27s before)
            start_stage = 2
        else:  # < 5s - too late
            logger.warning(f"⚠️  Race in {seconds_until_race:.0f}s - TOO LATE (need 5s minimum)")
            return
        
        if start_stage == 2:
            logger.info(f"⚡ LATE ENTRY: Starting at Stage 2 (race in {seconds_until_race:.0f}s)")
        
        # Check market status from Betfair (OPEN/SUSPENDED/CLOSED)
        market_status = self.check_market_status(market_id)
        if market_status:
            status = market_status.get('status')
            inplay = market_status.get('inplay', False)
            bet_delay = market_status.get('betDelay', 0)
            
            if status == 'NOT_FOUND':
                logger.warning(f"⏰ Market {market_id} NOT YET AVAILABLE on Betfair")
                logger.info(f"   Race may be delayed or market not created yet")
                return
            
            elif status == 'CLOSED':
                logger.warning(f"🏁 Market {market_id} is CLOSED")
                logger.info(f"   Race already completed or abandoned")
                return
            
            elif status == 'SUSPENDED':
                # Check if it's suspended because race is about to start (bet_delay > 0)
                if bet_delay > 0:
                    logger.info(f"⏸️  Market SUSPENDED with {bet_delay}s bet delay → Race imminent!")
                else:
                    logger.warning(f"⏸️  Market {market_id} is SUSPENDED (race may be delayed)")
                    logger.info(f"   Waiting for market to reopen...")
                    return
            
            elif status == 'OPEN':
                num_runners = market_status.get('numberOfActiveRunners', 0)
                
                # CRITICAL: Check if race is actually about to start
                # If bet_delay is 0 and not inplay, the race might be delayed!
                if bet_delay == 0 and not inplay and seconds_until_race < 45:
                    logger.warning(f"⚠️  Market OPEN but bet_delay=0 (race likely DELAYED)")
                    logger.info(f"   Scheduled: in {seconds_until_race:.0f}s, but market shows no imminent start")
                    logger.info(f"   Skipping this attempt - will retry when race is actually starting")
                    return
                
                logger.info(f"✅ Market OPEN → {num_runners} runners, bet_delay={bet_delay}s, inplay={inplay}")
            else:
                logger.warning(f"⚠️  Unknown market status: {status}")
        else:
            logger.warning(f"⚠️  Could not retrieve market status - proceeding with caution")
        
        # Keep trying to get favorite until market opens√ or we're too late
        max_attempts = 50  # Try for up to 50 seconds (covers T-45s to race start)
        favorite = None
        dominant_favorite_count = 0  # Track how many times in a row we see dominant favorite
        
        for attempt in range(max_attempts):
            favorite = self.get_current_favorite(market_id)
            
            # Check for dominant favorite flag (but give it a few chances to change)
            if favorite and favorite.get('dominant_favorite'):
                dominant_favorite_count += 1
                
                # Only skip if we've seen dominant favorite 3+ times in a row
                # OR if we're very close to race start (< 10s) and still dominant
                seconds_remaining = (race_info['race_datetime'] - datetime.now(pytz.timezone('Australia/Sydney'))).total_seconds()
                
                if dominant_favorite_count >= 3:
                    logger.warning(f"⚠️  Race skipped - dominant favorite persists after {dominant_favorite_count} checks")
                    return
                elif seconds_remaining < 10:
                    logger.warning(f"⚠️  Race skipped - dominant favorite still present at T-{seconds_remaining:.0f}s")
                    return
                else:
                    # Keep checking - odds might change
                    logger.info(f"   ⏰ Dominant favorite detected ({dominant_favorite_count}/3 checks), waiting for odds to change...")
                    time.sleep(2)  # Wait a bit longer between checks
                    continue
            else:
                # Reset counter if no longer dominant
                if dominant_favorite_count > 0:
                    logger.info(f"   ✅ Odds improved - no longer dominant favorite!")
                dominant_favorite_count = 0
            
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
        
        # Variables for Stage 2 and 3
        bet1_id = None
        bet2_id = None
        bet1_odds = None
        
        # STAGE 1: Place initial LIMIT bet (only if we have time)
        if start_stage == 1:
            bet1_odds = round_to_valid_betfair_odds(min(current_best, MAX_ODDS))
            logger.info(f"   Stage 1 (T-30s): LIMIT @ {bet1_odds:.2f} (current odds, LAPSE)")
            
            bet1 = self.place_limit_bet(
                market_id=market_id,
                selection_id=favorite['selection_id'],
                odds=bet1_odds,
                stake=FLAT_STAKE,
                persistence="LAPSE"
            )
            
            if not bet1:
                logger.error(f"❌ Stage 1 failed: {race_info['venue']} R{race_info['race_number']} (see bet placement error above)")
                return
            
            bet1_id = bet1['betId']
            logger.info(f"✅ Stage 1: Bet {bet1_id} placed @ {bet1_odds:.2f}")
            self.save_live_trade(race_info, favorite, bet1, current_best)
            
            # Wait 30 seconds for Stage 2 (T-30s to T-0s = race start)
            logger.info(f"⏰ Waiting 30s for Stage 2 (race start)...")
            time.sleep(30)
        
        # STAGE 2 (T-0s = race start): Check Stage 1 status, if unmatched cancel and replace
        if start_stage == 1 and bet1_id:
            logger.info(f"🔍 Stage 2 (race start): Checking Stage 1 status...")
            bet_status = self.get_bet_status(bet1_id, market_id)
            
            if not bet_status:
                logger.error(f"❌ Could not get bet status for {bet1_id} - backend error")
                logger.info(f"🏁 Betting complete (cannot verify match status)")
                return
            
            size_matched = bet_status['sizeMatched']
            size_remaining = bet_status['sizeRemaining']
            
            logger.info(f"📊 Stage 1 Status: matched=${size_matched:.2f}, remaining=${size_remaining:.2f}")
            
            if size_remaining == 0:
                # FULLY MATCHED - we're done!
                logger.info(f"✅ Stage 1 FULLY MATCHED → ${size_matched:.2f} @ {bet_status['averagePriceMatched']:.2f}")
                logger.info(f"🏁 Betting complete")
                return
            
            # Stage 1 is UNMATCHED or PARTIALLY MATCHED
            # Cancel entire Stage 1 and place Stage 2
            if size_matched == 0:
                logger.info(f"⚪ Stage 1 UNMATCHED → Canceling and placing Stage 2")
            else:
                logger.info(f"🟡 Stage 1 PARTIALLY MATCHED (${size_matched:.2f}) → Canceling and placing Stage 2 for FULL stake")
            
            # Cancel Stage 1
            cancel_success = self.cancel_bet(market_id, bet1_id)
            if not cancel_success:
                logger.error(f"❌ Failed to cancel Stage 1 bet {bet1_id}")
                logger.warning(f"⚠️  Stage 1 may still be active - not placing Stage 2")
                logger.info(f"🏁 Betting complete (Stage 1 still active)")
                return
            
            logger.info(f"✅ Stage 1 canceled successfully")
            
            # Get fresh current odds for Stage 2
            current_favorite = self.get_current_favorite(market_id)
            if not current_favorite:
                logger.warning(f"⚠️  Could not get current favorite for Stage 2")
                logger.info(f"🏁 Betting complete (no coverage)")
                return
            
            # Place Stage 2 at fresh current odds, LAPSE persistence
            stage2_odds = round_to_valid_betfair_odds(current_favorite['odds'])
            stage2_odds = min(stage2_odds, MAX_ODDS)
            
            bet2 = self.place_limit_bet(
                market_id=market_id,
                selection_id=current_favorite['selection_id'],
                odds=stage2_odds,
                stake=FLAT_STAKE,
                persistence="LAPSE"
            )
            
            if not bet2:
                logger.warning(f"⚠️  Stage 2 bet failed - no coverage")
                logger.info(f"🏁 Betting complete")
                return
            
            bet2_id = bet2['betId']
            logger.info(f"✅ Stage 2: Bet {bet2_id} placed @ {stage2_odds:.2f} (fresh current odds, LAPSE)")
            
            # Wait 10 seconds for Stage 3 (race start to T+10s)
            logger.info(f"⏰ Waiting 10s for Stage 3 (T+10s after race start)...")
            time.sleep(10)
            
            # STAGE 3 (T+10s): Check Stage 2 status, if unmatched place BSP
            logger.info(f"🔍 Stage 3 (T+10s): Checking Stage 2 status...")
            bet2_status = self.get_bet_status(bet2_id, market_id)
            
            if not bet2_status:
                logger.error(f"❌ Could not get Stage 2 bet status for {bet2_id}")
                logger.info(f"🏁 Betting complete (cannot verify Stage 2 status)")
                return
            
            size_matched_2 = bet2_status['sizeMatched']
            size_remaining_2 = bet2_status['sizeRemaining']
            
            logger.info(f"📊 Stage 2 Status: matched=${size_matched_2:.2f}, remaining=${size_remaining_2:.2f}")
            
            if size_remaining_2 == 0:
                # FULLY MATCHED - we're done!
                logger.info(f"✅ Stage 2 FULLY MATCHED → ${size_matched_2:.2f} @ {bet2_status['averagePriceMatched']:.2f}")
                logger.info(f"🏁 Betting complete")
                return
            
            # Stage 2 is UNMATCHED or PARTIALLY MATCHED - place BSP for full stake
            if size_matched_2 == 0:
                logger.info(f"⚪ Stage 2 UNMATCHED → Placing BSP bet for FULL stake")
                bsp_stake = FLAT_STAKE
            else:
                logger.info(f"🟡 Stage 2 PARTIALLY MATCHED (${size_matched_2:.2f}) → Placing BSP for FULL stake")
                bsp_stake = FLAT_STAKE
            
            # Place BSP bet
            max_bsp_odds = round_to_valid_betfair_odds(min(current_favorite['odds'] * 2.00, MAX_ODDS))
            
            bet3 = self.place_bsp_bet(
                market_id=market_id,
                selection_id=current_favorite['selection_id'],
                max_bsp_price=max_bsp_odds,
                stake=bsp_stake
            )
            
            if bet3:
                logger.info(f"✅ Stage 3 (BSP): Bet {bet3['betId']} placed - ${bsp_stake:.2f} stake, max BSP {max_bsp_odds:.2f}")
            else:
                logger.warning(f"⚠️  Stage 3 (BSP) failed - coverage incomplete")
            
            logger.info(f"🏁 Betting complete")
        
        else:
            # Late entry path (5-29s before race)
            # Just place Stage 2 at race start, then Stage 3 BSP 10s after
            logger.info(f"⚡ LATE ENTRY: Placing Stage 2 at race start + Stage 3 BSP 10s after")
            
            # Calculate when race actually starts
            seconds_until_race = (race_info['race_datetime'] - datetime.now(pytz.timezone('Australia/Sydney'))).total_seconds()
            
            # Wait until race start
            if seconds_until_race > 0:
                logger.info(f"⏰ Waiting {seconds_until_race:.0f}s for race start (Stage 2)...")
                time.sleep(seconds_until_race)
            
            # Stage 2: Place LIMIT at race start
            logger.info(f"🔍 Late Stage 2 (race start): Placing LIMIT bet")
            
            stage2_odds = round_to_valid_betfair_odds(current_best)
            stage2_odds = min(stage2_odds, MAX_ODDS)
            
            bet2 = self.place_limit_bet(
                market_id=market_id,
                selection_id=favorite['selection_id'],
                odds=stage2_odds,
                stake=FLAT_STAKE,
                persistence="LAPSE"
            )
            
            if not bet2:
                logger.error(f"❌ Late Stage 2 failed: {race_info['venue']} R{race_info['race_number']}")
                logger.info(f"🏁 Betting complete (no coverage)")
                return
            
            bet2_id = bet2['betId']
            logger.info(f"✅ Late Stage 2: Bet {bet2_id} placed @ {stage2_odds:.2f} (LAPSE)")
            self.save_live_trade(race_info, favorite, bet2, current_best)
            
            # Wait 10 seconds for Stage 3
            logger.info(f"⏰ Waiting 10s for Stage 3 (T+10s after race start)...")
            time.sleep(10)
            
            # Stage 3: Check if matched, if not place BSP
            logger.info(f"🔍 Late Stage 3 (T+10s): Checking Stage 2 status...")
            bet2_status = self.get_bet_status(bet2_id, market_id)
            
            if bet2_status and bet2_status['sizeRemaining'] == 0:
                logger.info(f"✅ Late Stage 2 FULLY MATCHED → ${bet2_status['sizeMatched']:.2f} @ {bet2_status['averagePriceMatched']:.2f}")
                logger.info(f"🏁 Betting complete")
                return
            
            # Place BSP for full stake
            logger.info(f"⚪ Late Stage 2 not fully matched → Placing BSP")
            max_bsp_odds = round_to_valid_betfair_odds(min(current_best * 2.00, MAX_ODDS))
            
            bet3 = self.place_bsp_bet(
                market_id=market_id,
                selection_id=favorite['selection_id'],
                max_bsp_price=max_bsp_odds,
                stake=FLAT_STAKE
            )
            
            if bet3:
                logger.info(f"✅ Late Stage 3 (BSP): Bet {bet3['betId']} placed - max BSP {max_bsp_odds:.2f}")
            else:
                logger.warning(f"⚠️  Late Stage 3 (BSP) failed")
            
            logger.info(f"🏁 Betting complete")
        
    async def execute_betting_strategy_async(self, race_info: Dict):
        """Async wrapper for execute_betting_strategy - runs in thread pool"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.execute_betting_strategy, race_info)
    
    async def run_async(self):
        """Main async betting loop with concurrent race handling"""
        logger.info(f"🚨 REAL BETTING STARTED - ${FLAT_STAKE}/bet, Max odds {MAX_ODDS}")
        logger.info(f"🔀 CONCURRENT MODE: Can handle multiple simultaneous races")
        
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
                
                # Get upcoming races (T-30s to T-60s window)
                races = self.get_upcoming_races()
                
                # Clean up completed tasks
                async with self.task_lock:
                    completed_markets = [m for m, task in self.active_tasks.items() if task.done()]
                    for market_id in completed_markets:
                        del self.active_tasks[market_id]
                
                # Log status every 30 seconds
                if (now - last_log_time).total_seconds() >= 30:
                    active_count = len(self.active_tasks)
                    if active_count > 0:
                        logger.info(f"🔀 {active_count} race(s) currently being processed")
                    
                    if len(races) > 0:
                        logger.info(f"🎯 {len(races)} race(s) in betting window")
                    else:
                        if hasattr(self, 'next_race_info') and self.next_race_info:
                            venue, race_num, race_datetime = self.next_race_info
                            # Recalculate seconds_until NOW (don't use stale value)
                            now_aest = datetime.now(pytz.timezone('Australia/Sydney'))
                            secs = (race_datetime - now_aest).total_seconds()
                            mins = int(secs // 60)
                            secs_remainder = int(secs % 60)
                            logger.info(f"⏳ Monitoring... Next: {venue} R{race_num} in {mins}m {secs_remainder}s")
                        else:
                            logger.info("⏳ Monitoring... No upcoming races in betting window.")
                    last_log_time = now
                
                # Process each race concurrently
                for race in races:
                    market_id = race['market_id']
                    
                    # DUPLICATE PROTECTION 1: In-memory check (this session)
                    if market_id in self.processed_markets:
                        continue
                    
                    # DUPLICATE PROTECTION 2: Check if already processing this race
                    async with self.task_lock:
                        if market_id in self.active_tasks:
                            continue  # Already being processed
                    
                    # DUPLICATE PROTECTION 3: Database check (all sessions)
                    if self.has_already_bet_on_race(market_id):
                        self.processed_markets.add(market_id)  # Don't check again
                        continue
                    
                    # CHECK DAILY LIMITS BEFORE BETTING
                    can_bet, reason = self.check_daily_limits()
                    if not can_bet:
                        logger.error(f"🛑 STOPPED: {reason}")
                        return  # Exit entirely
                    
                    # Start concurrent task for this race
                    logger.info(f"🚀 Starting concurrent task for {race['venue']} R{race['race_number']}")
                    async with self.task_lock:
                        self.active_tasks[market_id] = asyncio.create_task(
                            self.execute_betting_strategy_async(race)
                        )
                    
                    # Mark as processed
                    self.processed_markets.add(market_id)
                
                # Sleep between cycles
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("🛑 Stopping real betting script...")
                # Wait for active tasks to complete
                if self.active_tasks:
                    logger.info(f"⏳ Waiting for {len(self.active_tasks)} active tasks to complete...")
                    await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    def run(self):
        """Entry point - starts async event loop"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown complete")



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
