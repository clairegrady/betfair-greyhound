#!/bin/bash
# NCAA Basketball Paper Trading - Quick Start Script

echo "=============================================================="
echo "NCAA BASKETBALL PAPER TRADING - QUICK START"
echo "=============================================================="

cd /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor

# Check if backend is running
echo ""
echo "1. Checking backend status..."
if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend is running"
else
    echo "   ⚠️ Backend is not running!"
    echo "   Start it with: cd ../Betfair/Betfair-Backend && dotnet run"
    exit 1
fi

# Test the system
echo ""
echo "2. Testing system components..."
python3 test_paper_trading_system.py
if [ $? -ne 0 ]; then
    echo "   ❌ System test failed!"
    exit 1
fi

# Update lineups
echo ""
echo "3. Updating lineups for upcoming games..."
python3 pipelines/update_live_lineups.py 8

# Run paper trading
echo ""
echo "4. Running paper trading..."
python3 paper_trading_ncaa.py \
    --hours 8 \
    --min-edge 0.05 \
    --min-confidence 0.6 \
    --bankroll 1000

# Show results
echo ""
echo "5. Current paper trading status:"
sqlite3 paper_trades_ncaa.db "
SELECT 
    COUNT(*) as total_trades,
    COUNT(CASE WHEN is_settled = 0 THEN 1 END) as pending,
    COUNT(CASE WHEN is_settled = 1 THEN 1 END) as settled,
    ROUND(SUM(stake_amount), 2) as total_staked,
    ROUND(SUM(CASE WHEN is_settled = 1 THEN profit_loss ELSE 0 END), 2) as total_pl
FROM paper_trades;
"

echo ""
echo "=============================================================="
echo "✅ Paper trading complete!"
echo "=============================================================="
echo ""
echo "To monitor continuously:"
echo "  watch -n 300 './quick_start.sh'  # Run every 5 minutes"
echo ""
echo "To view recent trades:"
echo "  sqlite3 paper_trades_ncaa.db 'SELECT * FROM paper_trades ORDER BY timestamp DESC LIMIT 5;'"

