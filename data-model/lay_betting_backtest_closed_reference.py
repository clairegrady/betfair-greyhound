"""
Lay Betting Backtest Script - Uses closing reference odds for realistic simulation
"""
import pandas as pd
import numpy as np
from shared_lay_betting import LayBettingStrategy, LayBettingResults
from collections import defaultdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingBacktest:
    """
    Lay betting backtest using shared strategy logic
    """
    
    def __init__(self, csv_file: str, std_threshold: float = 1.5, max_odds: float = 25.0):
        self.csv_file = csv_file
        self.strategy = LayBettingStrategy(std_threshold, max_odds)
        self.results = LayBettingResults()
        self.df = None
        self.race_stats = defaultdict(list)
    
    def load_data(self):
        """Load racing data from CSV"""
        logger.info("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_file)
        
        # Filter out invalid odds (null, negative, or zero) but keep all horses
        original_count = len(self.df)
        self.df = self.df[
            (self.df['FixedWinClose_Reference'].notna()) & 
            (self.df['FixedWinClose_Reference'] > 0) &
            (self.df['FixedWinClose_Reference'] < 1000)  # Reasonable upper limit
        ].copy()
        final_count = len(self.df)
        invalid_odds_count = original_count - final_count
        
        logger.info(f"✅ Loaded {original_count} race entries")
        logger.info(f"🗑️ Filtered out {invalid_odds_count} entries with invalid odds")
        logger.info(f"📊 Using {final_count} valid entries for backtest")
        logger.info(f"ℹ️ Scratched horses will be filtered during race analysis")
    
    def get_race_groups(self):
        """Group data by race (meeting + date + race number)"""
        return self.df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    
    def run_backtest(self, stake_per_bet: float = 1, verbose: bool = True):
        """
        Run the backtest using shared strategy logic
        
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
            logger.info(f"📋 Strategy: {self.strategy.get_strategy_description()}")
        
        for (meeting, date, race_num), race_data in race_groups:
            # Use shared strategy to analyze race eligibility
            is_eligible, reason, eligible_horses = self.strategy.analyze_race_eligibility(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                if verbose:
                    logger.debug(f"❌ {meeting} {date} R{race_num}: {reason}")
                continue
            
            # Place lay bets on eligible horses (excluding scratched horses)
            for _, horse in eligible_horses.iterrows():
                # Skip scratched horses (negative finishing positions)
                if horse['finishingPosition'] <= 0:
                    continue
                    
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                
                # Calculate profit using shared strategy
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
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    results = []
    
    logger.info("🔬 Testing different std thresholds...")
    
    for std_threshold in std_thresholds:
        backtest = LayBettingBacktest(csv_file, std_threshold, 20.0)
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
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    max_odds = [20, 25, 30]
    results = []
    
    logger.info("🔬 COMPREHENSIVE LAY BETTING ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Testing {len(std_thresholds)} std thresholds × {len(max_odds)} max odds = {len(std_thresholds) * len(max_odds)} combinations")
    logger.info("=" * 80)
    
    for max_odd in max_odds:
        logger.info(f"\n🎯 TESTING MAX ODDS: {max_odd}:1")
        logger.info("=" * 50)
        
        for std_threshold in std_thresholds:
            logger.info(f"📊 Std: {std_threshold}, Max Odds: {max_odd}")
            
            backtest = LayBettingBacktest(csv_file, std_threshold, max_odd)
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
    csv_filename = "comprehensive_lay_analysis_results_closed_reference.csv"
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
