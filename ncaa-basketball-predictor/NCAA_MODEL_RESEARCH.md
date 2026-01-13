# NCAA Basketball Prediction Model - Research & Feature Plan

## 🎯 Critical Issues to Address

### 1. Player Graduation/Transfer Problem
**Issue:** Players from 24-25 season may not be in 25-26 season (graduated, transferred, NBA draft)

**Solutions:**
- ✅ **Use Season-Specific Data:** Train on 23-24 data, validate on 24-25, test on 25-26
- ✅ **Team-Level Features as Primary:** Focus on team efficiency metrics (less affected by roster changes)
- ✅ **Roster Continuity Feature:** % of minutes returning from previous season
- ✅ **Aggregate Player Stats:** Team average ORtg, weighted by minutes played
- ❌ **Don't:** Try to predict future rosters or match players across seasons

**Implementation:**
```python
# Flag players by season - never mix cross-season
player_stats[season=2025]  # 24-25 players
player_stats[season=2026]  # 25-26 players (different roster!)

# Build team aggregates WITHIN each season
team_avg_ortg_2025 = players_2025.groupby('team')['offensive_rating'].mean()
team_avg_ortg_2026 = players_2026.groupby('team')['offensive_rating'].mean()
```

---

## 📊 Feature Categories (Based on NCAA Research)

### **Tier 1: Core Efficiency Metrics** (KenPom-based)
*Most predictive features according to research*

#### Team Efficiency (Current Season)
1. **Offensive Efficiency (AdjO)** - Points per 100 possessions (adjusted)
2. **Defensive Efficiency (AdjD)** - Points allowed per 100 possessions (adjusted)
3. **Efficiency Margin (AdjEM)** - AdjO minus AdjD
4. **Tempo (AdjT)** - Possessions per 40 minutes (adjusted)
5. **Strength of Schedule**

#### Four Factors (Offense & Defense)
**Offensive:**
6. eFG% - Effective Field Goal %
7. TO% - Turnover Rate
8. OR% - Offensive Rebound %
9. FTRate - Free Throws per FGA

**Defensive:**
10. Opp_eFG% - Opponent eFG%
11. Opp_TO% - Opponent Turnover Rate
12. Opp_OR% - Opponent Offensive Rebound %
13. Opp_FTRate - Opponent FT Rate

---

### **Tier 2: Lineup & Roster Strength** (KenPom Player Data)
*Critical for handling injuries/lineup changes*

14. **Starter Average ORtg** - Avg offensive rating of 5 starters
15. **Starter Average Usage** - Avg usage rate of starters
16. **Starter Minutes %** - % of team minutes played by starters
17. **Bench ORtg** - Average ORtg of bench players
18. **Bench Depth Score** - Number of players with >10% minutes and ORtg >100
19. **Top Player ORtg** - Best player offensive rating
20. **Top 3 Players Avg ORtg** - Average of top 3 players
21. **Starting 5 Continuity** - Are the typical starters playing? (from lineup data)
22. **Minutes Concentration** - Gini coefficient of minute distribution

---

### **Tier 3: Recent Form & Momentum**

23. **Last 5 Games Win %**
24. **Last 10 Games Win %**
25. **Last 5 AdjEM** - Recent efficiency margin
26. **Last 5 eFG%** - Recent shooting
27. **Days Since Last Game** - Rest differential
28. **Streak** - Current win/loss streak
29. **Home Court Record** - Win % at home this season
30. **Away Record** - Win % away this season

---

### **Tier 4: Matchup-Specific Features**

31. **Pace Matchup** - Difference in tempo between teams
32. **Style Clash** - Fast team vs slow team? (interaction)
33. **3PT Rate Differential** - Team A 3pt% vs Team B 3pt defense
34. **Rebound Battle** - Team A OR% vs Team B DR%
35. **Turnover Battle** - Team A TO% vs Team B forced TO%
36. **Experience Gap** - Avg class year differential
37. **Height Advantage** - Average roster height difference

---

### **Tier 5: Situational Context**

38. **Home Court Advantage** - Binary + venue-specific multiplier
39. **Neutral Site** - Tournament games
40. **Conference Game** - In-conference vs out-of-conference
41. **Rivalry Game** - Historical rivalry indicator
42. **Tournament Round** - NCAA tournament specific
43. **Seed Differential** - Tournament seed difference
44. **Time of Season** - Early season (Nov/Dec) vs late (Feb/Mar)
45. **Back-to-Back Game** - Playing on consecutive days

---

### **Tier 6: Head-to-Head History**

46. **H2H Last 3 Years** - Win rate in recent matchups
47. **H2H Point Differential** - Avg margin in recent games
48. **H2H This Season** - Already played this year?

---

### **Tier 7: Advanced/Composite Features**

49. **Luck Factor** - Actual wins vs Pythagorean expectation
50. **Close Game Performance** - Win % in games decided by <5 pts
51. **Blowout Avoidance** - % of games within 15 pts
52. **Consistency Score** - StdDev of game-by-game eFG%
53. **Clutch Rating** - Performance in final 5 minutes of close games

---

## 🏀 Research-Backed Insights

### **Most Predictive Features (Academic Studies):**

