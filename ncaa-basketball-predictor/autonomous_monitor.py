"""
Autonomous monitoring script - monitors both scrapers and auto-restarts on failure
Runs continuously and handles errors without human intervention
"""

import sqlite3
import time
import subprocess
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"
LOG_PATH = Path(__file__).parent / "autonomous_monitor.log"


def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {message}"
    print(msg)
    with open(LOG_PATH, 'a') as f:
        f.write(msg + "\n")


def check_process(process_name):
    """Check if a process is running"""
    try:
        result = subprocess.run(['pgrep', '-f', process_name], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def start_lineup_scraper():
    """Start ESPN lineup scraper"""
    log("🚀 Starting ESPN lineup scraper...")
    subprocess.Popen(
        ['nohup', 'python3', 'pipelines/scrape_espn_lineups.py'],
        stdout=open('lineup_scrape.log', 'w'),
        stderr=subprocess.STDOUT,
        cwd='/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor'
    )
    time.sleep(3)
    log("   ESPN lineup scraper started")


def start_sportsref_scraper():
    """Start Sports Reference scraper"""
    log("🚀 Starting Sports Reference scraper...")
    subprocess.Popen(
        ['nohup', 'python3', 'pipelines/scrape_sportsref_season.py', '2025'],
        stdout=open('sportsref_2025.log', 'w'),
        stderr=subprocess.STDOUT,
        cwd='/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor'
    )
    time.sleep(3)
    log("   Sports Reference scraper started")


def check_progress():
    """Check scraping progress and return status"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Lineup scraper progress
        cursor.execute("SELECT COUNT(*) FROM games WHERE season IN (2024, 2025, 2026)")
        total_games = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT game_id) FROM game_lineups")
        games_with_lineups = cursor.fetchone()[0]
        
        lineup_pct = (games_with_lineups / total_games * 100) if total_games > 0 else 0
        
        # Sports Reference progress
        cursor.execute("SELECT COUNT(*) FROM player_stats WHERE season = 2025")
        total_players = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM player_stats WHERE season = 2025 AND points_per_game IS NOT NULL")
        with_stats = cursor.fetchone()[0]
        
        sportsref_pct = (with_stats / total_players * 100) if total_players > 0 else 0
        
        conn.close()
        
        return {
            'lineup_pct': lineup_pct,
            'lineup_count': games_with_lineups,
            'lineup_total': total_games,
            'sportsref_pct': sportsref_pct,
            'sportsref_count': with_stats,
            'sportsref_total': total_players
        }
        
    except Exception as e:
        log(f"❌ Error checking progress: {e}")
        return None


def monitor_and_recover():
    """Main monitoring loop with auto-recovery"""
    
    log("\n" + "="*70)
    log("🤖 AUTONOMOUS MONITORING STARTED")
    log("   Will monitor scrapers and auto-restart on failure")
    log("="*70 + "\n")
    
    check_interval = 120  # Check every 2 minutes
    last_lineup_count = 0
    last_sportsref_count = 0
    stalled_checks = {'lineup': 0, 'sportsref': 0}
    
    while True:
        try:
            # Check if processes are running
            lineup_running = check_process('scrape_espn_lineups.py')
            sportsref_running = check_process('scrape_sportsref_season.py')
            
            # Get progress
            progress = check_progress()
            
            if progress:
                lineup_pct = progress['lineup_pct']
                sportsref_pct = progress['sportsref_pct']
                lineup_count = progress['lineup_count']
                sportsref_count = progress['sportsref_count']
                
                # Log status
                log(f"📊 Status: Lineup {lineup_pct:.1f}% ({lineup_count:,}/{progress['lineup_total']:,}) | "
                    f"SportsRef {sportsref_pct:.1f}% ({sportsref_count:,}/{progress['sportsref_total']:,})")
                
                # Check if lineup scraper finished
                if lineup_pct >= 99.5:
                    log("✅ ESPN lineup scraper COMPLETE!")
                    lineup_running = False  # Don't restart
                
                # Check if sportsref scraper finished
                if sportsref_pct >= 99.5:
                    log("✅ Sports Reference scraper COMPLETE!")
                    sportsref_running = False  # Don't restart
                
                # Check for stalled progress (no new data in 3 checks = 6 minutes)
                if lineup_count == last_lineup_count and lineup_pct < 99:
                    stalled_checks['lineup'] += 1
                else:
                    stalled_checks['lineup'] = 0
                    last_lineup_count = lineup_count
                
                if sportsref_count == last_sportsref_count and sportsref_pct < 99:
                    stalled_checks['sportsref'] += 1
                else:
                    stalled_checks['sportsref'] = 0
                    last_sportsref_count = sportsref_count
                
                # Restart if stalled for 6+ minutes
                if stalled_checks['lineup'] >= 3 and lineup_pct < 99:
                    log("⚠️  Lineup scraper appears stalled - restarting...")
                    start_lineup_scraper()
                    stalled_checks['lineup'] = 0
                
                if stalled_checks['sportsref'] >= 3 and sportsref_pct < 99:
                    log("⚠️  SportsRef scraper appears stalled - restarting...")
                    start_sportsref_scraper()
                    stalled_checks['sportsref'] = 0
                
                # Check if both complete
                if lineup_pct >= 99.5 and sportsref_pct >= 99.5:
                    log("\n" + "="*70)
                    log("🎉 ALL SCRAPING COMPLETE!")
                    log(f"   Lineup data: {lineup_pct:.1f}%")
                    log(f"   Player stats: {sportsref_pct:.1f}%")
                    log("   Ready for model training!")
                    log("="*70 + "\n")
                    break
            
            # Restart crashed scrapers (if not complete)
            if not lineup_running and progress and progress['lineup_pct'] < 99:
                log("❌ Lineup scraper not running - restarting...")
                start_lineup_scraper()
            
            if not sportsref_running and progress and progress['sportsref_pct'] < 99:
                log("❌ SportsRef scraper not running - restarting...")
                start_sportsref_scraper()
            
            # Wait before next check
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            log("\n⏸️  Monitoring stopped by user")
            break
        except Exception as e:
            log(f"❌ Monitoring error: {e}")
            log("   Retrying in 30 seconds...")
            time.sleep(30)


if __name__ == "__main__":
    monitor_and_recover()

