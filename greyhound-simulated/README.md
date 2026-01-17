# 🐕 Greyhound Racing Paper Trading System

Production-ready greyhound racing paper trading system with comprehensive monitoring, analysis, and error handling.

---

## 📊 System Overview

**Strategy:** Bet $10 on favorite and 2nd favorite to PLACE
- **Total stake per race:** $20
- **Markets:** Australian greyhound PLACE markets only
- **Betting window:** 2 minutes before race start
- **Data source:** Betfair API (Event Type 4339)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GREYHOUND TRADING SYSTEM                  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌────────────────┐    ┌──────────────────┐
│ Race Scraper  │    │ Paper Trading  │    │ Results Checker  │
│               │    │                │    │                  │
│ • TAB API     │───▶│ • Live odds    │───▶│ • Settle bets    │
│ • Racenet     │    │ • Place bets   │    │ • Calculate P&L  │
│ • Saves to DB │    │ • 2 bets/race  │    │ • Update DB      │
└───────────────┘    └────────────────┘    └──────────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │   Analysis Tool  │
                    │                  │
                    │ • Performance    │
                    │ • Trends         │
                    │ • Insights       │
                    └──────────────────┘
```

---

## 📁 File Structure

```
greyhound-predictor/
├── greyhound_race_scraper.py      # Scrapes race times from TAB/Racenet
├── greyhound_paper_trading.py     # Main betting script
├── greyhound_check_results.py     # Results checker and settler
├── greyhound_analysis.py          # Performance analytics
├── README.md                       # This file
├── greyhound_paper_trading.log    # Trading logs
└── greyhound_results.log          # Results logs

