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
    """Get all bets that haven't been settled yet (ALL dates, not filtered)"""
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, market_id, betfair_bet_id, dog_name, initial_odds_requested, stake, liability, 
               position_in_market, selection_id, venue, race_number, date, total_matched
        FROM live_trades
        WHERE result = 'pending' AND status != 'FAILED'
        ORDER BY date DESC, created_at DESC
    """)
    
    bets = cursor.fetchall()
    conn.close()
    logger.info(f"📊 Found {len(bets)} unsettled bets (all dates)")
    return bets


def fetch_race_results(market_ids: list) -> dict:
    """Fetch race results from backend API"""
    try:
        url = f"{BACKEND_URL}/api/results/settled"
        logger.info(f"📡 Fetching results from {url} for {len(market_ids)} markets...")
        
        response = requests.post(
            url,
            json={"marketIds": market_ids},
            timeout=30
        )
        
        logger.info(f"📡 Backend response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            markets_with_results = len(data.get('markets', {}))
            logger.info(f"✅ Received results for {markets_with_results}/{len(market_ids)} markets from API")
            return data.get('markets', {})
        
        logger.error(f"❌ Error fetching results: HTTP {response.status_code}")
        logger.error(f"   Response: {response.text[:200]}")
        return {}
        
    except Exception as e:
        logger.error(f"❌ Error contacting backend: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {}


def get_results_from_db(market_id: str) -> list:
    """
    Fallback: Get results from GreyhoundMarketBook database
    """
    try:
        conn = get_db_connection('betfairmarket')
        cursor = conn.cursor()
        
        # Get distinct selection IDs and their status (BSP column doesn't exist in this table)
        cursor.execute("""
            SELECT DISTINCT selectionid, runnername, status
            FROM greyhoundmarketbook
            WHERE marketid = %s
            AND status IS NOT NULL
        """, (market_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return None
        
        # Build results
        results = []
        for sel_id, runner_name, status in rows:
            # Clean trap number from name
            import re
            clean_name = re.sub(r'^\d+\.\s*', '', runner_name) if runner_name else f'Dog {sel_id}'
            
            results.append({
                'selectionId': sel_id,
                'runnerName': clean_name,
                'status': status,
                'bsp': None  # BSP not stored in greyhoundmarketbook
            })
        
        conn.close()
        logger.info(f"   ✅ Found {market_id} in database")
        return results if results else None
        
    except Exception as e:
        logger.warning(f"   ⚠️  Error getting results from DB for {market_id}: {e}")
        return None


def update_bet_result(bet_id: int, result: str, finishing_position: int, pnl: float, bsp: float = None):
    """Update a LAY bet with its result"""
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE live_trades
        SET result = %s, finishing_position = %s, profit_loss = %s, bsp = %s
        WHERE id = %s
    """, (result, finishing_position, pnl, bsp, bet_id))
    
    conn.commit()
    conn.close()


