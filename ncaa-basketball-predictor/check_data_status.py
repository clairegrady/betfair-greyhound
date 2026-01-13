#!/usr/bin/env python3
"""
Check the current status of all data scrapers and data quality
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    
    print("=" * 80)
    print("NCAA BASKETBALL DATA STATUS")
    print("=" * 80)
    
    # Player stats by season
    print("\n📊 PLAYER_STATS TABLE:")
    print("-" * 80)
    df = pd.read_sql_query("""
        SELECT 
            season,
            COUNT(*) as total_players,
            COUNT(CASE WHEN player_name IS NOT NULL THEN 1 END) as have_name,
            COUNT(CASE WHEN offensive_rating IS NOT NULL THEN 1 END) as have_kenpom,
            COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) as have_sportsref,
            ROUND(100.0 * COUNT(CASE WHEN offensive_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct_kenpom,
            ROUND(100.0 * COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct_sportsref
        FROM player_stats
        GROUP BY season
        ORDER BY season
    """, conn)
    
    print(f"{'Season':<10} {'Total':>8} {'Names':>8} {'KenPom':>8} {'SportsRef':>11} {'% KenPom':>10} {'% SportsRef':>12}")
    print("-" * 80)
    for _, row in df.iterrows():
        season_label = f"{row['season']-1}-{str(row['season'])[-2:]}"  # e.g. "2024-25"
        print(f"{season_label:<10} {row['total_players']:>8} {row['have_name']:>8} {row['have_kenpom']:>8} {row['have_sportsref']:>11} {row['pct_kenpom']:>9.1f}% {row['pct_sportsref']:>11.1f}%")
    
    # Teams
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]
    print(f"\n👥 TEAMS TABLE: {total_teams} teams")
    
    # Games
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN home_score IS NOT NULL THEN 1 END) as completed,
            COUNT(CASE WHEN home_score IS NULL THEN 1 END) as upcoming
        FROM games
    """)
    total, completed, upcoming = cursor.fetchone()
    print(f"\n🏀 GAMES TABLE: {total:,} total ({completed:,} completed, {upcoming:,} upcoming)")
    
    # Check for data quality issues
    print("\n⚠️  DATA QUALITY CHECKS:")
    print("-" * 80)
    
    # Duplicate player_id + season in player_stats
    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT player_id, season
            FROM player_stats
            GROUP BY player_id, season
            HAVING COUNT(*) > 1
        )
    """)
    dupes = cursor.fetchone()[0]
    status = "✓" if dupes == 0 else f"❌ {dupes} duplicates"
    print(f"  Duplicate player_id+season in player_stats: {status}")
    
    # NULL names
    cursor.execute("SELECT COUNT(*) FROM player_stats WHERE player_name IS NULL")
    null_names = cursor.fetchone()[0]
    status = "✓" if null_names == 0 else f"❌ {null_names} NULL names"
    print(f"  NULL player names in player_stats: {status}")
    
    # Category headers (garbage data)
    cursor.execute("""
        SELECT COUNT(*) FROM player_stats 
        WHERE player_name LIKE '%Benchwarmer%' 
           OR player_name LIKE '%Go-to%'
           OR player_name LIKE '%Limited%'
           OR player_name LIKE '%Significant%'
           OR player_name LIKE '%Role%'
           OR player_name LIKE '%Major Contributor%'
           OR player_name LIKE '%Nearly invisible%'
    """)
    garbage = cursor.fetchone()[0]
    status = "✓" if garbage == 0 else f"❌ {garbage} garbage rows"
    print(f"  Category header rows (garbage): {status}")
    
    # Games with unrealistic scores
    cursor.execute("""
        SELECT COUNT(*) FROM games 
        WHERE home_score IS NOT NULL 
        AND (home_score + away_score = 0 
             OR home_score + away_score > 200 
             OR ABS(home_score - away_score) > 75)
    """)
    bad_games = cursor.fetchone()[0]
    status = "✓" if bad_games == 0 else f"⚠️  {bad_games} unrealistic scores"
    print(f"  Unrealistic game scores: {status}")
    
    print("\n" + "=" * 80)
    
    conn.close()

if __name__ == "__main__":
    main()
