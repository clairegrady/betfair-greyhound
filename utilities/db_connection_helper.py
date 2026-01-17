"""
Database Connection Helper
Provides robust database connections for SQLite
PostgreSQL implementation commented out for future use
"""

import sqlite3
import time
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ============================================================================
# POSTGRESQL IMPLEMENTATION (COMMENTED OUT FOR FUTURE USE)
# ============================================================================
# import psycopg2
# import psycopg2.extras
# import psycopg2.pool
#
# PG_CONFIG = {
#     'betfairmarket': {
#         'host': 'localhost',
#         'port': 5432,
#         'database': 'betfairmarket',
#         'user': 'clairegrady'
#     },
#     'betfair_trades': {
#         'host': 'localhost',
#         'port': 5432,
#         'database': 'betfair_trades',
#         'user': 'clairegrady'
#     },
#     'betfair_races': {
#         'host': 'localhost',
#         'port': 5432,
#         'database': 'betfair_races',
#         'user': 'clairegrady'
#     }
# }
#
# DB_PATH_MAPPING = {
#     'betfairmarket.sqlite': 'betfairmarket',
#     'live_trades_greyhounds.db': 'betfair_trades',
#     'paper_trades_greyhounds.db': 'betfair_trades',
#     'paper_trades_horses.db': 'betfair_trades',
#     'race_info.db': 'betfair_races',
#     'paper_trades_ncaa.db': 'betfairmarket',
# }
# ============================================================================


def get_db_connection(db_path: str, timeout: float = 30.0) -> sqlite3.Connection:
    """
    Create a SQLite database connection with optimizations.
    
    Args:
        db_path: Path to the SQLite database file
        timeout: Timeout in seconds
    
    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
    
    # SQLite optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=60000;")
    conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
    
    logger.debug(f"Connected to SQLite database: {db_path}")
    return conn


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
        db_path: Path to the SQLite database
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
            
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                    
            last_error = e
            
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5  # Exponential backoff
                logger.warning(f"Database locked, retry {attempt + 1}/{max_retries} in {wait_time}s...")
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
        db_path: Path to the SQLite database
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
                
        except sqlite3.OperationalError as e:
            last_error = e
            
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5
                logger.warning(f"Database locked, retry {attempt + 1}/{max_retries} in {wait_time}s...")
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


def convert_database_to_wal(db_path: str):
    """
    Convert a SQLite database to WAL mode for better concurrency.
    
    Args:
        db_path: Path to the SQLite database file
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()
        logger.info(f"Converted {db_path} to WAL mode")
    except Exception as e:
        logger.error(f"Error converting {db_path} to WAL: {e}")


if __name__ == "__main__":
    # Test the helper functions
    import sys
    
    print("=" * 60)
    print("DATABASE CONNECTION HELPER - SQLite Mode")
    print("=" * 60)
    print()
    print("Using SQLite with WAL mode for improved concurrency")
    print("PostgreSQL implementation available but commented out")