**Dean Oliver's Four Factors** (in order of importance):
1. **Shooting (eFG%)** - 40% of game outcome
2. **Turnovers (TO%)** - 25%
3. **Rebounding (OR%)** - 20%
4. **Free Throws (FTRate)** - 15%

**KenPom's Efficiency Ratings:**
- Adjusted Offensive/Defensive Efficiency are THE most predictive single metrics
- Better than win/loss record, especially early in season

**Lineup Data Importance:**
- Knowing which 5 players start increases prediction accuracy by **3-5%**
- Starter ORtg > Team average ORtg (starters play more minutes!)
- Injuries to top 3 players drop win probability **15-25%**

**Tempo Matters:**
- Fast teams vs slow teams = higher variance outcomes
- Slow, defensive teams are more predictable
- Tempo differential is interaction feature (slow team speeds up vs fast opponent)

---

## 🔬 Model Architecture Recommendation

### **Ensemble Approach:**

**Model 1: XGBoost (Gradient Boosting)**
- Best for tabular data with lots of features
- Handles non-linear relationships well
- Can capture feature interactions automatically
- Good for: Overall win probability, point spread

**Model 2: LightGBM**
- Faster than XGBoost for large datasets
- Similar accuracy
- Good for: Alternative ensemble member

**Model 3: Logistic Regression (Baseline)**
- Simple, interpretable
- Use as baseline to beat

**Model 4: Neural Network (Multi-Task)**
- Predict winner, margin, AND total points simultaneously
- Shared representations learn better features
- Good for: Total points (regression) + winner (classification)

**Final Ensemble:**
- Weighted average of Model 1, 2, 4
- Weights based on validation performance
- Separate models for:
  - Early season (Nov-Dec) - rely more on previous season data
  - Mid season (Jan-Feb) - balanced
  - Tournament (March) - emphasize recent form

---

## ⚠️ Data Leakage Prevention

**CRITICAL - DO NOT:**
- ❌ Use future game results in features for past games
- ❌ Include opponent's future stats
- ❌ Mix player data across seasons (graduation problem!)
- ❌ Use "end of season" team rankings for mid-season games

**DO:**
- ✅ Use only data available at prediction time
- ✅ Rolling averages (last 5, last 10 games)
- ✅ Time-based train/test split (train on early games, test on late games)
- ✅ Season-by-season split (train on 23-24, test on 24-25)

---

## 📈 Feature Engineering Priorities

### **Phase 1: Core Features (60 features)**
- Team efficiency metrics (13)
- Four factors offense + defense (8)
- Starter/bench aggregates (10)
- Recent form (10)
- Home court + situational (10)
- Matchup differentials (9)

### **Phase 2: Advanced Features (40 features)**
- Interaction terms (pace × efficiency, etc.)
- Polynomial features (efficiency^2)
- Lineup-specific features
- Head-to-head history
- Consistency metrics

### **Phase 3: Feature Selection**
- Remove correlated features (>0.9 correlation)
- Use XGBoost feature importance
- SHAP values for interpretation
- Keep top 80-100 features

---

## 🎓 Handling Roster Changes

### **Training Strategy:**

**For 24-25 Season (2025) Data:**
- Use player data from season 2025
- Aggregate to team level WITHIN season
- Train model on early 24-25 games → predict late 24-25 games

**For 25-26 Season (2026) Testing:**
- Use player data from season 2026 (NEW rosters!)
- Same aggregation method
- Model sees "Duke with 2026 roster" vs "Duke with 2025 roster" as different team states

**Key Insight:**
The model learns: "A team with starters averaging 115 ORtg and good bench depth beats a team with 105 ORtg starters"

NOT: "Kyle Filipowski's Duke beats..."

This way, roster changes don't break the model!

---

## 🚀 Implementation Plan

1. ✅ Wait for 24-25 KenPom data to reach 90%+
2. Build feature engineering pipeline (team aggregates + player stats)
3. Create training dataset:
   - 23-24 season games (historical)
   - Early 24-25 season games
4. Create test dataset:
   - Late 24-25 games + 25-26 games
5. Train models (XGBoost, LightGBM, Neural Net)
6. Backtest on 25-26 season
7. Deploy for live betting

---

## 📊 Expected Performance

**Accuracy Targets:**
- **Win/Loss Prediction:** 72-75% accuracy
- **Against Spread (ATS):** 54-57% (profitable!)
- **Total Points:** Within 8 points RMSE

**Feature Importance (Expected):**
1. Efficiency Margin (AdjEM)
2. Four Factors (eFG%, TO%)
3. Starter ORtg
4. Home Court Advantage
5. Recent Form (Last 5)
6. Pace Differential
7. Rest Days
8. Lineup Quality
9. Strength of Schedule
10. Tournament Seed (if applicable)

---

## ✅ Next Steps

Once 24-25 KenPom data hits 90%:
1. Build feature engineering pipeline (2-3 hours)
2. Generate training dataset (1 hour)
3. Train baseline models (1 hour)
4. Train XGBoost ensemble (2-3 hours with hyperparameter tuning)
5. Backtest and evaluate (1 hour)
6. **Total: 7-9 hours to first working model**

**ETA:** Depending on scraper speed, should be ready to start in 2-4 hours.

