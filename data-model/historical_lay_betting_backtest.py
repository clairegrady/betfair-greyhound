#!/usr/bin/env python3
"""
Historical Lay Betting Backtest Script

This script tests the lay betting strategy using historical race result data.
It calculates odds from the average of FixedWinOpen_Reference and FixedWinClose_Reference columns.
"""

import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HistoricalLayBettingBacktest:
    def __init__(self, csv_file_path: str):
        self.csv_file_path = csv_file_path
        self.results = []
        
    def load_historical_data(self) -> pd.DataFrame:
        """Load historical race result data from CSV"""
        try:
            logger.info(f"Loading historical data from {self.csv_file_path}")
            df = pd.read_csv(self.csv_file_path)
            logger.info(f"Loaded {len(df)} race results")
            return df
        except Exception as e:
            logger.error(f"Error loading historical data: {str(e)}")
            return pd.DataFrame()
    
    def calculate_odds(self, row: pd.Series) -> float:
        """Calculate odds from FixedWinOpen_Reference and FixedWinClose_Reference"""
        try:
            open_ref = float(row['FixedWinOpen_Reference']) if pd.notna(row['FixedWinOpen_Reference']) else None
            close_ref = float(row['FixedWinClose_Reference']) if pd.notna(row['FixedWinClose_Reference']) else None
            
            # Filter out invalid odds (negative, zero, or very high values)
            if open_ref is not None and (open_ref <= 0 or open_ref > 1000):
                open_ref = None
            if close_ref is not None and (close_ref <= 0 or close_ref > 1000):
                close_ref = None
            
            if open_ref is not None and close_ref is not None:
                return (open_ref + close_ref) / 2
            elif open_ref is not None:
                return open_ref
            elif close_ref is not None:
                return close_ref
            else:
                return None
        except Exception as e:
            logger.error(f"Error calculating odds: {str(e)}")
            return None
    
    def process_race(self, race_data: pd.DataFrame) -> Dict:
        """Process a single race and apply lay betting strategy"""
        try:
            # Calculate odds for each runner
            race_data['calculated_odds'] = race_data.apply(self.calculate_odds, axis=1)
            
            # Filter out runners with no odds and scratched horses (position = -2)
            valid_runners = race_data[
                (race_data['calculated_odds'].notna()) & 
                (race_data['finishingPosition'] != -2)
            ].copy()
            
            if len(valid_runners) < 2:
                logger.warning(f"Not enough runners with valid odds: {len(valid_runners)}")
                return None
            
            # Sort by odds (lowest = favorites)
            valid_runners = valid_runners.sort_values('calculated_odds')
            
            # Select top half (favorites)
            total_runners = len(valid_runners)
            top_half_count = max(1, total_runners // 2)
            top_half_runners = valid_runners.head(top_half_count)
            
            logger.info(f"Race: {race_data.iloc[0]['meetingName']} R{race_data.iloc[0]['raceNumber']}")
            logger.info(f"Total runners: {total_runners}, Selected for lay betting: {len(top_half_runners)}")
            
            # Log selected horses
            for idx, row in top_half_runners.iterrows():
                logger.info(f"  {row['runnerName']} (odds: {row['calculated_odds']:.2f})")
            
            # Calculate results
            race_result = {
                'meeting_name': race_data.iloc[0]['meetingName'],
                'race_number': race_data.iloc[0]['raceNumber'],
                'race_date': race_data.iloc[0]['meetingDate'],
                'total_runners': total_runners,
                'selected_runners': len(top_half_runners),
                'lay_bets': [],
                'winners_layed': 0,
                'total_liability': 0,
                'total_profit': 0
            }
            
            # Process each selected runner
            for idx, row in top_half_runners.iterrows():
                odds = row['calculated_odds']
                finishing_position = row['finishingPosition']
                runner_name = row['runnerName']
                
                # Calculate lay bet details
                stake = 1.0  # Fixed stake for backtest
                liability = stake * (odds - 1)  # Liability for lay bet
                
                # Determine if we won the lay bet (horse didn't win)
                lay_bet_won = finishing_position != 1.0
                
                if lay_bet_won:
                    profit = stake  # We keep the stake
                else:
                    profit = -liability  # We pay the liability
                
                lay_bet = {
                    'runner_name': runner_name,
                    'odds': odds,
                    'stake': stake,
                    'liability': liability,
                    'finishing_position': finishing_position,
                    'lay_bet_won': lay_bet_won,
                    'profit': profit
                }
                
                race_result['lay_bets'].append(lay_bet)
                race_result['total_liability'] += liability
                race_result['total_profit'] += profit
                
                if finishing_position == 1.0:
                    race_result['winners_layed'] += 1
                
                logger.info(f"    {runner_name}: odds={odds:.2f}, position={finishing_position}, "
                          f"lay_won={lay_bet_won}, profit={profit:.2f}")
            
            return race_result
            
        except Exception as e:
            logger.error(f"Error processing race: {str(e)}")
            return None
    
    def run_backtest(self) -> Dict:
        """Run the complete backtest"""
        logger.info("🚀 Starting historical lay betting backtest")
        
        # Load data
        df = self.load_historical_data()
        if df.empty:
            logger.error("No data loaded")
            return {}
        
        # Group by race
        races = df.groupby(['meetingName', 'raceNumber', 'meetingDate'])
        
        logger.info(f"Found {len(races)} races to analyze")
        
        backtest_results = {
            'total_races': 0,
            'total_lay_bets': 0,
            'total_profit': 0,
            'total_liability': 0,
            'winners_layed': 0,
            'race_results': []
        }
        
        # Process each race
        for (meeting_name, race_number, race_date), race_data in races:
            logger.info(f"\n🏇 Processing {meeting_name} R{race_number} on {race_date}")
            
            race_result = self.process_race(race_data)
            if race_result:
                backtest_results['race_results'].append(race_result)
                backtest_results['total_races'] += 1
                backtest_results['total_lay_bets'] += len(race_result['lay_bets'])
                backtest_results['total_profit'] += race_result['total_profit']
                backtest_results['total_liability'] += race_result['total_liability']
                backtest_results['winners_layed'] += race_result['winners_layed']
        
        # Calculate summary statistics
        if backtest_results['total_races'] > 0:
            backtest_results['avg_profit_per_race'] = backtest_results['total_profit'] / backtest_results['total_races']
            backtest_results['avg_lay_bets_per_race'] = backtest_results['total_lay_bets'] / backtest_results['total_races']
            backtest_results['win_rate'] = (backtest_results['total_lay_bets'] - backtest_results['winners_layed']) / backtest_results['total_lay_bets'] if backtest_results['total_lay_bets'] > 0 else 0
        
        return backtest_results
    
    def save_results_to_csv(self, results: Dict):
        """Save detailed results to CSV file"""
        try:
            # Create detailed results DataFrame
            detailed_results = []
            
            for race_result in results['race_results']:
                for lay_bet in race_result['lay_bets']:
                    detailed_results.append({
                        'meeting_name': race_result['meeting_name'],
                        'race_number': race_result['race_number'],
                        'race_date': race_result['race_date'],
                        'runner_name': lay_bet['runner_name'],
                        'odds': lay_bet['odds'],
                        'stake': lay_bet['stake'],
                        'liability': lay_bet['liability'],
                        'finishing_position': lay_bet['finishing_position'],
                        'lay_bet_won': lay_bet['lay_bet_won'],
                        'profit': lay_bet['profit']
                    })
            
            # Save to CSV
            df = pd.DataFrame(detailed_results)
            csv_filename = f"lay_betting_backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(csv_filename, index=False)
            logger.info(f"📁 Detailed results saved to: {csv_filename}")
            
            # Also save summary
            summary_data = {
                'metric': ['Total Races', 'Total Lay Bets', 'Average Lay Bets per Race', 
                          'Total Profit', 'Total Liability', 'Winners Layed', 'Win Rate %', 
                          'Average Profit per Race'],
                'value': [results['total_races'], results['total_lay_bets'], 
                         results.get('avg_lay_bets_per_race', 0),
                         results['total_profit'], results['total_liability'],
                         results['winners_layed'], results.get('win_rate', 0)*100,
                         results.get('avg_profit_per_race', 0)]
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_filename = f"lay_betting_backtest_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            summary_df.to_csv(summary_filename, index=False)
            logger.info(f"📁 Summary saved to: {summary_filename}")
            
        except Exception as e:
            logger.error(f"Error saving results to CSV: {str(e)}")
    
    def print_summary(self, results: Dict):
        """Print backtest summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 HISTORICAL LAY BETTING BACKTEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Races Analyzed: {results['total_races']}")
        logger.info(f"Total Lay Bets Placed: {results['total_lay_bets']}")
        logger.info(f"Average Lay Bets per Race: {results.get('avg_lay_bets_per_race', 0):.2f}")
        logger.info(f"Total Profit: ${results['total_profit']:.2f}")
        logger.info(f"Total Liability: ${results['total_liability']:.2f}")
        logger.info(f"Net Profit: ${results['total_profit']:.2f}")
        logger.info(f"Winners Layed (Lost Bets): {results['winners_layed']}")
        logger.info(f"Win Rate: {results.get('win_rate', 0)*100:.1f}%")
        logger.info(f"Average Profit per Race: ${results.get('avg_profit_per_race', 0):.2f}")
        logger.info("="*60)

def main():
    parser = argparse.ArgumentParser(description='Historical Lay Betting Backtest')
    parser.add_argument('--csv-file', 
                       default='/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-07.csv',
                       help='Path to historical race result CSV file')
    
    args = parser.parse_args()
    
    # Create backtest instance
    backtest = HistoricalLayBettingBacktest(args.csv_file)
    
    # Run backtest
    results = backtest.run_backtest()
    
    # Save results to CSV
    backtest.save_results_to_csv(results)
    
    # Print summary
    backtest.print_summary(results)

if __name__ == "__main__":
    main()
