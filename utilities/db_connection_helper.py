"""
Database Connection Helper
Provides robust database connections for PostgreSQL
"""

import psycopg2
import psycopg2.extras
import time
import logging
from typing import Optional
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

# Track which databases we've already logged connection for
_logged_connections = set()

# PostgreSQL Configuration
PG_CONFIG = {
    'betfairmarket': {
        'host': 'localhost',
        'port': 5432,
        'database': 'betfairmarket',
        'user': 'clairegrady',
        'password': 'World17!'
    },
    'betfair_trades': {
        'host': 'localhost',
        'port': 5432,
        'database': 'betfair_trades',
        'user': 'clairegrady',
        'password': 'World17!'
    },
    'betfair_races': {
        'host': 'localhost',
        'port': 5432,
        'database': 'betfair_races',
        'user': 'clairegrady',
        'password': 'World17!'
    },
    'ncaa_basketball': {
        'host': 'localhost',
        'port': 5432,
        'database': 'ncaa_basketball',
        'user': 'clairegrady',
        'password': 'World17!'
    }
}

# Map old SQLite paths to new PostgreSQL database names
DB_PATH_MAPPING = {
    '/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite': 'betfairmarket',
    '/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/live_trades_greyhounds.db': 'betfair_trades',
    '/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db': 'betfair_trades',
    '/Users/clairegrady/RiderProjects/betfair/databases/horses/paper_trades_horses.db': 'betfair_trades',
    '/Users/clairegrady/RiderProjects/betfair/databases/shared/race_info.db': 'betfair_races',
    '/Users/clairegrady/RiderProjects/betfair/databases/horses/race_info.db': 'betfair_races',
    'betfairmarket.sqlite': 'betfairmarket',
    'live_trades_greyhounds.db': 'betfair_trades',
    'paper_trades_greyhounds.db': 'betfair_trades',
    'paper_trades_horses.db': 'betfair_trades',
    'race_info.db': 'betfair_races',
    # Direct database names (no path)
    'betfairmarket': 'betfairmarket',
    'betfair_trades': 'betfair_trades',
    'betfair_races': 'betfair_races',
    'ncaa_basketball': 'ncaa_basketball',
}


def get_db_connection(db_path: str, timeout: float = 30.0) -> psycopg2.extensions.connection:
    """
    Create a PostgreSQL database connection.
    
    Args:
        db_path: Original SQLite path (will be mapped to PostgreSQL database)
        timeout: Timeout in seconds (used for compatibility, PostgreSQL handles timeouts differently)
    
    Returns:
        PostgreSQL connection object
    """
    # Map SQLite path to PostgreSQL database name
    db_name = DB_PATH_MAPPING.get(db_path)
    
    if not db_name:
        # Try extracting just the filename
        filename = os.path.basename(db_path)
        db_name = DB_PATH_MAPPING.get(filename)
    
    if not db_name:
        raise ValueError(f"Unknown database path: {db_path}. Cannot map to PostgreSQL database.")
    
    if db_name not in PG_CONFIG:
        raise ValueError(f"Unknown PostgreSQL database: {db_name}")
    
    try:
        conn = psycopg2.connect(**PG_CONFIG[db_name])
        conn.autocommit = False  # Require explicit commits
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL {db_name}: {e}")
        raise


@contextmanager
def db_transaction(db_path: str, max_retries: int = 3, timeout: float = 30.0):
    """
    Context manager for database transactions with retry logic.
    
    Usage:
        with db_transaction('/path/to/db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            # Transaction commits automatically on success
            # Rolls back automatically on error
    
    Args:
        db_path: Original SQLite path (will be mapped to PostgreSQL)
        max_retries: Maximum number of retry attempts
        timeout: Timeout in seconds
    """
    conn = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            conn = get_db_connection(db_path, timeout)
            
            yield conn
            
            conn.commit()
            return
            
        except psycopg2.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                    
            last_error = e
            
            if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5  # Exponential backoff
                logger.warning(f"Database deadlock, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
            
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    # If we get here, all retries failed
    raise last_error if last_error else Exception("Database transaction failed after retries")


def execute_with_retry(db_path: str, query: str, params: tuple = (), max_retries: int = 3, timeout: float = 30.0):
    """
    Execute a single query with retry logic.
    
    Args:
        db_path: Original SQLite path (will be mapped to PostgreSQL)
        query: SQL query to execute
        params: Query parameters
        max_retries: Maximum number of retry attempts
        timeout: Timeout in seconds
    
    Returns:
        Query results or None
    """
    last_error = None
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection(db_path, timeout)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            
            # Fetch results before closing
            try:
                results = cursor.fetchall()
                return results
            except:
                # Query didn't return results (INSERT, UPDATE, etc.)
                return None
                
        except psycopg2.OperationalError as e:
            last_error = e
            
            if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5
                logger.warning(f"Database deadlock, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                raise
                
        except Exception as e:
            raise
            
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    raise last_error if last_error else Exception("Query execution failed after retries")


if __name__ == "__main__":
    # Test the helper functions
    import sys
    
    print("=" * 60)
    print("DATABASE CONNECTION HELPER - PostgreSQL Mode")
    print("=" * 60)
    print()
    print("Testing PostgreSQL connections...")
    print()
    
    for db_name, config in PG_CONFIG.items():
        try:
            conn = psycopg2.connect(**config)
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✅ {db_name}: {version[:60]}...")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"❌ {db_name}: {e}")
