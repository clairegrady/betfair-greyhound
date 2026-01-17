#!/usr/bin/env python3
"""
Backfill runner names in GreyhoundMarketBook table
Uses the backend's existing Market Catalogue data to fill in "Runner XXXXX" entries
"""

import sqlite3
import sys
import time

# Configuration
BETFAIR_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"

def backfill_from_existing_data():
    """
    Backfill runner names by finding entries where the same SelectionId 
    has a real name in other rows
    """
    print("=" * 80)
    print("🐕 Greyhound Runner Names Backfill Script")
    print("=" * 80)
    
    conn = sqlite3.connect(BETFAIR_DB_PATH)
    cursor = conn.cursor()
    
    # Find all SelectionIds that have BOTH "Runner XXXXX" and actual names
    print("\n📊 Finding SelectionIds with mixed names...")
    
    query = """
        SELECT DISTINCT 
            bad.MarketId,
            bad.SelectionId,
            good.RunnerName,
            COUNT(*) as bad_rows
        FROM GreyhoundMarketBook bad
        INNER JOIN GreyhoundMarketBook good 
            ON bad.SelectionId = good.SelectionId
        WHERE bad.RunnerName LIKE 'Runner %'
        AND good.RunnerName NOT LIKE 'Runner %'
        GROUP BY bad.MarketId, bad.SelectionId, good.RunnerName
        ORDER BY bad_rows DESC
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    print(f"✅ Found {len(results)} SelectionId/Market combinations to fix")
    
    if not results:
        print("\n✅ No entries need backfilling!")
        conn.close()
        return
    
    # Show what we found
    print("\n📋 Preview of fixes:")
    for market_id, selection_id, runner_name, count in results[:10]:
        print(f"  • Market {market_id}, Runner {selection_id} → '{runner_name}' ({count} rows)")
    
    if len(results) > 10:
        print(f"  ... and {len(results) - 10} more")
    
    # Confirm (auto-confirm if no TTY)
    print(f"\n⚠️  This will update runner names for {len(results)} SelectionId/Market combinations")
    
    if sys.stdin.isatty():
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            conn.close()
            return
    else:
        print("✅ Auto-confirming (no interactive terminal)")
        response = 'y'
    
    # Perform updates
    print("\n🔄 Updating database...")
    total_updated = 0
    
    # Enable WAL mode and set busy timeout
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")  # 30 seconds
    
    for market_id, selection_id, runner_name, _ in results:
        update_query = """
            UPDATE GreyhoundMarketBook
            SET RunnerName = ?
            WHERE MarketId = ?
            AND SelectionId = ?
            AND RunnerName LIKE 'Runner %'
        """
        
        # Retry on lock
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cursor.execute(update_query, (runner_name, market_id, selection_id))
                updated = cursor.rowcount
                total_updated += updated
                
                if updated > 0:
                    print(f"  ✅ Market {market_id}, Runner {selection_id} → '{runner_name}' ({updated} rows)")
                break
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and attempt < max_retries - 1:
                    print(f"  ⏳ Database locked, retrying in 2s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    raise
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"✅ COMPLETE! Updated {total_updated} runner name entries")
    print("=" * 80)

def check_remaining():
    """Check how many 'Runner XXXXX' entries remain"""
    conn = sqlite3.connect(BETFAIR_DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT COUNT(*) as remaining,
               COUNT(DISTINCT MarketId) as markets,
               COUNT(DISTINCT SelectionId) as runners
        FROM GreyhoundMarketBook
        WHERE RunnerName LIKE 'Runner %'
    """
    
    cursor.execute(query)
    remaining, markets, runners = cursor.fetchone()
    
    conn.close()
    
    print(f"\n📊 Remaining 'Runner XXXXX' entries:")
    print(f"  • {remaining:,} total rows")
    print(f"  • {markets} unique markets")
    print(f"  • {runners} unique runners")
    
    if remaining > 0:
        print("\n💡 These are likely from markets where we never fetched the Market Catalogue")
        print("   They will get proper names as soon as the backend fetches the catalogue")

if __name__ == "__main__":
    try:
        backfill_from_existing_data()
        check_remaining()
    except KeyboardInterrupt:
        print("\n\n⚠️  Backfill interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
