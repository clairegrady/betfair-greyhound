"""
Harness Race Times Scraper - Gets harness racing (pace and trots) race start times from Racing and Sports
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import logging
import re
import sqlite3
from typing import List, Dict
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HarnessRaceTimesScraper:
    """
    Scrapes harness racing (pace and trots) race start times from Racenet.com.au
    """
    
    def __init__(self, db_path: str = None):
        self.base_url = "https://www.racenet.com.au"
        self.db_path = db_path or "/Users/clairegrady/RiderProjects/betfair/data-model/live_betting.sqlite"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Timezone mapping for harness racing venues
        self.venue_timezones = {
            # Australian harness racing venues
            'Albion Park': 'Australia/Brisbane',
            'Bendigo': 'Australia/Melbourne',
            'Globe Derby': 'Australia/Adelaide',
            'Harold Park': 'Australia/Sydney',
            'Menangle': 'Australia/Sydney',
            'Melton': 'Australia/Melbourne',
            'Moonee Valley': 'Australia/Melbourne',
            'Redcliffe': 'Australia/Brisbane',
            'Shepparton': 'Australia/Melbourne',
            'Tabcorp Park': 'Australia/Melbourne',
            'Trots': 'Australia/Melbourne',
            'Wagga': 'Australia/Sydney',
        }
        
        self._create_race_times_table()
    
    def _get_country_from_venue(self, venue):
        """Determine country from venue name based on timezone"""
        timezone = self.venue_timezones.get(venue, 'UTC')
        
        if 'Australia' in timezone:
            return 'AUS'
        else:
            return 'UNKNOWN'
    
    def _create_race_times_table(self):
        """Create race_times table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS race_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venue TEXT NOT NULL,
                race_number INTEGER NOT NULL,
                race_time TEXT NOT NULL,
                race_time_utc TEXT NOT NULL,
                race_date TEXT NOT NULL,
                timezone TEXT NOT NULL,
                country TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(venue, race_number, race_date)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Race times table created/verified")
    
    def convert_time_for_display(self, time_str: str) -> str:
        """Convert time for display purposes (same logic as convert_time but returns string)"""
        try:
            # Handle absolute time format (HH:MM)
            if ':' in time_str and not any(x in time_str.lower() for x in ['h', 'm', 's']):
                hour, minute = time_str.split(':')
                hour = int(hour)
                minute = int(minute)
                
                # Fix time conversion: if first digit is 0, make it 1; if it's 1, make it 2
                if hour < 10:  # First digit is 0
                    hour += 10  # 0X becomes 1X
                elif hour < 20:  # First digit is 1
                    hour += 10  # 1X becomes 2X
                
                if hour >= 24:
                    hour -= 24
                
                return f"{hour:02d}:{minute:02d}"
            
            return time_str
        except Exception as e:
            return time_str

    def convert_to_utc(self, venue: str, race_date: str, race_time: str) -> tuple:
        """
        Handle date assignment based on race time and venue
        
        Returns:
            tuple: (time_str, date_str, timezone_str)
        """
        from datetime import timedelta
        original_date = datetime.strptime(race_date, '%Y-%m-%d')
        
        # If race time starts with 00, 01, 02, or 03, it's tomorrow's race in AEST
        if race_time.startswith(('00:', '01:', '02:', '03:')):
            next_date = original_date + timedelta(days=1)
            return race_time, next_date.strftime('%Y-%m-%d'), 'Australia/Sydney'
        else:
            return race_time, race_date, 'Australia/Sydney'
    
    def save_race_times_to_db(self, races: List[Dict], date_str: str):
        """Save race times directly to database"""
        if not races:
            logger.warning("No races to save")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for race in races:
            try:
                # Convert to UTC
                utc_time, utc_date, timezone = self.convert_to_utc(
                    race['venue'], 
                    date_str, 
                    race['race_time_24h']
                )
                
                # Get country for this venue
                country = self._get_country_from_venue(race['venue'])
                
                cursor.execute("""
                    INSERT OR REPLACE INTO race_times 
                    (venue, race_number, race_time, race_time_utc, race_date, timezone, country, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    race['venue'], 
                    race['race_number'], 
                    race['race_time_24h'],  # Original local time
                    utc_time,  # UTC time
                    utc_date,  # UTC date (may be different if crossing midnight)
                    timezone,
                    country
                ))
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving race {race['venue']} R{race['race_number']}: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {saved_count} harness race times to database")
    
    def scrape_harness_race_times(self, date_str: str = None):
        """
        Scrape harness racing race times for a specific date
        
        Args:
            date_str: Date in YYYY-MM-DD format, defaults to today
            
        Returns:
            DataFrame with race times and details
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/form-guide/harness"
        logger.info(f"Scraping harness race times from: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            races = []
            
            # Look for harness racing specific elements
            # Try different selectors that might be used for harness racing
            harness_elements = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'harness|trot|pace|race', re.I))
            logger.info(f"Found {len(harness_elements)} potential harness racing elements")
            
            # Look for race links with harness-specific patterns
            race_links = soup.find_all('a', href=re.compile(r'harness|trot|pace'))
            logger.info(f"Found {len(race_links)} harness race links")
            
            for link in race_links:
                try:
                    text = link.get_text().strip()
                    href = link.get('href', '')
                    
                    # Look for race patterns in the text
                    if 'R' in text and any(char.isdigit() for char in text):
                        # Extract race number
                        race_num_match = re.search(r'R(\d+)', text)
                        race_number = race_num_match.group(1) if race_num_match else 'Unknown'
                        
                        # Extract time
                        time_match = re.search(r'(\d{1,2}:\d{2})', text)
                        race_time = time_match.group(1) if time_match else 'Unknown'
                        
                        # Extract venue from href or text
                        venue_name = 'Unknown'
                        if '/harness/' in href:
                            # Try to extract venue from URL path
                            path_parts = href.split('/')
                            for part in path_parts:
                                if part and part not in ['harness', 'form-guide', '']:
                                    venue_name = part.replace('-', ' ').title()
                                    break
                        
                        if race_time != 'Unknown' and venue_name != 'Unknown' and race_number != 'Unknown':
                            race_data = {
                                'venue': venue_name,
                                'race_number': race_number,
                                'race_time': race_time,
                                'raw_text': text[:150]
                            }
                            races.append(race_data)
                            
                except Exception as e:
                    logger.warning(f"Error processing harness race link: {e}")
                    continue
            
            # Fallback parsing - look for harness racing patterns in page text
            logger.info("Running fallback parsing for harness racing")
            
            page_text = soup.get_text()
            lines = page_text.split('\n')
            
            for line in lines:
                line = line.strip()
                # Look for harness racing specific patterns
                if ('harness' in line.lower() or 'trot' in line.lower() or 'pace' in line.lower()) and 'R' in line and ':' in line:
                    time_match = re.search(r'(\d{1,2}:\d{2})', line)
                    race_num_match = re.search(r'R(\d+)', line)
                    
                    if time_match and race_num_match:
                        # Try to extract venue name
                        venue_name = 'Unknown'
                        venue_patterns = [
                            re.compile(r'(\w+(?:\s+\w+)*)\s+R\d+', re.IGNORECASE),
                            re.compile(r'(\w+)\s+R\d+', re.IGNORECASE),
                        ]
                        
                        for pattern in venue_patterns:
                            venue_match = pattern.search(line)
                            if venue_match:
                                venue_name = venue_match.group(1).strip()
                                break
                        
                        if venue_name != 'Unknown':
                            race_data = {
                                'venue': venue_name,
                                'race_number': race_num_match.group(1),
                                'race_time': time_match.group(1),
                                'raw_text': line[:150]
                            }
                            races.append(race_data)
            
            # Remove duplicates
            unique_races = []
            seen = set()
            for race in races:
                key = (race['venue'], race['race_number'], race['race_time'])
                if key not in seen:
                    seen.add(key)
                    unique_races.append(race)
            
            logger.info(f"Extracted {len(unique_races)} unique harness races")
            
            if unique_races:
                df = pd.DataFrame(unique_races)
                logger.info(f"Harness race times found:")
                for _, race in df.iterrows():
                    # Convert time for display
                    converted_time = self.convert_time_for_display(race['race_time'])
                    logger.info(f"  {race['venue']} R{race['race_number']} - {converted_time}")
                return df
            else:
                logger.warning("No harness race times found")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error scraping harness race times: {str(e)}")
            return pd.DataFrame()


