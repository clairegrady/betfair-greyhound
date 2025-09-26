# Incremental Runner History Loader

This script efficiently loads horse racing data from CSV files into a SQLite database, only inserting new records that don't already exist.

## Features

- ✅ **Incremental Loading**: Only inserts new data, skips existing records
- ✅ **Automatic Schema Detection**: Creates database schema based on CSV columns
- ✅ **Date-based Filtering**: Uses `meetingDate` to determine what's new
- ✅ **Batch Processing**: Efficiently processes large datasets in batches
- ✅ **Error Handling**: Robust error handling and logging
- ✅ **Database Statistics**: Shows comprehensive database stats after loading

## Usage

### Basic Usage
```bash
python incremental_runner_loader.py [csv_file_path]
```

### Examples

**First time loading (loads all data):**
```bash
python incremental_runner_loader.py /path/to/Runner_Result_2025-09-21.csv
```

**Weekly update (only new data):**
```bash
python incremental_runner_loader.py /path/to/Runner_Result_2025-09-28.csv
```

**Using default CSV path:**
```bash
python incremental_runner_loader.py
```

## How It Works

1. **Connect to Database**: Creates `runner_history.sqlite` if it doesn't exist
2. **Load CSV**: Reads the CSV file and detects column structure
3. **Create Schema**: Dynamically creates database table based on CSV columns
4. **Check Last Date**: Finds the most recent date already in the database
5. **Filter New Data**: Only keeps records with dates newer than the last date
6. **Insert Data**: Efficiently inserts new records in batches of 1000
7. **Show Stats**: Displays comprehensive database statistics

## Database Schema

The script automatically creates a table with:
- **Primary Key**: `id` (auto-increment)
- **All CSV Columns**: Dynamically mapped with appropriate data types
- **Timestamps**: `created_at` for tracking when records were inserted
- **Indexes**: On `meetingDate` and `runnerName` for efficient queries

## Data Types

- **Integers**: `raceNumber`, `runnerNumber`, `finishingPosition`, all count columns
- **Reals**: `raceDistance`, `FixedWinOpen_Reference`, `FixedWinClose_Reference`
- **Text**: All other columns (names, conditions, etc.)

## Example Output

```
2025-09-25 09:35:26,849 - INFO - 📊 Database Statistics:
2025-09-25 09:35:26,849 - INFO -    Total records: 382,793
2025-09-25 09:35:26,849 - INFO -    Date range: 2023-01-11 to 2025-12-09
2025-09-25 09:35:26,849 - INFO -    Unique runners: 37,696
2025-09-25 09:35:26,849 - INFO -    Unique meetings: 3,930
```

## Weekly Workflow

1. **Get new CSV file** from your data provider
2. **Run the script**: `python incremental_runner_loader.py new_file.csv`
3. **Script automatically**:
   - Detects last date in database (e.g., 2025-12-09)
   - Only inserts records newer than that date
   - Skips any records that already exist
   - Shows you how many new records were added

## Benefits

- **Fast**: Only processes new data, not entire dataset
- **Safe**: Won't duplicate existing records
- **Efficient**: Batch processing for large datasets
- **Flexible**: Works with any CSV structure
- **Reliable**: Comprehensive error handling and logging

## Error Handling

The script handles common issues:
- Missing CSV files
- Database connection problems
- Data type conversion errors
- Duplicate record prevention
- Memory management for large files

## Requirements

- Python 3.7+
- pandas
- sqlite3 (built-in)

## Files Created

- `runner_history.sqlite`: Main database file
- Logs: Detailed logging of all operations
