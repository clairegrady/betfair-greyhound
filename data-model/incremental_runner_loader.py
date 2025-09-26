#!/usr/bin/env python3
"""
Incremental Runner History Data Loader

This script loads horse racing data from CSV files into a runner_history database.
It only inserts new data that's after the last date already in the database,
making it efficient for weekly updates.

Usage:
    python incremental_runner_loader.py [csv_file_path]
    
If no CSV file is provided, it defaults to:
    /Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv
"""

import sqlite3
import pandas as pd
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IncrementalRunnerLoader:
    def __init__(self, db_path="runner_history.sqlite"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to the database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
            
    def disconnect(self):
        """Disconnect from the database"""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")
            
    def create_table(self, df):
        """Create the runner_history table based on CSV columns"""
        try:
            cursor = self.conn.cursor()
            
            # Get column names and types from the dataframe
            columns = df.columns.tolist()
            
            # Create column definitions
            column_definitions = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            
            for col in columns:
                if col in ['raceNumber', 'runnerNumber', 'finishingPosition']:
                    column_definitions.append(f"{col} INTEGER")
                elif col in ['raceDistance', 'FixedWinOpen_Reference', 'FixedWinClose_Reference']:
                    column_definitions.append(f"{col} REAL")
                else:
                    column_definitions.append(f"{col} TEXT")
            
            column_definitions.append("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            
            # Create the table
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS runner_history (
                {', '.join(column_definitions)}
            )
            """
            
            cursor.execute(create_table_sql)
            self.conn.commit()
            
            # Create index on meetingDate for efficient date-based queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meeting_date 
                ON runner_history(meetingDate)
            """)
            
            # Create index on runner name for lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_runner_name 
                ON runner_history(runnerName)
            """)
            
            self.conn.commit()
            logger.info("✅ Table 'runner_history' created with indexes")
            
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise
            
    def get_last_date(self):
        """Get the last (most recent) date in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT MAX(meetingDate) FROM runner_history")
            result = cursor.fetchone()
            
            if result and result[0]:
                last_date = result[0]
                logger.info(f"📅 Last date in database: {last_date}")
                return last_date
            else:
                logger.info("📅 Database is empty - will load all data")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get last date: {e}")
            raise
            
    def load_csv_data(self, csv_path):
        """Load and prepare CSV data"""
        try:
            logger.info(f"📊 Loading CSV data from: {csv_path}")
            df = pd.read_csv(csv_path)
            
            # Convert meetingDate to string for comparison
            df['meetingDate'] = pd.to_datetime(df['meetingDate']).dt.strftime('%Y-%m-%d')
            
            logger.info(f"📊 Loaded {len(df)} records from CSV")
            logger.info(f"📊 Date range in CSV: {df['meetingDate'].min()} to {df['meetingDate'].max()}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load CSV data: {e}")
            raise
            
    def filter_new_data(self, df, last_date):
        """Filter CSV data to only include records after the last date"""
        if last_date is None:
            # Database is empty, return all data
            logger.info("📊 Database is empty - loading all data")
            return df
            
        # Filter for records after the last date
        new_data = df[df['meetingDate'] > last_date]
        
        if len(new_data) == 0:
            logger.info("📊 No new data to insert - CSV data is not newer than database")
            return None
            
        logger.info(f"📊 Found {len(new_data)} new records to insert")
        logger.info(f"📊 New data date range: {new_data['meetingDate'].min()} to {new_data['meetingDate'].max()}")
        
        return new_data
        
    def insert_data(self, df):
        """Insert data into the database"""
        try:
            cursor = self.conn.cursor()
            
            # Get all column names from the dataframe
            columns = df.columns.tolist()
            
            # Create placeholders for the SQL query
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            
            # Prepare the data for insertion
            data_to_insert = []
            for _, row in df.iterrows():
                record = []
                for col in columns:
                    value = row[col]
                    if pd.isna(value):
                        record.append(None)
                    elif col in ['raceNumber', 'runnerNumber', 'finishingPosition']:
                        record.append(int(value) if pd.notna(value) else None)
                    elif col in ['raceDistance']:
                        record.append(float(value) if pd.notna(value) else None)
                    elif col in ['FixedWinOpen_Reference', 'FixedWinClose_Reference']:
                        record.append(float(value) if pd.notna(value) else None)
                    else:
                        # For integer columns, try to convert to int, otherwise keep as string
                        try:
                            if str(value).replace('.', '').replace('-', '').isdigit():
                                record.append(int(float(value)))
                            else:
                                record.append(str(value))
                        except:
                            record.append(str(value))
                data_to_insert.append(record)
            
            # Insert data in batches for efficiency
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(data_to_insert), batch_size):
                batch = data_to_insert[i:i + batch_size]
                
                cursor.executemany(f"""
                    INSERT INTO runner_history ({column_names})
                    VALUES ({placeholders})
                """, batch)
                
                total_inserted += len(batch)
                logger.info(f"📊 Inserted batch {i//batch_size + 1}: {len(batch)} records (Total: {total_inserted})")
            
            self.conn.commit()
            logger.info(f"✅ Successfully inserted {total_inserted} new records")
            
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            self.conn.rollback()
            raise
            
    def get_database_stats(self):
        """Get statistics about the database"""
        try:
            cursor = self.conn.cursor()
            
            # Total records
            cursor.execute("SELECT COUNT(*) FROM runner_history")
            total_records = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("SELECT MIN(meetingDate), MAX(meetingDate) FROM runner_history")
            min_date, max_date = cursor.fetchone()
            
            # Unique runners
            cursor.execute("SELECT COUNT(DISTINCT runnerName) FROM runner_history")
            unique_runners = cursor.fetchone()[0]
            
            # Unique meetings
            cursor.execute("SELECT COUNT(DISTINCT meetingName || meetingDate) FROM runner_history")
            unique_meetings = cursor.fetchone()[0]
            
            logger.info("📊 Database Statistics:")
            logger.info(f"   Total records: {total_records:,}")
            logger.info(f"   Date range: {min_date} to {max_date}")
            logger.info(f"   Unique runners: {unique_runners:,}")
            logger.info(f"   Unique meetings: {unique_meetings:,}")
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            
    def load_incremental_data(self, csv_path):
        """Main method to load incremental data"""
        try:
            logger.info("🚀 Starting incremental data load...")
            
            # Connect to database
            self.connect()
            
            # Load CSV data first to get column structure
            df = self.load_csv_data(csv_path)
            
            # Create table based on CSV structure
            self.create_table(df)
            
            # Get last date in database
            last_date = self.get_last_date()
            
            # Filter for new data only
            new_data = self.filter_new_data(df, last_date)
            
            if new_data is None or len(new_data) == 0:
                logger.info("✅ No new data to insert")
                return
                
            # Insert new data
            self.insert_data(new_data)
            
            # Show database stats
            self.get_database_stats()
            
            logger.info("✅ Incremental data load completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Incremental data load failed: {e}")
            raise
        finally:
            self.disconnect()

def main():
    """Main function"""
    # Default CSV path
    default_csv = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    
    # Get CSV path from command line argument or use default
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = default_csv
        
    # Check if CSV file exists
    if not Path(csv_path).exists():
        logger.error(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)
        
    # Create loader and run
    loader = IncrementalRunnerLoader()
    loader.load_incremental_data(csv_path)

if __name__ == "__main__":
    main()
