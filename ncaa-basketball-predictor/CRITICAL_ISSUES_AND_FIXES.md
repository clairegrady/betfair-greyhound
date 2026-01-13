# NCAA Basketball Model - CRITICAL ISSUES IDENTIFIED

## 🚨 **MAJOR PROBLEMS FOUND**

### 1. **MASSIVE MISSING DATA** (60-87% missing!)
```
away_avg_assist_rate:       87.6% MISSING ❌
away_avg_turnover_rate:     86.9% MISSING ❌
home_avg_assist_rate:       84.9% MISSING ❌
home_avg_turnover_rate:     84.0% MISSING ❌
away_avg_player_ortg:       63.3% MISSING ❌
home_avg_player_ortg:       57.9% MISSING ❌
```

**Impact:** The model is training on mostly zeros/imputed values, not real data!

### 2. **LIMITED PLAYER DATA COVERAGE**
```
Season 2024: Only 457 players have offensive_rating (out of 1,038)
            Only 97 players have minutes_played
Season 2025: 4,168 players have data ✅ (GOOD!)
Season 2026: 3,382 players have data ✅ (GOOD!)
```

**Impact:** Training on Season 2024 data (2023-24) is using incomplete player stats!

### 3. **TEAM COVERAGE GAPS**
```
Total teams: 938 in database
Teams with player data in 2024: 237 (25% coverage!)
Teams with player data in 2025: 356 (38% coverage)
```

**Impact:** Many teams have NO player data, so features are all zeros.

### 4. **EXTREME OUTLIERS**
```
5,224+ potential outliers in player rating features
```

**Impact:** Model is seeing unrealistic values that distort learning.

### 5. **TARGET VARIABLE ISSUES**
- **Home Win Rate: 66.9%** (should be ~52-55% in neutral prediction)
  - This means home court advantage is strong OR data is biased
- **Total Points: Min=0, Max=238**
  - Zero points games are clearly data errors!
  - 238 points in a game is unrealistic (should be ~180 max)

### 6. **WRONG TRAINING SEASON**
We're training on Season 2024 (2023-24) which has:
- Only 237 teams with player data
- Only 457 players with ratings
- 84-87% missing feature values

**But** Season 2025 (2024-25) has:
- 356 teams with player data ✅
- 4,168 players with ratings ✅
- Much better coverage!

---

## 📋 **ACTION PLAN TO FIX**

### Phase 1: Data Cleaning (IMMEDIATE)

1. **Remove Bad Games**
   ```sql
   DELETE FROM games WHERE total_points = 0 OR total_points > 200
   ```

2. **Fix Player Data for Season 2024**
   - Re-scrape Season 2024 player data properly
   - OR skip Season 2024 entirely for training

3. **Handle Missing Values Properly**
   - Don't fill with zeros (misleading!)
   - Either drop features with >50% missing
   - OR impute with team/league averages

4. **Normalize/Scale Features**
   - Player ratings are on different scales
   - Need StandardScaler or MinMaxScaler
   - Already doing this, but check if it's working

### Phase 2: Feature Engineering (HIGH PRIORITY)

1. **Reduce Features**
   - Drop features with >70% missing data
   - Focus on most important features:
     - `home_avg_player_ortg`
     - `away_avg_player_ortg`
     - Simple differentials

2. **Add Baseline Features**
   - Home court advantage (binary flag)
   - Neutral site (binary flag)
   - Conference strength
   - Win/loss record (simple)

3. **Fix Target Variables**
   - Clip point margins to [-50, 50]
   - Clip total points to [100, 200]
   - Normalize total points (subtract 145, divide by std)

### Phase 3: Better Training Strategy

1. **Use Season 2025 Data Instead!**
   ```python
   # Current (BAD):
   train_df = season_2024[games < '2024-02-01']  # Only 457 players!
   
   # New (GOOD):
   train_df = season_2025[games < '2025-02-01']  # 4,168 players! ✅
   val_df = season_2025[games between '2025-02-01' and '2025-03-15']
   test_df = season_2025[games > '2025-03-15']
   ```

2. **Combine Seasons 2024 + 2025**
   - Use all complete games from both seasons
   - Much more training data
   - Better generalization

3. **Simpler Model First**
   - Start with just 5-10 features
   - Get that working well
   - Then add complexity

### Phase 4: Model Architecture Fixes

1. **Fix Output Ranges**
   ```python
   # For totals: Output should be ~145 ± 40
   # Currently predicting 300+, which is insane!
   
   # Add output constraints:
   totals_head = nn.Sequential(
       nn.Linear(last_hidden, 32),
       nn.ReLU(),
       nn.Linear(32, 3),
       nn.Sigmoid()  # Force to 0-1
   )
   # Then scale: output * 100 + 100 → range [100, 200]
   ```

2. **Separate Models**
   - Train 3 separate models instead of multi-task:
     1. Winner classification
     2. Margin regression
     3. Total regression
   - Multi-task is harder to debug

3. **Reduce Model Complexity**
   - Current: [256, 128, 64] with 57K parameters
   - Try: [64, 32] with ~5K parameters
   - Simpler model, less overfitting

---

## 🎯 **IMMEDIATE NEXT STEPS**

### Step 1: Clean the Data (30 min)
```python
# Remove bad games
conn = sqlite3.connect("ncaa_basketball.db")
cursor = conn.cursor()

# Delete impossible games
cursor.execute("DELETE FROM games WHERE total_points = 0 OR total_points > 200")
cursor.execute("DELETE FROM games WHERE ABS(home_score - away_score) > 75")

conn.commit()
```

### Step 2: Rebuild Features with Season 2025 (30 min)
```python
# In feature_engineering_v2.py
fe = NCAAFeatureEngineering()
features_df = fe.build_all_features(seasons=[2025])  # Only 2025!
fe.save_features(features_df, "features_dataset_v2.csv")
```

### Step 3: Simpler Model (30 min)
```python
# Train with:
# - Only top 10 features
# - StandardScaler applied
# - Output clipping
# - Separate models for each task
```

### Step 4: Validate (15 min)
- Check predictions are in reasonable ranges:
  - Win probability: 20-80%
  - Margin: -30 to +30
  - Total: 120-170

---

## 📊 **Expected Improvements**

| Metric | Current (Bad) | Expected (Fixed) |
|--------|---------------|------------------|
| Winner Accuracy | 53.3% | 60-65% |
| Margin MAE | 11.56 | 8-10 points |
| Total MAE | 21.08 | 8-12 points |
| Total Prediction | 300+ pts ❌ | 130-160 pts ✅ |
| Confidence | 0% (broken) | 60-80% ✅ |

---

## 💡 **Why the Model Was Terrible**

1. **Training on 60-87% missing data** → Model learned garbage patterns
2. **Using Season 2024 with poor coverage** → Should use Season 2025
3. **No output constraints** → Model can predict any number (300+ points!)
4. **No data validation** → Games with 0 points, 238 points included
5. **Too complex for small dataset** → 57K parameters for 1,311 games = massive overfit

**Bottom line:** The model never had a chance with this data quality!

---

## ✅ **READY TO FIX?**

Run these steps in order:
1. `python3 clean_data.py` - Remove bad games, fix outliers
2. `python3 rebuild_features.py` - Use Season 2025, drop bad features
3. `python3 train_simple_model.py` - Simpler model, better constraints
4. `python3 validate_predictions.py` - Check outputs are sane

Let's rebuild this properly! 🚀

