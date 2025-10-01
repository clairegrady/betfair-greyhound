#!/usr/bin/env python3
"""
Analyze simulation results by race type (horse vs harness)
"""

import sqlite3
import pandas as pd

def calculate_bet_outcome(bet, race_results):
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
    else:  # place bet
        placed = finishing_position in [1, 2, 3, 4]
        if placed:
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

def main():
    # Connect to database
    conn = sqlite3.connect('betting_simulation.sqlite')

    # Get simulation bets
    bets_query = '''
        SELECT 
            market_id,
            venue,
            race_number,
            race_date,
            strategy,
            horse_name,
            bet_type,
            stake,
            win_odds,
            place_odds,
            created_at
        FROM valid_simulation_results 
        WHERE race_date = '2025-09-30'
        ORDER BY venue, race_number, created_at
    '''
    bets_df = pd.read_sql_query(bets_query, conn)

    # Get race results
    results_query = '''
        SELECT 
            rr.venue,
            rr.race_number,
            rr.race_date,
            hr.finishing_position,
            hr.horse_name,
            hr.starting_price
        FROM race_results rr
        JOIN horse_results hr ON rr.id = hr.race_id
        WHERE rr.race_date = '2025-09-30'
        ORDER BY rr.venue, rr.race_number, hr.finishing_position
    '''
    results_df = pd.read_sql_query(results_query, conn)

    # Define race types
    harness_venues = ['Albion Park', 'Gloucester Park', 'Mildura', 'Shepparton', 'Young']
    horse_venues = ['Cairns', 'Grafton', 'Tamworth', 'Tatura']

    # Split by race type
    harness_bets = bets_df[bets_df['venue'].isin(harness_venues)]
    horse_bets = bets_df[bets_df['venue'].isin(horse_venues)]

    harness_results = results_df[results_df['venue'].isin(harness_venues)]
    horse_results = results_df[results_df['venue'].isin(horse_venues)]

    print('=== HARNESS RACES ANALYSIS ===')
    print(f'Harness bets: {len(harness_bets)}')
    print(f'Harness race results: {len(harness_results)}')

    # Calculate outcomes for harness races
    harness_outcomes = []
    for _, bet in harness_bets.iterrows():
        outcome = calculate_bet_outcome(bet.to_dict(), harness_results)
        harness_outcomes.append({
            'strategy': bet['strategy'],
            'bet_type': bet['bet_type'],
            'stake': bet['stake'],
            'profit_loss': outcome['profit_loss'],
            'has_results': outcome['has_results']
        })

    harness_outcomes_df = pd.DataFrame(harness_outcomes)

    # Calculate ROI by strategy for harness races
    print('\nHARNESS RACES - Strategy Performance:')
    harness_summary = []
    for strategy in harness_outcomes_df['strategy'].unique():
        strategy_bets = harness_outcomes_df[harness_outcomes_df['strategy'] == strategy]
        settled_bets = strategy_bets[strategy_bets['has_results'] == True]
        
        if not settled_bets.empty:
            total_stake = settled_bets['stake'].sum()
            total_profit = settled_bets['profit_loss'].sum()
            roi = (total_profit / total_stake) * 100 if total_stake > 0 else 0
            harness_summary.append({
                'strategy': strategy,
                'profit': total_profit,
                'roi': roi,
                'bets': len(settled_bets)
            })
            print(f'  {strategy}: ${total_profit:.2f} profit, {roi:.1f}% ROI ({len(settled_bets)} bets)')

    print('\n=== HORSE RACES ANALYSIS ===')
    print(f'Horse bets: {len(horse_bets)}')
    print(f'Horse race results: {len(horse_results)}')

    # Calculate outcomes for horse races
    horse_outcomes = []
    for _, bet in horse_bets.iterrows():
        outcome = calculate_bet_outcome(bet.to_dict(), horse_results)
        horse_outcomes.append({
            'strategy': bet['strategy'],
            'bet_type': bet['bet_type'],
            'stake': bet['stake'],
            'profit_loss': outcome['profit_loss'],
            'has_results': outcome['has_results']
        })

    horse_outcomes_df = pd.DataFrame(horse_outcomes)

    # Calculate ROI by strategy for horse races
    print('\nHORSE RACES - Strategy Performance:')
    horse_summary = []
    for strategy in horse_outcomes_df['strategy'].unique():
        strategy_bets = horse_outcomes_df[horse_outcomes_df['strategy'] == strategy]
        settled_bets = strategy_bets[strategy_bets['has_results'] == True]
        
        if not settled_bets.empty:
            total_stake = settled_bets['stake'].sum()
            total_profit = settled_bets['profit_loss'].sum()
            roi = (total_profit / total_stake) * 100 if total_stake > 0 else 0
            horse_summary.append({
                'strategy': strategy,
                'profit': total_profit,
                'roi': roi,
                'bets': len(settled_bets)
            })
            print(f'  {strategy}: ${total_profit:.2f} profit, {roi:.1f}% ROI ({len(settled_bets)} bets)')

    # Summary comparison
    print('\n=== SUMMARY COMPARISON ===')
    print('Strategy Performance by Race Type:')
    print('Strategy\t\tHarness ROI\tHorse ROI')
    print('-' * 50)
    
    # Get all strategies
    all_strategies = set()
    for item in harness_summary:
        all_strategies.add(item['strategy'])
    for item in horse_summary:
        all_strategies.add(item['strategy'])
    
    # Create comparison data
    comparison_data = []
    for strategy in sorted(all_strategies):
        harness_roi = next((item['roi'] for item in harness_summary if item['strategy'] == strategy), 0)
        horse_roi = next((item['roi'] for item in horse_summary if item['strategy'] == strategy), 0)
        harness_profit = next((item['profit'] for item in harness_summary if item['strategy'] == strategy), 0)
        horse_profit = next((item['profit'] for item in horse_summary if item['strategy'] == strategy), 0)
        harness_bets = next((item['bets'] for item in harness_summary if item['strategy'] == strategy), 0)
        horse_bets = next((item['bets'] for item in horse_summary if item['strategy'] == strategy), 0)
        
        comparison_data.append({
            'strategy': strategy,
            'harness_roi': harness_roi,
            'harness_profit': harness_profit,
            'harness_bets': harness_bets,
            'horse_roi': horse_roi,
            'horse_profit': horse_profit,
            'horse_bets': horse_bets
        })
        
        print(f'{strategy}\t\t{harness_roi:.1f}%\t\t{horse_roi:.1f}%')

    # Export to CSV files
    print('\n=== EXPORTING TO CSV ===')
    
    # Export harness summary with rounded decimals
    harness_df = pd.DataFrame(harness_summary)
    harness_df['profit'] = harness_df['profit'].round(2)
    harness_df['roi'] = harness_df['roi'].round(2)
    harness_df.to_csv('harness_race_performance.csv', index=False)
    print('✅ Harness race performance exported to harness_race_performance.csv')
    
    # Export horse summary with rounded decimals
    horse_df = pd.DataFrame(horse_summary)
    horse_df['profit'] = horse_df['profit'].round(2)
    horse_df['roi'] = horse_df['roi'].round(2)
    horse_df.to_csv('horse_race_performance.csv', index=False)
    print('✅ Horse race performance exported to horse_race_performance.csv')
    
    # Export comparison summary with rounded decimals
    comparison_df = pd.DataFrame(comparison_data)
    comparison_df['harness_roi'] = comparison_df['harness_roi'].round(2)
    comparison_df['harness_profit'] = comparison_df['harness_profit'].round(2)
    comparison_df['horse_roi'] = comparison_df['horse_roi'].round(2)
    comparison_df['horse_profit'] = comparison_df['horse_profit'].round(2)
    comparison_df.to_csv('race_type_comparison.csv', index=False)
    print('✅ Race type comparison exported to race_type_comparison.csv')
    
    # Export detailed outcomes with rounded decimals
    harness_outcomes_df['stake'] = harness_outcomes_df['stake'].round(2)
    harness_outcomes_df['profit_loss'] = harness_outcomes_df['profit_loss'].round(2)
    harness_outcomes_df.to_csv('harness_detailed_outcomes.csv', index=False)
    
    horse_outcomes_df['stake'] = horse_outcomes_df['stake'].round(2)
    horse_outcomes_df['profit_loss'] = horse_outcomes_df['profit_loss'].round(2)
    horse_outcomes_df.to_csv('horse_detailed_outcomes.csv', index=False)
    print('✅ Detailed outcomes exported to harness_detailed_outcomes.csv and horse_detailed_outcomes.csv')

    conn.close()

if __name__ == "__main__":
    main()
