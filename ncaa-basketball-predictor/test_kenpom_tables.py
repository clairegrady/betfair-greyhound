"""
Test what data is available on KenPom team pages
"""
import os
from dotenv import load_dotenv
from pathlib import Path
from kenpompy.utils import login, get_html
from bs4 import BeautifulSoup
import pandas as pd

load_dotenv(Path(__file__).parent / "config.env")
email = os.getenv('KENPOM_EMAIL')
password = os.getenv('KENPOM_PASSWORD')

print("Logging in to KenPom...")
browser = login(email, password)

# Test with Duke for 2025 season (24-25)
url = "https://kenpom.com/team.php?team=Duke&y=2025"
html_content = get_html(browser, url)
soup = BeautifulSoup(html_content, 'html5lib')

# Get ALL tables
tables = pd.read_html(str(soup), flavor='html5lib')

print(f"\n🔍 Found {len(tables)} tables on page\n")

for i, table in enumerate(tables):
    print(f"="*70)
    print(f"TABLE {i+1}:")
    print(f"Shape: {table.shape}")
    print(f"Columns: {list(table.columns)}")
    print(f"\nFirst 3 rows:")
    print(table.head(3))
    print()

