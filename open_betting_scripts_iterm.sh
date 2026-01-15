#!/bin/bash
################################################################################
# Open Betting Scripts in iTerm2 Tabs (If you use iTerm)
# Opens 8 greyhound + 18 horse betting scripts in iTerm tabs
################################################################################

BASE_DIR="/Users/clairegrady/RiderProjects/betfair"

echo "======================================================================="
echo "🚀 Opening All 26 Betting Scripts in iTerm2 Tabs"
echo "======================================================================="
echo ""

# Check if iTerm2 is installed
if ! osascript -e 'id of application "iTerm"' &>/dev/null; then
    echo "❌ iTerm2 not found! Use Terminal version instead:"
    echo "   ./open_betting_scripts_in_tabs.sh"
    exit 1
fi

echo "Opening in iTerm2..."
echo ""

# Create iTerm tabs for all scripts
osascript <<EOF
tell application "iTerm"
    activate
    
    -- Create new window
    create window with default profile
    
    tell current session of current window
        -- First greyhound script
        write text "cd '$BASE_DIR/greyhound-predictor' && venv/bin/python lay_betting/lay_position_1.py"
    end tell
    
    -- Greyhound positions 2-8
    repeat with i from 2 to 8
        tell current window
            create tab with default profile
            tell current session
                write text "cd '$BASE_DIR/greyhound-predictor' && venv/bin/python lay_betting/lay_position_" & i & ".py"
            end tell
        end tell
    end repeat
    
    -- Horse positions 1-18
    repeat with i from 1 to 18
        tell current window
            create tab with default profile
            tell current session
                write text "cd '$BASE_DIR/horse-racing-predictor' && venv/bin/python lay_betting/lay_position_" & i & ".py"
            end tell
        end tell
    end repeat
end tell
EOF

echo ""
echo "======================================================================="
echo "✅ All 26 betting scripts opened in iTerm2 tabs!"
echo "======================================================================="
echo ""
