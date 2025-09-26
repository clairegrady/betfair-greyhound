# Odds Scrapers README

This directory contains two odds scraping scripts for Australian horse racing:

## Scripts Overview

### 1. `ultimate_odds_scraper.py` - Comprehensive Scraper
**Purpose**: Scrapes odds for ALL races happening today across multiple venues.

**Usage**:
```bash
python ultimate_odds_scraper.py
```

**What it does**:
- Scrapes all AU/NZ venues for today's races
- Gets odds from 13+ bookmakers for each race
- Stores data in `scraped_odds` table
- Runs automatically without parameters

**Best for**: Daily automated scraping of all races

### 2. `specific_race_odds_scraper.py` - Targeted Scraper
**Purpose**: Scrapes odds for a SPECIFIC race by venue and race number.

**Usage**:
```bash
# Scrape today's race
python specific_race_odds_scraper.py --venue "Hawkesbury" --race 8

# Scrape specific date
python specific_race_odds_scraper.py --venue "Flemington" --race 1 --date "2025-09-25"
```

**Parameters**:
- `--venue`: Venue name (e.g., "Hawkesbury", "Flemington", "Perth")
- `--race`: Race number (e.g., 8)
- `--date`: Date in YYYY-MM-DD format (optional, defaults to today)

**Best for**: Getting fresh odds for a specific race you're interested in

## Database Schema

Both scripts store data in the `scraped_odds` table:

```sql
CREATE TABLE scraped_odds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    race_number INTEGER NOT NULL,
    race_time TEXT,
    race_date TEXT,
    horse_name TEXT NOT NULL,
    horse_number INTEGER,
    bookmaker TEXT NOT NULL,
    odds REAL NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(venue, race_number, horse_name, bookmaker, race_date)
);
```

## Supported Venues

The scrapers work with these AU/NZ venues:
- Flemington, Hawkesbury, Perth
- Devonport Synthetic, Sunshine Coast, Kalgoorlie
- Nowra, Mount Gambier, Gore, Te Aroha
- Alice Springs, Grafton, Narromine, Warrnambool
- Emerald, Leeton, Moe, Taree, Gatton
- Geelong, Goulburn, and more...

## Bookmakers Covered

The scripts extract odds from 13+ bookmakers:
- **Betfair** (Back and Lay)
- **Sportsbet, Ladbrokes, TAB**
- **Betr, ColossalBet, Unibet**
- **Pointsbet, Neds, Bet365**
- **BetRight, Palmerbet, BetDeluxe**
- And more...

## Example Output

```
2025-09-25 12:30:15 - INFO - Scraping Hawkesbury Race 8...
2025-09-25 12:30:20 - INFO - Found race numbers: ['1', '2', '3', '4', '5', '6', '7', '8', '9']
2025-09-25 12:30:25 - INFO - Extracted 8 runners with odds for Hawkesbury Race 8
2025-09-25 12:30:25 - INFO - ✅ Successfully scraped Hawkesbury Race 8
2025-09-25 12:30:25 - INFO - 📊 Found 8 horses with odds
2025-09-25 12:30:25 - INFO -   🐎 Horse Name 1: 13 odds, avg: 3.45
2025-09-25 12:30:25 - INFO -   🐎 Horse Name 2: 13 odds, avg: 5.67
```

## Prerequisites

1. **Chrome Driver**: Must be installed and in PATH
2. **Python Dependencies**:
   ```bash
   pip install selenium beautifulsoup4 pandas sqlite3
   ```
3. **Database**: `live_betting.sqlite` must exist
4. **Race Times**: `race_times` table must be populated

## Troubleshooting

### Common Issues:

1. **"No races found"**: Check if `race_times` table has data for today
2. **"Page error"**: Venue might not have races today, try different venue
3. **"Click intercepted"**: Script has retry logic, should work automatically
4. **"No odds found"**: Race might not have started yet, try closer to race time

### Debug Mode:
Add `--verbose` flag to see more detailed logging (if supported)

## Integration with Other Scripts

The scraped data can be used by:
- `scraped_odds_lay_betting.py` - For lay betting strategies
- `specific_race_lay_betting.py` - For targeted lay betting
- Any analysis scripts that need odds data

## Data Quality

- **Odds Range**: 1.01 to 1000 (filters out invalid data)
- **Bookmaker Validation**: Removes duplicates and invalid entries
- **Horse Name Matching**: Handles various name formats
- **Time Accuracy**: Uses actual race times from database

## Performance

- **Comprehensive Scraper**: ~2-3 minutes per venue
- **Specific Race Scraper**: ~30-60 seconds per race
- **Headless Mode**: Runs in background without browser window
- **Anti-Detection**: Uses advanced techniques to avoid blocking

## Maintenance

- Scripts automatically clean up yesterday's data
- Handles website changes with robust error handling
- Updates bookmaker names as they change
- Maintains compatibility with Punters.com.au updates
