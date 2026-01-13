# Phase 2: Multi-Task Neural Network - COMPLETE ✅

## Training Results

**Model:** Multi-Task Neural Network (PyTorch)
- **Architecture:** Shared layers [256, 128, 64] with 3 task-specific heads
- **Total Parameters:** 57,351
- **Training Data:** 1,311 games (23-24 season)
- **Validation Data:** 776 games (23-24 season)
- **Test Data:** 92 games (23-24 tournament)

### Test Set Performance

| Metric | Value |
|--------|-------|
| **Winner Accuracy** | 53.3% |
| **Margin MAE** | 11.56 points |
| **Totals MAE** | 21.08 points |
| **Total Loss** | 3.76 |

### Model Capabilities

The multi-task model predicts:

1. **Winner (Binary Classification)**
   - Probability of home team winning (0-1)
   - 53.3% accuracy on tournament games

2. **Point Margin (Quantile Regression)**
   - 10th, 50th, 90th percentile predictions
   - Confidence intervals for margin prediction
   - MAE: 11.56 points

3. **Total Points (Quantile Regression)**
   - 10th, 50th, 90th percentile predictions
   - Confidence intervals for total prediction
   - MAE: 21.08 points

### Confidence Scoring

The model provides confidence levels based on quantile spread:
- **Narrow spread** → High confidence
- **Wide spread** → Low confidence

This is critical for Kelly Criterion bet sizing in paper trading.

---

## Files Created

1. **`pipelines/train_multitask_model.py`**
   - Training script for multi-task neural network
   - Time-based train/val/test split
   - Early stopping with patience
   - Saves best model and results

2. **`models/multitask_model_best.pth`**
   - Trained model checkpoint
   - Includes scaler parameters and feature columns
   - Ready for inference

3. **`models/multitask_results.json`**
   - Test set metrics
   - Training configuration
   - Dataset sizes

4. **`pipelines/update_live_lineups.py`**
   - Fetches lineups from ESPN API
   - Updates database before paper trading
   - Handles games in the next N hours

5. **`paper_trading_ncaa.py`**
   - Complete paper trading script
   - Loads XGBoost + Multi-task models
   - Updates lineups before prediction
   - Kelly Criterion bet sizing
   - Saves trades to database

---

## What's Next

### Phase 3: Ensemble & Calibration (Optional)
- Weighted ensemble of XGBoost + Multi-task
- Isotonic calibration for better probability estimates
- Backtest different ensemble weights

### Phase 4: Paper Trading Deployment
1. **Backend API Endpoints** (C#)
   - `/api/ncaa/upcoming` - Get upcoming games
   - `/api/ncaa/odds/{gameId}` - Get Betfair odds
   - Already implemented in Betfair-Backend

2. **Automated Paper Trading**
   - Run `paper_trading_ncaa.py` on schedule (e.g., every 2 hours)
   - Update lineups 1 hour before game time
   - Place paper trades when edge > threshold

3. **Results Tracking**
   - Monitor paper trades in `paper_trades_ncaa.db`
   - Calculate ROI, win rate, average edge
   - Compare against baseline (random, always favorite, etc.)

---

## Usage

### Train Multi-Task Model
```bash
cd /Users/clairegrady/RiderProjects/betfair/ncaa-basketball-predictor
python3 pipelines/train_multitask_model.py
```

### Update Lineups for Upcoming Games
```bash
python3 pipelines/update_live_lineups.py <hours_ahead>
```

### Run Paper Trading
```bash
python3 paper_trading_ncaa.py --hours 8 --min-edge 0.05 --min-confidence 0.6 --bankroll 1000
```

Options:
- `--hours`: Look ahead window (default: 8)
- `--min-edge`: Minimum edge required to bet (default: 0.05 = 5%)
- `--min-confidence`: Minimum margin confidence (default: 0.6 = 60%)
- `--bankroll`: Starting bankroll for Kelly sizing (default: $1000)

---

## Key Improvements from Phase 1

1. **Multi-Task Learning**
   - Single model for winner, margin, and totals
   - Shared representations improve all tasks
   - Confidence intervals via quantile regression

2. **Lineup Integration**
   - Automatic lineup updates before prediction
   - Features include player ratings and bench depth
   - Handles lineup changes and injuries

3. **Advanced Bet Sizing**
   - Kelly Criterion for optimal stake calculation
   - Edge-based filtering (only bet with >5% edge)
   - Confidence-based filtering (only bet with >60% confidence)

4. **Enterprise-Grade Paper Trading**
   - Complete trade tracking in SQLite
   - Timestamps, odds, predictions, confidence stored
   - Ready for P&L calculation and backtesting

---

## Model Limitations & Future Work

### Current Limitations
1. **Test accuracy of 53.3%** is close to random (50%)
   - Need more training data (currently only 1,311 games)
   - Consider including earlier seasons (2022-23, 2021-22)
   - Add more features (recent form, rest days, home court)

2. **Margin/Totals MAE still high**
   - Margin MAE of 11.56 points (typical margin is ±10)
   - Totals MAE of 21.08 points (typical total is ~145)
   - May need more sophisticated features

3. **Limited lineup data**
   - Only 96.7% of games have lineup data
   - Missing lineups could hurt predictions

### Potential Improvements
1. **Data Augmentation**
   - Scrape more historical seasons
   - Add advanced stats (shot distribution, defensive schemes)
   - Include referee data (impacts totals)

2. **Feature Engineering**
   - Recent form (last 5/10 games)
   - Rest days / travel distance
   - Conference strength
   - Tournament context (elimination pressure)

3. **Model Architecture**
   - Add attention layers for player importance
   - Try larger models (more hidden units)
   - Experiment with residual connections

4. **Ensemble Methods**
   - Weighted average of XGBoost + Neural Network
   - Stacking with meta-learner
   - Bayesian model averaging

---

## Status: READY FOR PAPER TRADING ✅

All components are in place:
- ✅ Multi-task model trained and saved
- ✅ Lineup update script working
- ✅ Paper trading script complete
- ✅ Kelly Criterion bet sizing implemented
- ✅ Backend API ready (C#)

**Next Step:** Start paper trading and monitor results!

