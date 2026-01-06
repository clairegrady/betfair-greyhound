# NCAA Basketball Multi-Task Prediction Model
## Design Document

### Current Data Status
- **12,420 games** with complete scores (excellent dataset!)
- **421 teams** tracked
- **726 KenPom ratings** (advanced metrics)
- **Average total points**: 146 points per game
- **Average margin**: 14.4 points

### Prediction Targets

#### 1. Winner (Classification)
- Binary: Home Win (1) or Away Win (0)
- Current model already does this

#### 2. Point Margin (Regression with Confidence)
- **Point Estimate**: Predicted margin (e.g., +12.5 for home team)
- **Quantile Predictions**:
  - 10th percentile: Lower bound (conservative)
  - 50th percentile: Median prediction
  - 90th percentile: Upper bound (optimistic)
- **Confidence Level**: Width of prediction interval
  - Narrow interval = High confidence
  - Wide interval = Low confidence

**Example Output:**
```
Home team margin: +14.5 points
10th percentile: +8.2 (worst case: home wins by 8)
90th percentile: +20.8 (best case: home wins by 21)
Confidence: 80% (interval width = 12.6 points)
```

#### 3. Total Points (Regression with Confidence)
- **Point Estimate**: Combined score (e.g., 152.5 total points)
- **Quantile Predictions**: Same as margin
- **Confidence Level**: Interval width

**Example Output:**
```
Total points: 152.5
10th percentile: 145.2 (low-scoring game)
90th percentile: 159.8 (high-scoring game)
Confidence: 85% (interval width = 14.6 points)
```

### Model Architecture

```
Input Features (same as current model):
├── Team Stats (KenPom: efficiency, tempo, etc.)
├── Recent Form (last 5 games)
├── Head-to-Head History
├── Home/Away splits
├── Injuries & Lineups
└── Four Factors (eFG%, TOV%, ORB%, FTR)

↓

Shared Feature Layers:
├── Dense Layer 1: 256 units, ReLU, Dropout(0.3)
├── Dense Layer 2: 128 units, ReLU, Dropout(0.3)
└── Dense Layer 3: 64 units, ReLU, Dropout(0.2)

↓

Three Task-Specific Heads:

┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  Winner Head        │  │  Margin Head        │  │  Totals Head        │
│  ───────────        │  │  ───────────        │  │  ───────────        │
│  Dense: 32 units    │  │  Dense: 32 units    │  │  Dense: 32 units    │
│  Output: Sigmoid    │  │  Output: Linear x3  │  │  Output: Linear x3  │
│  (probability)      │  │  (10th, 50th, 90th) │  │  (10th, 50th, 90th) │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### Loss Function (Multi-Task)

```python
total_loss = (
    α * binary_crossentropy(winner_true, winner_pred) +          # Winner classification
    β * quantile_loss(margin_true, margin_preds, quantiles) +   # Margin quantiles
    γ * quantile_loss(totals_true, totals_preds, quantiles)     # Totals quantiles
)
```

**Loss weights** (α, β, γ):
- α = 0.3 (winner is important but less profitable)
- β = 0.4 (margins are very profitable - spread betting)
- γ = 0.3 (totals are profitable - over/under betting)

### Training Strategy

1. **Data Preparation**:
   - Split: 80% train, 10% validation, 10% test
   - Time-based split (older games = train, recent = test)
   - Calculate margin: `home_score - away_score`
   - Calculate totals: `home_score + away_score`

2. **Feature Engineering** (already done):
   - All current features work for all 3 tasks
   - Add: Pace differential (affects totals)
   - Add: Defensive efficiency spread (affects margins)

3. **Training**:
   - Optimizer: Adam with learning rate schedule
   - Batch size: 128
   - Epochs: 100-200 with early stopping
   - Monitor: Combined validation loss

4. **Quantile Loss Implementation**:
```python
def quantile_loss(y_true, y_pred, quantile):
    error = y_true - y_pred
    return torch.mean(torch.max(quantile * error, (quantile - 1) * error))
```

### Confidence Calculation

For each prediction:
```python
confidence = 1 - ((q90 - q10) / expected_range)

# Example for margin:
# If q90 - q10 = 8 points (narrow), confidence = 90%
# If q90 - q10 = 25 points (wide), confidence = 60%
```

### Betting Strategy Integration

**Paper Trading Rules**:

1. **Margin Bets**:
   - Only bet if confidence > 75%
   - Bet size scales with confidence
   - Compare predicted margin to Betfair spread

2. **Totals Bets**:
   - Only bet if confidence > 70%
   - Over if prediction > line + 3 points
   - Under if prediction < line - 3 points

3. **Winner Bets** (keep current logic):
   - Only bet if odds imply <predicted probability
   - Kelly Criterion for bet sizing

### Data Requirements - Current Status

✅ **We have enough data!**
- 12,420 games is excellent (horse racing typically uses 5K-10K races)
- Multiple seasons of historical data
- Rich feature set (KenPom, four factors, etc.)

**Optional improvements** (not required):
- More recent games (2024-2025 season in progress)
- Player-level stats (injuries impact margins/totals more than winners)
- Betting market history (to calibrate confidence against actual odds)

### Implementation Files

```
ncaa-basketball-predictor/
├── models/
│   └── multitask_model.py          # NEW: Multi-task architecture
├── pipelines/
│   ├── prepare_multitask_data.py   # NEW: Prepare margin & totals targets
│   └── train_multitask_model.py    # NEW: Training script
├── paper_trading_multitask.py      # NEW: Enhanced paper trading
└── MULTITASK_MODEL_DESIGN.md       # THIS FILE
```

### Expected Performance

Based on 12,420 games:

**Winner Prediction**:
- Accuracy: 70-75% (current model baseline)

**Margin Prediction**:
- MAE: 8-10 points (median absolute error)
- 80% confidence intervals should contain true margin ~80% of time

**Totals Prediction**:
- MAE: 10-12 points
- 80% confidence intervals should contain true total ~80% of time

**Profitable Betting**:
- Only bet when confidence > 75% and edge > 3%
- Expected ROI: 5-8% (vs. -5% for random betting)

### Next Steps

1. ✅ Design document (THIS FILE)
2. Create data preparation script (safe - read-only)
3. Implement multi-task model architecture (safe - new file)
4. Create training script (safe - new file)
5. WAIT for horse racing training to complete
6. Train multi-task model
7. Integrate with paper trading
8. Test on live markets

---

**Status**: Design complete, ready to implement when training finishes.
**Risk**: LOW - all new files, no changes to existing horse racing code.

