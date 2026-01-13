#!/usr/bin/env python3
"""
Autonomous scraping monitor - runs overnight
Monitors all scrapers, validates data, rebuilds features, retrains model
"""

import sqlite3
import time
import subprocess
from pathlib import Path
import sys

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def get_data_status():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    status = {}
    for season in [2024, 2025, 2026]:
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT player_id) as total,
                COUNT(DISTINCT CASE WHEN offensive_rating IS NOT NULL THEN player_id END) as ortg,
                COUNT(DISTINCT CASE WHEN points_per_game IS NOT NULL THEN player_id END) as ppg
            FROM player_stats WHERE season = {season}
        """)
        row = cursor.fetchone()
        status[season] = {'total': row[0], 'ortg': row[1], 'ppg': row[2]}
    
    conn.close()
    return status

def check_scraper_running(log_file):
    log_path = Path(__file__).parent / log_file
    if not log_path.exists():
        return False
    try:
        size1 = log_path.stat().st_size
        time.sleep(3)
        size2 = log_path.stat().st_size
        return size2 > size1
    except:
        return False

def restart_scraper_if_needed(script, season, log_file):
    if not check_scraper_running(log_file):
        print(f"🔄 Restarting {script} for season {season}...")
        cmd = f"cd {Path(__file__).parent} && nohup python3 pipelines/{script} {season} > {log_file} 2>&1 &"
        subprocess.run(cmd, shell=True)
        time.sleep(5)

def main():
    print("🤖 AUTONOMOUS OVERNIGHT SCRAPING")
    print("="*70)
    print("Started:", time.strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    iteration = 0
    all_complete = False
    
    while not all_complete:
        iteration += 1
        status = get_data_status()
        
        print(f"\n[{time.strftime('%H:%M:%S')}] Update #{iteration}")
        print("-"*70)
        
        targets = {2024: 3800, 2025: 4200, 2026: 3400}
        ready = []
        
        for season in [2024, 2025, 2026]:
            s = status[season]
            target = targets[season]
            ortg_pct = s['ortg'] / target * 100 if target > 0 else 0
            ppg_pct = s['ppg'] / target * 100 if target > 0 else 0
            
            kenpom_ready = s['ortg'] > target * 0.95
            sportsref_ready = s['ppg'] > target * 0.85
            
            print(f"Season {season}: KenPom {s['ortg']:,}/{target:,} ({ortg_pct:.0f}%) | "
                  f"SportsRef {s['ppg']:,}/{target:,} ({ppg_pct:.0f}%)")
            
            if kenpom_ready and sportsref_ready:
                print(f"  ✅ COMPLETE")
                ready.append(season)
            else:
                # Check and restart if needed
                restart_scraper_if_needed('scrape_season.py', season, f'scrape_{season}.log')
                restart_scraper_if_needed('scrape_sports_reference.py', season, f'scrape_sportsref_{season}.log')
        
        if len(ready) == 3:
            print("\n🎉 ALL DATA COMPLETE!")
            all_complete = True
            break
        
        print(f"\n⏳ {len(ready)}/3 seasons complete. Sleeping 60s...")
        time.sleep(60)
    
    # Data validation
    print("\n" + "="*70)
    print("📊 VALIDATING DATA QUALITY")
    print("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Check for nulls
    for season in [2024, 2025, 2026]:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN offensive_rating IS NULL THEN 1 ELSE 0 END) as null_ortg,
                SUM(CASE WHEN usage_rate IS NULL THEN 1 ELSE 0 END) as null_usage,
                SUM(CASE WHEN minutes_played IS NULL THEN 1 ELSE 0 END) as null_minutes
            FROM player_stats WHERE season = {season}
        """)
        row = cursor.fetchone()
        print(f"\nSeason {season}:")
        print(f"  Total: {row[0]:,} players")
        print(f"  Null ORtg: {row[1]:,} ({row[1]/max(row[0],1)*100:.1f}%)")
        print(f"  Null Usage: {row[2]:,} ({row[2]/max(row[0],1)*100:.1f}%)")
        print(f"  Null Minutes: {row[3]:,} ({row[3]/max(row[0],1)*100:.1f}%)")
    
    conn.close()
    
    # Rebuild features
    print("\n" + "="*70)
    print("🔨 REBUILDING FEATURES")
    print("="*70)
    subprocess.run("python3 pipelines/feature_engineering_v2.py", shell=True, cwd=Path(__file__).parent)
    
    # Retrain model
    print("\n" + "="*70)
    print("🧠 RETRAINING MODEL")
    print("="*70)
    subprocess.run("python3 pipelines/train_multitask_model.py", shell=True, cwd=Path(__file__).parent)
    
    # Test predictions
    print("\n" + "="*70)
    print("🎯 TESTING PREDICTIONS")
    print("="*70)
    subprocess.run("python3 show_predictions.py | head -100", shell=True, cwd=Path(__file__).parent)
    
    print("\n" + "="*70)
    print("✅ COMPLETE!")
    print("="*70)
    print("Finished:", time.strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

