# Horse Racing Paper Trading System

## Overview
Market-based paper trading system for Australian horse racing PLACE bets. No machine learning - just pure market pattern analysis.

## Strategy
**Bet on ALL horses with odds between 1.5-3.0 to PLACE**

Based on analysis of 17,446 historical races:
- **1.5-2.0 odds**: +3.96% ROI, 61.6% place rate
- **2.0-3.0 odds**: +6.92% ROI, 48.7% place rate
- **Overall expected ROI**: ~5%

Uses tiered Kelly staking (25% Kelly fraction) based on proven edges.

## Files

### Active Scripts
- `paper_trading.py` - Main paper trading system (monitors races, places bets)
- `check_results.py` - Check and settle bet results
- `race_times_scraper.py` - Scrape race times from racenet.com.au
- `backtest_market_strategy.py` - Backtest the market strategy on historical data
- `live_feature_lookup.py` - Helper for looking up horse features

### Databases
- `paper_trades.db` - Paper bet records
- `race_times.db` - Scraped race schedules
- `horse_racing_ml.db` - Combined historical data (161K horses, Jan 2024 - Nov 2025)

## Setup

1. **Activate virtual environment:**
```bash
source venv/bin/activate
```

2. **Run scraper to get today's races:**
```bash
python race_times_scraper.py
```

3. **Start paper trading:**
```bash
python paper_trading.py
```

4. **Check results after races complete:**
```bash
python check_results.py
```

## How It Works

1. **Scraper** gets race times from racenet.com.au and stores in `race_times.db`
2. **Backend** (C# service in `/Betfair/Betfair-Backend/`) queries Betfair API and stores market data
3. **Paper trading** monitors upcoming races and:
   - Gets current PLACE market odds from backend API
   - Finds ALL horses with odds 1.5-3.0
   - Calculates Kelly stakes based on proven edges
   - Records bets in `paper_trades.db`
4. **Check results** queries final results and calculates P&L

## Configuration

Edit `paper_trading.py`:
- `PAPER_BANKROLL` - Starting bankroll (default: $10,000)
- `KELLY_FRACTION` - Kelly fraction (default: 0.25 = 25%)
- `MINUTES_BEFORE_RACE` - Betting window (default: 2 mins)

## Requirements

See `requirements.txt`. Key dependencies:
- pandas
- requests
- sqlite3
- xgboost (legacy, not currently used)
- scikit-learn (legacy, not currently used)

## Backend Requirement

Requires C# backend running on `http://localhost:5173` with endpoints:
- `/api/horse-racing/market-book/{marketId}` - Get live odds

Backend code: `/Betfair/Betfair-Backend/`
