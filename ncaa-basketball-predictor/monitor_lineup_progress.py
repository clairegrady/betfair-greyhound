"""
Monitor lineup scraping progress
"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"


def check_progress():
    """Check lineup scraping progress"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total games to scrape
    cursor.execute("""
        SELECT COUNT(*) FROM games WHERE season IN (2024, 2025, 2026)
    """)
    total_games = cursor.fetchone()[0]
    
    # Games with lineups
    cursor.execute("""
        SELECT COUNT(DISTINCT game_id) FROM game_lineups
    """)
    games_with_lineups = cursor.fetchone()[0]
    
    # Player records
    cursor.execute("SELECT COUNT(*) FROM game_lineups")
    total_players = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_lineups WHERE is_starter = 1")
    starters = cursor.fetchone()[0]
    
    # Recent additions
    cursor.execute("""
        SELECT MAX(ROWID) FROM game_lineups
    """)
    max_row = cursor.fetchone()[0] or 0
    
    conn.close()
    
    pct = (games_with_lineups / total_games * 100) if total_games > 0 else 0
    
    print("\n" + "="*60)
    print(f"🏀 LINEUP SCRAPING PROGRESS")
    print("="*60)
    print(f"Games with lineups: {games_with_lineups:,} / {total_games:,} ({pct:.1f}%)")
    print(f"Player records: {total_players:,}")
    print(f"  - Starters: {starters:,}")
    print(f"  - Bench: {total_players - starters:,}")
    print(f"Latest row ID: {max_row:,}")
    print("="*60 + "\n")
    
    return pct


if __name__ == "__main__":
    while True:
        try:
            progress = check_progress()
            
            if progress >= 99:
                print("✅ Scraping appears complete!")
                break
            
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

