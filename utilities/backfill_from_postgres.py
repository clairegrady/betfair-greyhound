#!/usr/bin/env python3
"""
Backfill paper_trades dog names from PostgreSQL betfairmarket database
The Postgres DB has historical runner names that didn't make it to SQLite during migration attempt
"""

import sqlite3
import psycopg2
import time

# Configuration
PAPER_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
PG_HOST = "localhost"
PG_PORT = 5432
PG_DATABASE = "betfairmarket"
PG_USER = "clairegrady"
PG_PASSWORD = "World17!"

def backfill_from_postgres():
    """Backfill dog names from PostgreSQL greyhoundmarketbook table"""
    print("=" * 80)
    print("🐕 Backfill Paper Trades from PostgreSQL")
    print("=" * 80)
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(PAPER_TRADES_DB)
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("PRAGMA journal_mode=WAL;")
    sqlite_cursor.execute("PRAGMA busy_timeout = 30000;")
    
    # Connect to PostgreSQL
    try:
        pg_conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DATABASE,
            user=PG_USER,
            password=PG_PASSWORD
        )
        pg_cursor = pg_conn.cursor()
        print("✅ Connected to PostgreSQL betfairmarket database")
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        sqlite_conn.close()
        return
    
    # Get all trades that need dog names
    print("\n📊 Finding trades with incorrect dog names...")
    sqlite_cursor.execute("""
        SELECT DISTINCT market_id, selection_id, dog_name
        FROM paper_trades
        WHERE dog_name IS NULL 
           OR dog_name = '' 
           OR dog_name LIKE 'Runner %'
           OR dog_name LIKE 'Dog %'
        ORDER BY market_id, selection_id
    """)
    
    trades = sqlite_cursor.fetchall()
    print(f"✅ Found {len(trades)} unique market/runner combinations needing names")
    
    if not trades:
        print("\n✅ All paper_trades already have correct dog names!")
        pg_conn.close()
        sqlite_conn.close()
        return
    
    # Show preview
    print("\n📋 Preview of first 10:")
    for market_id, selection_id, dog_name in trades[:10]:
        print(f"  • Market {market_id}, Runner {selection_id}: '{dog_name}'")
    if len(trades) > 10:
        print(f"  ... and {len(trades) - 10} more")
    
    print("\n🔄 Querying PostgreSQL for runner names...")
    
    updated = 0
    not_found = 0
    
    # For each trade, find runner name from PostgreSQL
    for market_id, selection_id, old_name in trades:
        try:
            # Query PostgreSQL greyhoundmarketbook
            # Try exact market first, then any market with this SelectionId
            pg_cursor.execute("""
                SELECT runnername
                FROM greyhoundmarketbook
                WHERE selectionid = %s
                AND runnername NOT LIKE 'Runner %%'
                ORDER BY 
                    CASE WHEN marketid = %s THEN 0 ELSE 1 END,
                    id DESC
                LIMIT 1
            """, (selection_id, market_id))
            
            result = pg_cursor.fetchone()
            
            if result and result[0]:
                runner_name = result[0]
                
                # Update SQLite paper_trades
                for attempt in range(3):
                    try:
                        sqlite_cursor.execute("""
                            UPDATE paper_trades
                            SET dog_name = ?
                            WHERE market_id = ?
                            AND selection_id = ?
                            AND (dog_name IS NULL OR dog_name = '' OR dog_name LIKE 'Runner %' OR dog_name LIKE 'Dog %')
                        """, (runner_name, market_id, selection_id))
                        
                        if sqlite_cursor.rowcount > 0:
                            updated += sqlite_cursor.rowcount
                            print(f"  ✅ Market {market_id}, Runner {selection_id}: '{old_name}' → '{runner_name}' ({sqlite_cursor.rowcount} rows)")
                        break
                    except sqlite3.OperationalError as e:
                        if 'locked' in str(e) and attempt < 2:
                            time.sleep(1)
                        else:
                            raise
            else:
                not_found += 1
                if not_found <= 5:
                    print(f"  ⚠️  Market {market_id}, Runner {selection_id}: No name found in PostgreSQL")
        
        except Exception as e:
            print(f"  ❌ Error for market {market_id}, runner {selection_id}: {e}")
    
    sqlite_conn.commit()
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n" + "=" * 80)
    print("📊 Summary:")
    print(f"  ✅ Updated {updated} paper_trades entries from PostgreSQL")
    if not_found > 0:
        print(f"  ⚠️  {not_found} entries still missing (not in PostgreSQL either)")
    print("=" * 80)
    
    # Check remaining
    sqlite_conn2 = sqlite3.connect(PAPER_TRADES_DB)
    cursor2 = sqlite_conn2.cursor()
    cursor2.execute("""
        SELECT COUNT(*) 
        FROM paper_trades
        WHERE dog_name IS NULL 
           OR dog_name = '' 
           OR dog_name LIKE 'Runner %'
           OR dog_name LIKE 'Dog %'
    """)
    remaining = cursor2.fetchone()[0]
    sqlite_conn2.close()
    
    if remaining > 0:
        print(f"\n💡 {remaining} entries still need dog names")
    else:
        print(f"\n🎉 All paper_trades now have correct dog names!")

if __name__ == "__main__":
    try:
        backfill_from_postgres()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
