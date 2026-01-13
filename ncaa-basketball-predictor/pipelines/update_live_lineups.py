"""
Update Live Lineups Before Paper Trading
Fetches current lineups from ESPN API for upcoming games and updates the database.
This ensures the model has the most recent lineup information for predictions.
"""

import requests
import sqlite3
from pathlib import Path
import logging
from datetime import datetime, timedelta
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_upcoming_games(hours_ahead=24):
    """Get games scheduled in the next N hours"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow()
    cutoff = now + timedelta(hours=hours_ahead)
    
    cursor.execute("""
        SELECT game_id, home_team_name, away_team_name, game_date, season
        FROM games
        WHERE game_date BETWEEN ? AND ?
        ORDER BY game_date
    """, (now.isoformat(), cutoff.isoformat()))
    
    games = cursor.fetchall()
    conn.close()
    return games


def get_team_id_from_db(team_name, conn):
    """Find team_id from team name"""
    cursor = conn.cursor()
    
    # Try exact match
    cursor.execute("""
        SELECT team_id FROM teams 
        WHERE team_name = ? OR kenpom_name = ?
    """, (team_name, team_name))
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Try fuzzy match
    cursor.execute("""
        SELECT team_id FROM teams 
        WHERE team_name LIKE ? OR kenpom_name LIKE ?
    """, (f"%{team_name.split(' ')[0]}%", f"%{team_name.split(' ')[0]}%"))
    result = cursor.fetchone()
    if result:
        logger.warning(f"⚠️ Fuzzy matched '{team_name}' to team_id {result[0]}")
        return result[0]
    
    logger.warning(f"⚠️ Team '{team_name}' not found in database")
    return None


def get_player_id_from_db(player_name, team_id, season, conn):
    """Get or create player_id"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id FROM players 
        WHERE player_name = ? AND team_id = ? AND season = ?
    """, (player_name, team_id, season))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # Create new player
    cursor.execute("""
        INSERT INTO players (player_name, team_id, season)
        VALUES (?, ?, ?)
    """, (player_name, team_id, season))
    conn.commit()
    return cursor.lastrowid


def fetch_espn_lineup(game_id, home_team_name, away_team_name, season):
    """
    Fetch lineup from ESPN API for a specific game.
    Returns number of players found, or 0 if failed.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        boxscore = data.get('boxscore')
        if not boxscore:
            logger.debug(f"No boxscore data for game {game_id}")
            return 0
        
        teams_data = boxscore.get('teams')
        if not teams_data:
            logger.debug(f"No teams data for game {game_id}")
            return 0
        
        conn = get_db_connection()
        players_updated = 0
        
        for team_data in teams_data:
            team_name_espn = team_data['team']['displayName']
            team_id_db = get_team_id_from_db(team_name_espn, conn)
            
            if not team_id_db:
                logger.warning(f"Could not find team_id for '{team_name_espn}'")
                continue
            
            players_stats = team_data.get('statistics', [])
            if not players_stats:
                continue
            
            player_stats_list = players_stats[0].get('athletes', [])
            
            for player_entry in player_stats_list:
                player_name = player_entry['athlete']['displayName']
                is_starter = player_entry.get('starter', False)
                
                min_played_str = next(
                    (s['displayValue'] for s in player_entry['stats'] if s['name'] == 'min'), 
                    '0'
                )
                try:
                    minutes_played = float(min_played_str)
                except ValueError:
                    minutes_played = 0.0
                
                player_id_db = get_player_id_from_db(player_name, team_id_db, season, conn)
                
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO game_lineups 
                    (game_id, team_id, player_id, is_starter, minutes_played)
                    VALUES (?, ?, ?, ?, ?)
                """, (game_id, team_id_db, player_id_db, is_starter, minutes_played))
                players_updated += 1
        
        conn.commit()
        conn.close()
        
        if players_updated > 0:
            logger.info(f"✅ Updated lineup for game {game_id}: {players_updated} players")
        
        return players_updated
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request failed for game {game_id}: {e}")
    except Exception as e:
        logger.debug(f"Unexpected error for game {game_id}: {e}")
    
    return 0


def update_lineups_for_upcoming_games(hours_ahead=8):
    """
    Main function to update lineups for all upcoming games.
    """
    logger.info("="*70)
    logger.info("UPDATING LINEUPS FOR UPCOMING GAMES")
    logger.info("="*70)
    
    games = get_upcoming_games(hours_ahead)
    logger.info(f"\nFound {len(games)} games in the next {hours_ahead} hours")
    
    if not games:
        logger.info("No upcoming games to update")
        return 0
    
    updated_count = 0
    for game in games:
        game_id = game['game_id']
        home_team = game['home_team_name']
        away_team = game['away_team_name']
        game_date = game['game_date']
        season = game['season']
        
        logger.info(f"\nChecking game: {away_team} @ {home_team}")
        logger.info(f"  Game ID: {game_id}")
        logger.info(f"  Date: {game_date}")
        
        players_count = fetch_espn_lineup(game_id, home_team, away_team, season)
        if players_count > 0:
            updated_count += 1
        
        time.sleep(0.5)  # Be respectful to ESPN API
    
    logger.info(f"\n" + "="*70)
    logger.info(f"✅ Lineup update complete!")
    logger.info(f"   Updated {updated_count}/{len(games)} games")
    logger.info("="*70)
    
    return updated_count


if __name__ == '__main__':
    import sys
    
    # Allow custom time window from command line
    hours = 8
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid hours argument: {sys.argv[1]}")
            sys.exit(1)
    
    updated_count = update_lineups_for_upcoming_games(hours_ahead=hours)
    
    if updated_count == 0:
        logger.warning("⚠️ No lineups were updated. This is normal if:")
        logger.warning("   1. No games are scheduled in the time window")
        logger.warning("   2. Lineups haven't been announced yet (typically 30-60 min before tip)")
        logger.warning("   3. Games are still in the future and ESPN hasn't published data")

