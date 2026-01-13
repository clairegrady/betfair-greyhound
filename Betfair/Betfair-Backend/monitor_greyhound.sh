#!/bin/bash
# Monitor greyhound activity in the backend logs

echo "🔍 Monitoring Greyhound Backend Activity..."
echo "=========================================="
echo ""

# Clear the log file to start fresh
> backend.log

# Start the backend in the background
dotnet run > backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo ""

# Wait for backend to initialize
echo "⏳ Waiting for backend to initialize (10 seconds)..."
sleep 10
echo ""

# Monitor for 2 minutes and show greyhound-related activity
echo "📊 Monitoring for 120 seconds..."
echo "=========================================="
timeout 120 tail -f backend.log | grep --line-buffered -i -E "(greyhound|Processing event:|Got.*market|Cached.*runner|RunnerName)" &
TAIL_PID=$!

# Wait for the timeout
sleep 120

# Show summary
echo ""
echo "=========================================="
echo "📈 Summary"
echo "=========================================="
echo ""
echo "🔍 Greyhound events processed:"
grep -c "Processing event:" backend.log 2>/dev/null || echo "0"
echo ""
echo "🔍 Market catalogues fetched:"
grep -c "Got.*market catalogues" backend.log 2>/dev/null || echo "0"
echo ""
echo "🔍 Runner names cached:"
grep -c "Cached.*runner names" backend.log 2>/dev/null || echo "0"
echo ""
echo "🔍 Greyhound market books inserted:"
grep -c "Successfully inserted.*greyhound" backend.log 2>/dev/null || echo "0"
echo ""

# Check database
echo "📊 Database Check:"
echo "  Markets in GreyhoundMarketBook:"
sqlite3 betfairmarket.sqlite "SELECT COUNT(DISTINCT MarketId) FROM GreyhoundMarketBook WHERE EventName LIKE '%13th Jan%';" 2>/dev/null || echo "  Error querying database"
echo ""
echo "  Markets with runner names:"
sqlite3 betfairmarket.sqlite "SELECT COUNT(DISTINCT MarketId) FROM GreyhoundMarketBook WHERE EventName LIKE '%13th Jan%' AND RunnerName IS NOT NULL AND RunnerName != '';" 2>/dev/null || echo "  Error querying database"
echo ""

echo "✅ Monitoring complete. Backend still running (PID: $BACKEND_PID)"
echo "   To view full logs: tail -f backend.log"
echo "   To stop backend: kill $BACKEND_PID"
