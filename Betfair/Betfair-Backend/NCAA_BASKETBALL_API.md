# 🏀 NCAA Basketball API Backend

Complete C# .NET backend for NCAA Basketball predictions, KenPom data, and paper trading.

## 📋 Overview

This backend provides REST API endpoints to:
- Fetch today's and upcoming NCAA basketball games
- Get model predictions (win probabilities) 
- Access KenPom ratings and team data
- Fetch real-time odds from The Odds API
- Track paper trading performance
- Compare model predictions vs market odds

## 🚀 Quick Start

### 1. **Ensure Python Model is Trained**

```bash
cd /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor
python3 calculate_recent_form.py
python3 train_optimal_model.py
```

### 2. **Configure Odds API (Optional)**

Add to `appsettings.json`:

```json
{
  "OddsApi": {
    "ApiKey": "YOUR_THE_ODDS_API_KEY_HERE"
  }
}
```

Get free API key: https://the-odds-api.com/ (500 requests/month free)

### 3. **Start the Backend**

```bash
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet build
dotnet run
```

Backend runs on: `http://localhost:5173`

## 📡 API Endpoints

### **Games**

#### Get Today's Games
```http
GET /api/ncaa-basketball/games/today
```

Response:
```json
[
  {
    "gameId": "401585399",
    "gameDate": "2025-01-15",
    "season": 2025,
    "homeTeamId": 150,
    "awayTeamId": 156,
    "homeTeam": "Duke Blue Devils",
    "awayTeam": "North Carolina Tar Heels",
    "homeScore": null,
    "awayScore": null,
    "neutralSite": false,
    "tournament": null
  }
]
```

#### Get Upcoming Games
```http
GET /api/ncaa-basketball/games/upcoming?days=7
```

### **Predictions**

#### Get Prediction for Specific Game
```http
GET /api/ncaa-basketball/predictions/{gameId}
```

Response:
```json
{
  "gameId": "401585399",
  "homeTeam": "Duke Blue Devils",
  "awayTeam": "North Carolina Tar Heels",
  "homeWinProbability": 0.583,
  "awayWinProbability": 0.417,
  "confidence": "medium",
  "homeKenPom": {
    "adjEM": 25.4,
    "adjO": 115.2,
    "adjD": 89.8,
    "rank": 5
  },
  "awayKenPom": {
    "adjEM": 22.1,
    "adjO": 112.3,
    "adjD": 90.2,
    "rank": 8
  }
}
```

#### Get Today's Predictions
```http
GET /api/ncaa-basketball/predictions/today
```

#### Get Predictions with Odds Comparison
```http
GET /api/ncaa-basketball/predictions-with-odds/today
```

Response:
```json
[
  {
    "prediction": {
      "gameId": "401585399",
      "homeTeam": "Duke Blue Devils",
      "awayTeam": "North Carolina Tar Heels",
      "homeWinProbability": 0.583,
      "awayWinProbability": 0.417,
      "confidence": "medium"
    },
    "odds": {
      "homeTeam": "Duke Blue Devils",
      "awayTeam": "North Carolina Tar Heels",
      "homeOdds": 1.75,
      "awayOdds": 2.30,
      "bookmaker": "FanDuel",
      "lastUpdate": "2025-01-15T18:30:00Z"
    },
    "homeEdge": 0.012,
    "awayEdge": -0.018
  }
]
```

### **Teams & KenPom**

#### Get Team Info
```http
GET /api/ncaa-basketball/teams/{teamId}
```

#### Get KenPom Ratings
```http
GET /api/ncaa-basketball/kenpom/{teamId}?season=2025
```

Response:
```json
{
  "teamName": "Duke",
  "season": 2025,
  "rank": 5,
  "adjEM": 25.4,
  "adjO": 115.2,
  "adjORank": 3,
  "adjD": 89.8,
  "adjDRank": 12,
  "adjTempo": 70.5,
  "adjTempoRank": 45,
  "sos": 12.3,
  "sosRank": 8,
  "luck": 0.023,
  "luckRank": 120
}
```

### **Odds**

#### Get Today's Odds
```http
GET /api/ncaa-basketball/odds/today
```

### **Paper Trading**

#### Get Paper Trading History
```http
GET /api/ncaa-basketball/paper-trades?limit=50
```

#### Get Paper Trading Stats
```http
GET /api/ncaa-basketball/paper-trades/stats
```

Response:
```json
{
  "totalBets": 45,
  "won": 27,
  "lost": 15,
  "pending": 3,
  "settled": 42,
  "winRate": 64.3,
  "totalStaked": 3456.00,
  "totalProfit": 687.50,
  "roi": 19.9,
  "avgStake": 82.29,
  "avgOdds": 1.95,
  "avgEdge": 7.2
}
```

### **Health Check**

#### Check API Status
```http
GET /api/ncaa-basketball/health
```

