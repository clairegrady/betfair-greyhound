# 🏀 NCAA BASKETBALL BETTING SYSTEM - ML TRAINING PLAN
## Enterprise-Grade Prediction Pipeline

---

## 🎯 OBJECTIVE

Build a **multi-output ensemble model** that predicts:
1. **Winner** (binary classification with probability)
2. **Point Margin** (regression with confidence intervals)
3. **Total Points** (regression with confidence intervals)

**Target Performance:**
- Win rate: >58% (beat closing line)
- ROI: 7-10% sustained over 100+ bets
- Sharp line detection: Bet before odds move

---

## 📊 CURRENT DATA INVENTORY

### ✅ What We Have:
- **12,784 historical games** (2024, 2025, 2026 seasons)
  - Final scores, dates, home/away, neutral sites
- **4,168 players** (Season 2025) with KenPom advanced metrics
- **3,382 players** (Season 2026) with KenPom advanced metrics
- **~5,000 players** with Sports Reference per-game stats (in progress)
- **Team efficiency ratings** (KenPom)
- **Betfair market data** (51,346 odds records, 136 markets)

### ⚠️ CRITICAL GAP: Lineup Data

**Current Issue:**
We have season-level player stats but DON'T know:
- Who actually started each game
- Who was injured/suspended
- Minutes distribution per game
- Bench vs starters split

**Why This Matters:**
```
Example: Duke vs UNC
If Kyle Filipowski (Duke's star) is out:
- Duke win probability: 65% → 42%
- Spread: Duke -4.5 → UNC -2.0
- Total: 148 → 142 (slower pace without him)
```

**Impact on Predictions:**
- Missing 3 starters = -15% to -25% win probability
- Star player out = -8 to -12 point swing
- Key defender out = +5 to +8 total points

---

## 🚨 SOLVING THE LINEUP PROBLEM

### Phase 1: Aggregate Season-Level Features (NOW)
**Use what we have:**
- Team average efficiency (entire roster)
- Top 5 players' average stats (season-long)
- Bench depth metrics (6th-10th players)

**Assumption:** Starting 5 ≈ top 5 players by minutes
**Limitation:** Can't detect game-day injuries

### Phase 2: Historical Lineup Scraping (LATER)
**Sources:**
1. **ESPN Box Scores** - Shows who played, minutes, stats per game
2. **Sports Reference Game Logs** - Starters marked with asterisk
3. **KenPom Game Pages** - Some games have lineup info

**Data to collect:**
```python
{
  'game_id': 401638580,
  'team': 'Duke',
  'starters': ['Kyle Filipowski', 'Jeremy Roach', ...],
  'minutes_played': {'Filipowski': 35, 'Roach': 32, ...},
  'injury_status': {'Player X': 'OUT'},
  'suspension': []
}
```

### Phase 3: Real-Time Lineup Monitoring (PRODUCTION)
**For live betting:**
- Scrape ESPN/CBS 1 hour before tipoff
- Check official team injury reports
- Twitter monitoring for late scratches
- Update predictions dynamically

---

## 🤖 MODEL ARCHITECTURE

### Approach: Multi-Task Ensemble

**Why Multi-Task?**
- Winner, margin, and total points are correlated
- Shared features reduce overfitting
- More efficient than 3 separate models

**Ensemble Components:**

#### Model 1: XGBoost (Primary)
```python
# Three XGBoost models (one per output)
winner_model = XGBClassifier(
    max_depth=6,
    n_estimators=500,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=1.0  # Adjust for home bias
)

margin_model = XGBRegressor(...)
total_model = XGBRegressor(...)
```

**Strengths:**
- Handles non-linear relationships
- Feature importance analysis
- Fast inference
- Good with missing data

#### Model 2: LightGBM (Speed)
```python
# Faster training, similar performance
# Use for rapid experimentation
```

