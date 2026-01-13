"""
Update paper_trades schema to match greyhound structure
Adds: box_number, country, position_in_market, liability, finishing_position, date
"""

import sqlite3

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/paper_trades.db"

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(paper_trades)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    print(f"Existing columns: {existing_columns}")
    
    columns_to_add = {
        'box_number': 'INTEGER',
        'country': 'TEXT',
        'position_in_market': 'INTEGER',
        'liability': 'REAL',
        'finishing_position': 'INTEGER DEFAULT 0',
        'date': 'TEXT'
    }
    
    added = []
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE paper_trades ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
                print(f"✅ Added column: {col_name}")
            except Exception as e:
                print(f"⚠️  Error adding {col_name}: {e}")
        else:
            print(f"⏭️  Column {col_name} already exists")
    
    conn.commit()
    conn.close()
    
    if added:
        print(f"\n✅ Successfully added {len(added)} new columns")
    else:
        print(f"\n✅ Schema is up to date")

if __name__ == "__main__":
    update_schema()
