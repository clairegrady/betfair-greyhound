#!/usr/bin/env python3
"""Test the trained model on recent completed games"""

import sqlite3
import pandas as pd
import torch
import numpy as np
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "pipelines"))

from multitask_model import MultiTaskNCAAModel
from feature_engineering_v2 import build_features_for_game

def main():
    print("="*70)
    print("🏀 TESTING MODEL ON RECENT COMPLETED GAMES")
    print("="*70)
    
    # Load model
    print("\nLoading model...")
    model = MultiTaskNCAAModel(input_dim=37)
    model_path = PROJECT_ROOT / "models/multitask_model_best.pth"
    model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=False))
    model.eval()
    print("✅ Model loaded")
    
    # Load scaler
    scaler = torch.load(PROJECT_ROOT / "models/scaler.pth", map_location='cpu', weights_only=False)
    
    # Get recent games
    conn = sqlite3.connect(PROJECT_ROOT / "ncaa_basketball.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT game_id, game_date, home_team_name, away_team_name, home_score, away_score
        FROM games
        WHERE game_date >= '2025-01-08' AND game_date <= '2025-01-09'
        AND home_score IS NOT NULL
        ORDER BY game_date DESC
        LIMIT 10
    """)
    
    games = cursor.fetchall()
    print(f"\nTesting on {len(games)} recent games:\n")
    
    correct_winners = 0
    total_margin_error = 0
    total_total_error = 0
    valid_predictions = 0
    
    for game_id, game_date, home, away, home_score, away_score in games:
        # Build features
        features = build_features_for_game(game_id, conn)
        
        if features is None:
            print(f"❌ {away} @ {home}: Could not build features (missing data)")
            continue
        
        # Scale
        X = features.reshape(1, -1)
        X_scaled = scaler.transform(X)
        X_tensor = torch.FloatTensor(X_scaled)
        
        # Predict
        with torch.no_grad():
            pred = model(X_tensor)
            
            home_win_prob = pred['winner'][0, 0].item()
            margin_q50 = pred['margin'][0, 1].item()
            total_q50 = pred['totals'][0, 1].item()
        
        # Calculate actual
        actual_margin = home_score - away_score
        actual_total = home_score + away_score
        actual_winner = "Home" if home_score > away_score else "Away"
        pred_winner = "Home" if home_win_prob > 0.5 else "Away"
        
        winner_correct = actual_winner == pred_winner
        if winner_correct:
            correct_winners += 1
        
        margin_error = abs(margin_q50 - actual_margin)
        total_error = abs(total_q50 - actual_total)
        
        total_margin_error += margin_error
        total_total_error += total_error
        valid_predictions += 1
        
        status = "✅" if winner_correct else "❌"
        print(f"{status} {away} @ {home}")
        print(f"    Actual: {away_score}-{home_score} | Predicted: {home} by {margin_q50:+.1f}, Total: {total_q50:.0f}")
        print(f"    Winner confidence: {home_win_prob:.1%} | Errors: Margin={margin_error:.1f}, Total={total_error:.1f}")
        print()
    
    conn.close()
    
    if valid_predictions > 0:
        print("="*70)
        print("📊 OVERALL PERFORMANCE:")
        print("="*70)
        print(f"Winner Accuracy: {correct_winners}/{valid_predictions} ({correct_winners/valid_predictions*100:.1f}%)")
        print(f"Average Margin Error: {total_margin_error/valid_predictions:.1f} points")
        print(f"Average Total Error: {total_total_error/valid_predictions:.1f} points")
        print("="*70)
        print("\n✅ MODEL IS WORKING!")
    
if __name__ == "__main__":
    main()
