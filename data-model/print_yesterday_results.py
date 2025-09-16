import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def print_yesterday_results():
    """Print all Australian racing results from yesterday"""
    
    # Database path
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    
    # Get today's date (since the scraper saved data with today's date)
    target_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get all races from yesterday
        query = """
        SELECT DISTINCT 
            race_date, venue, race_number, race_name, race_distance, 
            race_class, race_prize_money, track_condition, weather
        FROM australian_punters_race_results 
        WHERE race_date = ?
        ORDER BY venue, race_number
        """
        
        races_df = pd.read_sql_query(query, conn, params=[target_date])
        
        if races_df.empty:
            print(f"❌ No Australian racing results found for {target_date}")
            return
        
        print(f"🇦🇺 AUSTRALIAN RACING RESULTS - {target_date}")
        print("=" * 80)
        print(f"Total races: {len(races_df)}")
        print()
        
        # Group by venue
        for venue in sorted(races_df['venue'].unique()):
            venue_races = races_df[races_df['venue'] == venue]
            print(f"🏁 {venue.upper()}")
            print("-" * 50)
            
            for _, race in venue_races.iterrows():
                print(f"Race {race['race_number']}: {race['race_name']}")
                print(f"  Distance: {race['race_distance']}")
                print(f"  Class: {race['race_class']}")
                print(f"  Prize: {race['race_prize_money']}")
                print(f"  Track: {race['track_condition']}")
                print(f"  Weather: {race['weather']}")
                # Count runners for this race
                runner_count_query = """
                SELECT COUNT(*) as runner_count 
                FROM australian_punters_race_results 
                WHERE race_date = ? AND venue = ? AND race_number = ?
                """
                runner_count = pd.read_sql_query(runner_count_query, conn, params=[
                    target_date, race['venue'], race['race_number']
                ]).iloc[0]['runner_count']
                print(f"  Runners: {runner_count}")
                print()
        
        # Get runner details for each race
        print("\n🏇 RUNNER DETAILS")
        print("=" * 80)
        
        for venue in sorted(races_df['venue'].unique()):
            venue_races = races_df[races_df['venue'] == venue]
            
            for _, race in venue_races.iterrows():
                print(f"\n🏁 {venue} - Race {race['race_number']}: {race['race_name']}")
                print("-" * 60)
                
                # Get runners for this race
                runners_query = """
                SELECT horse_name, horse_number, jockey_name, trainer_name, barrier, 
                       weight, finishing_position, margin, starting_price, last_600m_time
                FROM australian_punters_race_results 
                WHERE race_date = ? AND venue = ? AND race_number = ?
                ORDER BY finishing_position
                """
                
                runners_df = pd.read_sql_query(runners_query, conn, params=[
                    target_date, race['venue'], race['race_number']
                ])
                
                if not runners_df.empty:
                    # Print results in a nice table format
                    print(f"{'Pos':<4} {'Horse':<20} {'Jockey':<15} {'Trainer':<15} {'Weight':<8} {'SP':<8} {'Margin':<10}")
                    print("-" * 80)
                    
                    for _, runner in runners_df.iterrows():
                        pos = runner['finishing_position'] if runner['finishing_position'] else 'N/A'
                        horse = runner['horse_name'] if runner['horse_name'] else 'N/A'
                        jockey = runner['jockey_name'] if runner['jockey_name'] else 'N/A'
                        trainer = runner['trainer_name'] if runner['trainer_name'] else 'N/A'
                        weight = runner['weight'] if runner['weight'] else 'N/A'
                        sp = runner['starting_price'] if runner['starting_price'] else 'N/A'
                        margin = runner['margin'] if runner['margin'] else 'N/A'
                        
                        print(f"{pos:<4} {horse:<20} {jockey:<15} {trainer:<15} {weight:<8} {sp:<8} {margin:<10}")
                else:
                    print("No runner details available")
        
        # Summary statistics
        print(f"\n📊 SUMMARY STATISTICS")
        print("=" * 50)
        
        # Total runners
        total_runners_query = "SELECT COUNT(*) as total FROM australian_punters_race_results WHERE race_date = ?"
        total_runners = pd.read_sql_query(total_runners_query, conn, params=[target_date]).iloc[0]['total']
        
        # Races by state
        state_query = """
        SELECT 
            CASE 
                WHEN venue LIKE '%NSW%' OR venue LIKE '%Sydney%' OR venue LIKE '%Randwick%' OR venue LIKE '%Rosehill%' OR venue LIKE '%Warwick Farm%' OR venue LIKE '%Canterbury%' OR venue LIKE '%Kembla Grange%' OR venue LIKE '%Newcastle%' OR venue LIKE '%Gosford%' OR venue LIKE '%Wyong%' OR venue LIKE '%Hawkesbury%' OR venue LIKE '%Goulburn%' OR venue LIKE '%Wagga Wagga%' OR venue LIKE '%Albury%' OR venue LIKE '%Canberra%' OR venue LIKE '%Queanbeyan%' OR venue LIKE '%Bathurst%' OR venue LIKE '%Coffs Harbour%' THEN 'NSW'
                WHEN venue LIKE '%VIC%' OR venue LIKE '%Melbourne%' OR venue LIKE '%Flemington%' OR venue LIKE '%Caulfield%' OR venue LIKE '%Moonee Valley%' OR venue LIKE '%Sandown%' OR venue LIKE '%Mornington%' OR venue LIKE '%Geelong%' OR venue LIKE '%Ballarat%' OR venue LIKE '%Bendigo%' OR venue LIKE '%Warrnambool%' OR venue LIKE '%Hamilton%' OR venue LIKE '%Mildura%' OR venue LIKE '%Swan Hill%' OR venue LIKE '%Echuca%' OR venue LIKE '%Kilmore%' OR venue LIKE '%Pakenham%' OR venue LIKE '%Cranbourne%' OR venue LIKE '%Sale%' OR venue LIKE '%Traralgon%' OR venue LIKE '%Bairnsdale%' OR venue LIKE '%Moe%' THEN 'VIC'
                WHEN venue LIKE '%QLD%' OR venue LIKE '%Brisbane%' OR venue LIKE '%Eagle Farm%' OR venue LIKE '%Doomben%' OR venue LIKE '%Gold Coast%' OR venue LIKE '%Sunshine Coast%' OR venue LIKE '%Ipswich%' OR venue LIKE '%Toowoomba%' OR venue LIKE '%Rockhampton%' OR venue LIKE '%Townsville%' OR venue LIKE '%Cairns%' OR venue LIKE '%Mackay%' THEN 'QLD'
                WHEN venue LIKE '%SA%' OR venue LIKE '%Adelaide%' OR venue LIKE '%Morphettville%' OR venue LIKE '%Murray Bridge%' OR venue LIKE '%Gawler%' OR venue LIKE '%Port Augusta%' OR venue LIKE '%Bordertown%' THEN 'SA'
                WHEN venue LIKE '%WA%' OR venue LIKE '%Perth%' OR venue LIKE '%Ascot%' OR venue LIKE '%Belmont%' OR venue LIKE '%Bunbury%' OR venue LIKE '%Kalgoorlie%' OR venue LIKE '%Geraldton%' OR venue LIKE '%Northam%' THEN 'WA'
                WHEN venue LIKE '%TAS%' OR venue LIKE '%Hobart%' OR venue LIKE '%Launceston%' OR venue LIKE '%Devonport%' OR venue LIKE '%Spreyton%' OR venue LIKE '%Longford%' THEN 'TAS'
                WHEN venue LIKE '%NT%' OR venue LIKE '%Darwin%' OR venue LIKE '%Alice Springs%' OR venue LIKE '%Katherine%' OR venue LIKE '%Tennant Creek%' THEN 'NT'
                ELSE 'Other'
            END as state,
            COUNT(DISTINCT race_date || venue || race_number) as race_count
        FROM australian_punters_race_results 
        WHERE race_date = ?
        GROUP BY state
        ORDER BY race_count DESC
        """
        
        state_stats = pd.read_sql_query(state_query, conn, params=[target_date])
        
        print(f"Total races: {len(races_df)}")
        print(f"Total runners: {total_runners}")
        print(f"Date: {target_date}")
        print()
        print("Races by state:")
        for _, row in state_stats.iterrows():
            print(f"  {row['state']}: {row['race_count']} races")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print_yesterday_results()
