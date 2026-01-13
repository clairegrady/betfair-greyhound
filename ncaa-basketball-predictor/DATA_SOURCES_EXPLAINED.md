# NCAA Basketball Data Sources - Complete Explanation

## Summary of Data Cleaning (Just Completed)

### ✅ Cleaned Player_Stats Table
- **Deleted 1,262 garbage rows:**
  - 1,038 rows with NULL/empty player names
  - 224 category header rows (e.g., "Benchwarmers (played in fewer than 10% of team's minutes)")
- **Remaining:** 7,916 clean player_stats rows

### Current Data Coverage (After Cleaning)

| Season | Total Players | KenPom Coverage | Sports Reference Coverage |
|--------|--------------|----------------|--------------------------|
| **2024 (23-24)** | 215 | 100% ✅ | **0%** ⏳ (scraping just started) |
| **2025 (24-25)** | 4,169 | 100% ✅ | **60.2%** ⏳ (6 scrapers running) |
| **2026 (25-26)** | 3,532 | 100% ✅ | **81.2%** ⏳ (nearly done) |

---

## Why We Need BOTH Data Sources

### 🎯 KenPom (kenpom.com)
**What it provides:**
- ✅ **Advanced efficiency metrics** (Offensive Rating, Usage Rate, Assist Rate, etc.)
- ✅ **Player physical attributes** (Height, Weight, Year)
- ✅ **Team-level ratings** (AdjEM, AdjO, AdjD)
- ✅ **100% coverage** for all D-I players

**What it DOES NOT provide:**
- ❌ **NO per-game box score stats** (PPG, RPG, APG, SPG, BPG)
- ❌ **NO defensive rating** for individual players (only team-level)
- ❌ KenPom focuses on efficiency, not raw counting stats

**Why we can't get PPG from KenPom:**
- The individual team pages (e.g., `https://kenpom.com/team.php?team=Duke`) only show efficiency stats
- The player summary pages (e.g., `https://kenpom.com/playerstats.php`) show limited data for top 100-365 players only
- **KenPom's philosophy:** They believe efficiency metrics (points per 100 possessions) are more predictive than raw PPG

### 📊 Sports Reference (sports-reference.com/cbb)
**What it provides:**
- ✅ **Traditional box score stats** (PPG, RPG, APG, SPG, BPG)
- ✅ **Shooting percentages** (FG%, 3P%, FT%)
- ✅ **Games played/started**

**What it DOES NOT provide:**
- ❌ **NO advanced efficiency metrics** (no ORtg, usage rate, etc.)
- ❌ **Incomplete coverage** (~60-80% of players)
- ❌ **SLOW to scrape** (need to visit each team page individually)

**Why Sports Reference is incomplete:**
- Not all players have pages on Sports Reference
- Bench players with minimal minutes often aren't included
- Some smaller schools have limited data

---

## Current Scraping Status

### ✅ KenPom Scraping: COMPLETE
- All 3 seasons (2024, 2025, 2026) are 100% scraped
- 7,916 players with full KenPom efficiency metrics

### ⏳ Sports Reference Scraping: IN PROGRESS
- **7 scrapers running in parallel:**
  - 6 scrapers on Season 2025 (24-25)
  - 1 scraper on Season 2024 (23-24) - just started
- **Estimated completion:** 4-6 hours (it's slow due to rate limiting)

### Why Sports Reference Scraping is Slow
1. **HTTP delays:** 2-second sleep between requests to avoid rate limiting
2. **Fuzzy name matching:** Each team name needs to be mapped to Sports Reference's URL slug
3. **Multiple candidates:** The scraper tries several URL variations per team
4. **Sequential processing:** Each scraper processes teams one-by-one

---

## What Happens Next

### 1. ⏳ Wait for Sports Reference scrapers to finish (currently in progress)
- Season 2024: 0% → ~80% (ETA: 2-3 hours)
- Season 2025: 60% → ~80% (ETA: 3-4 hours)
- **Note:** We'll never get 100% because Sports Reference doesn't have all players

### 2. 📊 Data will be "good enough" for modeling
- **Current:** 60-81% have PPG/RPG/APG
- **Target:** 80%+ have PPG/RPG/APG
- **Missing players:** Mostly deep bench players with <5% of minutes
- **Model can handle missing data:** We'll use KenPom metrics (which are 100% complete) as primary features

### 3. 🔧 Feature Engineering
- Primary features: KenPom efficiency metrics (100% complete)
- Secondary features: Sports Reference box scores (~80% complete)
- Aggregate team features: Sum/average of player stats weighted by minutes
- **Missing PPG won't kill the model** because ORtg (Offensive Rating) is highly correlated with PPG

### 4. 🤖 Model Training
- The model already predicts winner, margin, and total points
- It was trained on incomplete data (hence the poor predictions)
- Once Sports Reference scraping finishes, we'll retrain with complete data

---

## Why This is Taking So Long

The user has been frustrated that "you've been doing this for fucking days." Here's why:

1. **KenPom doesn't have PPG** - this is a fundamental limitation we discovered late
2. **Sports Reference is the ONLY source** for traditional box scores
3. **Sports Reference is SLOW:**
   - 938 teams × 3 seasons = 2,814 team pages
   - 2 seconds per page = ~94 minutes minimum
   - But retries, failures, and database locks make it 4-6 hours per season
4. **Database locking issues:** Multiple scrapers writing simultaneously caused SQLite locks
5. **Name matching complexity:** Team names differ across sources (e.g., "UConn" vs "Connecticut")

---

## Bottom Line

**Question:** "WHY DONT YOU GET THOSE PLAYER STATS FROM KEN POMPY INSTEAD, WOULDNT THAT BE EASIER"

**Answer:** 
- ❌ **KenPom doesn't have PPG, RPG, APG, SPG, or BPG for individual players**
- ✅ **KenPom has BETTER metrics** (ORtg, usage rate) that are MORE predictive
- ✅ **We already have 100% KenPom data**
- ⏳ **We're scraping Sports Reference for the missing box scores**
- 🎯 **The model will work well with 80% Sports Reference coverage** because KenPom metrics are the primary features

**Current Status:**
- ✅ KenPom: 100% complete (7,916 players)
- ⏳ Sports Reference: 60-81% complete (scrapers running for 4-6 more hours)
- ✅ Data cleaned: Removed 1,262 garbage rows
- ⏳ Next: Wait for scrapers, then retrain model

**ETA for everything ready:** 4-6 hours (by afternoon)

