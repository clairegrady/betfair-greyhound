#!/bin/bash
###############################################################################
# Monitor All Betting Simulations Script
# 
# This script shows the status of all betting scripts
#
# Usage: ./monitor_simulations.sh
###############################################################################

echo "==============================================================================="
echo "📊 Betting Simulations Status - $(date)"
echo "==============================================================================="

# Count scripts
GREYHOUND_COUNT=$(ps aux | grep "[l]ay_position_[1-8]\.py" | grep "greyhound-simulated" | wc -l | tr -d ' ')
HORSE_COUNT=$(ps aux | grep "[l]ay_position_[0-9].*\.py" | grep "horse-simulated" | wc -l | tr -d ' ')
LIVE_COUNT=$(ps aux | grep "[l]ay_position_1_REAL\.py" | wc -l | tr -d ' ')

TOTAL_SIMULATED=$((GREYHOUND_COUNT + HORSE_COUNT))

echo ""
echo "🐕 Greyhound Simulated: $GREYHOUND_COUNT / 8 scripts running"
echo "🐴 Horse Simulated:     $HORSE_COUNT / 18 scripts running"
echo "🚨 LIVE Betting:        $LIVE_COUNT / 1 script running"
echo ""
echo "Total Simulated:       $TOTAL_SIMULATED / 26 scripts"
echo "==============================================================================="

# Show greyhound scripts
if [ "$GREYHOUND_COUNT" -gt 0 ]; then
    echo ""
    echo "🐕 Greyhound Scripts:"
    ps aux | grep "[l]ay_position_[1-8]\.py" | grep "greyhound-simulated" | awk '{print "  PID " $2 ": " $(NF-1) " " $NF}'
fi

# Show horse scripts
if [ "$HORSE_COUNT" -gt 0 ]; then
    echo ""
    echo "🐴 Horse Scripts:"
    ps aux | grep "[l]ay_position_[0-9].*\.py" | grep "horse-simulated" | awk '{print "  PID " $2 ": " $(NF-1) " " $NF}' | head -10
    if [ "$HORSE_COUNT" -gt 10 ]; then
        echo "  ... and $((HORSE_COUNT - 10)) more"
    fi
fi

# Show LIVE script
if [ "$LIVE_COUNT" -gt 0 ]; then
    echo ""
    echo "🚨 LIVE Script:"
    ps aux | grep "[l]ay_position_1_REAL\.py" | awk '{print "  PID " $2 ": " $(NF-1) " " $NF}'
fi

# Check logs
echo ""
echo "==============================================================================="
echo "📝 Recent Log Activity (last 5 minutes):"
echo "==============================================================================="

GREYHOUND_LOGS="/Users/clairegrady/RiderProjects/betfair/greyhound-simulated/lay_betting/dog_lay_*.log"
HORSE_LOGS="/Users/clairegrady/RiderProjects/betfair/horse-simulated/lay_betting/horse_lay_*.log"

# Find most recently updated log
LATEST_LOG=$(ls -t $GREYHOUND_LOGS $HORSE_LOGS 2>/dev/null | head -1)

if [ -n "$LATEST_LOG" ]; then
    echo ""
    echo "Most recent activity in: $(basename $LATEST_LOG)"
    echo "Last 3 lines:"
    tail -3 "$LATEST_LOG" | sed 's/^/  /'
else
    echo "No log files found"
fi

echo ""
echo "==============================================================================="
echo ""
echo "💡 Commands:"
echo "  Start all:  ./start_all_simulations.sh"
echo "  Stop all:   ./stop_all_simulations.sh"
echo "  Monitor:    ./monitor_simulations.sh"
echo ""
echo "  View logs:  tail -f greyhound-simulated/lay_betting/dog_lay_1.log"
echo "              tail -f horse-simulated/lay_betting/horse_lay_1.log"
echo ""
