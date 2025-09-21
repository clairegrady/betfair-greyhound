"""
Lay Betting Backtest Script - Uses closing reference odds with variable max odds based on field size
"""
import pandas as pd
import numpy as np
from shared_lay_betting import LayBettingStrategy, LayBettingResults
from collections import defaultdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingBacktestVariableMaxOdds:
    """
    Lay betting backtest using variable max odds based on field size
    Formula: MaxOddsAllowed = 30 × (N/12) where N = field size
    """
    
    def __init__(self, csv_file: str, std_threshold: float = 1.5, base_max_odds: float = 30.0):
        self.csv_file = csv_file
        self.std_threshold = std_threshold
        self.base_max_odds = base_max_odds  # Base max odds for 12-horse field
        self.results = LayBettingResults()
        self.df = None
        self.race_stats = defaultdict(list)
    
    def calculate_variable_max_odds(self, field_size: int) -> float:
        """
        Calculate max odds based on field size
        Formula: MaxOddsAllowed = 30 × (N/12)
        
        Examples:
        - N=12 → 30 × (12/12) = 30
        - N=18 → 30 × (18/12) = 45  
        - N=8  → 30 × (8/12) = 20
        """
        return self.base_max_odds * (field_size / 12.0)
    
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
        Check if a race meets our lay betting criteria with variable max odds
        
        Args:
            race_data: DataFrame with race odds data
            odds_column: Column name containing the odds
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses, variable_max_odds)
        """
        # Filter out horses without odds for analysis
        horses_with_odds = race_data.dropna(subset=[odds_column])
        
        # Check 1: Must have at least 4 horses total
        if len(race_data) < 4:
            return False, f"Less than 4 horses (total: {len(race_data)})", None, 0
        
        # Check 2: Must have at least 4 horses with odds
        if len(horses_with_odds) < 4:
            return False, f"Less than 4 horses with odds (total: {len(race_data)}, with odds: {len(horses_with_odds)})", None, 0
        
        # Calculate variable max odds based on field size
        field_size = len(horses_with_odds)
        variable_max_odds = self.calculate_variable_max_odds(field_size)
        
        # Sort by odds (lowest first)
        horses_with_odds = horses_with_odds.sort_values(odds_column)
        
        # Check 3: Get top half horses (lowest odds)
        top_half_count = len(horses_with_odds) // 2
        top_half = horses_with_odds.head(top_half_count)
        
        # Check 4: Calculate odds variance in top half
        top_half_odds = top_half[odds_column].values
        odds_std = np.std(top_half_odds)
        
        # If standard deviation is less than threshold, odds are too similar
        if odds_std < self.std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f})", None, variable_max_odds
        
        # Check 5: Get bottom half horses (highest odds)
        bottom_half = horses_with_odds.iloc[top_half_count:]  # Bottom half (0-indexed)
        
        # Check 6: Filter bottom half horses with odds <= variable_max_odds
        eligible_horses = bottom_half[bottom_half[odds_column] <= variable_max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {variable_max_odds:.1f}:1 (field size: {field_size})", None, variable_max_odds
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay (max odds: {variable_max_odds:.1f}:1)", eligible_horses, variable_max_odds

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
        Run the backtest using variable max odds based on field size
        
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
            logger.info(f"📋 Strategy: Variable max odds based on field size (base: {self.base_max_odds}:1 for 12-horse field)")
            logger.info(f"📊 Std threshold: {self.std_threshold}")
        
        for (meeting, date, race_num), race_data in race_groups:
            # Use variable max odds strategy to analyze race eligibility
            is_eligible, reason, eligible_horses, variable_max_odds = self.analyze_race_eligibility_variable(
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
                    'field_size': len(race_data)
                }
                
                self.results.add_bet(bet_data)
                
                if verbose:
                    logger.debug(f"  🐎 {horse.get('clothNumber', 0)}. {horse.get('runnerName', 'Unknown')} - Lay @ {horse_odds:.2f} → {finishing_pos} → ${profit:.2f} (max: {variable_max_odds:.1f}:1)")
        
        if verbose:
            stats = self.results.get_statistics()
            logger.info(f"✅ Backtest complete: {stats['total_bets']} bets, ROI: {stats['roi']:.1f}%, Profit: ${stats['total_profit']:.2f}")


def test_std_thresholds():
    """Test different standard deviation thresholds with variable max odds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    results = []
    
    logger.info("🔬 Testing different std thresholds with variable max odds...")
    
    for std_threshold in std_thresholds:
        backtest = LayBettingBacktestVariableMaxOdds(csv_file, std_threshold, 30.0)
        backtest.run_backtest(stake_per_bet=1, verbose=False)
        
        # Count eligible races
        race_groups = backtest.get_race_groups()
        eligible_count = 0
        for (meeting, date, race_num), race_data in race_groups:
            is_eligible, _, _, _ = backtest.analyze_race_eligibility_variable(race_data, 'FixedWinClose_Reference')
            if is_eligible:
                eligible_count += 1
        
        stats = backtest.results.get_statistics()
        stats.update({
            'std_threshold': std_threshold,
            'base_max_odds': 30.0,
            'total_races': len(race_groups),
            'eligible_races': eligible_count
        })
        results.append(stats)
        
        logger.info(f"  📊 Std: {std_threshold}, Eligible: {eligible_count}, ROI: {stats['roi']:.1f}%")
    
    return results


