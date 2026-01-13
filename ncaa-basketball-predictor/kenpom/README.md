# KenPom Betting System

Automated betting system using KenPom's 77% accurate predictions for NCAA basketball.

## 🎯 Performance

- **KenPom Accuracy**: 77.05% (validated on 2,431 games from 25-26 season)
- **Strategy**: Kelly Criterion staking with confidence-based tiers
- **Edge Requirement**: Minimum 5% edge to place bet

## 📊 Confidence Tiers

| Tier | Confidence | Historical Accuracy | Kelly Fraction | Use Case |
|------|------------|-------------------|----------------|----------|
| **High** | 75-100% | ~85%+ | 10% | Best bets |
| **Medium** | 60-75% | ~75%+ | 5% | Good value |
| **Low** | 52-60% | ~70% | 2% | Small edges |

## 🚀 Usage

### 1. Daily Paper Trading

```bash
# Fetch KenPom predictions and place bets
python3 kenpom/paper_trading.py
```

This will:
- Scrape KenPom's predictions for today/tomorrow
- Calculate edges vs market odds (from your C# backend)
- Place paper trades using Kelly Criterion
- Store in SQLite database

### 2. Check Results

```bash
# Settle completed games
python3 kenpom/check_results.py
```

This will:
- Scrape actual game results from KenPom
- Settle all pending paper trades
- Calculate profit/loss
- Display overall statistics

### 3. Manual Prediction Scraping

```bash
# Just fetch predictions without betting
python3 kenpom/scrape_predictions.py
```

## 📁 Files

- `scrape_predictions.py` - KenPom predictions scraper
- `paper_trading.py` - Main betting system with Kelly Criterion
- `check_results.py` - Results checker and trade settler
- `kenpom_paper_trades.db` - SQLite database for trades
- `kenpom_predictions.json` - Latest scraped predictions

## 🔧 Backend Integration

The system expects your C# backend at `http://localhost:5173` with endpoint:

```
GET /api/ncaa/odds?home={team}&away={team}
```

Response:
```json
{
  "home_moneyline_odds": 1.50,
  "away_moneyline_odds": 2.50
}
```

## 💰 Betting Logic

### Edge Calculation
```
Edge = KenPom Probability - Market Implied Probability
```

### Kelly Criterion
```
Stake = Bankroll × Kelly Fraction × [(odds - 1) × p - (1 - p)] / (odds - 1)
```

Where:
- `p` = KenPom confidence / 100
- Fractional Kelly used for risk management
- Maximum 5% of bankroll per bet
- Minimum $10 stake

## 📈 Expected Performance

Based on KenPom's 77% accuracy and assuming fair odds:
- **Win Rate**: 77%
- **Expected ROI**: 5-10% (depending on edge found)
- **Variance**: Lower than our ML model due to proven track record

## ⚠️ Notes

1. **KenPom Login Required**: Set credentials in `config.env`:
   ```
   KENPOM_EMAIL=your_email
   KENPOM_PASSWORD=your_password
   ```

2. **Rate Limiting**: KenPom scraper includes delays to be respectful

3. **Paper Trading Only**: This is for testing before live betting

4. **Odds Required**: System needs live odds from your backend to calculate edges

## 🔄 Automation

Set up cron jobs:

```bash
# Place bets daily at 9 AM
0 9 * * * cd /path/to/ncaa-basketball-predictor && python3 kenpom/paper_trading.py

# Check results daily at 11 PM
0 23 * * * cd /path/to/ncaa-basketball-predictor && python3 kenpom/check_results.py
```

## 📊 Database Schema

```sql
CREATE TABLE paper_trades (
    id INTEGER PRIMARY KEY,
    game_date TEXT,
    home_team TEXT,
    away_team TEXT,
    kenpom_predicted_winner TEXT,
    kenpom_confidence INTEGER,
    kenpom_margin REAL,
    bet_type TEXT,
    selection TEXT,
    odds REAL,
    stake REAL,
    edge REAL,
    placed_at TIMESTAMP,
    result TEXT,              -- 'won', 'lost', or NULL
    profit REAL,
    settled_at TIMESTAMP
);
```

## 🎓 Why KenPom Instead of Our Model?

| Metric | KenPom | Our Model |
|--------|--------|-----------|
| Accuracy | **77.05%** | 69.8% |
| Development Time | 20+ years | 2 weeks |
| Data Quality | Premium | 80% coverage |
| Track Record | Proven | Unproven |
| **ROI Potential** | **Higher** | Lower |

**Bottom Line**: Use the proven system. KenPom has already done the hard work.
