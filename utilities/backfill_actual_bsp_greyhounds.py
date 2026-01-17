#!/usr/bin/env python3
"""
Backfill ACTUAL BSP (not projections) for greyhound bets.
Fetches sp.actualSP from Betfair API via backend endpoint.
"""

import sqlite3
import requests
from typing import Optional
from datetime import datetime, timedelta

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BACKEND_URL = "http://localhost:5173"

def get_actual_bsp_from_api(market_id: str, selection_id: int) -> Optional[float]:
    """Fetch ACTUAL BSP from Betfair via backend"""
    try:
        # Use the results endpoint which fetches sp.actualSP
        url = f"{BACKEND_URL}/api/results/settled-markets"
        response = requests.post(url, json={"marketIds": [market_id]}, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        
        # Navigate through response structure
        if market_id not in data:
            return None
            
        for runner in data[market_id]:
            if runner.get('selectionId') == selection_id:
                return runner.get('bsp')  # Returns actualSP
                
        return None
    except Exception as e:
        print(f"Error fetching BSP for {market_id}/{selection_id}: {e}")
        return None

def backfill_actual_bsp():
    """Backfill ACTUAL BSP for all settled bets"""
    print("🔍 Finding settled bets needing ACTUAL BSP...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all settled bets from last 7 days (older markets may not have BSP available)
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT id, market_id, selection_id, dog_name, date, odds, bsp
        FROM paper_trades
        WHERE result != 'pending' 
          AND date >= ?
        ORDER BY date DESC, id DESC
    """, (seven_days_ago,))
    
    bets = cursor.fetchall()
    
    if not bets:
        print("✅ No bets need BSP backfill")
        conn.close()
        return
    
    print(f"📊 Found {len(bets)} settled bets from last 7 days\n")
    
    # Group by market to minimize API calls
    markets = {}
    for bet_id, market_id, selection_id, dog_name, date, odds, old_bsp in bets:
        if market_id not in markets:
            markets[market_id] = []
        markets[market_id].append((bet_id, selection_id, dog_name, odds, old_bsp))
    
    print(f"📋 Processing {len(markets)} unique markets...\n")
    
    updated = 0
    not_found = 0
    unchanged = 0
    
    for market_id, bets_in_market in markets.items():
        print(f"🔍 Market {market_id}...")
        
        for bet_id, selection_id, dog_name, odds, old_bsp in bets_in_market:
            actual_bsp = get_actual_bsp_from_api(market_id, selection_id)
            
            if actual_bsp:
                # Only update if different from current value
                if old_bsp is None or abs(old_bsp - actual_bsp) > 0.01:
                    cursor.execute("""
                        UPDATE paper_trades SET bsp = ? WHERE id = ?
                    """, (actual_bsp, bet_id))
                    print(f"   ✅ {dog_name}: {old_bsp} → {actual_bsp}")
                    updated += 1
                else:
                    unchanged += 1
            else:
                not_found += 1
        
        conn.commit()  # Commit after each market
    
    conn.close()
    
    print(f"\n✅ Backfill complete!")
    print(f"   Updated: {updated}")
    print(f"   Unchanged: {unchanged}")
    print(f"   BSP not found: {not_found}")

if __name__ == '__main__':
    backfill_actual_bsp()
