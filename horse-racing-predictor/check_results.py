"""
Check Results of Paper Trading Bets
Fetches settled race results and evaluates paper bets
"""

import sqlite3
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/paper_trades.db"
BACKEND_URL = "http://localhost:5173"

def get_unsettled_bets():
    """Get all paper bets that haven't been settled yet"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get bets that are still pending
    cursor.execute("""
        SELECT 
            id, bet_type, market_id, selection_id, horse_name,
            race_time, track, model_probability, market_probability, edge,
            odds_taken, stake, placed_at
        FROM paper_trades
        WHERE result = 'PENDING'
        ORDER BY race_time DESC
    """)
    
    bets = []
    for row in cursor.fetchall():
        bets.append({
            'id': row[0],
            'bet_type': row[1],
            'market_id': row[2],
            'selection_id': row[3],
            'horse_name': row[4],
            'race_time': row[5],
            'track': row[6],
            'model_prob': row[7],
            'market_prob': row[8],
            'edge': row[9],
            'odds': row[10],
            'stake': row[11],
            'placed_at': row[12]
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
            print(f"   📦 Response keys: {list(data.keys())}")
            if 'markets' in data:
                print(f"   ✅ Markets in response: {len(data['markets'])}")
            # Also get the full response to check market status
            return data
        else:
            print(f"❌ Error fetching results: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return {}
    except Exception as e:
        print(f"❌ Error contacting backend: {e}")
        import traceback
        traceback.print_exc()
        return {}

def update_bet_result(bet_id: int, result: str, pnl: float, bsp_odds: float = None):
    """Update a bet with its result and BSP"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if bsp_odds is not None:
        cursor.execute("""
            UPDATE paper_trades
            SET result = ?, profit_loss = ?, bsp_odds = ?, settled_at = datetime('now')
            WHERE id = ?
        """, (result, pnl, bsp_odds, bet_id))
    else:
        cursor.execute("""
            UPDATE paper_trades
            SET result = ?, profit_loss = ?, settled_at = datetime('now')
            WHERE id = ?
        """, (result, pnl, bet_id))
    
    conn.commit()
    conn.close()