def comprehensive_analysis():
    """Test different std thresholds with variable max odds based on field size"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    base_max_odds = [20, 25, 30]  # Base max odds for 12-horse field
    # Test field sizes from 6 to 24 horses (include 6 horses - 463 races is sufficient)
    target_field_sizes = list(range(6, 25))  # Test field sizes from 6 to 24 horses
    results = []
    
    logger.info("🔬 COMPREHENSIVE LAY BETTING ANALYSIS - VARIABLE MAX ODDS BY FIELD SIZE")
    logger.info("=" * 80)
    logger.info(f"Testing {len(std_thresholds)} std thresholds × {len(base_max_odds)} base max odds × {len(target_field_sizes)} field sizes")
    logger.info("Formula: MaxOddsAllowed = BaseMaxOdds × (FieldSize/12)")
    logger.info("=" * 80)
    
    for target_field_size in target_field_sizes:
        logger.info(f"\n🎯 TESTING FIELD SIZE: {target_field_size} horses")
        logger.info("=" * 50)
        
        for base_max_odd in base_max_odds:
            logger.info(f"📊 Base Max Odds: {base_max_odd}:1 → Max Odds for {target_field_size} horses: {base_max_odd * (target_field_size/12):.1f}:1")
            
            for std_threshold in std_thresholds:
                backtest = LayBettingBacktestVariableMaxOdds(csv_file, std_threshold, base_max_odd)
                
                # Filter races to only include the target field size
                race_groups = backtest.get_race_groups()
                filtered_races = []
                for (meeting, date, race_num), race_data in race_groups:
                    if len(race_data) == target_field_size:
                        filtered_races.append(((meeting, date, race_num), race_data))
                
                logger.info(f"  Found {len(filtered_races)} races with exactly {target_field_size} horses")
                
                if len(filtered_races) == 0:
                    logger.info(f"  ⚠️ No races with {target_field_size} horses found")
                    continue
                
                # Run backtest on filtered races
                eligible_count = 0
                total_bets = 0
                total_profit = 0
                
                for (meeting, date, race_num), race_data in filtered_races:
                    is_eligible, _, eligible_horses, variable_max_odds = backtest.analyze_race_eligibility_variable(race_data, 'FixedWinClose_Reference')
                    
                    if is_eligible:
                        eligible_count += 1
                        for _, horse in eligible_horses.iterrows():
                            horse_odds = horse['FixedWinClose_Reference']
                            finishing_pos = horse['finishingPosition']
                            profit = backtest.calculate_lay_bet_profit(horse_odds, finishing_pos, 1.0)
                            total_bets += 1
                            total_profit += profit
                
                # Calculate results
                roi = (total_profit / total_bets * 100) if total_bets > 0 else 0
                # Calculate actual win rate (percentage of winning bets)
                winning_bets = sum(1 for bet in backtest.results.bets if bet.get('won', False))
                win_rate = (winning_bets / total_bets * 100) if total_bets > 0 else 0
                
                result = {
                    'field_size': target_field_size,
                    'std_threshold': std_threshold,
                    'base_max_odds': base_max_odd,
                    'variable_max_odds': base_max_odd * (target_field_size/12),
                    'total_races': len(filtered_races),
                    'eligible_races': eligible_count,
                    'total_bets': total_bets,
                    'total_profit': total_profit,
                    'roi': roi,
                    'win_rate': win_rate
                }
                results.append(result)
                
                logger.info(f"  ✅ Eligible: {eligible_count}/{len(filtered_races)}, Bets: {total_bets}, ROI: {roi:.1f}%, Profit: ${total_profit:.2f}")
    
    # Save results to CSV with 2 decimal places
    df = pd.DataFrame(results)
    
    # Round numeric columns to 2 decimal places
    numeric_columns = ['variable_max_odds', 'total_profit', 'roi', 'win_rate']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].round(2)
    
    csv_filename = "comprehensive_lay_analysis_results_variable_max_odds.csv"
    df.to_csv(csv_filename, index=False)
    
    logger.info(f"\n💾 Results saved to {csv_filename}")
    
    # Summary table
    logger.info(f"\n📈 SUMMARY TABLE")
    logger.info("=" * 120)
    logger.info(f"{'Field':<5} {'Std':<4} {'Base':<4} {'VarMax':<6} {'Races':<6} {'Eligible':<8} {'Bets':<6} {'ROI':<6} {'Profit':<10}")
    logger.info("-" * 120)
    
    for result in results:
        logger.info(f"{result['field_size']:<5} {result['std_threshold']:<4} {result['base_max_odds']:<4} {result['variable_max_odds']:<6.1f} {result['total_races']:<6} {result['eligible_races']:<8} {result['total_bets']:<6} {result['roi']:<6.1f}% ${result['total_profit']:<9.2f}")
    
    # Top performers
    logger.info(f"\n🏆 TOP 5 PERFORMERS BY ROI:")
    top_roi = sorted(results, key=lambda x: x['roi'], reverse=True)[:5]
    for i, result in enumerate(top_roi, 1):
        logger.info(f"{i}. Std: {result['std_threshold']}, Base Max Odds: {result['base_max_odds']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    logger.info(f"\n💰 TOP 5 PERFORMERS BY TOTAL PROFIT:")
    top_profit = sorted(results, key=lambda x: x['total_profit'], reverse=True)[:5]
    for i, result in enumerate(top_profit, 1):
        logger.info(f"{i}. Std: {result['std_threshold']}, Base Max Odds: {result['base_max_odds']}, Profit: ${result['total_profit']:.2f}, ROI: {result['roi']:.1f}%")
    
    # Best overall
    best_overall = max(results, key=lambda x: x['roi'])
    logger.info(f"\n🏆 OVERALL BEST PERFORMANCE:")
    logger.info(f"  Std threshold: {best_overall['std_threshold']}")
    logger.info(f"  Base max odds: {best_overall['base_max_odds']}")
    logger.info(f"  ROI: {best_overall['roi']:.1f}%")
    logger.info(f"  Eligible races: {best_overall['eligible_races']}")
    logger.info(f"  Total bets: {best_overall['total_bets']}")
    logger.info(f"  Total profit: ${best_overall['total_profit']:.2f}")
    
    return results


def demonstrate_variable_max_odds():
    """Demonstrate the variable max odds calculation"""
    print("🎯 VARIABLE MAX ODDS DEMONSTRATION")
    print("=" * 50)
    print("Formula: MaxOddsAllowed = 30 × (FieldSize/12)")
    print()
    
    field_sizes = [6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
    base_max_odds = 30
    
    for field_size in field_sizes:
        variable_max_odds = base_max_odds * (field_size / 12.0)
        print(f"Field size {field_size:2d}: Max odds = {variable_max_odds:5.1f}:1")
    
    print()
    print("Key insights:")
    print("• Small fields (6-8 horses): Tighter odds cutoff (15-20:1)")
    print("• Medium fields (10-14 horses): Moderate cutoff (25-35:1)")  
    print("• Large fields (16+ horses): Relaxed cutoff (40+:1)")
    print("• This prevents betting on hopeless longshots in small fields")
    print("• While allowing reasonable longshots in large fields")


def main():
    """Main function"""
    # First demonstrate the concept
    demonstrate_variable_max_odds()
    print("\n" + "="*80 + "\n")
    
    # Then run the comprehensive analysis
    results = comprehensive_analysis()
    return results


if __name__ == "__main__":
    main()
