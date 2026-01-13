"""
Clean up paper_trades table - remove old unused columns
Creates new table with only needed columns matching greyhound structure
"""

import sqlite3
import shutil
from datetime import datetime

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/paper_trades.db"

def clean_schema():
    """Recreate paper_trades with clean schema matching greyhounds"""
    
    # Backup first
    backup_path = DB_PATH.replace('.db', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    shutil.copy(DB_PATH, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create new clean table (matching greyhound structure)
    cursor.execute("""
        CREATE TABLE paper_trades_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            venue TEXT,
            country TEXT,
            race_number INTEGER,
            market_id TEXT,
            selection_id INTEGER,
            horse_name TEXT,
            box_number INTEGER,
            position_in_market INTEGER,
            odds REAL,
            stake REAL,
            liability REAL,
            finishing_position INTEGER DEFAULT 0,
            result TEXT DEFAULT 'pending',
            profit_loss REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Created new clean table")
    
    # Copy data from old table (only the columns we want)
    cursor.execute("""
        INSERT INTO paper_trades_new 
        (id, date, venue, country, race_number, market_id, selection_id, horse_name, 
         box_number, position_in_market, odds, stake, liability, finishing_position, 
         result, profit_loss, created_at)
        SELECT 
            id,
            COALESCE(date, strftime('%Y-%m-%d', placed_at)) as date,
            COALESCE(venue, track) as venue,
            country,
            race_number,
            market_id,
            selection_id,
            horse_name,
            box_number,
            position_in_market,
            COALESCE(odds, odds_taken) as odds,
            stake,
            liability,
            finishing_position,
            result,
            profit_loss,
            placed_at as created_at
        FROM paper_trades
        WHERE horse_name IS NOT NULL
    """)
    
    rows_copied = cursor.rowcount
    print(f"✅ Copied {rows_copied} rows")
    
    # Drop old table
    cursor.execute("DROP TABLE paper_trades")
    print("✅ Dropped old table")
    
    # Rename new table
    cursor.execute("ALTER TABLE paper_trades_new RENAME TO paper_trades")
    print("✅ Renamed new table")
    
    # Show final schema
    cursor.execute("PRAGMA table_info(paper_trades)")
    columns = cursor.fetchall()
    
    print("\n📊 Final schema:")
    for col in columns:
        print(f"   {col[1]} ({col[2]})")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Schema cleanup complete!")
    print(f"   Backup saved to: {backup_path}")

if __name__ == "__main__":
    clean_schema()
