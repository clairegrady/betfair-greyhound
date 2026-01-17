#!/usr/bin/env python3
"""
Backfill BSP for already-settled bets that don't have BSP populated.
This is a one-time script to fix historical data.
"""

import sqlite3
from typing import Optional

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"

def get_bsp(market_id: str, selection_id: int) -> Optional[float]:
    """Fetch BSP from StreamBspProjections"""
    try:
        conn = sqlite3.connect(BETFAIR_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Average FROM StreamBspProjections 
            WHERE MarketId = ? AND SelectionId = ?
        """, (market_id, str(selection_id)))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching BSP: {e}")
        return None

def backfill_bsp():
    """Backfill BSP for all settled bets that don't have it"""
    print("🔍 Finding settled bets without BSP...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all settled bets without BSP
    cursor.execute("""
        SELECT id, market_id, selection_id, dog_name, date
        FROM paper_trades
        WHERE result != 'pending' AND (bsp IS NULL OR bsp = 0)
        ORDER BY date DESC, id DESC
    """)
    
    bets = cursor.fetchall()
    
    if not bets:
        print("✅ No bets need BSP backfill")
        conn.close()
        return
    
    print(f"📊 Found {len(bets)} bets needing BSP backfill\n")
    
    updated = 0
    not_found = 0
    
    for bet_id, market_id, selection_id, dog_name, date in bets:
        bsp = get_bsp(market_id, selection_id)
        
        if bsp:
            cursor.execute("""
                UPDATE paper_trades SET bsp = ? WHERE id = ?
            """, (bsp, bet_id))
            updated += 1
            if updated % 50 == 0:
                print(f"   Updated {updated} bets...")
        else:
            not_found += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Backfill complete!")
    print(f"   Updated: {updated}")
    print(f"   BSP not found: {not_found}")

if __name__ == '__main__':
    backfill_bsp()
