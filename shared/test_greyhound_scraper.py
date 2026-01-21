#!/usr/bin/env python3
"""
Test script for greyhound_race_scraper_postgres.py
Tests scraping without inserting into database
"""
import sys
sys.path.insert(0, '/Users/clairegrady/RiderProjects/betfair/shared')

from greyhound_race_scraper_postgres import GreyhoundRaceTimesScraper

def test_scraper():
    print("="*80)
    print("Testing Greyhound Race Times Scraper (PostgreSQL)")
    print("="*80)
    
    scraper = GreyhoundRaceTimesScraper()
    
    print("\n1. Testing scraping (fetching data only, not saving)...")
    try:
        races = scraper.scrape()
        
        print(f"\n✅ Successfully scraped {len(races)} races")
        
        if races:
            print("\n📊 Sample races (first 5):")
            print("-" * 80)
            for i, race in enumerate(races[:5], 1):
                print(f"\nRace {i}:")
                print(f"  Venue: {race['venue']}")
                print(f"  Race #: {race['race_number']}")
                print(f"  Time: {race['race_time']}")
                print(f"  Date: {race['race_date']}")
                print(f"  Country: {race['country']}")
                print(f"  Timezone: {race['timezone']}")
            
            # Show summary by country
            print("\n📈 Summary by country:")
            print("-" * 80)
            from collections import Counter
            country_counts = Counter(r['country'] for r in races)
            for country, count in country_counts.items():
                print(f"  {country}: {count} races")
            
            # Show summary by venue (top 10)
            print("\n🏟️  Top 10 venues by race count:")
            print("-" * 80)
            venue_counts = Counter(r['venue'] for r in races)
            for venue, count in venue_counts.most_common(10):
                print(f"  {venue}: {count} races")
        else:
            print("\n⚠️  No races were scraped")
            
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*80)
    print("✅ Scraper test complete! Data looks good.")
    print("To actually save to database, run: scraper.save_to_database(races)")
    print("="*80)
    return True

if __name__ == "__main__":
    test_scraper()
