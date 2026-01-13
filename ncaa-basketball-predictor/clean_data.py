"""
Clean NCAA Basketball Data
- Remove impossible games
- Fix outliers
- Validate data quality
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def clean_games():
    """Remove games with impossible scores"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*70)
    print("🧹 CLEANING GAMES DATA")
    print("="*70)
    
    # Count before
    cursor.execute("SELECT COUNT(*) FROM games")
    before_count = cursor.fetchone()[0]
    print(f"\nGames before cleaning: {before_count:,}")
    
    # Remove games with total_points = 0 (data errors)
    cursor.execute("DELETE FROM games WHERE (home_score + away_score) = 0")
    deleted_zero = cursor.rowcount
    print(f"  Deleted {deleted_zero} games with 0 total points")
    
    # Remove games with impossibly high totals (>200)
    cursor.execute("DELETE FROM games WHERE (home_score + away_score) > 200")
    deleted_high = cursor.rowcount
    print(f"  Deleted {deleted_high} games with >200 total points")
    
    # Remove games with margin > 75 (likely data errors)
    cursor.execute("""
        DELETE FROM games 
        WHERE ABS(CAST(home_score AS INTEGER) - CAST(away_score AS INTEGER)) > 75
    """)
    deleted_margin = cursor.rowcount
    print(f"  Deleted {deleted_margin} games with margin >75 points")
    
    # Count after
    cursor.execute("SELECT COUNT(*) FROM games")
    after_count = cursor.fetchone()[0]
    print(f"\nGames after cleaning: {after_count:,}")
    print(f"Total deleted: {before_count - after_count:,}")
    
    conn.commit()
    conn.close()


def validate_cleaned_data():
    """Validate the cleaned data"""
    conn = sqlite3.connect(DB_PATH)
    
    print("\n" + "="*70)
    print("✅ VALIDATION")
    print("="*70)
    
    # Check point totals
    df = pd.read_sql_query("""
        SELECT 
            MIN(home_score + away_score) as min_total,
            MAX(home_score + away_score) as max_total,
            AVG(home_score + away_score) as avg_total,
            MIN(ABS(home_score - away_score)) as min_margin,
            MAX(ABS(home_score - away_score)) as max_margin,
            AVG(ABS(home_score - away_score)) as avg_margin
        FROM games
        WHERE home_score IS NOT NULL
    """, conn)
    
    print("\nTotal Points:")
    print(f"  Min: {df['min_total'][0]:.0f}")
    print(f"  Max: {df['max_total'][0]:.0f}")
    print(f"  Avg: {df['avg_total'][0]:.1f}")
    
    print("\nPoint Margins:")
    print(f"  Min: {df['min_margin'][0]:.0f}")
    print(f"  Max: {df['max_margin'][0]:.0f}")
    print(f"  Avg: {df['avg_margin'][0]:.1f}")
    
    conn.close()


if __name__ == '__main__':
    clean_games()
    validate_cleaned_data()
    print("\n✅ Data cleaning complete!\n")

