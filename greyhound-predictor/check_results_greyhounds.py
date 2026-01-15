"""
Check Results for Greyhound LAY Betting Paper Trades
Updates finishing positions and calculates profit/loss
"""

import sqlite3
import requests
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
BACKEND_URL = "http://localhost:5173"

def get_unsettled_bets():
    """Get all paper LAY bets that haven't been settled yet"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id, date, venue, country, race_number, market_id, selection_id, 
            dog_name, box_number, position_in_market, odds, stake, liability, created_at
        FROM paper_trades
        WHERE result = 'pending'
        ORDER BY date DESC, created_at DESC
    """)
    
    bets = []
    for row in cursor.fetchall():
        bets.append({
            'id': row[0],
            'date': row[1],
            'venue': row[2],
            'country': row[3],
            'race_number': row[4],
            'market_id': row[5],
            'selection_id': row[6],
            'dog_name': row[7],
            'box_number': row[8],
            'position_in_market': row[9],
            'odds': row[10],
            'stake': row[11],
            'liability': row[12],
            'created_at': row[13]
        })
    
    conn.close()
    return bets

def fetch_settled_results(market_ids: List[str]) -> Dict:
    """Fetch settled results from backend"""
    try:
        print(f"   🌐 Calling backend with {len(market_ids)} market IDs...")
        response = requests.post(
            f"{BACKEND_URL}/api/results/settled",
            json={"marketIds": market_ids},
            timeout=30
        )
        
        print(f"   📡 Backend response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"❌ Error fetching results: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Error contacting backend: {e}")
        return {}

def get_results_from_db(market_id: str) -> Dict:
    """Fallback: Get results from GreyhoundMarketBook"""
    try:
        conn = sqlite3.connect(BETFAIR_DB)
        cursor = conn.cursor()
        
        # Get distinct selection IDs and their status/BSP with placing info
        cursor.execute("""
            SELECT DISTINCT SelectionId, RunnerName, Status, BSP, box, PlacedDate
            FROM GreyhoundMarketBook
            WHERE MarketId = ?
            AND Status IS NOT NULL
        """, (market_id,))
        
        results = []
        for sel_id, runner_name, status, bsp, box, placed_date in cursor.fetchall():
            # Clean trap number from name
            import re
            clean_name = re.sub(r'^\d+\.\s*', '', runner_name) if runner_name else f'Dog {sel_id}'
            
            # Determine finishing position based on status
            # WINNER = 1st, LOSER could be 2nd, 3rd, or no place
            finishing_position = None
            if status == 'WINNER':
                finishing_position = 1
            elif status == 'PLACED':
                finishing_position = 2  # Could be 2nd or 3rd, we'll refine this
            
            results.append({
                'selectionId': sel_id,
                'runnerName': clean_name,
                'status': status,
                'bsp': bsp,
                'box': box,
                'finishingPosition': finishing_position
            })
        
        conn.close()
        return results if results else None
        
    except Exception as e:
        print(f"   ⚠️  Error getting results from DB: {e}")
        return None

def update_bet_result(bet_id: int, result: str, finishing_position: int, pnl: float):
    """Update a LAY bet with its result"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE paper_trades
        SET result = ?, finishing_position = ?, profit_loss = ?
        WHERE id = ?
    """, (result, finishing_position, pnl, bet_id))
    
    conn.commit()
    conn.close()

