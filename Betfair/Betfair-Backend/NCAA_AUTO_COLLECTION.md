# 🏀 NCAA Basketball Auto-Collection System - COMPLETE

## ✅ What Was Built

### **1. Background Service (Automatic Game Collection)**
**File:** `Betfair/Betfair-Backend/AutomatedServices/NcaaBasketballBackgroundService.cs`

- ✅ Runs automatically like the horse racing service
- ✅ Fetches games from The Odds API every 5 minutes
- ✅ Stores games in the database automatically
- ✅ Stores real-time odds from multiple bookmakers
- ✅ Cleans up old/finished games

### **2. Enhanced Database Methods**
**File:** `Betfair/Betfair-Backend/Data/NcaaBasketballDb.cs`

Added methods:
- `GetGameByTeamsAndDateAsync()` - Check if game exists
- `GetTeamByNameAsync()` - Find team by name
- `InsertTeamAsync()` - Create new team
- `InsertUpcomingGameAsync()` - Store game in database
- `InsertOddsAsync()` - Store odds data
- `DeleteOldUpcomingGamesAsync()` - Cleanup old games

### **3. Odds API Integration**
**File:** `Betfair/Betfair-Backend/Services/NcaaOddsService.cs`

Added method:
- `GetUpcomingGamesAsync()` - Fetch all upcoming NCAA basketball games with odds

### **4. Human-Readable Game Display**
**File:** `Betfair/Betfair-Backend/Models/NcaaBasketball/NcaaBasketballModels.cs`

Added computed properties to `NcaaGame`:
- **`Matchup`**: "UNC @ Duke" or "UNC vs Duke (Neutral)"
- **`Venue`**: "Home: Duke" or "Neutral Court"
- **`Result`**: "Duke 85 - 82 UNC"
- **`Winner`**: "Duke" or "TBD"

### **5. Registered Background Service**
**File:** `Betfair/Betfair-Backend/Program.cs`

```csharp
builder.Services.AddHostedService<NcaaBasketballBackgroundService>();
```

---

## 📊 Example API Response (After Backend Restarts)

### Before (confusing):
```json
{
  "gameId": "401575519",
  "gameDate": "2023-11-14",
  "homeTeamId": 2633,
  "awayTeamId": 2747,
  "homeScore": 82,
  "awayScore": 61,
  "neutralSite": false
}
```

### After (crystal clear):
```json
{
  "gameId": "401575519",
  "gameDate": "2023-11-14",
  "season": 2024,
  "homeTeamId": 2633,
  "awayTeamId": 2747,
  "homeTeam": "Duke Blue Devils",
  "awayTeam": "UNC Tar Heels",
  "homeScore": 82,
  "awayScore": 61,
  "neutralSite": false,
  "tournament": null,
  "matchup": "UNC Tar Heels @ Duke Blue Devils",
  "venue": "Home: Duke Blue Devils",
  "result": "Duke Blue Devils 82 - 61 UNC Tar Heels",
  "winner": "Duke Blue Devils"
}
```

---

## 🚀 How It Works

### **1. Automatic Collection (Every 5 Minutes)**
```
NcaaBasketballBackgroundService starts
   ↓
Calls NcaaOddsService.GetUpcomingGamesAsync()
   ↓
Fetches games from The Odds API
   ↓
For each game:
   - Get or create teams
   - Check if game exists
   - Insert game into database
   - Store odds from all bookmakers
   ↓
Clean up old games
   ↓
Wait 5 minutes, repeat
```

### **2. Database Storage**
- **Games** → `ncaa_basketball.db` (predictor database)
- **Odds** → `betfair.sqlite` (live betting database)
- **Team names** are stored and joined automatically

---

## 🔧 To Start Collecting Games

**1. Ensure The Odds API key is configured:**
```json
// appsettings.json
{
  "OddsApi": {
    "ApiKey": "39d5bf82ca8f3f50f78c7b4eeee66ef1"
  }
}
```

**2. Restart the backend:**
```bash
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet run
```

**3. Watch the logs:**
```
🏀 NcaaBasketballBackgroundService started
🔄 Starting NCAA Basketball cycle #1
📅 Fetching NCAA Basketball games from The Odds API...
📊 Found 47 upcoming NCAA Basketball games
💾 Stored 12 new games in database
💰 Stored 156 odds updates
⏳ Waiting 5 minutes before next cycle...
```

**4. Check the games:**
```bash
curl http://localhost:5173/api/ncaa-basketball/games/upcoming | jq
```

---

## 📈 What Gets Collected

### **Game Data:**
- Game ID
- Date & Time
- Home & Away teams (with names!)
- Season
- Neutral site indicator
- Tournament info (if applicable)

### **Odds Data:**
- Multiple bookmakers (DraftKings, FanDuel, etc.)
- Moneyline odds for both teams
- Timestamp of odds
- Historical odds tracking (every 5 minutes)

---

## 🎯 Next Steps

With automatic game collection working, you can now:

1. ✅ **See upcoming games automatically** (no manual SQL needed)
2. ✅ **Track odds movements** (5-minute intervals)
3. ✅ **Get model predictions** for any upcoming game
4. ⏳ **Run paper trading** automatically (once model is trained)
5. ⏳ **Place live bets** (after paper trading is profitable)

---

## 🔍 Useful API Endpoints

```bash
# Get today's games
curl http://localhost:5173/api/ncaa-basketball/games/today

# Get next 7 days of games
curl http://localhost:5173/api/ncaa-basketball/games/upcoming

# Get next 14 days of games
curl http://localhost:5173/api/ncaa-basketball/games/upcoming?days=14

# Get prediction for a specific game
curl http://localhost:5173/api/ncaa-basketball/predictions/{gameId}

# Health check
curl http://localhost:5173/api/ncaa-basketball/health
```

---

## 🎉 Summary

**You now have:**
- ✅ Automatic game collection (like horse racing)
- ✅ Real-time odds tracking
- ✅ Human-readable game display
- ✅ Team name resolution
- ✅ Home/away/neutral clarity
- ✅ Multiple bookmaker odds
- ✅ Historical odds storage

**Just restart the backend and games will start flowing in automatically!** 🚀

