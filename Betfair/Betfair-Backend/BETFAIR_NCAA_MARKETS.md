# 🏀 NCAA Basketball Betfair Market Integration - COMPLETE

**Created:** December 29, 2025
**Status:** ✅ IMPLEMENTED

## Overview

This document outlines the **critical missing component** that has been added: **Betfair NCAA Basketball market collection** for actual betting.

Previously, the system was ONLY pulling:
- ✅ The Odds API (for general market odds)
- ✅ ESPN API (for historical games/scores)
- ❌ **Betfair API (MISSING - THIS IS WHERE WE BET!)**

## What Was Added

### 1. **New Background Service: `NcaaBasketballMarketWorker`**
**File:** `Betfair/Betfair-Backend/AutomatedServices/NcaaBasketballMarketWorker.cs`

- **Purpose:** Continuously fetch NCAA Basketball markets from Betfair (similar to horse racing `MarketBackgroundWorker`)
- **Event Type ID:** 7522 (Basketball on Betfair)
- **Cycle Frequency:** Every 5 minutes
- **Startup Delay:** 20 seconds (after horse racing services)

**Key Features:**
- Fetches all NCAA Basketball markets from Betfair
- Processes Match Odds / Moneyline markets (primary betting markets)
- Stores market catalogues and market books (odds) in Betfair database
- Handles errors gracefully with retries

### 2. **New API Method: `ListBasketballMarketCatalogueAsync`**
**File:** `Betfair/Betfair-Backend/Services/MarketApiService.cs`

```csharp
public async Task<string> ListBasketballMarketCatalogueAsync(string? competitionId = null, string? eventId = null)
```

**Purpose:** Dedicated Betfair API call for basketball markets

**Filters:**
- **Event Type:** 7522 (Basketball)
- **Market Types:** MATCH_ODDS, HANDICAP, TOTAL_POINTS
- **Market Statuses:** OPEN, ACTIVE, SUSPENDED
- **Time Range:** Yesterday to next 7 days (captures live + upcoming games)
- **Max Results:** 200 markets

### 3. **New Automation Method: `ProcessNcaaBasketballMarketCataloguesAsync`**
**File:** `Betfair/Betfair-Backend/AutomationServices/MarketAutomationService.cs`

```csharp
public async Task<List<MarketDetails>> ProcessNcaaBasketballMarketCataloguesAsync(
    string competitionId = null, 
    string eventId = null)
```

**Purpose:** Process and store NCAA Basketball market catalogues

**Key Features:**
- Deserializes Betfair market catalogues
- Filters for Match Odds / Moneyline markets (primary for predictions)
- Stores market details in database
- Returns list of market IDs for subsequent odds fetching

### 4. **Program.cs Registration**
**File:** `Betfair/Betfair-Backend/Program.cs`

Added:
```csharp
builder.Services.AddHostedService<NcaaBasketballMarketWorker>();
```

## Data Flow

### Betfair NCAA Basketball Market Collection Flow

```
NcaaBasketballMarketWorker (Every 5 mins)
    ↓
MarketAutomationService.ProcessNcaaBasketballMarketCataloguesAsync()
    ↓
MarketApiService.ListBasketballMarketCatalogueAsync()
    ↓
Betfair API (Event Type 7522 - Basketball)
    ↓
Filter for NCAA competitions
    ↓
Store in Betfair database:
    - list_market_catalogue table (market details)
    - market_books table (odds/runners)
```

## Integration with Existing System

### How It Works With Paper Trading

1. **Game Identification:**
   - `NcaaBasketballBackgroundService` pulls upcoming games from The Odds API → stores in `ncaa_basketball.db`
   - `NcaaBasketballMarketWorker` pulls NCAA Basketball markets from Betfair → stores in Betfair DB

2. **Market Matching:**
   - Need to match Betfair markets (by event name) to our NCAA games in `ncaa_basketball.db`
   - Betfair event names format: "Team A v Team B"
   - Our DB format: separate `home_team_name`, `away_team_name`