def scrape_and_save_harness_race_times(date_str: str = None, save_to_csv: bool = False):
    """Scrape harness race times and save directly to database (and optionally to CSV)"""
    from datetime import datetime
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    scraper = HarnessRaceTimesScraper()
    df = scraper.scrape_harness_race_times(date_str)
    
    if not df.empty:
        # Clean up the data
        df = df[df['venue'] != 'Unknown']  # Remove races with unknown venues
        df = df[df['race_number'] != 'Unknown']  # Remove races with unknown numbers
        
        logger.info(f"Found {len(df)} harness races")
        
        # Convert times - handle both absolute and relative time formats
        from datetime import datetime, timedelta
        scrape_time = datetime.now()
        
        def convert_time(time_str):
            try:
                # Handle absolute time format (HH:MM)
                if ':' in time_str and not any(x in time_str.lower() for x in ['h', 'm', 's']):
                    hour, minute = time_str.split(':')
                    hour = int(hour)
                    minute = int(minute)
                    
                    # Fix time conversion: if first digit is 0, make it 1; if it's 1, make it 2
                    if hour < 10:  # First digit is 0
                        hour += 10  # 0X becomes 1X
                    elif hour < 20:  # First digit is 1
                        hour += 10  # 1X becomes 2X
                    
                    if hour >= 24:
                        hour -= 24
                    
                    return f"{hour:02d}:{minute:02d}"
                
                # Handle relative time format (Xh Ym, Ym Zs, etc.)
                elif any(x in time_str.lower() for x in ['h', 'm', 's']):
                    reference_time = scrape_time
                    
                    if time_str.startswith('-'):
                        return reference_time.strftime('%H:%M')
                    
                    hours = 0
                    minutes = 0
                    seconds = 0
                    
                    if 'h' in time_str.lower():
                        hour_part = time_str.lower().split('h')[0].split()[-1]
                        hours = int(hour_part)
                    
                    if 'm' in time_str.lower():
                        parts = time_str.lower().split()
                        for part in parts:
                            if 'm' in part and 'h' not in part:
                                minute_part = part.replace('m', '').replace('s', '')
                                if minute_part.isdigit():
                                    minutes = int(minute_part)
                                    break
                    
                    if 's' in time_str.lower() and 'm' not in time_str.lower():
                        sec_part = time_str.lower().split('s')[0].split()[-1]
                        seconds = int(sec_part)
                    
                    race_start = reference_time + timedelta(hours=hours, minutes=minutes, seconds=seconds)
                    return race_start.strftime('%H:%M')
                
                return time_str
            except Exception as e:
                print(f"Error converting time '{time_str}': {e}")
                return time_str
        
        df['race_time_24h'] = df['race_time'].apply(convert_time)
        df['date'] = date_str
        
        # Save to database
        races_list = df.to_dict('records')
        scraper.save_race_times_to_db(races_list, date_str)
        
        # Optionally save to CSV
        if save_to_csv:
            filename = f"harness_race_times_{date_str}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Also saved to CSV: {filename}")
        
        # Show summary
        logger.info(f"Harness race times summary for {date_str}:")
        df_sorted = df.sort_values(['race_time_24h', 'venue', 'race_number'])
        for _, race in df_sorted.head(10).iterrows():
            logger.info(f"  {race['venue']} R{race['race_number']} - {race['race_time_24h']}")
        
        # Also show venue summary
        logger.info(f"Harness venue summary:")
        for venue in df['venue'].unique():
            venue_races = df[df['venue'] == venue]
            logger.info(f"  {venue}: {len(venue_races)} races")
        
        return df
    else:
        logger.warning("No harness race times found to save")
        return pd.DataFrame()


def main():
    """Scrape harness race times and save directly to database"""
    # Test with today's date
    today = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"Scraping harness race times for {today}")
    
    # Scrape and save to database
    df = scrape_and_save_harness_race_times(today, save_to_csv=False)
    
    return df


if __name__ == "__main__":
    main()