#### Model 3: Neural Network (Multi-Task)
```python
# Shared layers for feature learning
# 3 output heads (winner, margin, total)
input_layer → dense(256) → dropout(0.3) 
           → dense(128) → dropout(0.2)
           ↓              ↓              ↓
     winner_head    margin_head    total_head
     (sigmoid)      (linear)       (linear)
```

**Strengths:**
- Learns complex interactions
- Shared feature representations
- Confidence intervals via dropout

#### Model 4: Logistic Regression (Baseline)
```python
# Simple, interpretable
# Use to validate feature engineering
```

**Final Prediction:**
```python
# Weighted ensemble
winner_prob = (
    0.45 * xgb_winner +
    0.30 * lgbm_winner +
    0.20 * nn_winner +
    0.05 * logreg_winner
)
```

---

## 📐 FEATURE ENGINEERING

### Total Features: ~150-200

### 1. Team Efficiency Features (40 features)
**From KenPom:**
- Offensive/Defensive Efficiency (raw + rank)
- Tempo (possessions per 40 min)
- Four Factors:
  - eFG% (Effective Field Goal %)
  - TO% (Turnover Rate)
  - OR% (Offensive Rebound Rate)
  - FT Rate (Free Throw Rate)
- Strength of Schedule
- Luck Rating (close game performance)

**Derived:**
- Efficiency differential (Team A - Team B)
- Style matchup (fast vs slow, inside vs outside)

### 2. Player Aggregation Features (60 features)

**Starter Quality (Top 5 by minutes):**
- Average Offensive Rating
- Usage Rate (ball dominance)
- Average Minutes Played %
- Shot distribution (2P%, 3P%, FT%)
- Defensive metrics (Blk%, Stl%)
- Height/experience

**Bench Depth (6th-10th players):**
- Bench ORtg vs starters
- Minutes drop-off (starter min - bench min)
- Bench usage rate

**Key Player Impact:**
- Best player's ORtg - team avg
- Top 3 players' minutes % (concentration)
- Star power index (has a 120+ ORtg player?)

**Player-Level Stats (from Sports Reference):**
- Starters' average PPG, RPG, APG
- Scoring distribution (balanced vs one star)

**🚨 LINEUP AVAILABILITY (Phase 2):**
- Number of starters available (0-5)
- Missing starters' cumulative ORtg
- Injury impact score
- Days since injury for returning players

### 3. Recent Form (20 features)
- Last 5 games: Win%, Avg margin, Avg total
- Last 10 games trends
- Home vs away splits (last 5)
- Momentum score (improving or declining)
- Scoring consistency (std dev of last 10 scores)

### 4. Matchup Features (15 features)
- Head-to-head record (last 3 years)
- H2H average margin
- Conference rivalry (Big 10, ACC, SEC, etc.)
- Last meeting outcome (if this season)

### 5. Situational Features (15 features)
- **Home Court Advantage:**
  - Home win% (team-specific)
  - Venue altitude (e.g., Denver)
  - Crowd size/intensity
- **Rest Days:**
  - Days since last game (both teams)
  - Back-to-back games penalty
  - 3 games in 5 days fatigue
- **Travel Distance:**
  - Miles traveled for away team
  - Time zone changes (East→West coast)
- **Game Importance:**
  - Conference game (higher intensity)
  - Tournament game (variance increases)
  - Rivalry game (unpredictable)
  - Late season (seeding implications)

### 6. Temporal Features (10 features)
- Month of season (Nov vs March)
- Days into season
- Pre/post conference play
- Tournament round (if applicable)

### 7. Market Features (10 features)
- **Betfair Odds:**
  - Opening line (initial market)
  - Closing line (sharp money)
  - Line movement (public vs sharp)
  - Implied probability from odds
- **Market Efficiency:**
  - Matched volume (liquidity)
  - Odds vs our prediction (value)

---

## 🔀 DATA SPLITTING STRATEGY

### Critical: Time-Based Splits (NO SHUFFLE!)

**Why?**
- Prevents data leakage (future info → past)
- Mimics real-world prediction (past → future)
- Respects temporal dependencies

### Split Method:

