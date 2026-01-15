#!/bin/bash
################################################################################
# RESTART EVERYTHING - Complete System Restart Script
# This script restarts:
# - Backend (.NET)
# - Race scrapers (2 scripts)
# - All betting scripts (26 scripts)
################################################################################

set -e  # Exit on error

BASE_DIR="/Users/clairegrady/RiderProjects/betfair"
cd "$BASE_DIR"

echo "======================================================================="
echo "🚀 RESTARTING BETTING SYSTEM"
echo "======================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

################################################################################
# STEP 1: Kill any existing processes
################################################################################
echo -e "${YELLOW}STEP 1: Stopping any existing processes...${NC}"

# Kill backend
pkill -f "dotnet.*Betfair-Backend" || true

# Kill betting scripts
pkill -f "lay_position_" || true

# Kill scrapers
pkill -f "greyhound_race_scraper" || true
pkill -f "race_times_scraper" || true

# Kill backfill
pkill -f "continuous_backfill" || true

echo -e "${GREEN}✅ All existing processes stopped${NC}"
sleep 2
echo ""

################################################################################
# STEP 2: Start Backend
################################################################################
echo -e "${YELLOW}STEP 2: Starting backend...${NC}"

cd "$BASE_DIR/Betfair/Betfair-Backend"
nohup dotnet run > backend.log 2>&1 &
BACKEND_PID=$!

echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo "   Waiting 10 seconds for backend to initialize..."
sleep 10
echo ""

################################################################################
# STEP 3: Start Race Scrapers
################################################################################
echo -e "${YELLOW}STEP 3: Starting race scrapers to fetch today's races...${NC}"

# Start greyhound scraper
cd "$BASE_DIR/greyhound-predictor"
nohup venv/bin/python greyhound_race_scraper.py > greyhound_scraper.log 2>&1 &
echo -e "${GREEN}✅ Greyhound scraper started${NC}"

# Start horse scraper
cd "$BASE_DIR/horse-racing-predictor"
nohup venv/bin/python race_times_scraper.py > horse_scraper.log 2>&1 &
echo -e "${GREEN}✅ Horse scraper started${NC}"

echo "   Waiting 30 seconds for scrapers to fetch race data..."
sleep 30
echo ""

################################################################################
# STEP 4: Start Backfill Script
################################################################################
echo -e "${YELLOW}STEP 4: Starting backfill script...${NC}"

cd "$BASE_DIR"
nohup greyhound-predictor/venv/bin/python utilities/continuous_backfill_greyhound_data.py > utilities/backfill.log 2>&1 &
echo -e "${GREEN}✅ Backfill script started${NC}"
sleep 2
echo ""

################################################################################
# STEP 5: Start Greyhound Betting Scripts (8 scripts)
################################################################################
echo -e "${YELLOW}STEP 5: Starting greyhound betting scripts...${NC}"

cd "$BASE_DIR/greyhound-predictor"

for i in {1..8}; do
    nohup venv/bin/python lay_betting/lay_position_${i}.py > lay_betting/lay_position_${i}.log 2>&1 &
    echo -e "${GREEN}✅ Started greyhound position $i${NC}"
    sleep 2  # Stagger startups to reduce database contention
done

echo -e "${GREEN}✅ All 8 greyhound scripts started${NC}"
echo ""

################################################################################
# STEP 6: Start Horse Betting Scripts (18 scripts)
################################################################################
echo -e "${YELLOW}STEP 6: Starting horse betting scripts...${NC}"

cd "$BASE_DIR/horse-racing-predictor"

for i in {1..18}; do
    nohup venv/bin/python lay_betting/lay_position_${i}.py > lay_betting/lay_position_${i}.log 2>&1 &
    echo -e "${GREEN}✅ Started horse position $i${NC}"
    sleep 2  # Stagger startups to reduce database contention
done

echo -e "${GREEN}✅ All 18 horse scripts started${NC}"
echo ""

################################################################################
# STEP 7: Verify Everything is Running
################################################################################
echo "======================================================================="
echo -e "${YELLOW}STEP 7: Verification${NC}"
echo "======================================================================="
echo ""

# Count processes
BACKEND_COUNT=$(ps aux | grep -E "dotnet.*Betfair-Backend" | grep -v grep | wc -l | tr -d ' ')
GREYHOUND_COUNT=$(ps aux | grep -E "greyhound.*lay_position" | grep -v grep | wc -l | tr -d ' ')
HORSE_COUNT=$(ps aux | grep -E "horse.*lay_position" | grep -v grep | wc -l | tr -d ' ')
SCRAPER_COUNT=$(ps aux | grep -E "race.*scraper" | grep -v grep | wc -l | tr -d ' ')
BACKFILL_COUNT=$(ps aux | grep -E "continuous_backfill" | grep -v grep | wc -l | tr -d ' ')

echo "Process Status:"
echo "---------------"
echo "  Backend:          $BACKEND_COUNT / 1"
echo "  Race Scrapers:    $SCRAPER_COUNT / 2"
echo "  Greyhound Scripts: $GREYHOUND_COUNT / 8"
echo "  Horse Scripts:    $HORSE_COUNT / 18"
echo "  Backfill:         $BACKFILL_COUNT / 1"
echo ""

TOTAL=$((BACKEND_COUNT + GREYHOUND_COUNT + HORSE_COUNT + SCRAPER_COUNT + BACKFILL_COUNT))
EXPECTED=30

if [ "$TOTAL" -eq "$EXPECTED" ]; then
    echo -e "${GREEN}✅ SUCCESS: All $TOTAL processes running!${NC}"
else
    echo -e "${RED}⚠️  WARNING: Only $TOTAL / $EXPECTED processes running${NC}"
    echo "   Check log files for errors"
fi

echo ""
echo "======================================================================="
echo "📊 MONITORING COMMANDS"
echo "======================================================================="
echo ""
echo "Check recent bets (should show new bets within minutes):"
echo "  sqlite3 $BASE_DIR/databases/greyhounds/paper_trades_greyhounds.db \\"
echo "    \"SELECT COUNT(*) FROM paper_trades WHERE created_at > datetime('now', '-10 minutes')\""
echo ""
echo "Check for errors in greyhound scripts:"
echo "  tail -f $BASE_DIR/greyhound-predictor/lay_betting/lay_position_1.log"
echo ""
echo "Check today's races in database:"
echo "  sqlite3 $BASE_DIR/horse-racing-predictor/race_info.db \\"
echo "    \"SELECT COUNT(*) FROM greyhound_race_times WHERE race_date = date('now', 'localtime')\""
echo ""
echo "======================================================================="
echo -e "${GREEN}🎉 SYSTEM RESTART COMPLETE!${NC}"
echo "======================================================================="
