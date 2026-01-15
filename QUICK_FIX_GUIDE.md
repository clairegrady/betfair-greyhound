# 🚀 QUICK FIX GUIDE - Get Your Betting System Back Online

## 🔴 CURRENT STATUS
- ❌ Backend: NOT RUNNING
- ❌ All betting scripts: NOT RUNNING
- ✅ Databases: Converted to WAL mode
- ✅ Root cause: Identified and documented
- ⏰ Time lost: 11 hours of betting (10 AM - 9 PM)

---

## ⚡ OPTION 1: IMMEDIATE RESTART (5 minutes)

**Use this if:** You want to get betting NOW and fix properly later

### Step 1: Start the Backend
```bash
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet run > backend.log 2>&1 &
```

### Step 2: Restart Greyhound Scripts (with 2-second delays)
```bash
cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor

for i in {1..8}; do
    nohup venv/bin/python lay_betting/lay_position_${i}.py > lay_betting/lay_position_${i}.log 2>&1 &
    echo "Started greyhound position $i"
    sleep 2
done
```

### Step 3: Restart Horse Scripts (with 2-second delays)
```bash
cd /Users/clairegrady/RiderProjects/betfair/horse-racing-predictor

for i in {1..18}; do
    nohup venv/bin/python lay_betting/lay_position_${i}.py > lay_betting/lay_position_${i}.log 2>&1 &
    echo "Started horse position $i"
    sleep 2
done
```

### Step 4: Restart Backfill Script
```bash
cd /Users/clairegrady/RiderProjects/betfair
nohup greyhound-predictor/venv/bin/python utilities/continuous_backfill_greyhound_data.py > utilities/backfill.log 2>&1 &
```

### Step 5: Verify Everything is Running
```bash
ps aux | grep -E "(lay_position|dotnet|continuous_backfill)" | grep -v grep | wc -l
# Should show: 27 (8 greyhound + 18 horse + 1 backend)
```

**⚠️ WARNING:** This gets you running but scripts may still crash under heavy load. Proceed to Option 2 ASAP.

---

## 🛠️ OPTION 2: PROPER FIX (30-60 minutes)

**Use this if:** You want a permanent solution

### Step 1: Apply Automated Fixes
```bash
cd /Users/clairegrady/RiderProjects/betfair
python3 utilities/fix_all_betting_scripts.py
```

This will:
- Update all 26 betting scripts
- Add proper timeout handling
- Add retry logic
- Create .backup files

### Step 2: Review Changes (Optional but Recommended)
```bash
# Compare one script to see what changed
diff greyhound-predictor/lay_betting/lay_position_1.py.backup \
     greyhound-predictor/lay_betting/lay_position_1.py
```

### Step 3: Test One Script
```bash
cd /Users/clairegrady/RiderProjects/betfair/greyhound-predictor
venv/bin/python lay_betting/lay_position_1.py
# Watch for errors, press Ctrl+C after 30 seconds if it looks good
```

### Step 4: If Test Passes, Restart All Scripts
Follow the same steps as Option 1 above.

---

## 🔍 OPTION 3: HYBRID APPROACH (10 minutes + ongoing)

**Use this if:** You want betting running NOW but will fix properly over time

### Step 1: Restart Everything (Option 1)
Follow Option 1 steps to get betting running immediately.

### Step 2: Apply Fixes Gradually
```bash
# Fix and restart one script at a time
cd /Users/clairegrady/RiderProjects/betfair

# Fix greyhound position 1
python3 utilities/fix_all_betting_scripts.py  # Fix all at once, or...

# Manually update one script, test it, then restart just that one
pkill -f "lay_position_1.py"
nohup greyhound-predictor/venv/bin/python greyhound-predictor/lay_betting/lay_position_1.py > greyhound-predictor/lay_betting/lay_position_1.log 2>&1 &
```

### Step 3: Monitor and Replace
Over the next few hours, replace each script one by one with the fixed version.

---

## 📊 MONITORING COMMANDS

### Check if all scripts are running:
```bash
ps aux | grep -E "(lay_position|dotnet)" | grep -v grep | wc -l
# Should be: 27 (8 greyhound + 18 horse + 1 backend)
```

### Check for database lock errors:
```bash
tail -f /Users/clairegrady/RiderProjects/betfair/greyhound-predictor/lay_betting/lay_position_1.log | grep -i "locked"
```

### Check recent bets:
```bash
sqlite3 /Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db \
  "SELECT COUNT(*) FROM paper_trades WHERE created_at > datetime('now', '-10 minutes')"
```

### Check database mode (should be 'wal'):
```bash
sqlite3 /Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db \
  "PRAGMA journal_mode"
```

---

## 🆘 TROUBLESHOOTING

### Problem: Scripts won't start
```bash
# Check Python path
which python3
# Check venv
ls -la greyhound-predictor/venv/bin/python
```

### Problem: "Database is locked" errors still appearing
```bash
# Verify WAL mode is enabled
sqlite3 /path/to/database.db "PRAGMA journal_mode"
# Should show: wal

# If not, re-enable:
python3 -c "import sqlite3; conn = sqlite3.connect('/path/to/database.db'); conn.execute('PRAGMA journal_mode=WAL'); print(conn.execute('PRAGMA journal_mode').fetchone()[0]); conn.close()"
```

### Problem: Backend won't start
```bash
cd /Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend
dotnet build
dotnet run
# Check for errors in output
```

### Problem: Scripts crash immediately
```bash
# Check the log file
tail -50 /Users/clairegrady/RiderProjects/betfair/greyhound-predictor/lay_betting/lay_position_1.log
```

---

## ✅ VERIFICATION CHECKLIST

After restarting, verify:

- [ ] Backend is running: `ps aux | grep dotnet | grep -v grep`
- [ ] 8 greyhound scripts running: `ps aux | grep "greyhound.*lay_position" | wc -l`
- [ ] 18 horse scripts running: `ps aux | grep "horse.*lay_position" | wc -l`
- [ ] Bets being placed: Check database for recent entries
- [ ] No lock errors: `grep -i "locked" greyhound-predictor/lay_betting/*.log`
- [ ] Databases in WAL mode: `sqlite3 databases/greyhounds/paper_trades_greyhounds.db "PRAGMA journal_mode"`

---

## 📞 QUICK REFERENCE

**Key Files:**
- Investigation Report: `DATABASE_INVESTIGATION_REPORT.md`
- Technical Details: `DATABASE_FIX_IMPLEMENTATION.md`
- This Guide: `QUICK_FIX_GUIDE.md`
- Connection Helper: `utilities/db_connection_helper.py`
- Auto-Fix Script: `utilities/fix_all_betting_scripts.py`

**Key Databases:**
- Greyhounds: `/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db`
- Horses: `/Users/clairegrady/RiderProjects/betfair/databases/horses/paper_trades_horses.db`
- Backend: `/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite`

**Key Logs:**
- Backend: `Betfair/Betfair-Backend/backend.log`
- Greyhound Scripts: `greyhound-predictor/lay_betting/lay_position_*.log`
- Horse Scripts: `horse-racing-predictor/lay_betting/lay_position_*.log`

---

## 🎯 RECOMMENDED APPROACH

**For immediate recovery:** Use **Option 1** (5 minutes)  
**For long-term stability:** Follow up with **Option 2** within 24 hours

**Why?**
- Option 1 gets you betting again in 5 minutes
- WAL mode alone will prevent most crashes
- Option 2 adds retry logic for 100% reliability
- You can apply Option 2 gradually without downtime

---

**Last Updated:** January 14, 2026, 9:00 PM  
**Status:** Ready to deploy