```python
# Season 2025 (2024-25): TRAINING
train_games = games[games['season'] == 2025]  # 6,234 games

# Split 2025 into train/val
train_cutoff = '2025-02-01'  # First 3 months
train_set = train_games[train_games['date'] < train_cutoff]  # ~4,500 games
val_set = train_games[train_games['date'] >= train_cutoff]   # ~1,700 games

# Season 2026 (2025-26): TEST SET
test_set = games[games['season'] == 2026]  # 364 games (so far)

# NEVER train on 2026 data!
```

**Reasoning:**
- **Train:** Early 2024-25 season (build patterns)
- **Validation:** Late 2024-25 season (tune hyperparameters)
- **Test:** Entire 2025-26 season (final evaluation)

### Cross-Validation: Time-Series Aware

```python
# NOT standard k-fold (would leak future data)
# USE: Forward-chaining cross-validation

from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5)
for train_idx, val_idx in tscv.split(train_games):
    # Each fold: train on earlier games, validate on later games
    # Fold 1: Train on 20% → Validate on next 20%
    # Fold 2: Train on 40% → Validate on next 20%
    # Fold 3: Train on 60% → Validate on next 20%
    # Fold 4: Train on 80% → Validate on next 20%
    # Fold 5: Train on all → Final holdout
```

---

## 📊 MODEL OUTPUTS & CALIBRATION

### Output 1: Winner Probability
```python
# XGBoost classifier output
winner_prob = model.predict_proba(X)[:, 1]  # P(Home team wins)

# Calibration check:
# - If model says 70% win prob, team should win 70% of those games
# - Use Platt scaling or isotonic regression if miscalibrated
```

**Calibration Validation:**
```python
from sklearn.calibration import calibration_curve

# Plot predicted vs actual win rates
# Bins: [0-10%, 10-20%, ..., 90-100%]
# If well-calibrated: diagonal line
```

### Output 2: Point Margin (with confidence)
```python
# XGBoost regressor
margin_pred = margin_model.predict(X)  # Expected margin (e.g., Duke by 6.5)

# Confidence interval (quantile regression)
margin_lower = margin_model_10pct.predict(X)  # 10th percentile
margin_upper = margin_model_90pct.predict(X)  # 90th percentile

# Example: Duke by 6.5 ± 8 points (80% confidence)
```

### Output 3: Total Points (with confidence)
```python
total_pred = total_model.predict(X)  # Expected total (e.g., 148 pts)
total_lower = total_model_10pct.predict(X)
total_upper = total_model_90pct.predict(X)

# Example: Total 148 ± 12 points (80% confidence)
```

---

## 🎯 MODEL EVALUATION METRICS

### Classification (Winner):
```python
# Primary metrics
- Accuracy: % correct predictions
- AUC-ROC: Discrimination ability
- Log Loss: Probability calibration quality
- Brier Score: Squared error of probabilities

# Betting-specific
- Win Rate at 55%+ confidence: Should be >60% accurate
- Profit if betting all predictions: +EV?
- Beat closing line %: Are we sharper than market?
```

### Regression (Margin & Total):
```python
# Error metrics
- MAE (Mean Absolute Error): Avg miss in points
- RMSE (Root Mean Squared Error): Penalizes large misses
- R² (Coefficient of Determination): % variance explained

# Betting-specific
- Cover rate against spread: Beat Vegas line?
- Over/Under accuracy: Beat total line?
- Confidence interval coverage: 80% CI covers 80% of actuals?
```

### Backtesting Metrics:
```python
# Kelly Criterion sizing
- ROI%: Return on investment
- Sharpe Ratio: Risk-adjusted returns
- Max Drawdown: Worst losing streak
- Win Rate: % profitable bets
- Average Odds: Are we betting dogs or favorites?
- Units Won: Profit in standard units
```

---

## 🏗️ TRAINING PIPELINE

### Step 1: Data Preparation (2-3 hours)
```bash
python pipelines/build_features.py \
  --seasons 2025,2026 \
  --output features.parquet
```

