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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RaceTimesScraper:
    """
    Scrapes actual race start times from Racenet.com.au and saves directly to database
    """
    
    def __init__(self, db_path: str = None):
        self.base_url = "https://www.racenet.com.au"
        self.db_path = db_path or "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self._create_race_times_table()
    
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
                race_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(venue, race_number, race_date)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Race times table created/verified")
    
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
                cursor.execute("""
                    INSERT OR REPLACE INTO race_times 
                    (venue, race_number, race_time, race_date, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (race['venue'], race['race_number'], race['race_time_24h'], date_str))
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving race {race['venue']} R{race['race_number']}: {e}")
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {saved_count} race times to database")
    
    def scrape_race_times(self, date_str: str = None):
        """
        Scrape race times for a specific date
        
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
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
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
                            # Split venue and race number
                            if ' R' in venue_race:
                                venue_name = venue_race.split(' R')[0].strip()
                                race_number = venue_race.split(' R')[1].strip()
                    
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
            
            if not races:
                # Fallback: look for any time patterns and try to extract context
                logger.info("No structured race data found, trying fallback method")
                
                # Split page into lines and look for race-like patterns
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
                        
                        if time_match:
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
        
        # Filter for Australian and New Zealand venues
        australian_nz_venues = [
            # Australian venues
            'Belmont', 'Canterbury', 'Doomben', 'Murray Bridge', 'Murray Bdge', 'Bendigo', 
            'Flemington', 'Caulfield', 'Moonee Valley', 'Randwick', 'Rosehill',
            'Warwick Farm', 'Kembla Grange', 'Newcastle', 'Gosford', 'Wyong', 'Hawkesbury',
            'Kembla', 'Grafton', 'Lismore', 'Ballina', 'Coffs Harbour', 'Port Macquarie',
            'Taree', 'Muswellbrook', 'Scone', 'Tamworth', 'Gunnedah', 'Moree', 'Armidale',
            'Inverell', 'Grafton', 'Lismore', 'Ballina', 'Coffs Harbour', 'Port Macquarie',
            'Taree', 'Muswellbrook', 'Scone', 'Tamworth', 'Gunnedah', 'Moree', 'Armidale',
            'Inverell', 'Eagle Farm', 'Ipswich', 'Gold Coast', 'Sunshine Coast', 'Toowoomba',
            'Rockhampton', 'Mackay', 'Townsville', 'Cairns', 'Mount Isa', 'Longreach',
            'Charleville', 'Roma', 'Dalby', 'Warwick', 'Stanthorpe', 'Goondiwindi',
            'Adelaide', 'Morphettville', 'Gawler', 'Murray Bridge', 'Bordertown', 'Naracoorte',
            'Mount Gambier', 'Penola', 'Millicent', 'Port Augusta', 'Port Pirie', 'Whyalla',
            'Perth', 'Ascot', 'Belmont', 'Northam', 'York', 'Bunbury', 'Albany', 'Kalgoorlie',
            'Geraldton', 'Carnarvon', 'Broome', 'Kununurra', 'Hobart', 'Launceston', 'Devonport',
            'Burnie', 'Hobart', 'Launceston', 'Devonport', 'Burnie', 'Hobart', 'Launceston',
            # New Zealand venues
            'Taupo', 'Auckland', 'Ellerslie', 'Te Rapa', 'Trentham', 'Riccarton', 'Ashburton',
            'Timaru', 'Oamaru', 'Wingatui', 'Gore', 'Invercargill', 'Awapuni', 'Wanganui',
            'Hawera', 'New Plymouth', 'Taranaki', 'Palmerston North', 'Manawatu', 'Otaki',
            'Levin', 'Feilding', 'Marton', 'Waverley', 'Stratford', 'Pukekohe', 'Cambridge',
            'Te Awamutu', 'Matamata', 'Tauranga', 'Rotorua', 'Gisborne', 'Hastings', 'Napier',
            'Waipukurau', 'Dannevirke', 'Woodville', 'Masterton', 'Featherston', 'Greytown',
            'Carterton', 'Eketahuna', 'Pahiatua', 'Pongaroa', 'Kumeroa', 'Mangatainoka',
            'Blenheim', 'Nelson', 'Motueka', 'Takaka', 'Westport', 'Reefton', 'Greymouth',
            'Hokitika', 'Kumara', 'Rangiora', 'Kaikoura', 'Cheviot', 'Amberley', 'Culverden',
            'Waiau', 'Hanmer Springs', 'Kaikoura', 'Picton', 'Seddon', 'Ward', 'Spring Creek'
        ]
        
        # Filter for Australian and New Zealand venues
        df = df[df['venue'].isin(australian_nz_venues)]
        logger.info(f"Filtered to {len(df)} Australian and New Zealand races")
        
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
                    
                    # Racenet absolute times are missing the "1" prefix for ALL times
                    # Add 10 to all hours to get correct 24-hour format
                    # Times like 05:49 become 15:49, 03:35 become 13:35, etc.
                    hour += 10
                    if hour >= 24:
                        hour -= 24
                    
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
