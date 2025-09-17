"""
Race Time Integration - Integrates scraped race times with lay betting automation
"""
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_race_times(csv_file: str = None):
    """Load race times from CSV file"""
    if csv_file is None:
        csv_file = f"race_times_{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    try:
        df = pd.read_csv(csv_file)
        logger.info(f"Loaded {len(df)} race times from {csv_file}")
        return df
    except FileNotFoundError:
        logger.error(f"Race times file {csv_file} not found")
        return pd.DataFrame()


def get_races_starting_soon(race_times_df: pd.DataFrame, minutes_ahead: int = 30):
    """
    Get races that are starting within the next X minutes
    
    Args:
        race_times_df: DataFrame with race times
        minutes_ahead: How many minutes ahead to look for races
        
    Returns:
        DataFrame of races starting soon
    """
    if race_times_df.empty:
        return pd.DataFrame()
    
    current_time = datetime.now()
    target_time = current_time + timedelta(minutes=minutes_ahead)
    
    races_starting_soon = []
    
    for _, race in race_times_df.iterrows():
        try:
            # Parse race time (assuming 24-hour format)
            race_time_str = race['race_time_24h']
            if ':' in race_time_str:
                hour, minute = race_time_str.split(':')
                race_datetime = current_time.replace(
                    hour=int(hour), 
                    minute=int(minute), 
                    second=0, 
                    microsecond=0
                )
                
                # Check if race is starting soon
                if current_time <= race_datetime <= target_time:
                    races_starting_soon.append({
                        'venue': race['venue'],
                        'race_number': race['race_number'],
                        'race_time': race['race_time_24h'],
                        'minutes_until_start': int((race_datetime - current_time).total_seconds() / 60)
                    })
        except Exception as e:
            logger.warning(f"Error parsing race time {race['race_time_24h']}: {e}")
            continue
    
    if races_starting_soon:
        df = pd.DataFrame(races_starting_soon)
        logger.info(f"Found {len(df)} races starting within {minutes_ahead} minutes:")
        for _, race in df.iterrows():
            logger.info(f"  {race['venue']} R{race['race_number']} - {race['race_time']} ({race['minutes_until_start']} min)")
        return df
    else:
        logger.info(f"No races starting within {minutes_ahead} minutes")
        return pd.DataFrame()


def find_matching_races_in_database(races_starting_soon: pd.DataFrame, db_path: str):
    """
    Find races in the Betfair database that match the scraped race times
    
    Args:
        races_starting_soon: DataFrame of races starting soon
        db_path: Path to the Betfair database
        
    Returns:
        DataFrame of matching races with database info
    """
    if races_starting_soon.empty:
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    matching_races = []
    
    for _, race in races_starting_soon.iterrows():
        venue = race['venue']
        race_num = race['race_number']
        
        # Try to find matching race in database
        query = """
        SELECT DISTINCT 
            h.EventName,
            h.MarketName,
            h.MarketId,
            m.OpenDate
        FROM HorseMarketBook h
        JOIN MarketCatalogue m ON h.EventName = m.EventName AND h.MarketName = m.MarketName
        WHERE h.MarketName != 'To Be Placed'
        AND m.OpenDate IS NOT NULL
        AND date(m.OpenDate) = date('now')
        AND (
            h.EventName LIKE ? OR 
            h.EventName LIKE ? OR
            h.EventName LIKE ?
        )
        """
        
        # Try different venue name patterns
        patterns = [
            f"%{venue}%",
            f"%{venue.replace(' ', '')}%",
            f"%{venue.split()[0]}%"  # First word only
        ]
        
        for pattern in patterns:
            df = pd.read_sql_query(query, conn, params=[pattern, pattern, pattern])
            if not df.empty:
                for _, db_race in df.iterrows():
                    matching_races.append({
                        'venue': venue,
                        'race_number': race_num,
                        'race_time': race['race_time'],
                        'minutes_until_start': race['minutes_until_start'],
                        'event_name': db_race['EventName'],
                        'market_name': db_race['MarketName'],
                        'market_id': db_race['MarketId'],
                        'open_date': db_race['OpenDate']
                    })
                break  # Found match, no need to try other patterns
    
    conn.close()
    
    if matching_races:
        df = pd.DataFrame(matching_races)
        logger.info(f"Found {len(df)} matching races in database:")
        for _, race in df.iterrows():
            logger.info(f"  {race['venue']} R{race['race_number']} - {race['event_name']} ({race['market_id']})")
        return df
    else:
        logger.info("No matching races found in database")
        return pd.DataFrame()


def main():
    """Test the race time integration"""
    # Load race times
    race_times = load_race_times()
    
    if race_times.empty:
        logger.error("No race times loaded")
        return
    
    # Find races starting soon (next 60 minutes)
    races_starting_soon = get_races_starting_soon(race_times, minutes_ahead=60)
    
    if races_starting_soon.empty:
        logger.info("No races starting soon")
        return
    
    # Find matching races in database
    db_path = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
    matching_races = find_matching_races_in_database(races_starting_soon, db_path)
    
    if not matching_races.empty:
        # Save results
        output_file = f"races_starting_soon_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"
        matching_races.to_csv(output_file, index=False)
        logger.info(f"Saved {len(matching_races)} matching races to {output_file}")
    
    return matching_races


if __name__ == "__main__":
    main()
