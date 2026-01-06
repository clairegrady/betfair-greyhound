"""
Scrape game lineups (starters + minutes) from Sports Reference box scores
For all games in 2025 & 2026 seasons
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from pathlib import Path
import re
from io import StringIO

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def get_box_score_url_from_game_id(game_id):
    """
    Convert ESPN game_id to Sports Reference box score URL
    ESPN format: 401638580
    Sports Ref format: YYYY-MM-DD-19-team-slug
    """
    # For now, we'll need to construct from game data
    return None


def scrape_box_score_by_teams_and_date(home_team, away_team, date, game_id, conn):
    """
    Scrape box score from Sports Reference
    Strategy: Search for the game on team schedule page
    """
    
    # Simplify team names for URL
    home_slug = home_team.lower().replace(' ', '-').replace("'", "")
    away_slug = away_team.lower().replace(' ', '-').replace("'", "")
    
    # Remove mascots (common ones)
    for mascot in ['blue-devils', 'tar-heels', 'wildcats', 'tigers', 'bulldogs', 
                   'eagles', 'panthers', 'bears', 'spartans', 'trojans',
                   'huskies', 'cougars', 'cardinals', 'cowboys', 'jayhawks']:
        home_slug = home_slug.replace(f'-{mascot}', '')
        away_slug = away_slug.replace(f'-{mascot}', '')
    
    # Try to construct box score URL
    # Format: /cbb/boxscores/YYYY-MM-DD-{team}.html
    # e.g., /cbb/boxscores/2025-01-05-duke.html
    
    date_str = date.replace('/', '-')  # Ensure proper format
    
    # Try home team page
    urls_to_try = [
        f"https://www.sports-reference.com/cbb/boxscores/{date_str}-{home_slug}.html",
        f"https://www.sports-reference.com/cbb/boxscores/{date_str}-{away_slug}.html",
    ]
    
    for url in urls_to_try:
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                return scrape_box_score_from_html(response.text, game_id, conn)
        except Exception as e:
            continue
    
    return False


def scrape_box_score_from_html(html_content, game_id, conn):
    """
    Parse box score HTML and extract lineups
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all stat tables (one per team)
    tables = soup.find_all('table', {'class': 'stats_table'})
    
    if len(tables) < 2:
        return False
    
    cursor = conn.cursor()
    players_inserted = 0
    
    for table in tables:
        # Get team name from table ID
        table_id = table.get('id', '')
        if not table_id or 'box-' not in table_id:
            continue
        
        team_slug = table_id.replace('box-', '').replace('-game-basic', '').replace('-game-advanced', '')
        
        # Parse table with pandas
        try:
            df = pd.read_html(StringIO(str(table)))[0]
        except:
            continue
        
        # Sports Reference marks starters differently - check thead structure
        # Typically starters come first, then a "Reserves" row
        
        is_starter = True  # First players are starters
        
        for idx, row in df.iterrows():
            player_name = row.get('Player') or row.iloc[0] if len(row) > 0 else None
            
            if pd.isna(player_name) or player_name == 'Player':
                continue
            
            # Check if this is the "Reserves" divider
            if 'Reserve' in str(player_name) or 'Bench' in str(player_name):
                is_starter = False
                continue
            
            # Skip team totals
            if 'Team Totals' in str(player_name) or player_name == 'Team':
                continue
            
            # Get minutes played
            minutes_str = row.get('MP') or row.get('Min') or row.get('MIN')
            minutes = 0
            if pd.notna(minutes_str):
                try:
                    if ':' in str(minutes_str):
                        mins, secs = str(minutes_str).split(':')
                        minutes = int(mins)
                    else:
                        minutes = int(minutes_str)
                except:
                    minutes = 0
            
            # Get basic stats
            points = row.get('PTS') or row.get('Pts')
            rebounds = row.get('TRB') or row.get('Reb')
            assists = row.get('AST') or row.get('Ast')
            
            # Clean player name
            player_name = str(player_name).strip()
            
            # Insert into game_lineups
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO game_lineups 
                    (game_id, team_name, player_name, is_starter, minutes_played, points, rebounds, assists)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (game_id, team_slug, player_name, is_starter, minutes,
                      points if pd.notna(points) else None,
                      rebounds if pd.notna(rebounds) else None,
                      assists if pd.notna(assists) else None))
                
                players_inserted += 1
                
            except Exception as e:
                logger.debug(f"Error inserting {player_name}: {e}")
                continue
    
    conn.commit()
    return players_inserted > 0


def scrape_all_game_lineups(seasons=[2025, 2026]):
    """
    Scrape lineups for all games in specified seasons
    """
    
    print("\n" + "="*70)
    print(f"🏀 SCRAPING GAME LINEUPS - Seasons {seasons}")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all games for these seasons
    cursor.execute("""
        SELECT game_id, game_date, home_team_name, away_team_name, season
        FROM games
        WHERE season IN ({})
        ORDER BY game_date
    """.format(','.join('?' * len(seasons))), seasons)
    
    games = cursor.fetchall()
    
    logger.info(f"Found {len(games):,} games to scrape\n")
    
    success = 0
    failed = 0
    
    for i, (game_id, date, home_team, away_team, season) in enumerate(games, 1):
        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(games)} | Success: {success} | Failed: {failed}")
        
        # Check if already scraped
        cursor.execute("""
            SELECT COUNT(*) FROM game_lineups WHERE game_id = ?
        """, (game_id,))
        
        if cursor.fetchone()[0] > 0:
            continue  # Already have this game
        
        try:
            result = scrape_box_score_by_teams_and_date(home_team, away_team, date, game_id, conn)
            
            if result:
                success += 1
                if i % 50 == 0:
                    logger.info(f"  ✅ {date}: {away_team} @ {home_team}")
            else:
                failed += 1
                if failed % 20 == 0:
                    logger.debug(f"  ❌ {date}: {away_team} @ {home_team}")
            
            time.sleep(3)  # Rate limiting
            
        except Exception as e:
            failed += 1
            logger.error(f"Error on game {game_id}: {e}")
            time.sleep(5)
    
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ LINEUP SCRAPING COMPLETE!")
    print(f"   Games attempted: {len(games):,}")
    print(f"   Successful: {success:,}")
    print(f"   Failed: {failed:,}")
    print(f"   Success rate: {success/len(games)*100:.1f}%")
    print("="*70 + "\n")
    
    # Summary stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(DISTINCT game_id) FROM game_lineups")
    games_with_lineups = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_lineups")
    total_player_records = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_lineups WHERE is_starter = 1")
    starters = cursor.fetchone()[0]
    
    print(f"DATABASE SUMMARY:")
    print(f"   Games with lineups: {games_with_lineups:,}")
    print(f"   Total player-game records: {total_player_records:,}")
    print(f"   Starters: {starters:,}")
    print(f"   Bench players: {total_player_records - starters:,}")
    print()
    
    conn.close()


if __name__ == "__main__":
    scrape_all_game_lineups(seasons=[2025, 2026])

