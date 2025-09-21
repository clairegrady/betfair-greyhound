"""
Live Lay Betting Script v2 - Uses shared functionality
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from shared_lay_betting import LayBettingStrategy, LayBettingResults
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LiveLayBetting:
    """
    Live lay betting using shared strategy logic
    """
    
    def __init__(self, db_path: str, std_threshold: float = 1.5, max_odds: float = 25.0):
        self.db_path = db_path
        self.strategy = LayBettingStrategy(std_threshold, max_odds)
        self.results = LayBettingResults()
        self.opportunities = []
    
    def get_live_races(self, hours_ahead: int = 2, demo_mode: bool = False):
        """
        Get races starting within the specified time window
        
        Args:
            hours_ahead: Hours ahead to look for races
            demo_mode: If True, get any available races for demonstration
        """
        conn = sqlite3.connect(self.db_path)
        
        if demo_mode:
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
            AND datetime(m.OpenDate) > datetime('now')
            AND datetime(m.OpenDate) <= datetime('now', '+{} hours')
            ORDER BY m.OpenDate
            """.format(hours_ahead)
        
        races_df = pd.read_sql_query(query, conn)
        conn.close()
        
        if demo_mode:
            logger.info(f"Found {len(races_df)} races for today")
        else:
            logger.info(f"Found {len(races_df)} races starting within {hours_ahead} hours")
        return races_df
    
    def get_race_odds(self, market_id: str):
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
        
        odds_df = pd.read_sql_query(odds_query, conn, params=[market_id, self.strategy.max_odds])
        conn.close()
        
        # Merge to get all horses with their odds (if available)
        result_df = all_horses_df.merge(odds_df, on='SelectionId', how='left')
        
        return result_df
    
    def scan_opportunities(self, hours_ahead: int = 2, demo_mode: bool = False):
        """
        Scan for lay betting opportunities using shared strategy logic
        
        Args:
            hours_ahead: Hours ahead to look for races
            demo_mode: If True, get any available races for demonstration
        """
        logger.info("=== LIVE LAY BETTING OPPORTUNITY SCAN ===")
        logger.info(f"Strategy: {self.strategy.get_strategy_description()}")
        
        races_df = self.get_live_races(hours_ahead, demo_mode)
        
        if len(races_df) == 0:
            logger.info("No races found for the specified criteria")
            return
        
        opportunities_found = 0
        total_potential_bets = 0
        total_liability = 0
        
        for _, race in races_df.iterrows():
            event_name = race['EventName']
            market_name = race['MarketName']
            market_id = race['MarketId']
            open_date = race['OpenDate']
            
            logger.info(f"\nAnalyzing: {event_name} - {market_name}")
            logger.info(f"Start Time: {open_date}")
            
            # Get race odds
            race_odds = self.get_race_odds(market_id)
            
            if len(race_odds) == 0:
                logger.info("  ❌ No horses found for this race")
                continue
            
            # Use shared strategy to analyze race opportunity
            is_eligible, reason, eligible_horses = self.strategy.analyze_race_eligibility(
                race_odds, 'best_lay_price'
            )
            
            if not is_eligible:
                logger.info(f"  ❌ Not eligible: {reason}")
                continue
            
            # Found an opportunity
            opportunities_found += 1
            logger.info(f"  ✅ OPPORTUNITY FOUND: {reason}")
            
            race_opportunities = []
            for _, horse in eligible_horses.iterrows():
                # Calculate bet details using shared strategy
                bet_details = self.strategy.calculate_lay_bet_details(
                    horse['best_lay_price'], stake=1
                )
                
                horse_info = {
                    'selection_id': horse['SelectionId'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['best_lay_price'],
                    'stake': bet_details['stake'],
                    'liability': bet_details['liability'],
                    'potential_profit': bet_details['potential_profit']
                }
                
                race_opportunities.append(horse_info)
                total_potential_bets += 1
                total_liability += bet_details['liability']
                
                logger.info(f"    🐎 {horse['cloth_number']}. {horse['runner_name']} - Lay @ {horse['best_lay_price']:.2f} (Liability: ${bet_details['liability']:.2f})")
            
            # Store opportunity
            opportunity = {
                'event_name': event_name,
                'market_name': market_name,
                'market_id': market_id,
                'open_date': open_date,
                'horses': race_opportunities,
                'total_horses': len(race_odds),
                'eligible_horses': len(eligible_horses)
            }
            
            self.opportunities.append(opportunity)
        
        logger.info(f"\n=== SCAN COMPLETE ===")
        logger.info(f"Found {opportunities_found} betting opportunities")
        logger.info(f"Total potential lay bets: {total_potential_bets}")
        logger.info(f"Total liability: ${total_liability:.2f}")
        logger.info(f"Strategy: {self.strategy.get_strategy_description()}")
        
        return opportunities_found, total_potential_bets, total_liability
    
    def save_opportunities(self, filename: str = None):
        """Save opportunities to CSV file"""
        if not self.opportunities:
            logger.info("No opportunities to save")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"live_lay_opportunities_v2_{timestamp}.csv"
        
        # Flatten opportunities for CSV
        csv_data = []
        for opp in self.opportunities:
            for horse in opp['horses']:
                csv_data.append({
                    'event_name': opp['event_name'],
                    'market_name': opp['market_name'],
                    'market_id': opp['market_id'],
                    'open_date': opp['open_date'],
                    'selection_id': horse['selection_id'],
                    'runner_name': horse['runner_name'],
                    'cloth_number': horse['cloth_number'],
                    'lay_price': horse['lay_price'],
                    'stake': horse['stake'],
                    'liability': horse['liability'],
                    'potential_profit': horse['potential_profit']
                })
        
        df = pd.DataFrame(csv_data)
        df.to_csv(filename, index=False)
        
        logger.info(f"\n📊 Opportunities saved to: {filename}")
        return filename


def main():
    """Main function"""
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    
    # Create live betting instance
    live_betting = LiveLayBetting(db_path, std_threshold=1.5, max_odds=25.0)
    
    # Scan for opportunities
    opportunities_found, total_bets, total_liability = live_betting.scan_opportunities(
        hours_ahead=8, demo_mode=True
    )
    
    if opportunities_found > 0:
        # Save opportunities
        filename = live_betting.save_opportunities()
        
        print(f"\n📊 Opportunities saved to: {filename}")
        print(f"\n📈 SUMMARY:")
        print(f"   Races with opportunities: {opportunities_found}")
        print(f"   Total potential lay bets: {total_bets}")
        print(f"   Total liability: ${total_liability:.2f}")
        print(f"   Strategy: {live_betting.strategy.get_strategy_description()}")
    else:
        print("\n❌ No betting opportunities found")


if __name__ == "__main__":
    main()

