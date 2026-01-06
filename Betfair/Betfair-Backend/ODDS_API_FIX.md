# ✅ FIXED: Odds API Key Configuration

## Problem
```
warn: Betfair.Services.NcaaOddsService[0]
      Odds API key not configured. Returning empty games list.
```

## Solution
Added the Odds API configuration to `appsettings.json`:

```json
{
  "OddsApi": {
    "ApiKey": "39d5bf82ca8f3f50f78c7b4eeee66ef1"
  }
}
```

## ✅ Now Restart Backend

```bash
# Stop the current backend (Ctrl+C in the terminal)
# Then restart:
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet run
```

## Expected Output After Restart

You should now see:
```
🏀 NcaaBasketballBackgroundService started at 12/28/2024 15:45:23
🔄 Starting NCAA Basketball cycle #1 at 12/28/2024 15:45:33
📅 Fetching NCAA Basketball games from The Odds API...
📊 Found 47 upcoming NCAA Basketball games
💾 Stored 12 new games in database
💰 Stored 156 odds updates
⏳ Waiting 5 minutes before next cycle...
```

## Check Games Were Collected

After ~30 seconds, check:

```bash
# Via API
curl http://localhost:5173/api/ncaa-basketball/games/upcoming | jq

# Or directly in database
sqlite3 /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/ncaa_basketball.db \
  "SELECT g.game_date, ht.team_name as HOME, at.team_name as AWAY, 
   CASE WHEN g.neutral_site = 1 THEN 'NEUTRAL' ELSE 'HOME' END as venue 
   FROM games g 
   JOIN teams ht ON g.home_team_id = ht.team_id 
   JOIN teams at ON g.away_team_id = at.team_id 
   WHERE g.game_date >= date('now') 
   ORDER BY g.game_date LIMIT 10;"
```

## 🎉 What Happens Now

Every 5 minutes, automatically:
1. ✅ Fetches upcoming NCAA games from The Odds API
2. ✅ Creates/updates teams in database
3. ✅ Stores games with human-readable names
4. ✅ Stores odds from multiple bookmakers
5. ✅ Cleans up old/finished games

**Just like the horse racing system!** 🐎→🏀

