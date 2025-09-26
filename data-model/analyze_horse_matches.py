#!/usr/bin/env python3
"""
Analyze how many horses from today's races are found in the historical database
"""

import sqlite3
import pandas as pd
from datetime import datetime

def analyze_horse_matches():
    """Analyze horse name matches between today's races and historical database"""
    
    # Database paths
    betfair_db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    betting_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/live_betting.sqlite"
    historical_db_path = "/Users/clairegrady/RiderProjects/betfair/data-model/runner_history.sqlite"
    
    print("🔍 Analyzing Horse Name Matches")
    print("=" * 50)
    
    # Get today's races from race_times
    conn_betting = sqlite3.connect(betting_db_path)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Target only Australian venues with good historical data
    target_venues = ['Gatton', 'Goulburn', 'Geelong', 'Hawkesbury']
    
    # Get races for today - only target venues
    races_query = """
    SELECT venue, race_number, race_time 
    FROM race_times 
    WHERE venue IN ({})
    AND date(race_date) = date('now')
    ORDER BY venue, race_number
    """.format(','.join(['?' for _ in target_venues]))
    
    races_df = pd.read_sql_query(races_query, conn_betting, params=target_venues)
    print(f"📅 Found {len(races_df)} races for today (Australian venues only)")
    
    # Get all horses from today's races and track by race
    all_horses = []
    race_data = {}  # Track horses by race
    
    # Connect to Betfair database for HorseMarketBook
    conn_betfair = sqlite3.connect(betfair_db_path)
    
    for _, race in races_df.iterrows():
        venue = race['venue']
        race_number = race['race_number']
        race_key = f"{venue} R{race_number}"
        
        # Get horses from HorseMarketBook
        horses_query = """
        SELECT DISTINCT RUNNER_NAME 
        FROM HorseMarketBook 
        WHERE EventName LIKE ? AND MarketName LIKE ?
        """
        
        event_pattern = f"%{venue}%"
        market_pattern = f"R{race_number}%"
        
        horses_df = pd.read_sql_query(horses_query, conn_betfair, params=[event_pattern, market_pattern])
        
        race_horses = []
        for _, horse in horses_df.iterrows():
            if horse['RUNNER_NAME'] and horse['RUNNER_NAME'] != 'Unknown':
                # Clean horse name
                clean_name = horse['RUNNER_NAME']
                if '.' in clean_name:
                    parts = clean_name.split('.', 1)
                    if len(parts) > 1:
                        clean_name = parts[1].strip().upper()
                else:
                    clean_name = clean_name.upper()
                
                horse_data = {
                    'original_name': horse['RUNNER_NAME'],
                    'clean_name': clean_name,
                    'venue': venue,
                    'race_number': race_number
                }
                
                all_horses.append(horse_data)
                race_horses.append(horse_data)
        
        race_data[race_key] = race_horses
    
    conn_betting.close()
    conn_betfair.close()
    
    print(f"🐎 Found {len(all_horses)} horses in {len(race_data)} races")
    
    # Check matches in historical database and analyze by race
    conn_historical = sqlite3.connect(historical_db_path)
    
    matches = []
    no_matches = []
    complete_races = []  # Races where ALL horses have matches
    incomplete_races = []  # Races where NOT ALL horses have matches
    
    # Analyze each race
    for race_key, race_horses in race_data.items():
        race_matches = 0
        race_total = len(race_horses)
        
        for horse in race_horses:
            clean_name = horse['clean_name']
            
            # Create normalized version for matching (remove apostrophes, hyphens, etc.)
            normalized_name = clean_name.replace("'", "").replace("-", " ").replace(".", "").strip()
            
            # Try exact match first
            query = "SELECT COUNT(*) as count FROM runner_history WHERE runnerName = ?"
            result = pd.read_sql_query(query, conn_historical, params=[clean_name])
            
            # If no exact match, try normalized matching (remove apostrophes from both sides)
            if result['count'].iloc[0] == 0:
                query = """
                SELECT COUNT(*) as count FROM runner_history 
                WHERE REPLACE(REPLACE(REPLACE(runnerName, '''', ''), '-', ' '), '.', '') = ?
                """
                result = pd.read_sql_query(query, conn_historical, params=[normalized_name])
            
            if result['count'].iloc[0] > 0:
                matches.append(horse)
                race_matches += 1
            else:
                no_matches.append(horse)
        
        # Check if race is complete (all horses matched)
        if race_matches == race_total:
            complete_races.append(race_key)
        else:
            incomplete_races.append(race_key)
    
    conn_historical.close()
    
    # Results
    print(f"\n📊 RACE-LEVEL ANALYSIS")
    print("=" * 50)
    print(f"🏁 Total races: {len(race_data)}")
    print(f"✅ Complete races (ALL horses matched): {len(complete_races)} ({len(complete_races)/len(race_data)*100:.1f}%)")
    print(f"❌ Incomplete races (some horses missing): {len(incomplete_races)} ({len(incomplete_races)/len(race_data)*100:.1f}%)")
    
    print(f"\n📊 HORSE-LEVEL ANALYSIS")
    print("=" * 50)
    print(f"✅ Horses found in historical DB: {len(matches)} ({len(matches)/len(all_horses)*100:.1f}%)")
    print(f"❌ Horses NOT found in historical DB: {len(no_matches)} ({len(no_matches)/len(all_horses)*100:.1f}%)")
    
    print(f"\n✅ COMPLETE RACES (all horses matched):")
    for race in complete_races[:10]:  # Show first 10
        print(f"  - {race}")
    if len(complete_races) > 10:
        print(f"  ... and {len(complete_races) - 10} more")
    
    print(f"\n❌ INCOMPLETE RACES (some horses missing):")
    for race in incomplete_races[:10]:  # Show first 10
        print(f"  - {race}")
    if len(incomplete_races) > 10:
        print(f"  ... and {len(incomplete_races) - 10} more")
    
    # Summary by venue
    print(f"\n🏁 RACE COMPLETENESS BY VENUE:")
    venue_race_stats = {}
    for race_key, race_horses in race_data.items():
        venue = race_key.split(' R')[0]
        if venue not in venue_race_stats:
            venue_race_stats[venue] = {'total': 0, 'complete': 0}
        venue_race_stats[venue]['total'] += 1
        if race_key in complete_races:
            venue_race_stats[venue]['complete'] += 1
    
    for venue, stats in venue_race_stats.items():
        complete_rate = stats['complete'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {venue}: {stats['complete']}/{stats['total']} complete races ({complete_rate:.1f}%)")

if __name__ == "__main__":
    analyze_horse_matches()
