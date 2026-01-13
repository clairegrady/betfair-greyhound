#!/usr/bin/env python3
"""
Monitor ALL data scraping progress for Season 2024 rescrape
Checks KenPom, Sports Reference, and Lineups
"""

import sqlite3
from pathlib import Path
import time
import os
import signal
import sys

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def check_process_running(log_file):
    """Check if scraper is still running by monitoring log file"""
    if not Path(log_file).exists():
        return False, 0
    
    # Check if file is being written to (size changing)
    try:
        size1 = Path(log_file).stat().st_size
        time.sleep(2)
        size2 = Path(log_file).stat().st_size
        return size2 > size1, size2
    except:
        return False, 0

def get_progress():
    """Get current scraping progress"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # KenPom player stats
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT player_id) as total_players,
            COUNT(DISTINCT CASE WHEN offensive_rating IS NOT NULL THEN player_id END) as with_ortg,
            COUNT(DISTINCT CASE WHEN minutes_played IS NOT NULL AND minutes_played > 0 THEN player_id END) as with_minutes
        FROM player_stats
        WHERE season = 2024
    """)
    kenpom = cursor.fetchone()
    
    # Sports Reference stats
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT player_id) as total,
            COUNT(DISTINCT CASE WHEN points_per_game IS NOT NULL THEN player_id END) as with_stats
        FROM player_stats
        WHERE season = 2024
    """)
    sportsref = cursor.fetchone()
    
    # Lineups
    cursor.execute("""
        SELECT COUNT(DISTINCT game_id) as games_with_lineups
        FROM game_lineups gl
        JOIN games g ON gl.game_id = g.game_id
        WHERE g.season = 2024
    """)
    lineups = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM games WHERE season = 2024 AND home_score IS NOT NULL")
    total_games_2024 = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'kenpom_total': kenpom[0],
        'kenpom_ortg': kenpom[1],
        'kenpom_minutes': kenpom[2],
        'sportsref_total': sportsref[0],
        'sportsref_stats': sportsref[1],
        'lineups': lineups[0],
        'total_games': total_games_2024
    }

def print_progress(iteration=0):
    """Print current progress"""
    prog = get_progress()
    
    # Check if scrapers are running
    kenpom_running, kenpom_log_size = check_process_running("scrape_2024.log")
    sportsref_running, sportsref_log_size = check_process_running("scrape_sportsref_2024.log")
    
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("="*70)
    print("📊 SEASON 2024 (2023-24) DATA COLLECTION PROGRESS")
    print("="*70)
    print(f"Update #{iteration} - {time.strftime('%H:%M:%S')}")
    print()
    
    print("🔵 KENPOM PLAYER DATA (Efficiency, Usage, etc.)")
    print("-"*70)
    print(f"  Total players:        {prog['kenpom_total']:,}")
    print(f"  With ORtg:            {prog['kenpom_ortg']:,} ({prog['kenpom_ortg']/max(prog['kenpom_total'],1)*100:.1f}%)")
    print(f"  With minutes:         {prog['kenpom_minutes']:,} ({prog['kenpom_minutes']/max(prog['kenpom_total'],1)*100:.1f}%)")
    print(f"  Status:               {'🟢 RUNNING' if kenpom_running else '🔴 STOPPED'}")
    if kenpom_log_size > 0:
        print(f"  Log size:             {kenpom_log_size:,} bytes")
    print()
    
    print("🟢 SPORTS REFERENCE PLAYER STATS (PPG, RPG, APG, etc.)")
    print("-"*70)
    print(f"  Total players:        {prog['sportsref_total']:,}")
    print(f"  With stats:           {prog['sportsref_stats']:,} ({prog['sportsref_stats']/max(prog['sportsref_total'],1)*100:.1f}%)")
    print(f"  Status:               {'🟢 RUNNING' if sportsref_running else '🔴 STOPPED'}")
    if sportsref_log_size > 0:
        print(f"  Log size:             {sportsref_log_size:,} bytes")
    print()
    
    print("🟡 GAME LINEUPS (Starters + Bench)")
    print("-"*70)
    print(f"  Games with lineups:   {prog['lineups']:,} / {prog['total_games']:,} ({prog['lineups']/max(prog['total_games'],1)*100:.1f}%)")
    print()
    
    print("="*70)
    print("📈 OVERALL READINESS")
    print("="*70)
    
    # Calculate readiness score
    kenpom_ready = prog['kenpom_ortg'] > 3000  # Target: ~4000 players
    sportsref_ready = prog['sportsref_stats'] > 3000
    lineups_ready = prog['lineups'] / max(prog['total_games'], 1) > 0.90
    
    ready_count = sum([kenpom_ready, sportsref_ready, lineups_ready])
    
    print(f"  KenPom data:          {'✅ READY' if kenpom_ready else '⏳ IN PROGRESS'}")
    print(f"  Sports Ref data:      {'✅ READY' if sportsref_ready else '⏳ IN PROGRESS'}")
    print(f"  Lineup data:          {'✅ READY' if lineups_ready else '⏳ IN PROGRESS'}")
    print()
    
    if ready_count == 3:
        print("🎉 ALL DATA COMPLETE! Ready to rebuild features and retrain model.")
    else:
        print(f"⏳ {ready_count}/3 datasets ready. Continuing to scrape...")
    
    print("="*70)
    print("Press Ctrl+C to stop monitoring (scrapers will continue in background)")
    print()

def signal_handler(sig, frame):
    print('\n\n👋 Monitoring stopped. Scrapers continue in background.')
    print('Check logs: scrape_2024.log, scrape_sportsref_2024.log')
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    iteration = 0
    while True:
        print_progress(iteration)
        iteration += 1
        time.sleep(30)  # Update every 30 seconds

if __name__ == '__main__':
    main()