Databases:
├── paper_trades.db                # Betting records (greyhound_paper_trades table)
└── race_times.db                  # Race schedule (country='AUS_GREY')
```

---

## 🚀 Quick Start

### 1. Activate Backend (if not running)

The greyhound services are already registered in the backend. Just ensure the backend is running:

```bash
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet run
```

Verify greyhound data is flowing:
```bash
sqlite3 betfairmarket.sqlite "SELECT COUNT(*) FROM GreyhoundMarketBook"
```

### 2. Scrape Today's Races

```bash
cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor
python3 greyhound_race_scraper.py
```

This will:
- Scrape TAB and Racenet for greyhound races
- Save to `race_times.db` with `country='AUS_GREY'`
- Show summary of races found

### 3. Start Paper Trading

```bash
python3 greyhound_paper_trading.py
```

This will:
- Monitor upcoming races
- Place $10 bets on favorite and 2nd favorite (PLACE)
- Log all activity to `greyhound_paper_trading.log`
- Run until interrupted (Ctrl+C)

### 4. Check Results (after races finish)

```bash
python3 greyhound_check_results.py
```

This will:
- Find all unsettled bets
- Fetch results from Betfair
- Calculate P&L
- Update database
- Show summary statistics

### 5. Analyze Performance

```bash
python3 greyhound_analysis.py
```

This will show:
- Overall statistics (ROI, win rate, profit factor)
- Performance by odds range
- Performance by venue
- Favorite vs 2nd favorite comparison
- Daily performance trends
- Best and worst bets

---

## ⚙️ Configuration

### In `greyhound_paper_trading.py`:

```python
FLAT_STAKE = 10                # Stake per dog ($10)
MINUTES_BEFORE_RACE = 2        # Betting window (2 mins)
MAX_RETRIES = 3                # API retry attempts
RETRY_DELAY = 2                # Seconds between retries
```

### In `greyhound_race_scraper.py`:

```python
# Venue name mappings (standardize to Betfair names)
self.venue_mappings = {
    'the meadows': 'The Meadows',
    'sandown park': 'Sandown Park',
    # ... add more as needed
}
```

---

## 📊 Database Schema

### `greyhound_paper_trades` table:

```sql
CREATE TABLE greyhound_paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_type TEXT NOT NULL,           -- 'PLACE'
    market_id TEXT NOT NULL,
    selection_id INTEGER NOT NULL,
    dog_name TEXT,
    race_time TEXT,
    track TEXT,
    venue TEXT,
    race_number INTEGER,
    odds_taken REAL NOT NULL,
    bsp_odds REAL,                    -- Betfair Starting Price
    stake REAL NOT NULL,              -- $10 flat
    result TEXT DEFAULT 'PENDING',    -- PENDING/WON/LOST
    profit_loss REAL,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    notes TEXT,
    strategy TEXT DEFAULT 'fav_2nd_fav_place'
);
```

### `race_times` table (shared with horse racing):

```sql
CREATE TABLE race_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    race_number INTEGER NOT NULL,
    race_time TEXT NOT NULL,
    race_time_utc TEXT NOT NULL,
    race_date TEXT NOT NULL,
    timezone TEXT NOT NULL,
    country TEXT,                     -- 'AUS_GREY' for greyhounds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(venue, race_number, race_date, country)
);
```

---

## 🔧 Production Features

### Error Handling
- ✅ Comprehensive try-catch blocks
- ✅ Retry logic for API calls (3 attempts with delays)
- ✅ Graceful degradation (continues on single race failure)
- ✅ Detailed error logging with stack traces

### Logging
- ✅ Dual logging (file + console)
- ✅ Separate logs for trading and results
- ✅ Timestamped entries
- ✅ Log levels (INFO, WARNING, ERROR, DEBUG)

### Monitoring
- ✅ Real-time performance tracking
- ✅ Cumulative P&L calculations
- ✅ Win rate monitoring
- ✅ Venue-specific analytics
- ✅ Odds range analysis

### Data Integrity
- ✅ Database constraints (UNIQUE keys)
- ✅ Transaction management (commit/rollback)
- ✅ Timestamp tracking (placed_at, settled_at)
- ✅ BSP recording for actual odds

---

## 📈 Performance Tracking

### Key Metrics Tracked:

1. **Overall Performance**
   - Total bets, wins, losses
   - Win rate, ROI, profit factor
   - Average win/loss amounts
   - Cumulative P&L over time

2. **By Odds Range**
   - Performance for <1.5, 1.5-2.0, 2.0-2.5, 2.5-3.0, 3.0-5.0, 5.0+
   - Identifies optimal betting ranges

3. **By Venue**
   - Track-specific performance
   - Identifies profitable/unprofitable venues

4. **By Position**
   - Favorite vs 2nd favorite comparison
   - Shows which position is more profitable

5. **Daily Trends**
   - Day-by-day breakdown
   - Cumulative P&L progression
   - Identifies winning/losing days

---

## 🛠️ Troubleshooting

### No races found in scraper:

**Problem:** `greyhound_race_scraper.py` returns 0 races

**Solutions:**
1. Check if TAB API is responding:
   ```bash
   curl "https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/today?jurisdiction=NSW"
   ```

2. Try different jurisdiction: NSW, VIC, QLD, SA, WA
3. Check if greyhound racing is on today
4. Fallback: Manually add races to `race_times.db`

### Backend not collecting greyhound data:

**Problem:** `GreyhoundMarketBook` table is empty

**Solutions:**
1. Check backend logs for errors
2. Verify `GreyhoundBackgroundWorker` is running:
   ```bash
   grep "GreyhoundBackgroundWorker" backend_log.txt
   ```
3. Check if markets exist in `MarketCatalogue` table:
   ```sql
   SELECT * FROM MarketCatalogue WHERE EventType LIKE '%Greyhound%';
   ```

### Paper trading not placing bets:

**Problem:** Script runs but places 0 bets

**Solutions:**
1. Check if races are in database:
   ```sql
   SELECT * FROM race_times WHERE country='AUS_GREY' AND date(race_date) = date('now');
   ```

2. Check if markets are matched:
   ```sql
   SELECT * FROM MarketCatalogue WHERE EventName LIKE '%greyhound%';
   ```

3. Verify backend is running and accessible:
   ```bash
   curl http://localhost:5173/api/horse-racing/market-book/1.123456789
   ```

4. Check logs for errors:
   ```bash
   tail -f greyhound_paper_trading.log
   ```

### Results not settling:

**Problem:** `greyhound_check_results.py` shows "NOT SETTLED YET"

**Solutions:**
1. Wait longer (markets take 5-10 mins to settle after race)
2. Check if backend can fetch results:
   ```bash
   curl -X POST http://localhost:5173/api/results/settled \
     -H "Content-Type: application/json" \
     -d '{"marketIds":["1.123456789"]}'
   ```

3. Manually check Betfair website for market status

---

## 🔍 Monitoring Commands

### Check recent bets:
```sql
sqlite3 paper_trades.db "
SELECT dog_name, venue, odds_taken, result, profit_loss 
FROM greyhound_paper_trades 
ORDER BY placed_at DESC 
LIMIT 10
"
```

### Check today's performance:
```sql
sqlite3 paper_trades.db "
SELECT 
  COUNT(*) as bets,
  SUM(CASE WHEN result='WON' THEN 1 ELSE 0 END) as wins,
  SUM(profit_loss) as pnl
FROM greyhound_paper_trades
WHERE date(placed_at) = date('now')
AND result != 'PENDING'
"
```

### Check pending bets:
```sql
sqlite3 paper_trades.db "
SELECT dog_name, venue, race_time, odds_taken
FROM greyhound_paper_trades
WHERE result='PENDING'
ORDER BY placed_at
"
```

---

## 📅 Automation

### Cron Jobs (optional):

```bash
# Scrape races every 4 hours
0 */4 * * * cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor && python3 greyhound_race_scraper.py

