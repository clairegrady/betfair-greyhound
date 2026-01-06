"""
Injury Tracker - Enterprise Grade

Scrapes injury reports from ESPN:
- Current injuries
- Player status (out/questionable/probable)
- Expected return dates
- Impact scoring

Design Principles:
- Respectful scraping with rate limiting
- Robust error handling
- Data validation
- Comprehensive logging
- Historical tracking
"""

import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from tqdm import tqdm
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"
ESPN_INJURIES_URL = "https://www.espn.com/mens-college-basketball/injuries"


class InjuryTracker:
    """Tracks player injuries from ESPN"""
    
    def __init__(
        self,
        db_path: Path = DB_PATH,
        rate_limit_seconds: float = 2.0,
        max_retries: int = 3
    ):
        self.db_path = db_path
        self.rate_limit = rate_limit_seconds
        self.max_retries = max_retries
        self.session = None
        self.conn = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive'
        })
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
        if self.conn:
            self.conn.close()
    
    def create_injury_tables(self):
        """Ensure injury tables exist with proper schema"""
        cursor = self.conn.cursor()
        
        # Update injuries table to be more comprehensive
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_injuries (
                injury_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                injury_status TEXT NOT NULL,  -- OUT, QUESTIONABLE, DOUBTFUL, PROBABLE
                injury_description TEXT,
                expected_return TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'ESPN',
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                UNIQUE(team_id, player_name, last_updated)
            )
        """)
        
        # Historical injuries for analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS injury_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                injury_status TEXT NOT NULL,
                injury_description TEXT,
                reported_date DATE NOT NULL,
                resolved_date DATE,
                games_missed INTEGER DEFAULT 0,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)
        
        self.conn.commit()
        logger.info("✅ Injury tables created/verified")
    
    def scrape_espn_injuries(self) -> List[Dict]:
        """Scrape current injuries from ESPN"""
        injuries = []
        
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.rate_limit + random.uniform(0, 0.5))
                
                response = self.session.get(ESPN_INJURIES_URL, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    injuries = self._parse_espn_injuries(soup)
                    logger.info(f"✅ Scraped {len(injuries)} injuries from ESPN")
                    return injuries
                    
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    logger.warning(f"⚠️  Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    logger.warning(f"⚠️  HTTP {response.status_code} from ESPN")
                    return []
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
                return []
            except Exception as e:
                logger.error(f"❌ Unexpected error scraping ESPN: {e}")
                return []
        
        return []
    
    def _parse_espn_injuries(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse injury data from ESPN HTML"""
        injuries = []
        
        # ESPN typically structures injury reports by team
        # Look for injury tables or sections
        injury_sections = soup.find_all('div', class_='ResponsiveTable') or \
                         soup.find_all('table', class_='injuries') or \
                         soup.find_all('div', {'data-module': 'injuries'})
        
        if not injury_sections:
            # Try alternative selectors
            injury_sections = soup.find_all('section', class_='Card')
            
        logger.debug(f"Found {len(injury_sections)} potential injury sections")
        
        for section in injury_sections:
            try:
                # Extract team name
                team_header = section.find('h2') or section.find('div', class_='team-name') or \
                             section.find('a', class_='team-link')
                
                if not team_header:
                    continue
                
                team_name = team_header.text.strip()
                
                # Find injury rows
                rows = section.find_all('tr')[1:]  # Skip header
                
                if not rows:
                    # Try different structure
                    rows = section.find_all('div', class_='injury-row')
                
                for row in rows:
                    try:
                        cols = row.find_all('td') if row.name == 'tr' else row.find_all('div')
                        
                        if len(cols) < 3:
                            continue
                        
                        player_name = cols[0].text.strip()
                        status = cols[1].text.strip().upper()
                        description = cols[2].text.strip() if len(cols) > 2 else ""
                        expected_return = cols[3].text.strip() if len(cols) > 3 else ""
                        
                        injuries.append({
                            'team_name': team_name,
                            'player_name': player_name,
                            'status': status,
                            'description': description,
                            'expected_return': expected_return
                        })
                        
                    except Exception as e:
                        logger.debug(f"Error parsing injury row: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error parsing injury section: {e}")
                continue
        
        return injuries
    
    def match_team_name(self, espn_team_name: str) -> Optional[int]:
        """Match ESPN team name to our database team_id"""
        cursor = self.conn.cursor()
        
        # Try exact match first
        result = cursor.execute(
            "SELECT team_id FROM teams WHERE team_name = ?",
            (espn_team_name,)
        ).fetchone()
        
        if result:
            return result[0]
        
        # Try fuzzy match with LIKE
        result = cursor.execute(
            "SELECT team_id FROM teams WHERE team_name LIKE ?",
            (f"%{espn_team_name}%",)
        ).fetchone()
        
        if result:
            return result[0]
        
        # Try reverse
        teams = cursor.execute("SELECT team_id, team_name FROM teams").fetchall()
        for team_id, team_name in teams:
            if team_name in espn_team_name or espn_team_name in team_name:
                return team_id
        
        logger.warning(f"⚠️  Could not match team: {espn_team_name}")
        return None
    
    def insert_injuries(self, injuries: List[Dict]) -> int:
        """Insert injuries into database"""
        if not injuries:
            return 0
        
        cursor = self.conn.cursor()
        inserted = 0
        skipped = 0
        
        # Clear current injuries (will repopulate)
        cursor.execute("DELETE FROM current_injuries WHERE source = 'ESPN'")
        
        for injury in injuries:
            try:
                # Match team
                team_id = self.match_team_name(injury['team_name'])
                if not team_id:
                    skipped += 1
                    continue
                
                # Insert current injury
                cursor.execute("""
                    INSERT INTO current_injuries (
                        team_id, player_name, injury_status,
                        injury_description, expected_return, source
                    ) VALUES (?, ?, ?, ?, ?, 'ESPN')
                """, (
                    team_id,
                    injury['player_name'],
                    injury['status'],
                    injury['description'],
                    injury['expected_return']
                ))
                
                inserted += 1
                
            except Exception as e:
                logger.error(f"Error inserting injury for {injury.get('player_name')}: {e}")
                continue
        
        self.conn.commit()
        logger.info(f"✅ Inserted {inserted} injuries, skipped {skipped}")
        return inserted
    
    def calculate_injury_impact(self, team_id: int) -> Dict[str, any]:
        """Calculate impact of injuries on a team"""
        cursor = self.conn.cursor()
        
        # Get current injuries
        injuries = cursor.execute("""
            SELECT player_name, injury_status
            FROM current_injuries
            WHERE team_id = ?
        """, (team_id,)).fetchall()
        
        if not injuries:
            return {
                'total_injuries': 0,
                'out_count': 0,
                'questionable_count': 0,
                'impact_score': 0.0
            }
        
        out_count = sum(1 for _, status in injuries if status == 'OUT')
        questionable_count = sum(1 for _, status in injuries if status in ['QUESTIONABLE', 'DOUBTFUL'])
        
        # Simple impact score: OUT = 1.0, QUESTIONABLE = 0.5, DOUBTFUL = 0.7
        impact_score = out_count * 1.0 + \
                      sum(0.7 for _, status in injuries if status == 'DOUBTFUL') + \
                      sum(0.5 for _, status in injuries if status == 'QUESTIONABLE')
        
        return {
            'total_injuries': len(injuries),
            'out_count': out_count,
            'questionable_count': questionable_count,
            'impact_score': round(impact_score, 2)
        }
    
    def run(self) -> Dict[str, int]:
        """Main execution - scrape and store injuries"""
        logger.info("Starting Injury Tracking")
        
        # Create tables
        self.create_injury_tables()
        
        # Scrape ESPN
        injuries = self.scrape_espn_injuries()
        
        # Insert injuries
        inserted = self.insert_injuries(injuries)
        
        # Calculate summary stats
        cursor = self.conn.cursor()
        total_injuries = cursor.execute(
            "SELECT COUNT(*) FROM current_injuries"
        ).fetchone()[0]
        
        teams_affected = cursor.execute(
            "SELECT COUNT(DISTINCT team_id) FROM current_injuries"
        ).fetchone()[0]
        
        results = {
            'injuries_found': len(injuries),
            'injuries_inserted': inserted,
            'total_injuries': total_injuries,
            'teams_affected': teams_affected
        }
        
        logger.info(f"✅ Injury tracking complete: {results}")
        return results


def main():
    """Entry point"""
    print("\n" + "="*70)
    print("🏥 NCAA BASKETBALL - INJURY TRACKER")
    print("="*70)
    
    with InjuryTracker(rate_limit_seconds=2.0) as tracker:
        results = tracker.run()
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"🔍 Injuries Found: {results['injuries_found']}")
    print(f"✅ Injuries Inserted: {results['injuries_inserted']}")
    print(f"💾 Total in DB: {results['total_injuries']}")
    print(f"🏀 Teams Affected: {results['teams_affected']}")
    print("="*70)


if __name__ == "__main__":
    main()

