# 🐕 GREYHOUND RACING - DEEP DIVE ANALYSIS

## Executive Summary

**TL;DR:** You're **70-80% done**! Most infrastructure exists but is **commented out**. To get a simple "bet on fav/2nd fav to place" strategy running:

- **Minimal work:** 1-2 hours
- **With data scraper:** 4-6 hours
- **Production ready:** 8-12 hours

---

## ✅ What's Already Built (Backend)

### 1. **Database Infrastructure** ✅
- `GreyhoundMarketBook` table exists in `betfairmarket.sqlite`
- Schema includes: MarketId, MarketName, SelectionId, Status, PriceType, Price, Size, RunnerName, Venue, EventDate, EventName
- Currently **EMPTY** (0 rows) - needs to be populated

### 2. **Backend Services** ✅
All exist but are **COMMENTED OUT in Program.cs**:

```csharp
// Lines 102-121 in Program.cs are commented out:
// builder.Services.AddScoped<GreyhoundAutomationService>
// builder.Services.AddScoped<GreyhoundResultsService>
// builder.Services.AddScoped<GreyhoundMarketApiService>
```

**Services that exist:**
- ✅ `GreyhoundAutomationService.cs` - Processes market catalogues and market books
- ✅ `GreyhoundMarketApiService.cs` - Fetches data from Betfair API (event type 4339)
- ✅ `GreyhoundResultsService.cs` - Fetches settled results
- ✅ `GreyhoundStartupService.cs` - Background service (like horse racing)
- ✅ `GreyhoundBackgroundWorker.cs` - Continuous monitoring worker
- ✅ `GreyhoundOddsController.cs` - API endpoints for odds
- ✅ `GreyhoundMarketBookController.cs` - API endpoints for market data

**Key backend endpoints available:**
- `GET /api/GreyhoundMarketBook/details` - All greyhound market books
- `GET /api/GreyhoundMarketBook/odds/{selectionId}` - Back/lay odds for a dog
- `GET /api/GreyhoundMarketBook/market/{marketId}` - All odds for a market
- `GET /api/GreyhoundOdds/current/{marketId}/{selectionId}` - Current live odds

### 3. **Betfair Integration** ✅
- Configured for Australian & NZ greyhounds (`marketCountries: ["AU", "NZ"]`)
- Event Type ID: **4339** (greyhounds)
- Market types: **WIN** and **PLACE**
- Fetches data every 2 minutes (like horse racing)

---

## ❌ What's Missing

### 1. **Race Times Scraper** ❌
**Horse racing has:** `race_times_scraper.py` that scrapes racenet.com.au

**Greyhounds need:**
- Similar scraper for greyhound race times
- Sources could be:
  - https://www.racenet.com.au/greyhounds
  - https://www.tab.com.au/sports/racing/greyhounds
  - https://fasttrack.grv.org.au (Victoria)
  - https://www.gwic.nsw.gov.au (NSW)

**Database:** Can reuse `race_times.db` with `country = 'AUS_GREY'` or create `greyhound_race_times.db`

### 2. **Python Paper Trading Scripts** ❌
**Horse racing has:**
- `paper_trading.py` (PLACE betting)
- `paper_trading_win.py` (WIN + PLACE)
- `paper_trading_lay.py` (LAY all)
- `check_results.py`, `check_results_win.py`, `check_results_lay.py`

**Greyhounds need:**
- `greyhound_paper_trading.py` - Simple fav/2nd fav to PLACE strategy
- `greyhound_check_results.py` - Results checker
- New database table: `greyhound_paper_trades` (or reuse existing with `sport` column)

### 3. **Backend Services Activation** ❌
Need to **uncomment** lines 102-121 in `Program.cs` to enable greyhound services

---

## 📋 IMPLEMENTATION PLAN

### **Phase 1: Minimal Viable Product (1-2 hours)**

**Goal:** Get paper trading working WITHOUT race scraper (manually find races)

#### Step 1: Activate Backend Services (10 mins)
1. Uncomment lines 102-121 in `Program.cs`
2. Uncomment `GreyhoundStartupService` and `GreyhoundBackgroundWorker` registrations
3. Restart backend
4. Verify data is flowing into `GreyhoundMarketBook` table

#### Step 2: Create Simple Paper Trading Script (30 mins)
Copy `paper_trading.py` and adapt for greyhounds:
- **Strategy:** Bet $10 on favorite and 2nd favorite to PLACE
- **Market ID:** Manually get from `GreyhoundMarketBook` table for testing
- **Endpoint:** Use `/api/horse-racing/market-book/{marketId}` (works for all racing)
- **No scraper needed** - just test with live races

#### Step 3: Create Results Checker (20 mins)
Copy `check_results.py` and adapt:
- Query `greyhound_paper_trades` table
- Use existing `/api/results/settled` endpoint

#### Step 4: Test! (30 mins)
- Run backend
- Run paper trading script on 1-2 live greyhound races
- Check results after races complete

**At this point: You have a working greyhound paper trading system!**

---

### **Phase 2: Add Race Scraper (2-3 hours additional)**

