"""
Check and settle REAL greyhound lay bets (live trading)
Fetches actual results from Betfair and updates live_trades database
"""

import sqlite3
import requests
import logging
from datetime import datetime, timedelta
import sys
import os
import csv

sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/utilities')
from db_connection_helper import get_db_connection

LIVE_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/live_trades_greyhounds.db"
BACKEND_URL = "http://localhost:5173"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_unsettled_bets():
    """Get all bets that haven't been settled yet"""
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, market_id, betfair_bet_id, dog_name, initial_odds_requested, stake, liability, 
               position_in_market, selection_id, venue, race_number, date
        FROM live_trades
        WHERE result = 'pending' AND status != 'FAILED'
        ORDER BY created_at
    """)
    
    bets = cursor.fetchall()
    conn.close()
    return bets


def fetch_race_results(market_ids: list) -> dict:
    """Fetch race results from backend API"""
    try:
        url = f"{BACKEND_URL}/api/results/settled"
        response = requests.post(
            url,
            json={"marketIds": market_ids},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('markets', {})
        
        logger.error(f"Error fetching results: {response.status_code}")
        return {}
        
    except Exception as e:
        logger.error(f"Error contacting backend: {e}")
        return {}


def update_bet_result(bet_id: int, result: str, finishing_position: int, pnl: float, bsp: float = None):
    """Update a LAY bet with its result"""
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE live_trades
        SET result = ?, finishing_position = ?, profit_loss = ?, bsp = ?, settled_at = ?
        WHERE id = ?
    """, (result, finishing_position, pnl, bsp, datetime.now(), bet_id))
    
    conn.commit()
    conn.close()


def check_results():
    """Check and settle all pending bets"""
    logger.info("="*80)
    logger.info("🎰 CHECKING REAL GREYHOUND LAY BETS (LIVE TRADING)")
    logger.info("="*80)
    
    unsettled_bets = get_unsettled_bets()
    
    if not unsettled_bets:
        logger.info("✅ No unsettled LAY bets to check")
        return
    
    logger.info(f"📊 Found {len(unsettled_bets)} unsettled bets")
    logger.info("")
    
    # Group bets by market_id
    markets_to_check = {}
    for bet in unsettled_bets:
        bet_id, market_id, betfair_bet_id, dog_name, odds, stake, liability, position, selection_id, venue, race_number, date = bet
        
        if market_id not in markets_to_check:
            markets_to_check[market_id] = []
        
        markets_to_check[market_id].append({
            'id': bet_id,
            'bet_id': betfair_bet_id,
            'dog_name': dog_name,
            'odds': odds,
            'stake': stake,
            'liability': liability,
            'position': position,
            'selection_id': selection_id,
            'venue': venue,
            'race_number': race_number,
            'date': date
        })
    
    logger.info(f"🔍 Checking {len(markets_to_check)} markets...")
    logger.info("")
    
    # Fetch all results
    results = fetch_race_results(list(markets_to_check.keys()))
    
    settled_count = 0
    
    # Process each market
    for market_id, bets in markets_to_check.items():
        market_results = results.get(market_id)
        
        if not market_results:
            logger.debug(f"No results yet for market {market_id}")
            continue
        
        # Create lookup by selection_id
        results_lookup = {r['selectionId']: r for r in market_results}
        
        # Find winner and placed dogs
        winners = [r for r in market_results if r.get('status') == 'WINNER']
        placed = [r for r in market_results if r.get('status') == 'PLACED']
        
        # Process each bet in this market
        for bet in bets:
            selection_id = bet['selection_id']
            dog_name = bet['dog_name']
            position = bet['position']
            
            # Get result for this dog
            dog_result = results_lookup.get(selection_id)
            if not dog_result:
                logger.warning(f"   ⚠️  {dog_name} (Pos {position}): No result found")
                continue
            
            # Determine finishing position
            status = dog_result.get('status', 'UNKNOWN')
            
            if status == 'WINNER':
                finishing_position = 1
            elif status == 'PLACED':
                placed_ids = [r['selectionId'] for r in placed]
                placed_index = placed_ids.index(selection_id) if selection_id in placed_ids else 0
                finishing_position = 2 + placed_index
            else:
                finishing_position = 0
            
            # Get ACTUAL BSP
            bsp_value = None
            if dog_result.get('bsp') is not None:
                bsp_value = dog_result.get('bsp')
            
            # For LAY bets:
            # - Dog WINS = We LOSE (pay liability)
            # - Dog LOSES = We WIN (keep stake)
            if status == 'WINNER':
                result = 'lost'
                profit_loss = -bet['liability']
            else:
                result = 'won'
                profit_loss = bet['stake']
            
            # Update database
            update_bet_result(bet['id'], result, finishing_position, profit_loss, bsp_value)
            
            # Log result
            emoji = "❌" if result == 'lost' else "✅"
            logger.info(f"{emoji} {bet['venue']} R{bet['race_number']}: {dog_name} (Pos {position})")
            logger.info(f"   Status: {status}, Finishing: {finishing_position}, P&L: ${profit_loss:+.2f}")
            
            settled_count += 1
    
    logger.info("")
    logger.info(f"✅ Settled {settled_count} bets")
    logger.info("")


