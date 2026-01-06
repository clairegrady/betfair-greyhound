"""
Scrape KenPom for SPECIFIC SEASON (command-line argument)
Usage: python scrape_season.py 2025
"""

import sqlite3
import pandas as pd
from kenpompy.utils import login, get_html
from kenpompy.team import get_valid_teams
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import logging
import re
import time
from pathlib import Path
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_player_id(player_name, team_id, season, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT player_id FROM players WHERE player_name = ? AND team_id = ? AND season = ?", (player_name, team_id, season))
    result = cursor.fetchone()
    if result:
        return result['player_id']
    else:
        cursor.execute("INSERT INTO players (player_name, team_id, season) VALUES (?, ?, ?)", (player_name, team_id, season))
        return cursor.lastrowid


def get_team_id(team_name, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT team_id FROM teams WHERE team_name = ? OR kenpom_name = ?", (team_name, team_name))
    result = cursor.fetchone()
    if result:
        return result['team_id']
    else:
        logger.warning(f"⚠️ Team not found in DB: {team_name}. Inserting.")
        cursor.execute("INSERT INTO teams (team_name, kenpom_name) VALUES (?, ?)", (team_name, team_name))
        return cursor.lastrowid


def clean_player_name(name):
    if not isinstance(name, str):
        return str(name)
    name = re.sub(r'\s+\d+\s+National Rank', '', name)
    name = re.sub(r'\s+National Rank', '', name)
    name = name.strip()
    return name


def scrape_team(browser, team_name, season, conn):
    try:
        team_id = get_team_id(team_name, conn)
        url = f"https://kenpom.com/team.php?team={team_name.replace(' ', '%20')}&y={season}"
        html_content = get_html(browser, url)
        soup = BeautifulSoup(html_content, 'html5lib')
        tables = pd.read_html(str(soup), flavor='html5lib')

        player_stats_table = None
        for table in tables:
            if '%Min' in table.columns:
                player_stats_table = table
                break

        if player_stats_table is None:
            logger.warning(f"❌ No player table for {team_name}")
            return 0
        
        inserted = 0
        for index, row in player_stats_table.iterrows():
            player_name_raw = row.get('Unnamed: 1')
            if pd.isna(player_name_raw):
                continue
            
            player_name = clean_player_name(player_name_raw)
            player_id = get_player_id(player_name, team_id, season, conn)

            height_str = row.get('Ht')
            height_inches = None
            if isinstance(height_str, str) and '-' in height_str:
                try:
                    feet, inches = map(int, height_str.split('-'))
                    height_inches = feet * 12 + inches
                except:
                    pass
            
            weight = row.get('Wt')
            if pd.isna(weight):
                weight = None
            else:
                try:
                    weight = int(weight)
                except:
                    weight = None

            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO player_stats (
                    player_id, season, player_name,
                    minutes_played, offensive_rating, usage_rate,
                    shot_rate, efg_pct, true_shooting_pct,
                    assist_rate, turnover_rate,
                    offensive_rebound_rate, defensive_rebound_rate,
                    steal_rate, block_rate,
                    fouls_committed_40, fouls_drawn_40, ft_rate,
                    two_pt_pct, three_pt_pct, ft_pct,
                    games_played, games_started,
                    height_inches, weight, class_year
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id, season, player_name,
                row.get('%Min'), row.get('ORtg'), row.get('%Poss'),
                row.get('%Shots'), row.get('eFG%'), row.get('TS%'),
                row.get('ARate'), row.get('TORate'),
                row.get('OR%'), row.get('DR%'),
                row.get('Stl%'), row.get('Blk%'),
                row.get('FC/40'), row.get('FD/40'), row.get('FTRate'),
                row.get('Pct.1'), row.get('Pct.2'), row.get('Pct'),
                row.get('G'), row.get('S'),
                height_inches, weight, row.get('Yr')
            ))
            
            inserted += 1
        
        conn.commit()
        return inserted
        
    except Exception as e:
        logger.error(f"❌ Error scraping {team_name}: {e}")
        return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_season.py <season>")
        print("Example: python scrape_season.py 2025  # for 2024-25 season")
        sys.exit(1)
    
    season = int(sys.argv[1])
    
    print("\n" + "="*70)
    print(f"🏀 SCRAPING ALL D1 TEAMS - SEASON {season} ({season-1}-{str(season)[2:]})")
    print("="*70 + "\n")
    
    load_dotenv(Path(__file__).parent.parent / "config.env")
    email = os.getenv('KENPOM_EMAIL')
    password = os.getenv('KENPOM_PASSWORD')
    
    if not email or not password:
        logger.error("KENPOM_EMAIL and KENPOM_PASSWORD must be set!")
        sys.exit(1)
    
    logger.info("🔐 Logging in to KenPom...")
    browser = login(email, password)
    logger.info("✅ Logged in")
    
    logger.info(f"📋 Getting list of all D1 teams for season {season}...")
    teams = get_valid_teams(browser, season=str(season))
    logger.info(f"✅ Found {len(teams)} teams")
    
    conn = get_db_connection()
    
    total_players = 0
    for i, team_name in enumerate(teams, 1):
        if i % 20 == 0:
            logger.info(f"Progress: {i}/{len(teams)} teams | {total_players} players")
        
        try:
            count = scrape_team(browser, team_name, season, conn)
            total_players += count
            
            if count > 0:
                logger.info(f"✅ {team_name}: {count} players")
            
            time.sleep(6)
            
        except Exception as e:
            logger.error(f"❌ Failed {team_name}: {e}")
            time.sleep(10)
    
    conn.close()
    browser.close()
    
    print("\n" + "="*70)
    print(f"✅ SCRAPING COMPLETE - SEASON {season}")
    print(f"   Total players scraped: {total_players}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

