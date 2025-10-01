"""
Odds Analysis Script - Check for races with high place odds relative to win odds
"""
import sqlite3
import requests
import pandas as pd
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OddsAnalyzer:
    def __init__(self):
        self.api_base_url = "http://localhost:5173"
        self.betting_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/betting_history.sqlite"
        self.market_db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
        self.race_times_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/live_betting.sqlite"
        
    def get_races_with_markets(self):
        """Get all races that have market IDs"""
        try:
            # Connect to race_times database
            conn_race_times = sqlite3.connect(self.race_times_db_path)
            cursor_race_times = conn_race_times.cursor()
            
            # Get Australian races for today
            today = datetime.now().strftime('%Y-%m-%d')
            cursor_race_times.execute('''
                SELECT venue, race_number, race_time 
                FROM race_times 
                WHERE country = 'AUS' AND race_date = ?
                ORDER BY venue, race_number
            ''', (today,))
            
            all_races = cursor_race_times.fetchall()
            conn_race_times.close()
            
            # Connect to market database to find races with market IDs
            conn_market = sqlite3.connect(self.market_db_path)
            cursor_market = conn_market.cursor()
            
            races_with_markets = []
            
            for venue, race_number, race_time in all_races:
                # Find market ID for this race
                cursor_market.execute('''
                    SELECT DISTINCT MarketId, EventName, MarketName
                    FROM HorseMarketBook 
                    WHERE EventName LIKE ? AND EventName LIKE '%30th Sep%'
                    AND (MarketName LIKE ? OR MarketName LIKE ?)
                    LIMIT 1
                ''', (f'%{venue}%', f'R{race_number}%', f'Race {race_number}%'))
                
                result = cursor_market.fetchone()
                if result:
                    market_id, event_name, market_name = result
                    races_with_markets.append({
                        'venue': venue,
                        'race_number': race_number,
                        'race_time': race_time,
                        'market_id': market_id,
                        'event_name': event_name,
                        'market_name': market_name
                    })
            
            conn_market.close()
            logger.info(f"Found {len(races_with_markets)} races with market IDs")
            return races_with_markets
            
        except Exception as e:
            logger.error(f"Error getting races with markets: {e}")
            return []
    
    def get_win_odds(self, market_id):
        """Get win odds for a market using the same approach as betting_simulation.py"""
        try:
            import sqlite3
            import pandas as pd
            import requests
            
            # Connect to betting database (same as lay_betting_automation.py)
            betting_conn = sqlite3.connect(self.betting_db_path)
            
            # Get best back odds (for betting on horses to win)
            current_odds_query = """
            SELECT 
                SelectionId,
                COALESCE(RunnerName, 'Horse ' || SelectionId) as runner_name,
                best_back_price,
                best_back_size,
                LastPriceTraded,
                TotalMatched,
                0 as cloth_number
            FROM CurrentWinOdds
            WHERE MarketId = ? AND best_back_price IS NOT NULL
            ORDER BY best_back_price
            """
            
            result_df = pd.read_sql_query(current_odds_query, betting_conn, params=[market_id])
            betting_conn.close()
            
            if result_df.empty:
                logger.warning(f"⚠️ No CurrentWinOdds data for market {market_id}, attempting refresh...")
                try:
                    refresh_url = f"{self.api_base_url}/api/odds/refresh/{market_id}"
                    response = requests.get(refresh_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"🔄 Refresh successful, retrying CurrentWinOdds query...")
                        # Retry the CurrentWinOdds query with fresh connection
                        betting_conn_retry = sqlite3.connect(self.betting_db_path)
                        result_df = pd.read_sql_query(current_odds_query, betting_conn_retry, params=[market_id])
                        betting_conn_retry.close()
                        if not result_df.empty:
                            logger.info(f"📊 Using refreshed CurrentWinOdds data for market {market_id} ({len(result_df)} horses)")
                        else:
                            logger.warning(f"⚠️ Still no CurrentWinOdds data after refresh for market {market_id}")
                            return {}
                    else:
                        logger.warning(f"⚠️ Refresh failed with status {response.status_code}")
                        return {}
                except Exception as e:
                    logger.warning(f"⚠️ Refresh failed: {e}")
                    return {}
            
            # Convert to dictionary format
            win_odds = {}
            for _, row in result_df.iterrows():
                win_odds[row['SelectionId']] = {
                    'runner_name': row['runner_name'],
                    'back_price': row['best_back_price'],
                    'lay_price': None  # Not needed for this analysis
                }
            
            return win_odds
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting win odds for {market_id}: {e}")
            return {}
    
    def get_place_odds(self, market_id):
        """Get place odds for a market using the same approach as betting_simulation.py"""
        try:
            import sqlite3
            import pandas as pd
            import requests
            
            # Calculate place market ID (win market ID + 0.000000001)
            win_id_float = float(market_id)
            place_id_float = win_id_float + 0.000000001
            place_market_id = f"{place_id_float:.9f}"
            
            # Connect to betting database
            betting_conn = sqlite3.connect(self.betting_db_path)
            
            # Get best back odds for place market
            current_odds_query = """
            SELECT 
                SelectionId,
                COALESCE(RunnerName, 'Horse ' || SelectionId) as runner_name,
                best_back_price,
                best_back_size,
                LastPriceTraded,
                TotalMatched,
                0 as cloth_number
            FROM CurrentPlaceOdds
            WHERE MarketId = ? AND best_back_price IS NOT NULL
            ORDER BY best_back_price
            """
            
            result_df = pd.read_sql_query(current_odds_query, betting_conn, params=[place_market_id])
            betting_conn.close()
            
            if result_df.empty:
                logger.warning(f"⚠️ No CurrentPlaceOdds data for market {place_market_id}, attempting refresh...")
                try:
                    refresh_url = f"{self.api_base_url}/api/odds/refresh/{market_id}"
                    response = requests.get(refresh_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"🔄 Refresh successful, retrying CurrentPlaceOdds query...")
                        # Retry the CurrentPlaceOdds query with fresh connection
                        betting_conn_retry = sqlite3.connect(self.betting_db_path)
                        result_df = pd.read_sql_query(current_odds_query, betting_conn_retry, params=[place_market_id])
                        betting_conn_retry.close()
                        if not result_df.empty:
                            logger.info(f"📊 Using refreshed CurrentPlaceOdds data for market {place_market_id} ({len(result_df)} horses)")
                        else:
                            logger.warning(f"⚠️ Still no CurrentPlaceOdds data after refresh for market {place_market_id}")
                            return {}
                    else:
                        logger.warning(f"⚠️ Refresh failed with status {response.status_code}")
                        return {}
                except Exception as e:
                    logger.warning(f"⚠️ Refresh failed: {e}")
                    return {}
            
            # Convert to dictionary format
            place_odds = {}
            for _, row in result_df.iterrows():
                place_odds[row['SelectionId']] = {
                    'runner_name': row['runner_name'],
                    'back_price': row['best_back_price'],
                    'lay_price': None  # Not needed for this analysis
                }
            
            return place_odds
            
        except Exception as e:
            logger.warning(f"⚠️ Error getting place odds for {market_id}: {e}")
            return {}
    
    def analyze_odds_ratio(self, win_odds, place_odds):
        """Analyze odds ratio between place and win"""
        high_ratio_horses = []
        
        for selection_id in win_odds:
            if selection_id in place_odds:
                win_price = win_odds[selection_id]['back_price']
                place_price = place_odds[selection_id]['back_price']
                
                if win_price and place_price and win_price > 0 and place_price > 0:
                    # Calculate ratio (place odds / win odds)
                    ratio = place_price / win_price
                    
                    # Check if place odds are 85% or higher than win odds
                    if ratio >= 0.85:
                        high_ratio_horses.append({
                            'selection_id': selection_id,
                            'runner_name': win_odds[selection_id]['runner_name'],
                            'win_odds': win_price,
                            'place_odds': place_price,
                            'ratio': ratio,
                            'ratio_percentage': ratio * 100
                        })
        
        return high_ratio_horses
    
    def analyze_all_races(self):
        """Analyze all races for high place odds ratios"""
        logger.info("🔍 Starting odds analysis for all races...")
        
        # Get all races with market IDs
        races = self.get_races_with_markets()
        if not races:
            logger.error("❌ No races found with market IDs")
            return
        
        logger.info(f"📊 Analyzing {len(races)} races...")
        
        all_results = []
        
        for i, race in enumerate(races, 1):
            venue = race['venue']
            race_number = race['race_number']
            market_id = race['market_id']
            
            logger.info(f"🏇 [{i}/{len(races)}] Analyzing {venue} R{race_number} (Market: {market_id})")
            
            # Get win and place odds (refresh is handled within these methods)
            win_odds = self.get_win_odds(market_id)
            place_odds = self.get_place_odds(market_id)
            
            if not win_odds:
                logger.warning(f"⚠️ No win odds found for {venue} R{race_number}")
                continue
            
            if not place_odds:
                logger.warning(f"⚠️ No place odds found for {venue} R{race_number}")
                continue
            
            # Analyze odds ratio
            high_ratio_horses = self.analyze_odds_ratio(win_odds, place_odds)
            
            if high_ratio_horses:
                logger.info(f"🚨 HIGH RATIO FOUND in {venue} R{race_number}:")
                for horse in high_ratio_horses:
                    logger.info(f"  {horse['runner_name']}: Win {horse['win_odds']:.2f}, Place {horse['place_odds']:.2f}, Ratio {horse['ratio_percentage']:.1f}%")
                
                all_results.append({
                    'venue': venue,
                    'race_number': race_number,
                    'market_id': market_id,
                    'race_time': race['race_time'],
                    'high_ratio_horses': high_ratio_horses
                })
            else:
                logger.info(f"✅ {venue} R{race_number}: No high ratio horses found")
        
        # Summary
        logger.info(f"\n📊 ANALYSIS SUMMARY:")
        logger.info(f"Total races analyzed: {len(races)}")
        logger.info(f"Races with high place odds ratios: {len(all_results)}")
        
        if all_results:
            logger.info(f"\n🚨 RACES WITH HIGH PLACE ODDS RATIOS:")
            for result in all_results:
                logger.info(f"\n{result['venue']} R{result['race_number']} ({result['race_time']}):")
                for horse in result['high_ratio_horses']:
                    logger.info(f"  {horse['runner_name']}: Win {horse['win_odds']:.2f}, Place {horse['place_odds']:.2f}, Ratio {horse['ratio_percentage']:.1f}%")
        
        return all_results

def main():
    """Main function"""
    analyzer = OddsAnalyzer()
    results = analyzer.analyze_all_races()
    
    if results:
        print(f"\n🎯 Found {len(results)} races with high place odds ratios!")
    else:
        print("\n✅ No races found with high place odds ratios")

if __name__ == "__main__":
    main()