def check_results():
    """Main function to check and settle paper bets"""
    print("\n🔍 Checking Paper Trading Results\n")
    
    # Get unsettled bets
    unsettled_bets = get_unsettled_bets()
    
    if not unsettled_bets:
        print("✅ No unsettled bets to check")
        return
    
    print(f"📊 Found {len(unsettled_bets)} unsettled bets\n")
    
    # Group bets by market_id
    bets_by_market = {}
    for bet in unsettled_bets:
        market_id = bet['market_id']
        if market_id not in bets_by_market:
            bets_by_market[market_id] = []
        bets_by_market[market_id].append(bet)
    
    print(f"📋 Checking {len(bets_by_market)} unique markets...\n")
    
    # Fetch results for all markets IN BATCHES (backend can't handle too many at once)
    market_ids = list(bets_by_market.keys())
    BATCH_SIZE = 5
    all_markets = {}
    
    for i in range(0, len(market_ids), BATCH_SIZE):
        batch = market_ids[i:i+BATCH_SIZE]
        print(f"🔍 Fetching batch {i//BATCH_SIZE + 1} ({len(batch)} markets)...")
        results_data = fetch_settled_results(batch)
        
        if results_data and 'markets' in results_data:
            all_markets.update(results_data['markets'])
    
    print(f"✅ Fetched {len(all_markets)} total markets\n")
    markets = all_markets
    
    # Process each market
    total_bets_settled = 0
    total_pnl = 0.0
    wins = 0
    losses = 0
    
    for market_id, market_bets in bets_by_market.items():
        if market_id not in markets:
            print(f"⚠️  Market {market_id} not yet settled or not found")
            continue
        
        market_results = markets[market_id]
        
        # Check if any horses have been settled (status != ACTIVE)
        # If all are still ACTIVE, the race hasn't been settled yet
        settled_horses = [r for r in market_results if r.get('status') != 'ACTIVE']
        
        if not settled_horses:
            print(f"\n⏳ Race: {market_bets[0]['track']} at {market_bets[0]['race_time']}")
            print(f"   Market ID: {market_id}")
            print(f"   ⚠️  NOT SETTLED YET - all horses still ACTIVE, skipping...")
            continue
        
        # Get horse names from the database for this market
        import sqlite3
        horse_name_lookup = {}
        try:
            conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SelectionId, RUNNER_NAME 
                FROM HorseMarketBook 
                WHERE MarketId = ?
            """, (market_id,))
            for sel_id, name in cursor.fetchall():
                horse_name_lookup[sel_id] = name
            conn.close()
        except Exception as e:
            print(f"   ⚠️  Could not fetch horse names: {e}")
        
        # Create lookup for BSP by selection ID
        bsp_lookup = {}
        for r in market_results:
            sel_id = r.get('selectionId')  # lowercase from backend
            bsp = r.get('bsp')  # lowercase from backend
            if sel_id:
                bsp_lookup[sel_id] = bsp
        
        # Find winners and get their names
        winners = [r for r in market_results if r.get('status') == 'WINNER']  # lowercase
        winner_ids = [r['selectionId'] for r in winners]  # lowercase
        winner_names = [horse_name_lookup.get(wid, f"ID:{wid}") for wid in winner_ids]
        
        # Find placed horses (for place bets) and get their names
        placed = [r for r in market_results if r.get('status') in ['WINNER', 'PLACED']]  # lowercase
        placed_ids = [r['selectionId'] for r in placed]  # lowercase
        placed_names = [horse_name_lookup.get(pid, f"ID:{pid}") for pid in placed_ids]
        
        print(f"\n🏁 Race: {market_bets[0]['track']} at {market_bets[0]['race_time']}")
        print(f"   Market ID: {market_id}")
        print(f"   🏆 Winners: {', '.join(winner_names)}")
        print(f"   🎯 Placed: {', '.join(placed_names)}")
        print(f"   Bets on this race: {len(market_bets)}")
        
        for bet in market_bets:
            bet_id = bet['id']
            selection_id = bet['selection_id']
            stake = bet['stake']
            odds_taken = bet['odds']  # Odds at bet placement time
            bet_type = bet['bet_type']
            horse_name = bet['horse_name']
            
            # Get BSP (Betfair Starting Price) - this is the ACTUAL odds
            bsp = bsp_lookup.get(selection_id)
            
            # Use BSP if available, otherwise fall back to odds_taken
            final_odds = bsp if bsp is not None else odds_taken
            
            # Determine result
            if bet_type == 'WIN':
                won = selection_id in winner_ids
            else:  # PLACE
                won = selection_id in placed_ids
            
            if won:
                pnl = stake * (final_odds - 1)  # Profit = stake * (odds - 1)
                result = 'WON'
                wins += 1
                bsp_note = f" @ BSP {bsp:.2f}" if bsp else f" @ {odds_taken:.2f}"
                odds_drift = f" (drift: {bsp - odds_taken:+.2f})" if bsp and bsp != odds_taken else ""
                print(f"   ✅ {horse_name} ({bet_type}): WON ${pnl:.2f}{bsp_note}{odds_drift}")
            else:
                pnl = -stake  # Lost the stake
                result = 'LOST'
                losses += 1
                bsp_note = f" @ BSP {bsp:.2f}" if bsp else f" @ {odds_taken:.2f}"
                odds_drift = f" (drift: {bsp - odds_taken:+.2f})" if bsp and bsp != odds_taken else ""
                print(f"   ❌ {horse_name} ({bet_type}): LOST ${abs(pnl):.2f}{bsp_note}{odds_drift}")
            
            # Update database with BSP
            update_bet_result(bet_id, result, pnl, bsp)
            total_bets_settled += 1
            total_pnl += pnl
    
    # Summary
    print("\n" + "="*70)
    print(f"📊 RESULTS SUMMARY")
    print("="*70)
    print(f"   Bets Settled: {total_bets_settled}")
    print(f"   Wins: {wins}")
    print(f"   Losses: {losses}")
    print(f"   Win Rate: {wins/total_bets_settled*100:.1f}%" if total_bets_settled > 0 else "   Win Rate: N/A")
    print(f"   Total P&L: ${total_pnl:+.2f}")
    print(f"   ROI: {total_pnl/sum(b['stake'] for b in unsettled_bets if b['id'] in [bet['id'] for bet in unsettled_bets])*100:+.1f}%" if total_bets_settled > 0 else "   ROI: N/A")
    print("="*70 + "\n")

def show_historical_results():
    """Show recent settled bets with winners"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get recent settled bets grouped by race
    cursor.execute("""
        SELECT DISTINCT market_id, race_time, track, venue, race_number
        FROM paper_trades
        WHERE result != 'PENDING'
        ORDER BY race_time DESC
        LIMIT 5
    """)
    
    races = cursor.fetchall()
    
    if not races:
        conn.close()
        return
    
    print("\n" + "="*70)
    print("📜 RECENT RACE RESULTS")
    print("="*70)
    
    betfair_conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite")
    
    for market_id, race_time, track, venue, race_number in races:
        # Get horse name lookup for this market
        betfair_cursor = betfair_conn.cursor()
        betfair_cursor.execute("""
            SELECT SelectionId, RUNNER_NAME 
            FROM HorseMarketBook 
            WHERE MarketId = ?
        """, (market_id,))
        horse_names = {sel_id: name for sel_id, name in betfair_cursor.fetchall()}
        
        # Get bets for this race
        cursor.execute("""
            SELECT bet_type, horse_name, odds_taken, bsp_odds, result, profit_loss, model_probability, edge
            FROM paper_trades
            WHERE market_id = ?
            ORDER BY bet_type, placed_at
        """, (market_id,))
        
        bets = cursor.fetchall()
        
        # Try to get winners from backend
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/results/settled",
                json={"marketIds": [market_id]},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'markets' in data and market_id in data['markets']:
                    market_results = data['markets'][market_id]
                    
                    winners = [r for r in market_results if r.get('status') == 'WINNER']
                    winner_ids = [r['selectionId'] for r in winners]
                    winner_names = [horse_names.get(wid, f"ID:{wid}") for wid in winner_ids]
                    
                    placed = [r for r in market_results if r.get('status') in ['WINNER', 'PLACED']]
                    placed_ids = [r['selectionId'] for r in placed]
                    placed_names = [horse_names.get(pid, f"ID:{pid}") for pid in placed_ids]
                else:
                    winner_names = ["Unknown"]
                    placed_names = ["Unknown"]
            else:
                winner_names = ["Unknown"]
                placed_names = ["Unknown"]
        except:
            winner_names = ["Unknown"]
            placed_names = ["Unknown"]
        
        print(f"\n🏁 {track} ({race_time})")
        if winner_names and winner_names[0] != "Unknown":
            print(f"   🏆 Winners: {', '.join(winner_names)}")
            print(f"   🎯 Placed: {', '.join(placed_names)}")
        
        for bet_type, horse, odds_taken, bsp, result, pnl, model_prob, edge in bets:
            emoji = "✅" if result == "WON" else "❌"
            
            # Handle potential corrupted data
            try:
                bsp_val = float(bsp) if bsp else None
                odds_val = float(odds_taken)
                pnl_val = float(pnl) if pnl else 0
                model_val = float(model_prob) if model_prob else 0
                edge_val = float(edge) if edge else 0
                
                bsp_str = f"BSP {bsp_val:.2f}" if bsp_val else f"{odds_val:.2f}"
                drift = f" (drift: {bsp_val - odds_val:+.2f})" if bsp_val and bsp_val != odds_val else ""
                
                print(f"   {emoji} {horse} ({bet_type}): {result} | {bsp_str}{drift} | Model {model_val*100:.1f}% | Edge {edge_val*100:+.1f}% | P&L ${pnl_val:+.2f}")
            except (ValueError, TypeError) as e:
                print(f"   {emoji} {horse} ({bet_type}): {result} | Data error")
    
    betfair_conn.close()
    conn.close()
    print("="*70)

