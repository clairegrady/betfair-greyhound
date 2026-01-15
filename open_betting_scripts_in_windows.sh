#!/bin/bash
################################################################################
# Open All Betting Scripts in Separate Terminal Windows
# Opens 8 greyhound + 18 horse betting scripts in separate windows
# WARNING: This creates 26 windows - use tabs version instead!
################################################################################

BASE_DIR="/Users/clairegrady/RiderProjects/betfair"

echo "======================================================================="
echo "⚠️  WARNING: This will open 26 SEPARATE WINDOWS!"
echo "======================================================================="
echo ""
echo "This is NOT recommended - use open_betting_scripts_in_tabs.sh instead!"
echo ""
echo "Press Ctrl+C to cancel, or type 'yes' to continue anyway:"
read -r response

if [ "$response" != "yes" ]; then
    echo "Cancelled. Use: ./open_betting_scripts_in_tabs.sh instead"
    exit 0
fi

echo ""
echo "Opening 26 windows..."
echo ""

# Greyhound scripts (8 windows)
for i in {1..8}; do
    osascript <<EOF
tell application "Terminal"
    do script "cd '$BASE_DIR/greyhound-predictor' && venv/bin/python lay_betting/lay_position_${i}.py"
end tell
EOF
    echo "Opened greyhound position $i"
    sleep 0.5
done

# Horse scripts (18 windows)
for i in {1..18}; do
    osascript <<EOF
tell application "Terminal"
    do script "cd '$BASE_DIR/horse-racing-predictor' && venv/bin/python lay_betting/lay_position_${i}.py"
end tell
EOF
    echo "Opened horse position $i"
    sleep 0.5
done

echo ""
echo "======================================================================="
echo "✅ All 26 betting scripts opened in separate windows!"
echo "======================================================================="
echo ""
echo "To stop all scripts:"
echo "  pkill -f 'lay_position'"
echo ""