#### Step 1: Build Greyhound Scraper (2 hours)
Copy `race_times_scraper.py` and adapt:
- Target: https://www.racenet.com.au/greyhounds or similar
- Extract: venue, race_number, race_time, race_date
- Save to: `race_times.db` with `country = 'AUS_GREY'`
- **Challenges:**
  - Different HTML structure than horse racing
  - May need different CSS selectors
  - Greyhound venues are different (tracks vs TABtouch venues)

#### Step 2: Update Paper Trading to Use Scraper (30 mins)
- Modify `get_upcoming_races()` to query greyhound races
- Match with `GreyhoundMarketBook` / `MarketCatalogue` tables
- **Challenge:** Venue name matching (e.g., "The Meadows" vs "Meadows")

#### Step 3: Schedule Scraper (10 mins)
- Add cron job or systemd timer
- Run every hour or before major race times

**At this point: Fully automated greyhound paper trading!**

---

### **Phase 3: Production Ready (2-3 hours additional)**

#### Additional work:
1. **Error handling** - Retry logic, logging, alerts
2. **Database indices** - Speed up queries
3. **Multiple strategies** - Test different odds ranges
4. **Historical analysis** - Scrape past results to find edges
5. **Monitoring** - Dashboard, alerts, performance tracking
6. **Backfilling** - Get historical greyhound data from Betfair

---

## 🎯 SIMPLE "FAV/2ND FAV TO PLACE" STRATEGY

### Database Schema

```sql
CREATE TABLE greyhound_paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_type TEXT NOT NULL,  -- 'PLACE'
    market_id TEXT NOT NULL,
    selection_id INTEGER NOT NULL,
    dog_name TEXT,
    race_time TEXT,
    track TEXT,
    venue TEXT,
    race_number INTEGER,
    odds_taken REAL NOT NULL,
    bsp_odds REAL,
    stake REAL NOT NULL,  -- $10 flat
    result TEXT DEFAULT 'PENDING',
    profit_loss REAL,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    notes TEXT
);
```

### Python Script Logic

```python
# 1. Get upcoming greyhound races (from scraper or manual)
upcoming_races = get_greyhound_races()

# 2. For each race starting in next 2 minutes:
for race in upcoming_races:
    # 3. Get current odds from backend
    odds_map = get_greyhound_odds(race['market_id'])
    
    # 4. Sort by odds (lowest = favorite)
    sorted_dogs = sorted(odds_map.items(), key=lambda x: x[1])
    
    # 5. Get fav and 2nd fav
    fav = sorted_dogs[0]
    second_fav = sorted_dogs[1]
    
    # 6. Place $10 PLACE bet on each
    place_bet(fav, stake=10, bet_type='PLACE')
    place_bet(second_fav, stake=10, bet_type='PLACE')
```

**Total stake per race:** $20
**Expected:** Similar to horse racing - favorites have good place rates

---

## 💰 EFFORT vs VALUE ANALYSIS

### Option A: MINIMAL (1-2 hours)
**What you get:**
- Working paper trading system
- Manual race selection
- Basic results tracking

**Limitations:**
- Must manually find upcoming races
- No automation
- Can only test a few races per day

**Value:** ⭐⭐⭐ Good for testing strategy viability

---

### Option B: WITH SCRAPER (4-6 hours)
**What you get:**
- Fully automated system
- Runs 24/7 on all Australian greyhound races
- Proper race time matching
- Database of results

**Limitations:**
- Scraper may break if website changes
- Limited to scraper's coverage

**Value:** ⭐⭐⭐⭐⭐ Full production system

---

### Option C: PRODUCTION (8-12 hours)
**What you get:**
- Everything from Option B
- Robust error handling
- Multiple strategies
- Historical analysis
- Performance monitoring

**Value:** ⭐⭐⭐⭐ Professional system, but diminishing returns

---

## 🔧 TECHNICAL COMPARISON: HORSES vs GREYHOUNDS

| Feature | Horse Racing | Greyhounds | Notes |
|---------|-------------|------------|-------|
| **Backend services** | ✅ Active | ⚠️ Commented out | Just uncomment |
| **Database table** | ✅ HorseMarketBook | ✅ GreyhoundMarketBook | Already exists |
| **Race scraper** | ✅ Working | ❌ Need to build | 2-3 hours work |
| **Paper trading** | ✅ 3 strategies | ❌ Need to build | 1-2 hours work |
| **Results checker** | ✅ Working | ❌ Need to build | 30 mins work |
| **Betfair event type** | 7 (horse racing) | 4339 (greyhounds) | Already configured |
| **Market types** | WIN, PLACE | WIN, PLACE | Same |
| **API endpoints** | ✅ Working | ✅ Working | Reusable |

---

## 🚀 RECOMMENDED APPROACH

### **Start with Option A (Minimal)**

**Why:**
1. **Test the waters** - See if greyhounds are even profitable
2. **Minimal time investment** - 1-2 hours vs 4-6 hours
3. **Learn the domain** - Understand greyhound racing differences
4. **Validate strategy** - Test fav/2nd fav approach with real data

