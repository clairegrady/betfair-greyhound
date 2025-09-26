# Betting Simulation System

This system provides automated betting simulation and results analysis for horse racing markets.

## Files Overview

### 1. `betting_simulation.py`
**Main simulation engine that places simulated bets on Australian horse races.**

**Features:**
- Monitors Australian races from the `race_times` table
- Places bets 1 minute before race start (up to 2 minutes after)
- Implements 5 different betting strategies:
  - Strategy 1: Bet $1 on favorite to win and place
  - Strategy 2: Bet $1 on top 2 horses to win and place  
  - Strategy 3: Bet $1 on top 3 horses to win and place
  - Strategy 4: Bet $1 on top 4 horses to win and place
  - Strategy 5: If favorite odds ≤ 60% of 2nd favorite, bet $10 on favorite to win
- Stores all bets in `simulation_results` table
- Prevents duplicate betting on same race
- Uses real-time odds from `CurrentOdds` table

**Usage:**
```bash
python betting_simulation.py
```

### 2. `betfair_results_fetcher.py`
**Fetches settled race results from Betfair API and stores them in the database.**

**Features:**
- Calls `/api/results/settled` endpoint to get settled market data
- Parses winner/loser status from Betfair API response
- Stores race results in `race_results` table
- Stores horse results in `horse_results` table
- Matches results with simulation bets by market ID

**Usage:**
```python
from betfair_results_fetcher import BetfairResultsFetcher

fetcher = BetfairResultsFetcher()
market_ids = ["1.248194824", "1.248195256"]  # Your market IDs
results = fetcher.fetch_results(market_ids)
```

### 3. `simulation_results_analyzer.py`
**Analyzes simulation performance and exports metrics to CSV.**

**Features:**
- Calculates win rate, total profit/loss, total liability, ROI
- Matches simulation bets with actual race results
- Calculates P&L for each bet based on finishing position
- Exports performance metrics by race to CSV
- Provides summary statistics

**Usage:**
```bash
python simulation_results_analyzer.py
```

## Database Schema

### `simulation_results` table
Stores all simulated bets:
- `market_id`, `venue`, `race_number`, `race_date`
- `strategy`, `horse_name`, `bet_type` (win/place)
- `win_odds`, `place_odds`, `stake`

### `race_results` table  
Stores race information:
- `venue`, `race_number`, `race_date`, `race_name`

### `horse_results` table
Stores horse finishing positions:
- `race_id`, `finishing_position`, `horse_name`, `starting_price`

## Workflow

1. **Run Simulation**: Execute `betting_simulation.py` to place bets on live races
2. **Wait for Results**: Let races finish and results become available
3. **Fetch Results**: Run `betfair_results_fetcher.py` to get settled results
4. **Analyze Performance**: Run `simulation_results_analyzer.py` to calculate metrics

## Output

The analyzer exports a CSV with the following columns:
- `venue`, `race_number`, `race_date`
- `total_stake`, `total_profit_loss`, `total_liability`
- `win_rate`, `place_rate`, `roi`
- `num_bets`

## Requirements

- Backend API running on `http://localhost:5173`
- SQLite databases: `betting_simulation.sqlite`, `betting_history.sqlite`, `live_betting.sqlite`
- Python packages: `requests`, `pandas`, `sqlite3`

## Notes

- The system only processes Australian races (country = 'AUS' in race_times)
- Results are fetched from Betfair's settled market API
- Place odds are estimated as 1/4 of win odds for positions 1-3, 1/5 for position 4
- The system prevents duplicate betting on the same race
