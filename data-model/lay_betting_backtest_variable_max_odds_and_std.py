#!/usr/bin/env python3
"""
Lay Betting Backtest Script - Variable Max Odds AND Variable Standard Deviation
Combines field-size-based max odds with adaptive std thresholds for optimal performance
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
import sqlite3

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LayBettingBacktestVariableMaxOddsAndStd:
    """
    Lay betting backtest with variable max odds AND variable standard deviation
    based on field size for optimal performance across all race types
    """
    
    def __init__(self, csv_file: str, base_max_odds: float = 30.0, base_std_threshold: float = 1.0):
        """
        Initialize the backtest with variable parameters
        
        Args:
            csv_file: Path to the racing data CSV
            base_max_odds: Base max odds for 12-horse field (default: 30.0)
            base_std_threshold: Base std threshold for 12-horse field (default: 1.0)
        """
        self.csv_file = csv_file
        self.base_max_odds = base_max_odds
        self.base_std_threshold = base_std_threshold
        self.df = None
        self.results = LayBettingResults()
        
    def calculate_variable_max_odds(self, field_size: int) -> float:
        """
        Calculate max odds based on field size
        Formula: MaxOddsAllowed = base_max_odds × (field_size / 12)
        
        Examples:
        - 6 horses → 30 × (6/12) = 15.0
        - 12 horses → 30 × (12/12) = 30.0  
        - 18 horses → 30 × (18/12) = 45.0
        """
        return self.base_max_odds * (field_size / 12.0)
    
    def calculate_variable_std_threshold(self, field_size: int) -> float:
        """
        Calculate std threshold based on field size
        Formula: StdThreshold = base_std × (field_size / 12)
        
        Examples:
        - 6 horses → 1.0 × (6/12) = 0.5
        - 12 horses → 1.0 × (12/12) = 1.0
        - 18 horses → 1.0 × (18/12) = 1.5
        """
        return self.base_std_threshold * (field_size / 12.0)
    
    def load_data(self):
        """Load racing data from CSV"""
        logger.info("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_file)
        logger.info(f"✅ Loaded {len(self.df)} race entries")
    
    def get_race_groups(self):
        """Group data by race (meeting + date + race number)"""
        if self.df is None:
            self.load_data()
        return self.df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    
    def analyze_race_eligibility_variable(self, race_data: pd.DataFrame, odds_column: str = 'FixedWinClose_Reference'):
        """
        Check if a race meets our lay betting criteria with variable max odds AND std threshold
        
        Args:
            race_data: DataFrame containing race data
            odds_column: Column name for odds data
            
        Returns:
            Tuple of (is_eligible, reason, eligible_horses, variable_max_odds, variable_std_threshold)
        """
        # Check 1: Must have at least 6 horses
        if len(race_data) < 6:
            return False, f"Too few horses ({len(race_data)})", None, None, None
        
        # Check 2: All horses must have odds
        horses_with_odds = race_data[race_data[odds_column].notna() & (race_data[odds_column] > 0)]
        if len(horses_with_odds) < 6:
            return False, f"Too few horses with odds ({len(horses_with_odds)})", None, None, None
        
        # Calculate variable parameters based on field size
        field_size = len(horses_with_odds)
        variable_max_odds = self.calculate_variable_max_odds(field_size)
        variable_std_threshold = self.calculate_variable_std_threshold(field_size)
        
        # Check 3: Calculate standard deviation of odds
        odds_std = horses_with_odds[odds_column].std()
        if pd.isna(odds_std) or odds_std <= 0:
            return False, "Invalid odds standard deviation", None, None, None
        
        # Check 4: Standard deviation must be above variable threshold
        if odds_std < variable_std_threshold:
            return False, f"Std dev {odds_std:.2f} below variable threshold {variable_std_threshold:.2f}", None, None, None
        
        # Check 5: Sort horses by odds and split into top/bottom half
        horses_sorted = horses_with_odds.sort_values(odds_column)
        top_half = horses_sorted.head(len(horses_sorted) // 2)
        bottom_half = horses_sorted.tail(len(horses_sorted) // 2)
        
        # Check 6: Filter bottom half horses with odds <= variable_max_odds
        eligible_horses = bottom_half[bottom_half[odds_column] <= variable_max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {variable_max_odds:.1f}:1 (field size: {field_size})", None, None, None
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay (max odds: {variable_max_odds:.1f}:1, std: {variable_std_threshold:.1f})", eligible_horses, variable_max_odds, variable_std_threshold

    def calculate_lay_bet_profit(self, horse_odds: float, horse_finished_position: float, stake: float = 1) -> float:
        """
        Calculate lay bet profit/loss
        
        Lay bet: We bet AGAINST the horse winning
        - If horse loses (position > 1): We win the stake
        - If horse wins (position = 1): We lose (odds - 1) * stake
        """
        if horse_finished_position == 1:  # Horse won
            loss = (horse_odds - 1) * stake
            return -loss
        else:  # Horse lost (or scratched/abandoned)
            return stake

    def run_backtest(self, stake_per_bet: float = 1, verbose: bool = True):
        """
        Run the backtest using variable max odds AND variable std threshold based on field size
        
        Args:
            stake_per_bet: Amount to stake per bet
            verbose: Whether to print detailed output
        """
        if self.df is None:
            self.load_data()
        
        race_groups = self.get_race_groups()
        total_races = len(race_groups)
        
        if verbose:
            logger.info(f"🏁 Starting backtest on {total_races} races")
            logger.info(f"📋 Strategy: Variable max odds AND std threshold based on field size")
            logger.info(f"📊 Base max odds: {self.base_max_odds}:1 for 12-horse field")
            logger.info(f"📊 Base std threshold: {self.base_std_threshold} for 12-horse field")
        
        for (meeting, date, race_num), race_data in race_groups:
            # Use variable max odds AND std threshold strategy to analyze race eligibility
            is_eligible, reason, eligible_horses, variable_max_odds, variable_std_threshold = self.analyze_race_eligibility_variable(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                if verbose:
                    logger.debug(f"❌ {meeting} {date} R{race_num}: {reason}")
                continue
            
            # Place lay bets on eligible horses
            for _, horse in eligible_horses.iterrows():
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                
                # Calculate profit using variable max odds logic
                profit = self.calculate_lay_bet_profit(
                    horse_odds, finishing_pos, stake_per_bet
                )
                
                won_bet = profit > 0
                
                bet_data = {
                    'meeting': meeting,
                    'date': date,
                    'race_num': race_num,
                    'horse_name': horse.get('runnerName', 'Unknown'),
                    'cloth_number': horse.get('clothNumber', 0),
                    'odds': horse_odds,
                    'finishing_position': finishing_pos,
                    'stake': stake_per_bet,
                    'profit': profit,
                    'won': won_bet,
                    'variable_max_odds': variable_max_odds,
                    'variable_std_threshold': variable_std_threshold,
                    'field_size': len(race_data)
                }
                
                self.results.add_bet(bet_data)
                
                if verbose:
                    logger.debug(f"  🐎 {horse.get('clothNumber', 0)}. {horse.get('runnerName', 'Unknown')} - Lay @ {horse_odds:.2f} → {finishing_pos} → ${profit:.2f} (max: {variable_max_odds:.1f}:1, std: {variable_std_threshold:.1f})")
        
        if verbose:
            logger.info(f"✅ Backtest complete: {self.results.total_bets} bets, ${self.results.total_profit:.2f} profit, {self.results.roi:.1f}% ROI")
        
        return self.results

    def run_backtest_on_filtered_races(self, filtered_races: list, stake_per_bet: float = 1, verbose: bool = True):
        """
        Run the backtest on a specific set of filtered races
        
        Args:
            filtered_races: List of (race_key, race_data) tuples
            stake_per_bet: Amount to stake per bet
            verbose: Whether to print detailed output
        """
        if self.df is None:
            self.load_data()
        
        total_races = len(filtered_races)
        
        if verbose:
            logger.info(f"🏁 Starting backtest on {total_races} filtered races")
            logger.info(f"📋 Strategy: Variable max odds AND std threshold based on field size")
            logger.info(f"📊 Base max odds: {self.base_max_odds}:1 for 12-horse field")
            logger.info(f"📊 Base std threshold: {self.base_std_threshold} for 12-horse field")
        
        for (meeting, date, race_num), race_data in filtered_races:
            # Use variable max odds AND std threshold strategy to analyze race eligibility
            is_eligible, reason, eligible_horses, variable_max_odds, variable_std_threshold = self.analyze_race_eligibility_variable(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                if verbose:
                    logger.debug(f"❌ {meeting} {date} R{race_num}: {reason}")
                continue
            
            # Place lay bets on eligible horses
            for _, horse in eligible_horses.iterrows():
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                
                # Calculate profit using variable max odds logic
                profit = self.calculate_lay_bet_profit(
                    horse_odds, finishing_pos, stake_per_bet
                )
                
                won_bet = profit > 0
                
                bet_data = {
                    'meeting': meeting,
                    'date': date,
                    'race_num': race_num,
                    'horse_name': horse.get('runnerName', 'Unknown'),
                    'cloth_number': horse.get('clothNumber', 0),
                    'odds': horse_odds,
                    'finishing_position': finishing_pos,
                    'stake': stake_per_bet,
                    'profit': profit,
                    'won': won_bet,
                    'variable_max_odds': variable_max_odds,
                    'variable_std_threshold': variable_std_threshold,
                    'field_size': len(race_data)
                }
                
                self.results.add_bet(bet_data)
                
                if verbose:
                    logger.debug(f"  🐎 {horse.get('clothNumber', 0)}. {horse.get('runnerName', 'Unknown')} - Lay @ {horse_odds:.2f} → {finishing_pos} → ${profit:.2f} (max: {variable_max_odds:.1f}:1, std: {variable_std_threshold:.1f})")
        
        if verbose:
            logger.info(f"✅ Backtest complete: {self.results.total_bets} bets, ${self.results.total_profit:.2f} profit, {self.results.roi:.1f}% ROI")
        
        return self.results

    def export_to_csv(self, filename: str = None):
        """Export results to CSV"""
        if filename is None:
            filename = "lay_betting_results_variable_max_odds_and_std.csv"
        
        if len(self.results.bets) == 0:
            logger.warning("No bets to export")
            return
        
        df = pd.DataFrame(self.results.bets)
        
        # Round numeric columns to 2 decimal places
        numeric_columns = ['odds', 'profit', 'variable_max_odds', 'variable_std_threshold']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].round(2)
        
        df.to_csv(filename, index=False)
        logger.info(f"💾 Results exported to {filename}")

class LayBettingResults:
    """Container for lay betting results"""
    
    def __init__(self):
        self.bets = []
        self.total_bets = 0
        self.total_profit = 0.0
        self.winning_bets = 0
        self.roi = 0.0
        self.win_rate = 0.0
    
    def add_bet(self, bet_data: dict):
        """Add a bet to the results"""
        self.bets.append(bet_data)
        self.total_bets += 1
        self.total_profit += bet_data['profit']
        
        if bet_data['won']:
            self.winning_bets += 1
        
        # Update ROI and win rate
        if self.total_bets > 0:
            self.roi = (self.total_profit / self.total_bets) * 100
            self.win_rate = (self.winning_bets / self.total_bets) * 100

def test_std_thresholds():
    """Test different base std thresholds with variable max odds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    base_std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    base_max_odds = [20, 25, 30]  # Base max odds for 12-horse field
    target_field_sizes = list(range(6, 25))  # Test field sizes from 6 to 24 horses
    results = []
    
    logger.info("🔬 COMPREHENSIVE LAY BETTING ANALYSIS - VARIABLE MAX ODDS AND STD THRESHOLD")
    logger.info("=" * 80)
    logger.info(f"Testing {len(base_std_thresholds)} base std thresholds × {len(base_max_odds)} base max odds × {len(target_field_sizes)} field sizes")
    
    for base_std in base_std_thresholds:
        for base_max_odd in base_max_odds:
            for target_field_size in target_field_sizes:
                logger.info(f"🎯 Testing: Base Std {base_std}, Base Max Odds {base_max_odd}, Field Size {target_field_size}")
                
                # Create backtest instance
                backtest = LayBettingBacktestVariableMaxOddsAndStd(
                    csv_file=csv_file,
                    base_max_odds=base_max_odd,
                    base_std_threshold=base_std
                )
                
                # Reset results for each test
                backtest.results = LayBettingResults()
                
                # Filter races by field size
                race_groups = backtest.get_race_groups()
                filtered_races = []
                
                for (meeting, date, race_num), race_data in race_groups:
                    if len(race_data) == target_field_size:
                        filtered_races.append(((meeting, date, race_num), race_data))
                
                if len(filtered_races) == 0:
                    logger.info(f"  ⚠️ No races found with {target_field_size} horses")
                    continue
                
                # Run backtest on filtered races
                backtest.run_backtest_on_filtered_races(filtered_races, verbose=False)
                
                # Calculate results
                total_bets = backtest.results.total_bets
                total_profit = backtest.results.total_profit
                roi = (total_profit / total_bets * 100) if total_bets > 0 else 0
                
                # Calculate actual win rate (percentage of winning bets)
                winning_bets = sum(1 for bet in backtest.results.bets if bet.get('won', False))
                win_rate = (winning_bets / total_bets * 100) if total_bets > 0 else 0
                
                # Calculate variable parameters
                variable_max_odds = base_max_odd * (target_field_size / 12.0)
                variable_std_threshold = base_std * (target_field_size / 12.0)
                
                # Count actually eligible races (races that passed the strategy criteria)
                eligible_races_count = 0
                for (meeting, date, race_num), race_data in filtered_races:
                    is_eligible, reason, eligible_horses, _, _ = backtest.analyze_race_eligibility_variable(
                        race_data, 'FixedWinClose_Reference'
                    )
                    if is_eligible:
                        eligible_races_count += 1
                
                result = {
                    'field_size': target_field_size,
                    'base_std_threshold': base_std,
                    'base_max_odds': base_max_odd,
                    'variable_max_odds': variable_max_odds,
                    'variable_std_threshold': variable_std_threshold,
                    'total_races': len(filtered_races),
                    'eligible_races': eligible_races_count,
                    'total_bets': total_bets,
                    'total_profit': total_profit,
                    'roi': roi,
                    'win_rate': win_rate
                }
                results.append(result)
                
                logger.info(f"  ✅ Eligible: {result['eligible_races']}/{len(filtered_races)}, Bets: {total_bets}, ROI: {roi:.1f}%, Profit: ${total_profit:.2f}")
    
    # Save results to CSV with 2 decimal places
    df = pd.DataFrame(results)
    
    # Round numeric columns to 2 decimal places
    numeric_columns = ['variable_max_odds', 'variable_std_threshold', 'total_profit', 'roi', 'win_rate']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].round(2)
    
    csv_filename = "lay_betting_backtest_variable_max_odds_and_std.csv"
    df.to_csv(csv_filename, index=False)
    
    logger.info(f"\n💾 Results saved to {csv_filename}")
    
    # Summary table
    logger.info(f"\n📈 SUMMARY TABLE")
    logger.info("=" * 120)
    logger.info(f"{'Field':<5} {'BaseStd':<6} {'BaseMax':<6} {'VarMax':<6} {'VarStd':<6} {'Races':<6} {'Eligible':<8} {'Bets':<6} {'ROI':<6} {'Profit':<10}")
    logger.info("-" * 120)
    
    for result in results:
        logger.info(f"{result['field_size']:<5} {result['base_std_threshold']:<6} {result['base_max_odds']:<6} {result['variable_max_odds']:<6.1f} {result['variable_std_threshold']:<6.1f} {result['total_races']:<6} {result['eligible_races']:<8} {result['total_bets']:<6} {result['roi']:<6.1f}% ${result['total_profit']:<9.2f}")
    
    # Top performers
    logger.info(f"\n🏆 TOP 5 PERFORMERS BY ROI:")
    top_roi = sorted(results, key=lambda x: x['roi'], reverse=True)[:5]
    for i, result in enumerate(top_roi, 1):
        logger.info(f"{i}. Field: {result['field_size']}, Base Std: {result['base_std_threshold']}, Base Max Odds: {result['base_max_odds']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    logger.info(f"\n💰 TOP 5 PERFORMERS BY TOTAL PROFIT:")
    top_profit = sorted(results, key=lambda x: x['total_profit'], reverse=True)[:5]
    for i, result in enumerate(top_profit, 1):
        logger.info(f"{i}. Field: {result['field_size']}, Base Std: {result['base_std_threshold']}, Base Max Odds: {result['base_max_odds']}, Profit: ${result['total_profit']:.2f}, ROI: {result['roi']:.1f}%")
    
    # Best overall
    best_overall = max(results, key=lambda x: x['roi'])
    logger.info(f"\n🏆 OVERALL BEST PERFORMANCE:")
    logger.info(f"  Field size: {best_overall['field_size']}")
    logger.info(f"  Base std threshold: {best_overall['base_std_threshold']}")
    logger.info(f"  Base max odds: {best_overall['base_max_odds']}")
    logger.info(f"  Variable max odds: {best_overall['variable_max_odds']:.1f}")
    logger.info(f"  Variable std threshold: {best_overall['variable_std_threshold']:.1f}")
    logger.info(f"  ROI: {best_overall['roi']:.1f}%")
    logger.info(f"  Eligible races: {best_overall['eligible_races']}")
    logger.info(f"  Total bets: {best_overall['total_bets']}")
    logger.info(f"  Total profit: ${best_overall['total_profit']:.2f}")
    
    return results

def main():
    """Main function to run the comprehensive analysis"""
    logger.info("🚀 Starting Variable Max Odds AND Standard Deviation Analysis")
    results = test_std_thresholds()
    logger.info("✅ Analysis complete!")

if __name__ == "__main__":
    main()
