#!/usr/bin/env python3
"""
Analyze why races are not eligible for lay betting strategy
"""

import pandas as pd
import numpy as np
from collections import defaultdict

def analyze_race_eligibility():
    """Analyze all races and categorize exclusion reasons"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/scripts/Runner_Result_2025-09-07.csv"
    
    print("📊 Loading racing data...")
    df = pd.read_csv(csv_file)
    
    # Ensure odds are numeric
    df['FixedWinOpen_Reference'] = pd.to_numeric(df['FixedWinOpen_Reference'], errors='coerce')
    df.dropna(subset=['FixedWinOpen_Reference'], inplace=True)
    
    print(f"✅ Loaded {len(df)} race entries")
    
    # Group by race
    race_groups = df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    total_races = len(race_groups)
    
    print(f"📈 Analyzing {total_races} races...")
    
    # Track exclusion reasons
    exclusion_reasons = defaultdict(int)
    horse_count_distribution = defaultdict(int)
    std_dev_distribution = defaultdict(int)
    
    # Test different std thresholds
    std_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    max_odds = [20, 25, 30]
    
    for std_threshold in std_thresholds:
        for max_odds_val in max_odds:
            print(f"\n🔍 Analyzing with Std: {std_threshold}, Max Odds: {max_odds_val}")
            
            eligible_count = 0
            exclusion_reasons_current = defaultdict(int)
            
            for (meeting, date, race_num), race_data in race_groups:
                race_data = race_data.sort_values('FixedWinOpen_Reference')
                
                # Check 1: Must have 8+ horses
                if len(race_data) < 8:
                    exclusion_reasons_current["Less than 8 horses"] += 1
                    horse_count_distribution[len(race_data)] += 1
                    continue
                
                # Check 2: Get top 4 horses (lowest odds)
                top_4 = race_data.head(4)
                
                # Check 3: Calculate odds variance in top 4
                top_4_odds = top_4['FixedWinOpen_Reference'].values
                odds_variance = np.var(top_4_odds)
                odds_std = np.std(top_4_odds)
                
                # If standard deviation is less than threshold, odds are too similar
                if odds_std < std_threshold:
                    exclusion_reasons_current[f"Top 4 odds too similar (std < {std_threshold})"] += 1
                    std_dev_distribution[f"std < {std_threshold}"] += 1
                    continue
                
                # Check 4: Get bottom half horses (positions 5-8)
                bottom_half = race_data.iloc[4:8]  # Positions 5-8 (0-indexed)
                
                # Check 5: Filter bottom half horses with odds <= max_odds
                eligible_horses = bottom_half[bottom_half['FixedWinOpen_Reference'] <= max_odds_val]
                
                if len(eligible_horses) == 0:
                    exclusion_reasons_current[f"No horses in bottom half with odds <= {max_odds_val}"] += 1
                    continue
                
                # If we get here, race is eligible
                eligible_count += 1
            
            print(f"  ✅ Eligible races: {eligible_count} ({eligible_count/total_races*100:.1f}%)")
            print(f"  ❌ Excluded races: {total_races - eligible_count} ({(total_races - eligible_count)/total_races*100:.1f}%)")
            
            # Show top exclusion reasons
            print(f"  📊 Top exclusion reasons:")
            sorted_reasons = sorted(exclusion_reasons_current.items(), key=lambda x: x[1], reverse=True)
            for reason, count in sorted_reasons[:5]:
                percentage = count / total_races * 100
                print(f"    - {reason}: {count} races ({percentage:.1f}%)")
    
    # Overall analysis
    print(f"\n📈 OVERALL ANALYSIS")
    print("=" * 60)
    
    # Analyze horse count distribution
    print(f"\n🐎 HORSE COUNT DISTRIBUTION:")
    sorted_horse_counts = sorted(horse_count_distribution.items())
    for horse_count, race_count in sorted_horse_counts:
        percentage = race_count / total_races * 100
        print(f"  {horse_count} horses: {race_count} races ({percentage:.1f}%)")
    
    # Analyze std dev distribution
    print(f"\n📊 STANDARD DEVIATION DISTRIBUTION:")
    for std_range, race_count in std_dev_distribution.items():
        percentage = race_count / total_races * 100
        print(f"  {std_range}: {race_count} races ({percentage:.1f}%)")
    
    # Sample some races to understand the data better
    print(f"\n🔍 SAMPLE RACE ANALYSIS:")
    sample_count = 0
    for (meeting, date, race_num), race_data in race_groups:
        if sample_count >= 5:
            break
        
        race_data = race_data.sort_values('FixedWinOpen_Reference')
        print(f"\n  Race: {meeting} - Race {race_num} ({date})")
        print(f"    Horses: {len(race_data)}")
        
        if len(race_data) >= 4:
            top_4 = race_data.head(4)
            top_4_odds = top_4['FixedWinOpen_Reference'].values
            odds_std = np.std(top_4_odds)
            print(f"    Top 4 odds: {top_4_odds}")
            print(f"    Std deviation: {odds_std:.2f}")
        
        if len(race_data) >= 8:
            bottom_half = race_data.iloc[4:8]
            bottom_odds = bottom_half['FixedWinOpen_Reference'].values
            print(f"    Bottom half odds: {bottom_odds}")
        
        sample_count += 1

if __name__ == "__main__":
    analyze_race_eligibility()