**Outputs:**
- `X_train.csv`: Training features (4,500 games × 180 features)
- `y_train.csv`: Labels (winner, margin, total)
- `X_val.csv`: Validation set
- `X_test.csv`: Test set (2026 games)

### Step 2: Baseline Models (1 hour)
```bash
python pipelines/train_baseline.py
```

**Train 4 simple models:**
1. Logistic Regression (winner)
2. Linear Regression (margin, total)
3. Efficiency differential only (KenPom ratings)
4. Vegas line proxy (if we had odds)

**Goal:** Establish floor performance
- Accuracy: ~65% (efficiency diff alone)
- MAE Margin: ~11 points
- MAE Total: ~14 points

### Step 3: XGBoost Ensemble (3-4 hours)
```bash
python pipelines/train_xgboost.py \
  --tune-hyperparameters \
  --cv-folds 5
```

**Hyperparameter tuning:**
```python
param_grid = {
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'n_estimators': [300, 500, 1000],
    'subsample': [0.7, 0.8, 0.9],
    'colsample_bytree': [0.7, 0.8, 0.9],
}

# Use TimeSeriesSplit CV
best_params = GridSearchCV(xgb_model, param_grid, cv=tscv)
```

**Feature importance analysis:**
```python
# Top 20 features for winner prediction
# Top 20 for margin prediction
# Top 20 for total prediction

# Remove low-importance features (<1% gain)
```

### Step 4: Neural Network (2-3 hours)
```bash
python pipelines/train_neural_net.py \
  --architecture multitask \
  --epochs 100 \
  --early-stopping
```

**Architecture:**
```python
# Multi-task learning
model = MultiTaskNN(
    input_dim=180,
    hidden_layers=[256, 128, 64],
    dropout=0.3,
    l2_reg=0.01,
    outputs={
        'winner': 'binary',      # Sigmoid
        'margin': 'continuous',  # Linear
        'total': 'continuous'    # Linear
    }
)

# Custom loss function
loss = (
    binary_crossentropy(y_winner, pred_winner) +
    0.5 * mse(y_margin, pred_margin) +
    0.5 * mse(y_total, pred_total)
)
```

### Step 5: Ensemble Combination (30 min)
```bash
python pipelines/build_ensemble.py \
  --models xgb,lgbm,nn,logreg \
  --method weighted_avg
```

**Stacking approach:**
```python
# Meta-learner: Logistic regression on top
# Inputs: Predictions from 4 base models
# Output: Final ensemble prediction

# Weights optimized on validation set
```

### Step 6: Calibration (30 min)
```python
# Calibrate winner probabilities
from sklearn.calibration import CalibratedClassifierCV

calibrated_model = CalibratedClassifierCV(
    ensemble_model,
    method='isotonic',
    cv='prefit'
)

calibrated_model.fit(X_val, y_val)
```

### Step 7: Confidence Intervals (1 hour)
```python
# Train quantile regression models for margin/total
# 10th, 50th (median), 90th percentiles

from xgboost import XGBRegressor

margin_q10 = XGBRegressor(objective='reg:quantileerror', quantile_alpha=0.10)
margin_q50 = XGBRegressor(objective='reg:quantileerror', quantile_alpha=0.50)
margin_q90 = XGBRegressor(objective='reg:quantileerror', quantile_alpha=0.90)

# Same for total points
```

---

## ✅ VALIDATION CHECKLIST

### Before Deployment:

**1. Data Quality:**
- [ ] No missing values in critical features
- [ ] No data leakage (future → past)
- [ ] Feature distributions similar train/val/test
- [ ] No duplicated games
- [ ] Team IDs consistent across tables

**2. Model Performance:**
- [ ] Accuracy > 65% on validation set
- [ ] Win rate >58% on high-confidence bets (>60% prob)
- [ ] MAE margin < 10 points
- [ ] MAE total < 12 points
- [ ] Calibration curve R² > 0.95

