#!/bin/bash
###############################################################################
# Master Automation Script for Betting Simulations
# 
# This script:
# 1. Scrapes greyhound race times
# 2. Scrapes horse race times  
# 3. Checks results for greyhounds
# 4. Checks results for horses
# 5. Starts all simulated betting scripts (8 greyhound + 18 horse = 26 scripts)
#
# Run manually: ./start_all_simulations.sh
# Or add to cron: 0 6 * * * /Users/clairegrady/RiderProjects/betfair/start_all_simulations.sh
###############################################################################

PROJECT_ROOT="/Users/clairegrady/RiderProjects/betfair"
SHARED_VENV="$PROJECT_ROOT/shared/venv/bin/python3"
GREYHOUND_VENV="$PROJECT_ROOT/greyhound-simulated/venv/bin/python3"
HORSE_VENV="$PROJECT_ROOT/horse-simulated/venv/bin/python3"

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="$LOG_DIR/automation_${TIMESTAMP}.log"

echo "===============================================================================" | tee -a "$MAIN_LOG"
echo "🚀 Starting Betting Simulation Automation at $(date)" | tee -a "$MAIN_LOG"
echo "===============================================================================" | tee -a "$MAIN_LOG"

###############################################################################
# STEP 1: Scrape Greyhound Race Times
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "📊 STEP 1/5: Scraping greyhound race times..." | tee -a "$MAIN_LOG"
echo "-------------------------------------------------------------------------------" | tee -a "$MAIN_LOG"

cd "$PROJECT_ROOT/shared"
$SHARED_VENV greyhound_race_scraper_postgres.py >> "$MAIN_LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Greyhound race times scraped successfully" | tee -a "$MAIN_LOG"
else
    echo "❌ ERROR: Greyhound race scraping failed! Check logs." | tee -a "$MAIN_LOG"
fi

###############################################################################
# STEP 2: Scrape Horse Race Times
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "🐴 STEP 2/5: Scraping horse race times..." | tee -a "$MAIN_LOG"
echo "-------------------------------------------------------------------------------" | tee -a "$MAIN_LOG"

cd "$PROJECT_ROOT/shared"
$SHARED_VENV race_times_scraper_postgres.py >> "$MAIN_LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Horse race times scraped successfully" | tee -a "$MAIN_LOG"
else
    echo "❌ ERROR: Horse race scraping failed! Check logs." | tee -a "$MAIN_LOG"
fi

###############################################################################
# STEP 3: Check Greyhound Results
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "📈 STEP 3/5: Checking greyhound results..." | tee -a "$MAIN_LOG"
echo "-------------------------------------------------------------------------------" | tee -a "$MAIN_LOG"

cd "$PROJECT_ROOT/greyhound-simulated"
$GREYHOUND_VENV check_results_greyhounds.py >> "$MAIN_LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Greyhound results checked successfully" | tee -a "$MAIN_LOG"
else
    echo "⚠️  WARNING: Greyhound results check had issues. Check logs." | tee -a "$MAIN_LOG"
fi

###############################################################################
# STEP 4: Check Horse Results
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "🏇 STEP 4/5: Checking horse results..." | tee -a "$MAIN_LOG"
echo "-------------------------------------------------------------------------------" | tee -a "$MAIN_LOG"

cd "$PROJECT_ROOT/horse-simulated"
$HORSE_VENV check_results_horses.py >> "$MAIN_LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Horse results checked successfully" | tee -a "$MAIN_LOG"
else
    echo "⚠️  WARNING: Horse results check had issues. Check logs." | tee -a "$MAIN_LOG"
fi

###############################################################################
# STEP 5: Start All Betting Scripts (26 total)
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "🎯 STEP 5/5: Starting all betting scripts..." | tee -a "$MAIN_LOG"
echo "-------------------------------------------------------------------------------" | tee -a "$MAIN_LOG"

SCRIPT_COUNT=0

# Start Greyhound Betting Scripts (8 total)
echo "🐕 Starting greyhound betting scripts (positions 1-8)..." | tee -a "$MAIN_LOG"
cd "$PROJECT_ROOT/greyhound-simulated/lay_betting"

for i in {1..8}; do
    SCRIPT="lay_position_${i}.py"
    LOG_FILE="$PROJECT_ROOT/greyhound-simulated/lay_betting/dog_lay_${i}.log"
    
    if [ -f "$SCRIPT" ]; then
        # Kill existing process if running
        pkill -f "$SCRIPT" 2>/dev/null
        
        # Start new process in background
        nohup $GREYHOUND_VENV "$SCRIPT" > "$LOG_FILE" 2>&1 &
        PID=$!
        echo "  ✓ Started $SCRIPT (PID: $PID)" | tee -a "$MAIN_LOG"
        SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
    else
        echo "  ✗ Script not found: $SCRIPT" | tee -a "$MAIN_LOG"
    fi
done

# Start Horse Betting Scripts (18 total)
echo "" | tee -a "$MAIN_LOG"
echo "🐴 Starting horse betting scripts (positions 1-18)..." | tee -a "$MAIN_LOG"
cd "$PROJECT_ROOT/horse-simulated/lay_betting"

for i in {1..18}; do
    SCRIPT="lay_position_${i}.py"
    LOG_FILE="$PROJECT_ROOT/horse-simulated/lay_betting/horse_lay_${i}.log"
    
    if [ -f "$SCRIPT" ]; then
        # Kill existing process if running
        pkill -f "$SCRIPT" 2>/dev/null
        
        # Start new process in background
        nohup $HORSE_VENV "$SCRIPT" > "$LOG_FILE" 2>&1 &
        PID=$!
        echo "  ✓ Started $SCRIPT (PID: $PID)" | tee -a "$MAIN_LOG"
        SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
    else
        echo "  ✗ Script not found: $SCRIPT" | tee -a "$MAIN_LOG"
    fi
done

###############################################################################
# Summary
###############################################################################
echo "" | tee -a "$MAIN_LOG"
echo "===============================================================================" | tee -a "$MAIN_LOG"
echo "✅ Automation Complete!" | tee -a "$MAIN_LOG"
echo "===============================================================================" | tee -a "$MAIN_LOG"
echo "Started: $SCRIPT_COUNT betting scripts" | tee -a "$MAIN_LOG"
echo "Expected: 26 scripts (8 greyhound + 18 horse)" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"
echo "📝 Logs:" | tee -a "$MAIN_LOG"
echo "  Main log: $MAIN_LOG" | tee -a "$MAIN_LOG"
echo "  Greyhound logs: $PROJECT_ROOT/greyhound-simulated/lay_betting/dog_lay_*.log" | tee -a "$MAIN_LOG"
echo "  Horse logs: $PROJECT_ROOT/horse-simulated/lay_betting/horse_lay_*.log" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"
echo "🔍 Check running processes:" | tee -a "$MAIN_LOG"
echo "  ps aux | grep 'lay_position'" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"
echo "🛑 Stop all scripts:" | tee -a "$MAIN_LOG"
echo "  pkill -f lay_position" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"
echo "Finished at: $(date)" | tee -a "$MAIN_LOG"
echo "===============================================================================" | tee -a "$MAIN_LOG"

# Display a summary of running processes
echo "" | tee -a "$MAIN_LOG"
echo "📊 Currently running betting scripts:" | tee -a "$MAIN_LOG"
ps aux | grep "[l]ay_position" | wc -l | xargs echo "  Active scripts:" | tee -a "$MAIN_LOG"