def check_results():
    """Check and settle all pending bets (all dates)"""
    logger.info("="*80)
    logger.info("🎰 CHECKING REAL GREYHOUND LAY BETS (LIVE TRADING)")
    logger.info("="*80)
    
    unsettled_bets = get_unsettled_bets()
    
    if not unsettled_bets:
        logger.info("✅ No unsettled LAY bets to check")
        return
    
    logger.info("")
    
    # Group bets by market_id
    markets_to_check = {}
    for bet in unsettled_bets:
        bet_id, market_id, betfair_bet_id, dog_name, odds, stake, liability, position, selection_id, venue, race_number, date, total_matched = bet
        
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
            'date': date,
            'total_matched': total_matched or stake  # Use total_matched if available, otherwise stake
        })
    
    logger.info(f"🔍 Checking {len(markets_to_check)} markets...")
    logger.info("")
    
    # Fetch all results from API
    results = fetch_race_results(list(markets_to_check.keys()))
    
    # For markets not found in API, try database fallback
    missing_markets = [mid for mid in markets_to_check.keys() if mid not in results]
    if missing_markets:
        logger.info(f"🔍 Checking {len(missing_markets)} markets in database fallback...")
        for market_id in missing_markets:
            db_results = get_results_from_db(market_id)
            if db_results:
                results[market_id] = db_results
                logger.info(f"   ✅ Found {market_id} in database")
    
    logger.info(f"✅ Total markets with results: {len(results)}/{len(markets_to_check)}")
    logger.info("")
    
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
        
        # CRITICAL: Check if race is settled (has WINNER/LOSER, not just ACTIVE)
        settled_dogs = [r for r in market_results if r.get('status') and r.get('status') != 'ACTIVE']
        
        if not settled_dogs:
            logger.debug(f"⏳ {bets[0]['venue']} R{bets[0]['race_number']} - NOT SETTLED YET (all ACTIVE) - skipping...")
            continue
        
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
            
            # DEBUG: Log what Betfair returned
            logger.debug(f"   🔍 {dog_name}: status={status}, bsp={dog_result.get('bsp')}")
            
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
            
            # Get the ACTUAL matched amount (not the requested stake)
            matched_amount = bet['total_matched']  # Now we're fetching it properly
            matched_liability = matched_amount * (bet['odds'] - 1)  # Use bet['odds'] which is initial_odds_requested
            
            # For LAY bets:
            # - Dog WINS = We LOSE (pay liability on MATCHED amount)
            # - Dog LOSES = We WIN (keep MATCHED stake)
            if status == 'WINNER':
                result = 'lost'
                profit_loss = -matched_liability  # Loss based on matched amount
            else:
                result = 'won'
                profit_loss = matched_amount  # Profit based on matched amount
            
            # Update database
            update_bet_result(bet['id'], result, finishing_position, profit_loss, bsp_value)
            
            # Log result
            emoji = "❌" if result == 'lost' else "✅"
            logger.info(f"{emoji} {bet['venue']} R{bet['race_number']}: {dog_name} (Pos {position})")
            logger.info(f"   Status: {status}, Finishing: {finishing_position}")
            logger.info(f"   Matched: ${matched_amount:.2f}/${bet['stake']:.2f}, P&L: ${profit_loss:+.2f}")
            
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
            ROUND(AVG(initial_odds_requested)::NUMERIC, 2) as avg_odds,
            ROUND(SUM(stake)::NUMERIC, 2) as total_stake,
            ROUND(SUM(liability)::NUMERIC, 2) as total_liability,
            ROUND(SUM(profit_loss)::NUMERIC, 2) as total_pl
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
            ROUND(AVG(initial_odds_requested)::NUMERIC, 2) as avg_odds,
            ROUND(SUM(liability)::NUMERIC, 2) as liability,
            ROUND(SUM(profit_loss)::NUMERIC, 2) as pnl
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
    """Export live trades to CSV with summary"""
    results_dir = "/Users/clairegrady/RiderProjects/betfair/greyhound-live/results-csvs"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    date_str = datetime.now().strftime("%Y-%m-%d")  # Use today's date
    
    # Export all settled bets (detailed view with matched/unmatched info)
    logger.info("")
    logger.info("📄 Exporting to CSV files...")
    
    cursor.execute("""
        SELECT 
            id, date, venue, country, race_number, market_id, selection_id,
            dog_name, box_number, position_in_market, initial_odds_requested, stake, liability,
            result, finishing_position, profit_loss, bsp, created_at, 
            betfair_bet_id, status, final_odds_matched, total_matched
        FROM live_trades
        WHERE result IN ('won', 'lost', 'pending')
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
                'bet_id', 'status', 'final_odds_matched', 'total_matched'
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
                if row_list[20]:  # final_odds_matched
                    row_list[20] = round(row_list[20], 2)
                
                writer.writerow(row_list)
        
        logger.info(f"   ✅ All bets (detailed): {csv_file}")
    else:
        logger.info("   ⚠️  No bets to export")
    
    # Export ONE summary CSV (position 1 only, like simulated greyhounds_by_day_and_position)
    cursor.execute("""
        SELECT 
            date,
            position_in_market,
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            ROUND(AVG(CASE WHEN result IN ('won', 'lost') THEN initial_odds_requested END)::NUMERIC, 2) as avg_odds,
            ROUND(SUM(CASE WHEN result IN ('won', 'lost') THEN stake END)::NUMERIC, 2) as total_stake,
            ROUND(SUM(CASE WHEN result IN ('won', 'lost') THEN liability END)::NUMERIC, 2) as total_liability,
            ROUND(SUM(CASE WHEN result IN ('won', 'lost') THEN profit_loss END)::NUMERIC, 2) as pnl
        FROM live_trades
        WHERE date = %s
        GROUP BY date, position_in_market
        ORDER BY position_in_market
    """, (date_str,))
    
    result = cursor.fetchone()
    
    if result:
        csv_file = f"{results_dir}/live_trades_summary_{date_str}.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Position', 'Bets', 'Wins', 'Losses', 'Pending',
                            'Win Rate %', 'Avg Odds', 'Total Stake', 'Total Liability', 'P&L', 'ROI %'])
            
            date, pos, total_bets, wins, losses, pending, avg_odds, stake, liability, pnl = result
            settled = wins + losses
            win_rate = round(wins/settled*100, 2) if settled > 0 else 0
            roi = round(pnl/liability*100, 2) if liability and settled > 0 else 0
            
            writer.writerow([
                date, pos, total_bets, wins, losses, pending,
                win_rate,
                round(float(avg_odds or 0), 2),
                round(float(stake or 0), 2),
                round(float(liability or 0), 2),
                round(float(pnl or 0), 2),
                roi
            ])
        
        logger.info(f"   ✅ Summary: {csv_file}")
        logger.info(f"      📊 {total_bets} bets: {wins}W / {losses}L / {pending}P")
        logger.info(f"      💰 P&L: ${pnl or 0:.2f} | ROI: {roi:.2f}%")
    else:
        logger.info("   ⚠️  No bets for summary")
    
    conn.close()


def main():
    # Check results for ALL pending bets (no date filter)
    check_results()
    
    # Print summary
    print_summary()
    
    # Export to CSV
    export_to_csv()
    
    logger.info("")
    logger.info("✅ Results check complete")


if __name__ == "__main__":
    main()
