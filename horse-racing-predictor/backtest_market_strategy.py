#!/usr/bin/env python3
"""
Backtest the Market-Based Strategy
Simple rule: Bet on favorite to PLACE if odds 1.5-3.0
Uses tiered Kelly staking
"""

import sqlite3
import pandas as pd
import numpy as np

# Configuration
DB_PATH = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/horse_racing_ml.db"
STARTING_BANKROLL = 10000
KELLY_FRACTION = 0.25

# TEST: Extended upper range (1.5-4.0 instead of 1.5-3.0)
EDGE_BY_ODDS = {
    (1.5, 2.0): 0.0396,  # 3.96% edge
    (2.0, 3.0): 0.0692,  # 6.92% edge
    (3.0, 4.0): 0.0692,  # Assuming same edge as 2.0-3.0 for now
}

def calculate_kelly_stake(odds, bankroll):
    """Calculate stake using Kelly Criterion"""
    for (min_odds, max_odds), edge in EDGE_BY_ODDS.items():
        if min_odds <= odds < max_odds:
            stake = bankroll * edge * KELLY_FRACTION
            return round(stake, 2)
    return 0

def main():
    print("=" * 80)
    print("BACKTESTING MARKET-BASED STRATEGY")
    print("=" * 80)
    print("\nStrategy: Bet on favorite to PLACE if odds 1.5-4.0 (TESTING extended upper range)")
    print(f"Staking: Tiered Kelly ({KELLY_FRACTION*100:.0f}% Kelly)")
    print(f"Starting bankroll: ${STARTING_BANKROLL:,}")
    
    # Load data
    print("\n📊 Loading historical data...")
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            MARKET_ID as marketId,
            SELECTION_ID as selectionId,
            runnerName,
            BSP,
            finishingPosition,
            raceStartTime,
            meetingName as trackName,
            raceDistance
        FROM combined_data
        WHERE BSP IS NOT NULL
        AND BSP > 0
        AND finishingPosition IS NOT NULL
        AND finishingPosition >= 0
        ORDER BY raceStartTime
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"   Loaded {len(df):,} horses from {df['marketId'].nunique():,} races")
    
    # Identify favorite in each race (lowest BSP)
    print("\n🔍 Identifying favorites in each race...")
    favorites = df.loc[df.groupby('marketId')['BSP'].idxmin()].copy()
    
    print(f"   Found {len(favorites):,} favorites")
    
    # Filter for favorites in our odds range (1.5-4.0)
    favorites_in_range = favorites[
        (favorites['BSP'] >= 1.5) & (favorites['BSP'] < 4.0)
    ].copy()
    
    print(f"   {len(favorites_in_range):,} favorites have odds 1.5-4.0 ({len(favorites_in_range)/len(favorites)*100:.1f}%)")
    
    # Determine if horse placed (top 3)
    favorites_in_range['placed'] = (favorites_in_range['finishingPosition'] > 0) & \
                                     (favorites_in_range['finishingPosition'] <= 3)
    
    # Split by odds ranges
    range_1_5_2_0 = favorites_in_range[
        (favorites_in_range['BSP'] >= 1.5) & (favorites_in_range['BSP'] < 2.0)
    ]
    range_2_0_3_0 = favorites_in_range[
        (favorites_in_range['BSP'] >= 2.0) & (favorites_in_range['BSP'] < 3.0)
    ]
    range_3_0_4_0 = favorites_in_range[
        (favorites_in_range['BSP'] >= 3.0) & (favorites_in_range['BSP'] < 4.0)
    ]
    
    print("\n" + "=" * 80)
    print("RESULTS BY ODDS RANGE")
    print("=" * 80)
    
    # Function to calculate stats
    def calculate_stats(races_df, range_name, edge):
        if len(races_df) == 0:
            return None
        
        place_rate = races_df['placed'].sum() / len(races_df)
        avg_odds = races_df['BSP'].mean()
        
        # Calculate P&L with flat stakes first (for comparison)
        flat_stake = 100
        flat_total_staked = flat_stake * len(races_df)
        flat_total_return = sum(races_df.apply(
            lambda x: flat_stake * x['BSP'] if x['placed'] else 0, axis=1
        ))
        flat_profit = flat_total_return - flat_total_staked
        flat_roi = (flat_profit / flat_total_staked) * 100
        
        # Calculate P&L with Kelly staking
        bankroll = STARTING_BANKROLL
        kelly_total_staked = 0
        kelly_total_return = 0
        
        for _, race in races_df.iterrows():
            stake = calculate_kelly_stake(race['BSP'], bankroll)
            kelly_total_staked += stake
            
            if race['placed']:
                returns = stake * race['BSP']
                kelly_total_return += returns
                profit = returns - stake
            else:
                profit = -stake
            
            # Update bankroll (for next bet sizing)
            bankroll += profit
        
        kelly_profit = kelly_total_return - kelly_total_staked
        kelly_roi = (kelly_profit / kelly_total_staked) * 100
        final_bankroll = STARTING_BANKROLL + sum(races_df.apply(
            lambda x: (calculate_kelly_stake(x['BSP'], STARTING_BANKROLL) * x['BSP'] - 
                      calculate_kelly_stake(x['BSP'], STARTING_BANKROLL)) if x['placed'] 
                      else -calculate_kelly_stake(x['BSP'], STARTING_BANKROLL), axis=1
        ))
        
        return {
            'range': range_name,
            'races': len(races_df),
            'avg_odds': avg_odds,
            'place_rate': place_rate,
            'expected_edge': edge,
            'flat_roi': flat_roi,
            'kelly_roi': kelly_roi,
            'flat_profit': flat_profit,
            'kelly_profit': kelly_profit,
            'flat_staked': flat_total_staked,
            'kelly_staked': kelly_total_staked,
            'final_bankroll': final_bankroll
        }
    
    # Calculate stats for each range
    stats_1_5_2_0 = calculate_stats(range_1_5_2_0, "1.5-2.0", 0.0396)
    stats_2_0_3_0 = calculate_stats(range_2_0_3_0, "2.0-3.0", 0.0692)
    stats_3_0_4_0 = calculate_stats(range_3_0_4_0, "3.0-4.0", 0.0692)
    
    # Display results
    for stats in [stats_1_5_2_0, stats_2_0_3_0, stats_3_0_4_0]:
        if stats:
            print(f"\n📈 Odds Range: {stats['range']}")
            print(f"   Sample size: {stats['races']:,} races")
            print(f"   Avg odds: {stats['avg_odds']:.2f}")
            print(f"   Place rate: {stats['place_rate']*100:.2f}% (won {int(stats['races']*stats['place_rate'])} times)")
            print(f"   Expected edge: {stats['expected_edge']*100:.2f}%")
            print(f"\n   FLAT STAKING ($100/bet):")
            print(f"      Total staked: ${stats['flat_staked']:,.2f}")
            print(f"      Total return: ${stats['flat_staked'] + stats['flat_profit']:,.2f}")
            print(f"      Profit: ${stats['flat_profit']:,.2f}")
            print(f"      ROI: {stats['flat_roi']:+.2f}%")
            print(f"\n   KELLY STAKING (25% Kelly):")
            print(f"      Total staked: ${stats['kelly_staked']:,.2f}")
            print(f"      Total return: ${stats['kelly_staked'] + stats['kelly_profit']:,.2f}")
            print(f"      Profit: ${stats['kelly_profit']:,.2f}")
            print(f"      ROI: {stats['kelly_roi']:+.2f}%")
            print(f"      Final bankroll: ${stats['final_bankroll']:,.2f} (from ${STARTING_BANKROLL:,})")
    
    # Combined stats
    print("\n" + "=" * 80)
    print("COMBINED RESULTS (ALL BETS)")
    print("=" * 80)
    
    total_races = len(favorites_in_range)
    total_placed = favorites_in_range['placed'].sum()
    overall_place_rate = total_placed / total_races
    avg_odds = favorites_in_range['BSP'].mean()
    
    # Flat staking combined
    flat_stake = 100
    flat_total_staked = flat_stake * total_races
    flat_total_return = sum(favorites_in_range.apply(
        lambda x: flat_stake * x['BSP'] if x['placed'] else 0, axis=1
    ))
    flat_profit = flat_total_return - flat_total_staked
    flat_roi = (flat_profit / flat_total_staked) * 100
    
    # Kelly staking combined
    kelly_total_staked = 0
    kelly_total_return = 0
    
    for _, race in favorites_in_range.iterrows():
        stake = calculate_kelly_stake(race['BSP'], STARTING_BANKROLL)
        kelly_total_staked += stake
        
        if race['placed']:
            kelly_total_return += stake * race['BSP']
    
    kelly_profit = kelly_total_return - kelly_total_staked
    kelly_roi = (kelly_profit / kelly_total_staked) * 100
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Total bets: {total_races:,}")
    print(f"   Wins: {total_placed:,}")
    print(f"   Losses: {total_races - total_placed:,}")
    print(f"   Win rate: {overall_place_rate*100:.2f}%")
    print(f"   Avg odds: {avg_odds:.2f}")
    
    print(f"\n💰 FLAT STAKING ($100/bet):")
    print(f"   Total staked: ${flat_total_staked:,.2f}")
    print(f"   Total return: ${flat_total_return:,.2f}")
    print(f"   Profit: ${flat_profit:+,.2f}")
    print(f"   ROI: {flat_roi:+.2f}%")
    
    print(f"\n💰 KELLY STAKING (25% Kelly, Tiered):")
    print(f"   Total staked: ${kelly_total_staked:,.2f}")
    print(f"   Total return: ${kelly_total_return:,.2f}")
    print(f"   Profit: ${kelly_profit:+,.2f}")
    print(f"   ROI: {kelly_roi:+.2f}%")
    
    # Monthly projections
    if len(favorites_in_range) > 0:
        # Get date range
        favorites_in_range['date'] = pd.to_datetime(favorites_in_range['raceStartTime'])
        date_range = (favorites_in_range['date'].max() - favorites_in_range['date'].min()).days
        months = date_range / 30
        
        bets_per_month = total_races / months if months > 0 else 0
        kelly_profit_per_month = kelly_profit / months if months > 0 else 0
        
        print(f"\n📅 Projections:")
        print(f"   Date range: {favorites_in_range['date'].min().date()} to {favorites_in_range['date'].max().date()}")
        print(f"   Period: {date_range} days ({months:.1f} months)")
        print(f"   Avg bets/month: {bets_per_month:.0f}")
        print(f"   Avg profit/month: ${kelly_profit_per_month:+,.2f}")
    
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    
    if kelly_roi > 0:
        print(f"\n✅ Strategy is PROFITABLE: +{kelly_roi:.2f}% ROI with Kelly staking")
        print(f"   Turned ${STARTING_BANKROLL:,} into ${STARTING_BANKROLL + kelly_profit:,.2f}")
        print(f"   Based on {total_races:,} bets over {date_range} days")
    else:
        print(f"\n❌ Strategy is UNPROFITABLE: {kelly_roi:.2f}% ROI")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

