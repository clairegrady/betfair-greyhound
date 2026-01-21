#!/usr/bin/env python3
"""Reset Jan 19 results to re-settle them correctly"""

import sys
sys.path.insert(0, '../utilities')
from db_connection_helper import get_db_connection

LIVE_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/live_trades_greyhounds.db"

def main():
    conn = get_db_connection(LIVE_TRADES_DB)
    cursor = conn.cursor()
    
    # First check how many we have
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending
        FROM live_trades 
        WHERE date = '2026-01-19'
    """)
    
    row = cursor.fetchone()
    print(f"\n📊 Jan 19 bets BEFORE reset:")
    print(f"   Total: {row[0]}")
    print(f"   Won: {row[1]}")
    print(f"   Lost: {row[2]}")
    print(f"   Pending: {row[3]}")
    
    # Reset all to pending
    cursor.execute("""
        UPDATE live_trades 
        SET result = 'pending', finishing_position = NULL, profit_loss = 0, bsp = NULL
        WHERE date = '2026-01-19'
        AND result IN ('won', 'lost')
    """)
    
    affected = cursor.rowcount
    conn.commit()
    
    print(f"\n✅ Reset {affected} bets back to 'pending'")
    print(f"\nNow run: python3 check_results_LIVE.py")
    
    conn.close()

if __name__ == "__main__":
    main()
