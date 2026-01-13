# NCAA Basketball Model - Complete Analysis & Fix Plan

## 📊 **DATA ANALYSIS SUMMARY**

### ✅ What We Have
- **12,734 games** (after cleaning bad data)
- **82 games tomorrow** (Jan 7-8, 2026) including Purdue
- **Season 2025 (24-25):** 4,168 players with complete data ✅
- **Season 2026 (25-26):** 3,382 players with complete data ✅

### ❌ Critical Problems Found

#### 1. **MASSIVE MISSING DATA (60-87%!)**
The features dataset has:
- `home_avg_player_ortg`: **57.9% MISSING**
- `away_avg_player_ortg`: **63.3% MISSING**  
- `away_avg_assist_rate`: **87.6% MISSING**
- `away_avg_turnover_rate`: **86.9% MISSING**

**Root cause:** Training on Season 2024 (2023-24) which only has 457 players with ratings!

#### 2. **Wrong Training Season**
Current model trains on Season 2024 which has:
- Only **237 teams** with player data (25% coverage)
- Only **457 players** with ratings
- Only **97 players** with minutes played

Should train on Season 2025 which has:
- **356 teams** with player data (38% coverage) ✅
- **4,168 players** with ratings ✅  
- **4,168 players** with minutes ✅

#### 3. **Model Output is Broken**
Predictions show:
- Total points: **339 points** (should be ~145)
- Margin confidence: **0%** (broken)
- Winner probability: Often 100% (overconfident)

**Why:** No output constraints, trained on garbage data

#### 4. **Data Quality Issues** (FIXED ✅)
- Deleted 12 games with 0 points
- Deleted 64 games with >200 points  
- Deleted 28 games with margin >75 points
- **Total: 104 bad games removed**

---

## 🎯 **FIX PLAN**

### Option A: **QUICK FIX** (1-2 hours)
Use only the features that work, train simple model

**Steps:**
1. Drop all features with >50% missing data
2. Use only these 8 features:
   - `home_avg_player_ortg`
   - `away_avg_player_ortg`
   - `ortg_diff` (home - away)
   - `home_roster_depth`
   - `away_roster_depth`
   - `home_minutes_concentration`
   - `away_minutes_concentration`
   - Plus: `is_neutral`, `is_tournament`
3. Train on **Season 2025** data (not 2024!)
4. Use simpler model: [64, 32] layers instead of [256, 128, 64]
5. Add output constraints (sigmoid + scaling)

**Expected results:**
- Winner accuracy: 58-62%
- Margin MAE: 10-12 points
- Total MAE: 12-15 points
- **Predictions will be reasonable!**

### Option B: **PROPER FIX** (4-6 hours)
Re-scrape missing data, build complete features

**Steps:**
1. Re-scrape Season 2024 player data from KenPom
2. Fill in missing assist_rate/turnover_rate/usage data
3. Get 90%+ feature coverage
4. Train on combined 2024+2025 data (~12K games)
5. Use full feature set with proper imputation
6. Train ensemble of models

**Expected results:**
- Winner accuracy: 62-66%
- Margin MAE: 8-10 points
- Total MAE: 10-12 points
- **Production-quality predictions**

### Option C: **NUCLEAR OPTION** (8+ hours)
Start from scratch with better architecture

**What to do:**
1. Use pre-aggregated team stats (KenPom efficiency ratings)
2. Skip player-level features entirely (too sparse)
3. Add external features (Vegas lines, ELO ratings)
4. Use transfer learning from existing sports models
5. Train gradient boosted trees (XGBoost/LightGBM)

---

## 💡 **MY RECOMMENDATION: Option A (Quick Fix)**

**Why:**
1. You want predictions NOW, not in 3 days
2. 58-62% accuracy is respectable (random is 50%)
3. Can iterate and improve later
4. Gets system working end-to-end

**Implementation Time:** ~1-2 hours

**What I'll do:**
1. ✅ Clean data (DONE - deleted 104 bad games)
2. Rebuild features using Season 2025 only
3. Drop high-missing features
4. Train simpler, constrained model
5. Validate predictions are sane
6. Show you tomorrow's games with GOOD predictions

---

## 🚀 **LET'S DO THE QUICK FIX NOW**

I'll implement Option A right now. Here's what will happen:

### Step 1: Rebuild Features (5 min)
```python
# Use Season 2025 data with 4,168 players
features_df = build_all_features(seasons=[2025])
# Drop bad features
features_df = features_df.drop(columns=[
    'home_avg_assist_rate', 'away_avg_assist_rate',
    'home_avg_turnover_rate', 'away_avg_turnover_rate'
])
```

### Step 2: Train Simple Model (10 min)
```python
model = MultiTaskNCAAModel(
    input_dim=10,  # Only good features
    hidden_dims=[64, 32],  # Simpler
    dropout_rate=0.2
)

# Add output constraints
def constrain_output(totals):
    # Force totals to [100, 190] range
    return 100 + torch.sigmoid(totals) * 90
```

### Step 3: Validate (2 min)
Check that predictions are:
- Win prob: 30-70% (not 0% or 100%)
- Margin: -25 to +25 (not -37 to +181!)
- Total: 120-170 (not 300+!)

### Step 4: Show Predictions (1 min)
Run `show_predictions.py` and see GOOD results!

---

## ⏱️ **Ready to proceed?**

Say the word and I'll:
1. Rebuild features using Season 2025
2. Train a proper, constrained model  
3. Show you tomorrow's 82 games with realistic predictions

This will take ~20 minutes total.

**Current status:**  
✅ Data cleaned (104 bad games removed)  
⏳ Ready to rebuild features  
⏳ Ready to retrain model  
⏳ Ready to show predictions  

Let's fix this properly! 🔧

