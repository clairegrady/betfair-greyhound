"""
Reset ALL live trades back to pending so they can be properly re-settled
"""
import psycopg2
from datetime import datetime
import sys
import os

# Add the parent directory to the sys.path to import db_connection_helper
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utilities')))
from db_connection_helper import get_db_connection

LIVE_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/live_trades_greyhounds.db"

def main():
    print("="*80)
    print("🔄 RESETTING ALL LIVE TRADES TO PENDING")
    print("="*80)
    
    conn = None
    try:
        conn = get_db_connection(LIVE_TRADES_DB)
        cursor = conn.cursor()

        # Count current settled bets
        cursor.execute("""
            SELECT 
                date,
                COUNT(*) as count,
                SUM(CASE WHEN result='won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='lost' THEN 1 ELSE 0 END) as losses
            FROM live_trades
            WHERE result IN ('won', 'lost')
            GROUP BY date
            ORDER BY date
        """)
        
        settled_by_date = cursor.fetchall()
        
        if not settled_by_date:
            print("✅ No settled bets found to reset")
            return
        
        print("\nCurrently settled bets:")
        print("-" * 80)
        total_settled = 0
        for date, count, wins, losses in settled_by_date:
            print(f"  {date}: {count} bets ({wins}W / {losses}L)")
            total_settled += count
        print("-" * 80)
        print(f"  TOTAL: {total_settled} settled bets")
        print()
        
        # Ask for confirmation
        response = input(f"⚠️  Reset all {total_settled} bets to 'pending'? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled")
            return
        
        # Reset them to pending
        cursor.execute("""
            UPDATE live_trades
            SET result = 'pending', 
                profit_loss = 0, 
                finishing_position = 0, 
                bsp = NULL
            WHERE result IN ('won', 'lost')
        """)
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ Successfully reset {rows_updated} bets to 'pending'")
        print()
        print("Now run: python3 check_results_LIVE.py")
        print("="*80)

    except ValueError as ve:
        print(f"❌ Database connection error: {ve}")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
