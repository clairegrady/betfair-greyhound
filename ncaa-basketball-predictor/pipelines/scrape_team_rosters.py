"""
Enterprise-Grade KenPom Team Roster Scraper

Scrapes player shooting percentages (2P%, 3P%, FT%) from team roster pages.
This is necessary because KenPom doesn't have leaderboard pages for these metrics.

Design:
- Scrapes all D-I teams (~365 teams)
- Extracts complete player rosters with shooting stats
- Rate limiting: 2s between requests
- Robust error handling and logging
- Progress tracking
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
from tqdm import tqdm
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from kenpompy.utils import login, get_html
import kenpompy.team as kt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class KenPomTeamRosterScraper:
    """Scrapes complete team rosters from KenPom including shooting percentages"""
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        email: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit_seconds: float = 2.0
    ):
        self.db_path = db_path
        self.email = email or os.getenv('KENPOM_EMAIL')
        self.password = password or os.getenv('KENPOM_PASSWORD')
        self.rate_limit = rate_limit_seconds
        self.browser = None
        self.conn = None
        
        if not self.email or not self.password:
            raise ValueError("❌ KenPom email and password required")
    
    def __enter__(self):
        """Initialize browser and database"""
        logger.info("🔐 Logging in to KenPom...")
        self.browser = login(self.email, self.password)
        logger.info("✅ Authenticated")
        
        self.conn = sqlite3.connect(self.db_path)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup"""
        if self.conn:
            self.conn.commit()
            self.conn.close()
    
    def get_all_teams(self, season: int = 2025) -> List[str]:
        """Get list of all D-I teams for a season"""
        logger.info(f"📋 Fetching team list for season {season}...")
        teams = kt.get_valid_teams(self.browser, season=str(season))
        logger.info(f"✅ Found {len(teams)} teams")
        return teams
    
    def scrape_team_roster(self, team: str, season: int = 2025) -> List[Dict]:
        """
        Scrape player roster from a team's page
        
        Returns list of player dicts with: player_name, ht, wt, yr, g, ortg, ft_pct, two_pt_pct, three_pt_pct, etc.
        """
        try:
            time.sleep(self.rate_limit)
            
            url = f'https://kenpom.com/team.php?team={team}&y={season}'
            html = get_html(self.browser, url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the roster table (has %Min, 2PM-A headers)
            roster_table = None
            for table in soup.find_all('table'):
                headers = []
                thead = table.find('thead')
                if thead:
                    headers = [th.text.strip() for th in thead.find_all('th')]
                
                if '%Min' in headers and '2PM-A' in headers:
                    roster_table = table
                    break
            
            if not roster_table:
                logger.warning(f"⚠️  No roster table found for {team}")
                return []
            
            # Parse headers to get column indices
            headers = [th.text.strip() for th in roster_table.find('thead').find_all('th')]
            
            # Find column indices
            col_map = {}
            for i, header in enumerate(headers):
                col_map[header] = i
            
            # Parse player rows
            players = []
            tbody = roster_table.find('tbody')
            rows = tbody.find_all('tr') if tbody else roster_table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all(['td', 'th'])
                
                # Skip header rows (like "Go-to guys")
                if len(cols) < 10:
                    continue
                
                # Skip if first column is empty or just a category header
                first_col_text = cols[0].text.strip()
                if not first_col_text or not first_col_text[0].isdigit():
                    continue
                
                try:
                    # Extract player data
                    player = {
                        'team': team,
                        'season': season,
                    }
                    
                    # Player name is usually in column 1
                    player_cell = cols[1] if len(cols) > 1 else None
                    if player_cell:
                        # Remove "National Rank" text
                        player_name = player_cell.text.strip().split('\\n')[0].strip()
                        player['player_name'] = player_name
                    else:
                        continue
                    
                    # Extract other columns based on header map
                    for col_name, col_idx in col_map.items():
                        if col_idx >= len(cols):
                            continue
                        
                        value = cols[col_idx].text.strip()
                        
                        # Map to database columns
                        if col_name == 'Ht':
                            player['height'] = value
                        elif col_name == 'Wt':
                            try:
                                player['weight'] = int(value) if value else None
                            except:
                                player['weight'] = None
                        elif col_name == 'Yr':
                            player['class_year'] = value
                        elif col_name == 'G':
                            try:
                                player['games_played'] = int(value) if value else None
                            except:
                                player['games_played'] = None
                        elif col_name == 'ORtg':
                            # Remove rank number
                            try:
                                player['offensive_rating'] = float(value.split()[0]) if value else None
                            except:
                                player['offensive_rating'] = None
                        elif col_name == '%Poss':
                            try:
                                player['usage_rate'] = float(value.split()[0]) if value else None
                            except:
                                player['usage_rate'] = None
                    
                    # Extract shooting percentages (FT, 2P, 3P)
                    # These are in pairs: "FTM-A" then "Pct"
                    # Find the indices
                    ft_idx = None
                    two_pt_idx = None
                    three_pt_idx = None
                    
                    for i, header in enumerate(headers):
                        if header == 'FTM-A' and i + 1 < len(headers):
                            ft_idx = i + 1
                        elif header == '2PM-A' and i + 1 < len(headers):
                            two_pt_idx = i + 1
                        elif header == '3PM-A' and i + 1 < len(headers):
                            three_pt_idx = i + 1
                    
                    # Extract percentages
                    if ft_idx and ft_idx < len(cols):
                        ft_pct_text = cols[ft_idx].text.strip()
                        try:
                            # Extract first value, remove rank if present
                            ft_pct = ft_pct_text.split()[0]
                            if ft_pct and ft_pct != '-':
                                # KenPom shows percentages like ".840" or "0.840"
                                pct = float(ft_pct)
                                # If already in decimal form (0.0-1.0), use as-is
                                # If in percentage form (0-100), convert
                                if pct > 1.0:
                                    pct = pct / 100.0
                                player['ft_pct'] = pct
                        except (ValueError, IndexError):
                            player['ft_pct'] = None
                    
                    if two_pt_idx and two_pt_idx < len(cols):
                        two_pt_text = cols[two_pt_idx].text.strip()
                        try:
                            two_pct = two_pt_text.split()[0]
                            if two_pct and two_pct != '-':
                                pct = float(two_pct)
                                if pct > 1.0:
                                    pct = pct / 100.0
                                player['two_pt_pct'] = pct
                        except (ValueError, IndexError):
                            player['two_pt_pct'] = None
                    
                    if three_pt_idx and three_pt_idx < len(cols):
                        three_pt_text = cols[three_pt_idx].text.strip()
                        try:
                            three_pct = three_pt_text.split()[0]
                            if three_pct and three_pct != '-':
                                pct = float(three_pct)
                                if pct > 1.0:
                                    pct = pct / 100.0
                                player['three_pt_pct'] = pct
                        except (ValueError, IndexError):
                            player['three_pt_pct'] = None
                    
                    players.append(player)
                    
                except Exception as e:
                    logger.debug(f"Error parsing player row: {e}")
                    continue
            
            return players
            
        except Exception as e:
            logger.error(f"❌ Error scraping {team}: {e}")
            return []
    
    def update_player_stats(self, players: List[Dict]) -> int:
        """Insert/update players and their shooting percentages"""
        if not players:
            return 0
        
        cursor = self.conn.cursor()
        inserted = 0
        updated = 0
        
        for player in players:
            try:
                player_name = player['player_name']
                season = player['season']
                
                # Try to find matching team_id from our database
                team_id = None
                if 'team' in player:
                    # Try to match team name
                    result = cursor.execute("""
                        SELECT our_team_id FROM team_name_mapping 
                        WHERE kenpom_team_name = ?
                    """, (player['team'],)).fetchone()
                    if result:
                        team_id = result[0]
                
                # Insert player if doesn't exist
                cursor.execute("""
                    INSERT OR IGNORE INTO players (player_name, team_id, season)
                    VALUES (?, ?, ?)
                """, (player_name, team_id, season))
                
                # Get player_id
                player_id = cursor.execute("""
                    SELECT player_id FROM players 
                    WHERE player_name = ? AND season = ?
                """, (player_name, season)).fetchone()
                
                if not player_id:
                    continue
                
                player_id = player_id[0]
                
                # Insert or update player_stats
                cursor.execute("""
                    INSERT INTO player_stats (
                        player_id, season, 
                        two_pt_pct, three_pt_pct, ft_pct,
                        offensive_rating, usage_rate, games_played
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, season) DO UPDATE SET
                        two_pt_pct = COALESCE(excluded.two_pt_pct, two_pt_pct),
                        three_pt_pct = COALESCE(excluded.three_pt_pct, three_pt_pct),
                        ft_pct = COALESCE(excluded.ft_pct, ft_pct),
                        offensive_rating = COALESCE(excluded.offensive_rating, offensive_rating),
                        usage_rate = COALESCE(excluded.usage_rate, usage_rate),
                        games_played = COALESCE(excluded.games_played, games_played),
                        scraped_at = CURRENT_TIMESTAMP
                """, (
                    player_id, season,
                    player.get('two_pt_pct'),
                    player.get('three_pt_pct'),
                    player.get('ft_pct'),
                    player.get('offensive_rating'),
                    player.get('usage_rate'),
                    player.get('games_played')
                ))
                
                if cursor.rowcount > 0:
                    updated += 1
                
            except Exception as e:
                logger.debug(f"Error updating player {player.get('player_name')}: {e}")
                continue
        
        self.conn.commit()
        return updated
    
    def run(self, season: int = 2025) -> Dict:
        """Main execution - scrape all teams"""
        logger.info(f"🚀 Starting team roster scraping for season {season}")
        
        # Get all teams
        teams = self.get_all_teams(season)
        
        total_players = 0
        total_updated = 0
        teams_scraped = 0
        teams_failed = 0
        
        for team in tqdm(teams, desc="Scraping teams"):
            try:
                players = self.scrape_team_roster(team, season)
                if players:
                    total_players += len(players)
                    updated = self.update_player_stats(players)
                    total_updated += updated
                    teams_scraped += 1
                else:
                    teams_failed += 1
            except Exception as e:
                logger.error(f"❌ Failed to scrape {team}: {e}")
                teams_failed += 1
                continue
        
        # Verify
        cursor = self.conn.cursor()
        players_with_shooting = cursor.execute("""
            SELECT COUNT(*) FROM player_stats 
            WHERE two_pt_pct IS NOT NULL OR three_pt_pct IS NOT NULL OR ft_pct IS NOT NULL
        """).fetchone()[0]
        
        results = {
            'season': season,
            'teams_scraped': teams_scraped,
            'teams_failed': teams_failed,
            'total_teams': len(teams),
            'players_found': total_players,
            'players_updated': total_updated,
            'players_with_shooting_stats': players_with_shooting
        }
        
        logger.info(f"✅ Scraping complete: {results}")
        return results


def main():
    """Entry point"""
    load_dotenv(Path(__file__).parent.parent / 'config.env')
    
    print("\n" + "="*70)
    print("🏀 KENPOM TEAM ROSTER SCRAPER - SHOOTING PERCENTAGES")
    print("="*70)
    print("Scraping shooting stats from all D-I team rosters...")
    print("This will take ~15-20 minutes (365 teams × 2 seconds)")
    print("="*70 + "\n")
    
    try:
        with KenPomTeamRosterScraper(rate_limit_seconds=2.0) as scraper:
            results = scraper.run(season=2025)
        
        print("\n" + "="*70)
        print("📊 FINAL RESULTS")
        print("="*70)
        print(f"✅ Teams Scraped: {results['teams_scraped']}/{results['total_teams']}")
        print(f"❌ Teams Failed: {results['teams_failed']}")
        print(f"👥 Players Found: {results['players_found']:,}")
        print(f"📈 Players Updated: {results['players_updated']:,}")
        print(f"🎯 Players with Shooting Stats: {results['players_with_shooting_stats']:,}")
        print("="*70)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()