def add_profit_loss_column_if_needed():
    """Add profit_loss column to paper_trades if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(paper_trades)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'profit_loss' not in columns:
        print("   Adding profit_loss column to paper_trades table...")
        cursor.execute("ALTER TABLE paper_trades ADD COLUMN profit_loss REAL DEFAULT 0")
        conn.commit()
    
    conn.close()

def check_results():
    """Main function to check and settle greyhound LAY paper bets"""
    print("\n🐕 Checking Greyhound LAY Betting Paper Trading Results\n")
    
    # Ensure profit_loss column exists
    add_profit_loss_column_if_needed()
    
    unsettled_bets = get_unsettled_bets()
    
    if not unsettled_bets:
        print("✅ No unsettled LAY bets to check")
        return
    
    print(f"📊 Found {len(unsettled_bets)} unsettled LAY bets\n")
    
    # Group bets by market_id
    bets_by_market = {}
    for bet in unsettled_bets:
        market_id = bet['market_id']
        if market_id not in bets_by_market:
            bets_by_market[market_id] = []
        bets_by_market[market_id].append(bet)
    
    print(f"📋 Checking {len(bets_by_market)} unique markets...\n")
    
    # Try backend API first, fall back to DB
    market_ids = list(bets_by_market.keys())
    all_markets = {}
    
    # Try backend API in batches
    BATCH_SIZE = 5
    for i in range(0, len(market_ids), BATCH_SIZE):
        batch = market_ids[i:i+BATCH_SIZE]
        print(f"🔍 Fetching batch {i//BATCH_SIZE + 1} ({len(batch)} markets)...")
        results_data = fetch_settled_results(batch)
        
        if results_data and 'markets' in results_data:
            all_markets.update(results_data['markets'])
    
    print(f"✅ Fetched {len(all_markets)} markets from API")
    
    # For markets not found in API, try database
    missing_markets = [mid for mid in market_ids if mid not in all_markets]
    if missing_markets:
        print(f"🔍 Checking {len(missing_markets)} markets in database...")
        for market_id in missing_markets:
            db_results = get_results_from_db(market_id)
            if db_results:
                all_markets[market_id] = db_results
    
    print(f"✅ Total markets found: {len(all_markets)}\n")
    
    # Process each market
    total_bets_settled = 0
    total_pnl = 0.0
    wins = 0  # For LAY bets, a "win" means the dog LOST
    losses = 0  # For LAY bets, a "loss" means the dog WON
    
    for market_id, market_bets in bets_by_market.items():
        if market_id not in all_markets:
            print(f"⚠️  Market {market_id} not yet settled or not found")
            continue
        
        market_results = all_markets[market_id]
        
        # Check if settled
        settled_dogs = [r for r in market_results if r.get('status') and r.get('status') != 'ACTIVE']
        
        if not settled_dogs:
            print(f"\n⏳ Race: {market_bets[0]['venue']} R{market_bets[0]['race_number']}")
            print(f"   ⚠️  NOT SETTLED YET - skipping...")
            continue
        
        # Create lookup by selection_id
        results_lookup = {r['selectionId']: r for r in market_results}
        
        # Find winner and placed dogs
        winners = [r for r in market_results if r.get('status') == 'WINNER']
        placed = [r for r in market_results if r.get('status') == 'PLACED']
        winner_ids = [r['selectionId'] for r in winners]
        placed_ids = [r['selectionId'] for r in placed]
        winner_names = [r.get('runnerName') or f"Dog {r['selectionId']}" for r in winners]
        placed_names = [r.get('runnerName') or f"Dog {r['selectionId']}" for r in placed]
        
        print(f"\n🏁 Race: {market_bets[0]['venue']} ({market_bets[0]['country']}) - R{market_bets[0]['race_number']}")
        print(f"   Market ID: {market_id}")
        print(f"   🏆 Winner: {', '.join(winner_names)}")
        if placed_names:
            print(f"   🥈 Placed: {', '.join(placed_names)}")
        print(f"   LAY Bets on this race: {len(market_bets)}")
        
        for bet in market_bets:
            bet_id = bet['id']
            selection_id = bet['selection_id']
            stake = bet['stake']
            liability = bet['liability']
            odds_taken = bet['odds']
            dog_name = bet['dog_name']
            position = bet['position_in_market']
            
            # Get result for this dog
            dog_result = results_lookup.get(selection_id)
            if not dog_result:
                print(f"   ⚠️  {dog_name} (Pos {position}): No result found")
                continue
            
            # Determine finishing position
            dog_status = dog_result.get('status', 'UNKNOWN')
            dog_won = selection_id in winner_ids
            dog_placed = selection_id in placed_ids
            
            if dog_won:
                finishing_position = 1
            elif dog_placed:
                # If placed, assign 2 or 3 (we'll use 2 for now as we can't distinguish)
                # Count how many placed to determine if 2nd or 3rd
                placed_index = placed_ids.index(selection_id) if selection_id in placed_ids else 0
                finishing_position = 2 + placed_index  # 2 for first placed, 3 for second placed
            else:
                finishing_position = 0  # Did not place
            
            # For LAY bets:
            # - If dog WON, we LOSE the liability
            # - If dog LOST (including placed), we WIN the stake
            
            if dog_won:
                # Dog won, so our LAY bet loses
                pnl = -liability  # We lose the liability
                result = 'lost'
                losses += 1
                print(f"   ❌ {dog_name} (Pos {position} LAY): LOST ${abs(pnl):.2f} @ {odds_taken:.2f} (dog WON 1st)")
            else:
                # Dog lost, so our LAY bet wins
                pnl = stake  # We win the stake
                result = 'won'
                wins += 1
                position_text = f"{finishing_position}nd/3rd" if dog_placed else "no place"
                print(f"   ✅ {dog_name} (Pos {position} LAY): WON ${pnl:.2f} @ {odds_taken:.2f} (dog {position_text})")
            
            update_bet_result(bet_id, result, finishing_position, pnl)
            total_bets_settled += 1
            total_pnl += pnl
    
    # Summary
    print("\n" + "="*70)
    print(f"📊 GREYHOUND LAY BETTING RESULTS SUMMARY")
    print("="*70)
    print(f"   LAY Bets Settled: {total_bets_settled}")
    print(f"   Wins (dogs lost): {wins}")
    print(f"   Losses (dogs won): {losses}")
    print(f"   Win Rate: {wins/total_bets_settled*100:.1f}%" if total_bets_settled > 0 else "   Win Rate: N/A")
    print(f"   Total P&L: ${total_pnl:+.2f}")
    print("="*70 + "\n")

def show_overall_stats():
    """Show overall greyhound LAY betting statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if profit_loss column exists
    cursor.execute("PRAGMA table_info(paper_trades)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'profit_loss' not in columns:
        print("\n📊 No settled bets yet (profit_loss column not created)\n")
        conn.close()
        return
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(profit_loss) as total_pnl,
            SUM(liability) as total_liability,
            SUM(stake) as total_stake
        FROM paper_trades
        WHERE result != 'pending'
    """)
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        total_bets, wins, losses, total_pnl, total_liability, total_stake = row
        
        print("\n" + "="*70)
        print(f"📈 OVERALL GREYHOUND LAY BETTING STATS")
        print("="*70)
        print(f"   Total LAY Bets: {total_bets}")
        print(f"   Wins (dogs lost): {wins}")
        print(f"   Losses (dogs won): {losses}")
        print(f"   Win Rate: {wins/total_bets*100:.1f}%")
        print(f"   Total Stake: ${total_stake:.2f}")
        print(f"   Total Liability: ${total_liability:.2f}")
        print(f"   Total P&L: ${total_pnl:+.2f}")
        print(f"   ROI on Liability: {total_pnl/total_liability*100:+.1f}%")
        print("="*70 + "\n")
    else:
        print("\n📊 No settled greyhound LAY bets yet\n")
    
    # Show breakdown by position
    cursor.execute("""
        SELECT 
            position_in_market,
            COUNT(*) as bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(profit_loss) as pnl,
            SUM(stake) as total_stake,
            SUM(liability) as total_liability
        FROM paper_trades
        WHERE result != 'pending'
        GROUP BY position_in_market
        ORDER BY position_in_market
    """)
    
    rows = cursor.fetchall()
    if rows:
        print("\n" + "="*90)
        print(f"📊 RESULTS BY POSITION (Favorite = 1, 2nd Fav = 2, etc.)")
        print("="*90)
        print(f"{'Pos':<4} {'Bets':<6} {'Win Rate':<12} {'Liability':<14} {'P&L':<12} {'ROI':<8}")
        print("-"*90)
        for row in rows:
            pos, bets, wins, losses, pnl, stake, liability = row
            win_rate = wins/bets*100 if bets > 0 else 0
            roi = pnl/liability*100 if liability > 0 else 0
            print(f"{pos:<4} {bets:<6} {wins}W-{losses}L ({win_rate:>4.1f}%) ${liability:>10,.2f}   ${pnl:>+9.2f}  {roi:>+6.1f}%")
        print("="*90 + "\n")
    
    conn.close()

def show_daily_stats():
    """Show greyhound LAY betting statistics broken down by day"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if profit_loss column exists
    cursor.execute("PRAGMA table_info(paper_trades)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'profit_loss' not in columns:
        conn.close()
        return
    
    # Get daily stats
    cursor.execute("""
        SELECT 
            date,
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(profit_loss) as total_pnl,
            SUM(liability) as total_liability,
            SUM(stake) as total_stake
        FROM paper_trades
        GROUP BY date
        ORDER BY date DESC
    """)
    
    rows = cursor.fetchall()
    if rows:
        print("\n" + "="*100)
        print(f"📅 DAILY BREAKDOWN - GREYHOUND LAY BETTING")
        print("="*100)
        print(f"{'Date':<12} {'Bets':<6} {'Win Rate':<15} {'Liability':<14} {'P&L':<12} {'ROI':<8} {'Status':<10}")
        print("-"*100)
        
        for row in rows:
            date, bets, wins, losses, pending, pnl, liability, stake = row
            settled = wins + losses
            win_rate = wins/settled*100 if settled > 0 else 0
            roi = pnl/liability*100 if liability and settled > 0 else 0
            status = "✅ Complete" if pending == 0 else f"⏳ {pending} pending"
            
            # Only show P&L and ROI for settled days
            if settled > 0:
                print(f"{date:<12} {bets:<6} {wins}W-{losses}L ({win_rate:>4.1f}%)  ${liability:>10,.2f}   ${pnl:>+9.2f}  {roi:>+6.1f}%   {status}")
            else:
                print(f"{date:<12} {bets:<6} {'--':<15} ${'0.00':>10}   ${'0.00':>9}  {'--':>6}   {status}")
        
        print("="*100 + "\n")
    
    conn.close()

def export_to_csv():
    """Export all greyhound betting data to CSV files with 2 decimal places"""
    import os
    
    # Create results directory if it doesn't exist
    results_dir = "results-csvs"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Export all bets
    print("\n📄 Exporting to CSV files...")
    cursor.execute("""
        SELECT 
            id, date, venue, country, race_number, market_id, selection_id,
            dog_name, box_number, position_in_market, odds, stake, liability,
            result, finishing_position, profit_loss, bsp, created_at
        FROM paper_trades
        WHERE date = ?
        ORDER BY created_at DESC
    """, (date_str,))
    
    csv_file = f"{results_dir}/greyhounds_all_bets_{date_str}.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Date', 'Venue', 'Country', 'Race', 'Market ID', 'Selection ID',
                        'Dog Name', 'Box', 'Position', 'Odds', 'Stake', 'Liability',
                        'Result', 'Finish Pos', 'P&L', 'BSP', 'Created At'])
        
        for row in cursor.fetchall():
            # Round all decimal values to 2 places
            formatted_row = list(row)
            if formatted_row[10] is not None:  # odds
                formatted_row[10] = round(float(formatted_row[10]), 2)
            if formatted_row[11] is not None:  # stake
                formatted_row[11] = round(float(formatted_row[11]), 2)
            if formatted_row[12] is not None:  # liability
                formatted_row[12] = round(float(formatted_row[12]), 2)
            if formatted_row[15] is not None:  # profit_loss
                formatted_row[15] = round(float(formatted_row[15]), 2)
            if formatted_row[16] is not None:  # bsp
                formatted_row[16] = round(float(formatted_row[16]), 2)
            writer.writerow(formatted_row)
    
    print(f"   ✅ All bets: {csv_file}")
    
    # Export position breakdown
    cursor.execute("""
        SELECT 
            position_in_market,
            COUNT(*) as bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            AVG(odds) as avg_odds,
            SUM(stake) as total_stake,
            SUM(liability) as total_liability,
            SUM(profit_loss) as pnl
        FROM paper_trades
        WHERE date = ?
        GROUP BY position_in_market
        ORDER BY position_in_market
    """, (date_str,))
    
    csv_file = f"{results_dir}/greyhounds_by_position_{date_str}.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Position', 'Total Bets', 'Wins', 'Losses', 'Pending', 
                        'Win Rate %', 'Avg Odds', 'Total Stake', 'Total Liability', 'P&L', 'ROI %'])
        
        for row in cursor.fetchall():
            pos, bets, wins, losses, pending, avg_odds, stake, liability, pnl = row
            settled = wins + losses
            win_rate = round(wins/settled*100, 2) if settled > 0 else 0
            roi = round(pnl/liability*100, 2) if liability and settled > 0 else 0
            
            writer.writerow([
                pos, bets, wins, losses, pending,
                win_rate,
                round(float(avg_odds or 0), 2),
                round(float(stake or 0), 2),
                round(float(liability or 0), 2),
                round(float(pnl or 0), 2),
                roi
            ])
    
    print(f"   ✅ By position: {csv_file}")
    
    # Export daily breakdown
    cursor.execute("""
        SELECT 
            date,
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            AVG(odds) as avg_odds,
            SUM(stake) as total_stake,
            SUM(liability) as total_liability,
            SUM(profit_loss) as total_pnl
        FROM paper_trades
        WHERE date = ?
        GROUP BY date
    """, (date_str,))
    
    csv_file = f"{results_dir}/greyhounds_by_day_{date_str}.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Total Bets', 'Wins', 'Losses', 'Pending',
                        'Win Rate %', 'Avg Odds', 'Stake', 'Liability', 'P&L', 'ROI %'])
        
        for row in cursor.fetchall():
            date, bets, wins, losses, pending, avg_odds, stake, liability, pnl = row
            settled = wins + losses
            win_rate = round(wins/settled*100, 2) if settled > 0 else 0
            roi = round(pnl/liability*100, 2) if liability and settled > 0 else 0
            
            writer.writerow([
                date, bets, wins, losses, pending,
                win_rate,
                round(float(avg_odds or 0), 2),
                round(float(stake or 0), 2),
                round(float(liability or 0), 2),
                round(float(pnl or 0), 2),
                roi
            ])
    
    print(f"   ✅ By day: {csv_file}")
    
    # Export daily breakdown BY POSITION (new detailed view)
    cursor.execute("""
        SELECT 
            date,
            position_in_market,
            COUNT(*) as bets,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            AVG(odds) as avg_odds,
            SUM(stake) as total_stake,
            SUM(liability) as total_liability,
            SUM(profit_loss) as pnl
        FROM paper_trades
        WHERE date = ?
        GROUP BY date, position_in_market
        ORDER BY position_in_market
    """, (date_str,))
    
    csv_file = f"{results_dir}/greyhounds_by_day_and_position_{date_str}.csv"
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Position', 'Bets', 'Wins', 'Losses', 'Pending', 'Win Rate %', 
                        'Avg Odds', 'Total Stake', 'Total Liability', 'P&L', 'ROI %'])
        
        for row in cursor.fetchall():
            date, pos, bets, wins, losses, pending, avg_odds, stake, liability, pnl = row
            settled = wins + losses
            win_rate = round(wins/settled*100, 2) if settled > 0 else 0
            roi = round(pnl/liability*100, 2) if liability and settled > 0 else 0
            
            writer.writerow([
                date, pos, bets, wins, losses, pending,
                win_rate,
                round(float(avg_odds or 0), 2),
                round(float(stake or 0), 2),
                round(float(liability or 0), 2),
                round(float(pnl or 0), 2),
                roi
            ])
    
    print(f"   ✅ By day & position: {csv_file}\n")
    
    conn.close()

if __name__ == "__main__":
    check_results()
    show_overall_stats()
    show_daily_stats()
    export_to_csv()