#!/usr/bin/env python3
"""
Re-fetch Market Catalogues and backfill runner names
Uses the backend's /api/ManageOrders/refetch-catalogues endpoint
"""

import sqlite3
import requests
import time

# Configuration
BETFAIR_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
PAPER_TRADES_DB_PATH = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BACKEND_URL = "http://localhost:5173"

def get_events_with_runner_issues():
    """Get event IDs that have Runner XXXXX entries"""
    conn = sqlite3.connect(BETFAIR_DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT mc.EventId, mc.EventName, mc.CountryCode, COUNT(DISTINCT gmb.MarketId) as markets
        FROM GreyhoundMarketBook gmb
        INNER JOIN MarketCatalogue mc ON gmb.MarketId = mc.MarketId
        WHERE gmb.RunnerName LIKE 'Runner %'
        GROUP BY mc.EventId, mc.EventName, mc.CountryCode
        ORDER BY markets DESC
    """
    
    cursor.execute(query)
    events = cursor.fetchall()
    conn.close()
    
    return events

def trigger_backend_catalogue_refetch(event_id):
    """Trigger the backend to re-fetch Market Catalogue for an event"""
    try:
        # The GreyhoundBackgroundWorker should have a method we can trigger
        # For now, we'll directly call the automation service endpoint
        url = f"{BACKEND_URL}/api/GreyhoundAutomation/fetch-catalogue/{event_id}"
        response = requests.post(url, timeout=60)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return None

def update_from_market_catalogue_table():
    """
    Copy runner names from recently updated MarketCatalogue entries
    This handles the case where the backend successfully fetched but didn't backfill
    """
    conn = sqlite3.connect(BETFAIR_DB_PATH)
    cursor = conn.cursor()
    
    # Enable WAL
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")
    
    # For each market with Runner XXXXX, try to find runner names from the same SelectionId
    query = """
        SELECT DISTINCT 
            bad.MarketId,
            bad.SelectionId,
            good.RunnerName,
            COUNT(*) as rows
        FROM GreyhoundMarketBook bad
        INNER JOIN GreyhoundMarketBook good 
            ON bad.SelectionId = good.SelectionId
        WHERE bad.RunnerName LIKE 'Runner %'
        AND good.RunnerName NOT LIKE 'Runner %'
        GROUP BY bad.MarketId, bad.SelectionId, good.RunnerName
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    total_updated = 0
    for market_id, selection_id, runner_name, _ in results:
        update_query = """
            UPDATE GreyhoundMarketBook
            SET RunnerName = ?
            WHERE MarketId = ?
            AND SelectionId = ?
            AND RunnerName LIKE 'Runner %'
        """
        
        for attempt in range(3):
            try:
                cursor.execute(update_query, (runner_name, market_id, selection_id))
                total_updated += cursor.rowcount
                break
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and attempt < 2:
                    time.sleep(1)
    
    conn.commit()
    conn.close()
    
    return total_updated

def backfill_paper_trades():
    """Backfill paper_trades from GreyhoundMarketBook"""
    print("\n📊 Backfilling paper_trades_greyhounds...")
    
    try:
        # Connect to both databases
        betfair_conn = sqlite3.connect(BETFAIR_DB_PATH)
        paper_conn = sqlite3.connect(PAPER_TRADES_DB_PATH)
        
        paper_cursor = paper_conn.cursor()
        paper_cursor.execute("PRAGMA journal_mode=WAL;")
        paper_cursor.execute("PRAGMA busy_timeout = 30000;")
        
        # Get all trades that need dog names
        paper_cursor.execute("""
            SELECT DISTINCT market_id, selection_id
            FROM paper_trades
            WHERE dog_name IS NULL OR dog_name = '' OR dog_name LIKE 'Runner %'
        """)
        
        trades = paper_cursor.fetchall()
        print(f"  Found {len(trades)} trades needing dog names")
        
        if not trades:
            paper_conn.close()
            betfair_conn.close()
            return 0
        
        # For each trade, find the dog name from GreyhoundMarketBook
        betfair_cursor = betfair_conn.cursor()
        updated = 0
        
        for market_id, selection_id in trades:
            # Find runner name
            betfair_cursor.execute("""
                SELECT RunnerName
                FROM GreyhoundMarketBook
                WHERE MarketId = ?
                AND SelectionId = ?
                AND RunnerName NOT LIKE 'Runner %'
                LIMIT 1
            """, (market_id, selection_id))
            
            result = betfair_cursor.fetchone()
            if result and result[0]:
                runner_name = result[0]
                
                # Update paper_trades
                paper_cursor.execute("""
                    UPDATE paper_trades
                    SET dog_name = ?
                    WHERE market_id = ?
                    AND selection_id = ?
                """, (runner_name, market_id, selection_id))
                
                updated += paper_cursor.rowcount
        
        paper_conn.commit()
        paper_conn.close()
        betfair_conn.close()
        
        print(f"  ✅ Updated {updated} paper_trades entries")
        return updated
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 0

def main():
    print("=" * 80)
    print("🔄 Market Catalogue Re-fetch and Backfill")
    print("=" * 80)
    
    # Step 1: Update from existing data
    print("\n1️⃣  Backfilling from existing GreyhoundMarketBook data...")
    updated = update_from_market_catalogue_table()
    print(f"✅ Updated {updated} entries from existing data")
    
    # Step 2: Backfill paper_trades
    print("\n2️⃣  Backfilling paper_trades_greyhounds...")
    paper_updated = backfill_paper_trades()
    
    # Step 3: Check remaining
    conn = sqlite3.connect(BETFAIR_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as remaining,
               COUNT(DISTINCT MarketId) as markets,
               COUNT(DISTINCT SelectionId) as runners
        FROM GreyhoundMarketBook
        WHERE RunnerName LIKE 'Runner %'
    """)
    remaining, markets, runners = cursor.fetchone()
    conn.close()
    
    print("\n" + "=" * 80)
    print("📊 Summary:")
    print(f"  • GreyhoundMarketBook: Updated {updated} rows")
    print(f"  • paper_trades: Updated {paper_updated} rows")
    print(f"  • Remaining 'Runner XXXXX': {remaining:,} rows ({markets} markets, {runners} runners)")
    
    if remaining > 0:
        print(f"\n💡 To fix remaining entries:")
        print(f"   1. Restart your backend (wait for GreyhoundBackgroundWorker)")
        print(f"   2. Run this script again in 2-3 minutes")
    
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
