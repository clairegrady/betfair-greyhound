#!/bin/bash
################################################################################
# Open All Betting Scripts in Separate Terminal Tabs
# Opens 8 greyhound + 18 horse betting scripts in new Terminal tabs
################################################################################

BASE_DIR="/Users/clairegrady/RiderProjects/betfair"

echo "======================================================================="
echo "🚀 Opening All 26 Betting Scripts in Terminal Tabs"
echo "======================================================================="
echo ""
echo "This will open a new Terminal window with 26 tabs:"
echo "  - 8 greyhound betting scripts"
echo "  - 18 horse betting scripts"
echo ""
echo "Press Ctrl+C to cancel, or wait 3 seconds to continue..."
sleep 3
echo ""

# Create AppleScript to open Terminal tabs
osascript <<EOF
-- Create new Terminal window
tell application "Terminal"
    activate
    
    -- First tab (greyhound position 1)
    do script "cd '$BASE_DIR/greyhound-predictor' && venv/bin/python lay_betting/lay_position_1.py"
    
    -- Greyhound positions 2-8
    repeat with i from 2 to 8
        tell application "System Events" to keystroke "t" using command down
        delay 0.5
        do script "cd '$BASE_DIR/greyhound-predictor' && venv/bin/python lay_betting/lay_position_" & i & ".py" in front window
    end repeat
    
    -- Horse positions 1-18
    repeat with i from 1 to 18
        tell application "System Events" to keystroke "t" using command down
        delay 0.5
        do script "cd '$BASE_DIR/horse-racing-predictor' && venv/bin/python lay_betting/lay_position_" & i & ".py" in front window
    end repeat
end tell
EOF

echo ""
echo "======================================================================="
echo "✅ All 26 betting scripts opened in Terminal tabs!"
echo "======================================================================="
echo ""
echo "Tips:"
echo "  - Switch between tabs: Cmd+Shift+[ or Cmd+Shift+]"
echo "  - Close a tab: Cmd+W"
echo "  - View all tabs: Click the tab bar"
echo ""
echo "To stop all scripts:"
echo "  pkill -f 'lay_position'"
echo ""
