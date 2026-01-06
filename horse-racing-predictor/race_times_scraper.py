"""
Race Times Scraper - Gets actual race start times from Racing and Sports
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


class RaceTimesScraper:
    """
    Scrapes actual race start times from Racenet.com.au and saves directly to database
    """
    
    def __init__(self, db_path: str = None):
        self.base_url = "https://www.racenet.com.au"
        self.db_path = db_path or "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/race_times.db"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Timezone mapping for venues
        self.venue_timezones = {
            # Australia - VIC
            'Bairnsdale': 'Australia/Melbourne',
            'Ballarat': 'Australia/Melbourne',
            'Bendigo': 'Australia/Melbourne',
            'Burrumbeet': 'Australia/Melbourne',
            'Colac': 'Australia/Melbourne',
            'Caulfield': 'Australia/Melbourne',
            'Cranbourne': 'Australia/Melbourne',
            'Flemington': 'Australia/Melbourne',
            'Geelong': 'Australia/Melbourne',
            'Gunbower': 'Australia/Melbourne',
            'Hamilton': 'Australia/Melbourne',
            'Hanging Rock': 'Australia/Melbourne',
            'Horsham': 'Australia/Melbourne',
            'Kerang': 'Australia/Melbourne',
            'Manangatang': 'Australia/Melbourne',
            'Merton': 'Australia/Melbourne',
            'Moonee Valley': 'Australia/Melbourne',
            'Murtoa': 'Australia/Melbourne',
            'Mornington': 'Australia/Melbourne',
            'Morphettville': 'Australia/Melbourne',
            'Pakenham': 'Australia/Melbourne',
            'Rosehill Gardens': 'Australia/Melbourne',
            'Sale': 'Australia/Melbourne',
            'Sandown Hillside': 'Australia/Melbourne',
            'Sandown': 'Australia/Melbourne',
            'Seymour': 'Australia/Melbourne',
            'Swan Hill': 'Australia/Melbourne',
            'Stawell': 'Australia/Melbourne',
            'Stony Creek': 'Australia/Melbourne',
            'Terang': 'Australia/Melbourne',
            'Wadonga': 'Australia/Melbourne',
            'Wangaratta': 'Australia/Melbourne',
            'Warrnambool': 'Australia/Melbourne',
            'Yarra Valley': 'Australia/Melbourne',
            
            # Australia - NSW
            'Albury': 'Australia/Sydney',
            'Armidale': 'Australia/Sydney',
            'Ballina': 'Australia/Sydney',
            'Canterbury': 'Australia/Sydney',  # Short form
            'Canterbury Park': 'Australia/Sydney',
            'Coffs Harbour': 'Australia/Sydney',
            'Cootamundra': 'Australia/Sydney',
            'Corowa': 'Australia/Sydney',
            'Forbes': 'Australia/Sydney',
            'Gilgandra': 'Australia/Sydney',
            'Gosford': 'Australia/Sydney',
            'Gundagai': 'Australia/Sydney',
            'Hawkesbury': 'Australia/Sydney',
            'Kembla Grange': 'Australia/Sydney',
            'Kensington': 'Australia/Sydney',
            'Inverell': 'Australia/Sydney',
            'Lismore': 'Australia/Sydney',
            'Lockhart': "Australia/Sydney",
            'Moree': 'Australia/Sydney',
            'Moruya': 'Australia/Sydney',
            'Mudgee': 'Australia/Sydney',
            'Murwillumbah': 'Australia/Sydney',
            'Muswellbrook': 'Australia/Sydney',
            'Narromine': 'Australia/Sydney',
            'Newcastle': 'Australia/Sydney',
            'Nowra': 'Australia/Sydney',
            'Orange': 'Australia/Sydney',
            'Parkes': 'Australia/Sydney',
            'Port Macquarie': 'Australia/Sydney',
            'Queanbeyan': 'Australia/Sydney',
            'Randwick': 'Australia/Sydney',
            'Rosehill': 'Australia/Sydney',
            'Sapphire Coast': 'Australia/Sydney',
            'Scone': 'Australia/Sydney',
            'Tamworth': 'Australia/Sydney',
            'Taree': 'Australia/Sydney',
            'Wagga': 'Australia/Sydney',
            'Warwick Farm': 'Australia/Sydney',
            
            # Australia - QLD
            'Aquis Park Gold Coast Polytrack': 'Australia/Brisbane',
            'Beaudesert': 'Australia/Brisbane',
            'Doomben': 'Australia/Brisbane',
            'Eagle Farm': 'Australia/Brisbane',
            'Gold Coast': 'Australia/Brisbane',
            'Gympie': 'Australia/Brisbane',
            'Ipswich': 'Australia/Brisbane',
            'Kilcoy': 'Australia/Brisbane',
            'Mackay': 'Australia/Brisbane',
            'Rockhampton': 'Australia/Brisbane',
            'Sunshine Coast': 'Australia/Brisbane',
            'Toowoomba': 'Australia/Brisbane',
            'Townsville': 'Australia/Brisbane',
            'Warwick': 'Australia/Brisbane',
            
            # Australia - SA
            'Balaklava': 'Australia/Adelaide',
            'Gawler': 'Australia/Adelaide',
            'Morphettville': 'Australia/Adelaide',
            'Mount Gambier': 'Australia/Adelaide',
            'Murray Bridge': 'Australia/Adelaide',
            'Port Lincoln': 'Australia/Adelaide',
            'Pinjarra': 'Australia/Perth',
            'Warwick': 'Australia/Brisbane',
            'Murray Bdge': 'Australia/Adelaide',
            'Naracoorte': 'Australia/Adelaide',
            'Oakbank': 'Australia/Adelaide',
            'Port Lincoln': 'Australia/Adelaide',
            'Strathalbyn': 'Australia/Adelaide',
            
            # Australia - WA
            'Albany': 'Australia/Perth',
            'Ascot': 'Australia/Perth',
            'Belmont': 'Australia/Perth',
            'Broome': 'Australia/Perth',
            'Bunbury': 'Australia/Perth',
            'Esperance': 'Australia/Perth',
            'Esperance Bay': 'Australia/Perth',
            'Geraldton': 'Australia/Perth',
            'Moora': 'Australia/Perth',
            'Mt Barker': 'Australia/Perth',
            'Narrogin': 'Australia/Perth',
            'Northam': 'Australia/Perth',
            'Pinjarra Park': 'Australia/Perth',
            'Pinjarra': 'Australia/Perth',
            
            # Australia - TAS
            'Hobart': 'Australia/Hobart',
            'Launceston': 'Australia/Hobart',
            'Longford': 'Australia/Hobart',
            
            # Australia - ACT
            'Canberra': 'Australia/Sydney',
            
            # Australia - NT
            'Alice Springs': 'Australia/Darwin',
            'Darwin': 'Australia/Darwin',
            'Kalgoorlie': 'Australia/Darwin',
            
            # Additional existing venues (keeping for compatibility)
            'Benalla': 'Australia/Melbourne',
            'Bowraville': 'Australia/Sydney',
            'Coleraine': 'Australia/Melbourne',
            'Dalby': 'Australia/Brisbane',
            'Echuca': 'Australia/Melbourne',
            'Ewan': 'Australia/Brisbane',
            'Gladstone': 'Australia/Brisbane',
            'Mount Magnet': 'Australia/Perth',
            'Morven': 'Australia/Brisbane',
            'Pooncarie': 'Australia/Sydney',
            'Wagga Riverside': 'Australia/Sydney',
            'Winton': 'Australia/Brisbane',
            'Devonport Synthetic': 'Australia/Hobart',
            'Dubbo': 'Australia/Sydney',
            'Toodyay': 'Australia/Perth',
            
            # UK/Ireland
            'Ayr': 'Europe/London',
            'Chester': 'Europe/London',
            'Downpatrick': 'Europe/London',
            'Gowran Park': 'Europe/Dublin',
            'Navan': 'Europe/Dublin',
            'Newbury': 'Europe/London',
            'Newmarket': 'Europe/London',
            'Newton Abbot': 'Europe/London',
            'Saint-Cloud': 'Europe/Paris',
            
            # New Zealand
            'Ellerslie': 'Pacific/Auckland',
            'Te Aroha': 'Pacific/Auckland',
            'Trentham': 'Pacific/Auckland',
            
            # South Africa
            'Turffontein': 'Africa/Johannesburg',
            'Fairview': 'Africa/Johannesburg',
            
            # Japan
            'Hanshin': 'Asia/Tokyo',
            'Kanazawa': 'Asia/Tokyo',
            'Nagoya': 'Asia/Tokyo',
            'Nakayama': 'Asia/Tokyo',
            'Ohi': 'Asia/Tokyo',
            'Saga': 'Asia/Tokyo',
            'Sonoda': 'Asia/Tokyo',
            
            # US
            'Churchill Downs': 'America/New_York',
            'Fairmount Park': 'America/Chicago',
            'Lone Star Park': 'America/Chicago',
            'Los Alamitos': 'America/Los_Angeles',
            'Meadowlands': 'America/New_York',
            'Penn National': 'America/New_York',
            'Prairie Meadows': 'America/Chicago',
            'Presque Isle Downs': 'America/New_York',
            'Remington Park': 'America/Chicago',
            'Woodbine': 'America/Toronto',
        }
        
        self._create_race_times_table()
    
    def _normalize_venue_name(self, venue):
        """Normalize venue names to match Betfair naming conventions"""
        venue_normalizations = {
            "Wagga Riverside": "Wagga",
            'Sandown Hillside': 'Sandown',
            'Rosehill Gardens': 'Rosehill',
            'Sandown Hillside Racecourse': 'Sandown',
            'Rosehill Gardens Racecourse': 'Rosehill',
            'Moonee Valley Racecourse': 'Moonee Valley',
            'Flemington Racecourse': 'Flemington',
            'Caulfield Racecourse': 'Caulfield',
            'Randwick Racecourse': 'Randwick',
            'Warwick Farm Racecourse': 'Warwick Farm',
            'Canterbury Park Racecourse': 'Canterbury Park',
            'Hawkesbury Racecourse': 'Hawkesbury',
            'Gosford Racecourse': 'Gosford',
            'Newcastle Racecourse': 'Newcastle',
            'Wyong Racecourse': 'Wyong',
            'Kembla Grange Racecourse': 'Kembla Grange',
            'Murray Bdge': 'Murray Bridge',
            'Wagga Wagga Racecourse': 'Wagga',
            'Albury Racecourse': 'Albury',
            'Grafton Racecourse': 'Grafton',
            'Lismore Racecourse': 'Lismore',
            'Murwillumbah Racecourse': 'Murwillumbah',
            'Ballina Racecourse': 'Ballina',
            'Coffs Harbour Racecourse': 'Coffs Harbour',
            'Port Macquarie Racecourse': 'Port Macquarie',
            'Taree Racecourse': 'Taree',
            'Tamworth Racecourse': 'Tamworth',
            'Scone Racecourse': 'Scone',
            'Muswellbrook Racecourse': 'Muswellbrook',
            'Mudgee Racecourse': 'Mudgee',
            'Murray Bdge': 'Murray Bridge',
            'Bathurst Racecourse': 'Bathurst',
            'Orange Racecourse': 'Orange',
            'Dubbo Racecourse': 'Dubbo',
            'Narromine Racecourse': 'Narromine',
            'Parkes Racecourse': 'Parkes',
            'Forbes Racecourse': 'Forbes',
            'Cowra Racecourse': 'Cowra',
            'Young Racecourse': 'Young',
            'Gundagai Racecourse': 'Gundagai',
            'Tumut Racecourse': 'Tumut',
            'Cootamundra Racecourse': 'Cootamundra',
            'Harden Racecourse': 'Harden',
            'Esperance Bay': 'Esperance'  # FIX: Scraper shows "Esperance Bay", Betfair shows "Esperance"
        }
        
        # Return normalized name if found, otherwise return original
        return venue_normalizations.get(venue, venue)

    def _get_country_from_venue(self, venue):
        """Determine country from venue name based on timezone"""
        timezone = self.venue_timezones.get(venue, 'UTC')
        
        if 'Australia' in timezone:
            return 'AUS'
        elif 'Europe/London' in timezone or 'Europe/Dublin' in timezone:
            return 'UK/IRE'
        elif 'Pacific/Auckland' in timezone:
            return 'NZ'
        elif 'Africa/Johannesburg' in timezone:
            return 'SA'
        elif 'Asia/Tokyo' in timezone:
            return 'JPN'
        elif 'America' in timezone:
            return 'US/CAN'
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
    
    def convert_to_aest(self, venue: str, race_date: str, race_time: str) -> tuple:
        """
        Convert race time to AEST based on venue timezone
        
        Args:
            venue: Venue name
            race_date: Race date in YYYY-MM-DD format
            race_time: Race time in HH:MM format (local time for that venue)
        
        Returns:
            tuple: (aest_time_str, aest_date_str, original_timezone_str)
        """
        # Get the venue's timezone
        venue_tz_str = self.venue_timezones.get(venue, 'Australia/Sydney')
        venue_tz = pytz.timezone(venue_tz_str)
        aest_tz = pytz.timezone('Australia/Sydney')
        
        # Parse the date and time
        try:
            # Combine date and time
            datetime_str = f"{race_date} {race_time}"
            naive_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            
            # Localize to venue timezone
            local_dt = venue_tz.localize(naive_dt)
            
            # Convert to AEST
            aest_dt = local_dt.astimezone(aest_tz)
            
            return aest_dt.strftime('%H:%M'), aest_dt.strftime('%Y-%m-%d'), venue_tz_str
            
        except Exception as e:
            logger.warning(f"Error converting time for {venue}: {e}")
            # Fallback: assume it's already in AEST
            return race_time, race_date, venue_tz_str
    
    def save_race_times_to_db(self, races: List[Dict], date_str: str):
        """Save race times directly to database"""
        if not races:
            logger.warning("No races to save")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM race_times");   
        saved_count = 0
        skipped_count = 0
        for race in races:
            try:
                # Normalize venue name to match Betfair conventions
                normalized_venue = self._normalize_venue_name(race['venue'])
                
                # Get timezone for this venue
                timezone = self.venue_timezones.get(normalized_venue, None)
                
                # FILTER: Only save races from venues we know AND have Australian timezones
                if timezone is None:
                    logger.debug(f"Skipping unknown venue: {normalized_venue}")
                    skipped_count += 1
                    continue
                
                if 'Australia' not in timezone:
                    logger.debug(f"Skipping non-Australian venue: {normalized_venue} (timezone: {timezone})")
                    skipped_count += 1
                    continue
                
                # Times from racenet.com.au are already in Bangkok time (=AEST) - no conversion needed!
                aest_time = race['race_time_24h']
                aest_date = date_str
                
                # Additional filter for ambiguous venues (e.g., Warwick QLD vs Warwick UK)
                # Australian races typically run between 10:00 and 21:00 AEST
                # UK evening races show as 19:00-23:00 in Bangkok time (7pm-11pm)
                race_hour = int(aest_time.split(':')[0])
                if normalized_venue == 'Warwick' and race_hour >= 19:
                    logger.debug(f"Skipping {normalized_venue} R{race['race_number']} at {aest_time} (likely UK Warwick based on time)")
                    skipped_count += 1
                    continue
                
                # Get country for this venue
                country = self._get_country_from_venue(normalized_venue)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO race_times 
                    (venue, race_number, race_time, race_time_utc, race_date, timezone, country, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    normalized_venue,  # Use normalized venue name
                    race['race_number'], 
                    aest_time,  # AEST time (already from website)
                    aest_time,  # Same as race_time (for compatibility)
                    aest_date,  # AEST date
                    timezone,
                    country
                ))
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving race {race['venue']} R{race['race_number']}: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {saved_count} Australian race times to database (skipped {skipped_count} non-Australian races)")
    
    def scrape_race_times(self, date_str: str = None):
        """
        Scrape race times for a specific date from both horse racing and harness racing pages
        
        Args:
            date_str: Date in YYYY-MM-DD format, defaults to today
            
        Returns:
            DataFrame with race times and details
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Try the main form guide page first
        url = f"{self.base_url}/form-guide/horse-racing"
        logger.info(f"Scraping race times from: {url}")
        
        try:
            # Use Selenium to load JavaScript content
            from selenium import webdriver
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.by import By
            import time as time_module
            
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            
            # Wait for content to load
            logger.info("Waiting for race content to load...")
            time_module.sleep(5)  # Give it time to load all dynamic content
            
            html = driver.page_source
            driver.quit()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            races = []
            
            # Look for race meeting cards or race lists
            race_cards = soup.find_all(['div', 'section'], class_=re.compile(r'race|meeting|card|form', re.I))
            
            if not race_cards:
                # Try alternative selectors for Racenet
                race_cards = soup.find_all('div', class_=re.compile(r'meeting|venue|race-day', re.I))
            
            logger.info(f"Found {len(race_cards)} potential race card elements")
            
            # Look for specific Racenet HTML structure
            # Race time: <abbr class="relative-time__inner"><span>16:24</span></abbr>
            # Race number: <div class="upcoming-race-table__event-number">R2</div>
            # Venue: data-analytics="Race Event Link : Horse Racing : Belmont R2"
            
            # Look for the specific Racenet structure
            # Find all upcoming race table links
            race_links = soup.find_all('a', class_='upcoming-race-table__event-link')
            logger.info(f"Found {len(race_links)} race links")
            
            for link in race_links:
                try:
                    # Extract venue from data-analytics attribute
                    analytics = link.get('data-analytics', '')
                    venue_name = 'Unknown'
                    race_number = 'Unknown'
                    
                    if 'Race Event Link : Horse Racing :' in analytics:
                        # Extract venue and race number from "Race Event Link : Horse Racing : Belmont R2"
                        parts = analytics.split(' : ')
                        if len(parts) >= 3:
                            venue_race = parts[2].strip()
                            # Split venue and race number - handle venues with "Racecourse" and "Riverside"
                            if ' R' in venue_race:
                                # Find the last occurrence of ' R' to handle venues like "Los Alamitos Racecourse R1"
                                last_r_index = venue_race.rfind(' R')
                                venue_name = venue_race[:last_r_index].strip()
                                race_number = venue_race[last_r_index + 2:].strip()
                    
                            # Find race time within the link
                            time_element = link.find('abbr', class_='relative-time__inner')
                            race_time = 'Unknown'
                            
                            if time_element:
                                time_span = time_element.find('span')
                                if time_span:
                                    race_time = time_span.get_text().strip()
                    
                    # Only add if we have valid data
                    if race_time != 'Unknown' and venue_name != 'Unknown' and race_number != 'Unknown':
                        race_data = {
                            'venue': venue_name,
                            'race_number': race_number,
                            'race_time': race_time,
                            'raw_text': f"{venue_name} R{race_number} - {race_time}"
                        }
                        races.append(race_data)
                        
                except Exception as e:
                    logger.warning(f"Error processing race link: {e}")
                    continue
            
            # Always run fallback parsing to catch any races missed by structured parsing
            logger.info("Running fallback parsing to catch any missed races")
            
            # Define patterns for fallback parsing
            race_time_pattern = re.compile(r'(\d{1,2}:\d{2})')
            race_number_pattern = re.compile(r'R(\d+)')
            venue_patterns = [
                re.compile(r'(\w+(?:\s+\w+)*)\s+R\d+', re.IGNORECASE),  # "Wagga Riverside R1"
                re.compile(r'(\w+)\s+R\d+', re.IGNORECASE),  # "Belmont R1"
            ]
            
            # Split page into lines and look for race-like patterns
            page_text = soup.get_text()
            lines = page_text.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if 'R' in line and any(char.isdigit() for char in line) and ':' in line:
                    time_match = race_time_pattern.search(line)
                    race_num_match = race_number_pattern.search(line)
                    
                    # Try different venue patterns
                    venue_name = 'Unknown'
                    for pattern in venue_patterns:
                        venue_match = pattern.search(line)
                        if venue_match:
                            venue_name = venue_match.group(1).strip()
                            break
                    
                    if time_match and venue_name != 'Unknown':
                        race_data = {
                            'venue': venue_name,
                            'race_number': race_num_match.group(1) if race_num_match else 'Unknown',
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
            
            logger.info(f"Extracted {len(unique_races)} unique races")
            
            if unique_races:
                df = pd.DataFrame(unique_races)
                logger.info(f"Race times found:")
                for _, race in df.iterrows():
                    logger.info(f"  {race['venue']} R{race['race_number']} - {race['race_time']}")
                return df
            else:
                logger.warning("No race times found")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error scraping race times: {str(e)}")
            return pd.DataFrame()
    
    def get_race_times_for_date(self, date_str: str = None):
        """
        Get race times and return in a more structured format
        """
        df = self.scrape_race_times(date_str)
        
        if df.empty:
            return []
        
        races = []
        for _, row in df.iterrows():
            try:
                # Parse time and convert to 24-hour format
                time_str = row['race_time']
                if ':' in time_str:
                    hour, minute = time_str.split(':')
                    hour = int(hour)
                    minute = int(minute)
                    
                    # Convert to 24-hour format if needed
                    if hour < 12 and 'PM' in str(row.get('raw_text', '')).upper():
                        hour += 12
                    elif hour == 12 and 'AM' in str(row.get('raw_text', '')).upper():
                        hour = 0
                    
                    race_time = f"{hour:02d}:{minute:02d}"
                    
                    races.append({
                        'venue': row['venue'],
                        'race_time': race_time,
                        'race_time_12h': time_str
                    })
            except Exception as e:
                logger.warning(f"Error parsing time {row['race_time']}: {e}")
                continue
        
        return races


def scrape_and_save_race_times(date_str: str = None, save_to_csv: bool = False):
    """Scrape race times and save directly to database (and optionally to CSV)"""
    from datetime import datetime
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    scraper = RaceTimesScraper()
    df = scraper.scrape_race_times(date_str)
    
    if not df.empty:
        # Clean up the data
        df = df[df['venue'] != 'Unknown']  # Remove races with unknown venues
        df = df[df['race_number'] != 'Unknown']  # Remove races with unknown numbers
        
        # Filter out Non-TAB races (no betting markets available)
        if 'raw_text' in df.columns:
            df = df[~df['raw_text'].str.contains('Non-TAB', case=False, na=False)]
        
        # Include all races regardless of country
        logger.info(f"Found {len(df)} races from all countries")
        
        # Convert times - handle both absolute and relative time formats
        # Capture the exact time when we start processing to use as reference
        from datetime import datetime, timedelta
        scrape_time = datetime.now()
        
        def convert_time(time_str):
            try:
                # Handle absolute time format (HH:MM)
                if ':' in time_str and not any(x in time_str.lower() for x in ['h', 'm', 's']):
                    hour, minute = time_str.split(':')
                    hour = int(hour)
                    minute = int(minute)
                    
                    # Racenet times are already in correct 24-hour format
                    # No conversion needed!
                    return f"{hour:02d}:{minute:02d}"
                
                # Handle relative time format (Xh Ym, Ym Zs, etc.)
                elif any(x in time_str.lower() for x in ['h', 'm', 's']):
                    # Use the scrape_time as reference instead of current time
                    reference_time = scrape_time
                    
                    # Handle negative times (race already started)
                    if time_str.startswith('-'):
                        # Race already started, return reference time
                        return reference_time.strftime('%H:%M')
                    
                    # Parse hours, minutes, seconds
                    hours = 0
                    minutes = 0
                    seconds = 0
                    
                    # Extract hours
                    if 'h' in time_str.lower():
                        hour_part = time_str.lower().split('h')[0].split()[-1]
                        hours = int(hour_part)
                    
                    # Extract minutes
                    if 'm' in time_str.lower():
                        # Find the part with minutes
                        parts = time_str.lower().split()
                        for part in parts:
                            if 'm' in part and 'h' not in part:
                                minute_part = part.replace('m', '').replace('s', '')
                                if minute_part.isdigit():
                                    minutes = int(minute_part)
                                    break
                    
                    # Extract seconds
                    if 's' in time_str.lower() and 'm' not in time_str.lower():
                        sec_part = time_str.lower().split('s')[0].split()[-1]
                        seconds = int(sec_part)
                    
                    # Calculate race start time using reference time
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
            filename = f"race_times_{date_str}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Also saved to CSV: {filename}")
        
        # Show summary - ordered by race time
        logger.info(f"Race times summary for {date_str}:")
        df_sorted = df.sort_values(['race_time_24h', 'venue', 'race_number'])
        for _, race in df_sorted.head(10).iterrows():
            logger.info(f"  {race['venue']} R{race['race_number']} - {race['race_time_24h']}")
        
        # Also show venue summary
        logger.info(f"Venue summary:")
        for venue in df['venue'].unique():
            venue_races = df[df['venue'] == venue]
            logger.info(f"  {venue}: {len(venue_races)} races")
        
        return df
    else:
        logger.warning("No race times found to save")
        return pd.DataFrame()


def main():
    """Scrape race times and save directly to database"""
    # Test with today's date
    today = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"Scraping race times for {today}")
    
    # Scrape and save to database (optionally also to CSV)
    df = scrape_and_save_race_times(today, save_to_csv=False)
    
    return df


if __name__ == "__main__":
    main()
