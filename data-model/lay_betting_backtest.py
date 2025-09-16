#!/usr/bin/env python3
"""
Lay Betting Backtest Script

Strategy:
1. Only consider races with 8+ horses
2. Only lay horses in positions 5-8 (bottom half)
3. Only lay horses with odds <= max_odds (configurable)
4. Skip races where top 4 horses have similar odds (low variance)
5. Track all bets and calculate profit/loss
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
from collections import defaultdict
import statistics

class LayBettingBacktest:
    def __init__(self, csv_file, std_threshold=2.0, max_odds=30.0):
        self.csv_file = csv_file
        self.std_threshold = std_threshold
        self.max_odds = max_odds
        self.bets = []
        self.race_stats = defaultdict(list)
        self.total_stake = 0
        self.total_profit = 0
        
    def load_data(self):
        """Load and prepare the racing data"""
        print("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_file)
        
        # Convert odds to numeric, handle any non-numeric values
        self.df['FixedWinOpen_Reference'] = pd.to_numeric(self.df['FixedWinOpen_Reference'], errors='coerce')
        self.df['FixedWinClose_Reference'] = pd.to_numeric(self.df['FixedWinClose_Reference'], errors='coerce')
        
        # Remove rows with missing odds
        self.df = self.df.dropna(subset=['FixedWinOpen_Reference', 'FixedWinClose_Reference'])
        
        print(f"✅ Loaded {len(self.df)} race entries")
        return self.df
    
    def get_race_groups(self):
        """Group data by race (meeting + date + race number)"""
        race_groups = self.df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
        return race_groups
    
    def analyze_race_eligibility(self, race_data):
        """Check if race meets our criteria"""
        race_data = race_data.sort_values('FixedWinOpen_Reference')
        total_horses = len(race_data)
        
        # Check 1: Must have at least 4 horses (minimum for meaningful analysis)
        if total_horses < 4:
            return False, "Less than 4 horses"
        
        # Check 2: Get top half horses (lowest odds)
        top_half_count = total_horses // 2
        top_half = race_data.head(top_half_count)
        
        # Check 3: Calculate odds variance in top half
        top_half_odds = top_half['FixedWinOpen_Reference'].values
        odds_std = np.std(top_half_odds)
        
        # If standard deviation is less than threshold, odds are too similar
        if odds_std < self.std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f})"
        
        # Check 4: Get bottom half horses (highest odds)
        bottom_half = race_data.iloc[top_half_count:]  # Bottom half (0-indexed)
        
        # Check 5: Filter bottom half horses with odds <= max_odds
        eligible_horses = bottom_half[bottom_half['FixedWinOpen_Reference'] <= self.max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {self.max_odds}:1"
        
        return True, eligible_horses
    
    def calculate_lay_bet_profit(self, horse_odds, horse_finished_position, stake=10):
        """
        Calculate lay bet profit/loss
        
        Lay bet: We bet AGAINST the horse winning
        - If horse loses (position > 1): We win the stake
        - If horse wins (position = 1): We lose (odds - 1) * stake
        """
        if horse_finished_position == 1:  # Horse won
            # We lose: (odds - 1) * stake
            loss = (horse_odds - 1) * stake
            return -loss
        else:  # Horse lost
            # We win: stake
            return stake
    
    def run_backtest(self, stake_per_bet=10):
        """Run the complete backtest"""
        print(f"🏇 Starting Lay Betting Backtest (std threshold: {self.std_threshold}, max odds: {self.max_odds})...")
        print("=" * 60)
        
        race_groups = self.get_race_groups()
        total_races = len(race_groups)
        eligible_races = 0
        total_bets = 0
        
        print(f"📈 Analyzing {total_races} races...")
        
        for (meeting, date, race_num), race_data in race_groups:
            is_eligible, result = self.analyze_race_eligibility(race_data)
            
            if is_eligible:
                eligible_races += 1
                eligible_horses = result
                
                print(f"\n✅ ELIGIBLE RACE: {meeting} - Race {race_num} ({date})")
                print(f"   Horses to lay: {len(eligible_horses)}")
                
                # Place lay bets on eligible horses
                for _, horse in eligible_horses.iterrows():
                    horse_odds = horse['FixedWinOpen_Reference']
                    horse_name = horse['runnerName']
                    finishing_pos = horse['finishingPosition']
                    
                    # Calculate profit/loss for this bet
                    profit = self.calculate_lay_bet_profit(horse_odds, finishing_pos, stake_per_bet)
                    
                    # Record the bet
                    bet_record = {
                        'meeting': meeting,
                        'date': date,
                        'race_number': race_num,
                        'horse_name': horse_name,
                        'odds': horse_odds,
                        'finishing_position': finishing_pos,
                        'stake': stake_per_bet,
                        'profit': profit,
                        'won': finishing_pos != 1  # True if horse didn't win
                    }
                    
                    self.bets.append(bet_record)
                    total_bets += 1
                    
                    # Update totals
                    self.total_stake += stake_per_bet
                    self.total_profit += profit
                    
                    # Print bet details
                    result_emoji = "✅" if finishing_pos != 1 else "❌"
                    print(f"   {result_emoji} Lay {horse_name} @ {horse_odds:.1f} - Finished {finishing_pos} - Profit: ${profit:.2f}")
            else:
                reason = result
                print(f"❌ SKIPPED: {meeting} Race {race_num} - {reason}")
        
        print(f"\n📊 BACKTEST COMPLETE")
        print("=" * 60)
        print(f"Total races analyzed: {total_races}")
        print(f"Eligible races: {eligible_races}")
        print(f"Total bets placed: {total_bets}")
        print(f"Total stake: ${self.total_stake:.2f}")
        print(f"Total profit/loss: ${self.total_profit:.2f}")
        
        if self.total_stake > 0:
            roi = (self.total_profit / self.total_stake) * 100
            print(f"ROI: {roi:.2f}%")
        
        return self.bets
    
    def analyze_results(self):
        """Detailed analysis of betting results"""
        if not self.bets:
            print("No bets to analyze")
            return
        
        bets_df = pd.DataFrame(self.bets)
        
        print(f"\n📈 DETAILED ANALYSIS")
        print("=" * 60)
        
        # Win rate
        winning_bets = bets_df[bets_df['won'] == True]
        win_rate = len(winning_bets) / len(bets_df) * 100
        print(f"Win Rate: {win_rate:.1f}% ({len(winning_bets)}/{len(bets_df)})")
        
        # Profit by odds range
        print(f"\n💰 PROFIT BY ODDS RANGE:")
        odds_ranges = [(5, 10), (10, 15), (15, 20)]
        for min_odds, max_odds in odds_ranges:
            range_bets = bets_df[(bets_df['odds'] >= min_odds) & (bets_df['odds'] < max_odds)]
            if len(range_bets) > 0:
                range_profit = range_bets['profit'].sum()
                range_stake = range_bets['stake'].sum()
                range_roi = (range_profit / range_stake) * 100 if range_stake > 0 else 0
                print(f"  {min_odds}-{max_odds}: ${range_profit:.2f} profit (ROI: {range_roi:.1f}%) - {len(range_bets)} bets")
        
        # Monthly performance
        print(f"\n📅 MONTHLY PERFORMANCE:")
        bets_df['date'] = pd.to_datetime(bets_df['date'])
        monthly = bets_df.groupby(bets_df['date'].dt.to_period('M')).agg({
            'profit': 'sum',
            'stake': 'sum',
            'won': 'sum',
            'horse_name': 'count'
        }).round(2)
        monthly['roi'] = (monthly['profit'] / monthly['stake'] * 100).round(1)
        monthly.columns = ['Profit', 'Stake', 'Wins', 'Bets', 'ROI%']
        print(monthly)
        
        # Worst losing bets (horses that won when we laid them)
        losing_bets = bets_df[bets_df['won'] == False].sort_values('profit')
        if len(losing_bets) > 0:
            print(f"\n💸 BIGGEST LOSSES (Horses that won):")
            for _, bet in losing_bets.head(5).iterrows():
                print(f"  {bet['horse_name']} @ {bet['odds']:.1f} - Lost ${abs(bet['profit']):.2f}")
    
    def save_results(self, filename="lay_betting_results_2.csv"):
        """Save detailed results to CSV"""
        if self.bets:
            bets_df = pd.DataFrame(self.bets)
            bets_df.to_csv(filename, index=False)
            print(f"\n💾 Results saved to {filename}")

    def run_backtest_silent(self, stake_per_bet=10):
        """Run the complete backtest without printing details"""
        race_groups = self.get_race_groups()
        total_races = len(race_groups)
        eligible_races = 0
        total_bets = 0
        
        for (meeting, date, race_num), race_data in race_groups:
            is_eligible, result = self.analyze_race_eligibility(race_data)
            
            if is_eligible:
                eligible_races += 1
                
                for _, horse in result.iterrows():
                    horse_name = horse['runnerName']
                    odds = horse['FixedWinOpen_Reference']
                    finishing_position = horse['finishingPosition']
                    
                    profit = self.calculate_lay_bet_profit(odds, finishing_position, stake_per_bet)
                    self.total_stake += stake_per_bet
                    self.total_profit += profit
                    total_bets += 1
                    
                    won_bet = profit > 0
                    
                    self.bets.append({
                        'meeting': meeting,
                        'date': date,
                        'race_number': race_num,
                        'horse_name': horse_name,
                        'odds': odds,
                        'finishing_position': finishing_position,
                        'stake': stake_per_bet,
                        'profit': profit,
                        'won': won_bet
                    })

def test_std_thresholds():
    """Test different standard deviation thresholds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/scripts/Runner_Result_2025-09-07.csv"
    
    # Test different std thresholds
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    results = []
    
    print("🔬 TESTING DIFFERENT STANDARD DEVIATION THRESHOLDS")
    print("=" * 70)
    
    for std_threshold in std_thresholds:
        print(f"\n📊 Testing std threshold: {std_threshold}")
        print("-" * 50)
        
        # Initialize backtest with specific threshold
        backtest = LayBettingBacktest(csv_file, std_threshold)
        
        # Load data
        backtest.load_data()
        
        # Run backtest
        backtest.run_backtest(stake_per_bet=1)
        
        # Count total races in dataset
        race_groups = backtest.get_race_groups()
        total_races = len(race_groups)
        
        # Collect results
        result = {
            'std_threshold': std_threshold,
            'total_races': total_races,
            'eligible_races': len([bet for bet in backtest.bets if bet['meeting'] == backtest.bets[0]['meeting']]) if backtest.bets else 0,
            'total_bets': len(backtest.bets),
            'total_stake': backtest.total_stake,
            'total_profit': backtest.total_profit,
            'roi': (backtest.total_profit / backtest.total_stake * 100) if backtest.total_stake > 0 else 0,
            'win_rate': (len([bet for bet in backtest.bets if bet['won']]) / len(backtest.bets) * 100) if backtest.bets else 0
        }
        
        # Count eligible races properly
        race_groups = backtest.get_race_groups()
        eligible_count = 0
        for (meeting, date, race_num), race_data in race_groups:
            is_eligible, _ = backtest.analyze_race_eligibility(race_data)
            if is_eligible:
                eligible_count += 1
        
        result['eligible_races'] = eligible_count
        results.append(result)
        
        print(f"  Eligible races: {eligible_count}")
        print(f"  Total bets: {result['total_bets']}")
        print(f"  ROI: {result['roi']:.1f}%")
        print(f"  Win rate: {result['win_rate']:.1f}%")
    
    # Summary table
    print(f"\n📈 SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Std':<6} {'Eligible':<8} {'Bets':<6} {'ROI':<8} {'Win%':<6} {'Profit':<8}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['std_threshold']:<6} {result['eligible_races']:<8} {result['total_bets']:<6} {result['roi']:<7.1f}% {result['win_rate']:<5.1f}% ${result['total_profit']:<7.2f}")
    
    return results