def show_overall_stats():
    """Show overall paper trading statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get overall stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_bets,
            SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOST' THEN 1 ELSE 0 END) as losses,
            SUM(profit_loss) as total_pnl,
            SUM(stake) as total_staked,
            AVG(edge) as avg_edge
        FROM paper_trades
        WHERE result != 'PENDING'
    """)
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        total_bets, wins, losses, total_pnl, total_staked, avg_edge = row
        
        print("\n" + "="*70)
        print(f"📈 OVERALL PAPER TRADING STATS")
        print("="*70)
        print(f"   Total Bets: {total_bets}")
        print(f"   Wins: {wins}")
        print(f"   Losses: {losses}")
        print(f"   Win Rate: {wins/total_bets*100:.1f}%")
        print(f"   Average Edge: {avg_edge*100:+.1f}%")
        print(f"   Total Staked: ${total_staked:.2f}")
        print(f"   Total P&L: ${total_pnl:+.2f}")
        print(f"   ROI: {total_pnl/total_staked*100:+.1f}%")
        print("="*70 + "\n")
    else:
        print("\n📊 No settled bets yet\n")
    
    conn.close()

if __name__ == "__main__":
    # Check results
    check_results()
    
    # Show historical bets with winners
    show_historical_results()
    
    # Show overall stats
    show_overall_stats()

