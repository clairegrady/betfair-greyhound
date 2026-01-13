#!/usr/bin/env python3
"""
Scrape NCAA.com for comprehensive player stats (PPG, RPG, APG, SPG, BPG, FG%)
Much faster and more reliable than Sports Reference!
"""

import sqlite3
import requests
import pandas as pd
import time
import logging
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"

# NCAA.com stat IDs for different stats
STAT_IDS = {
    'ppg': 136,    # Points Per Game
    'rpg': 137,    # Rebounds Per Game
    'apg': 140,    # Assists Per Game
    'spg': 139,    # Steals Per Game
    'bpg': 138,    # Blocks Per Game
    'fgpct': 149,  # Field Goal %
}

def scrape_stat(stat_name, stat_id, season):
    """Scrape a specific stat from NCAA.com"""
    base_url = f"https://www.ncaa.com/stats/basketball-men/d1/{season}/individual/{stat_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    all_players = []
    page = 1
    
    while page <= 100:  # Safety limit
        if page == 1:
            url = base_url
        else:
            url = f"{base_url}/p{page}"
        
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=10)
            if response.status_code != 200:
                break
                
            tables = pd.read_html(response.text)
            if not tables or len(tables[0]) == 0:
                break
                
            df = tables[0]
            all_players.append(df)
            logger.info(f"  Page {page}: {len(df)} players")
            page += 1
            time.sleep(0.5)  # Be nice to their servers
            
        except Exception as e:
            logger.error(f"  Page {page} error: {e}")
            break
    
    if all_players:
        combined = pd.concat(all_players, ignore_index=True)
        logger.info(f"✅ {stat_name}: {len(combined)} total players")
        return combined
    return None


def update_database(ppg_df, rpg_df, apg_df, spg_df, bpg_df, fgpct_df, season):
    """Update player_stats table with NCAA.com data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats_dfs = {
        'ppg': ppg_df,
        'rpg': rpg_df,
        'apg': apg_df,
        'spg': spg_df,
        'bpg': bpg_df,
        'fgpct': fgpct_df,
    }
    
    # Build a player -> stats mapping
    player_stats = {}
    
    for stat_name, df in stats_dfs.items():
        if df is None:
            continue
            
        # Find the stat column
        stat_col = None
        for col in df.columns:
            col_upper = str(col).upper()
            if stat_name.upper() in col_upper or \
               ('PPG' in col_upper and stat_name == 'ppg') or \
               ('RPG' in col_upper and stat_name == 'rpg') or \
               ('APG' in col_upper and stat_name == 'apg') or \
               ('STPG' in col_upper and stat_name == 'spg') or \
               ('BKPG' in col_upper and stat_name == 'bpg') or \
               ('FG%' in col_upper and stat_name == 'fgpct'):
                stat_col = col
                break
        
        if stat_col is None:
            logger.warning(f"Could not find stat column for {stat_name} in {list(df.columns)}")
            continue
        
        for _, row in df.iterrows():
            player_name = row['Name']
            team_name = row['Team']
            stat_value = row[stat_col]
            
            key = (player_name, team_name)
            if key not in player_stats:
                player_stats[key] = {}
            player_stats[key][stat_name] = stat_value
    
    # Update database
    updated = 0
    for (player_name, team_name), stats in player_stats.items():
        try:
            # Build UPDATE query dynamically based on available stats
            set_clauses = []
            values = []
            
            if 'ppg' in stats:
                set_clauses.append("points_per_game = ?")
                values.append(stats['ppg'])
            if 'rpg' in stats:
                set_clauses.append("rebounds_per_game = ?")
                values.append(stats['rpg'])
            if 'apg' in stats:
                set_clauses.append("assists_per_game = ?")
                values.append(stats['apg'])
            if 'spg' in stats:
                set_clauses.append("steals_per_game = ?")
                values.append(stats['spg'])
            if 'bpg' in stats:
                set_clauses.append("blocks_per_game = ?")
                values.append(stats['bpg'])
            if 'fgpct' in stats:
                set_clauses.append("fg_pct = ?")
                values.append(stats['fgpct'])
            
            if not set_clauses:
                continue
            
            # Add WHERE clause values
            values.extend([player_name, season])
            
            query = f"""
                UPDATE player_stats
                SET {', '.join(set_clauses)}
                WHERE player_name = ? AND season = ?
            """
            
            cursor.execute(query, values)
            if cursor.rowcount > 0:
                updated += 1
        except Exception as e:
            logger.error(f"Error updating {player_name}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Updated {updated} players in database")
    return updated


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_ncaa_stats.py <season>")
        print("Example: python scrape_ncaa_stats.py 2025")
        sys.exit(1)
    
    season = int(sys.argv[1])
    
    print("\n" + "="*70)
    print(f"📊 NCAA.COM SCRAPER - SEASON {season} ({season-1}-{str(season)[2:]})")
    print("="*70 + "\n")
    
    # Scrape all stats
    logger.info("Scraping Points Per Game...")
    ppg_df = scrape_stat("PPG", STAT_IDS['ppg'], season)
    
    logger.info("\nScraping Rebounds Per Game...")
    rpg_df = scrape_stat("RPG", STAT_IDS['rpg'], season)
    
    logger.info("\nScraping Assists Per Game...")
    apg_df = scrape_stat("APG", STAT_IDS['apg'], season)
    
    logger.info("\nScraping Steals Per Game...")
    spg_df = scrape_stat("SPG", STAT_IDS['spg'], season)
    
    logger.info("\nScraping Blocks Per Game...")
    bpg_df = scrape_stat("BPG", STAT_IDS['bpg'], season)
    
    logger.info("\nScraping Field Goal %...")
    fgpct_df = scrape_stat("FG%", STAT_IDS['fgpct'], season)
    
    # Update database
    logger.info("\nUpdating database...")
    updated = update_database(ppg_df, rpg_df, apg_df, spg_df, bpg_df, fgpct_df, season)
    
    print("\n" + "="*70)
    print(f"✅ NCAA.COM SCRAPER COMPLETE - Updated {updated} players")
    print("="*70)


if __name__ == "__main__":
    main()

