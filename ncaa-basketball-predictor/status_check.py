#!/usr/bin/env python3
"""
Quick status check - shows what's running and current progress
"""

import sqlite3
from pathlib import Path
import os

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def check_log_active(log_file):
    """Check if log file is being written to"""
    log_path = Path(__file__).parent / log_file
    if not log_path.exists():
        return False, 0
    
    size = log_path.stat().st_size
    return size > 0, size

def main():
    print("\n" + "="*70)
    print("📊 NCAA BASKETBALL OVERNIGHT STATUS")
    print("="*70)
    
    # Check scrapers
    print("\n🔵 ACTIVE SCRAPERS:")
    for season in [2024, 2025, 2026]:
        kenpom_active, kp_size = check_log_active(f"scrape_{season}.log")
        sportsref_active, sr_size = check_log_active(f"scrape_sportsref_{season}.log")
        
        kp_status = f"🟢 {kp_size:,} bytes" if kenpom_active else "🔴 Stopped"
        sr_status = f"🟢 {sr_size:,} bytes" if sportsref_active else "🔴 Stopped"
        
        print(f"  Season {season}:")
        print(f"    KenPom:      {kp_status}")
        print(f"    Sports Ref:  {sr_status}")
    
    # Check main system
    main_active, main_size = check_log_active("complete_system.log")
    print(f"\n🤖 MAIN SYSTEM: {'🟢 RUNNING' if main_active else '🔴 Not started'}")
    if main_active:
        print(f"   Log size: {main_size:,} bytes")
    
    # Check data
    print("\n📊 CURRENT DATA STATUS:")
    conn = sqlite3.connect(DB_PATH)
    
    for season in [2024, 2025, 2026]:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT 
                COUNT(DISTINCT player_id) as total,
                COUNT(DISTINCT CASE WHEN offensive_rating IS NOT NULL THEN player_id END) as ortg,
                COUNT(DISTINCT CASE WHEN points_per_game IS NOT NULL THEN player_id END) as ppg
            FROM player_stats WHERE season = {season}
        """)
        row = cursor.fetchone()
        
        targets = {2024: 3500, 2025: 4000, 2026: 3200}
        target = targets[season]
        
        ortg_pct = row[1] / target * 100
        ppg_pct = row[2] / target * 100
        
        status = "✅" if (ortg_pct > 90 and ppg_pct > 75) else "⏳"
        
        print(f"  {status} Season {season}: {row[1]:,} ORtg ({ortg_pct:.0f}%), {row[2]:,} PPG ({ppg_pct:.0f}%)")
    
    conn.close()
    
    # Check model
    model_path = Path(__file__).parent / 'models' / 'multitask_model_best.pth'
    if model_path.exists():
        mod_time = model_path.stat().st_mtime
        import datetime
        mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🧠 MODEL: ✅ Exists (last updated: {mod_time_str})")
    else:
        print(f"\n🧠 MODEL: ⏳ Not trained yet")
    
    print("\n" + "="*70)
    print("To view logs in real-time:")
    print("  tail -f complete_system.log")
    print("  tail -f scrape_2024.log")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()

