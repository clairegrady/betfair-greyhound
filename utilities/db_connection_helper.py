"""
Database Connection Helper
Provides robust SQLite connections with proper concurrency handling
"""

import sqlite3
import time
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_db_connection(db_path: str, timeout: float = 30.0) -> sqlite3.Connection:
    """
    Create a SQLite connection with proper concurrency settings.
    
    Args:
        db_path: Path to the SQLite database
        timeout: Timeout in seconds for database locks (default: 30)
    
    Returns:
        sqlite3.Connection with WAL mode and busy_timeout enabled
    """
    try:
        # Connect with timeout
        conn = sqlite3.connect(db_path, timeout=timeout)
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Set busy timeout (in milliseconds)
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
        
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn
        
    except Exception as e:
        logger.error(f"Error connecting to database {db_path}: {e}")
        raise


@contextmanager
def db_transaction(db_path: str, max_retries: int = 3, timeout: float = 30.0):
    """
    Context manager for database transactions with retry logic.
    
    Usage:
        with db_transaction('/path/to/db.sqlite') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            # Transaction commits automatically on success
            # Rolls back automatically on error
    
    Args:
        db_path: Path to the SQLite database
        max_retries: Maximum number of retry attempts
        timeout: Timeout in seconds for database locks
    """
    conn = None
    last_error = None
    
    for attempt in range(max_retries):
        try:
            conn = get_db_connection(db_path, timeout)
            conn.execute("BEGIN IMMEDIATE")  # Acquire write lock immediately
            
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
        timeout: Timeout in seconds for database locks
    
    Returns:
        Cursor with query results
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
    Convert a database from DELETE/TRUNCATE mode to WAL mode.
    
    Args:
        db_path: Path to the SQLite database
    """
    try:
        conn = sqlite3.connect(db_path)
        
        # Check current mode
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        current_mode = cursor.fetchone()[0]
        
        if current_mode.lower() != 'wal':
            logger.info(f"Converting {db_path} from {current_mode} to WAL mode...")
            cursor.execute("PRAGMA journal_mode=WAL")
            new_mode = cursor.fetchone()[0]
            logger.info(f"✅ Database converted to {new_mode} mode")
        else:
            logger.info(f"✅ Database already in WAL mode")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error converting database to WAL mode: {e}")
        raise


if __name__ == "__main__":
    # Test the helper functions
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        print(f"Converting {db_path} to WAL mode...")
        convert_database_to_wal(db_path)
    else:
        print("Usage: python db_connection_helper.py /path/to/database.db")
