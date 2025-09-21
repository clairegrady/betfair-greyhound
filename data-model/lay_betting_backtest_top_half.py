"""
Lay Betting Backtest Script - TOP HALF VERSION
Lays $1 on the top half horses (lowest odds) instead of bottom half
"""
import pandas as pd
import numpy as np
from shared_lay_betting import LayBettingResults
from collections import defaultdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingTopHalfStrategy:
    """
    Lay betting strategy that bets on the TOP HALF (lowest odds) horses
    """
    
    def __init__(self, std_threshold: float = 1.5, max_odds: float = 25.0):
        self.std_threshold = std_threshold
        self.max_odds = max_odds
    
    def analyze_race_eligibility(self, race_data: pd.DataFrame, odds_column: str = 'FixedWinClose_Reference') -> tuple:
        """
        Check if a race meets our lay betting criteria for TOP HALF horses
        
        Args:
            race_data: DataFrame with race odds data
            odds_column: Column name containing the odds
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses)
        """
        # Filter out horses without odds for analysis
        horses_with_odds = race_data.dropna(subset=[odds_column])
        
        # Check 1: Must have at least 4 horses total
        if len(race_data) < 4:
            return False, f"Less than 4 horses (total: {len(race_data)})", None
        
        # Check 2: Must have at least 4 horses with odds
        if len(horses_with_odds) < 4:
            return False, f"Less than 4 horses with odds (total: {len(race_data)}, with odds: {len(horses_with_odds)})", None
        
        # Sort by odds (lowest first)
        horses_with_odds = horses_with_odds.sort_values(odds_column)
        
        # Check 3: Get top half horses (lowest odds) - these are the ones we'll bet on
        total_horses = len(horses_with_odds)
        top_half_count = total_horses // 2
        
        # For odd numbers, bet on the greater half (e.g., 7 horses = bet on top 4)
        if total_horses % 2 == 1:
            top_half_count += 1
            
        top_half = horses_with_odds.head(top_half_count)
        
        # Check 4: Calculate odds variance in top half
        top_half_odds = top_half[odds_column].values
        odds_std = np.std(top_half_odds)
        
        # If standard deviation is less than threshold, odds are too similar
        if odds_std < self.std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f})", None
        
        # Check 5: Filter top half horses with odds <= max_odds
        eligible_horses = top_half[top_half[odds_column] <= self.max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in top half with odds <= {self.max_odds}:1", None
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay", eligible_horses
    
    def calculate_lay_bet_profit(self, horse_odds: float, finishing_pos: int, stake: float) -> float:
        """
        Calculate profit from a lay bet
        
        Args:
            horse_odds: The odds we laid at
            finishing_pos: Where the horse finished (1 = won, 2+ = lost)
            stake: Amount we staked
            
        Returns:
            float: Profit (positive if we won the bet, negative if we lost)
        """
        if finishing_pos == 1:  # Horse won - we lose the bet
            # We lose: stake * (odds - 1)
            return -stake * (horse_odds - 1)
        else:  # Horse lost - we win the bet
            # We win: stake
            return stake
    
    def get_strategy_description(self) -> str:
        """Get a description of the strategy"""
        return f"Top Half Lay Strategy: Std threshold {self.std_threshold}, Max odds {self.max_odds}:1"


class LayBettingTopHalfBacktest:
    """
    Lay betting backtest using TOP HALF strategy
    """
    
    def __init__(self, csv_file: str, std_threshold: float = 1.5, max_odds: float = 25.0):
        self.csv_file = csv_file
        self.strategy = LayBettingTopHalfStrategy(std_threshold, max_odds)
        self.results = LayBettingResults()
        self.df = None
        self.race_stats = defaultdict(list)
    
    def load_data(self):
        """Load racing data from CSV"""
        logger.info("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_file)
        logger.info(f"✅ Loaded {len(self.df)} race entries")
    
    def get_race_groups(self):
        """Group data by race (meeting + date + race number)"""
        return self.df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    
    def run_backtest(self, stake_per_bet: float = 1, verbose: bool = True):
        """
        Run the backtest using TOP HALF strategy
        
        Args:
            stake_per_bet: Amount to stake per bet
            verbose: Whether to print detailed output
        """
        if self.df is None:
            self.load_data()
        
        race_groups = self.get_race_groups()
        total_races = len(race_groups)
        
        if verbose:
            logger.info(f"🏁 Starting TOP HALF backtest on {total_races} races")
            logger.info(f"📋 Strategy: {self.strategy.get_strategy_description()}")
        
        for (meeting, date, race_num), race_data in race_groups:
            # Use strategy to analyze race eligibility
            is_eligible, reason, eligible_horses = self.strategy.analyze_race_eligibility(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                if verbose:
                    logger.debug(f"❌ {meeting} {date} R{race_num}: {reason}")
                continue
            
            # Place lay bets on eligible horses (TOP HALF)
            for _, horse in eligible_horses.iterrows():
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                
                # Calculate profit using strategy
                profit = self.strategy.calculate_lay_bet_profit(
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
                    'won': won_bet
                }
                
                self.results.add_bet(bet_data)
                
                if verbose:
                    logger.debug(f"  🐎 {horse.get('clothNumber', 0)}. {horse.get('runnerName', 'Unknown')} - Lay @ {horse_odds:.2f} → {finishing_pos} → ${profit:.2f}")
        
        if verbose:
            stats = self.results.get_statistics()
            logger.info(f"✅ Backtest complete: {stats['total_bets']} bets, ROI: {stats['roi']:.1f}%, Profit: ${stats['total_profit']:.2f}")


def test_std_thresholds():
    """Test different standard deviation thresholds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    results = []
    
    logger.info("🔬 Testing different std thresholds for TOP HALF strategy...")
    
    for std_threshold in std_thresholds:
        backtest = LayBettingTopHalfBacktest(csv_file, std_threshold, 20.0)
        backtest.run_backtest(stake_per_bet=1, verbose=False)
        
        # Count eligible races
        race_groups = backtest.get_race_groups()
        eligible_count = 0
        for (meeting, date, race_num), race_data in race_groups:
            is_eligible, _, _ = backtest.strategy.analyze_race_eligibility(race_data, 'FixedWinClose_Reference')
            if is_eligible:
                eligible_count += 1
        
        stats = backtest.results.get_statistics()
        stats.update({
            'std_threshold': std_threshold,
            'max_odds': 20.0,
            'total_races': len(race_groups),
            'eligible_races': eligible_count
        })
        results.append(stats)
        
        logger.info(f"  📊 Std: {std_threshold}, Eligible: {eligible_count}, ROI: {stats['roi']:.1f}%")
    
    return results


def comprehensive_analysis():
    """Test all combinations of std thresholds and max odds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    max_odds = [20, 25, 30]
    results = []
    
    logger.info("🔬 COMPREHENSIVE TOP HALF LAY BETTING ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Testing {len(std_thresholds)} std thresholds × {len(max_odds)} max odds = {len(std_thresholds) * len(max_odds)} combinations")
    logger.info("=" * 80)
    
    for max_odd in max_odds:
        logger.info(f"\n🎯 TESTING MAX ODDS: {max_odd}:1")
        logger.info("=" * 50)
        
        for std_threshold in std_thresholds:
            logger.info(f"📊 Std: {std_threshold}, Max Odds: {max_odd}")
            
            backtest = LayBettingTopHalfBacktest(csv_file, std_threshold, max_odd)
            backtest.run_backtest(stake_per_bet=1, verbose=False)
            
            # Count eligible races
            race_groups = backtest.get_race_groups()
            eligible_count = 0
            for (meeting, date, race_num), race_data in race_groups:
                is_eligible, _, _ = backtest.strategy.analyze_race_eligibility(race_data, 'FixedWinClose_Reference')
                if is_eligible:
                    eligible_count += 1
            
            stats = backtest.results.get_statistics()
            result = {
                'std_threshold': std_threshold,
                'max_odds': max_odd,
                'total_races': len(race_groups),
                'eligible_races': eligible_count,
                **stats
            }
            results.append(result)
            
            logger.info(f"  ✅ Eligible: {eligible_count}, Bets: {result['total_bets']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    # Save results to CSV
    df = pd.DataFrame(results)
    csv_filename = "comprehensive_lay_analysis_results_top_half.csv"
    df.to_csv(csv_filename, index=False)
    
    logger.info(f"\n💾 Results saved to {csv_filename}")
    
    # Summary table
    logger.info(f"\n📈 SUMMARY TABLE")
    logger.info("=" * 100)
    logger.info(f"{'Std':<4} {'Max':<4} {'Eligible':<8} {'Bets':<6} {'ROI':<6} {'Win%':<6} {'Profit':<10} {'Risk':<6}")
    logger.info("-" * 100)
    
    for result in results:
        logger.info(f"{result['std_threshold']:<4} {result['max_odds']:<4} {result['eligible_races']:<8} {result['total_bets']:<6} {result['roi']:<6.1f}% {result['win_rate']:<6.1f}% ${result['total_profit']:<9.2f} {result['risk_score']:<6.1f}%")
    
    # Top performers
    logger.info(f"\n🏆 TOP 5 PERFORMERS BY ROI:")
    top_roi = sorted(results, key=lambda x: x['roi'], reverse=True)[:5]
    for i, result in enumerate(top_roi, 1):
        logger.info(f"{i}. Std: {result['std_threshold']}, Max Odds: {result['max_odds']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    logger.info(f"\n💰 TOP 5 PERFORMERS BY TOTAL PROFIT:")
    top_profit = sorted(results, key=lambda x: x['total_profit'], reverse=True)[:5]
    for i, result in enumerate(top_profit, 1):
        logger.info(f"{i}. Std: {result['std_threshold']}, Max Odds: {result['max_odds']}, Profit: ${result['total_profit']:.2f}, ROI: {result['roi']:.1f}%")
    
    # Best overall
    best_overall = max(results, key=lambda x: x['roi'])
    logger.info(f"\n🏆 OVERALL BEST PERFORMANCE:")
    logger.info(f"  Std threshold: {best_overall['std_threshold']}")
    logger.info(f"  Max odds: {best_overall['max_odds']}")
    logger.info(f"  ROI: {best_overall['roi']:.1f}%")
    logger.info(f"  Eligible races: {best_overall['eligible_races']}")
    logger.info(f"  Total bets: {best_overall['total_bets']}")
    logger.info(f"  Total profit: ${best_overall['total_profit']:.2f}")
    
    return results


def main():
    """Main function"""
    results = comprehensive_analysis()
    return results


if __name__ == "__main__":
    main()
