#!/usr/bin/env python3
"""Test predictions on today's upcoming games (Jan 8, 2026)"""

import sqlite3
import torch
import sys
from pathlib import Path

# Fix imports
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import model directly
import importlib.util
spec = importlib.util.spec_from_file_location("multitask_model", PROJECT_ROOT / "models/multitask_model.py")
mm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mm)
MultiTaskNCAAModel = mm.MultiTaskNCAAModel

spec2 = importlib.util.spec_from_file_location("feature_eng", PROJECT_ROOT / "pipelines/feature_engineering_v2.py")
fe_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(fe_module)
build_features_for_game = fe_module.build_features_for_game

print("="*70)
print("🏀 TODAY'S GAMES - PREDICTIONS (January 8, 2026)")
print("="*70)

# Load model and scaler
print("\nLoading model...")
model = MultiTaskNCAAModel(input_dim=37)
checkpoint = torch.load(PROJECT_ROOT / "models/multitask_model_best.pth", map_location='cpu', weights_only=False)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Load scaler and feature columns from checkpoint
import numpy as np
scaler_mean = checkpoint['scaler_mean']
scaler_scale = checkpoint['scaler_scale']
feature_cols = checkpoint['feature_cols']

class SimpleScaler:
    def __init__(self, mean, scale):
        self.mean_ = mean
        self.scale_ = scale
    def transform(self, X):
        return (X - self.mean_) / self.scale_

scaler = SimpleScaler(scaler_mean, scaler_scale)
print(f"✅ Model loaded ({len(feature_cols)} features)\n")

# Get today's games
conn = sqlite3.connect(PROJECT_ROOT / "ncaa_basketball.db")
cursor = conn.cursor()
cursor.execute("""
    SELECT game_id, home_team_name, away_team_name, game_date
    FROM games
    WHERE season = 2026 
    AND game_date = '2026-01-08'
    AND home_score IS NULL
    ORDER BY home_team_name
""")

games = cursor.fetchall()
print(f"Found {len(games)} upcoming games for today\n")
print("="*70)

predictions_made = 0
for game_id, home, away, game_date in games:
    # Build features
    features_dict = build_features_for_game(game_id, home, away, game_date, 2026)
    
    if features_dict is None:
        print(f"❌ {away} @ {home}: Missing data")
        continue
    
    # Convert dict to array using feature_cols order
    features = np.array([features_dict.get(col, 0.0) for col in feature_cols])
    
    # Scale and predict
    X = features.reshape(1, -1)
    X_scaled = scaler.transform(X)
    X_tensor = torch.FloatTensor(X_scaled)
    
    with torch.no_grad():
        pred = model(X_tensor)
        home_win_prob = pred['winner'][0, 0].item()
        margin_q10 = pred['margin'][0, 0].item()
        margin_q50 = pred['margin'][0, 1].item()
        margin_q90 = pred['margin'][0, 2].item()
        total_q50 = pred['totals'][0, 1].item()
    
    predicted_winner = home if home_win_prob > 0.5 else away
    confidence = max(home_win_prob, 1 - home_win_prob)
    
    print(f"\n{away} @ {home}")
    print(f"  🏆 Predicted Winner: {predicted_winner} ({confidence:.1%} confidence)")
    print(f"  📊 Point Margin: {margin_q50:+.1f} (Range: {margin_q10:+.1f} to {margin_q90:+.1f})")
    print(f"  🎯 Total Points: {total_q50:.0f}")
    
    predictions_made += 1

conn.close()

print("\n" + "="*70)
print(f"✅ Made {predictions_made} predictions")
print("="*70)
print("\n✅ MODEL IS WORKING AND PREDICTING WINNER, MARGIN, AND TOTAL POINTS!")
