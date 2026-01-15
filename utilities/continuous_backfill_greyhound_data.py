#!/usr/bin/env python3
"""
Continuously backfill missing dog names and box numbers from backend
Run this alongside your lay betting scripts
"""

import sqlite3
import re
import time
from datetime import datetime

PAPER_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BACKEND_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
CHECK_INTERVAL = 60  # Check every 60 seconds

def clean_dog_name(name):
    """Remove trap number prefix from dog name"""
    if not name:
        return None
    return re.sub(r'^\d+\.\s*', '', name)

def backfill_missing_data():
    """Backfill any trades missing names or box numbers"""
    
    paper_conn = sqlite3.connect(PAPER_TRADES_DB)
    paper_cursor = paper_conn.cursor()
    
    backend_conn = sqlite3.connect(BACKEND_DB)
    backend_cursor = backend_conn.cursor()
    
    # Get today's trades with missing data
    today = datetime.now().strftime('%Y-%m-%d')
    paper_cursor.execute("""
        SELECT id, market_id, selection_id, dog_name, box_number
        FROM paper_trades
        WHERE date = ?
          AND ((dog_name LIKE 'Dog %' OR dog_name LIKE 'Runner %')
               OR (box_number IS NULL OR box_number = 0))
    """, (today,))
    
    trades_to_update = paper_cursor.fetchall()
    
    if not trades_to_update:
        return 0, 0
    
    updated_names = 0
    updated_boxes = 0
    
    for trade_id, market_id, selection_id, current_name, current_box in trades_to_update:
        backend_cursor.execute("""
            SELECT DISTINCT RunnerName, box
            FROM GreyhoundMarketBook
            WHERE MarketId = ? AND SelectionId = ?
            AND RunnerName IS NOT NULL
            LIMIT 1
        """, (market_id, selection_id))
        
        result = backend_cursor.fetchone()
        
        if result:
            backend_name, backend_box = result
            clean_name = clean_dog_name(backend_name)
            
            needs_name_update = (current_name.startswith('Dog ') or current_name.startswith('Runner ')) and clean_name
            needs_box_update = (current_box is None or current_box == 0) and backend_box
            
            if needs_name_update or needs_box_update:
                updates = []
                params = []
                
                if needs_name_update:
                    updates.append("dog_name = ?")
                    params.append(clean_name)
                    updated_names += 1
                
                if needs_box_update:
                    updates.append("box_number = ?")
                    params.append(backend_box)
                    updated_boxes += 1
                
                params.append(trade_id)
                
                paper_cursor.execute(f"""
                    UPDATE paper_trades
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
    
    paper_conn.commit()
    paper_conn.close()
    backend_conn.close()
    
    return updated_names, updated_boxes

def main():
    """Run continuous backfill loop"""
    print(f"🔄 Starting continuous backfill service...")
    print(f"   Checking every {CHECK_INTERVAL} seconds")
    print(f"   Press Ctrl+C to stop\n")
    
    try:
        while True:
            names, boxes = backfill_missing_data()
            
            if names > 0 or boxes > 0:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] ✅ Updated {names} names, {boxes} boxes")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Stopping backfill service...")

if __name__ == "__main__":
    main()
