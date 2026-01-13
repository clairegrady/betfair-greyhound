"""
Backfill box numbers for today's paper trades from GreyhoundMarketBook
"""

import sqlite3
from datetime import datetime

PAPER_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/greyhound-predictor/paper_trades_greyhounds.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"

def backfill_box_numbers():
    """Backfill box numbers for trades with missing box_number"""
    
    # Connect to both databases
    paper_conn = sqlite3.connect(PAPER_TRADES_DB)
    paper_cursor = paper_conn.cursor()
    
    betfair_conn = sqlite3.connect(BETFAIR_DB)
    betfair_cursor = betfair_conn.cursor()
    
    # Get trades with missing box numbers from today
    today = datetime.now().strftime('%Y-%m-%d')
    paper_cursor.execute("""
        SELECT id, market_id, selection_id, dog_name
        FROM paper_trades
        WHERE date = ?
        AND (box_number IS NULL OR box_number = 0)
    """, (today,))
    
    trades = paper_cursor.fetchall()
    print(f"Found {len(trades)} trades with missing box numbers from today\n")
    
    updated = 0
    not_found = 0
    
    for trade_id, market_id, selection_id, dog_name in trades:
        # Look up box number in GreyhoundMarketBook
        betfair_cursor.execute("""
            SELECT DISTINCT box
            FROM GreyhoundMarketBook
            WHERE MarketId = ?
            AND SelectionId = ?
            AND box IS NOT NULL
            AND box > 0
            LIMIT 1
        """, (market_id, selection_id))
        
        result = betfair_cursor.fetchone()
        
        if result:
            box = int(result[0]) if result[0] else None
            if box:
                paper_cursor.execute("""
                    UPDATE paper_trades
                    SET box_number = ?
                    WHERE id = ?
                """, (box, trade_id))
                updated += 1
                print(f"✅ Trade {trade_id}: {dog_name} → Box {box}")
        else:
            not_found += 1
            print(f"⚠️  Trade {trade_id}: {dog_name} → Box not found in backend")
    
    paper_conn.commit()
    paper_conn.close()
    betfair_conn.close()
    
    print(f"\n{'='*70}")
    print(f"BACKFILL COMPLETE")
    print(f"{'='*70}")
    print(f"   Updated: {updated}")
    print(f"   Not found: {not_found}")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    backfill_box_numbers()
