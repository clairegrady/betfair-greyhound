#!/usr/bin/env python3
"""
Price vs Results Tracker
Tracks last traded prices and compares them to actual race results
"""

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
        logging.FileHandler('price_results_tracker.log'),
        logging.StreamHandler()
    ]
)

class PriceResultsTracker:
    def __init__(self):
        self.db_path = 'price_results_tracking.db'
        self.setup_database()
        
    def setup_database(self):
        """Create database tables for tracking prices and results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for pre-race prices
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            horse_name TEXT,
            last_traded_price REAL,
            bookmaker TEXT,
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
            jockey_name TEXT,
            trainer_name TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Table for price vs results analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_date TEXT,
            venue TEXT,
            race_number INTEGER,
            horse_name TEXT,
            last_traded_price REAL,
            finishing_position INTEGER,
            placed INTEGER,
            price_rank INTEGER,
            performance_vs_price TEXT,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database setup complete")
    
    def get_todays_race_prices(self):
        """Get today's race prices from odds.com.au"""
        today = datetime.now().strftime('%Y-%m-%d')
        logging.info(f"Getting race prices for {today}")
        
        try:
            # Get main racing page
            url = "https://www.odds.com.au/horse-racing/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find race links
            race_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/horse-racing/' in href and today.replace('-', '') in href:
                    race_links.append(href)
            
            logging.info(f"Found {len(race_links)} race links for today")
            
            # Process first 10 races
            for i, race_url in enumerate(race_links[:10]):
                try:
                    self.process_race_prices(race_url, today)
                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logging.error(f"Error processing race {race_url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error getting main page: {e}")
    
    def process_race_prices(self, race_url, race_date):
        """Process a single race to get prices"""
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
            
            # Get prices data
            prices_data = self.get_prices_from_race(race_url)
            
            if not prices_data:
                logging.warning(f"No prices data found for {race_url}")
                return
            
            # Save prices
            for price_data in prices_data:
                self.save_price(
                    race_date, venue, race_number, race_name,
                    price_data['horse_name'], price_data['price'], price_data['bookmaker']
                )
                logging.info(f"Saved price: {price_data['horse_name']} - {price_data['price']} ({price_data['bookmaker']})")
            
        except Exception as e:
            logging.error(f"Error processing race {race_url}: {e}")
    
    def get_prices_from_race(self, race_url):
        """Get prices from a race page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(race_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for prices in various formats
            prices_data = []
            
            # Method 1: Look for prices in JavaScript
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'odds' in script.string.lower():
                    content = script.string
                    
                    # Look for patterns like "odds": 3.5
                    odds_pattern = r'"odds":\s*(\d+\.?\d*)'
                    horse_pattern = r'"name":\s*"([^"]+)"'
                    
                    odds_matches = re.findall(odds_pattern, content)
                    horse_matches = re.findall(horse_pattern, content)
                    
                    if odds_matches and horse_matches:
                        for i, (horse, odds) in enumerate(zip(horse_matches, odds_matches)):
                            if i < len(odds_matches):
                                prices_data.append({
                                    'horse_name': horse,
                                    'price': float(odds),
                                    'bookmaker': 'odds.com.au'
                                })
                        break
            
            # Method 2: Look for prices in HTML elements
            if not prices_data:
                odds_elements = soup.find_all(['div', 'span'], class_=re.compile(r'odds|price'))
                for element in odds_elements:
                    text = element.get_text().strip()
                    if re.match(r'^\d+\.?\d*$', text):
                        # Try to find associated horse name
                        parent = element.parent
                        if parent:
                            horse_name = parent.get_text().strip()
                            if horse_name and not re.match(r'^\d+\.?\d*$', horse_name):
                                prices_data.append({
                                    'horse_name': horse_name,
                                    'price': float(text),
                                    'bookmaker': 'odds.com.au'
                                })
            
            return prices_data
            
        except Exception as e:
            logging.error(f"Error getting prices from {race_url}: {e}")
            return []
    
    def save_price(self, race_date, venue, race_number, race_name, horse_name, price, bookmaker):
        """Save price to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO race_prices 
        (race_date, venue, race_number, race_name, horse_name, last_traded_price, bookmaker)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (race_date, venue, race_number, race_name, horse_name, price, bookmaker))
        
        conn.commit()
        conn.close()
    
    def get_race_results_from_racenet(self, race_date):
        """Get race results from racenet.com.au"""
        logging.info(f"Getting race results for {race_date}")
        
        try:
            # Get main results page
            url = "https://www.racenet.com.au/results/horse-racing"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find race result links
            race_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/results/horse-racing/' in href and race_date.replace('-', '') in href:
                    race_links.append(href)
            
            logging.info(f"Found {len(race_links)} race result links for {race_date}")
            
            # Process first 20 races
            for i, race_url in enumerate(race_links[:20]):
                try:
                    self.process_race_results(race_url, race_date)
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    logging.error(f"Error processing race results {race_url}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error getting results page: {e}")
    
    def process_race_results(self, race_url, race_date):
        """Process a single race to get results"""
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
            
            # Get results data
            results_data = self.get_results_from_race(race_url)
            
            if not results_data:
                logging.warning(f"No results data found for {race_url}")
                return
            
            # Save results
            for result_data in results_data:
                self.save_result(
                    race_date, venue, race_number, race_name,
                    result_data['horse_name'], result_data['position'],
                    result_data.get('jockey'), result_data.get('trainer')
                )
                logging.info(f"Saved result: {result_data['horse_name']} - {result_data['position']}")
            
        except Exception as e:
            logging.error(f"Error processing race results {race_url}: {e}")
    
    def get_results_from_race(self, race_url):
        """Get results from a race page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(race_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract results from text
            page_text = soup.get_text()
            lines = page_text.split('\n')
            
            results = []
            for line in lines:
                line = line.strip()
                # Look for position + horse name pattern
                pos_horse_match = re.search(r'(\d+)\.\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', line)
                if pos_horse_match:
                    position = int(pos_horse_match.group(1))
                    horse_name = pos_horse_match.group(2)
                    
                    # Clean up horse name (remove country codes)
                    horse_name = re.sub(r'\s*\([^)]*\)\s*', '', horse_name)
                    
                    results.append({
                        'position': position,
                        'horse_name': horse_name,
                        'jockey': None,
                        'trainer': None
                    })
            
            return results
            
        except Exception as e:
            logging.error(f"Error getting results from {race_url}: {e}")
            return []
    
    def save_result(self, race_date, venue, race_number, race_name, horse_name, position, jockey, trainer):
        """Save result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO race_results 
        (race_date, venue, race_number, race_name, horse_name, finishing_position, jockey_name, trainer_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (race_date, venue, race_number, race_name, horse_name, position, jockey, trainer))
        
        conn.commit()
        conn.close()
    
    def analyze_price_vs_results(self, race_date):
        """Analyze price vs results for a specific date"""
        conn = sqlite3.connect(self.db_path)
        
        # Get races with both prices and results
        query = '''
        SELECT 
            p.race_date,
            p.venue,
            p.race_number,
            p.horse_name,
            p.last_traded_price,
            r.finishing_position,
            CASE WHEN r.finishing_position <= 3 THEN 1 ELSE 0 END as placed
        FROM race_prices p
        LEFT JOIN race_results r ON p.race_date = r.race_date 
            AND p.venue = r.venue 
            AND p.race_number = r.race_number 
            AND p.horse_name = r.horse_name
        WHERE p.race_date = ? AND r.finishing_position IS NOT NULL
        ORDER BY p.venue, p.race_number, p.last_traded_price
        '''
        
        df = pd.read_sql_query(query, conn, params=(race_date,))
        conn.close()
        
        if len(df) == 0:
            logging.info(f"No completed races with both prices and results for {race_date}")
            return
        
        # Analyze by race
        analysis_results = []
        for (venue, race_number), race_data in df.groupby(['venue', 'race_number']):
            race_data = race_data.sort_values('last_traded_price')
            race_data['price_rank'] = range(1, len(race_data) + 1)
            
            for _, row in race_data.iterrows():
                # Determine performance vs price
                if row['placed'] == 1:
                    if row['price_rank'] <= 3:
                        performance = "Favored and Placed"
                    else:
                        performance = "Longshot and Placed"
                else:
                    if row['price_rank'] <= 3:
                        performance = "Favored but Unplaced"
                    else:
                        performance = "Longshot and Unplaced"
                
                analysis_results.append({
                    'race_date': row['race_date'],
                    'venue': venue,
                    'race_number': race_number,
                    'horse_name': row['horse_name'],
                    'last_traded_price': row['last_traded_price'],
                    'finishing_position': row['finishing_position'],
                    'placed': row['placed'],
                    'price_rank': row['price_rank'],
                    'performance_vs_price': performance
                })
        
        # Save analysis
        if analysis_results:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for result in analysis_results:
                cursor.execute('''
                INSERT INTO price_analysis 
                (race_date, venue, race_number, horse_name, last_traded_price, finishing_position, placed, price_rank, performance_vs_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result['race_date'], result['venue'], result['race_number'],
                    result['horse_name'], result['last_traded_price'], result['finishing_position'],
                    result['placed'], result['price_rank'], result['performance_vs_price']
                ))
            
            conn.commit()
            conn.close()
            
            # Print summary
            self.print_analysis_summary(analysis_results)
    
    def print_analysis_summary(self, analysis_results):
        """Print analysis summary"""
        df = pd.DataFrame(analysis_results)
        
        print(f"\n📊 PRICE VS RESULTS ANALYSIS")
        print("=" * 60)
        
        # Overall stats
        total_horses = len(df)
        placed_horses = len(df[df['placed'] == 1])
        place_rate = (placed_horses / total_horses * 100) if total_horses > 0 else 0
        
        print(f"Total horses analyzed: {total_horses}")
        print(f"Horses placed (1st-3rd): {placed_horses}")
        print(f"Overall place rate: {place_rate:.1f}%")
        
        # By price rank
        print(f"\nBy Price Rank (1=shortest odds):")
        for rank in [1, 2, 3, 4, 5]:
            rank_data = df[df['price_rank'] == rank]
            if len(rank_data) > 0:
                rank_placed = len(rank_data[rank_data['placed'] == 1])
                rank_rate = (rank_placed / len(rank_data) * 100)
                print(f"  Rank {rank}: {rank_placed}/{len(rank_data)} placed ({rank_rate:.1f}%)")
        
        # By performance category
        print(f"\nBy Performance Category:")
        for category in df['performance_vs_price'].unique():
            cat_data = df[df['performance_vs_price'] == category]
            print(f"  {category}: {len(cat_data)} horses")
        
        # Show some examples
        print(f"\nSample Results:")
        for _, row in df.head(10).iterrows():
            status = "✅ PLACED" if row['placed'] == 1 else "❌ UNPLACED"
            print(f"  {row['venue']} R{row['race_number']} - {row['horse_name']:20s} "
                  f"Price: {row['last_traded_price']:5.2f} (Rank {row['price_rank']}) "
                  f"→ {row['finishing_position']} {status}")

def main():
    tracker = PriceResultsTracker()
    
    print("🏇 PRICE VS RESULTS TRACKER")
    print("=" * 50)
    print("This tracks last traded prices and compares them to actual race results")
    print()
    
    while True:
        print("\nOptions:")
        print("1. Get today's race prices")
        print("2. Get race results for a date")
        print("3. Analyze price vs results for a date")
        print("4. Show analysis summary")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            tracker.get_todays_race_prices()
        elif choice == '2':
            date = input("Enter date (YYYY-MM-DD): ").strip()
            tracker.get_race_results_from_racenet(date)
        elif choice == '3':
            date = input("Enter date (YYYY-MM-DD): ").strip()
            tracker.analyze_price_vs_results(date)
        elif choice == '4':
            # Show recent analysis
            conn = sqlite3.connect(tracker.db_path)
            query = '''
            SELECT DISTINCT race_date 
            FROM price_analysis 
            ORDER BY race_date DESC 
            LIMIT 5
            '''
            dates = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(dates) > 0:
                print("Available dates for analysis:")
                for _, row in dates.iterrows():
                    print(f"  {row['race_date']}")
            else:
                print("No analysis data available")
        elif choice == '5':
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
