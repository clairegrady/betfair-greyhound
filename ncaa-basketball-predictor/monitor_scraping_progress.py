#!/usr/bin/env python3
"""
Monitor Sports Reference scraping progress until 100% coverage
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def check_coverage():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            season,
            COUNT(*) as total,
            COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) as have_ppg,
            ROUND(100.0 * COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
        FROM player_stats
        WHERE season IN (2025, 2026)
        GROUP BY season
        ORDER BY season
    """)
    
    results = cursor.fetchall()
    conn.close()
    return results

print("\n" + "="*70)
print("📊 MONITORING BOX SCORE COVERAGE - Target: 100%")
print("="*70 + "\n")
print("Checking every 30 seconds until 100% coverage achieved...")
print("Press Ctrl+C to stop monitoring\n")

try:
    iteration = 0
    while True:
        iteration += 1
        results = check_coverage()
        
        print(f"\n[Update #{iteration}] {time.strftime('%H:%M:%S')}")
        print("-" * 70)
        
        all_complete = True
        for row in results:
            season_label = f"{row[0]-1}-{str(row[0])[2:]}"
            pct = row[3]
            missing = row[1] - row[2]
            status = "✅" if pct == 100.0 else "⏳"
            
            print(f"{status} Season {season_label}: {row[2]:,}/{row[1]:,} ({pct:5.1f}%) - Missing: {missing:,}")
            
            if pct < 100.0:
                all_complete = False
        
        if all_complete:
            print("\n" + "="*70)
            print("🎉 100% COVERAGE ACHIEVED!")
            print("="*70)
            break
        
        time.sleep(30)
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user.")

