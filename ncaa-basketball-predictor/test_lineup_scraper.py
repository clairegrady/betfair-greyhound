"""
Test lineup scraper on one game before running full scrape
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path
from io import StringIO

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


def test_scrape_duke_houston():
    """
    Test: 2024-03-30: Duke @ Houston (54-51)
    Should be available on Sports Reference
    """
    
    print("\n" + "="*70)
    print("🧪 TEST: Scraping Duke vs Houston (2024-03-30)")
    print("="*70 + "\n")
    
    # Try different URL patterns
    urls_to_try = [
        "https://www.sports-reference.com/cbb/boxscores/2024-03-30-duke.html",
        "https://www.sports-reference.com/cbb/boxscores/2024-03-30-houston.html",
        "https://www.sports-reference.com/cbb/boxscores/2024-03-30-19-houston.html",
    ]
    
    for url in urls_to_try:
        print(f"Trying: {url}")
        
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ Found box score!\n")
                
                # Parse the HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all stat tables
                tables = soup.find_all('table', {'class': 'stats_table'})
                print(f"  Found {len(tables)} stat tables\n")
                
                for i, table in enumerate(tables):
                    table_id = table.get('id', 'Unknown')
                    print(f"  Table {i+1}: {table_id}")
                    
                    # Try to parse with pandas
                    try:
                        df = pd.read_html(StringIO(str(table)))[0]
                        print(f"    Rows: {len(df)}")
                        print(f"    Columns: {list(df.columns)[:5]}")  # First 5 columns
                        
                        # Show first few players
                        print(f"\n    Sample players:")
                        for idx in range(min(5, len(df))):
                            if 'Player' in df.columns:
                                player = df.iloc[idx]['Player']
                                mp = df.iloc[idx].get('MP', 'N/A')
                                pts = df.iloc[idx].get('PTS', 'N/A')
                                print(f"      {player}: {mp} min, {pts} pts")
                        
                        print()
                        
                    except Exception as e:
                        print(f"    Error parsing: {e}\n")
                
                return True
                
        except requests.RequestException as e:
            print(f"  ❌ Request failed: {e}\n")
        except Exception as e:
            print(f"  ❌ Error: {e}\n")
    
    print("❌ Could not find box score\n")
    return False


if __name__ == "__main__":
    test_scrape_duke_houston()

