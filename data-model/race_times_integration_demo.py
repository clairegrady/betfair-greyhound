#!/usr/bin/env python3
"""
Demo script showing how to integrate race times with lay betting automation
"""

import os
from lay_betting_automation import LayBettingAutomation

def main():
    # Database path
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    
    # API base URL (your C# backend)
    api_base_url = "http://localhost:5173"
    
    # Initialize automation with 10-minute betting window
    automation = LayBettingAutomation(
        db_path=db_path,
        api_base_url=api_base_url,
        std_threshold=1.5,
        max_odds=25.0,
        min_minutes_before_race=10  # Only bet within 10 minutes of race start
    )
    
    # Step 1: Scrape race times directly to database
    print("Scraping race times and saving to database...")
    from race_times_scraper import scrape_and_save_race_times
    scrape_and_save_race_times(save_to_csv=False)
    
    # Step 2: Check for races within betting window
    print("\nChecking for races within betting window...")
    races_df = automation.get_races_within_betting_window(max_minutes_ahead=10)
    
    if len(races_df) == 0:
        print("No races within betting window (0-10 minutes before start)")
        return
    
    # Step 3: Run automation (dry run first)
    print("\nRunning lay betting automation (dry run)...")
    automation.scan_and_bet(
        max_minutes_ahead=10,
        stake_per_bet=1.0,
        dry_run=True,  # Set to False for live betting
        demo_mode=False
    )

if __name__ == "__main__":
    main()
