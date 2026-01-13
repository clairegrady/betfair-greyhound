"""
Betfair Comments Scraper - Extracts runner comments/blurbs from Betfair markets
These comments contain valuable sentiment analysis that can be used for automated betting
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import re
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BetfairCommentsScraper:
    """
    Scrapes runner comments from Betfair exchange markets
    """
    
    def __init__(self, db_path: str = None, username: str = None, password: str = None, headless: bool = True):
        self.base_url = "https://www.betfair.com.au/exchange/plus/horse-racing/market/"
        self.login_url = "https://identitysso.betfair.com.au/view/login"
        self.db_path = db_path or "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/race_info.db"
        self.username = username
        self.password = password
        self.headless = headless
        self.driver = None
        
        # Sentiment keywords for classification
        self.negative_keywords = [
            'doubt', 'not among', 'making up the numbers', 'unlikely', 'hard to see',
            'will struggle', 'poor', 'no chance', 'difficult', 'tough ask', 
            'will be tough', 'long odds', 'not expected', 'hard to recommend'
        ]
        
        self.positive_keywords = [
            'no excuses', 'tough to beat', 'looks the goods', 'strong chance',
            'main danger', 'hard to beat', 'should win', 'top chance', 'leading hope',
            'can win', 'will take beating', 'looks well placed', 'worth considering'
        ]
        
        self.neutral_keywords = [
            'stays in the mix', 'keep safe', 'place prospects', 'deserves another chance',
            'can improve', 'each-way', 'keep in mind', 'don\'t dismiss'
        ]
    
    def extract_market_id_from_url(self, url: str) -> Optional[str]:
        """Extract market ID from Betfair URL"""
        match = re.search(r'/market/(\d+\.\d+)', url)
        if match:
            return match.group(1)
        return None
    
    def setup_driver(self):
        """Setup Selenium Chrome driver"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless=new')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Disable automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logger.info("Chrome driver initialized")
    
    def login(self) -> bool:
        """
        Login to Betfair using Selenium
        
        Returns:
            True if login successful, False otherwise
        """
        if not self.username or not self.password:
            logger.warning("No credentials provided, skipping login")
            return False
        
        logger.info("Attempting to login to Betfair...")
        
        try:
            self.driver.get("https://www.betfair.com.au/exchange")
            time.sleep(2)
            
            # Wait for and fill in username
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[placeholder*='email'], input[placeholder*='username']"))
            )
            username_field.send_keys(self.username)
            
            # Fill in password
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.send_keys(self.password)
            
            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button:contains('Log In')")
            login_button.click()
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login was successful (look for logout button or user account info)
            if "login" not in self.driver.current_url.lower():
                logger.info("Login successful!")
                return True
            else:
                logger.warning("Login may have failed")
                return False
            
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
    
    def scrape_market(self, market_id: str) -> Dict:
        """
        Scrape a specific Betfair market for runner comments
        
        Args:
            market_id: Betfair market ID (e.g., '1.252447747')
            
        Returns:
            Dictionary containing race info and runner comments
        """
        url = f"{self.base_url}{market_id}"
        logger.info(f"Scraping market: {url}")
        
        try:
            # Setup driver if not already done
            if not self.driver:
                self.setup_driver()
            
            # Login if credentials provided
            if self.username and self.password:
                self.login()
            
            # Navigate to market page
            self.driver.get(url)
            logger.info("Page loaded, waiting for content...")
            
            # Close any welcome popups
            try:
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close'], .close-button, button:has(svg)")
                for btn in close_buttons:
                    try:
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(1)
                            logger.info("Closed popup")
                    except:
                        pass
            except:
                pass
            
            # Wait for page to load
            time.sleep(3)
            
            # Click all runner dropdown arrows to expand comments
            logger.info("Expanding all runner dropdowns...")
            self._expand_all_dropdowns()
            
            # Wait for content to load
            time.sleep(2)
            
            # Get page source and parse
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract race title
            race_title = self._extract_race_title(soup)
            
            # Extract runners and their comments
            runners = self._extract_runner_comments(soup)
            
            # Extract race analysis (overall commentary)
            race_analysis = self._extract_race_analysis(soup)
            
            result = {
                'market_id': market_id,
                'race_title': race_title,
                'scraped_at': datetime.now().isoformat(),
                'race_analysis': race_analysis,
                'runners': runners,
                'url': url
            }
            
            logger.info(f"Successfully scraped {len(runners)} runners")
            return result
            
        except Exception as e:
            logger.error(f"Error scraping market {market_id}: {e}")
            raise
    
    def _expand_all_dropdowns(self):
        """Click all dropdown arrows to expand runner comments"""
        try:
            # Find all dropdown elements (arrows)
            # Look for SVG elements with class containing "dropdown" or "arrow"
            dropdowns = self.driver.find_elements(By.CSS_SELECTOR, 
                "svg[class*='dropdown'], svg[data-icon='arrow'], svg[class*='runner-timeform-info-dropdown-icon']")
            
            logger.info(f"Found {len(dropdowns)} dropdown arrows")
            
            # Click each dropdown
            for i, dropdown in enumerate(dropdowns):
                try:
                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
                    time.sleep(0.2)
                    
                    # Check if already expanded
                    parent = dropdown.find_element(By.XPATH, "..")
                    classes = parent.get_attribute("class") or ""
                    
                    if "expanded" not in classes.lower():
                        # Click the parent element or the dropdown itself
                        try:
                            dropdown.click()
                        except:
                            # If direct click fails, try clicking parent
                            parent.click()
                        
                        time.sleep(0.3)
                        logger.info(f"Expanded dropdown {i+1}/{len(dropdowns)}")
                except Exception as e:
                    logger.debug(f"Could not click dropdown {i+1}: {e}")
                    continue
            
            logger.info("All dropdowns expanded")
            
        except Exception as e:
            logger.warning(f"Error expanding dropdowns: {e}")
            # Continue anyway - some content may still be visible
    
    def _extract_race_title(self, soup: BeautifulSoup) -> str:
        """Extract race title from page"""
        # Try multiple selectors
        title_selectors = [
            'title',
            'h1',
            '[class*="race-title"]',
            '[class*="market-title"]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Clean up title
                if 'Betfair' in text:
                    # Extract just the race part
                    match = re.search(r'(\d+:\d+.*?(?:R\d+|Race \d+).*?)(?:Betting|»)', text)
                    if match:
                        return match.group(1).strip()
                return text
        
        return "Unknown Race"
    
    def _extract_race_analysis(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the overall race analysis commentary"""
        # Look for "Race Analysis" section
        text = soup.get_text()
        
        # Find race analysis section
        match = re.search(r'Race Analysis\s+(.*?)(?:Runner Comments|Selections|About Betfair)', text, re.DOTALL)
        if match:
            analysis = match.group(1).strip()
            # Clean up whitespace
            analysis = re.sub(r'\s+', ' ', analysis)
            return analysis
        
        return None
    
    def _extract_runner_comments(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract individual runner comments from the page"""
        text = soup.get_text()
        runners = []
        
        # Find the "Runner Comments" section
        runner_section_match = re.search(r'Runner Comments\s+(.*?)(?:About Betfair|Betfair Pty Limited)', text, re.DOTALL)
        
        if not runner_section_match:
            logger.warning("Could not find Runner Comments section")
            return runners
        
        runner_text = runner_section_match.group(1)
        
        # More sophisticated parsing: Look for pattern "HorseName\nComment text ending with period."
        # Each comment typically ends with a period followed by newline or next horse name
        
        # Split into blocks by looking for Title Case names followed by long text
        blocks = re.split(r'\n([A-Z][a-z]+(?:\s+[A-Z][a-z\']+){0,4})\n', runner_text)
        
        # Process blocks (they come in pairs: text before, horse name, comment)
        i = 1  # Start at 1 to skip any text before first horse
        while i < len(blocks) - 1:
            horse_name = blocks[i].strip()
            comment = blocks[i + 1].strip()
            
            # Clean up the comment (remove extra whitespace)
            comment = re.sub(r'\s+', ' ', comment)
            
            # Only add if we have substantial comment
            if comment and len(comment) > 20:
                runners.append({
                    'horse_name': horse_name,
                    'comment': comment,
                    'sentiment': self._classify_sentiment(comment),
                    'last_sentence': self._extract_last_sentence(comment)
                })
            
            i += 2
        
        return runners
    
    def _extract_last_sentence(self, comment: str) -> str:
        """Extract the last sentence which usually contains the key sentiment"""
        sentences = re.split(r'[.!?]\s+', comment)
        if sentences:
            # Return last non-empty sentence
            for sentence in reversed(sentences):
                if sentence.strip():
                    return sentence.strip()
        return comment
    
    def _classify_sentiment(self, comment: str) -> str:
        """
        Classify the sentiment of a runner comment
        
        Returns: 'negative', 'positive', 'neutral'
        """
        comment_lower = comment.lower()
        
        # Check negative keywords first (these are often stronger indicators)
        for keyword in self.negative_keywords:
            if keyword in comment_lower:
                return 'negative'
        
        # Check positive keywords
        for keyword in self.positive_keywords:
            if keyword in comment_lower:
                return 'positive'
        
        # Check neutral keywords
        for keyword in self.neutral_keywords:
            if keyword in comment_lower:
                return 'neutral'
        
        # Default to neutral if no clear sentiment
        return 'neutral'
    
    def save_to_database(self, market_data: Dict):
        """Save scraped market data to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create consolidated betfair_comments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS betfair_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                race_title TEXT,
                race_analysis TEXT,
                horse_name TEXT,
                comment TEXT,
                last_sentence TEXT,
                sentiment TEXT,
                scraped_at TEXT,
                url TEXT,
                UNIQUE(market_id, horse_name)
            )
        ''')
        
        # Insert runner comments with race info
        for runner in market_data['runners']:
            cursor.execute('''
                INSERT OR REPLACE INTO betfair_comments
                (market_id, race_title, race_analysis, horse_name, comment, last_sentence, sentiment, scraped_at, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market_data['market_id'],
                market_data['race_title'],
                market_data.get('race_analysis'),
                runner['horse_name'],
                runner['comment'],
                runner['last_sentence'],
                runner['sentiment'],
                market_data['scraped_at'],
                market_data['url']
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved market {market_data['market_id']} to database: {self.db_path}")
    
    def get_lay_betting_candidates(self, market_data: Dict, max_lay_odds: float = 50.0) -> List[Dict]:
        """
        Identify potential lay betting candidates based on negative sentiment
        
        Args:
            market_data: Market data from scrape_market()
            max_lay_odds: Maximum lay odds to consider (default 50)
            
        Returns:
            List of potential lay candidates with reasons
        """
        candidates = []
        
        for runner in market_data['runners']:
            if runner['sentiment'] == 'negative':
                candidates.append({
                    'horse_name': runner['horse_name'],
                    'reason': runner['last_sentence'],
                    'full_comment': runner['comment'],
                    'sentiment': runner['sentiment']
                })
        
        return candidates
    
    def print_market_summary(self, market_data: Dict):
        """Print a formatted summary of the market"""
        print(f"\n{'='*80}")
        print(f"RACE: {market_data['race_title']}")
        print(f"Market ID: {market_data['market_id']}")
        print(f"Scraped: {market_data['scraped_at']}")
        print(f"{'='*80}\n")
        
        if market_data.get('race_analysis'):
            print("RACE ANALYSIS:")
            print(f"{market_data['race_analysis']}\n")
        
        print("RUNNER COMMENTS:")
        print(f"{'-'*80}")
        
        for runner in market_data['runners']:
            sentiment_emoji = {
                'negative': '❌',
                'positive': '✅',
                'neutral': '⚪'
            }.get(runner['sentiment'], '⚪')
            
            print(f"\n{sentiment_emoji} {runner['horse_name']} ({runner['sentiment'].upper()})")
            print(f"   Last line: {runner['last_sentence']}")
            print(f"   Full: {runner['comment'][:150]}..." if len(runner['comment']) > 150 else f"   Full: {runner['comment']}")
        
        print(f"\n{'-'*80}")
        
        # Show lay betting candidates
        candidates = self.get_lay_betting_candidates(market_data)
        if candidates:
            print(f"\n🎯 LAY BETTING CANDIDATES ({len(candidates)}):")
            for candidate in candidates:
                print(f"   - {candidate['horse_name']}: {candidate['reason']}")


def main():
    """Example usage"""
    import argparse
    import getpass
    
    parser = argparse.ArgumentParser(description='Scrape Betfair runner comments')
    parser.add_argument('--market-id', '-m', type=str, help='Betfair market ID')
    parser.add_argument('--username', '-u', type=str, help='Betfair username/email')
    parser.add_argument('--password', '-p', type=str, help='Betfair password')
    parser.add_argument('--no-login', action='store_true', help='Skip login (comments may still be accessible)')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window (useful for debugging)')
    
    args = parser.parse_args()
    
    # Get credentials if not provided
    username = args.username
    password = args.password
    
    if not args.no_login:
        if not username:
            username = input("Betfair username/email (or press Enter to skip login): ").strip()
        if username and not password:
            password = getpass.getpass("Betfair password: ")
    
    # Create scraper
    scraper = BetfairCommentsScraper(
        username=username if username else None, 
        password=password if password else None,
        headless=not args.no_headless
    )
    
    # Get market ID
    market_id = args.market_id or "1.252447747"  # Default to example
    
    try:
        # Scrape the market
        market_data = scraper.scrape_market(market_id)
        
        # Print summary
        scraper.print_market_summary(market_data)
        
        # Save to database
        scraper.save_to_database(market_data)
        
        # Export to JSON for inspection
        with open('betfair_market_example.json', 'w') as f:
            json.dump(market_data, f, indent=2)
        logger.info("Saved example to betfair_market_example.json")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        # Always close the browser
        scraper.close()


if __name__ == "__main__":
    main()
