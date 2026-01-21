# Direct Stream API Test - Triple Bet

## What This Does
This script connects **directly** to Betfair's Stream API (bypassing the C# backend) to get real-time odds with minimal latency (~50-100ms instead of ~1-2 seconds from database).

## Why This Matters
- ⚡ **10-20x faster** than querying PostgreSQL
- 🎯 **Always fresh odds** - no database lag
- 💰 **Better bet timing** - especially for in-play bets

## Setup

### 1. Get Your Session Token
```bash
cd /Users/clairegrady/RiderProjects/betfair
./get_session_token.sh
```

This will prompt for your Betfair username/password and return a session token.

### 2. Run the Test
```bash
cd /Users/clairegrady/RiderProjects/betfair/greyhound-simulated/lay_betting
source ../venv/bin/activate
python3 lay_position_1_triple_stream_test.py '<YOUR_SESSION_TOKEN>'
```

## What It Tests
- **Bet 1**: T-30s (30 seconds before race)
- **Bet 2**: T-5s (5 seconds before race)  
- **Bet 3**: T+5s (5 seconds AFTER race starts - IN-PLAY)

## Expected Output
```
🔌 Connecting to Betfair Stream API...
✅ Connection ID: 002-230915140112-174
✅ Authenticated successfully
🎧 Started listening thread
⏰ Monitoring...

📡 Subscribed to market: 1.252856909
💰 1.252856909 | Runner 83676984 | Lay @ 3.45 ($250.00)
💰 1.252856909 | Runner 83676985 | Lay @ 5.20 ($180.00)

🎯 BET #1 - T-30s ⚡ DIRECT STREAM
================================================================================
Race:      Richmond R2
Dog:       Opawa Mocha [Box 4] (ID: 83676984)
Lay Odds:  3.45
Odds Age:  0.08s old (Stream API)  <-- THIS IS THE KEY METRIC
Liability: $24.50
================================================================================
```

## Key Differences from Database Version
| Metric | Database Version | Stream API Version |
|--------|-----------------|-------------------|
| Odds Age | 1-2 seconds | 0.05-0.2 seconds |
| Update Frequency | Every 500-1000ms | Every 50-100ms |
| Data Source | PostgreSQL | In-memory cache |
| Latency | High | Ultra-low |

## If This Works Better...
We can:
1. Implement for all betting scripts (Option B)
2. OR keep database but add conflation changes (Option A + C)
3. OR hybrid: Stream for critical bets, DB for bulk monitoring

## Notes
- Session tokens expire after 8-12 hours
- Stream API has same connection limits as backend
- This bypasses ALL backend logic - uses raw Betfair data
