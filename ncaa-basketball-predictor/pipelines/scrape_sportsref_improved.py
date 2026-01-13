"""
IMPROVED Sports Reference Scraper
- Better name matching (handles "Jr.", "III", etc.)
- INSERTS missing players (doesn't just update)
- Focuses on Season 2025 (2024-25) to get >90% coverage
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from pathlib import Path
from io import StringIO
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def normalize_player_name(name):
    """Normalize player name for better matching"""
    if not name:
        return ""
    
    name = str(name).strip()
    
    # Remove suffixes
    name = re.sub(r'\s+(Jr\.|Sr\.|III|IV|II)\.?$', '', name, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    # Lowercase for comparison
    return name.lower()


def clean_team_slug(team_name):
    """Convert team name to Sports Reference URL format"""
    # Manual mappings
    manual_map = {
        'UConn': 'connecticut',
        'UMass': 'massachusetts',
        'UMBC': 'umbc',
        'VCU': 'vcu',
        'TCU': 'texas-christian',
        'SMU': 'southern-methodist',
        'BYU': 'brigham-young',
        'UCF': 'central-florida',
        'UNLV': 'nevada-las-vegas',
        'USC': 'southern-california',
        'UCLA': 'ucla',
        'LSU': 'louisiana-state',
        'Ole Miss': 'mississippi',
        'Miami (FL)': 'miami-fl',
        'Miami (OH)': 'miami-oh',
        'UNC': 'north-carolina',
        'NC State': 'north-carolina-state',
        'Pitt': 'pittsburgh',
        'Penn': 'pennsylvania',
        "St. John's": 'st-johns-ny',
    }
    
    for key, value in manual_map.items():
        if key in team_name:
            return value
    
    # General cleanup
    slug = team_name.lower()
    slug = re.sub(r'\s+(university|college|state|tech|a&m)(\s+|$)', ' ', slug)
    slug = slug.strip()
    slug = slug.replace(' ', '-')
    slug = slug.replace("'", "")
    
    return slug


def scrape_team_season(team_name, season, conn):
    """
    Scrape Sports Reference for a team and season
    INSERTS or UPDATES players
    """
    
    team_slug = clean_team_slug(team_name)
    url = f"https://www.sports-reference.com/cbb/schools/{team_slug}/{season}.html"
    
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return 0, 0
        
        # Parse tables
        tables = pd.read_html(StringIO(response.text))
        
        # Find per-game stats table
        per_game_stats = None
        for table in tables:
            if 'Player' in str(table.columns) and 'PTS' in str(table.columns):
                per_game_stats = table
                break
        
        if per_game_stats is None:
            return 0, 0
        
        cursor = conn.cursor()
        inserted = 0
        updated = 0
        
        for _, row in per_game_stats.iterrows():
            player_name = row.get('Player')
            
            if pd.isna(player_name) or player_name == 'Player':
                continue
            
            player_name = str(player_name).strip()
            normalized_name = normalize_player_name(player_name)
            
            # Extract stats
            ppg = row.get('PTS')
            rpg = row.get('TRB')
            apg = row.get('AST')
            bpg = row.get('BLK')
            spg = row.get('STL')
            fg_pct = row.get('FG%')
            
            # Try to find existing player with similar name
            cursor.execute("""
                SELECT player_id, player_name 
                FROM player_stats 
                WHERE season = ?
            """, (season,))
            
            existing_players = cursor.fetchall()
            matched_player_id = None
            
            for pid, pname in existing_players:
                if normalize_player_name(pname) == normalized_name:
                    matched_player_id = pid
                    break
            
            if matched_player_id:
                # UPDATE existing player
                cursor.execute("""
                    UPDATE player_stats
                    SET points_per_game = ?,
                        rebounds_per_game = ?,
                        assists_per_game = ?,
                        blocks_per_game = ?,
                        steals_per_game = ?,
                        fg_pct = ?
                    WHERE player_id = ? AND season = ?
                """, (ppg, rpg, apg, bpg, spg, fg_pct, matched_player_id, season))
                
                if cursor.rowcount > 0:
                    updated += 1
            else:
                # INSERT new player (get new player_id)
                cursor.execute("SELECT MAX(player_id) FROM players")
                max_id = cursor.fetchone()[0] or 0
                new_player_id = max_id + 1
                
                # Insert into players table
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_id, player_name, season)
                    VALUES (?, ?, ?)
                """, (new_player_id, player_name, season))
                
                # Insert into player_stats
                cursor.execute("""
                    INSERT OR IGNORE INTO player_stats 
                    (player_id, player_name, season, points_per_game, rebounds_per_game, 
                     assists_per_game, blocks_per_game, steals_per_game, fg_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (new_player_id, player_name, season, ppg, rpg, apg, bpg, spg, fg_pct))
                
                if cursor.rowcount > 0:
                    inserted += 1
        
        conn.commit()
        return inserted, updated
        
    except Exception as e:
        logger.error(f"Error scraping {team_name}: {e}")
        return 0, 0


def main():
    print("\n" + "="*70)
    print("🏀 IMPROVED SPORTS REFERENCE SCRAPER")
    print("   - Better name matching")
    print("   - Inserts missing players")
    print("   - Target: >90% coverage")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all teams
    cursor.execute("""
        SELECT DISTINCT team_name 
        FROM teams 
        ORDER BY team_name
    """)
    
    teams = [row[0] for row in cursor.fetchall()]
    
    logger.info(f"Scraping {len(teams)} teams for season 2025 (2024-25)\n")
    
    total_inserted = 0
    total_updated = 0
    season = 2025
    
    for i, team in enumerate(teams, 1):
        if i % 20 == 0:
            logger.info(f"\n📊 Progress: {i}/{len(teams)} | Inserted: {total_inserted} | Updated: {total_updated}\n")
        
        try:
            inserted, updated = scrape_team_season(team, season, conn)
            total_inserted += inserted
            total_updated += updated
            
            if inserted > 0 or updated > 0:
                logger.info(f"  ✅ {team}: +{inserted} new, ~{updated} updated")
            
            time.sleep(6)  # Be nice to Sports Reference
            
        except Exception as e:
            logger.error(f"❌ {team}: {e}")
            time.sleep(10)
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ SCRAPING COMPLETE!")
    print(f"   Teams: {len(teams)}")
    print(f"   New players: {total_inserted}")
    print(f"   Updated players: {total_updated}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

