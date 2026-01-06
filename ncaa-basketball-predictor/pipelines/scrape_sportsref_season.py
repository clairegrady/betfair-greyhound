"""
Scrape Sports Reference for SPECIFIC SEASON
Usage: python scrape_sportsref_season.py 2025
"""

import sqlite3
import requests
from io import StringIO
import pandas as pd
import time
import logging
from pathlib import Path
import sys
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


# COMPLETE manual mappings from our previous work
TEAM_MAPPINGS = {
    'UConn Huskies': 'connecticut',
    'UMass Minutemen': 'massachusetts',
    'UMBC Retrievers': 'maryland-baltimore-county',
    'VCU Rams': 'virginia-commonwealth',
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
    'Miami RedHawks': 'miami-oh',
    'UNC Tar Heels': 'north-carolina',
    'NC State Wolfpack': 'north-carolina-state',
    'Pitt Panthers': 'pittsburgh',
    'Penn Quakers': 'pennsylvania',
    "St. John's Red Storm": 'st-johns-ny',
    'Central Connecticut Blue Devils': 'central-connecticut-state',
    'LIU Sharks': 'long-island-university',
    'Southern Miss Golden Eagles': 'southern-mississippi',
    'Mississippi State Bulldogs': 'mississippi-state',
    'Michigan State Spartans': 'michigan-state',
    'Loyola Chicago Ramblers': 'loyola-il',
    'Charleston Cougars': 'charleston-southern',
    'Penn State Nittany Lions': 'penn-state',
    'SIUE': 'southern-illinois-edwardsville',
    'Cal Baptist Lancers': 'california-baptist',
    'The Citadel Bulldogs': 'citadel',
    "Saint Mary's Gaels": 'saint-marys-ca',
    'UC Davis Aggies': 'california-davis',
    'UT Rio Grande Valley Vaqueros': 'texas-pan-american',
    'Montana State Bobcats': 'montana-state',
    'Jacksonville State Gamecocks': 'jacksonville-state',
    'Saint Francis Red Flash': 'saint-francis-pa',
    'UC Santa Barbara Gauchos': 'california-santa-barbara',
    'Nicholls Colonels': 'nicholls-state',
    'UMass Lowell River Hawks': 'massachusetts-lowell',
    'Houston Christian Huskies': 'houston-baptist',
    "Louisiana Ragin' Cajuns": 'louisiana-lafayette',
    'Oregon State Beavers': 'oregon-state',
    'New Mexico State Aggies': 'new-mexico-state',
    'Kansas City Roos': 'missouri-kansas-city',
    'UC San Diego Tritons': 'california-san-diego',
    'UC Riverside Highlanders': 'california-riverside',
    'UAB Blazers': 'alabama-birmingham',
    'Queens University Royals': 'queens-nc',
    'Purdue Fort Wayne Mastodons': 'ipfw',
    'VMI Keydets': 'virginia-military-institute',
    'UTSA Roadrunners': 'texas-san-antonio',
    'UNC Greensboro Spartans': 'north-carolina-greensboro',
    'UNC Asheville Bulldogs': 'north-carolina-asheville',
    'McNeese Cowboys': 'mcneese-state',
    'UAlbany Great Danes': 'albany-ny',
    'UC Irvine Anteaters': 'california-irvine',
    'UT Arlington Mavericks': 'texas-arlington',
    'Bowling Green Falcons': 'bowling-green-state',
    'Iowa State Cyclones': 'iowa-state',
    'CSUN': 'cal-state-northridge',
    'Utah Tech Trailblazers': 'dixie-state',
    'St. Bonaventure Bonnies': 'st-bonaventure',
    'Colorado Buffaloes': 'colorado',
    'UNC Wilmington Seahawks': 'north-carolina-wilmington',
}


def clean_team_name_for_sports_ref(team_name):
    """Get Sports Reference URL slug"""
    if team_name in TEAM_MAPPINGS:
        return [TEAM_MAPPINGS[team_name]]
    
    # Fallback logic
    candidates = []
    words = team_name.split()
    
    if len(words) > 1 and words[-1][0].isupper():
        base_name = ' '.join(words[:-1])
        base_name = re.sub(r'\bSt\.?\b', 'State', base_name, flags=re.IGNORECASE)
        slug = base_name.lower().replace('&', 'and').replace('.', '').replace("'", '').replace(' ', '-')
        candidates.append(slug)
    
    return candidates if candidates else [team_name.lower().replace(' ', '-')]


def scrape_team(team_name, season, conn):
    """Scrape a single team"""
    team_slugs = clean_team_name_for_sports_ref(team_name)
    
    for team_slug in team_slugs:
        url = f"https://www.sports-reference.com/cbb/schools/{team_slug}/{season}.html"
        
        try:
            response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                continue
            
            tables = pd.read_html(StringIO(response.text))
            
            per_game_stats = None
            for table in tables:
                if 'Player' in str(table.columns) and 'PTS' in str(table.columns):
                    per_game_stats = table
                    break
            
            if per_game_stats is None:
                continue
            
            cursor = conn.cursor()
            updated = 0
            
            for _, row in per_game_stats.iterrows():
                player_name = row.get('Player')
                if pd.isna(player_name) or player_name == 'Player':
                    continue
                
                ppg = row.get('PTS')
                rpg = row.get('TRB')
                apg = row.get('AST')
                bpg = row.get('BLK')
                spg = row.get('STL')
                fg_pct = row.get('FG%')
                
                cursor.execute("""
                    UPDATE player_stats
                    SET points_per_game = ?, rebounds_per_game = ?, assists_per_game = ?,
                        blocks_per_game = ?, steals_per_game = ?, fg_pct = ?
                    WHERE (player_name LIKE ? OR player_name LIKE ?) AND season = ?
                """, (ppg, rpg, apg, bpg, spg, fg_pct, f"%{player_name}%", f"{player_name}%", season))
                
                if cursor.rowcount > 0:
                    updated += 1
            
            conn.commit()
            if updated > 0:
                logger.info(f"  ✅ {team_name} ({team_slug}): {updated} players")
            return updated
            
        except Exception as e:
            continue
    
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_sportsref_season.py <season>")
        print("Example: python scrape_sportsref_season.py 2025")
        sys.exit(1)
    
    season = int(sys.argv[1])
    
    print("\n" + "="*70)
    print(f"📊 SPORTS REFERENCE - SEASON {season} ({season-1}-{str(season)[2:]})")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get teams that have KenPom data for this season
    cursor.execute("""
        SELECT DISTINCT t.team_name, t.kenpom_name
        FROM teams t
        WHERE EXISTS (
            SELECT 1 FROM players p 
            JOIN player_stats ps ON p.player_id = ps.player_id
            WHERE p.team_id = t.team_id AND ps.season = ?
        )
        ORDER BY t.team_name
    """, (season,))
    
    teams = cursor.fetchall()
    logger.info(f"Scraping {len(teams)} teams for season {season}...\n")
    
    total_updated = 0
    successes = 0
    
    for i, (team_name, kenpom_name) in enumerate(teams, 1):
        scrape_name = kenpom_name if kenpom_name else team_name
        
        if i % 20 == 0:
            logger.info(f"Progress: {i}/{len(teams)} teams | {total_updated} players")
        
        updated = scrape_team(scrape_name, season, conn)
        total_updated += updated
        
        if updated > 0:
            successes += 1
        
        time.sleep(5)
    
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ SPORTS REFERENCE COMPLETE - SEASON {season}")
    print(f"  Teams: {successes}/{len(teams)}")
    print(f"  Players: {total_updated}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

