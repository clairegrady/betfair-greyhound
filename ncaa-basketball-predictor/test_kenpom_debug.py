from kenpompy.utils import login, get_html
from bs4 import BeautifulSoup
import pandas as pd
import os

print("Testing KenPom scraper on a failing team: Bellarmine")
print("="*70 + "\n")

# Hardcode credentials (we know they work)
email = os.environ.get('KENPOM_EMAIL', 'clairegrady@me.com')
password = os.environ.get('KENPOM_PASSWORD')

if not password:
    print("❌ No KENPOM_PASSWORD environment variable!")
    exit(1)

print(f"✅ Using credentials for: {email}")

try:
    browser = login(email, password)
    print("✅ Logged in\n")
    
    # Try Bellarmine for season 2025 (24-25)
    team_name = "Bellarmine"
    season = 2025
    url = f"https://kenpom.com/team.php?team={team_name}&y={season}"
    
    print(f"URL: {url}\n")
    
    html_content = get_html(browser, url)
    soup = BeautifulSoup(html_content, 'html5lib')
    
    # Try to find tables
    from io import StringIO
    tables = pd.read_html(StringIO(str(soup)), flavor='html5lib')
    
    print(f"Number of tables found: {len(tables)}\n")
    
    if len(tables) > 0:
        print("Table columns found:")
        for i, table in enumerate(tables):
            print(f"\nTable {i}: {list(table.columns)[:10]}")  # First 10 columns
            
            if '%Min' in table.columns:
                print(f"  ✅ Found player stats table!")
                print(f"  Rows: {len(table)}")
                print(f"\nFirst few rows:")
                print(table.head(3))
    else:
        print("❌ NO TABLES FOUND")
        print("\nFirst 1000 chars of HTML:")
        print(html_content[:1000])
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
