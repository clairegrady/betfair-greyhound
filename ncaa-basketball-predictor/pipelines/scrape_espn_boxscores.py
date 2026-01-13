#!/usr/bin/env python3
"""
Scrape player stats from ESPN box scores for ALL completed games
This is MUCH faster and more complete than Sports Reference!
"""

import sqlite3
import requests
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"

def get_espn_box_score(espn_game_id):
    """Fetch box score from ESPN API"""
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={espn_game_id}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'boxscore' in data and 'players' in data['boxscore']:
                return data['boxscore']['players']
    except Exception as e:
        logger.error(f"Error fetching {espn_game_id}: {e}")
    
    return None


def parse_box_score(players_data):
    """Extract player stats from ESPN box score"""
    player_stats = []
    
    for team in players_data:
        team_name = team.get('team', {}).get('displayName', '')
        
        if not team.get('statistics'):
            continue
            
        stat_labels = team['statistics'][0].get('labels', [])
        athletes = team['statistics'][0].get('athletes', [])
        
        for athlete_data in athletes:
            athlete = athlete_data.get('athlete', {})
            stats = athlete_data.get('stats', [])
            
            player_name = athlete.get('displayName', '')
            if not player_name or not stats:
                continue
            
            # Parse stats array: ['MIN', 'FG', '3PT', 'FT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PF', 'PTS']
            try:
                stat_dict = dict(zip(stat_labels, stats))
                
                # Extract the stats we need
                player_stats.append({
                    'name': player_name,
                    'team': team_name,
                    'points': float(stat_dict.get('PTS', 0)) if stat_dict.get('PTS') != '-' else 0,
                    'rebounds': float(stat_dict.get('REB', 0)) if stat_dict.get('REB') != '-' else 0,
                    'assists': float(stat_dict.get('AST', 0)) if stat_dict.get('AST') != '-' else 0,
                    'steals': float(stat_dict.get('STL', 0)) if stat_dict.get('STL') != '-' else 0,
                    'blocks': float(stat_dict.get('BLK', 0)) if stat_dict.get('BLK') != '-' else 0,
                    'minutes': float(stat_dict.get('MIN', 0)) if stat_dict.get('MIN', '0') != '-' else 0,
                })
            except Exception as e:
                logger.warning(f"Error parsing stats for {player_name}: {e}")
                continue
    
    return player_stats


def update_player_season_stats(conn, season):
    """Update player_stats with season averages from game box scores"""
    cursor = conn.cursor()
    
    # Get all completed games for this season with ESPN IDs
    cursor.execute("""
        SELECT DISTINCT espn_game_id, game_date
        FROM games
        WHERE home_score IS NOT NULL 
          AND espn_game_id IS NOT NULL
          AND game_date LIKE ?
        ORDER BY game_date
    """, (f"{season-1}%",))
    
    games = cursor.fetchall()
    logger.info(f"Found {len(games)} completed games with ESPN IDs for season {season}")
    
    # Collect all player game stats
    player_game_stats = {}  # {(player_name, team): [game_stats]}
    
    games_processed = 0
    for espn_game_id, game_date in games:
        box_score = get_espn_box_score(espn_game_id)
        if not box_score:
            continue
        
        player_stats = parse_box_score(box_score)
        
        for stats in player_stats:
            key = (stats['name'], stats['team'])
            if key not in player_game_stats:
                player_game_stats[key] = []
            player_game_stats[key].append(stats)
        
        games_processed += 1
        if games_processed % 100 == 0:
            logger.info(f"  Processed {games_processed}/{len(games)} games...")
        
        time.sleep(0.1)  # Be nice to ESPN
    
    logger.info(f"Collected stats for {len(player_game_stats)} unique players")
    
    # Calculate season averages and update database
    updated = 0
    for (player_name, team), games_stats in player_game_stats.items():
        num_games = len(games_stats)
        if num_games == 0:
            continue
        
        # Calculate averages
        ppg = sum(g['points'] for g in games_stats) / num_games
        rpg = sum(g['rebounds'] for g in games_stats) / num_games
        apg = sum(g['assists'] for g in games_stats) / num_games
        spg = sum(g['steals'] for g in games_stats) / num_games
        bpg = sum(g['blocks'] for g in games_stats) / num_games
        
        # Update database - match by player_name and season
        cursor.execute("""
            UPDATE player_stats
            SET points_per_game = ?,
                rebounds_per_game = ?,
                assists_per_game = ?,
                steals_per_game = ?,
                blocks_per_game = ?,
                games_played = ?
            WHERE player_name LIKE ? AND season = ?
        """, (ppg, rpg, apg, spg, bpg, num_games, f"%{player_name}%", season))
        
        if cursor.rowcount > 0:
            updated += 1
    
    conn.commit()
    return updated


def main():
    print("\n" + "="*70)
    print("📊 ESPN BOX SCORE SCRAPER - Get 100% Player Stats")
    print("="*70 + "\n")
    
    conn = sqlite3.connect(DB_PATH)
    
    for season in [2025, 2026]:
        season_label = f"{season-1}-{str(season)[2:]}"
        print(f"\n{'='*70}")
        print(f"Season {season_label}")
        print('='*70)
        
        updated = update_player_season_stats(conn, season)
        logger.info(f"✅ Updated {updated} players for season {season_label}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ ESPN BOX SCORE SCRAPING COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

