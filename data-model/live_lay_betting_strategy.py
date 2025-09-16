#!/usr/bin/env python3
"""
Live Lay Betting Strategy Implementation
Uses the backtested strategy parameters to identify live betting opportunities
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class LiveLayBettingStrategy:
    def __init__(self, db_path, std_threshold=1.5, max_odds=25.0):
        """
        Initialize the live lay betting strategy
        
        Args:
            db_path: Path to betfairmarket.sqlite database
            std_threshold: Standard deviation threshold for odds variance (from backtest)
            max_odds: Maximum odds to consider for lay bets (from backtest)
        """
        self.db_path = db_path
        self.std_threshold = std_threshold
        self.max_odds = max_odds
        self.logger = self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging for the strategy"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('live_lay_betting.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def get_live_races(self, hours_ahead=2, demo_mode=False):
        """
        Get races starting within the next X hours
        
        Args:
            hours_ahead: How many hours ahead to look for races
            demo_mode: If True, get any available races for demonstration
        """
        conn = sqlite3.connect(self.db_path)
        
        if demo_mode:
            # For demonstration, get today's races
            query = """
            SELECT DISTINCT 
                h.EventName,
                h.MarketName,
                h.MarketId,
                m.OpenDate
            FROM HorseMarketBook h
            JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
            WHERE h.MarketName != 'To Be Placed'
            AND m.OpenDate IS NOT NULL
            AND date(m.OpenDate) = date('now')
            ORDER BY m.OpenDate
            """
        else:
            # Get current time and future cutoff
            now = datetime.now()
            future_cutoff = now + timedelta(hours=hours_ahead)
            
            query = """
            SELECT DISTINCT 
                h.EventName,
                h.MarketName,
                h.MarketId,
                m.OpenDate
            FROM HorseMarketBook h
            JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
            WHERE h.MarketName != 'To Be Placed'
            AND m.OpenDate IS NOT NULL
            AND date(m.OpenDate) = date('now')
            ORDER BY m.OpenDate
            """
        
        races_df = pd.read_sql_query(query, conn)
        conn.close()
        
        if demo_mode:
            self.logger.info(f"Found {len(races_df)} races for today")
        else:
            self.logger.info(f"Found {len(races_df)} races for today")
        return races_df
    
    def get_race_odds(self, market_id):
        """
        Get all lay odds for a specific race, with best odds per horse
        
        Args:
            market_id: The market ID for the race
        """
        conn = sqlite3.connect(self.db_path)
        
        # First get all horses in the race
        all_horses_query = """
        SELECT 
            h.SelectionId,
            COALESCE(h.RUNNER_NAME, 'Unknown') as runner_name,
            COALESCE(h.CLOTH_NUMBER, 0) as cloth_number
        FROM HorseMarketBook h
        WHERE h.MarketId = ?
        """
        
        all_horses_df = pd.read_sql_query(all_horses_query, conn, params=[market_id])
        
        # Then get lay odds for horses that have them and meet our criteria
        # Use the same MarketId from HorseMarketBook to ensure we get the right odds
        odds_query = """
        SELECT 
            h.SelectionId,
            MIN(l.Price) as best_lay_price,
            MAX(l.Size) as max_available_size,
            l.LastPriceTraded,
            l.TotalMatched
        FROM HorseMarketBook h
        JOIN MarketBookLayPrices l ON h.SelectionId = l.SelectionId AND h.MarketId = l.MarketId
        WHERE h.MarketId = ?
        AND l.Price > 0
        AND l.Price <= ?
        GROUP BY h.SelectionId
        """
        
        odds_df = pd.read_sql_query(odds_query, conn, params=[market_id, self.max_odds])
        conn.close()
        
        # Merge to get all horses with their odds (if available)
        result_df = all_horses_df.merge(odds_df, on='SelectionId', how='left')
        
        return result_df
    
    def analyze_race_opportunity(self, race_data):
        """
        Analyze if a race meets our lay betting criteria
        
        Args:
            race_data: DataFrame with race odds data
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses)
        """
        # Filter out horses without lay odds for analysis
        horses_with_odds = race_data.dropna(subset=['best_lay_price'])
        
        if len(race_data) < 4:
            return False, f"Less than 4 horses (total: {len(race_data)})", None
        
        if len(horses_with_odds) < 4:
            return False, f"Less than 4 horses with lay odds (total: {len(race_data)}, with odds: {len(horses_with_odds)})", None
        
        # Sort by best lay price (lowest odds first)
        horses_with_odds = horses_with_odds.sort_values('best_lay_price')
        
        # Get top half horses (lowest odds)
        top_half_count = len(horses_with_odds) // 2
        top_half = horses_with_odds.head(top_half_count)
        
        # Calculate odds variance in top half
        top_half_odds = top_half['best_lay_price'].values
        odds_std = np.std(top_half_odds)
        
        # Check if odds are too similar
        if odds_std < self.std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f})", None
        
        # Get bottom half horses (highest odds)
        bottom_half = horses_with_odds.iloc[top_half_count:]
        
        # Filter bottom half horses with odds <= max_odds
        eligible_horses = bottom_half[bottom_half['best_lay_price'] <= self.max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {self.max_odds}:1", None
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay", eligible_horses
    
    def calculate_lay_bet_details(self, horse_odds, stake=1):
        """
        Calculate lay bet details
        
        Args:
            horse_odds: The lay odds for the horse
            stake: Stake amount
            
        Returns:
            dict: Bet details including liability and potential profit
        """
        liability = (horse_odds - 1) * stake
        potential_profit = stake
        
        return {
            'stake': stake,
            'liability': liability,
            'potential_profit': potential_profit,
            'total_risk': stake + liability
        }
    
    def scan_for_opportunities(self, hours_ahead=2, demo_mode=False):
        """
        Scan for live lay betting opportunities
        
        Args:
            hours_ahead: How many hours ahead to scan
            demo_mode: If True, use demo mode to show any available races
        """
        self.logger.info("=== LIVE LAY BETTING OPPORTUNITY SCAN ===")
        self.logger.info(f"Strategy: Std Threshold={self.std_threshold}, Max Odds={self.max_odds}")
        
        # Get upcoming races
        races = self.get_live_races(hours_ahead, demo_mode)
        
        if races.empty:
            self.logger.info("No upcoming races found")
            return []
        
        opportunities = []
        
        for _, race in races.iterrows():
            event_name = race['EventName']
            market_name = race['MarketName']
            market_id = race['MarketId']
            start_time = race['OpenDate']
            
            self.logger.info(f"\nAnalyzing: {event_name} - {market_name}")
            self.logger.info(f"Start Time: {start_time}")
            
            # Get race odds
            race_odds = self.get_race_odds(market_id)
            
            if race_odds.empty:
                self.logger.info("  No odds available")
                continue
            
            # Analyze opportunity
            is_eligible, reason, eligible_horses = self.analyze_race_opportunity(race_odds)
            
            if is_eligible:
                self.logger.info(f"  ✅ OPPORTUNITY FOUND: {reason}")
                
                opportunity = {
                    'event_name': event_name,
                    'market_name': market_name,
                    'market_id': market_id,
                    'start_time': start_time,
                    'total_horses': len(race_odds),
                    'eligible_horses': len(eligible_horses),
                    'horses': []
                }
                
                # Calculate bet details for each eligible horse
                for _, horse in eligible_horses.iterrows():
                    bet_details = self.calculate_lay_bet_details(horse['best_lay_price'])
                    
                horse_info = {
                    'selection_id': horse['SelectionId'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['best_lay_price'],
                    'available_size': horse['max_available_size'],
                    'last_traded': horse['LastPriceTraded'],
                    'total_matched': horse['TotalMatched'],
                    **bet_details
                }
                
                opportunity['horses'].append(horse_info)
                
                self.logger.info(f"    🐎 {horse['cloth_number']}. {horse['runner_name']} - Lay @ {horse['best_lay_price']:.2f} (Liability: ${bet_details['liability']:.2f})")
                
                opportunities.append(opportunity)
            else:
                self.logger.info(f"  ❌ Not eligible: {reason}")
        
        self.logger.info(f"\n=== SCAN COMPLETE ===")
        self.logger.info(f"Found {len(opportunities)} betting opportunities")
        
        return opportunities
    
    def save_opportunities(self, opportunities, filename=None):
        """
        Save opportunities to CSV for review
        
        Args:
            opportunities: List of opportunity dictionaries
            filename: Output filename (optional)
        """
        if not opportunities:
            self.logger.info("No opportunities to save")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"live_lay_opportunities_{timestamp}.csv"
        
        # Flatten opportunities for CSV
        rows = []
        for opp in opportunities:
            for horse in opp['horses']:
                row = {
                    'event_name': opp['event_name'],
                    'market_name': opp['market_name'],
                    'market_id': opp['market_id'],
                    'start_time': opp['start_time'],
                    'total_horses': opp['total_horses'],
                    'selection_id': horse['selection_id'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['lay_price'],
                    'available_size': horse['available_size'],
                    'stake': horse['stake'],
                    'liability': horse['liability'],
                    'potential_profit': horse['potential_profit'],
                    'total_risk': horse['total_risk']
                }
                rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(filename, index=False)
        self.logger.info(f"Opportunities saved to {filename}")
        
        return filename

def main():
    """Main function to run the live lay betting strategy"""
    
    # Database path
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    
    # Strategy parameters (from backtest analysis)
    # You can adjust these based on your risk tolerance
    std_threshold = 1.5  # From backtest: good balance of opportunities and ROI
    max_odds = 25.0      # From backtest: good balance of risk and opportunities
    
    # Create strategy instance
    strategy = LiveLayBettingStrategy(db_path, std_threshold, max_odds)
    
    # Scan for opportunities in today's races
    opportunities = strategy.scan_for_opportunities(hours_ahead=8, demo_mode=True)
    
    # Save opportunities to CSV
    if opportunities:
        filename = strategy.save_opportunities(opportunities)
        print(f"\n📊 Opportunities saved to: {filename}")
        
        # Summary
        total_bets = sum(len(opp['horses']) for opp in opportunities)
        total_liability = sum(
            sum(horse['liability'] for horse in opp['horses']) 
            for opp in opportunities
        )
        
        print(f"\n📈 SUMMARY:")
        print(f"   Races with opportunities: {len(opportunities)}")
        print(f"   Total potential lay bets: {total_bets}")
        print(f"   Total liability: ${total_liability:.2f}")
        print(f"   Strategy: Std={std_threshold}, Max Odds={max_odds}")
    else:
        print("\n❌ No betting opportunities found with current criteria")

if __name__ == "__main__":
    main()