**3. Backtesting:**
- [ ] Test on full 2026 season (364 games)
- [ ] ROI > 5% with Kelly sizing
- [ ] Max drawdown < 20%
- [ ] Sharpe ratio > 1.0
- [ ] No overfitting (train vs test gap < 3%)

**4. Production Readiness:**
- [ ] Inference time < 1 second per game
- [ ] Model versioning implemented
- [ ] Logging/monitoring set up
- [ ] Graceful handling of missing features
- [ ] API endpoint tested

---

## 🚀 DEPLOYMENT PLAN

### Phase 1: Paper Trading (Week 1-2)
```python
# Predict every game, track results, DON'T bet real money
# Metrics: ROI, win rate, calibration
# Goal: Validate in live environment
```

### Phase 2: Small Stakes (Week 3-4)
```python
# Bankroll: $1,000
# Max bet: $20 (2% Kelly)
# Only bet when:
#   - Confidence > 65%
#   - Expected value > 5%
#   - Betfair has liquidity
```

### Phase 3: Scale Up (Month 2+)
```python
# If ROI > 7% sustained:
#   - Increase bankroll to $10,000
#   - Max bet: $500 (5% Kelly)
#   - Add live betting features
```

---

## 📋 IMPLEMENTATION TIMELINE

### Week 1: Data Prep & Baselines
- **Day 1-2:** Feature engineering pipeline
- **Day 3:** Baseline model training
- **Day 4-5:** Data validation & cleaning
- **Deliverable:** `features.parquet`, baseline_results.json

### Week 2: Advanced Models
- **Day 1-2:** XGBoost tuning & training
- **Day 3:** Neural network training
- **Day 4:** Ensemble building
- **Day 5:** Calibration & confidence intervals
- **Deliverable:** `ensemble_model.pkl`, calibration_curves.png

### Week 3: Validation & Testing
- **Day 1-2:** Backtest on 2026 season
- **Day 3:** Feature importance analysis
- **Day 4:** Error analysis (where does model fail?)
- **Day 5:** Documentation
- **Deliverable:** `backtest_report.md`, feature_importance.csv

### Week 4: Production & Paper Trading
- **Day 1-2:** API endpoint & deployment
- **Day 3:** Betfair integration
- **Day 4-5:** Paper trading monitoring
- **Deliverable:** Live predictions, performance dashboard

---

## 🔧 DEPENDENCIES

### Python Packages:
```bash
pip install xgboost lightgbm scikit-learn pandas numpy
pip install torch torchvision torchaudio  # Neural network
pip install matplotlib seaborn plotly  # Visualization
pip install shap  # Feature explanation
pip install optuna  # Hyperparameter tuning
```

### Data Requirements:
- ✅ Games table (12,784 records)
- ✅ Player stats (KenPom + Sports Ref)
- ✅ Team ratings (KenPom efficiency)
- ⚠️ Lineup data (Phase 2)
- ⏳ Betfair odds (for production)

---

## 🎯 SUCCESS CRITERIA

### Minimum Viable Product:
- [x] 12,000+ historical games with scores
- [x] Player season stats (both seasons)
- [⏳] Per-game stats (Sports Ref finishing)
- [ ] Trained ensemble model
- [ ] >65% accuracy on validation
- [ ] >55% win rate on test set
- [ ] Backtested ROI > 3%

### Enterprise Grade:
- [ ] Lineup availability tracking
- [ ] Injury impact modeling
- [ ] Real-time odds integration
- [ ] >68% accuracy
- [ ] >58% win rate
- [ ] ROI > 7% sustained
- [ ] Automated paper trading
- [ ] Performance monitoring dashboard

---

## ⚠️ CRITICAL NEXT STEPS

1. **WAIT for Sports Ref to finish** (~30 min remaining)
2. **Verify data quality** (no missing links, clean team names)
3. **Build feature engineering pipeline** (Day 1)
4. **Train baseline models** (Day 2)
5. **Start lineup data collection** (parallel track)

**Estimated time to first working model: 3-5 days**

---

_Last updated: Jan 6, 2026_
_Sports Ref progress: 27.5% (scraping in background)_