---

## 🏗️ Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      NCAA BASKETBALL API                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                     │
         ▼                    ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ NcaaBasketball  │  │ NcaaBasketball  │  │  NcaaOdds       │
│    Controller   │  │     Service     │  │   Service       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                     │
         │                    │                     │
         ▼                    ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ NcaaBasketball  │  │ Python Model    │  │  The Odds API   │
│       Db        │  │ predict_game.py │  │    (External)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │
         │                    │
         ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│              ncaa_basketball.db (SQLite)                      │
│  • games              • kenpom_ratings                        │
│  • teams              • recent_form                           │
│  • team_name_mapping  • head_to_head                          │
└──────────────────────────────────────────────────────────────┘
```

### Key Components

1. **NcaaBasketballController** - REST API endpoints
2. **NcaaBasketballDb** - Database access layer
3. **NcaaBasketballService** - Business logic & Python model integration
4. **NcaaOddsService** - Real-time odds fetching
5. **predict_game.py** - Python prediction script (called via subprocess)

---

## 🔧 Configuration

### Database Paths

All hardcoded in `NcaaBasketballDb.cs`:
- NCAA database: `/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/ncaa_basketball.db`
- Paper trades: `/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/basketball_paper_trades.db`

### Python Integration

Python path and model location in `NcaaBasketballService.cs`:
- Python: `/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/venv/bin/python3`
- Predictor: `/Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor/`

### Odds API

Configure in `appsettings.json`:
```json
{
  "OddsApi": {
    "ApiKey": "your_api_key_here"
  }
}
```

---

## 🧪 Testing Endpoints

### Using curl:

```bash
# Health check
curl http://localhost:5173/api/ncaa-basketball/health

# Today's games
curl http://localhost:5173/api/ncaa-basketball/games/today

# Get prediction
curl http://localhost:5173/api/ncaa-basketball/predictions/401585399

# Today's predictions with odds
curl http://localhost:5173/api/ncaa-basketball/predictions-with-odds/today

# Paper trading stats
curl http://localhost:5173/api/ncaa-basketball/paper-trades/stats
```

### Using Swagger:

Navigate to: `http://localhost:5173/swagger`

---

## 📊 Model Details

The backend calls `predict_game.py` which uses:
- **XGBoost** classifier
- **38 features** (20 KenPom + 12 recent form + 6 matchups)
- Trained on 2024 season data
- Returns win probabilities (0.0 - 1.0)

Output format from Python:
```json
{
  "gameId": "401585399",
  "homeTeam": "Duke Blue Devils",
  "awayTeam": "North Carolina Tar Heels",
  "homeWinProbability": 0.5834,
  "awayWinProbability": 0.4166,
  "confidence": "medium",
  "homeKenPom": {...},
  "awayKenPom": {...}
}
```

---

## 🚨 Troubleshooting

### Error: "Model not found"
```bash
cd /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor
python3 train_optimal_model.py
```

### Error: "Could not build features"
- Check that `recent_form` table has data
- Run: `python3 calculate_recent_form.py`

### Error: "No KenPom data"
- Verify team name mapping: `python3 match_team_names.py`
- Check KenPom API data exists: `python3 fetch_kenpom.py`

### Error: "Odds API failed"
- Check API key in `appsettings.json`
- Verify quota not exceeded (500/month free tier)

---

## 📝 Files Created

### Backend (C#):
- `Controllers/NcaaBasketballController.cs` - API endpoints
- `Services/NcaaBasketballService.cs` - Prediction service
- `Services/NcaaOddsService.cs` - Odds fetching
- `Data/NcaaBasketballDb.cs` - Database layer
- `Models/NcaaBasketball/NcaaBasketballModels.cs` - DTOs

### Python:
- `predict_game.py` - Prediction script called by backend

### Configuration:
- Updated `Program.cs` - Service registration

---

## ✅ Next Steps

1. **Train the model:**
   ```bash
   cd /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor
   python3 train_optimal_model.py
   ```

2. **Start backend:**
   ```bash
   cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
   dotnet run
   ```

3. **Test endpoints:**
   - Visit: `http://localhost:5173/swagger`
   - Test: `http://localhost:5173/api/ncaa-basketball/health`

4. **Get odds API key (optional):**
   - Sign up: https://the-odds-api.com/
   - Add to `appsettings.json`

5. **Build frontend (later):**
   - Connect React app to these endpoints
   - Display predictions + odds
   - Paper trading UI

---

## 🎯 Summary

✅ **Complete backend API for NCAA Basketball**  
✅ **Database connection** to SQLite  
✅ **Python model integration** via subprocess  
✅ **Real-time odds** from The Odds API  
✅ **Paper trading** stats and history  
✅ **Ready to use** - just train model and run!

**Frontend NOT included** - focus on testing model performance first via API/paper trading before building UI.

