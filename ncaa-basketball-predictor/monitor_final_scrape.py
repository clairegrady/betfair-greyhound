#!/usr/bin/env python3
"""Monitor the final push to 100% Sports Reference coverage"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def get_coverage():
    """Get current SportsRef coverage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    for season in [2025, 2026]:
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) as with_sportsref
            FROM player_stats
            WHERE season = ?
        """, (season,))
        
        total, with_sportsref = cursor.fetchone()
        pct = (with_sportsref / total * 100) if total > 0 else 0
        stats[season] = {
            'total': total,
            'with_sportsref': with_sportsref,
            'pct': pct
        }
    
    conn.close()
    return stats

print("\n" + "="*70)
print("📊 MONITORING SPORTS REFERENCE SCRAPING PROGRESS")
print("="*70 + "\n")
print("Target: 100% coverage for seasons 2024-25 and 2025-26")
print("Scrapers: 10 parallel instances (5 per season)")
print("\nPress Ctrl+C to stop monitoring\n")
print("="*70 + "\n")

prev_stats = {}
iteration = 0

try:
    while True:
        stats = get_coverage()
        iteration += 1
        
        print(f"\n[{time.strftime('%H:%M:%S')}] Iteration {iteration}")
        print("-" * 70)
        
        all_complete = True
        for season in [2025, 2026]:
            s = stats[season]
            season_label = f"{season-1}-{str(season)[2:]}"
            
            # Calculate rate if we have previous data
            rate = ""
            if season in prev_stats:
                gain = s['with_sportsref'] - prev_stats[season]['with_sportsref']
                if gain > 0:
                    remaining = s['total'] - s['with_sportsref']
                    eta_minutes = (remaining / gain) * 0.5  # Check every 30 seconds
                    rate = f" (+{gain}/30s, ETA: {eta_minutes:.1f}m)"
            
            status = "✅" if s['pct'] >= 99.9 else "🔄"
            print(f"{status} Season {season_label}: {s['with_sportsref']}/{s['total']} ({s['pct']:.1f}%){rate}")
            
            if s['pct'] < 99.9:
                all_complete = False
        
        if all_complete:
            print("\n" + "="*70)
            print("🎉 SUCCESS! 100% COVERAGE ACHIEVED!")
            print("="*70)
            break
        
        prev_stats = stats
        time.sleep(30)  # Check every 30 seconds

except KeyboardInterrupt:
    print("\n\n⚠️  Monitoring stopped by user")
    print("Scrapers are still running in background")
    print("Run this script again to resume monitoring")
