#!/usr/bin/env python3
"""
Simulation Results Analyzer
Integrates with Betfair Results Fetcher to calculate performance metrics
"""

import sqlite3
import pandas as pd
from datetime import datetime, date
import logging
from typing import List, Dict
from betfair_results_fetcher import BetfairResultsFetcher

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimulationResultsAnalyzer:
    def __init__(self, db_path: str = "betting_simulation.sqlite"):
        self.db_path = db_path
        self.results_fetcher = BetfairResultsFetcher(db_path)
    
    def get_simulation_bets(self) -> pd.DataFrame:
        """Get simulation bets from today"""
        conn = sqlite3.connect(self.db_path)
        
        # Use today's date
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        query = """
            SELECT 
                market_id,
                venue,
                race_number,
                race_date,
                strategy,
                horse_name,
                win_odds,
                place_odds,
                lay_odds,
                stake,
                bet_type,
                created_at
            FROM valid_simulation_results
            WHERE race_date = ?
            ORDER BY race_date, venue, race_number, created_at
        """
        
        df = pd.read_sql_query(query, conn, params=[target_date])
        conn.close()
        
        return df
    
    def get_race_results(self) -> pd.DataFrame:
        """Get race results from today, excluding races with ACTIVE horses"""
        conn = sqlite3.connect(self.db_path)
        
        # Use today's date
        target_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get all race results for today
        query = """
            SELECT 
                rr.venue,
                rr.race_number,
                rr.race_date,
                hr.finishing_position,
                hr.horse_name,
                hr.starting_price
            FROM race_results rr
            JOIN horse_results hr ON rr.id = hr.race_id
            WHERE rr.race_date = ?
            ORDER BY rr.race_date, rr.venue, rr.race_number, hr.finishing_position
        """
        
        df = pd.read_sql_query(query, conn, params=[target_date])
        conn.close()
        
        # Filter to only include races that have results in the race_results table
        if not df.empty:
            # Get races that have results (settled races)
            results_conn = sqlite3.connect(self.db_path)
            results_query = """
                SELECT DISTINCT venue, race_number
                FROM race_results
                WHERE race_date = ?
            """
            results_df = pd.read_sql_query(results_query, results_conn, params=[target_date])
            results_conn.close()
            
            if not results_df.empty:
                # Filter df to only include races with results (settled races)
                df = df.merge(results_df, on=['venue', 'race_number'], how='inner')
            else:
                df = pd.DataFrame()  # No races with results
        
        return df
    
    def calculate_bet_outcome(self, bet: Dict, race_results: pd.DataFrame) -> Dict:
        """Calculate the outcome of a single bet"""
        # Find matching race results
        race_match = race_results[
            (race_results['venue'] == bet['venue']) &
            (race_results['race_number'] == bet['race_number']) &
            (race_results['race_date'] == bet['race_date'])
        ]
        
        if race_match.empty:
            return {
                'won': False,
                'placed': False,
                'profit_loss': 0.0,
                'finishing_position': 0,
                'has_results': False
            }
        
        # Find the horse's finishing position
        horse_result = race_match[race_match['horse_name'].str.contains(bet['horse_name'], case=False, na=False)]
        
        if horse_result.empty:
            return {
                'won': False,
                'placed': False,
                'profit_loss': 0.0,
                'finishing_position': 0,
                'has_results': True
            }
        
        finishing_position = horse_result.iloc[0]['finishing_position']
        
        # Calculate outcome based on bet type
        if bet['bet_type'] == 'win':
            won = finishing_position == 1
            if won:
                profit_loss = (bet['win_odds'] - 1) * bet['stake']
            else:
                profit_loss = -bet['stake']
        elif bet['bet_type'] == 'lay':
            # For lay bets: we win if the horse doesn't win (finishes 2nd or worse)
            # We lose if the horse wins (finishes 1st)
            # Handle NULL finishing positions (no result available)
            if finishing_position is None or finishing_position == 0 or pd.isna(finishing_position):
                return {
                    'won': False,
                    'placed': False,
                    'profit_loss': 0.0,
                    'finishing_position': finishing_position,
                    'has_results': False
                }
            won = finishing_position != 1
            if won:
                # Lay bet wins: we keep the stake (profit = stake)
                profit_loss = bet['stake']
            else:
                # Lay bet loses: we lose the liability = stake * (lay_odds - 1)
                lay_odds = bet.get('lay_odds', 0.0)
                profit_loss = -bet['stake'] * (lay_odds - 1)
        else:  # place bet
            placed = finishing_position in [1, 2, 3, 4]
            if placed:
                # Use actual place odds from simulation data
                place_odds = bet['place_odds']
                profit_loss = (place_odds - 1) * bet['stake']
            else:
                profit_loss = -bet['stake']
            won = False
        
        return {
            'won': won,
            'placed': placed if bet['bet_type'] == 'place' else won,
            'profit_loss': profit_loss,
            'finishing_position': finishing_position,
            'has_results': True
        }
    
    def analyze_simulation_performance(self) -> pd.DataFrame:
        """Analyze simulation performance and return metrics"""
        logger.info("📊 Analyzing simulation performance...")
        
        # Get simulation bets
        bets_df = self.get_simulation_bets()
        if bets_df.empty:
            logger.warning("⚠️ No simulation bets found")
            return pd.DataFrame()
        
        # Get race results
        results_df = self.get_race_results()
        if results_df.empty:
            logger.warning("⚠️ No race results found. Fetching results from Betfair...")
            # Get unique market IDs from bets
            market_ids = bets_df['market_id'].unique().tolist()
            self.results_fetcher.fetch_results(market_ids)
            results_df = self.get_race_results()
        else:
            # Check for missing races and fetch their results
            logger.info("🔍 Checking for missing race results...")
            
            # Get races with results
            races_with_results = set()
            for _, row in results_df.iterrows():
                races_with_results.add((row['venue'], row['race_number'], row['race_date']))
            
            # Get races with simulation bets
            races_with_bets = set()
            for _, row in bets_df.iterrows():
                races_with_bets.add((row['venue'], row['race_number'], row['race_date']))
            
            # Find missing races
            missing_races = races_with_bets - races_with_results
            if missing_races:
                logger.info(f"📋 Found {len(missing_races)} missing races, fetching results...")
                # Get market IDs for missing races
                missing_market_ids = []
                for venue, race_number, race_date in missing_races:
                    race_bets = bets_df[
                        (bets_df['venue'] == venue) & 
                        (bets_df['race_number'] == race_number) & 
                        (bets_df['race_date'] == race_date)
                    ]
                    if not race_bets.empty:
                        missing_market_ids.extend(race_bets['market_id'].unique().tolist())
                
                if missing_market_ids:
                    self.results_fetcher.fetch_results(missing_market_ids)
                    # Re-fetch all results
                    results_df = self.get_race_results()
        
        if results_df.empty:
            logger.error("❌ No race results available for analysis")
            return pd.DataFrame()
        
        # Calculate outcomes for each bet
        outcomes = []
        for _, bet in bets_df.iterrows():
            bet_dict = bet.to_dict()
            # Ensure lay_odds is included in the bet dictionary with actual value
            bet_dict['lay_odds'] = bet.get('lay_odds', 0.0)
            outcome = self.calculate_bet_outcome(bet_dict, results_df)
            outcomes.append({
                'market_id': bet['market_id'],
                'venue': bet['venue'],
                'race_number': bet['race_number'],
                'race_date': bet['race_date'],
                'strategy': bet['strategy'],
                'horse_name': bet['horse_name'],
                'bet_type': bet['bet_type'],
                'stake': bet['stake'],
                'win_odds': bet['win_odds'],
                'place_odds': bet['place_odds'],
                'finishing_position': outcome['finishing_position'],
                'won': outcome['won'],
                'placed': outcome['placed'],
                'profit_loss': outcome['profit_loss'],
                'has_results': outcome['has_results']
            })
        
        outcomes_df = pd.DataFrame(outcomes)
        
        # Calculate performance metrics by race and strategy
        race_metrics = []
        for (venue, race_number, race_date), race_bets in outcomes_df.groupby(['venue', 'race_number', 'race_date']):
            # Group by base strategy (remove bet type suffixes)
            race_bets['base_strategy'] = race_bets['strategy'].str.extract(r'(Strategy \d+)')[0]
            
            # Sort strategies numerically (Strategy 1, 2, 3, etc.)
            sorted_strategies = sorted(race_bets.groupby('base_strategy'), 
                                     key=lambda x: int(x[0].split()[-1]) if x[0].split()[-1].isdigit() else 999)
            
            for base_strategy, strategy_bets in sorted_strategies:
                total_stake = strategy_bets['stake'].sum()
                total_liability = strategy_bets['stake'].sum()  # Total amount risked
                
                # Check if race has results
                has_results = strategy_bets['has_results'].any()
                
                if has_results:
                    # Only calculate profits for races with results
                    settled_bets = strategy_bets[strategy_bets['has_results'] == True]
                    total_profit_loss = settled_bets['profit_loss'].sum()
                    
                    
                    # Calculate success rate from settled bets only
                    success_rate = 0.0
                    if not settled_bets.empty:
                        successful_bets = settled_bets[(settled_bets['won'] == True) | (settled_bets['placed'] == True)]
                        success_rate = (len(successful_bets) / len(settled_bets)) * 100
                    
                    # Calculate ROI from settled bets only
                    roi = 0.0
                    if total_liability > 0:
                        roi = (total_profit_loss / total_liability) * 100
                else:
                    # Race has no results - leave profit/ROI blank
                    total_profit_loss = None
                    success_rate = None
                    roi = None
                
                race_metrics.append({
                    'venue': venue,
                    'race_number': race_number,
                    'race_date': race_date,
                    'strategy': base_strategy,
                    'total_stake': total_stake,
                    'total_profit': total_profit_loss,
                    'total_liability': total_liability,
                    'success_rate': success_rate,
                    'roi': roi,
                    'num_bets': len(strategy_bets)
                })
        
        return pd.DataFrame(race_metrics)
    
    def export_strategy_summary_csv(self, output_file: str = None):
        if output_file is None:
            # Use current date for filename
            today = datetime.now().strftime("%d_%m")
            output_file = f"simulation_strategy_summary_{today}.csv"
        """Export strategy summary metrics to CSV"""
        logger.info("📈 Calculating strategy summary metrics...")
        
        performance_df = self.analyze_simulation_performance()
        
        if performance_df.empty:
            logger.warning("⚠️ No performance data to export")
            return
        
        # Group by strategy and calculate summary metrics
        strategy_summary = []
        for strategy, strategy_data in performance_df.groupby('strategy'):
            # Only include races with results for profit calculations
            settled_races = strategy_data[strategy_data['total_profit'].notna()]
            pending_races = strategy_data[strategy_data['total_profit'].isna()]
            
            # Count races
            unique_races = strategy_data[['venue', 'race_number', 'race_date']].drop_duplicates()
            settled_unique_races = settled_races[['venue', 'race_number', 'race_date']].drop_duplicates()
            pending_unique_races = pending_races[['venue', 'race_number', 'race_date']].drop_duplicates()
            
            num_races = len(unique_races)
            settled_race_count = len(settled_unique_races)
            pending_race_count = len(pending_unique_races)
            
            # Only calculate profits from settled races
            if not settled_races.empty:
                total_stake = settled_races['total_stake'].sum()
                total_liability = settled_races['total_liability'].sum()
                total_bets = settled_races['num_bets'].sum()
                total_profit = settled_races['total_profit'].sum()
                
                # Calculate success rate from individual bets for this strategy
                strategy_bets = performance_df[performance_df['strategy'] == strategy]
                settled_strategy_bets = strategy_bets[strategy_bets['total_profit'].notna()]
                if not settled_strategy_bets.empty:
                    # Get all individual bets for this strategy from the original data
                    # We need to recalculate this from the bet outcomes
                    avg_success_rate = settled_strategy_bets['success_rate'].mean()
                else:
                    avg_success_rate = 0.0
                
                roi = (total_profit / total_liability) * 100
            else:
                total_stake = 0.0
                total_liability = 0.0
                total_bets = 0
                total_profit = 0.0
                avg_success_rate = 0.0
                roi = 0.0
            
            strategy_summary.append({
                'strategy': strategy,
                'total_races': num_races,
                'settled_races': settled_race_count,
                'pending_races': pending_race_count,
                'total_bets': total_bets,
                'total_stake': total_stake,
                'total_profit': total_profit,
                'total_liability': total_liability,
                'avg_success_rate_%': avg_success_rate,
                'roi_%': roi
            })
        
        summary_df = pd.DataFrame(strategy_summary)
        
        # Round numeric columns to 2 decimal places
        numeric_columns = ['total_stake', 'total_profit', 'total_liability', 'avg_success_rate_%', 'roi_%']
        for col in numeric_columns:
            if col in summary_df.columns:
                summary_df[col] = summary_df[col].round(2)
        
        # Ensure all numeric columns are properly rounded
        for col in summary_df.columns:
            if col not in ['strategy', 'total_races', 'settled_races', 'pending_races', 'total_bets']:
                summary_df[col] = summary_df[col].round(2)
        
        # Add overall weighted total for all strategies combined
        overall_total = {
            'strategy': 'OVERALL WEIGHTED TOTAL',
            'total_races': 0,
            'settled_races': 0,
            'pending_races': 0,
            'total_bets': 0,
            'total_stake': 0.0,
            'total_profit': 0.0,
            'total_liability': 0.0,
            'avg_success_rate_%': 0.0,
            'roi_%': 0.0
        }
        
        # Calculate overall totals from all strategies
        for _, row in summary_df.iterrows():
            overall_total['total_races'] += row['total_races']
            overall_total['settled_races'] += row['settled_races']
            overall_total['pending_races'] += row['pending_races']
            overall_total['total_bets'] += row['total_bets']
            overall_total['total_stake'] += row['total_stake']
            overall_total['total_profit'] += row['total_profit']
            overall_total['total_liability'] += row['total_liability']
        
        # Calculate overall ROI and success rate
        if overall_total['total_liability'] > 0:
            overall_total['roi_%'] = (overall_total['total_profit'] / overall_total['total_liability']) * 100
        
        # Calculate overall success rate from all settled bets
        # We need to get this from the performance data
        all_settled_races = performance_df[performance_df['total_profit'].notna()]
        if not all_settled_races.empty:
            overall_total['avg_success_rate_%'] = all_settled_races['success_rate'].mean()
        
        # Add overall total to summary
        summary_df = pd.concat([summary_df, pd.DataFrame([overall_total])], ignore_index=True)
        
        # Round all numeric columns to 2 decimal places
        for col in summary_df.columns:
            if col not in ['strategy', 'total_races', 'settled_races', 'pending_races', 'total_bets']:
                summary_df[col] = summary_df[col].round(2)
        
        # Export to CSV
        summary_df.to_csv(output_file, index=False)
        logger.info(f"✅ Strategy summary exported to {output_file}")
        
        # Print summary
        print(f"\n📊 STRATEGY SUMMARY")
        for _, row in summary_df.iterrows():
            print(f"{row['strategy']}: {row['settled_races']} settled races, ${row['total_profit']:.2f} profit, {row['roi_%']:.1f}% ROI")
        
        return summary_df
    
    def export_performance_csv(self, output_file: str = None):
        if output_file is None:
            # Use current date for filename
            today = datetime.now().strftime("%d_%m")
            output_file = f"simulation_performance_{today}.csv"
        """Export performance metrics to CSV"""
        logger.info("📈 Calculating performance metrics...")
        
        performance_df = self.analyze_simulation_performance()
        
        if performance_df.empty:
            logger.warning("⚠️ No performance data to export")
            return
        
        # Round numeric columns to 2 decimal places
        numeric_columns = ['total_stake', 'total_profit', 'total_liability', 'success_rate', 'roi']
        for col in numeric_columns:
            if col in performance_df.columns:
                performance_df[col] = performance_df[col].round(2)
        
        # Export to CSV
        performance_df.to_csv(output_file, index=False)
        logger.info(f"✅ Performance metrics exported to {output_file}")
        
        # Print summary - only include races with results
        settled_races = performance_df[performance_df['total_profit'].notna()]
        
        # Count unique races
        unique_races = performance_df[['venue', 'race_number', 'race_date']].drop_duplicates()
        settled_unique_races = settled_races[['venue', 'race_number', 'race_date']].drop_duplicates()
        
        # Only calculate summary from settled races
        settled_stake = settled_races['total_stake'].sum()
        settled_profit = settled_races['total_profit'].sum()
        settled_liability = settled_races['total_liability'].sum()
        
        if settled_liability > 0:
            avg_roi = (settled_profit / settled_liability) * 100
        else:
            avg_roi = 0.0
        
        print(f"\n📊 SIMULATION PERFORMANCE SUMMARY")
        print(f"Total Races: {len(unique_races)}")
        print(f"Settled Races: {len(settled_unique_races)}")
        print(f"Pending Races: {len(unique_races) - len(settled_unique_races)}")
        print(f"Total Stake (Settled): ${settled_stake:.2f}")
        print(f"Total Profit: ${settled_profit:.2f}")
        print(f"Total Liability (Settled): ${settled_liability:.2f}")
        print(f"Average ROI: {avg_roi:.2f}%")
        
        return performance_df
    
    def export_detailed_strategy_summary_csv(self, output_file: str = None):
        if output_file is None:
            # Use current date for filename
            today = datetime.now().strftime("%d_%m")
            output_file = f"simulation_detailed_strategy_summary_{today}.csv"
        """Export detailed strategy summary metrics to CSV - shows each strategy component separately"""
        logger.info("📈 Calculating detailed strategy summary metrics...")
        
        # Get simulation bets
        bets_df = self.get_simulation_bets()
        if bets_df.empty:
            logger.warning("⚠️ No simulation bets found")
            return
        
        # Get race results
        results_df = self.get_race_results()
        if results_df.empty:
            logger.warning("⚠️ No race results found. Fetching results from Betfair...")
            market_ids = bets_df['market_id'].unique().tolist()
            self.results_fetcher.fetch_results(market_ids)
            results_df = self.get_race_results()
        
        if results_df.empty:
            logger.error("❌ No race results available for analysis")
            return
        
        # Calculate outcomes for each bet
        outcomes = []
        for _, bet in bets_df.iterrows():
            bet_dict = bet.to_dict()
            # Ensure lay_odds is included in the bet dictionary with actual value
            bet_dict['lay_odds'] = bet.get('lay_odds', 0.0)
            outcome = self.calculate_bet_outcome(bet_dict, results_df)
            outcomes.append({
                'market_id': bet['market_id'],
                'venue': bet['venue'],
                'race_number': bet['race_number'],
                'race_date': bet['race_date'],
                'strategy': bet['strategy'],
                'horse_name': bet['horse_name'],
                'bet_type': bet['bet_type'],
                'stake': bet['stake'],
                'win_odds': bet['win_odds'],
                'place_odds': bet['place_odds'],
                'finishing_position': outcome['finishing_position'],
                'won': outcome['won'],
                'placed': outcome['placed'],
                'profit_loss': outcome['profit_loss'],
                'has_results': outcome['has_results']
            })
        
        outcomes_df = pd.DataFrame(outcomes)
        
        # Extract base strategy name (e.g., "Strategy 1" from "Strategy 1 - Favorite Place")
        outcomes_df['base_strategy'] = outcomes_df['strategy'].str.extract(r'(Strategy \d+)')[0]
        
        # Calculate performance metrics by base strategy and bet type (grouped)
        strategy_metrics = []
        for (base_strategy, bet_type), strategy_bets in outcomes_df.groupby(['base_strategy', 'bet_type']):
            # Group by race to calculate race-level metrics
            race_metrics = []
            for (venue, race_number, race_date), race_bets in strategy_bets.groupby(['venue', 'race_number', 'race_date']):
                total_stake = race_bets['stake'].sum()
                total_liability = race_bets['stake'].sum()
                
                # Check if race has results
                has_results = race_bets['has_results'].any()
                
                if has_results:
                    # Only calculate profits for races with results
                    settled_bets = race_bets[race_bets['has_results'] == True]
                    total_profit_loss = settled_bets['profit_loss'].sum()
                    
                    # Calculate success rate from settled bets only
                    success_rate = 0.0
                    if not settled_bets.empty:
                        successful_bets = settled_bets[(settled_bets['won'] == True) | (settled_bets['placed'] == True)]
                        success_rate = (len(successful_bets) / len(settled_bets)) * 100
                    
                    # Calculate ROI from settled bets only
                    roi = 0.0
                    if total_liability > 0:
                        roi = (total_profit_loss / total_liability) * 100
                else:
                    # Race has no results - leave profit/ROI blank
                    total_profit_loss = None
                    success_rate = None
                    roi = None
                
                race_metrics.append({
                    'venue': venue,
                    'race_number': race_number,
                    'race_date': race_date,
                    'strategy': base_strategy,
                    'bet_type': bet_type,
                    'total_stake': total_stake,
                    'total_profit': total_profit_loss,
                    'total_liability': total_liability,
                    'success_rate': success_rate,
                    'roi': roi,
                    'num_bets': len(race_bets),
                    'has_results': has_results
                })
            
            # Calculate strategy-level summary
            race_metrics_df = pd.DataFrame(race_metrics)
            
            # Count races
            total_races = len(race_metrics_df)
            settled_races = len(race_metrics_df[race_metrics_df['has_results'] == True])
            pending_races = total_races - settled_races
            
            # Only calculate profits from settled races
            settled_races_df = race_metrics_df[race_metrics_df['has_results'] == True]
            
            if not settled_races_df.empty:
                total_stake = settled_races_df['total_stake'].sum()
                total_liability = settled_races_df['total_liability'].sum()
                total_bets = settled_races_df['num_bets'].sum()
                total_profit = settled_races_df['total_profit'].sum()
                avg_success_rate = settled_races_df['success_rate'].mean()
                roi = (total_profit / total_liability) * 100 if total_liability > 0 else 0.0
            else:
                total_stake = 0.0
                total_liability = 0.0
                total_bets = 0
                total_profit = 0.0
                avg_success_rate = 0.0
                roi = 0.0
            
            # Create strategy name with bet type
            strategy_name = f"{base_strategy} - {bet_type.title()}"
            
            # Calculate weighted average ROI
            weighted_roi = 0.0
            if total_liability > 0:
                weighted_roi = (total_profit / total_liability) * 100
            
            strategy_metrics.append({
                'strategy': strategy_name,
                'settled_races': settled_races,
                'pending_races': pending_races,
                'total_stake': total_stake,
                'total_profit': total_profit,
                'total_liability': total_liability,
                'total_bets': total_bets,
                'avg_success_rate_%': avg_success_rate,
                'roi_%': weighted_roi
            })
        
        # Add weighted summary rows for each base strategy
        weighted_summaries = []
        # Sort strategies numerically
        unique_strategies = sorted(outcomes_df['base_strategy'].unique(), 
                                 key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999)
        
        for base_strategy in unique_strategies:
            if pd.isna(base_strategy):
                continue
                
            # Get all bets for this base strategy
            strategy_bets = outcomes_df[outcomes_df['base_strategy'] == base_strategy]
            
            # Group by race to calculate race-level metrics
            race_metrics = []
            for (venue, race_number, race_date), race_bets in strategy_bets.groupby(['venue', 'race_number', 'race_date']):
                total_stake = race_bets['stake'].sum()
                total_liability = race_bets['stake'].sum()
                
                # Check if race has results
                has_results = race_bets['has_results'].any()
                
                if has_results:
                    # Only calculate profits for races with results
                    settled_bets = race_bets[race_bets['has_results'] == True]
                    total_profit_loss = settled_bets['profit_loss'].sum()
                    
                    # Calculate success rate from settled bets only
                    success_rate = 0.0
                    if not settled_bets.empty:
                        successful_bets = settled_bets[(settled_bets['won'] == True) | (settled_bets['placed'] == True)]
                        success_rate = (len(successful_bets) / len(settled_bets)) * 100
                    
                    # Calculate ROI from settled bets only
                    roi = 0.0
                    if total_liability > 0:
                        roi = (total_profit_loss / total_liability) * 100
                else:
                    # Race has no results - leave profit/ROI blank
                    total_profit_loss = None
                    success_rate = None
                    roi = None
                
                race_metrics.append({
                    'venue': venue,
                    'race_number': race_number,
                    'race_date': race_date,
                    'total_stake': total_stake,
                    'total_profit': total_profit_loss,
                    'total_liability': total_liability,
                    'success_rate': success_rate,
                    'roi': roi,
                    'num_bets': len(race_bets),
                    'has_results': has_results
                })
            
            # Calculate strategy-level summary
            race_metrics_df = pd.DataFrame(race_metrics)
            
            # Count races
            total_races = len(race_metrics_df)
            settled_races = len(race_metrics_df[race_metrics_df['has_results'] == True])
            pending_races = total_races - settled_races
            
            # Only calculate profits from settled races
            settled_races_df = race_metrics_df[race_metrics_df['has_results'] == True]
            
            if not settled_races_df.empty:
                total_stake = settled_races_df['total_stake'].sum()
                total_liability = settled_races_df['total_liability'].sum()
                total_bets = settled_races_df['num_bets'].sum()
                total_profit = settled_races_df['total_profit'].sum()
                
                # Calculate success rate from individual bets
                settled_bets = strategy_bets[strategy_bets['has_results'] == True]
                if not settled_bets.empty:
                    successful_bets = settled_bets[(settled_bets['won'] == True) | (settled_bets['placed'] == True)]
                    avg_success_rate = (len(successful_bets) / len(settled_bets)) * 100
                else:
                    avg_success_rate = 0.0
                
                weighted_roi = (total_profit / total_liability) * 100 if total_liability > 0 else 0.0
            else:
                total_stake = 0.0
                total_liability = 0.0
                total_bets = 0
                total_profit = 0.0
                avg_success_rate = 0.0
                weighted_roi = 0.0
            
            weighted_summaries.append({
                'strategy': f"{base_strategy} - Weighted Total",
                'settled_races': settled_races,
                'pending_races': pending_races,
                'total_stake': total_stake,
                'total_profit': total_profit,
                'total_liability': total_liability,
                'total_bets': total_bets,
                'avg_success_rate_%': avg_success_rate,
                'roi_%': weighted_roi
            })
        
        # Add overall weighted total for all strategies combined
        overall_total = {
            'strategy': 'OVERALL WEIGHTED TOTAL',
            'settled_races': 0,
            'pending_races': 0,
            'total_stake': 0.0,
            'total_profit': 0.0,
            'total_liability': 0.0,
            'total_bets': 0,
            'avg_success_rate_%': 0.0,
            'roi_%': 0.0
        }
        
        # Calculate overall totals from all settled races
        # Sort strategies numerically
        unique_strategies = sorted(outcomes_df['base_strategy'].unique(), 
                                 key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999)
        
        for base_strategy in unique_strategies:
            if pd.isna(base_strategy):
                continue
                
            # Get all bets for this base strategy
            strategy_bets = outcomes_df[outcomes_df['base_strategy'] == base_strategy]
            
            # Group by race to calculate race-level metrics
            for (venue, race_number, race_date), race_bets in strategy_bets.groupby(['venue', 'race_number', 'race_date']):
                total_stake = race_bets['stake'].sum()
                total_liability = race_bets['stake'].sum()
                
                # Check if race has results
                has_results = race_bets['has_results'].any()
                
                if has_results:
                    # Only calculate profits for races with results
                    settled_bets = race_bets[race_bets['has_results'] == True]
                    total_profit_loss = settled_bets['profit_loss'].sum()
                    
                    # Add to overall totals
                    overall_total['settled_races'] += 1
                    overall_total['total_stake'] += total_stake
                    overall_total['total_liability'] += total_liability
                    overall_total['total_profit'] += total_profit_loss
                    overall_total['total_bets'] += len(race_bets)
                else:
                    overall_total['pending_races'] += 1
        
        # Calculate overall ROI and success rate
        if overall_total['total_liability'] > 0:
            overall_total['roi_%'] = (overall_total['total_profit'] / overall_total['total_liability']) * 100
        
        # Calculate overall success rate from all settled bets
        all_settled_bets = outcomes_df[outcomes_df['has_results'] == True]
        if not all_settled_bets.empty:
            successful_bets = all_settled_bets[(all_settled_bets['won'] == True) | (all_settled_bets['placed'] == True)]
            overall_total['avg_success_rate_%'] = (len(successful_bets) / len(all_settled_bets)) * 100
        
        # Combine individual strategy components with weighted summaries and overall total
        all_summaries = strategy_metrics + weighted_summaries + [overall_total]
        summary_df = pd.DataFrame(all_summaries)
        
        # Round numeric columns to 2 decimal places
        numeric_columns = ['total_stake', 'total_profit', 'total_liability', 'avg_success_rate_%', 'roi_%']
        for col in numeric_columns:
            if col in summary_df.columns:
                summary_df[col] = summary_df[col].round(2)
        
        # Export to CSV
        summary_df.to_csv(output_file, index=False)
        logger.info(f"✅ Detailed strategy summary exported to {output_file}")
        
        # Print summary
        print(f"\n📊 DETAILED STRATEGY SUMMARY")
        for _, row in summary_df.iterrows():
            print(f"{row['strategy']}: {row['settled_races']} settled races, ${row['total_profit']:.2f} profit, {row['roi_%']:.1f}% ROI")
        
        return summary_df

def main():
    """Main function to run the analysis"""
    analyzer = SimulationResultsAnalyzer()
    analyzer.export_performance_csv()
    analyzer.export_strategy_summary_csv()
    analyzer.export_detailed_strategy_summary_csv()

if __name__ == "__main__":
    main()
