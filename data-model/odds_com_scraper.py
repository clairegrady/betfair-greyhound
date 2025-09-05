import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import logging
from datetime import datetime
import re
import json
from dataclasses import dataclass
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class RaceOdds:
    race_id: str
    venue: str
    race_number: str
    race_name: str
    race_time: str
    distance: str
    runner_name: str
    runner_number: str
    bookmaker: str
    odds: str
    odds_type: str
    scraped_at: datetime
    source: str

class OddsComScraper:
    def __init__(self, db_path: str = 'racing_data.db'):
        self.db_path = db_path
        self.setup_database()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def setup_database(self):
        """Create database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS odds_com_race_odds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT,
                venue TEXT,
                race_number TEXT,
                race_name TEXT,
                race_time TEXT,
                distance TEXT,
                runner_name TEXT,
                runner_number TEXT,
                bookmaker TEXT,
                odds TEXT,
                odds_type TEXT,
                scraped_at TIMESTAMP,
                source TEXT,
                UNIQUE(race_id, runner_name, bookmaker, source, scraped_at)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database setup complete")
    
    def get_race_links(self) -> List[Dict]:
        """Get race links from odds.com.au by first getting venues, then all races per venue"""
        url = "https://www.odds.com.au/horse-racing/"
        
        try:
            logger.info(f"Fetching race links from {url}")
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            race_links = []
            
            # First, get all venue URLs from the main page
            all_links = soup.find_all('a', href=True)
            horse_racing_links = [link for link in all_links if '/horse-racing/' in link.get('href')]
            
            venue_urls = set()
            for link in horse_racing_links:
                href = link.get('href')
                text = link.get_text(strip=True)
                
                # Skip obvious navigation links
                if href in ['/horse-racing/', '/horse-racing/news/', '/blog/horse-racing/']:
                    continue
                
                # Skip if text contains navigation keywords
                if any(keyword in text.lower() for keyword in ['racing news', 'news', 'blog']):
                    continue
                
                # Check if this looks like a venue URL (ends with date)
                if len(href.split('/')) > 2:
                    parts = href.split('/')
                    if len(parts) >= 3:
                        venue_date = parts[2]
                        
                        # Check if this looks like a venue-date URL
                        if '-' in venue_date and len(venue_date.split('-')) >= 2:
                            venue_parts = venue_date.split('-')
                            # Check if the last part looks like a date (8 digits)
                            if len(venue_parts[-1]) == 8 and venue_parts[-1].isdigit():
                                venue_url = href if href.startswith('http') else f"https://www.odds.com.au{href}"
                                venue_urls.add(venue_url)
            
            logger.info(f"Found {len(venue_urls)} venue URLs")
            
            # Now visit each venue page to get all races
            for venue_url in venue_urls:
                try:
                    logger.info(f"Fetching races from venue: {venue_url}")
                    venue_response = self.session.get(venue_url)
                    venue_response.raise_for_status()
                    
                    venue_soup = BeautifulSoup(venue_response.content, 'html.parser')
                    
                    # Extract venue name from URL
                    venue_parts = venue_url.split('/')
                    venue_date = venue_parts[-2] if venue_parts[-1] == '' else venue_parts[-1]
                    venue_name = venue_date.split('-')[0] if '-' in venue_date else 'Unknown'
                    
                    # Find all race links on this venue page
                    venue_links = venue_soup.find_all('a', href=True)
                    venue_race_links = [link for link in venue_links if '/horse-racing/' in link.get('href') and 'race-' in link.get('href')]
                    
                    for link in venue_race_links:
                        href = link.get('href')
                        text = link.get_text(strip=True)
                        
                        # Extract race number
                        race_number_match = re.search(r'race-(\d+)', href)
                        if race_number_match:
                            race_number = race_number_match.group(1)
                            
                            race_info = {
                                'url': href if href.startswith('http') else f"https://www.odds.com.au{href}",
                                'race_number': f"R{race_number}",
                                'race_name': text if text and len(text) > 3 else f"Race {race_number}",
                                'venue': venue_name.title()
                            }
                            race_links.append(race_info)
                    
                    # Add a small delay between venue requests
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error fetching races from venue {venue_url}: {e}")
                    continue
            
            logger.info(f"Found {len(race_links)} total race links")
            return race_links
            
        except Exception as e:
            logger.error(f"Error fetching race links: {e}")
            return []
    
    def scrape_race_odds_from_javascript(self, race_url: str) -> List[RaceOdds]:
        """Scrape odds for a specific race by extracting from JavaScript"""
        try:
            logger.info(f"Scraping odds from {race_url}")
            
            response = self.session.get(race_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract race information from URL and page
            race_info = self.extract_race_info_from_url(race_url)
            race_info = self.extract_race_info_from_page(soup, race_info)
            
            # Extract horses from the page text
            horses = self.extract_horses_from_page(soup)
            
            # Extract odds from JavaScript
            odds_data = self.extract_odds_from_javascript(soup, horses, race_info)
            
            logger.info(f"Scraped {len(odds_data)} odds entries for race")
            return odds_data
            
        except Exception as e:
            logger.error(f"Error scraping race odds from {race_url}: {e}")
            return []
    
    def extract_race_info_from_url(self, url: str) -> Dict:
        """Extract race information from URL"""
        race_info = {
            'race_id': url.split('/')[-2] if '/' in url else url,
            'venue': 'Unknown',
            'race_number': 'Unknown',
            'race_name': 'Unknown',
            'race_time': 'Unknown',
            'distance': 'Unknown'
        }
        
        # Extract venue and race details from URL
        # Handle both relative and absolute URLs
        if url.startswith('http'):
            # Remove protocol and domain
            url_path = url.replace('https://www.odds.com.au', '').replace('http://www.odds.com.au', '')
        else:
            url_path = url
        
        parts = url_path.split('/')
        parts = [p for p in parts if p]  # Remove empty parts
        
        if len(parts) >= 2:
            venue_date = parts[1]  # e.g., "rosehill-gardens-20250830"
            if venue_date and '-' in venue_date:
                venue_parts = venue_date.split('-')
                # Take all parts before the date (which should be 8 digits)
                venue_name_parts = []
                for part in venue_parts:
                    if part and len(part) == 8 and part.isdigit():
                        break
                    if part:  # Only add non-empty parts
                        venue_name_parts.append(part)
                if venue_name_parts:
                    race_info['venue'] = ' '.join(venue_name_parts).title()
            
            # Extract race number from the last part
            if len(parts) >= 3:
                race_part = parts[2]  # e.g., "bankstown-sports-bm78-race-3"
                # Look for race-X pattern
                race_match = re.search(r'race-(\d+)', race_part)
                if race_match:
                    race_info['race_number'] = f"R{race_match.group(1)}"
                
                # Extract race name from the URL part
                race_name_parts = race_part.split('-')
                if len(race_name_parts) > 1:
                    # Remove 'race-X' from the name
                    name_parts = [part for part in race_name_parts if not part.startswith('race')]
                    if name_parts:
                        race_info['race_name'] = ' '.join(name_parts).title()
        
        return race_info
    
    def extract_race_info_from_page(self, soup, race_info: Dict) -> Dict:
        """Extract additional race information from the page content"""
        try:
            # Look for race title/name in page
            title_elements = soup.find_all(['h1', 'h2', 'h3'])
            for element in title_elements:
                text = element.get_text(strip=True)
                if 'race' in text.lower() and len(text) > 10:
                    # Clean up the race name
                    race_name = text.replace('Betting Odds', '').replace('Horse Racing', '').strip()
                    if race_name and len(race_name) > 5:
                        race_info['race_name'] = race_name
                    break
            
            # Look for distance information
            all_text = soup.get_text()
            distance_match = re.search(r'(\d+)m', all_text)
            if distance_match:
                race_info['distance'] = f"{distance_match.group(1)}m"
            
            # Look for race time
            time_match = re.search(r'(\d{1,2}):(\d{2})', all_text)
            if time_match:
                race_info['race_time'] = f"{time_match.group(1)}:{time_match.group(2)}"
            
            return race_info
            
        except Exception as e:
            logger.error(f"Error extracting race info from page: {e}")
            return race_info
    
    def extract_horses_from_page(self, soup) -> List[Dict]:
        """Extract horse names and numbers from the page"""
        horses = []
        
        try:
            all_text = soup.get_text()
            
            # Look for horse patterns: "5. Doing Time", "9. No Joke Antares"
            horse_pattern = r'(\d+)\.\s+([A-Za-z\s]+?)(?=\s+\d+%|\s*$)'
            horse_matches = re.findall(horse_pattern, all_text)
            
            for match in horse_matches:
                horse_number = match[0]
                horse_name = match[1].strip()
                
                # Clean up horse name (remove extra spaces and special characters)
                horse_name = re.sub(r'\s+', ' ', horse_name).strip()
                
                if len(horse_name) > 2:  # Filter out very short names
                    horses.append({
                        'number': horse_number,
                        'name': horse_name
                    })
            
            horse_list = [f"{h['number']}. {h['name']}" for h in horses]
            logger.info(f"Found {len(horses)} horses: {horse_list}")
            return horses
            
        except Exception as e:
            logger.error(f"Error extracting horses: {e}")
            return []
    
    def extract_odds_from_javascript(self, soup, horses: List[Dict], race_info: Dict) -> List[RaceOdds]:
        """Extract odds from JavaScript data"""
        odds_data = []
        
        try:
            # Find all script tags
            scripts = soup.find_all('script')
            
            # First, extract the horse ID to name mapping
            horse_id_mapping = {}
            for script in scripts:
                script_text = script.get_text()
                
                # Look for the pattern: name:"Horse Name",selectionId:123456
                mapping_pattern = r'name:"([^"]+)",selectionId:(\d+)'
                mapping_matches = re.findall(mapping_pattern, script_text)
                
                for match in mapping_matches:
                    horse_name = match[0]
                    horse_id = match[1]
                    horse_id_mapping[horse_id] = horse_name
                    logger.info(f"Found mapping: {horse_id} -> {horse_name}")
            
            # Create a comprehensive horses list from JavaScript mapping
            js_horses = []
            for horse_id, horse_name in horse_id_mapping.items():
                # Try to find horse number from page text first
                horse_number = "Unknown"
                for horse in horses:
                    if horse['name'] == horse_name:
                        horse_number = horse['number']
                        break
                
                js_horses.append({
                    'id': horse_id,
                    'name': horse_name,
                    'number': horse_number
                })
            
            logger.info(f"Found {len(js_horses)} horses in JavaScript: {[h['name'] for h in js_horses]}")
            
            # Now extract odds and match them to horses using the mapping
            # First, try to find odds in the HTML content - specifically target the odds cells
            odds_elements = soup.find_all('div', class_='octd-right__odds-value-cell')
            html_odds = {}
            
            for element in odds_elements:
                text = element.get_text(strip=True)
                # Look for decimal odds patterns
                odds_match = re.search(r'(\d+\.?\d*)', text)
                if odds_match:
                    odds_value = odds_match.group(1)
                    try:
                        odds_float = float(odds_value)
                        if 1.0 <= odds_float <= 1000:
                            # Find the bookmaker from the bet sign element
                            bet_sign_element = element.find_previous('span', class_='octd-right__bet-sign')
                            bookmaker = bet_sign_element.get_text(strip=True) if bet_sign_element else 'Unknown'
                            
                            # Try to find the horse name in the parent elements
                            parent = element.parent
                            for _ in range(5):  # Look up to 5 levels up
                                if parent:
                                    parent_text = parent.get_text()
                                    for horse_name in [h['name'] for h in js_horses]:
                                        if horse_name.lower() in parent_text.lower():
                                            if horse_name not in html_odds:
                                                html_odds[horse_name] = []
                                            html_odds[horse_name].append({
                                                'odds': str(odds_float),
                                                'bookmaker': bookmaker,
                                                'source': 'html'
                                            })
                                            break
                                    parent = parent.parent
                    except:
                        pass
            
            # Now extract odds from JavaScript
            for script in scripts:
                script_text = script.get_text()
                
                # Look for the odds data pattern in JavaScript
                # Pattern: oddsKey:"20877711-Ubet-FixedWin",hasOdds:b,betUrl:L,odds:12,isBest:a
                odds_pattern = r'oddsKey:"(\d+)-([^-]+)-([^"]+)",[^}]*odds:([^,}]+)'
                odds_matches = re.findall(odds_pattern, script_text)
                
                if odds_matches:
                    logger.info(f"Found {len(odds_matches)} odds entries in JavaScript")
                    
                    # Group odds by horse ID (first part of oddsKey)
                    horse_odds = {}
                    for match in odds_matches:
                        horse_id = match[0]  # e.g., "20877711"
                        bookmaker = match[1]  # e.g., "Ubet"
                        bet_type = match[2]   # e.g., "FixedWin"
                        odds_value = match[3] # e.g., "12"
                        
                        if horse_id not in horse_odds:
                            horse_odds[horse_id] = []
                        
                        # Clean up odds value
                        try:
                            # First, try to convert directly to float (for numeric odds)
                            if odds_value.isdigit() or ('.' in odds_value and odds_value.replace('.', '').isdigit()):
                                odds_float = float(odds_value)
                                if 1.0 <= odds_float <= 1000:  # Reasonable odds range
                                    horse_odds[horse_id].append({
                                        'bookmaker': bookmaker.title(),
                                        'odds': str(odds_float),
                                        'bet_type': bet_type
                                    })
                            else:
                                # For encoded odds (like 'aC', 'bq', etc.), store them as-is
                                # We'll need to decode these later or handle them differently
                                horse_odds[horse_id].append({
                                    'bookmaker': bookmaker.title(),
                                    'odds': odds_value,  # Store encoded value
                                    'bet_type': bet_type,
                                    'encoded': True
                                })
                        except:
                            pass
                    
                    # Now match horses to odds using the correct mapping
                    for horse_id, odds_list in horse_odds.items():
                        if horse_id in horse_id_mapping:
                            horse_name = horse_id_mapping[horse_id]
                            
                            # Find the horse number from our comprehensive horses list
                            horse_number = "Unknown"
                            for horse in js_horses:
                                if horse['name'] == horse_name:
                                    horse_number = horse['number']
                                    break
                            
                            for odds_info in odds_list:
                                # Handle encoded odds - SKIP THEM, they're useless
                                odds_value = odds_info['odds']
                                if odds_info.get('encoded', False):
                                    # Skip encoded odds entirely - they're not usable
                                    logger.debug(f"  Skipping encoded odds: {horse_name} - {odds_info['bookmaker']}: {odds_value}")
                                    continue
                                
                                odds_obj = RaceOdds(
                                    race_id=race_info['race_id'],
                                    venue=race_info['venue'],
                                    race_number=race_info['race_number'],
                                    race_name=race_info['race_name'],
                                    race_time=race_info['race_time'],
                                    distance=race_info['distance'],
                                    runner_name=horse_name,
                                    runner_number=horse_number,
                                    bookmaker=odds_info['bookmaker'],
                                    odds=odds_value,
                                    odds_type=odds_info['bet_type'].lower(),
                                    scraped_at=datetime.now(),
                                    source='odds_com_au_javascript'
                                )
                                odds_data.append(odds_obj)
                                
                                logger.info(f"  {horse_name} - {odds_info['bookmaker']}: {odds_value}")
                    
                    # Also add HTML odds if we found any
                    for horse_name, html_odds_list in html_odds.items():
                        # Find the horse number
                        horse_number = "Unknown"
                        for horse in js_horses:
                            if horse['name'] == horse_name:
                                horse_number = horse['number']
                                break
                        
                        for odds_info in html_odds_list:
                            odds_obj = RaceOdds(
                                race_id=race_info['race_id'],
                                venue=race_info['venue'],
                                race_number=race_info['race_number'],
                                race_name=race_info['race_name'],
                                race_time=race_info['race_time'],
                                distance=race_info['distance'],
                                runner_name=horse_name,
                                runner_number=horse_number,
                                bookmaker=odds_info.get('bookmaker', 'Unknown'),
                                odds=odds_info['odds'],
                                odds_type='fixedwin',
                                scraped_at=datetime.now(),
                                source='odds_com_au_html'
                            )
                            odds_data.append(odds_obj)
                            
                            logger.info(f"  {horse_name} - {odds_info.get('bookmaker', 'Unknown')}: {odds_info['odds']}")
            
            return odds_data
            
        except Exception as e:
            logger.error(f"Error extracting odds from JavaScript: {e}")
            return []
    
    def save_odds_data(self, odds_data: List[RaceOdds]):
        """Save odds data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for odds in odds_data:
            cursor.execute('''
                INSERT OR IGNORE INTO odds_com_race_odds 
                (race_id, venue, race_number, race_name, race_time, distance, 
                 runner_name, runner_number, bookmaker, odds, odds_type, scraped_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                odds.race_id, odds.venue, odds.race_number, odds.race_name, 
                odds.race_time, odds.distance, odds.runner_name, odds.runner_number,
                odds.bookmaker, odds.odds, odds.odds_type, odds.scraped_at, odds.source
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(odds_data)} odds entries to database")
    
    def scrape_races_from_javascript(self, max_races: int = 2):
        """Scrape odds from multiple races using JavaScript extraction"""
        logger.info("Starting odds.com.au scraping")
        
        try:
            # Get race links
            race_links = self.get_race_links()
            
            if not race_links:
                logger.warning("No race links found")
                return
            
            logger.info(f"Found {len(race_links)} races to scrape")
            
            # Determine how many races to scrape
            races_to_scrape = race_links if max_races is None else race_links[:max_races]
            
            for i, race_link in enumerate(races_to_scrape):
                try:
                    race_name = race_link.get('race_name', 'Unknown Race')
                    logger.info(f"Scraping race {i+1}/{len(races_to_scrape)}: {race_name}")
                    odds_data = self.scrape_race_odds_from_javascript(race_link['url'])
                    
                    if odds_data:
                        self.save_odds_data(odds_data)
                    
                    time.sleep(2)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error scraping race {race_link['url']}: {e}")
                    continue
            
            self.show_results()
            
        except Exception as e:
            logger.error(f"Error in scraping process: {e}")
    
    def show_results(self):
        """Show scraping results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM odds_com_race_odds")
        total_odds = cursor.fetchone()[0]
        
        cursor.execute("SELECT DISTINCT runner_name, bookmaker, odds, odds_type FROM odds_com_race_odds ORDER BY runner_name LIMIT 15")
        sample_odds = cursor.fetchall()
        
        conn.close()
        
        print(f"\nOdds.com.au Scraping Results:")
        print(f"Total odds entries: {total_odds}")
        print(f"Sample odds:")
        for runner, bookmaker, odds, odds_type in sample_odds:
            print(f"  {runner} - {bookmaker}: {odds} ({odds_type})")

def main():
    """Main function"""
    scraper = OddsComScraper()
    scraper.scrape_races_from_javascript(max_races=1)  # Test with just 1 race  # Scrape all races

if __name__ == "__main__":
    main()
