"""
Sports Reference Scraper for Per-Game Stats
Source: https://www.sports-reference.com/cbb/
Gets: points, rebounds, assists, blocks, steals per game
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def clean_team_name_for_sports_ref(team_name):
    """
    Convert team name to Sports Reference URL format with robust matching
    """
    import re
    
    # Manual mappings for known problematic teams
    manual_map = {
        'UConn Huskies': 'connecticut',
        'UMass Minutemen': 'massachusetts',
        'UMBC Retrievers': 'umbc',
        'VCU Rams': 'vcu',
        'TCU Horned Frogs': 'texas-christian',
        'SMU Mustangs': 'southern-methodist',
        'BYU Cougars': 'brigham-young',
        'UCF Knights': 'central-florida',
        'UNLV Rebels': 'nevada-las-vegas',
        'USC Trojans': 'southern-california',
        'UCLA Bruins': 'ucla',
        'LSU Tigers': 'louisiana-state',
        'Ole Miss Rebels': 'mississippi',
        'Miami Hurricanes': 'miami-fl',
        'Miami (FL) Hurricanes': 'miami-fl',
        'Miami RedHawks': 'miami-oh',
        'Miami (OH) RedHawks': 'miami-oh',
        'UNC Tar Heels': 'north-carolina',
        'NC State Wolfpack': 'north-carolina-state',
        'Pitt Panthers': 'pittsburgh',
        'Penn Quakers': 'pennsylvania',
        "St. John's Red Storm": 'st-johns-ny',
        "St. John's": 'st-johns-ny',
        'Central Connecticut Blue Devils': 'central-connecticut-state',
        'Central Connecticut State Blue Devils': 'central-connecticut-state',
        'LIU Brooklyn Blackbirds': 'long-island-university',
        'LIU Sharks': 'long-island-university',
    }
    
    # Check manual map first
    if team_name in manual_map:
        return [manual_map[team_name]]
    
    # Generate multiple candidate URLs to try
    candidates = []
    
    # Strategy 1: Remove last word (mascot) and slugify
    words = team_name.split()
    if len(words) > 1:
        # Remove last word if it's capitalized (likely mascot)
        if words[-1][0].isupper():
            base_name = ' '.join(words[:-1])
            
            # Handle abbreviations
            base_name = re.sub(r'\bSt\.?\b', 'State', base_name, flags=re.IGNORECASE)
            base_name = re.sub(r'\bMt\.?\b', 'Mount', base_name, flags=re.IGNORECASE)
            
            # Clean special chars
            slug = base_name.lower()
            slug = slug.replace('&', 'and')
            slug = slug.replace('.', '')
            slug = slug.replace("'", '')
            slug = slug.replace('(', '').replace(')', '')
            slug = slug.replace(' ', '-')
            
            candidates.append(slug)
    
    # Strategy 2: Remove last TWO words (for multi-word mascots like "Blue Devils")
    if len(words) > 2:
        base_name2 = ' '.join(words[:-2])
        base_name2 = re.sub(r'\bSt\.?\b', 'State', base_name2, flags=re.IGNORECASE)
        slug2 = base_name2.lower().replace(' ', '-').replace('.', '').replace("'", "").replace('&', 'and')
        if slug2 not in candidates:
            candidates.append(slug2)
    
    # Strategy 3: Try just first word for compound names
    if len(words) > 1:
        first_word = words[0].lower().replace('.', '')
        if len(first_word) > 3 and first_word not in candidates:
            candidates.append(first_word)
    
    return candidates if candidates else [team_name.lower().replace(' ', '-')]


def scrape_team_stats_from_sports_reference(team_name: str, season: int, conn):
    """
    Scrape player stats from Sports Reference
    URL format: https://www.sports-reference.com/cbb/schools/{team}/{season}.html
    """
    
    # Get candidate team slugs (in order of likelihood)
    team_slugs = clean_team_name_for_sports_ref(team_name)
    
    # Try each candidate
    for team_slug in team_slugs:
        url = f"https://www.sports-reference.com/cbb/schools/{team_slug}/{season}.html"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                continue  # Try next candidate
            
            # Parse with pandas
            tables = pd.read_html(response.text)
            
            # Per-game stats table is usually the first or second table
            per_game_stats = None
            for table in tables:
                if 'Player' in str(table.columns) and 'PTS' in str(table.columns):
                    per_game_stats = table
                    break
            
            if per_game_stats is None:
                continue  # Try next candidate
            
            # SUCCESS - we found the right team page!
            cursor = conn.cursor()
            updated = 0
            
            for _, row in per_game_stats.iterrows():
                player_name = row.get('Player')
                
                if pd.isna(player_name) or player_name == 'Player':
                    continue
                
                # Extract stats
                ppg = row.get('PTS')
                rpg = row.get('TRB')  # Total rebounds
                apg = row.get('AST')
                bpg = row.get('BLK')
                spg = row.get('STL')
                fg_pct = row.get('FG%')
                
                # Update database
                cursor.execute("""
                    UPDATE player_stats
                    SET points_per_game = ?,
                        rebounds_per_game = ?,
                        assists_per_game = ?,
                        blocks_per_game = ?,
                        steals_per_game = ?,
                        fg_pct = ?
                    WHERE (player_name LIKE ? OR player_name LIKE ?)
                      AND season = ?
                """, (
                    ppg, rpg, apg, bpg, spg, fg_pct,
                    f"%{player_name}%",
                    f"{player_name}%",
                    season
                ))
                
                if cursor.rowcount > 0:
                    updated += 1
            
            if updated > 0:
                logger.info(f"  ✅ {team_name} ({team_slug}): {updated} players updated")
            
            conn.commit()
            return updated
            
        except Exception as e:
            logger.error(f"❌ Error trying {team_slug}: {e}")
            continue
    
    # If we get here, all candidates failed
    logger.warning(f"⚠️ {team_name}: No matching Sports Reference page found (tried {team_slugs})")
    return 0


def main():
    print("\n" + "="*70)
    print("🏀 SPORTS REFERENCE PER-GAME STATS SCRAPER - ALL TEAMS - ROBUST v2")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all unique team names from players table (teams that have players with KenPom data)
    cursor.execute("""
        SELECT DISTINCT t.team_name, t.kenpom_name
        FROM teams t
        WHERE EXISTS (
            SELECT 1 FROM players p 
            JOIN player_stats ps ON p.player_id = ps.player_id
            WHERE p.team_id = t.team_id AND ps.season = 2026
        )
        ORDER BY t.team_name
    """)
    teams = cursor.fetchall()
    
    logger.info(f"Scraping Sports Reference for {len(teams)} teams...")
    
    total_updated = 0
    season = 2025  # 2024-25 SEASON (most recent complete data on Sports Reference)
    
    for i, (team_name, kenpom_name) in enumerate(teams, 1):
        # Use kenpom_name if available, otherwise use team_name
        scrape_name = kenpom_name if kenpom_name else team_name
        
        if i % 20 == 0:
            logger.info(f"\n📊 Progress: {i}/{len(teams)} teams | {total_updated} players updated")
        
        try:
            logger.info(f"\nScraping {scrape_name}...")
            updated = scrape_team_stats_from_sports_reference(scrape_name, season, conn)
            total_updated += updated
            time.sleep(6)  # Be respectful to Sports Reference
        except Exception as e:
            logger.error(f"❌ Failed {scrape_name}: {e}")
            time.sleep(10)
    
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ SPORTS REFERENCE SCRAPING COMPLETE!")
    print(f"   Total teams: {len(teams)}")
    print(f"   Total players updated: {total_updated}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

