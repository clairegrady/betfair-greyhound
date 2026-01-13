"""
Check KenPom Paper Trade Results
Scrapes actual game results and settles paper trades
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from scrape_predictions import KenPomScraper
from bs4 import BeautifulSoup
import pandas as pd
import re

PAPER_TRADES_DB = Path(__file__).parent / "kenpom_paper_trades.db"


def parse_game_result(game_text):
    """
    Parse completed game from KenPom fanmatch
    Example: "22 Nebraska 72, 39 Ohio St. 69"
    Returns: {'team1': 'Nebraska', 'score1': 72, 'team2': 'Ohio St.', 'score2': 69, 'winner': 'Nebraska'}
    """
    try:
        match = re.match(r'(\d+\s+)?(.+?)\s+(\d+),\s+(\d+\s+)?(.+?)\s+(\d+)', game_text)
        if match:
            team1 = match.group(2).strip()
            score1 = int(match.group(3))
            team2 = match.group(5).strip()
            score2 = int(match.group(6))
            
            winner = team1 if score1 > score2 else team2
            
            return {
                'team1': team1,
                'score1': score1,
                'team2': team2,
                'score2': score2,
                'winner': winner
            }
    except:
        pass
    return None


def team_names_match(name1, name2):
    """Check if two team names match (fuzzy)"""
    n1 = name1.lower().replace('.', '').replace(' ', '')
    n2 = name2.lower().replace('.', '').replace(' ', '')
    
    # Direct match
    if n1 == n2:
        return True
    
    # One contained in other
    if n1 in n2 or n2 in n1:
        return True
    
    # Check first word (usually the main identifier)
    w1 = name1.split()[0].lower()
    w2 = name2.split()[0].lower()
    if len(w1) > 3 and len(w2) > 3 and (w1 in w2 or w2 in w1):
        return True
    
    return False


def scrape_results_for_date(scraper, date_str):
    """Scrape game results from KenPom fanmatch for a specific date"""
    url = f"https://kenpom.com/fanmatch.php?d={date_str}"
    
    try:
        html = scraper.browser.get(url)
        tables = pd.read_html(html.content)
        
        if len(tables) == 0:
            return []
        
        df = tables[0]
        results = []
        
        for idx, row in df.iterrows():
            game_result = parse_game_result(row['Game'])
            if game_result:
                results.append(game_result)
        
        return results
        
    except Exception as e:
        print(f"Error scraping results for {date_str}: {e}")
        return []


def settle_paper_trades():
    """Check unsettled paper trades and settle them with results"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    # Get unsettled trades
    cursor.execute("""
        SELECT id, game_date, home_team, away_team, selection, odds, stake
        FROM paper_trades
        WHERE result IS NULL
        ORDER BY game_date
    """)
    
    unsettled = cursor.fetchall()
    
    if not unsettled:
        print("✅ No unsettled trades")
        return
    
    print(f"Found {len(unsettled)} unsettled trades\n")
    
    # Login to KenPom
    scraper = KenPomScraper()
    scraper.login()
    
    settled_count = 0
    wins = 0
    losses = 0
    total_profit = 0
    
    # Group by date
    dates = set(trade[1] for trade in unsettled)
    
    for date_str in sorted(dates):
        print(f"Checking results for {date_str}...")
        results = scrape_results_for_date(scraper, date_str)
        
        if not results:
            print(f"  No results found yet")
            continue
        
        # Process trades for this date
        trades_for_date = [t for t in unsettled if t[1] == date_str]
        
        for trade in trades_for_date:
            trade_id, game_date, home_team, away_team, selection, odds, stake = trade
            
            # Find matching game result
            for result in results:
                # Check if this result matches our trade
                teams_match = (
                    (team_names_match(result['team1'], home_team) and team_names_match(result['team2'], away_team)) or
                    (team_names_match(result['team1'], away_team) and team_names_match(result['team2'], home_team))
                )
                
                if teams_match:
                    # Determine if our bet won
                    won = team_names_match(result['winner'], selection)
                    
                    if won:
                        profit = stake * (odds - 1)
                        result_text = 'won'
                        wins += 1
                        symbol = "✅"
                    else:
                        profit = -stake
                        result_text = 'lost'
                        losses += 1
                        symbol = "❌"
                    
                    # Update trade
                    cursor.execute("""
                        UPDATE paper_trades
                        SET result = ?, profit = ?, settled_at = ?
                        WHERE id = ?
                    """, (result_text, profit, datetime.now(), trade_id))
                    
                    settled_count += 1
                    total_profit += profit
                    
                    print(f"  {symbol} {home_team} vs {away_team}: {result_text} (${profit:+.2f})")
                    break
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*80}")
    print("SETTLEMENT SUMMARY")
    print(f"{'='*80}")
    print(f"Settled: {settled_count} trades")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    if settled_count > 0:
        print(f"Win Rate: {wins/settled_count*100:.1f}%")
    print(f"Total Profit/Loss: ${total_profit:+,.2f}")
    print(f"{'='*80}")


def print_stats():
    """Print overall paper trading statistics"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
            SUM(stake) as total_staked,
            SUM(profit) as total_profit,
            COUNT(CASE WHEN result IS NULL THEN 1 END) as pending
        FROM paper_trades
    """)
    
    stats = cursor.fetchone()
    total_trades, wins, losses, total_staked, total_profit, pending = stats
    
    conn.close()
    
    print(f"\n{'='*80}")
    print("OVERALL STATISTICS")
    print(f"{'='*80}")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Pending: {pending}")
    
    if wins + losses > 0:
        win_rate = wins / (wins + losses) * 100
        print(f"Win Rate: {win_rate:.1f}%")
    
    if total_staked:
        roi = (total_profit / total_staked) * 100
        print(f"Total Staked: ${total_staked:,.2f}")
        print(f"Total Profit: ${total_profit:+,.2f}")
        print(f"ROI: {roi:+.1f}%")
    
    current_bankroll = 10000 + (total_profit or 0)
    print(f"Current Bankroll: ${current_bankroll:,.2f}")
    print(f"{'='*80}")


def main():
    print("="*80)
    print("KENPOM PAPER TRADES - RESULTS CHECKER")
    print("="*80 + "\n")
    
    settle_paper_trades()
    print_stats()


if __name__ == "__main__":
    main()
