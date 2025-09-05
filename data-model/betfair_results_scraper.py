#!/usr/bin/env python3
"""
Betfair Racing Results Scraper
Scrapes detailed race results from Betfair's racing results page
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import sqlite3
import re
from urllib.parse import urljoin, urlparse

class BetfairResultsScraper:
    def __init__(self, db_path=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.db_path = db_path
        self.base_url = "https://www.betfair.com.au"
        
    def get_results_page(self, url="https://www.betfair.com.au/hub/racing/horse-racing/racing-results/"):
        """Get the main racing results page."""
        try:
            print(f"🏇 Fetching Betfair racing results from: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            print(f"✅ Successfully fetched page ({len(response.text)} characters)")
            return response.text
            
        except requests.RequestException as e:
            print(f"❌ Error fetching results page: {e}")
            return None
    
    def extract_race_links(self, html_content):
        """Extract links to individual race result pages."""
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        race_links = []
        
        try:
            # Look for race result links
            # Betfair might have different link patterns
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                link_text = link.get_text().strip()
                
                # Look for racing-related URLs
                if any(keyword in href.lower() for keyword in ['racing', 'results', 'race', 'horse']):
                    full_url = urljoin(self.base_url, href)
                    race_links.append({
                        'url': full_url,
                        'text': link_text,
                        'href': href
                    })
            
            print(f"🔍 Found {len(race_links)} potential racing links")
            
            # Also look for any table or list elements that might contain race data
            race_elements = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'race|result|card|meeting', re.I))
            print(f"🔍 Found {len(race_elements)} potential race elements")
            
        except Exception as e:
            print(f"❌ Error extracting race links: {e}")
            
        return race_links
    
    def get_race_results(self, race_url):
        """Get detailed results for a specific race."""
        try:
            print(f"🏇 Fetching race results from: {race_url}")
            response = self.session.get(race_url, timeout=30)
            response.raise_for_status()
            
            print(f"✅ Successfully fetched race page ({len(response.text)} characters)")
            return self.parse_race_page(response.text, race_url)
            
        except requests.RequestException as e:
            print(f"❌ Error fetching race results: {e}")
            return None
    
    def parse_race_page(self, html_content, race_url):
        """Parse individual race result page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            race_info = {
                'url': race_url,
                'course': None,
                'date': None,
                'race_name': None,
                'distance': None,
                'going': None,
                'prize_money': None,
                'runners': []
            }
            
            # Extract race information from page content
            page_text = soup.get_text()
            
            # Look for course name
            course_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:Racecourse|Track|Racing)', page_text)
            if course_match:
                race_info['course'] = course_match.group(1)
            
            # Look for date
            date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', page_text)
            if date_match:
                race_info['date'] = date_match.group(1)
            
            # Look for distance
            distance_match = re.search(r'(\d+)\s*(?:m|metres?|meters?)', page_text, re.I)
            if distance_match:
                race_info['distance'] = f"{distance_match.group(1)}m"
            
            # Look for going/conditions
            going_match = re.search(r'(Good|Heavy|Soft|Firm|Dead|Slow|Fast)\s*(?:Track|Going|Surface)?', page_text, re.I)
            if going_match:
                race_info['going'] = going_match.group(1)
            
            # Look for prize money
            prize_match = re.search(r'\$([\d,]+)', page_text)
            if prize_match:
                race_info['prize_money'] = prize_match.group(1)
            
            # Extract runners
            runners = self.extract_runners_from_page(soup, page_text)
            race_info['runners'] = runners
            
            return race_info
            
        except Exception as e:
            print(f"❌ Error parsing race page: {e}")
            return None
    
    def extract_runners_from_page(self, soup, page_text):
        """Extract runner information from race page."""
        runners = []
        
        try:
            # Look for result tables
            tables = soup.find_all('table')
            
            for table in tables:
                table_runners = self.extract_runners_from_table(table)
                if table_runners:
                    runners.extend(table_runners)
            
            # If no table data found, try text-based extraction
            if not runners:
                runners = self.extract_runners_from_text(page_text)
            
        except Exception as e:
            print(f"❌ Error extracting runners from page: {e}")
            
        return runners
    
    def extract_runners_from_table(self, table):
        """Extract runner information from a table."""
        runners = []
        
        try:
            rows = table.find_all('tr')
            if len(rows) < 2:
                return runners
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 4:
                    runner_info = self.extract_runner_from_cells(cells)
                    if runner_info:
                        runners.append(runner_info)
            
        except Exception as e:
            print(f"❌ Error extracting runners from table: {e}")
            
        return runners
    
    def extract_runner_from_cells(self, cells):
        """Extract runner information from table cells."""
        try:
            runner_info = {
                'position': None,
                'horse_name': None,
                'jockey': None,
                'trainer': None,
                'weight': None,
                'bsp': None,  # Betfair Starting Price
                'tote_price': None,
                'time': None,
                'margin': None
            }
            
            # Extract position from first cell
            if cells[0]:
                pos_text = cells[0].get_text().strip()
                pos_match = re.search(r'(\d+)', pos_text)
                if pos_match:
                    runner_info['position'] = int(pos_match.group(1))
            
            # Extract horse name from second cell
            if len(cells) > 1 and cells[1]:
                horse_text = cells[1].get_text().strip()
                # Clean up horse name
                horse_name = re.sub(r'\s*\([^)]*\)\s*', '', horse_text)  # Remove country codes
                if horse_name:
                    runner_info['horse_name'] = horse_name
            
            # Extract jockey from third cell
            if len(cells) > 2 and cells[2]:
                jockey_text = cells[2].get_text().strip()
                if jockey_text:
                    runner_info['jockey'] = jockey_text
            
            # Extract trainer from fourth cell
            if len(cells) > 3 and cells[3]:
                trainer_text = cells[3].get_text().strip()
                if trainer_text:
                    runner_info['trainer'] = trainer_text
            
            # Extract BSP, tote price, weight, time from remaining cells
            for cell in cells[4:]:
                cell_text = cell.get_text().strip()
                
                # Look for BSP (Betfair Starting Price)
                bsp_match = re.search(r'BSP[:\s]*(\d+\.?\d*)', cell_text, re.I)
                if bsp_match:
                    runner_info['bsp'] = bsp_match.group(1)
                
                # Look for tote price
                tote_match = re.search(r'Tote[:\s]*(\d+\.?\d*)', cell_text, re.I)
                if tote_match:
                    runner_info['tote_price'] = tote_match.group(1)
                
                # Look for weight
                weight_match = re.search(r'(\d+\.?\d*)kg', cell_text)
                if weight_match:
                    runner_info['weight'] = weight_match.group(1)
                
                # Look for time
                time_match = re.search(r'(\d+:\d+\.\d+)', cell_text)
                if time_match:
                    runner_info['time'] = time_match.group(1)
                
                # Look for margin
                margin_match = re.search(r'(\d+\.?\d*)\s*(?:lengths?|len)', cell_text, re.I)
                if margin_match:
                    runner_info['margin'] = margin_match.group(1)
            
            return runner_info if runner_info['position'] or runner_info['horse_name'] else None
            
        except Exception as e:
            print(f"❌ Error extracting runner from cells: {e}")
            return None
    
    def extract_runners_from_text(self, text):
        """Extract runner information from page text."""
        runners = []
        
        try:
            # Look for result patterns in text
            # Pattern: position, horse name, jockey, trainer, BSP, tote price, etc.
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for position + horse name pattern
                pos_horse_match = re.search(r'(\d+)\.\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', line)
                if pos_horse_match:
                    position = int(pos_horse_match.group(1))
                    horse_name = pos_horse_match.group(2)
                    
                    # Clean up horse name
                    horse_name = re.sub(r'\s*\([^)]*\)\s*', '', horse_name)
                    
                    runner_info = {
                        'position': position,
                        'horse_name': horse_name,
                        'jockey': None,
                        'trainer': None,
                        'weight': None,
                        'bsp': None,
                        'tote_price': None,
                        'time': None,
                        'margin': None
                    }
                    
                    # Look for BSP in the same line
                    bsp_match = re.search(r'BSP[:\s]*(\d+\.?\d*)', line, re.I)
                    if bsp_match:
                        runner_info['bsp'] = bsp_match.group(1)
                    
                    # Look for tote price in the same line
                    tote_match = re.search(r'Tote[:\s]*(\d+\.?\d*)', line, re.I)
                    if tote_match:
                        runner_info['tote_price'] = tote_match.group(1)
                    
                    # Look for weight in the same line
                    weight_match = re.search(r'(\d+\.?\d*)kg', line)
                    if weight_match:
                        runner_info['weight'] = weight_match.group(1)
                    
                    runners.append(runner_info)
            
        except Exception as e:
            print(f"❌ Error extracting runners from text: {e}")
            
        return runners
    
    def save_to_database(self, results):
        """Save results to database."""
        if not self.db_path:
            print("⚠️ No database path provided, skipping save")
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS betfair_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    course TEXT,
                    date TEXT,
                    race_name TEXT,
                    distance TEXT,
                    going TEXT,
                    prize_money TEXT,
                    position INTEGER,
                    horse_name TEXT,
                    jockey TEXT,
                    trainer TEXT,
                    weight TEXT,
                    bsp TEXT,
                    tote_price TEXT,
                    time TEXT,
                    margin TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert results
            total_runners = 0
            for race in results:
                for runner in race.get('runners', []):
                    cursor.execute('''
                        INSERT INTO betfair_results 
                        (url, course, date, race_name, distance, going, prize_money, position, horse_name, jockey, trainer, weight, bsp, tote_price, time, margin)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        race.get('url'),
                        race.get('course'),
                        race.get('date'),
                        race.get('race_name'),
                        race.get('distance'),
                        race.get('going'),
                        race.get('prize_money'),
                        runner.get('position'),
                        runner.get('horse_name'),
                        runner.get('jockey'),
                        runner.get('trainer'),
                        runner.get('weight'),
                        runner.get('bsp'),
                        runner.get('tote_price'),
                        runner.get('time'),
                        runner.get('margin')
                    ))
                    total_runners += 1
            
            conn.commit()
            print(f"✅ Saved {len(results)} races with {total_runners} runners to database")
            
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
        finally:
            if conn:
                conn.close()
    
    def scrape_results(self, max_races=10):
        """Scrape race results from Betfair."""
        print("🏇 Starting to scrape Betfair racing results...")
        
        # Get main results page
        html_content = self.get_results_page()
        if not html_content:
            return []
        
        # Extract race links
        race_links = self.extract_race_links(html_content)
        if not race_links:
            print("❌ No race links found")
            return []
        
        # Limit to max_races for testing
        race_links = race_links[:max_races]
        
        # Get results for each race
        results = []
        for i, race_link in enumerate(race_links):
            print(f"\n{'='*60}")
            print(f"🏇 Processing race {i+1}/{len(race_links)}")
            print(f"URL: {race_link['url']}")
            print(f"Text: {race_link['text']}")
            print(f"{'='*60}")
            
            race_result = self.get_race_results(race_link['url'])
            if race_result:
                results.append(race_result)
                print(f"✅ Found {len(race_result.get('runners', []))} runners")
            else:
                print(f"❌ No results found")
            
            # Polite delay between requests
            time.sleep(2)
        
        # Save to database if path provided
        if self.db_path:
            self.save_to_database(results)
        
        return results

def main():
    # Initialize scraper with database path
    db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/racing_data.db"
    scraper = BetfairResultsScraper(db_path)
    
    # Scrape results (limit to 5 races for testing)
    results = scraper.scrape_results(max_races=5)
    
    print(f"\n📊 SCRAPING SUMMARY:")
    print(f"  🏇 Races processed: {len(results)}")
    
    # Print sample results
    for i, race in enumerate(results[:3]):
        print(f"\n🏆 Race {i+1}:")
        print(f"  Course: {race.get('course', 'Unknown')}")
        print(f"  Date: {race.get('date', 'Unknown')}")
        print(f"  Race Name: {race.get('race_name', 'Unknown')}")
        print(f"  Distance: {race.get('distance', 'Unknown')}")
        print(f"  Going: {race.get('going', 'Unknown')}")
        print(f"  Prize Money: {race.get('prize_money', 'Unknown')}")
        print(f"  Runners: {len(race.get('runners', []))}")
        
        # Print first 3 runners
        for j, runner in enumerate(race.get('runners', [])[:3]):
            print(f"    {j+1}. {runner.get('horse_name', 'Unknown')} - {runner.get('position', 'Unknown')} - BSP: {runner.get('bsp', 'Unknown')} - Tote: {runner.get('tote_price', 'Unknown')}")

if __name__ == "__main__":
    main()
