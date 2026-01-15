#!/bin/bash
# Continuously monitor all 26 lay betting scripts

while true; do
    clear
    echo "═══════════════════════════════════════════════════════════════════"
    echo "🎯 LAY BETTING MONITOR - All 26 Scripts (Auto-refresh every 5s)"
    echo "═══════════════════════════════════════════════════════════════════"
    echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Check how many are running
    RUNNING=$(ps aux | grep "lay_position" | grep -v grep | wc -l | tr -d ' ')
    
    if [ "$RUNNING" -eq "26" ]; then
        echo "📊 Scripts Running: ✅ $RUNNING / 26"
    else
        echo "📊 Scripts Running: ⚠️  $RUNNING / 26"
    fi
    echo ""

    if [ "$RUNNING" -eq "0" ]; then
        echo "❌ No scripts are running!"
        echo ""
        echo "To start all scripts, run:"
        echo "   cd /Users/clairegrady/RiderProjects/betfair"
        echo "   for i in {1..8}; do cd greyhound-predictor/lay_betting && venv/bin/python lay_position_\$i.py > dog_lay_\$i.log 2>&1 & done"
        echo ""
        echo "Press Ctrl+C to exit"
        sleep 5
        continue
    fi

    echo "───────────────────────────────────────────────────────────────────"
    echo "🐕 GREYHOUND SCRIPTS (Last 2 lines):"
    echo "───────────────────────────────────────────────────────────────────"

    for i in {1..8}; do
        LOG="/Users/clairegrady/RiderProjects/betfair/greyhound-predictor/lay_betting/dog_lay_$i.log"
        if [ -f "$LOG" ]; then
            LAST_LINE=$(tail -1 "$LOG" 2>/dev/null | cut -c 1-80)
            if [ -n "$LAST_LINE" ]; then
                echo "▶ dog_lay_$i: $LAST_LINE"
            fi
        fi
    done

    echo ""
    echo "───────────────────────────────────────────────────────────────────"
    echo "🐴 HORSE SCRIPTS (Last 2 lines):"
    echo "───────────────────────────────────────────────────────────────────"

    for i in {1..18}; do
        LOG="/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/lay_betting/horse_lay_$i.log"
        if [ -f "$LOG" ]; then
            LAST_LINE=$(tail -1 "$LOG" 2>/dev/null | cut -c 1-80)
            if [ -n "$LAST_LINE" ]; then
                echo "▶ horse_lay_$i: $LAST_LINE"
            fi
        fi
    done

    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "💡 Press Ctrl+C to stop monitoring"
    echo "💡 To view a specific log: tail -f <path_to_log>"
    echo "💡 To stop all scripts: pkill -f 'lay_position'"
    echo "═══════════════════════════════════════════════════════════════════"
    
    sleep 5
done
