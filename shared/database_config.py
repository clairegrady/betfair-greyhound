"""
PostgreSQL Database Configuration Module

This module provides database connection utilities for the betfair betting system.
All databases have been migrated from SQLite to PostgreSQL.

Usage:
    from shared.database_config import get_connection, PG_CONFIG
    
    # Get a connection to betfairmarket database
    conn = get_connection('betfairmarket')
    
    # Or use the config directly with psycopg2
    import psycopg2
    conn = psycopg2.connect(**PG_CONFIG['betfairmarket'])
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# PostgreSQL connection configurations
PG_CONFIG = {
    "betfairmarket": {
        "host": "localhost",
        "port": 5432,
        "database": "betfairmarket",
        "user": "clairegrady",
        "password": "World17!"
    },
    "betfair_trades": {
        "host": "localhost",
        "port": 5432,
        "database": "betfair_trades",
        "user": "clairegrady",
        "password": "World17!"
    },
    "betfair_races": {
        "host": "localhost",
        "port": 5432,
        "database": "betfair_races",
        "user": "clairegrady",
        "password": "World17!"
    },
    "ncaa_basketball": {
        "host": "localhost",
        "port": 5432,
        "database": "ncaa_basketball",
        "user": "clairegrady",
        "password": "World17!"
    }
}

# Legacy database name mapping (for easier migration)
LEGACY_DB_MAPPING = {
    "betfairmarket.sqlite": "betfairmarket",
    "live_trades_greyhounds.db": "betfair_trades",
    "paper_trades_greyhounds.db": "betfair_trades",
    "paper_trades_horses.db": "betfair_trades",
    "race_info.db": "betfair_races",
    "ncaa_basketball.db": "ncaa_basketball"
}

logger = logging.getLogger(__name__)

def get_connection(db_name, cursor_factory=None):
    """
    Get a PostgreSQL database connection.
    
    Args:
        db_name (str): Name of the database (betfairmarket, betfair_trades, betfair_races, ncaa_basketball)
        cursor_factory: Optional cursor factory (e.g., RealDictCursor for dict results)
    
    Returns:
        psycopg2.connection: Database connection
        
    Example:
        # Regular cursor
        conn = get_connection('betfairmarket')
        
        # Dict cursor (returns rows as dictionaries)
        conn = get_connection('betfairmarket', cursor_factory=RealDictCursor)
    """
    if db_name not in PG_CONFIG:
        # Check if it's a legacy database name
        if db_name in LEGACY_DB_MAPPING:
            logger.warning(f"Using legacy database name '{db_name}', mapped to '{LEGACY_DB_MAPPING[db_name]}'")
            db_name = LEGACY_DB_MAPPING[db_name]
        else:
            raise ValueError(f"Unknown database: {db_name}. Valid databases: {list(PG_CONFIG.keys())}")
    
    try:
        if cursor_factory:
            conn = psycopg2.connect(**PG_CONFIG[db_name], cursor_factory=cursor_factory)
        else:
            conn = psycopg2.connect(**PG_CONFIG[db_name])
        logger.debug(f"Connected to PostgreSQL database: {db_name}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database {db_name}: {e}")
        raise

def get_connection_string(db_name):
    """
    Get a PostgreSQL connection string for the specified database.
    
    Args:
        db_name (str): Name of the database
        
    Returns:
        str: PostgreSQL connection string
    """
    if db_name not in PG_CONFIG:
        if db_name in LEGACY_DB_MAPPING:
            db_name = LEGACY_DB_MAPPING[db_name]
        else:
            raise ValueError(f"Unknown database: {db_name}")
    
    config = PG_CONFIG[db_name]
    return f"host={config['host']} port={config['port']} dbname={config['database']} user={config['user']} password={config['password']}"

# Test connection function
def test_connections():
    """Test all database connections"""
    for db_name in PG_CONFIG.keys():
        try:
            conn = get_connection(db_name)
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"✅ {db_name}: Connected successfully - {version[0][:50]}...")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"❌ {db_name}: Connection failed - {e}")

if __name__ == "__main__":
    # Test all connections when run directly
    print("Testing PostgreSQL connections...")
    test_connections()
