"""
Greyhound Race Times Scraper - PostgreSQL Version
Gets actual race start times
Scrapes from multiple sources for Australian and New Zealand greyhound racing
"""
import psycopg2
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import logging
import re
from typing import List, Dict
import pytz
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PostgreSQL connection details
PG_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'betfair_races',
    'user': 'clairegrady',
    'password': 'World17!'
}


class GreyhoundRaceTimesScraper:
    """
    Scrapes greyhound race start times and saves to PostgreSQL database
    """
    
    def __init__(self):
        self.base_url = "https://www.racenet.com.au"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Greyhound venue name mappings (standardize to Betfair names)
        self.venue_mappings = {
            # Australian venues
            'the meadows': 'The Meadows',
            'sandown park': 'Sandown Park',
            'angle park': 'Angle Park',
            'wentworth park': 'Wentworth Park',
            'albion park': 'Albion Park',
            'murray bridge': 'Murray Bridge',
            'cannington': 'Cannington',
            'warragul': 'Warragul',
            'horsham': 'Horsham',
            'geelong': 'Geelong',
            'ballarat': 'Ballarat',
            'bendigo': 'Bendigo',
            'sale': 'Sale',
            'traralgon': 'Traralgon',
            'healesville': 'Healesville',
            'shepparton': 'Shepparton',
            'buxton': 'Buxton',
            'richmond': 'Richmond',
            'dapto': 'Dapto',
            'dubbo': 'Dubbo',
            'goulburn': 'Goulburn',
            'gosford': 'Gosford',
            'bathurst': 'Bathurst',
            'temora': 'Temora',
            'nowra': 'Nowra',
            'Murray Bridge Straight': 'Murray Bridge',
            # New Zealand venues
            'hatrick straight': 'Hatrick Straight',
            'hatrick': 'Hatrick Straight',  # Fallback
            'manawatu': 'Manawatu',
            'addington': 'Addington',
            'cambridge': 'Cambridge',
            'ascot park': 'Ascot Park',
        }
    
    def scrape_racenet_greyhounds(self) -> List[Dict]:
        """
        Scrape greyhound races from Racenet (AUS + NZ races)
        Returns list of race dictionaries
        """
        races = []
        
        try:
            from selenium import webdriver
            import time as time_module
            
            url = "https://www.racenet.com.au/form-guide/greyhounds"
            logger.info(f"Scraping {url} with Selenium...")
            
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            
            # Wait for content to load
            logger.info("Waiting for race content to load...")
            time_module.sleep(5)
            
            html = driver.page_source
            driver.quit()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for specific Racenet structure
            race_links = soup.find_all('a', class_='upcoming-race-table__event-link')
            logger.info(f"Found {len(race_links)} race links")
            
            for link in race_links:
                try:
                    analytics = link.get('data-analytics', '')
                    venue_name = 'Unknown'
                    race_number = 'Unknown'
                    
                    if 'Race Event Link : Greyhounds :' in analytics or 'Race Event Link : Greyhound :' in analytics:
                        parts = analytics.split(' : ')
                        if len(parts) >= 3:
                            venue_race = parts[2].strip()
                            if ' R' in venue_race:
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
                    
                    # Add race if we have venue, race number, and valid time
                    if venue_name != 'Unknown' and race_number != 'Unknown' and race_time != 'Unknown':
                        race_data = {
                            'venue': venue_name,
                            'race_number': race_number,
                            'race_time': race_time,
                            'raw_text': f"{venue_name} R{race_number} - {race_time}"
                        }
                        races.append(race_data)
                        
                except Exception as e:
                    logger.debug(f"Error processing race link: {e}")
                    continue
            
            # FALLBACK PARSING
            logger.info("Running fallback parsing to catch any missed races")
            
            race_time_pattern = re.compile(r'(\d{1,2}:\d{2})')
            race_number_pattern = re.compile(r'R(\d+)')
            venue_patterns = [
                re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+R\d+', re.IGNORECASE),
                re.compile(r'([A-Z][a-z]+)\s+R\d+', re.IGNORECASE),
            ]
            
            page_text = soup.get_text()
            lines = page_text.split('\n')
            for line in lines:
                line = line.strip()
                if 'R' in line and any(char.isdigit() for char in line) and ':' in line:
                    time_match = race_time_pattern.search(line)
                    race_num_match = race_number_pattern.search(line)
                    
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
            unique_races_dict = {}
            for race in races:
                key = (race['venue'], race['race_number'], race['race_time'])
                if key not in unique_races_dict:
                    unique_races_dict[key] = race
            
            unique_races = list(unique_races_dict.values())
            logger.info(f"Extracted {len(unique_races)} unique races after deduplication (AUS + NZ)")
            
            # Convert times
            from datetime import timedelta
            scrape_time = datetime.now()
            
            def convert_time(time_str):
                """Convert race time to HH:MM format"""
                try:
                    # Handle absolute time format (HH:MM)
                    if ':' in time_str and not any(x in time_str.lower() for x in ['h', 'm', 's']):
                        hour, minute = time_str.split(':')
                        hour = int(hour)
                        minute = int(minute)
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
                    logger.warning(f"Error converting time '{time_str}': {e}")
                    return time_str
            
            formatted_races = []
            for race in unique_races:
                try:
                    if race['race_time'] == 'Unknown':
                        logger.debug(f"Skipping {race['venue']} R{race['race_number']} - no valid time")
                        continue
                    
                    venue = self.venue_mappings.get(race['venue'].lower(), race['venue'])
                    timezone_str = self._get_timezone_for_venue(venue)
                    country = self._get_country_from_venue(venue)
                    
                    aest_time = convert_time(race['race_time'])
                    aest_date = datetime.now().strftime('%Y-%m-%d')
                    
                    formatted_races.append({
                        'venue': venue,
                        'race_number': int(race['race_number']) if race['race_number'] != 'Unknown' else 0,
                        'race_time': aest_time,
                        'race_time_utc': aest_time,
                        'race_date': aest_date,
                        'timezone': timezone_str,
                        'country': country
                    })
                except Exception as e:
                    logger.debug(f"Error formatting race: {e}")
                    continue
            
            if formatted_races:
                logger.info(f"✅ Scraped {len(formatted_races)} greyhound races from Racenet (AUS + NZ)")
            else:
                logger.warning("⚠️  No greyhound races found on Racenet")
                
            return formatted_races
            
        except ImportError:
            logger.error("❌ Selenium not installed. Install with: pip install selenium")
        except Exception as e:
            logger.error(f"❌ Error scraping Racenet: {e}")
        
        return races
    
    def _get_timezone_for_venue(self, venue: str) -> str:
        """Get timezone for venue based on state/country"""
        venue_lower = venue.lower()
        
        # NZ venues
        nz_venues = ['hatrick straight', 'hatrick', 'manawatu', 'manukau', 'addington', 'cambridge', 'ascot park']
        if any(v in venue_lower for v in nz_venues):
            return 'Pacific/Auckland'
        
        # VIC venues
        vic_venues = ['the meadows', 'sandown park', 'warragul', 'geelong', 'ballarat', 'bendigo', 'horsham', 'sale', 'traralgon', 'healesville', 'shepparton']
        if any(v in venue_lower for v in vic_venues):
            return 'Australia/Melbourne'
        
        # NSW venues  
        nsw_venues = ['wentworth park', 'richmond', 'dapto', 'dubbo', 'goulburn', 'gosford', 'bathurst', 'temora', 'nowra', 'bulli', 'the gardens']
        if any(v in venue_lower for v in nsw_venues):
            return 'Australia/Sydney'
        
        # QLD venues
        qld_venues = ['albion park', 'ipswich', 'gold coast', 'townsville', 'rockhampton', 'q1 lakeside', 'lakeside']
        if any(v in venue_lower for v in qld_venues):
            return 'Australia/Brisbane'
        
        # SA venues
        sa_venues = ['angle park', 'murray bridge', 'gawler']
        if any(v in venue_lower for v in sa_venues):
            return 'Australia/Adelaide'
        
        # WA venues
        wa_venues = ['cannington', 'mandurah']
        if any(v in venue_lower for v in wa_venues):
            return 'Australia/Perth'
        
        # Default to Sydney/AEST (most venues)
        return 'Australia/Sydney'
    
    def _get_country_from_venue(self, venue: str) -> str:
        """Determine country from venue name"""
        timezone = self._get_timezone_for_venue(venue)
        
        if 'Pacific/Auckland' in timezone:
            return 'NZ'
        elif 'Australia' in timezone:
            return 'AUS'
        else:
            return 'UNKNOWN'
    
    def save_to_database(self, races: List[Dict]):
        """Save races to PostgreSQL greyhound_race_times table"""
        if not races:
            logger.info("No races to save")
            return
        
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor()
        
        try:
            # DELETE old entries before adding new ones
            cursor.execute("DELETE FROM greyhound_race_times")
            logger.info("🗑️  Cleared previous entries")
            
            saved = 0
            errors = 0
            aus_count = 0
            nz_count = 0
            
            for race in races:
                try:
                    cursor.execute("""
                        INSERT INTO greyhound_race_times 
                        (venue, race_number, race_time, race_time_utc, race_date, timezone, country)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        race['venue'],
                        race['race_number'],
                        race['race_time'],
                        race['race_time_utc'],
                        race['race_date'],
                        race['timezone'],
                        race.get('country', 'AUS')
                    ))
                    
                    saved += 1
                    
                    if race.get('country') == 'NZ':
                        nz_count += 1
                    else:
                        aus_count += 1
                        
                except Exception as e:
                    logger.error(f"Error saving race {race}: {e}")
                    errors += 1
            
            conn.commit()
            
            # Normalize venue names (fix any stragglers that weren't caught by mappings)
            self._normalize_venue_names(cursor)
            conn.commit()
            
            logger.info(f"💾 Saved: {saved}, Errors: {errors}")
            logger.info(f"🌏 AUS: {aus_count}, NZ: {nz_count}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
        finally:
            cursor.close()
            conn.close()
    
    def _normalize_venue_names(self, cursor):
        """Normalize venue names in database (fix stragglers)"""
        normalizations = [
            ("UPDATE greyhound_race_times SET venue = 'Murray Bridge' WHERE venue = 'Murray Bridge Straight'", "Murray Bridge Straight → Murray Bridge"),
            ("UPDATE greyhound_race_times SET venue = 'Hatrick Straight' WHERE venue = 'Hatrick'", "Hatrick → Hatrick Straight"),
            ("UPDATE greyhound_race_times SET venue = 'The Meadows' WHERE venue = 'meadows'", "meadows → The Meadows"),
            ("UPDATE greyhound_race_times SET venue = 'Sandown Park' WHERE venue ILIKE 'sandown%'", "sandown* → Sandown Park"),
            ("UPDATE greyhound_race_times SET venue = 'Angle Park' WHERE venue ILIKE 'angle%'", "angle* → Angle Park"),
            ("UPDATE greyhound_race_times SET venue = 'Q Straight' WHERE venue ILIKE 'q%straight'", "Q*Straight → Q Straight"),
        ]
        
        for sql, description in normalizations:
            cursor.execute(sql)
            if cursor.rowcount > 0:
                logger.info(f"   ✅ Normalized {cursor.rowcount} venues: {description}")
    
    def scrape_all_sources(self) -> List[Dict]:
        """Scrape greyhound races - using ONLY Racenet (includes AUS + NZ races)"""
        logger.info("🔍 Starting greyhound race scraping (AUS + NZ)...")
        races = self.scrape_racenet_greyhounds()
        return races
    
    def run(self):
        """Main scraping workflow"""
        logger.info("=" * 70)
        logger.info("🐕 GREYHOUND RACE TIMES SCRAPER (AUS + NZ) - POSTGRESQL")
        logger.info("=" * 70)
        
        races = self.scrape_all_sources()
        
        if races:
            self.save_to_database(races)
            logger.info(f"\n✅ Total unique races scraped: {len(races)}")
        else:
            logger.warning("\n⚠️  No races found")
        
        self.show_summary()
    
    def show_summary(self):
        """Show summary of races in database"""
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM greyhound_race_times 
                WHERE race_date::date = CURRENT_DATE
            """)
            
            count = cursor.fetchone()[0]
            logger.info(f"\n📊 Total greyhound races in database for today: {count}")
            
            # Show breakdown by country
            cursor.execute("""
                SELECT country, COUNT(*) as race_count
                FROM greyhound_race_times
                WHERE race_date::date = CURRENT_DATE
                GROUP BY country
            """)
            
            countries = cursor.fetchall()
            if countries:
                logger.info("\n🌏 By Country:")
                for country, cnt in countries:
                    logger.info(f"   {country or 'Unknown'}: {cnt} races")
            
            # Show venues
            cursor.execute("""
                SELECT venue, country, COUNT(*) as race_count
                FROM greyhound_race_times
                WHERE race_date::date = CURRENT_DATE
                GROUP BY venue, country
                ORDER BY country, race_count DESC
            """)
            
            venues = cursor.fetchall()
            if venues:
                logger.info("\n📍 Venues:")
                for venue, country, cnt in venues:
                    country_flag = "🇦🇺" if country == "AUS" else "🇳🇿" if country == "NZ" else "🏁"
                    logger.info(f"   {country_flag} {venue}: {cnt} races")
            
        finally:
            cursor.close()
            conn.close()


def main():
    scraper = GreyhoundRaceTimesScraper()
    scraper.run()


if __name__ == "__main__":
    main()
