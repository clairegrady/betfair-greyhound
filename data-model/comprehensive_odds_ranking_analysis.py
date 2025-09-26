#!/usr/bin/env python3
"""
Comprehensive Odds Ranking Analysis

This script analyzes horse performance based on their odds ranking within each race.
It shows performance statistics for favorites, 2nd favorites, 3rd favorites, etc.

Features:
- Ranks all horses by closing odds within each race
- Tracks position distribution for each ranking
- Calculates odds statistics for each ranking
- Exports comprehensive results to CSV
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_odds_ranking_performance(csv_file_path):
    """
    Analyze horse performance by odds ranking within each race.
    
    Args:
        csv_file_path (str): Path to the CSV file containing race data
    
    Returns:
        dict: Analysis results with performance statistics by ranking
    """
    
    logger.info(f"📊 Loading data from: {csv_file_path}")
    
    try:
        # Load the CSV file
        df = pd.read_csv(csv_file_path)
        logger.info(f"✅ Loaded {len(df):,} records")
        
        # Filter out scratched horses (negative finishing positions)
        original_count = len(df)
        df_clean = df[df['finishingPosition'] >= 0].copy()
        scratched_count = original_count - len(df_clean)
        
        logger.info(f"🚫 Filtered out {scratched_count:,} scratched horses")
        logger.info(f"📈 Analyzing {len(df_clean):,} valid race entries")
        
        # Group by race (meetingDate, meetingName, raceNumber)
        race_groups = df_clean.groupby(['meetingDate', 'meetingName', 'raceNumber'])
        
        all_rankings = []
        total_races = 0
        
        logger.info("🏇 Analyzing odds ranking performance by race...")
        
        for (meeting_date, meeting_name, race_number), race_data in race_groups:
            total_races += 1
            
            # Skip races with no valid closing odds
            valid_odds = race_data[race_data['FixedWinClose_Reference'] > 0].copy()
            if len(valid_odds) == 0:
                continue
            
            # Sort by closing odds to get ranking
            valid_odds_sorted = valid_odds.sort_values('FixedWinClose_Reference')
            valid_odds_sorted['odds_ranking'] = range(1, len(valid_odds_sorted) + 1)
            
            # Add race info to each horse
            for _, horse in valid_odds_sorted.iterrows():
                all_rankings.append({
                    'meeting_date': meeting_date,
                    'meeting_name': meeting_name,
                    'race_number': race_number,
                    'horse_name': horse['runnerName'],
                    'closing_odds': horse['FixedWinClose_Reference'],
                    'finishing_position': horse['finishingPosition'],
                    'odds_ranking': horse['odds_ranking']
                })
        
        # Convert to DataFrame for analysis
        rankings_df = pd.DataFrame(all_rankings)
        
        if len(rankings_df) == 0:
            logger.warning("⚠️ No valid ranking data found")
            return {}
        
        # Get the maximum ranking to know how many positions to analyze
        max_ranking = rankings_df['odds_ranking'].max()
        logger.info(f"📊 Maximum odds ranking found: {max_ranking}")
        
        # Get total races for proper win rate calculation
        total_races = len(rankings_df.groupby(['meeting_date', 'meeting_name', 'race_number']))
        logger.info(f"📊 Total races: {total_races}")
        
        # Analyze each ranking position
        ranking_results = []
        
        for ranking in range(1, max_ranking + 1):  # Analyze all rankings
            ranking_data = rankings_df[rankings_df['odds_ranking'] == ranking]
            
            if len(ranking_data) == 0:
                continue
            
            # Calculate position distribution
            position_counts = ranking_data['finishing_position'].value_counts().sort_index()
            total_horses = len(ranking_data)
            
            # Calculate win/place rates
            wins = (ranking_data['finishing_position'] == 1).sum()
            places = (ranking_data['finishing_position'].isin([2, 3, 4])).sum()  # Only positions 2, 3, 4 (excluding wins)
            win_rate = round((wins / total_races) * 100, 2)  # Win rate as % of total races
            place_rate = round((places / total_horses) * 100, 2)  # Place rate as % of horses in this ranking
            
            # Calculate odds statistics
            avg_odds = round(ranking_data['closing_odds'].mean(), 2)
            median_odds = round(ranking_data['closing_odds'].median(), 2)
            min_odds = round(ranking_data['closing_odds'].min(), 2)
            max_odds = round(ranking_data['closing_odds'].max(), 2)
            
            # Position distribution percentages
            position_dist = {}
            for pos in [0, 1, 2, 3, 4]:
                count = position_counts.get(pos, 0)
                percentage = round((count / total_horses) * 100, 2)
                position_dist[f'position_{pos}'] = count
                position_dist[f'position_{pos}_pct'] = percentage
            
            ranking_results.append({
                'ranking': ranking,
                'total_horses': total_horses,
                'wins': wins,
                'places': places,  # Only positions 2, 3, 4 (excluding wins)
                'win_rate': win_rate,
                'place_rate': place_rate,
                'avg_odds': avg_odds,
                'median_odds': median_odds,
                'min_odds': min_odds,
                'max_odds': max_odds,
                **position_dist
            })
        
        # Create summary DataFrame
        summary_df = pd.DataFrame(ranking_results)
        
        # Results summary
        results = {
            'total_races_analyzed': total_races,
            'total_horses_analyzed': len(rankings_df),
            'max_ranking': max_ranking,
            'summary_data': summary_df,
            'detailed_data': rankings_df
        }
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error analyzing data: {str(e)}")
        return {}

def print_ranking_analysis(results):
    """Print formatted ranking analysis results."""
    
    if not results or 'summary_data' not in results:
        print("❌ No results to display")
        return
    
    summary_df = results['summary_data']
    
    print("\n" + "="*80)
    print("🏇 COMPREHENSIVE ODDS RANKING ANALYSIS")
    print("="*80)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Total Races Analyzed: {results['total_races_analyzed']:,}")
    print(f"   Total Horses Analyzed: {results['total_horses_analyzed']:,}")
    print(f"   Maximum Ranking: {results['max_ranking']}")
    
    print(f"\n🎯 PERFORMANCE BY RANKING:")
    print(f"{'Rank':<6} {'Horses':<8} {'Wins':<6} {'Places':<7} {'Win%':<7} {'Place%':<8} {'Avg Odds':<9} {'Med Odds':<9} {'Min Odds':<9} {'Max Odds':<9}")
    print("-" * 80)
    
    for _, row in summary_df.iterrows():
        print(f"{row['ranking']:<6} {row['total_horses']:<8} {row['wins']:<6} {row['places']:<7} "
              f"{row['win_rate']:<7.2f} {row['place_rate']:<8.2f} {row['avg_odds']:<9.2f} "
              f"{row['median_odds']:<9.2f} {row['min_odds']:<9.2f} {row['max_odds']:<9.2f}")
    
    print(f"\n🏁 POSITION DISTRIBUTION BY RANKING:")
    print(f"{'Rank':<6} {'Pos 0':<8} {'Pos 1':<8} {'Pos 2':<8} {'Pos 3':<8} {'Pos 4':<8}")
    print("-" * 50)
    
    for _, row in summary_df.iterrows():
        print(f"{row['ranking']:<6} {row['position_0']:<8} {row['position_1']:<8} "
              f"{row['position_2']:<8} {row['position_3']:<8} {row['position_4']:<8}")
    
    print("\n" + "="*80)

def save_comprehensive_results(results, output_file="comprehensive_odds_ranking_analysis.csv"):
    """Save comprehensive results to CSV file."""
    
    if not results or 'summary_data' not in results:
        logger.warning("⚠️ No summary data to save")
        return
    
    try:
        results['summary_data'].to_csv(output_file, index=False)
        logger.info(f"💾 Comprehensive results saved to: {output_file}")
        
        # Also save detailed data
        detailed_file = "detailed_odds_ranking_data.csv"
        results['detailed_data'].to_csv(detailed_file, index=False)
        logger.info(f"💾 Detailed data saved to: {detailed_file}")
        
    except Exception as e:
        logger.error(f"❌ Error saving results: {str(e)}")

def main():
    """Main function to run the comprehensive analysis."""
    
    # Default CSV file path
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    print("🏇 Starting Comprehensive Odds Ranking Analysis...")
    print(f"📁 Analyzing file: {csv_file}")
    
    # Run the analysis
    results = analyze_odds_ranking_performance(csv_file)
    
    if results:
        # Print results
        print_ranking_analysis(results)
        
        # Save comprehensive results
        save_comprehensive_results(results)
        
        print(f"\n✅ Analysis complete!")
        print(f"📊 Summary results: comprehensive_odds_ranking_analysis.csv")
        print(f"📊 Detailed data: detailed_odds_ranking_data.csv")
    else:
        print("❌ Analysis failed - check the logs for details")

if __name__ == "__main__":
    main()
