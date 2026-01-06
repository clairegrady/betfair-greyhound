"""
Scrape game lineups from ESPN API for all historical games
ESPN provides clean JSON with starter flags and full stats
"""

import sqlite3
import requests
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def scrape_espn_box_score(game_id, conn):
    """
    Scrape lineup data from ESPN API for a single game
    Returns: (success, players_inserted)
    """
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return False, 0
        
        data = response.json()
        
        if 'boxscore' not in data or 'players' not in data['boxscore']:
            return False, 0
        
        cursor = conn.cursor()
        players_inserted = 0
        
        # Process each team's players
        for team_data in data['boxscore']['players']:
            try:
                team_name = team_data['team']['displayName']
            except:
                continue
            
            # Get player statistics
            for stat_group in team_data['statistics']:
                labels = stat_group['names']
                
                for athlete_data in stat_group['athletes']:
                    try:
                        # Get athlete info
                        athlete = athlete_data.get('athlete', {})
                        if not athlete:
                            continue
                        
                        player_name = athlete.get('displayName', '')
                        if not player_name:
                            continue
                        
                        # Check if starter
                        is_starter = athlete_data.get('starter', False)
                        
                        # Get stats
                        stats = athlete_data.get('stats', [])
                        stat_dict = dict(zip(labels, stats))
                        
                        # Parse minutes (might be string like "34:30")
                        mins_str = stat_dict.get('MIN', '0')
                        try:
                            if ':' in str(mins_str):
                                mins, secs = str(mins_str).split(':')
                                minutes = int(mins)
                            else:
                                minutes = int(float(mins_str)) if mins_str else 0
                        except:
                            minutes = 0
                        
                        # Get other stats
                        points = stat_dict.get('PTS')
                        rebounds = stat_dict.get('REB')
                        assists = stat_dict.get('AST')
                        
                        # Convert to int if possible
                        try:
                            points = int(points) if points else None
                        except:
                            points = None
                        
                        try:
                            rebounds = int(rebounds) if rebounds else None
                        except:
                            rebounds = None
                        
                        try:
                            assists = int(assists) if assists else None
                        except:
                            assists = None
                        
                        # Insert into database
                        cursor.execute("""
                            INSERT OR REPLACE INTO game_lineups 
                            (game_id, team_name, player_name, is_starter, minutes_played, points, rebounds, assists)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (game_id, team_name, player_name, is_starter, minutes, points, rebounds, assists))
                        
                        players_inserted += 1
                        
                    except Exception as e:
                        logger.debug(f"Error processing athlete: {e}")
                        continue
                
                break  # Only need first stat group per team
        
        conn.commit()
        return True, players_inserted
        
    except Exception as e:
        logger.debug(f"Error scraping game {game_id}: {e}")
        return False, 0


def scrape_all_game_lineups(seasons=[2024, 2025, 2026]):
    """
    Scrape lineups for all games using ESPN game IDs
    """
    
    print("\n" + "="*70)
    print(f"🏀 SCRAPING GAME LINEUPS FROM ESPN - Seasons {seasons}")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all games with ESPN game IDs
    # Our game_id might be ESPN ID or might be custom
    # Let's check what format we have
    cursor.execute("""
        SELECT game_id, game_date, home_team_name, away_team_name, season
        FROM games
        WHERE season IN ({})
        AND game_id NOT LIKE '%_%'
        ORDER BY game_date
    """.format(','.join('?' * len(seasons))), seasons)
    
    games = cursor.fetchall()
    
    logger.info(f"Found {len(games):,} games with ESPN-style IDs\n")
    
    if len(games) == 0:
        # Try alternative: look for any numeric game IDs
        cursor.execute("""
            SELECT game_id, game_date, home_team_name, away_team_name, season
            FROM games
            WHERE season IN ({})
            ORDER BY game_date
        """.format(','.join('?' * len(seasons))), seasons)
        
        games = cursor.fetchall()
        logger.info(f"Found {len(games):,} total games\n")
    
    success = 0
    failed = 0
    total_players = 0
    
    for i, (game_id, date, home_team, away_team, season) in enumerate(games, 1):
        
        # Check if already scraped
        cursor.execute("""
            SELECT COUNT(*) FROM game_lineups WHERE game_id = ?
        """, (game_id,))
        
        if cursor.fetchone()[0] > 0:
            continue  # Already have this game
        
        try:
            result, num_players = scrape_espn_box_score(game_id, conn)
            
            if result:
                success += 1
                total_players += num_players
                if i % 50 == 0:
                    logger.info(f"  ✅ [{i}/{len(games)}] {date}: {away_team} @ {home_team} ({num_players} players)")
            else:
                failed += 1
                if failed % 50 == 0:
                    logger.debug(f"  ❌ [{i}/{len(games)}] {date}: {away_team} @ {home_team}")
            
            # Progress update every 100 games
            if i % 100 == 0:
                pct = (success / i) * 100
                logger.info(f"\n📊 Progress: {i}/{len(games)} | Success: {success} ({pct:.1f}%) | Failed: {failed}\n")
            
            time.sleep(1)  # Rate limiting (ESPN is pretty lenient)
            
        except Exception as e:
            failed += 1
            logger.error(f"Error on game {game_id}: {e}")
            time.sleep(2)
    
    conn.close()
    
    print("\n" + "="*70)
    print(f"✅ LINEUP SCRAPING COMPLETE!")
    print(f"   Games attempted: {len(games):,}")
    print(f"   Successful: {success:,} ({success/len(games)*100:.1f}%)")
    print(f"   Failed: {failed:,}")
    print(f"   Players collected: {total_players:,}")
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
    
    cursor.execute("SELECT AVG(minutes_played) FROM game_lineups WHERE minutes_played > 0")
    avg_minutes = cursor.fetchone()[0]
    
    print(f"📊 DATABASE SUMMARY:")
    print(f"   Games with lineups: {games_with_lineups:,}")
    print(f"   Total player-game records: {total_player_records:,}")
    print(f"   Starters: {starters:,}")
    print(f"   Bench players: {total_player_records - starters:,}")
    print(f"   Avg minutes per player: {avg_minutes:.1f}")
    print()
    
    conn.close()


if __name__ == "__main__":
    scrape_all_game_lineups(seasons=[2024, 2025, 2026])

