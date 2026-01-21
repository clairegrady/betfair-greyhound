#!/bin/bash
###############################################################################
# Stop All Betting Simulations Script
# 
# This script stops all running simulated betting scripts (greyhound and horse)
# Does NOT stop the LIVE betting script
#
# Usage: ./stop_all_simulations.sh
###############################################################################

echo "==============================================================================="
echo "🛑 Stopping All Betting Simulations"
echo "==============================================================================="

# Count running scripts before stopping
BEFORE=$(ps aux | grep -E "[l]ay_position_[0-9]+\.py" | grep -v "REAL" | wc -l | tr -d ' ')
echo "Currently running: $BEFORE simulated betting scripts"
echo ""

# Stop all greyhound simulated scripts
echo "🐕 Stopping greyhound simulated scripts..."
pkill -f "greyhound-simulated/lay_betting/lay_position"
sleep 1

# Stop all horse simulated scripts  
echo "🐴 Stopping horse simulated scripts..."
pkill -f "horse-simulated/lay_betting/lay_position"
sleep 1

# Count running scripts after stopping
AFTER=$(ps aux | grep -E "[l]ay_position_[0-9]+\.py" | grep -v "REAL" | wc -l | tr -d ' ')

echo ""
echo "==============================================================================="
if [ "$AFTER" -eq 0 ]; then
    echo "✅ All simulated betting scripts stopped successfully"
else
    echo "⚠️  Warning: $AFTER scripts still running"
    echo ""
    echo "Remaining processes:"
    ps aux | grep -E "[l]ay_position_[0-9]+\.py" | grep -v "REAL"
    echo ""
    echo "To force kill all: pkill -9 -f lay_position"
fi
echo "==============================================================================="

# Check if LIVE script is still running (should be)
LIVE=$(ps aux | grep "[l]ay_position_1_REAL.py" | wc -l | tr -d ' ')
if [ "$LIVE" -gt 0 ]; then
    echo ""
    echo "✅ LIVE betting script is still running (not stopped)"
fi

echo ""
echo "Stopped: $((BEFORE - AFTER)) scripts"
echo "Still running: $AFTER scripts"
