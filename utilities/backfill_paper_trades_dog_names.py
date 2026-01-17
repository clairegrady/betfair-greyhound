#!/usr/bin/env python3
"""
Backfill paper_trades_greyhounds with actual dog names from GreyhoundMarketBook
Replaces "Runner XXXXX" and "Dog XXXXX" with real names
"""

import sqlite3
import time

# Configuration
BETFAIR_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
PAPER_TRADES_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"

def backfill_paper_trades_dog_names():
    """Backfill dog names in paper_trades from GreyhoundMarketBook"""
    print("=" * 80)
    print("🐕 Backfill Paper Trades Dog Names")
    print("=" * 80)
    
    try:
        # Connect to both databases
        betfair_conn = sqlite3.connect(BETFAIR_DB_PATH)
        paper_conn = sqlite3.connect(PAPER_TRADES_DB_PATH)
        
        paper_cursor = paper_conn.cursor()
        paper_cursor.execute("PRAGMA journal_mode=WAL;")
        paper_cursor.execute("PRAGMA busy_timeout = 30000;")
        
        # First, check the schema
        print("\n📋 Checking paper_trades schema...")
        paper_cursor.execute("PRAGMA table_info(paper_trades)")
        columns = [row[1] for row in paper_cursor.fetchall()]
        print(f"  Columns: {', '.join(columns)}")
        
        # Get all trades that need dog names (Runner XXXXX or Dog XXXXX or NULL)
        print("\n📊 Finding trades with incorrect dog names...")
        paper_cursor.execute("""
            SELECT DISTINCT market_id, selection_id, dog_name
            FROM paper_trades
            WHERE dog_name IS NULL 
               OR dog_name = '' 
               OR dog_name LIKE 'Runner %'
               OR dog_name LIKE 'Dog %'
            ORDER BY market_id, selection_id
        """)
        
        trades = paper_cursor.fetchall()
        print(f"✅ Found {len(trades)} unique market/runner combinations needing names")
        
        if not trades:
            print("\n✅ All paper_trades already have correct dog names!")
            paper_conn.close()
            betfair_conn.close()
            return
        
        # Show preview
        print("\n📋 Preview of first 10:")
        for market_id, selection_id, dog_name in trades[:10]:
            print(f"  • Market {market_id}, Runner {selection_id}: '{dog_name}'")
        if len(trades) > 10:
            print(f"  ... and {len(trades) - 10} more")
        
        # For each trade, find the dog name from GreyhoundMarketBook
        betfair_cursor = betfair_conn.cursor()
        updated = 0
        not_found = 0
        
        print("\n🔄 Updating dog names...")
        
        for market_id, selection_id, old_name in trades:
            # Find runner name from GreyhoundMarketBook
            # Try exact market first, then any market with this SelectionId
            betfair_cursor.execute("""
                SELECT RunnerName
                FROM GreyhoundMarketBook
                WHERE SelectionId = ?
                AND RunnerName NOT LIKE 'Runner %'
                ORDER BY 
                    CASE WHEN MarketId = ? THEN 0 ELSE 1 END,
                    ROWID DESC
                LIMIT 1
            """, (selection_id, market_id))
            
            result = betfair_cursor.fetchone()
            if result and result[0]:
                runner_name = result[0]
                
                # Update paper_trades with retry logic
                for attempt in range(3):
                    try:
                        paper_cursor.execute("""
                            UPDATE paper_trades
                            SET dog_name = ?
                            WHERE market_id = ?
                            AND selection_id = ?
                            AND (dog_name IS NULL OR dog_name = '' OR dog_name LIKE 'Runner %' OR dog_name LIKE 'Dog %')
                        """, (runner_name, market_id, selection_id))
                        
                        if paper_cursor.rowcount > 0:
                            updated += paper_cursor.rowcount
                            print(f"  ✅ Market {market_id}, Runner {selection_id}: '{old_name}' → '{runner_name}' ({paper_cursor.rowcount} rows)")
                        break
                    except sqlite3.OperationalError as e:
                        if 'locked' in str(e) and attempt < 2:
                            time.sleep(1)
                        else:
                            raise
            else:
                not_found += 1
                if not_found <= 5:  # Only show first 5
                    print(f"  ⚠️  Market {market_id}, Runner {selection_id}: No name found in GreyhoundMarketBook")
        
        paper_conn.commit()
        paper_conn.close()
        betfair_conn.close()
        
        print("\n" + "=" * 80)
        print("📊 Summary:")
        print(f"  ✅ Updated {updated} paper_trades entries with actual dog names")
        if not_found > 0:
            print(f"  ⚠️  {not_found} entries still missing (no name in GreyhoundMarketBook)")
        print("=" * 80)
        
        # Check remaining
        paper_conn2 = sqlite3.connect(PAPER_TRADES_DB_PATH)
        cursor2 = paper_conn2.cursor()
        cursor2.execute("""
            SELECT COUNT(*) 
            FROM paper_trades
            WHERE dog_name IS NULL 
               OR dog_name = '' 
               OR dog_name LIKE 'Runner %'
               OR dog_name LIKE 'Dog %'
        """)
        remaining = cursor2.fetchone()[0]
        paper_conn2.close()
        
        if remaining > 0:
            print(f"\n💡 {remaining} entries still need dog names")
            print("   These are likely from markets not yet in GreyhoundMarketBook")
        else:
            print(f"\n🎉 All paper_trades now have correct dog names!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        backfill_paper_trades_dog_names()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
