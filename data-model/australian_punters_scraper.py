import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import time
import re
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin, urlparse
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('australian_punters_scraper.log'),
        logging.StreamHandler()
    ]
)

class AustralianPuntersScraper:
    def __init__(self):
        self.base_url = "https://www.punters.com.au"
        self.results_url = "https://www.punters.com.au/racing-results/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        # Database path - using your main database
        self.db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
        
        # Australian racing venues (major tracks)
        self.australian_venues = [
            'Flemington', 'Caulfield', 'Moonee Valley', 'Sandown', 'Mornington',
            'Randwick', 'Rosehill', 'Warwick Farm', 'Canterbury', 'Kembla Grange',
            'Newcastle', 'Gosford', 'Wyong', 'Hawkesbury', 'Kembla Grange',
            'Eagle Farm', 'Doomben', 'Gold Coast', 'Sunshine Coast', 'Ipswich',
            'Toowoomba', 'Rockhampton', 'Townsville', 'Cairns', 'Mackay',
            'Morphettville', 'Murray Bridge', 'Gawler', 'Port Augusta', 'Bordertown',
            'Ascot', 'Bunbury', 'Kalgoorlie', 'Geraldton',
            'Hobart', 'Launceston', 'Devonport', 'Spreyton', 'Longford',
            'Alice Springs', 'Darwin', 'Katherine', 'Tennant Creek',
            'Wagga Wagga', 'Albury', 'Goulburn', 'Canberra', 'Queanbeyan',
            'Ballarat', 'Bendigo', 'Geelong', 'Warrnambool', 'Hamilton',
            'Mildura', 'Swan Hill', 'Echuca', 'Kilmore', 'Pakenham',
            'Cranbourne', 'Sale', 'Traralgon', 'Bairnsdale', 'Moe',
            # Adding missing venues
            'Northam', 'Bathurst', 'Coffs Harbour'
        ]
        
        self.setup_database()
        
    def setup_database(self):
        """Create database tables for storing Australian racing results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for Australian race results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS australian_punters_race_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            race_distance TEXT,
            race_class TEXT,
            race_prize_money TEXT,
            track_condition TEXT,
            weather TEXT,
            horse_name TEXT,
            horse_number INTEGER,
            jockey_name TEXT,
            trainer_name TEXT,
            barrier INTEGER,
            weight REAL,
            finishing_position INTEGER,
            margin TEXT,
            starting_price REAL,
            last_600m_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Table for Australian race metadata
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS australian_punters_race_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            race_distance TEXT,
            race_class TEXT,
            race_prize_money TEXT,
            track_condition TEXT,
            weather TEXT,
            total_runners INTEGER,
            race_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Australian racing database setup complete")
    
    def is_australian_venue(self, venue_name):
        """Check if venue is Australian"""
        if not venue_name:
            return False
        
        venue_clean = venue_name.strip().lower()
        
        # First check for US/International exclusions
        us_exclusions = [
            'belmont at the big a', 'belmont park', 'churchill downs', 'delaware park',
            'monmouth park', 'gulfstream', 'laurel park', 'los alamitos', 'hawthorne',
            'mountaineer', 'woodbine', 'prairie meadows', 'nakayama', 'hanshin',
            'tokyo', 'kyoto', 'sapporo', 'hakodate', 'niigata', 'fukushima',
            'newmarket', 'ascot', 'epsom', 'goodwood', 'york', 'doncaster',
            'leopardstown', 'curragh', 'fairyhouse', 'punchestown'
        ]
        
        for exclusion in us_exclusions:
            if exclusion in venue_clean:
                return False
        
        # Check against known Australian venues
        for aus_venue in self.australian_venues:
            if aus_venue.lower() in venue_clean:
                return True
        
        # Additional checks for Australian patterns
        australian_patterns = [
            r'\b(nsw|vic|qld|sa|wa|tas|nt|act)\b',  # State abbreviations
            r'\b(australia|australian)\b',
            r'\b(sydney|melbourne|brisbane|perth|adelaide|hobart|darwin)\b'
        ]
        
        for pattern in australian_patterns:
            if re.search(pattern, venue_clean):
                return True
        
        return False
    
    def get_page(self, url, retries=3):
        """Get page content with retry logic"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logging.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logging.error(f"Failed to get {url} after {retries} attempts")
                    return None
    
    def parse_australian_race_results(self, url):
        """Parse Australian race results from the main results page"""
        logging.info(f"Parsing Australian race results from: {url}")
        
        response = self.get_page(url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        australian_races = []
        
        try:
            # First, find all Australian venue links
            australian_venue_links = self.find_australian_venue_links(soup, url)
            logging.info(f"Found {len(australian_venue_links)} Australian venue links")
            
            # Visit each venue page to get race results
            for venue_name, venue_url in australian_venue_links:
                logging.info(f"Scraping venue: {venue_name}")
                venue_races = self.scrape_venue_page(venue_url, venue_name)
                australian_races.extend(venue_races)
            
            # Also check the main page for any Australian races
            race_tables = soup.find_all('table', class_=re.compile(r'results-table'))
            logging.info(f"Found {len(race_tables)} race tables on main page")
            
            for table in race_tables:
                race_data = self.parse_race_table(table)
                if race_data and self.is_australian_venue(race_data['venue']):
                    australian_races.append(race_data)
                    logging.info(f"✅ Australian race found on main page: {race_data['venue']} Race {race_data['race_number']}")
                elif race_data:
                    logging.info(f"❌ Non-Australian race skipped: {race_data['venue']} Race {race_data['race_number']}")
            
        except Exception as e:
            logging.error(f"Error parsing Australian results page {url}: {e}")
        
        return australian_races
    
    def find_australian_venue_links(self, soup, base_url):
        """Find all Australian venue links on the main results page"""
        venue_links = []
        
        # Look for links with class 'label-link' that contain Australian venue names
        links = soup.find_all('a', class_='label-link')
        
        for link in links:
            venue_name = link.get_text().strip()
            venue_url = link.get('href')
            
            if venue_url and self.is_australian_venue(venue_name):
                # Convert relative URL to absolute URL
                if venue_url.startswith('/'):
                    venue_url = self.base_url + venue_url
                
                venue_links.append((venue_name, venue_url))
                logging.info(f"Found Australian venue link: {venue_name} -> {venue_url}")
        
        return venue_links
    
    def scrape_venue_page(self, venue_url, venue_name):
        """Scrape race results from a specific venue page"""
        logging.info(f"Scraping venue page: {venue_url}")
        
        response = self.get_page(venue_url)
        if not response:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        venue_races = []
        
        try:
            # Find all race tables on the venue page
            race_tables = soup.find_all('table', class_=re.compile(r'results-table'))
            logging.info(f"Found {len(race_tables)} race tables on {venue_name} page")
            
            for table in race_tables:
                race_data = self.parse_race_table(table)
                if race_data:
                    # Override venue name with the actual venue name
                    race_data['venue'] = venue_name
                    venue_races.append(race_data)
                    logging.info(f"✅ Found race: {venue_name} Race {race_data['race_number']}")
            
        except Exception as e:
            logging.error(f"Error scraping venue page {venue_url}: {e}")
        
        return venue_races
    
    def parse_race_table(self, table):
        """Parse individual race table"""
        try:
            race_data = {
                'race_date': datetime.now().strftime('%Y-%m-%d'),
                'venue': '',
                'race_number': 0,
                'race_name': '',
                'race_distance': '',
                'race_class': '',
                'race_prize_money': '',
                'track_condition': '',
                'weather': '',
                'runners': []
            }
            
            # Extract race header information
            header = table.find('thead')
            if header:
                header_cell = header.find('th')
                if header_cell:
                    header_text = header_cell.get_text().strip()
                    
                    # Parse venue and race number
                    if ' - Race ' in header_text:
                        parts = header_text.split(' - Race ')
                        race_data['venue'] = parts[0].strip()
                        race_number_text = parts[1].split()[0]
                        try:
                            race_data['race_number'] = int(race_number_text)
                        except:
                            race_data['race_number'] = 1
                    
                    # Extract race name
                    race_name_elem = header_cell.find('b')
                    if race_name_elem:
                        race_data['race_name'] = race_name_elem.get_text().strip()
            
            # Check if this is a "no results" table
            if 'no-results' in table.get('class', []):
                return None
            
            # Parse runner rows
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                
                for i, row in enumerate(rows, 1):
                    runner_data = self.parse_runner_row(row, i)
                    if runner_data:
                        race_data['runners'].append(runner_data)
            
            # Only return if we have runners
            if race_data['runners']:
                return race_data
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error parsing race table: {e}")
            return None
    
    def parse_runner_row(self, row, position):
        """Parse runner data from table row"""
        try:
            cells = row.find_all('td')
            if len(cells) < 3:
                return None
            
            runner_data = {
                'horse_name': '',
                'horse_number': 0,
                'jockey_name': '',
                'trainer_name': '',
                'barrier': 0,
                'weight': 0.0,
                'finishing_position': position,
                'margin': '',
                'starting_price': 0.0,
                'last_600m_time': ''
            }
            
            # Extract horse name and number (usually first cell)
            horse_cell = cells[0]
            if horse_cell:
                horse_link = horse_cell.find('a')
                if horse_link:
                    runner_data['horse_name'] = horse_link.get_text().strip()
                
                cell_text = horse_cell.get_text()
                number_match = re.search(r'(\d+)', cell_text)
                if number_match:
                    runner_data['horse_number'] = int(number_match.group(1))
            
            # Extract jockey (usually second cell)
            if len(cells) > 1:
                jockey_cell = cells[1]
                jockey_link = jockey_cell.find('a')
                if jockey_link:
                    runner_data['jockey_name'] = jockey_link.get_text().strip()
            
            # Extract trainer (usually third cell)
            if len(cells) > 2:
                trainer_cell = cells[2]
                trainer_link = trainer_cell.find('a')
                if trainer_link:
                    runner_data['trainer_name'] = trainer_link.get_text().strip()
            
            # Extract weight
            for cell in cells:
                cell_text = cell.get_text()
                if 'kg' in cell_text:
                    weight_match = re.search(r'(\d+\.?\d*)\s*kg', cell_text)
                    if weight_match:
                        runner_data['weight'] = float(weight_match.group(1))
                        break
            
            # Extract starting price
            for cell in cells:
                cell_text = cell.get_text()
                if '$' in cell_text or 'SP' in cell_text:
                    price_match = re.search(r'(\d+\.?\d*)', cell_text)
                    if price_match:
                        runner_data['starting_price'] = float(price_match.group(1))
                        break
            
            return runner_data
            
        except Exception as e:
            logging.error(f"Error parsing runner row: {e}")
            return None
    
    def save_australian_race_results(self, race_data):
        """Save Australian race results to database"""
        if not race_data or not race_data['runners']:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Save race metadata
            cursor.execute('''
            INSERT OR REPLACE INTO australian_punters_race_metadata 
            (race_date, venue, race_number, race_name, race_distance, race_class, 
             race_prize_money, track_condition, weather, total_runners)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                race_data['race_date'],
                race_data['venue'],
                race_data['race_number'],
                race_data['race_name'],
                race_data['race_distance'],
                race_data['race_class'],
                race_data['race_prize_money'],
                race_data['track_condition'],
                race_data['weather'],
                len(race_data['runners'])
            ))
            
            # Save individual runner results
            for runner in race_data['runners']:
                cursor.execute('''
                INSERT OR REPLACE INTO australian_punters_race_results 
                (race_date, venue, race_number, race_name, race_distance, race_class,
                 race_prize_money, track_condition, weather, horse_name, horse_number,
                 jockey_name, trainer_name, barrier, weight, finishing_position,
                 margin, starting_price, last_600m_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    race_data['race_date'],
                    race_data['venue'],
                    race_data['race_number'],
                    race_data['race_name'],
                    race_data['race_distance'],
                    race_data['race_class'],
                    race_data['race_prize_money'],
                    race_data['track_condition'],
                    race_data['weather'],
                    runner['horse_name'],
                    runner['horse_number'],
                    runner['jockey_name'],
                    runner['trainer_name'],
                    runner['barrier'],
                    runner['weight'],
                    runner['finishing_position'],
                    runner['margin'],
                    runner['starting_price'],
                    runner['last_600m_time']
                ))
            
            conn.commit()
            logging.info(f"Saved Australian race: {race_data['venue']} Race {race_data['race_number']} - {len(race_data['runners'])} runners")
            
        except Exception as e:
            logging.error(f"Error saving Australian race results: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def scrape_australian_results(self, target_date=None):
        """Scrape Australian race results only"""
        if target_date is None:
            # Default to yesterday
            from datetime import datetime, timedelta
            target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Construct URL for specific date
        results_url = f"{self.results_url}?date={target_date}"
        logging.info(f"Scraping Australian horse racing results from Punters.com.au for {target_date}")
        
        races = self.parse_australian_race_results(results_url)
        
        if not races:
            logging.warning("No Australian races found on results page")
            return
        
        logging.info(f"Found {len(races)} Australian races to process")
        
        for race in races:
            self.save_australian_race_results(race)
            time.sleep(1)  # Rate limiting
    
    def get_australian_results_summary(self):
        """Get summary of Australian racing results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total Australian races
        cursor.execute("SELECT COUNT(DISTINCT race_date || venue || race_number) FROM australian_punters_race_results")
        total_races = cursor.fetchone()[0]
        
        # Get total runners
        cursor.execute("SELECT COUNT(*) FROM australian_punters_race_results")
        total_runners = cursor.fetchone()[0]
        
        # Get date range
        cursor.execute("SELECT MIN(race_date), MAX(race_date) FROM australian_punters_race_results")
        date_range = cursor.fetchone()
        
        # Get Australian venues
        cursor.execute("SELECT DISTINCT venue FROM australian_punters_race_results ORDER BY venue")
        venues = [row[0] for row in cursor.fetchall()]
        
        # Get races by state
        cursor.execute('''
        SELECT 
            CASE 
                WHEN venue LIKE '%Flemington%' OR venue LIKE '%Caulfield%' OR venue LIKE '%Moonee Valley%' OR venue LIKE '%Sandown%' THEN 'VIC'
                WHEN venue LIKE '%Randwick%' OR venue LIKE '%Rosehill%' OR venue LIKE '%Warwick Farm%' OR venue LIKE '%Canterbury%' THEN 'NSW'
                WHEN venue LIKE '%Eagle Farm%' OR venue LIKE '%Doomben%' OR venue LIKE '%Gold Coast%' THEN 'QLD'
                WHEN venue LIKE '%Morphettville%' OR venue LIKE '%Murray Bridge%' THEN 'SA'
                WHEN venue LIKE '%Ascot%' OR venue LIKE '%Belmont%' THEN 'WA'
                WHEN venue LIKE '%Hobart%' OR venue LIKE '%Launceston%' THEN 'TAS'
                WHEN venue LIKE '%Alice Springs%' OR venue LIKE '%Darwin%' THEN 'NT'
                ELSE 'Other'
            END as state,
            COUNT(DISTINCT race_date || venue || race_number) as race_count
        FROM australian_punters_race_results 
        GROUP BY state
        ORDER BY race_count DESC
        ''')
        state_stats = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_races': total_races,
            'total_runners': total_runners,
            'date_range': date_range,
            'venues': venues,
            'state_stats': state_stats
        }

def main():
    scraper = AustralianPuntersScraper()
    
    print("🇦🇺 AUSTRALIAN HORSE RACING RESULTS SCRAPER")
    print("=" * 60)
    print("Focusing on Australian venues only")
    print()
    
    # Scrape Australian results for yesterday
    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Scraping Australian horse racing results for {yesterday}...")
    scraper.scrape_australian_results(yesterday)
    
    # Show summary
    summary = scraper.get_australian_results_summary()
    print(f"\n📊 AUSTRALIAN RACING SUMMARY:")
    print(f"Total Australian races: {summary['total_races']}")
    print(f"Total runners: {summary['total_runners']}")
    print(f"Date range: {summary['date_range'][0]} to {summary['date_range'][1]}")
    print(f"Australian venues: {', '.join(summary['venues'][:10])}{'...' if len(summary['venues']) > 10 else ''}")
    
    print(f"\n🏁 RACES BY STATE:")
    for state, count in summary['state_stats']:
        print(f"  {state}: {count} races")

if __name__ == "__main__":
    main()
