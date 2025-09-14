#!/usr/bin/env python3
"""
Get Australian race results from September 10th, 2025
"""

import requests
from bs4 import BeautifulSoup
import re
import sqlite3
import json
from datetime import datetime, timedelta

class YesterdayResultsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.base_url = "https://www.racenet.com.au"
        
    def get_race_results(self, race_url):
        """Get detailed results for a specific race."""
        try:
            print(f"🏇 Fetching: {race_url}")
            response = self.session.get(race_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract race info from URL
            url_parts = race_url.split('/')
            venue = url_parts[-2].replace('-20250910', '') if len(url_parts) > 1 else "Unknown"
            race_name = url_parts[-1] if len(url_parts) > 0 else "Unknown"
            
            # Try to extract race number
            race_number = 1
            race_match = re.search(r'race-(\d+)', race_url)
            if race_match:
                race_number = int(race_match.group(1))
            
            # Look for results table
            results = []
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Check if this looks like a results table
                header_row = rows[0]
                header_text = header_row.get_text().lower()
                if any(word in header_text for word in ['position', 'horse', 'jockey', 'trainer', 'finish']):
                    
                    for row in rows[1:]:  # Skip header
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 3:
                            result = self.extract_result_from_row(cells)
                            if result:
                                result['venue'] = venue
                                result['race_number'] = race_number
                                result['race_name'] = race_name
                                results.append(result)
                    break
            
            # If no table found, try text-based extraction
            if not results:
                results = self.extract_results_from_text(soup.get_text(), venue, race_number, race_name)
            
            print(f"✅ Found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"❌ Error fetching {race_url}: {e}")
            return []
    
    def extract_result_from_row(self, cells):
        """Extract result from table row."""
        try:
            result = {
                'position': None,
                'horse_name': None,
                'jockey': None,
                'trainer': None,
                'weight': None,
                'odds': None,
                'margin': None
            }
            
            # Position from first cell
            if cells[0]:
                pos_text = cells[0].get_text().strip()
                pos_match = re.search(r'(\d+)', pos_text)
                if pos_match:
                    result['position'] = int(pos_match.group(1))
            
            # Horse name from second cell
            if len(cells) > 1 and cells[1]:
                horse_text = cells[1].get_text().strip()
                # Clean up horse name
                horse_name = re.sub(r'\s*\([^)]*\)\s*', '', horse_text)
                if horse_name:
                    result['horse_name'] = horse_name
            
            # Jockey from third cell
            if len(cells) > 2 and cells[2]:
                jockey_text = cells[2].get_text().strip()
                if jockey_text:
                    result['jockey'] = jockey_text
            
            # Trainer from fourth cell
            if len(cells) > 3 and cells[3]:
                trainer_text = cells[3].get_text().strip()
                if trainer_text:
                    result['trainer'] = trainer_text
            
            # Look for weight, odds, margin in remaining cells
            for cell in cells[4:]:
                cell_text = cell.get_text().strip()
                
                # Weight
                weight_match = re.search(r'(\d+\.?\d*)kg', cell_text)
                if weight_match:
                    result['weight'] = weight_match.group(1)
                
                # Odds
                odds_match = re.search(r'(\d+\.?\d*|\d+/\d+)', cell_text)
                if odds_match and not result['weight']:
                    result['odds'] = odds_match.group(1)
                
                # Margin
                margin_match = re.search(r'(\d+\.?\d*)\s*(?:lengths?|len)', cell_text, re.I)
                if margin_match:
                    result['margin'] = margin_match.group(1)
            
            return result if result['position'] and result['horse_name'] else None
            
        except Exception as e:
            print(f"❌ Error extracting result: {e}")
            return None
    
    def extract_results_from_text(self, text, venue, race_number, race_name):
        """Extract results from page text."""
        results = []
        
        try:
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
                    
                    result = {
                        'position': position,
                        'horse_name': horse_name,
                        'jockey': None,
                        'trainer': None,
                        'weight': None,
                        'odds': None,
                        'margin': None,
                        'venue': venue,
                        'race_number': race_number,
                        'race_name': race_name
                    }
                    
                    # Look for additional info in the same line
                    jockey_match = re.search(r'J:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', line)
                    if jockey_match:
                        result['jockey'] = jockey_match.group(1)
                    
                    weight_match = re.search(r'(\d+\.?\d*)kg', line)
                    if weight_match:
                        result['weight'] = weight_match.group(1)
                    
                    odds_match = re.search(r'\$(\d+\.?\d*)', line)
                    if odds_match:
                        result['odds'] = odds_match.group(1)
                    
                    results.append(result)
            
        except Exception as e:
            print(f"❌ Error extracting from text: {e}")
            
        return results
    
    def get_australian_races_from_yesterday(self):
        """Get all Australian races from September 10th, 2025."""
        yesterday_short = "20250910"
        
        print(f"🏇 Getting Australian races from {yesterday_short}")
        
        url = 'https://www.racenet.com.au/results/horse-racing'
        response = self.session.get(url, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find Australian race links
        australian_races = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/results/horse-racing/' in href and yesterday_short in href:
                # Check if it's Australian
                if any(venue in href.lower() for venue in ['sandown', 'canterbury', 'ipswich', 'balaklava', 'belmont', 'geelong', 'hawkesbury', 'goulburn', 'warwick', 'bunbury', 'lismore', 'bordertown', 'tuncurry', 'mackay']):
                    australian_races.append({
                        'url': f'https://www.racenet.com.au{href}',
                        'text': link.get_text().strip()
                    })
        
        print(f"Found {len(australian_races)} Australian races")
        return australian_races
    
    def save_results_to_db(self, all_results):
        """Save results to database."""
        conn = sqlite3.connect('yesterday_results.db')
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS race_results_20250910 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue TEXT,
            race_number INTEGER,
            race_name TEXT,
            position INTEGER,
            horse_name TEXT,
            jockey TEXT,
            trainer TEXT,
            weight TEXT,
            odds TEXT,
            margin TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert results
        for result in all_results:
            cursor.execute('''
            INSERT INTO race_results_20250910 
            (venue, race_number, race_name, position, horse_name, jockey, trainer, weight, odds, margin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.get('venue'),
                result.get('race_number'),
                result.get('race_name'),
                result.get('position'),
                result.get('horse_name'),
                result.get('jockey'),
                result.get('trainer'),
                result.get('weight'),
                result.get('odds'),
                result.get('margin')
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Saved {len(all_results)} results to database")
    
    def run(self):
        """Run the scraper."""
        print("🏇 GETTING AUSTRALIAN RACE RESULTS FROM SEPTEMBER 10TH, 2025")
        print("=" * 70)
        
        # Get race URLs
        races = self.get_australian_races_from_yesterday()
        
        if not races:
            print("❌ No Australian races found")
            return
        
        # Get results for each race
        all_results = []
        
        for i, race in enumerate(races[:20]):  # Limit to first 20 races
            print(f"\n{'='*60}")
            print(f"🏇 Processing race {i+1}/{min(20, len(races))}")
            print(f"Text: {race['text']}")
            print(f"{'='*60}")
            
            results = self.get_race_results(race['url'])
            all_results.extend(results)
            
            # Show sample results
            if results:
                print(f"Sample results:")
                for result in results[:3]:
                    print(f"  {result['position']}. {result['horse_name']} - {result.get('jockey', 'Unknown')}")
        
        # Save to database
        if all_results:
            self.save_results_to_db(all_results)
            
            # Show summary
            print(f"\n📊 SUMMARY:")
            print(f"Total races processed: {len(races[:20])}")
            print(f"Total results: {len(all_results)}")
            
            # Show venues
            venues = set(result['venue'] for result in all_results)
            print(f"Venues: {', '.join(sorted(venues))}")
            
            # Show Sandown results specifically
            sandown_results = [r for r in all_results if 'sandown' in r['venue'].lower()]
            if sandown_results:
                print(f"\n🏆 SANDOWN RESULTS:")
                for result in sandown_results:
                    print(f"  R{result['race_number']} - {result['position']}. {result['horse_name']} - {result.get('jockey', 'Unknown')}")
        else:
            print("❌ No results found")

def main():
    scraper = YesterdayResultsScraper()
    scraper.run()

if __name__ == "__main__":
    main()
