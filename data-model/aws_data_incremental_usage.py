#!/usr/bin/env python3
"""
Example usage of the incremental runner loader

This script demonstrates how to use the incremental_runner_loader.py
for weekly data updates.
"""

from incremental_runner_loader import IncrementalRunnerLoader
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Example usage of the incremental loader"""
    
    # Create loader instance
    loader = IncrementalRunnerLoader("runner_history.sqlite")
    
    # Example 1: Load initial data (first time)
    logger.info("=== Example 1: Initial Load ===")
    csv_path = "/Users/clairegrady/RiderProjects/betfair/data-model/data-analysis/Runner_Result_2025-09-21.csv"
    loader.load_incremental_data(csv_path)
    
    # Example 2: Load the same data again (should detect no new data)
    logger.info("\n=== Example 2: Same Data (No New Records) ===")
    loader.load_incremental_data(csv_path)
    
    # Example 3: How to use with a new CSV file
    logger.info("\n=== Example 3: Future Weekly Update ===")
    logger.info("When you get a new CSV file next week, just run:")
    logger.info("python incremental_runner_loader.py /path/to/new_csv_file.csv")
    logger.info("The script will automatically:")
    logger.info("- Detect the last date in the database")
    logger.info("- Only insert records newer than that date")
    logger.info("- Skip records that already exist")

if __name__ == "__main__":
    main()
