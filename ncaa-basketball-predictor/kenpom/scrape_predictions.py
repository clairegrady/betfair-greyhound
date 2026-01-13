"""
KenPom Daily Predictions Scraper
Fetches KenPom's predictions for upcoming games
"""

import pandas as pd
from kenpompy.utils import login
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / 'config.env')

class KenPomScraper:
    def __init__(self):
        self.email = os.getenv('KENPOM_EMAIL')
        self.password = os.getenv('KENPOM_PASSWORD')
        self.browser = None
        
    def login(self):
        """Login to KenPom"""
        self.browser = login(self.email, self.password)
        return self.browser
    
    def parse_prediction(self, pred_text):
        """
        Parse KenPom prediction text
        Example: "Ohio St. 78-77 (52%) [69]"
        Returns: {'team': 'Ohio St.', 'pred_score': 78, 'opp_score': 77, 'confidence': 52}
        """
        try:
            # Extract team name, scores, and confidence
            match = re.match(r'(.+?)\s+(\d+)-(\d+)\s+\((\d+)%\)', pred_text)
            if match:
                return {
                    'predicted_winner': match.group(1).strip(),
                    'pred_winner_score': int(match.group(2)),
                    'pred_loser_score': int(match.group(3)),
                    'confidence': int(match.group(4)),
                    'predicted_margin': int(match.group(2)) - int(match.group(3))
                }
        except:
            pass
        return None
    
    def parse_game_teams(self, game_text):
        """
        Parse game text to extract teams
        Example: "22 Nebraska 72, 39 Ohio St. 69" or for upcoming: "22 Nebraska vs. 39 Ohio St."
        Returns: {'team1': 'Nebraska', 'team2': 'Ohio St.'}
        """
        try:
            # For upcoming games (with "vs." or "at")
            if ' vs. ' in game_text or ' at ' in game_text:
                separator = ' vs. ' if ' vs. ' in game_text else ' at '
                parts = game_text.split(separator)
                
                # Extract team names (remove rankings)
                team1_match = re.search(r'(\d+\s+)?(.+?)(?:\s+vs\.|\s+at|$)', parts[0])
                team2_match = re.search(r'(\d+\s+)?(.+?)(?:\s+\[|$)', parts[1])
                
                if team1_match and team2_match:
                    return {
                        'team1': team1_match.group(2).strip(),
                        'team2': team2_match.group(2).strip(),
                        'game_started': False
                    }
            
            # For completed/in-progress games (with scores)
            match = re.match(r'(\d+\s+)?(.+?)\s+\d+,\s+(\d+\s+)?(.+?)\s+\d+', game_text)
            if match:
                return {
                    'team1': match.group(2).strip(),
                    'team2': match.group(4).strip(),
                    'game_started': True
                }
        except:
            pass
        return None
    
    def scrape_date(self, date_str):
        """
        Scrape KenPom predictions for a specific date
        Args:
            date_str: Date in format 'YYYY-MM-DD'
        Returns:
            List of predictions
        """
        if not self.browser:
            self.login()
        
        url = f"https://kenpom.com/fanmatch.php?d={date_str}"
        
        try:
            html = self.browser.get(url)
            tables = pd.read_html(html.content)
            
            if len(tables) == 0:
                return []
            
            df = tables[0]
            predictions = []
            
            for idx, row in df.iterrows():
                game_info = self.parse_game_teams(row['Game'])
                pred_info = self.parse_prediction(row['Prediction'])
                
                if game_info and pred_info and not game_info['game_started']:
                    # Only include upcoming games
                    predictions.append({
                        'date': date_str,
                        'team1': game_info['team1'],
                        'team2': game_info['team2'],
                        'predicted_winner': pred_info['predicted_winner'],
                        'confidence': pred_info['confidence'],
                        'predicted_margin': pred_info['predicted_margin'],
                        'pred_winner_score': pred_info['pred_winner_score'],
                        'pred_loser_score': pred_info['pred_loser_score'],
                        'scraped_at': datetime.now().isoformat()
                    })
            
            return predictions
            
        except Exception as e:
            print(f"Error scraping {date_str}: {e}")
            return []
    
    def scrape_upcoming_days(self, days=1):
        """
        Scrape KenPom predictions for the next N days
        """
        all_predictions = []
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            print(f"Scraping {date_str}...")
            predictions = self.scrape_date(date_str)
            all_predictions.extend(predictions)
            print(f"  Found {len(predictions)} upcoming games")
        
        return all_predictions


def main():
    """Test the scraper"""
    print("="*80)
    print("KENPOM PREDICTIONS SCRAPER")
    print("="*80 + "\n")
    
    scraper = KenPomScraper()
    
    # Scrape today and tomorrow
    predictions = scraper.scrape_upcoming_days(days=2)
    
    print(f"\n✅ Found {len(predictions)} total predictions\n")
    
    # Display sample
    for pred in predictions[:10]:
        winner_mark = "⭐" if pred['confidence'] >= 70 else ""
        print(f"{pred['team1']:25s} vs {pred['team2']:25s}")
        print(f"  Winner: {pred['predicted_winner']:25s} ({pred['confidence']}% confident) {winner_mark}")
        print(f"  Margin: {pred['predicted_margin']:+d} points\n")
    
    # Save to JSON
    with open('kenpom_predictions.json', 'w') as f:
        json.dump(predictions, f, indent=2)
    
    print(f"✅ Saved to kenpom_predictions.json")


if __name__ == "__main__":
    main()
