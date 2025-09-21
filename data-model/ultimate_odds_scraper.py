#!/usr/bin/env python3
"""
Ultimate Odds Scraper for AU/NZ Races
Final version with advanced click interception handling
"""

import sqlite3
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
from datetime import datetime
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UltimateOddsScraper:
    def __init__(self):
        self.driver = None
        self.market_db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
        self.betting_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/betting_history.sqlite"
        self.setup_driver()
        self.create_odds_table()
    
    def setup_driver(self):
        """Setup Chrome driver with ultimate anti-detection options"""
        chrome_options = Options()
        
        # Basic options
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Ultimate anti-detection
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-background-networking')
        
        # User agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Experimental options
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Ultimate Chrome driver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise
    
    def create_odds_table(self):
        """Create odds table in betting_history database"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraped_odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venue TEXT NOT NULL,
                    race_number INTEGER NOT NULL,
                    race_time TEXT,
                    race_date TEXT,
                    horse_name TEXT NOT NULL,
                    horse_number INTEGER,
                    bookmaker TEXT NOT NULL,
                    odds REAL NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(venue, race_number, horse_name, bookmaker, race_date)
                )
            ''')
            conn.commit()
            logger.info("Created scraped_odds table")
        except Exception as e:
            logger.error(f"Error creating odds table: {str(e)}")
        finally:
            conn.close()
    
    def get_todays_races(self) -> List[Dict]:
        """Get today's races from race_times database for AU/NZ venues"""
        conn = sqlite3.connect(self.market_db_path)
        cursor = conn.cursor()
        
        try:
            # Get today's date
            today = datetime.now().strftime('%Y-%m-%d')
            
            # AU/NZ venues
            au_nz_venues = [
                'Flemington', 'Devonport Synthetic', 'Sunshine Coast', 'Kalgoorlie', 
                'Nowra', 'Mount Gambier', 'Gore', 'Te Aroha', 'Hamilton'
            ]
            
            # Query for today's races
            placeholders = ','.join(['?' for _ in au_nz_venues])
            query = f"""
                SELECT DISTINCT venue, race_number, race_time, race_date
                FROM race_times 
                WHERE race_date = ? 
                AND venue IN ({placeholders})
                ORDER BY venue, race_number
            """
            
            cursor.execute(query, [today] + au_nz_venues)
            races = cursor.fetchall()
            
            race_list = []
            for venue, race_number, race_time, race_date in races:
                race_list.append({
                    'venue': venue,
                    'race_number': race_number,
                    'race_time': race_time,
                    'race_date': race_date
                })
            
            logger.info(f"Found {len(race_list)} races for today")
            return race_list
            
        except Exception as e:
            logger.error(f"Error getting today's races: {str(e)}")
            return []
        finally:
            conn.close()
    
    def remove_ads_and_overlays(self):
        """Remove ad banners and overlays that block clicks"""
        try:
            self.driver.execute_script("""
                // Remove only specific blocking elements, not navigation
                var elementsToRemove = document.querySelectorAll(
                    '[class*="bz-custom-container"]'
                );
                for (var i = 0; i < elementsToRemove.length; i++) {
                    elementsToRemove[i].style.display = 'none';
                }
                
                // Remove sticky elements that block clicks
                var sticky = document.querySelectorAll('[style*="position: fixed"], [style*="position: absolute"]');
                for (var i = 0; i < sticky.length; i++) {
                    if (sticky[i].style.zIndex > 100 && !sticky[i].classList.contains('odds-event-navigation')) {
                        sticky[i].style.display = 'none';
                    }
                }
                
                // Remove header containers that block clicks (but not navigation)
                var headers = document.querySelectorAll('.header__container');
                for (var i = 0; i < headers.length; i++) {
                    if (headers[i].style.position === 'fixed' || headers[i].style.position === 'absolute') {
                        headers[i].style.display = 'none';
                    }
                }
            """)
            
            time.sleep(1)
            logger.info("Removed blocking ads and overlays")
            
        except Exception as e:
            logger.warning(f"Error removing ads: {str(e)}")
    
    def click_with_retry(self, element, max_retries=5):
        """Click element with multiple retry strategies"""
        for attempt in range(max_retries):
            try:
                # Strategy 1: Regular click
                element.click()
                return True
                
            except ElementClickInterceptedException:
                logger.warning(f"Click intercepted, trying strategy {attempt + 1}")
                
                # Strategy 2: JavaScript click
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    pass
                
                # Strategy 3: ActionChains click
                try:
                    ActionChains(self.driver).move_to_element(element).click().perform()
                    return True
                except Exception:
                    pass
                
                # Strategy 4: Scroll and click
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    element.click()
                    return True
                except Exception:
                    pass
                
                # Strategy 5: Force click with JavaScript
                try:
                    self.driver.execute_script("""
                        arguments[0].style.pointerEvents = 'auto';
                        arguments[0].style.zIndex = '9999';
                        arguments[0].click();
                    """, element)
                    return True
                except Exception:
                    pass
                
                # Remove blocking elements and try again
                self.remove_ads_and_overlays()
                time.sleep(1)
                
            except Exception as e:
                logger.warning(f"Click attempt {attempt + 1} failed: {str(e)}")
                time.sleep(1)
        
        return False
    
    def scrape_venue_races(self, venue: str, date: str = None) -> List[Dict]:
        """Scrape all races for a specific venue"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Convert venue name to URL format
        venue_url = venue.lower().replace(' ', '-')
        
        # Construct URL
        url = f"https://www.punters.com.au/odds-comparison/horse-racing/{venue_url}/{date.replace('-', '-')}/"
        
        try:
            logger.info(f"Scraping {venue} races from {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Remove ads and overlays
            self.remove_ads_and_overlays()
            
            # Check if page loaded successfully
            if "error" in self.driver.title.lower() or "not found" in self.driver.title.lower():
                logger.warning(f"Page error for {venue}: {self.driver.title}")
                return []
            
            # Try to find race navigation
            try:
                race_nav = self.driver.find_element(By.CLASS_NAME, "odds-event-navigation")
                nav_text = race_nav.text
                logger.info(f"Race navigation for {venue}: {nav_text}")
                
                # Extract race numbers
                race_numbers = re.findall(r'R(\d+)', nav_text)
                logger.info(f"Found race numbers for {venue}: {race_numbers}")
                
                if not race_numbers:
                    logger.warning(f"No race numbers found for {venue}")
                    return []
                
            except NoSuchElementException:
                logger.warning(f"No race navigation found for {venue}")
                return []
            
            all_races = []
            
            # Scrape each race
            for race_num in race_numbers:
                try:
                    logger.info(f"Scraping {venue} Race {race_num}...")
                    race_data = self.scrape_single_race(race_num, venue, date)
                    if race_data:
                        all_races.append(race_data)
                        logger.info(f"✅ Successfully scraped {venue} Race {race_num}")
                    else:
                        logger.warning(f"❌ Failed to scrape {venue} Race {race_num}")
                        
                except Exception as e:
                    logger.error(f"Error scraping {venue} Race {race_num}: {str(e)}")
                    continue
            
            return all_races
            
        except Exception as e:
            logger.error(f"Error scraping {venue}: {str(e)}")
            return []
    
    def scrape_single_race(self, race_num: str, venue: str, date: str) -> Optional[Dict]:
        """Scrape a single race by clicking on the race tab"""
        try:
            # Find the race tab
            race_tab = self.driver.find_element(By.XPATH, f"//a[contains(text(), 'R{race_num}')]")
            
            # Scroll to element
            self.driver.execute_script("arguments[0].scrollIntoView(true);", race_tab)
            time.sleep(1)
            
            # Remove ads before clicking
            self.remove_ads_and_overlays()
            
            # Click with retry
            if not self.click_with_retry(race_tab):
                logger.error(f"Failed to click race tab R{race_num} for {venue}")
                return None
            
            # Wait for race data to load
            time.sleep(3)
            
            # Get the page source and parse
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Extract race data
            race_data = self.extract_race_data_with_odds(soup, race_num, venue, date)
            
            return race_data
            
        except NoSuchElementException:
            logger.error(f"Race tab R{race_num} not found for {venue}")
            return None
        except Exception as e:
            logger.error(f"Error scraping race {race_num} for {venue}: {str(e)}")
            return None
    
    def extract_race_data_with_odds(self, soup: BeautifulSoup, race_num: str, venue: str, date: str) -> Optional[Dict]:
        """Extract race data with odds from BeautifulSoup object"""
        try:
            # Find race title
            race_title = soup.find('h1') or soup.find('h2') or soup.find('h3')
            race_title_text = race_title.get_text(strip=True) if race_title else f"Race {race_num}"
            
            # Extract horse names and odds
            runners = []
            
            # Look for horse names in competitor elements
            competitor_elements = soup.find_all('span', class_='competitor-name')
            for i, competitor in enumerate(competitor_elements):
                horse_name = competitor.get_text(strip=True)
                if horse_name:
                    runners.append({
                        'runner_number': i + 1,
                        'runner_name': horse_name,
                        'odds': []
                    })
            
            # If no competitors found, try alternative method
            if not runners:
                # Look for horse names in the text
                full_text = soup.get_text(strip=True)
                horse_patterns = re.findall(r'(\d+)\.\s*([A-Za-z\s]+?)(?=\s*\(|\s*J:|$)', full_text)
                for i, (num, name) in enumerate(horse_patterns[:10]):  # Limit to 10 horses
                    if name.strip():
                        runners.append({
                            'runner_number': int(num),
                            'runner_name': name.strip(),
                            'odds': []
                        })
            
            # Extract odds data
            self.extract_odds_for_runners(soup, runners)
            
            race_data = {
                'venue': venue,
                'race_number': race_num,
                'race_time': 'Unknown',
                'date': date,
                'race_title': race_title_text,
                'runners': runners
            }
            
            logger.info(f"Extracted {len(runners)} runners with odds for {venue} Race {race_num}")
            return race_data
            
        except Exception as e:
            logger.error(f"Error extracting race data: {str(e)}")
            return None
    
    def extract_odds_for_runners(self, soup: BeautifulSoup, runners: List[Dict]):
        """Extract odds data for all runners"""
        try:
            # Bookmaker names in order
            bookmaker_names = [
                'TAB', 'TABtouch', 'Betr', 'BoomBet', 'BetfairBack', 'BetfairLay', 
                'Picklebet', 'Ladbrokes', 'PointsBet', 'Neds', 'Colossal', 'bet365'
            ]
            
            # Find all odds elements
            odds_elements = soup.find_all('div', class_='oc-table-td')
            
            # Extract odds values
            odds_values = []
            for element in odds_elements:
                text = element.get_text(strip=True)
                if text.startswith('bet') and text[3:].replace('.', '').isdigit():
                    try:
                        odds_value = float(text[3:])
                        odds_values.append(odds_value)
                    except ValueError:
                        continue
            
            # Distribute odds to runners
            odds_per_horse = 13  # 13 bookmakers
            for i, runner in enumerate(runners):
                start_idx = i * odds_per_horse
                end_idx = start_idx + odds_per_horse
                
                runner_odds = odds_values[start_idx:end_idx]
                
                # Create odds entries for this runner
                for j, odds_value in enumerate(runner_odds):
                    if j < len(bookmaker_names):
                        runner['odds'].append({
                            'bookmaker': bookmaker_names[j],
                            'odds': odds_value
                        })
            
            logger.info(f"Extracted odds for {len(runners)} runners")
            
        except Exception as e:
            logger.error(f"Error extracting odds: {str(e)}")
    
    def store_race_odds(self, race_data: Dict):
        """Store race odds in database"""
        conn = sqlite3.connect(self.betting_db_path)
        cursor = conn.cursor()
        
        try:
            for runner in race_data.get('runners', []):
                for odds_entry in runner.get('odds', []):
                    cursor.execute('''
                        INSERT OR REPLACE INTO scraped_odds 
                        (venue, race_number, race_time, race_date, horse_name, horse_number, bookmaker, odds)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        race_data['venue'],
                        race_data['race_number'],
                        race_data.get('race_time', 'Unknown'),
                        race_data['date'],
                        runner['runner_name'],
                        runner.get('runner_number', 0),
                        odds_entry['bookmaker'],
                        odds_entry['odds']
                    ))
            
            conn.commit()
            logger.info(f"Stored odds for {race_data['venue']} Race {race_data['race_number']}")
            
        except Exception as e:
            logger.error(f"Error storing odds: {str(e)}")
        finally:
            conn.close()
    
    def run_comprehensive_scrape(self):
        """Run comprehensive scraping for all today's races"""
        logger.info("Starting ultimate odds scraping...")
        
        # Get today's races from database
        todays_races = self.get_todays_races()
        
        if not todays_races:
            logger.warning("No races found for today")
            return
        
        # Group races by venue
        venues = list(set([race['venue'] for race in todays_races]))
        logger.info(f"Found races for venues: {venues}")
        
        total_races_scraped = 0
        failed_venues = []
        
        for venue in venues:
            try:
                logger.info(f"Scraping {venue}...")
                races = self.scrape_venue_races(venue)
                
                if races:
                    for race in races:
                        self.store_race_odds(race)
                        total_races_scraped += 1
                    
                    logger.info(f"✅ Completed {venue}: {len(races)} races")
                else:
                    logger.warning(f"❌ No races scraped for {venue}")
                    failed_venues.append(venue)
                
            except Exception as e:
                logger.error(f"Error scraping {venue}: {str(e)}")
                failed_venues.append(venue)
                continue
        
        # Summary
        logger.info(f"✅ Ultimate scraping completed: {total_races_scraped} races scraped")
        if failed_venues:
            logger.warning(f"❌ Failed venues: {failed_venues}")
    
    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()
            logger.info("Chrome driver closed")

def main():
    """Main function to run ultimate odds scraping"""
    scraper = UltimateOddsScraper()
    
    try:
        scraper.run_comprehensive_scrape()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