# Check results every hour
0 * * * * cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor && python3 greyhound_check_results.py

# Daily analysis report at 11 PM
0 23 * * * cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor && python3 greyhound_analysis.py > daily_report.txt
```

### Systemd Service (Linux):

```ini
[Unit]
Description=Greyhound Paper Trading
After=network.target

[Service]
Type=simple
User=clairegrady
WorkingDirectory=/Users/clairegrady/RiderProjects/betfair/greyhound-predictor
ExecStart=/usr/bin/python3 greyhound_paper_trading.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 🎯 Strategy Notes

### Why Favorite + 2nd Favorite?

1. **High Place Rates:** Top 2 dogs have ~70-80% combined place rate
2. **Diversification:** 2 bets per race spreads risk
3. **Simple:** No complex analysis needed, just market odds
4. **Liquid:** Top 2 always have good liquidity

### Expected Performance:

Based on horse racing similar strategy:
- **Win Rate:** ~50-60% (at least one of two places)
- **ROI:** Target 2-5%
- **Variance:** Moderate (2 bets reduces variance vs single bet)

### Risk Management:

- **Fixed stakes:** $10 per bet prevents over-betting
- **PLACE only:** Lower variance than WIN betting
- **2-minute window:** Ensures stable odds before race
- **Favorites only:** Avoids longshots with high variance

---

## 📊 Sample Output

### Paper Trading:
```
🐕 GREYHOUND PAPER TRADING SYSTEM
══════════════════════════════════════════════════════════════════════

Config:
   Strategy: Bet on favorite and 2nd favorite
   Bet type: PLACE only
   Stake: $10 per dog ($20 per race)
   Betting window: Within 2 mins of race

══════════════════════════════════════════════════════════════════════
🎯 The Meadows - Race 5
   Race time: 2026-01-08T19:30:00
   Time until race: 1.8 mins
══════════════════════════════════════════════════════════════════════

✅ BETTING ON TOP 2:
   1st: Swift Thunder @ 1.85
   2nd: Lightning Bolt @ 2.40
   Total stake: $20

💾 Bet recorded (ID: 1)
💾 Bet recorded (ID: 2)
✅ Both bets placed successfully!
```

### Results:
```
🐕 CHECKING GREYHOUND PAPER TRADING RESULTS
══════════════════════════════════════════════════════════════════════

🏁 Race: The Meadows - Race 5
   🏆 Winners: Swift Thunder
   🎯 Placed: Swift Thunder, Lightning Bolt, Quick Fox

   ✅ Swift Thunder (PLACE): WON $8.50 @ BSP 1.85
   ✅ Lightning Bolt (PLACE): WON $14.00 @ BSP 2.40

══════════════════════════════════════════════════════════════════════
📊 RESULTS SUMMARY
══════════════════════════════════════════════════════════════════════
   Bets Settled: 2
   Wins: 2
   Losses: 0
   Win Rate: 100.0%
   Total P&L: $+22.50
   ROI: +112.5%
══════════════════════════════════════════════════════════════════════
```

---

## 🆚 Comparison to Horse Racing

| Feature | Horse Racing | Greyhounds |
|---------|-------------|------------|
| **Races per day** | ~100-200 | ~50-100 |
| **Race duration** | ~1-3 mins | ~30 secs |
| **Field size** | 8-16 horses | 6-8 dogs |
| **Place positions** | Top 3 (usually) | Top 3 |
| **Favorites place rate** | ~74% (1.4-1.5 odds) | Unknown (testing) |
| **Market liquidity** | High | Medium |
| **Form data available** | Extensive | Limited |

---

## 🎓 Next Steps

1. **Collect 1 week of data** - Test strategy viability
2. **Analyze results** - Compare to horse racing
3. **Optimize odds ranges** - Find profitable ranges
4. **Test different strategies** - WIN betting, laying, etc.
5. **Add more venues** - Expand beyond main tracks
6. **Historical backtesting** - Get Betfair historical data

---

## 📞 Support

Check logs first:
```bash
tail -f greyhound_paper_trading.log
tail -f greyhound_results.log
```

Common issues are documented in the Troubleshooting section above.

---

## ✅ System Status Checklist

Before running, verify:
- [ ] Backend is running (`dotnet run`)
- [ ] `GreyhoundMarketBook` has data
- [ ] Race scraper has run today
- [ ] `race_times.db` has `AUS_GREY` races
- [ ] Database tables exist
- [ ] Log files are writable

---

**Built with ❤️ for systematic greyhound betting**

🐕 Happy betting! 🐕