def comprehensive_analysis():
    """Test all combinations of std thresholds and max odds"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/scripts/Runner_Result_2025-09-07.csv"
    
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    max_odds = [20, 25, 30]
    results = []
    
    print("🔬 COMPREHENSIVE LAY BETTING ANALYSIS")
    print("=" * 80)
    print(f"Testing {len(std_thresholds)} std thresholds × {len(max_odds)} max odds = {len(std_thresholds) * len(max_odds)} combinations")
    print("=" * 80)
    
    for max_odd in max_odds:
        print(f"\n🎯 TESTING MAX ODDS: {max_odd}:1")
        print("=" * 50)
        
        for std_threshold in std_thresholds:
            print(f"📊 Std: {std_threshold}, Max Odds: {max_odd}")
            
            # Initialize backtest with specific threshold and max odds
            backtest = LayBettingBacktest(csv_file, std_threshold, max_odd)
            
            # Load data
            backtest.load_data()
            
            # Run backtest (silent mode)
            backtest.run_backtest_silent(stake_per_bet=1)
            
            # Count eligible races properly
            race_groups = backtest.get_race_groups()
            eligible_count = 0
            for (meeting, date, race_num), race_data in race_groups:
                is_eligible, _ = backtest.analyze_race_eligibility(race_data)
                if is_eligible:
                    eligible_count += 1
            
            # Count total races in dataset
            total_races = len(race_groups)
            
            # Collect results
            result = {
                'std_threshold': std_threshold,
                'max_odds': max_odd,
                'total_races': total_races,
                'eligible_races': eligible_count,
                'total_bets': len(backtest.bets),
                'total_stake': backtest.total_stake,
                'total_profit': backtest.total_profit,
                'roi': (backtest.total_profit / backtest.total_stake * 100) if backtest.total_stake > 0 else 0,
                'win_rate': (len([bet for bet in backtest.bets if bet['won']]) / len(backtest.bets) * 100) if backtest.bets else 0,
                'avg_profit_per_bet': backtest.total_profit / len(backtest.bets) if backtest.bets else 0,
                'risk_score': (100 - backtest.total_profit / backtest.total_stake * 100) if backtest.total_stake > 0 else 100
            }
            
            results.append(result)
            
            print(f"  ✅ Eligible: {eligible_count}, Bets: {result['total_bets']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    # Save results to CSV
    import pandas as pd
    df = pd.DataFrame(results)
    csv_filename = "comprehensive_lay_analysis_results3.csv"
    df.to_csv(csv_filename, index=False)
    
    print(f"\n💾 Results saved to {csv_filename}")
    
    # Summary table
    print(f"\n📈 SUMMARY TABLE")
    print("=" * 100)
    print(f"{'Std':<4} {'Max':<4} {'Eligible':<8} {'Bets':<5} {'ROI':<7} {'Win%':<6} {'Profit':<8} {'Risk':<6}")
    print("-" * 100)
    
    for result in results:
        print(f"{result['std_threshold']:<4} {result['max_odds']:<4} {result['eligible_races']:<8} {result['total_bets']:<5} {result['roi']:<6.1f}% {result['win_rate']:<5.1f}% ${result['total_profit']:<7.2f} {result['risk_score']:<5.1f}%")
    
    # Find best combinations
    print(f"\n🏆 TOP 5 PERFORMERS BY ROI:")
    top_roi = sorted(results, key=lambda x: x['roi'], reverse=True)[:5]
    for i, result in enumerate(top_roi, 1):
        print(f"{i}. Std: {result['std_threshold']}, Max Odds: {result['max_odds']}, ROI: {result['roi']:.1f}%, Profit: ${result['total_profit']:.2f}")
    
    print(f"\n💰 TOP 5 PERFORMERS BY TOTAL PROFIT:")
    top_profit = sorted(results, key=lambda x: x['total_profit'], reverse=True)[:5]
    for i, result in enumerate(top_profit, 1):
        print(f"{i}. Std: {result['std_threshold']}, Max Odds: {result['max_odds']}, Profit: ${result['total_profit']:.2f}, ROI: {result['roi']:.1f}%")
    
    print(f"\n⚖️ TOP 5 LOWEST RISK (Best Risk/Reward):")
    top_low_risk = sorted(results, key=lambda x: x['risk_score'])[:5]
    for i, result in enumerate(top_low_risk, 1):
        print(f"{i}. Std: {result['std_threshold']}, Max Odds: {result['max_odds']}, Risk: {result['risk_score']:.1f}%, ROI: {result['roi']:.1f}%")
    
    return results

def main():
    # Run comprehensive analysis
    results = comprehensive_analysis()
    
    # Find best overall performer
    best_result = max(results, key=lambda x: x['roi'])
    print(f"\n🏆 OVERALL BEST PERFORMANCE:")
    print(f"  Std threshold: {best_result['std_threshold']}")
    print(f"  Max odds: {best_result['max_odds']}")
    print(f"  ROI: {best_result['roi']:.1f}%")
    print(f"  Eligible races: {best_result['eligible_races']}")
    print(f"  Total bets: {best_result['total_bets']}")
    print(f"  Total profit: ${best_result['total_profit']:.2f}")

if __name__ == "__main__":
    main()
