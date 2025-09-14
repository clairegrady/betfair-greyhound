import pandas as pd
import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime, timedelta
import logging
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('favorite_tracker.log'),
        logging.StreamHandler()
    ]
)

class FavoriteTracker:
    def __init__(self):
        self.db_path = 'favorite_tracking.db'
        self.setup_database()
        
    def setup_database(self):
        """Create database tables for tracking favorites and results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for pre-race favorites
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            horse_name TEXT,
            jockey_name TEXT,
            trainer_name TEXT,
            barrier INTEGER,
            weight REAL,
            form TEXT,
            odds REAL,
            favorite_rank INTEGER,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Table for race results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            horse_name TEXT,
            finishing_position INTEGER,
            margin TEXT,
            jockey_name TEXT,
            trainer_name TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Table for favorite performance analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorite_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            favorite_1_name TEXT,
            favorite_1_odds REAL,
            favorite_1_position INTEGER,
            favorite_2_name TEXT,
            favorite_2_odds REAL,
            favorite_2_position INTEGER,
            favorite_3_name TEXT,
            favorite_3_odds REAL,
            favorite_3_position INTEGER,
            favorites_placed INTEGER,
            total_favorites INTEGER,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database setup complete")
    
    def get_race_odds_from_odds_com(self, race_url):
        """Scrape odds from odds.com.au for a specific race"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(race_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for odds data in JavaScript
            script_tags = soup.find_all('script')
            odds_data = []
            
            for script in script_tags:
                if script.string and 'odds' in script.string.lower():
                    # Try to extract odds data from JavaScript
                    content = script.string
                    
                    # Look for patterns like "odds": 3.5
                    odds_pattern = r'"odds":\s*(\d+\.?\d*)'
                    horse_pattern = r'"name":\s*"([^"]+)"'
                    
                    odds_matches = re.findall(odds_pattern, content)
                    horse_matches = re.findall(horse_pattern, content)
                    
                    if odds_matches and horse_matches:
                        for i, (horse, odds) in enumerate(zip(horse_matches, odds_matches)):
                            if i < len(odds_matches):
                                odds_data.append({
                                    'horse_name': horse,
                                    'odds': float(odds)
                                })
            
            # If no JavaScript data, try to find odds in HTML
            if not odds_data:
                odds_elements = soup.find_all(['div', 'span'], class_=re.compile(r'odds|price'))
                for element in odds_elements:
                    text = element.get_text().strip()
                    if re.match(r'^\d+\.?\d*$', text):
                        # Try to find associated horse name
                        parent = element.parent
                        if parent:
                            horse_name = parent.get_text().strip()
                            if horse_name and not re.match(r'^\d+\.?\d*$', horse_name):
                                odds_data.append({
                                    'horse_name': horse_name,
                                    'odds': float(text)
                                })
            
            return odds_data
            
        except Exception as e:
            logging.error(f"Error scraping odds from {race_url}: {e}")
            return []
    
    def get_race_results_from_racing_com(self, race_url):
        """Scrape race results from racing.com or similar site"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(race_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            results = []
            
            # Look for results table or div
            results_table = soup.find('table', class_=re.compile(r'result|finish'))
            if results_table:
                rows = results_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        position = cells[0].get_text().strip()
                        horse_name = cells[1].get_text().strip()
                        jockey = cells[2].get_text().strip() if len(cells) > 2 else ""
                        
                        if position.isdigit():
                            results.append({
                                'position': int(position),
                                'horse_name': horse_name,
                                'jockey_name': jockey
                            })
            
            return results
            
        except Exception as e:
            logging.error(f"Error scraping results from {race_url}: {e}")
            return []
    
    def scrape_todays_races(self):
        """Scrape today's races and identify favorites"""
        today = datetime.now().strftime('%Y-%m-%d')
        logging.info(f"Scraping races for {today}")
        
        # Get race URLs from odds.com.au
        main_url = "https://www.odds.com.au/horse-racing/"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(main_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find race links
            race_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/horse-racing/' in href and today.replace('-', '') in href:
                    race_links.append(href)
            
            logging.info(f"Found {len(race_links)} race links for today")
            
            # Process each race
            for race_url in race_links[:20]:  # Limit to first 20 races
                try:
                    self.process_race(race_url, today)
                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logging.error(f"Error processing race {race_url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error scraping main page: {e}")
    
    def process_race(self, race_url, race_date):
        """Process a single race to get favorites"""
        try:
            # Extract venue and race info from URL
            url_parts = race_url.split('/')
            venue = url_parts[-2] if len(url_parts) > 1 else "Unknown"
            race_name = url_parts[-1] if len(url_parts) > 0 else "Unknown"
            
            # Try to extract race number
            race_number = 1
            race_match = re.search(r'race-(\d+)', race_url)
            if race_match:
                race_number = int(race_match.group(1))
            
            # Get odds data
            odds_data = self.get_race_odds_from_odds_com(race_url)
            
            if not odds_data:
                logging.warning(f"No odds data found for {race_url}")
                return
            
            # Sort by odds to get favorites
            odds_data.sort(key=lambda x: x['odds'])
            favorites = odds_data[:3]  # Top 3 favorites
            
            # Get additional horse details from Betfair database
            conn = sqlite3.connect('/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite')
            
            for i, favorite in enumerate(favorites):
                horse_name = favorite['horse_name']
                odds = favorite['odds']
                
                # Try to get horse details from Betfair
                query = '''
                SELECT 
                    RUNNER_NAME,
                    JOCKEY_NAME,
                    TRAINER_NAME,
                    STALL_DRAW,
                    WEIGHT_VALUE,
                    FORM
                FROM HorseMarketBook 
                WHERE RUNNER_NAME LIKE ? AND EventName LIKE ?
                LIMIT 1
                '''
                
                cursor = conn.cursor()
                cursor.execute(query, (f'%{horse_name}%', f'%{race_date}%'))
                horse_details = cursor.fetchone()
                
                if horse_details:
                    # Save favorite to database
                    self.save_favorite(
                        race_date, venue, race_number, race_name,
                        horse_details[0], horse_details[1], horse_details[2],
                        horse_details[3], horse_details[4], horse_details[5],
                        odds, i + 1
                    )
                    logging.info(f"Saved favorite {i+1}: {horse_details[0]} at {odds}")
                else:
                    # Save with limited info
                    self.save_favorite(
                        race_date, venue, race_number, race_name,
                        horse_name, "Unknown", "Unknown",
                        0, 0, "Unknown",
                        odds, i + 1
                    )
                    logging.info(f"Saved favorite {i+1}: {horse_name} at {odds} (limited info)")
            
            conn.close()
            
        except Exception as e:
            logging.error(f"Error processing race {race_url}: {e}")
    
    def save_favorite(self, race_date, venue, race_number, race_name, 
                     horse_name, jockey_name, trainer_name, barrier, weight, form, odds, rank):
        """Save favorite to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO race_favorites 
        (race_date, venue, race_number, race_name, horse_name, jockey_name, 
         trainer_name, barrier, weight, form, odds, favorite_rank)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (race_date, venue, race_number, race_name, horse_name, jockey_name,
              trainer_name, barrier, weight, form, odds, rank))
        
        conn.commit()
        conn.close()
    
    def check_race_results(self):
        """Check for race results and update performance"""
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get races from last 2 days that don't have results yet
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT DISTINCT race_date, venue, race_number, race_name
        FROM race_favorites 
        WHERE race_date IN (?, ?)
        AND NOT EXISTS (
            SELECT 1 FROM race_results 
            WHERE race_results.race_date = race_favorites.race_date
            AND race_results.venue = race_favorites.venue
            AND race_results.race_number = race_favorites.race_number
        )
        ''', (today, yesterday))
        
        races_to_check = cursor.fetchall()
        conn.close()
        
        logging.info(f"Checking results for {len(races_to_check)} races")
        
        for race_date, venue, race_number, race_name in races_to_check:
            try:
                self.get_race_results(race_date, venue, race_number, race_name)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logging.error(f"Error getting results for {venue} R{race_number}: {e}")
    
    def get_race_results(self, race_date, venue, race_number, race_name):
        """Get results for a specific race"""
        # Try multiple sources for results
        result_sources = [
            f"https://www.racing.com/results/{race_date}/{venue.lower()}/race-{race_number}",
            f"https://www.racingpost.com/results/{race_date}/{venue.lower()}/race-{race_number}",
            f"https://www.skysports.com/racing/results/{race_date}/{venue.lower()}/race-{race_number}"
        ]
        
        for source_url in result_sources:
            try:
                results = self.get_race_results_from_racing_com(source_url)
                if results:
                    self.save_race_results(race_date, venue, race_number, race_name, results)
                    logging.info(f"Found results for {venue} R{race_number}")
                    return
            except Exception as e:
                logging.debug(f"Failed to get results from {source_url}: {e}")
                continue
        
        logging.warning(f"No results found for {venue} R{race_number}")
    
    def save_race_results(self, race_date, venue, race_number, race_name, results):
        """Save race results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for result in results:
            cursor.execute('''
            INSERT INTO race_results 
            (race_date, venue, race_number, race_name, horse_name, finishing_position, jockey_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (race_date, venue, race_number, race_name, 
                  result['horse_name'], result['position'], result['jockey_name']))
        
        conn.commit()
        conn.close()
    
    def analyze_favorite_performance(self):
        """Analyze how favorites performed"""
        conn = sqlite3.connect(self.db_path)
        
        # Get races with both favorites and results
        query = '''
        SELECT 
            f.race_date,
            f.venue,
            f.race_number,
            f.horse_name as favorite_1_name,
            f.odds as favorite_1_odds,
            r1.finishing_position as favorite_1_position,
            f2.horse_name as favorite_2_name,
            f2.odds as favorite_2_odds,
            r2.finishing_position as favorite_2_position,
            f3.horse_name as favorite_3_name,
            f3.odds as favorite_3_odds,
            r3.finishing_position as favorite_3_position
        FROM race_favorites f
        LEFT JOIN race_favorites f2 ON f.race_date = f2.race_date 
            AND f.venue = f2.venue 
            AND f.race_number = f2.race_number 
            AND f2.favorite_rank = 2
        LEFT JOIN race_favorites f3 ON f.race_date = f3.race_date 
            AND f.venue = f3.venue 
            AND f.race_number = f3.race_number 
            AND f3.favorite_rank = 3
        LEFT JOIN race_results r1 ON f.race_date = r1.race_date 
            AND f.venue = r1.venue 
            AND f.race_number = r1.race_number 
            AND f.horse_name = r1.horse_name
        LEFT JOIN race_results r2 ON f2.race_date = r2.race_date 
            AND f2.venue = r2.venue 
            AND f2.race_number = r2.race_number 
            AND f2.horse_name = r2.horse_name
        LEFT JOIN race_results r3 ON f3.race_date = r3.race_date 
            AND f3.venue = r3.venue 
            AND f3.race_number = r3.race_number 
            AND f3.horse_name = r3.horse_name
        WHERE f.favorite_rank = 1
        AND (r1.finishing_position IS NOT NULL OR r2.finishing_position IS NOT NULL OR r3.finishing_position IS NOT NULL)
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) == 0:
            logging.info("No completed races with results yet")
            return
        
        # Analyze performance
        total_races = len(df)
        favorites_placed = 0
        total_favorites = 0
        
        for _, race in df.iterrows():
            race_favorites_placed = 0
            race_total_favorites = 0
            
            # Check each favorite
            for i in range(1, 4):
                favorite_name = race[f'favorite_{i}_name']
                favorite_position = race[f'favorite_{i}_position']
                
                if pd.notna(favorite_name):
                    race_total_favorites += 1
                    if pd.notna(favorite_position) and favorite_position <= 3:
                        race_favorites_placed += 1
            
            favorites_placed += race_favorites_placed
            total_favorites += race_total_favorites
        
        # Calculate statistics
        place_rate = (favorites_placed / total_favorites * 100) if total_favorites > 0 else 0
        
        logging.info(f"\n=== FAVORITE PERFORMANCE ANALYSIS ===")
        logging.info(f"Total races analyzed: {total_races}")
        logging.info(f"Total favorites: {total_favorites}")
        logging.info(f"Favorites placed (1st-3rd): {favorites_placed}")
        logging.info(f"Place rate: {place_rate:.1f}%")
        
        # Save analysis
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for _, race in df.iterrows():
            cursor.execute('''
            INSERT INTO favorite_performance 
            (race_date, venue, race_number, favorite_1_name, favorite_1_odds, favorite_1_position,
             favorite_2_name, favorite_2_odds, favorite_2_position,
             favorite_3_name, favorite_3_odds, favorite_3_position,
             favorites_placed, total_favorites)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (race['race_date'], race['venue'], race['race_number'],
                  race['favorite_1_name'], race['favorite_1_odds'], race['favorite_1_position'],
                  race['favorite_2_name'], race['favorite_2_odds'], race['favorite_2_position'],
                  race['favorite_3_name'], race['favorite_3_odds'], race['favorite_3_position'],
                  race_favorites_placed, race_total_favorites))
        
        conn.commit()
        conn.close()
        
        return place_rate
    
    def run_tracking(self, days=3):
        """Run the tracking system for specified days"""
        logging.info(f"Starting favorite tracking for {days} days")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(days=days)
        
        while datetime.now() < end_time:
            try:
                # Scrape today's races for favorites
                self.scrape_todays_races()
                
                # Check for race results
                self.check_race_results()
                
                # Analyze performance
                self.analyze_favorite_performance()
                
                # Wait 30 minutes before next check
                logging.info("Waiting 30 minutes before next check...")
                time.sleep(1800)  # 30 minutes
                
            except KeyboardInterrupt:
                logging.info("Tracking stopped by user")
                break
            except Exception as e:
                logging.error(f"Error in tracking loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
        
        logging.info("Tracking completed")

def main():
    tracker = FavoriteTracker()
    
    print("🏇 FAVORITE TRACKING SYSTEM")
    print("=" * 50)
    print("This will track the 3 horses with lowest odds in each race")
    print("and monitor their actual finishing positions over 2-3 days")
    print()
    
    # Run for 3 days
    tracker.run_tracking(days=3)

if __name__ == "__main__":
    main()