**How to start:**
1. Uncomment greyhound services in `Program.cs`
2. Restart backend and verify data flows
3. Copy `paper_trading_win.py` → `greyhound_paper_trading.py`
4. Adapt for greyhounds (use `GreyhoundMarketBook` table)
5. Manually get 1-2 market IDs from database
6. Run script and place bets
7. Check results after races

**Decision point after 1 week:**
- ✅ **If profitable:** Build Option B (scraper + automation)
- ❌ **If not:** Save 4-6 hours and focus on horse racing

---

## 📊 DATA AVAILABILITY

### **Do you have greyhound data?**

**Betfair Historical Data:**
- ✅ Available through same Betfair Historical Data API
- ✅ Event type 4339 (greyhounds)
- ✅ Australian markets well covered
- ✅ BSP (Betfair Starting Price) data available

**What you DON'T have yet:**
- ❌ Greyhound race form data (equivalent to horse racing form)
- ❌ Track conditions
- ❌ Dog statistics (wins, places, recent form)
- ❌ Trainer/kennel data

**Can you get it?**
- ✅ **Yes** - Similar scraping approach to horse racing
- ✅ Sources: GRV (Victoria), GWIC (NSW), Racing NSW
- ⏰ **Effort:** 4-8 hours to build comprehensive scraper

**For simple fav/2nd fav strategy:**
- ✅ **No form data needed!** Just need current odds
- ✅ Betfair odds alone are sufficient
- ✅ Can start immediately with Option A

---

## 🎯 MY RECOMMENDATION

### **START NOW with Option A - Here's why:**

1. **You already have 70-80% of infrastructure**
2. **1-2 hours to test viability** vs committing 6+ hours
3. **Greyhound markets are different** - need to validate edge exists
4. **Horse racing is working** - don't want to distract from profitable system
5. **Easy to scale up** - If it works, add scraper later

### **Action Plan:**

**Today (1-2 hours):**
1. ✅ Uncomment greyhound services in backend
2. ✅ Restart backend, verify data collection
3. ✅ Create `greyhound_paper_trading.py` (copy from horse racing)
4. ✅ Test on 2-3 live races manually

**This Week (as races happen):**
- ✅ Collect 20-30 race results
- ✅ Analyze profitability
- ✅ Compare to horse racing ROI

**Decision Point (1 week from now):**
- **If profitable:** Invest 4-6 hours to build scraper and automate
- **If break-even/unprofitable:** Skip greyhounds, focus on optimizing horse racing

---

## 💡 QUESTIONS TO CONSIDER

1. **Do greyhounds have similar favorite bias as horses?**
   - Horses: 74.4% place rate for 1.4-1.5 odds
   - Greyhounds: Unknown (need to test)

2. **Are greyhound markets as liquid as horses?**
   - May have wider spreads
   - May have less volume
   - Need to verify with live data

3. **How many races per day?**
   - Horses: ~100-200 Australian races/day
   - Greyhounds: ~??? (need to check)

4. **Is the effort worth it?**
   - If horse racing is already profitable
   - Maybe better to optimize existing system?
   - Or is diversification valuable?

---

## 📁 FILES TO CREATE

**Minimal (Option A):**
1. `greyhound_paper_trading.py` - Main betting script
2. `greyhound_check_results.py` - Results checker
3. Update `Program.cs` - Uncomment services

**With Scraper (Option B):**
4. `greyhound_race_scraper.py` - Scrape race times
5. `greyhound_race_times.db` - Race schedule database

**Production (Option C):**
6. `greyhound_analysis.py` - Performance analytics
7. `greyhound_backtest.py` - Historical backtesting
8. `GREYHOUND_STRATEGY.md` - Strategy documentation

---

## ⏱️ TIME ESTIMATE BREAKDOWN

### Option A: Minimal (1-2 hours)
- Backend activation: 10 mins
- Create paper trading script: 30 mins
- Create results checker: 20 mins
- Testing and debugging: 30 mins
- **TOTAL: 1.5 hours**

### Option B: With Scraper (+2-3 hours)
- Research scraping sources: 30 mins
- Build scraper: 1.5 hours
- Integration and testing: 1 hour
- **TOTAL: 3-4 hours** (4.5-5.5 hours cumulative)

### Option C: Production (+2-3 hours)
- Error handling and logging: 1 hour
- Historical data collection: 1 hour
- Monitoring and analysis: 1 hour
- **TOTAL: 3 hours** (7.5-8.5 hours cumulative)

---

## 🏁 CONCLUSION

**You're in a great position!** Most of the hard work is done. The backend infrastructure is solid and just needs to be activated.

**My strong recommendation:**
1. **Start with Option A (1-2 hours)** - Test viability
2. **Collect data for 1 week**
3. **Analyze profitability**
4. **Decide whether to invest in Option B**

**Risk:** Low (1-2 hours)
**Reward:** High (if greyhounds are as profitable as horses, you've doubled your bet flow)
**Effort:** Minimal (70-80% already built)

**Want me to implement Option A right now?** I can have you up and running in 1-2 hours. 🚀