3. **Betting Execution:**
   - Paper trading script (`paper_trading.py`) finds games with high prediction confidence
   - **NEW:** Look up corresponding Betfair market using team names
   - Place bets on Betfair using market IDs from the `list_market_catalogue` table

## Database Schema

### Betfair Database Tables (Already Exist)

**`list_market_catalogue`** - Market details
- `market_id` (PRIMARY KEY)
- `market_name`
- `event_name` ← **USE THIS TO MATCH TO NCAA GAMES**
- `competition_name`
- `event_type_id` (should be "7522" for basketball)
- `market_start_time`
- `total_matched`
- `event_open_date`

**`market_books`** - Live odds data
- `market_id`
- `selection_id` (runner/team)
- `runner_name` ← Team name
- `last_price_traded`
- `available_to_back` (JSON)
- `available_to_lay` (JSON)
- `status`

## Next Steps

### Immediate Tasks

1. **✅ DONE:** Create Betfair market worker
2. **✅ DONE:** Register as hosted service
3. **✅ DONE:** Add basketball-specific API methods
4. **TODO:** Test if Betfair has NCAA Basketball markets
5. **TODO:** Create market matching logic (Betfair event name → our NCAA games)
6. **TODO:** Update paper trading to use Betfair markets for betting
7. **TODO:** Create bet placement service (if not already exists)

### Testing Plan

1. **Start backend and check logs:**
   ```bash
   cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
   dotnet run
   ```

2. **Look for NCAA Basketball market worker logs:**
   ```
   🏀 NCAA Basketball Market Worker started...
   🏀 Fetching NCAA Basketball markets from Betfair...
   🏀 Found X NCAA Basketball markets
   ```

3. **Query Betfair database:**
   ```bash
   sqlite3 /Users/clairegrady/RiderProjects/betfair/database.db \
   "SELECT COUNT(*) FROM list_market_catalogue WHERE event_type_id = '7522';"
   ```

4. **Check what competitions Betfair has:**
   ```bash
   sqlite3 /Users/clairegrady/RiderProjects/betfair/database.db \
   "SELECT DISTINCT competition_name FROM list_market_catalogue WHERE event_type_id = '7522';"
   ```

### Potential Issues

1. **Betfair May Not Have NCAA Markets:**
   - Betfair primarily focuses on major US sports (NBA, NFL, MLB)
   - NCAA Basketball might be limited to March Madness / high-profile games
   - **Action:** Check what competitions appear in Betfair database after first run

2. **Team Name Matching:**
   - Betfair format: "Duke v North Carolina"
   - The Odds API format: "Duke Blue Devils" vs "North Carolina Tar Heels"
   - **Action:** Create fuzzy matching algorithm (similar to KenPom/ESPN matching)

3. **Market Availability:**
   - Betfair markets may not be available until closer to game time
   - **Action:** Monitor when markets appear relative to game start time

## Implementation Status

- ✅ `NcaaBasketballMarketWorker.cs` created
- ✅ `ListBasketballMarketCatalogueAsync()` added to `MarketApiService`
- ✅ `ProcessNcaaBasketballMarketCataloguesAsync()` added to `MarketAutomationService`
- ✅ Registered in `Program.cs`
- ✅ No linter errors
- ⏳ **READY TO BUILD AND TEST**

## Files Modified

1. `/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/AutomatedServices/NcaaBasketballMarketWorker.cs` (NEW)
2. `/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/Services/MarketApiService.cs` (MODIFIED)
3. `/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/AutomationServices/MarketAutomationService.cs` (MODIFIED)
4. `/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/Program.cs` (MODIFIED)

## Summary

**CRITICAL COMPONENT NOW ADDED:** The system can now fetch NCAA Basketball markets directly from Betfair for actual betting. This was a missing piece - we were collecting game data and odds from external sources but not pulling from the platform where we actually place bets!

**Next:** Build, test, and verify Betfair has NCAA markets available.