def print_summary():
    """Print overall live trading summary"""
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(initial_odds_requested), 2) as avg_odds,
            ROUND(SUM(stake), 2) as total_stake,
            ROUND(SUM(liability), 2) as total_liability,
            ROUND(SUM(profit_loss), 2) as total_pl
        FROM live_trades
        WHERE result IN ('won', 'lost')
    """)
    
    row = cursor.fetchone()
    
    if row and row[0] > 0:
        total, wins, losses, avg_odds, total_stake, total_liability, pl = row
        win_rate = (wins / total) * 100 if total > 0 else 0
        roi = (pl / total_liability) * 100 if total_liability > 0 else 0
        
        logger.info("="*80)
        logger.info("📈 LIVE TRADING SUMMARY (ALL TIME)")
        logger.info("="*80)
        logger.info(f"   Total Bets: {total}")
        logger.info(f"   Wins (dogs lost): {wins}")
        logger.info(f"   Losses (dogs won): {losses}")
        logger.info(f"   Win Rate: {win_rate:.1f}%")
        logger.info(f"   Average Odds: {avg_odds:.2f}")
        logger.info(f"   Total Stake: ${total_stake:.2f}")
        logger.info(f"   Total Liability: ${total_liability:.2f}")
        logger.info(f"   Total P&L: ${pl:+.2f}")
        logger.info(f"   ROI on Liability: {roi:+.1f}%")
        logger.info("="*80)
    else:
        logger.info("📊 No settled bets yet")
    
    # By position
    cursor.execute("""
        SELECT 
            position_in_market,
            COUNT(*) as bets,
            SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(initial_odds_requested), 2) as avg_odds,
            ROUND(SUM(liability), 2) as liability,
            ROUND(SUM(profit_loss), 2) as pnl
        FROM live_trades
        WHERE result IN ('won', 'lost')
        GROUP BY position_in_market
        ORDER BY position_in_market
    """)
    
    position_rows = cursor.fetchall()
    
    if position_rows:
        logger.info("")
        logger.info("📊 RESULTS BY POSITION")
        logger.info("="*80)
        logger.info(f"{'Pos':<4} {'Bets':<6} {'Win Rate':<15} {'Avg Odds':<10} {'Liability':<12} {'P&L':<10} {'ROI':<8}")
        logger.info("-"*80)
        
        for row in position_rows:
            pos, bets, wins, losses, avg_odds, liability, pnl = row
            win_rate = (wins / bets) * 100 if bets > 0 else 0
            roi = (pnl / liability) * 100 if liability > 0 else 0
            
            logger.info(
                f"{pos:<4} {bets:<6} "
                f"{wins}W-{losses}L ({win_rate:.1f}%) "
                f"{avg_odds:<10.2f} ${liability:<11.2f} ${pnl:+9.2f} {roi:+.1f}%"
            )
        
        logger.info("="*80)
    
    conn.close()


def export_to_csv():
    """Export live trades to CSV"""
    results_dir = "/Users/clairegrady/RiderProjects/betfair/greyhound-live/results-csvs"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Export all settled bets
    logger.info("")
    logger.info("📄 Exporting to CSV files...")
    
    cursor.execute("""
        SELECT 
            id, date, venue, country, race_number, market_id, selection_id,
            dog_name, box_number, position_in_market, initial_odds_requested, stake, liability,
            result, finishing_position, profit_loss, bsp, created_at, 
            betfair_bet_id, status, final_odds_matched, total_matched
        FROM live_trades
        WHERE result IN ('won', 'lost')
        ORDER BY date DESC, created_at DESC
    """)
    
    rows = cursor.fetchall()
    
    if rows:
        csv_file = f"{results_dir}/live_trades_all_bets_{date_str}.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'date', 'venue', 'country', 'race_number', 'market_id', 'selection_id',
                'dog_name', 'box_number', 'position', 'odds', 'stake', 'liability',
                'result', 'finishing_position', 'profit_loss', 'bsp', 'created_at',
                'bet_id', 'bet_status', 'size_matched', 'avg_price_matched', 'limit_on_close',
                'total_matched'
            ])
            
            for row in rows:
                # Round decimal values
                row_list = list(row)
                if row_list[10]:  # odds
                    row_list[10] = round(row_list[10], 2)
                if row_list[11]:  # stake
                    row_list[11] = round(row_list[11], 2)
                if row_list[12]:  # liability
                    row_list[12] = round(row_list[12], 2)
                if row_list[15]:  # profit_loss
                    row_list[15] = round(row_list[15], 2)
                if row_list[16]:  # bsp
                    row_list[16] = round(row_list[16], 2)
                if row_list[21]:  # avg_price_matched
                    row_list[21] = round(row_list[21], 2)
                if row_list[22]:  # limit_on_close
                    row_list[22] = round(row_list[22], 2)
                
                writer.writerow(row_list)
        
        logger.info(f"   ✅ All bets: {csv_file}")
    else:
        logger.info("   ⚠️  No settled bets to export")
    
    conn.close()


def main():
    # Check results
    check_results()
    
    # Print summary
    print_summary()
    
    # Export to CSV
    export_to_csv()
    
    logger.info("")
    logger.info("✅ Results check complete")


if __name__ == "__main__":
    main()
