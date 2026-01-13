"""
Comprehensive Data Analysis for NCAA Basketball Model
- Check data quality
- Look for missing values
- Analyze distributions
- Identify issues with training data
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"


def check_games_coverage():
    """Check what games we have and when"""
    conn = sqlite3.connect(DB_PATH)
    
    print("\n" + "="*70)
    print("📅 GAMES COVERAGE ANALYSIS")
    print("="*70)
    
    # Overall game counts by season
    df = pd.read_sql_query("""
        SELECT 
            season,
            COUNT(*) as total_games,
            SUM(CASE WHEN home_score IS NOT NULL THEN 1 ELSE 0 END) as games_with_scores,
            MIN(game_date) as earliest_game,
            MAX(game_date) as latest_game
        FROM games
        GROUP BY season
        ORDER BY season
    """, conn)
    
    print("\nGames by Season:")
    print(df.to_string(index=False))
    
    # Check upcoming games
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    today = datetime.now().date()
    
    upcoming = pd.read_sql_query("""
        SELECT COUNT(*) as count, MIN(game_date) as earliest, MAX(game_date) as latest
        FROM games
        WHERE DATE(game_date) IN (?, ?)
    """, conn, params=(str(today), str(tomorrow)))
    
    print(f"\nUpcoming Games (Today/Tomorrow):")
    print(f"  Count: {upcoming['count'][0]}")
    if upcoming['count'][0] > 0:
        print(f"  Range: {upcoming['earliest'][0]} to {upcoming['latest'][0]}")
    
    # Check for specific teams
    purdue_games = pd.read_sql_query("""
        SELECT game_id, game_date, home_team_name, away_team_name, season
        FROM games
        WHERE (home_team_name LIKE '%Purdue%' OR away_team_name LIKE '%Purdue%')
        AND DATE(game_date) BETWEEN DATE('now') AND DATE('now', '+2 days')
        ORDER BY game_date
    """, conn)
    
    if len(purdue_games) > 0:
        print(f"\nPurdue Games (Next 2 Days):")
        print(purdue_games.to_string(index=False))
    else:
        print(f"\n⚠️ No Purdue games found in next 2 days")
    
    conn.close()


def check_player_data_quality():
    """Check quality of player data"""
    conn = sqlite3.connect(DB_PATH)
    
    print("\n" + "="*70)
    print("👥 PLAYER DATA QUALITY")
    print("="*70)
    
    # Player stats by season
    player_stats = pd.read_sql_query("""
        SELECT 
            season,
            COUNT(DISTINCT player_id) as total_players,
            COUNT(DISTINCT CASE WHEN offensive_rating IS NOT NULL THEN player_id END) as players_with_ortg,
            COUNT(DISTINCT CASE WHEN minutes_played IS NOT NULL AND minutes_played > 0 THEN player_id END) as players_with_minutes,
            AVG(CASE WHEN offensive_rating IS NOT NULL THEN offensive_rating END) as avg_ortg,
            AVG(CASE WHEN minutes_played IS NOT NULL AND minutes_played > 0 THEN minutes_played END) as avg_minutes
        FROM player_stats
        GROUP BY season
        ORDER BY season
    """, conn)
    
    print("\nPlayer Stats by Season:")
    print(player_stats.to_string(index=False))
    
    # Teams with player data
    teams_with_data = pd.read_sql_query("""
        SELECT 
            ps.season,
            COUNT(DISTINCT t.team_id) as teams_with_player_data
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        WHERE ps.offensive_rating IS NOT NULL
        GROUP BY ps.season
    """, conn)
    
    print("\nTeams with Player Data:")
    print(teams_with_data.to_string(index=False))
    
    # Total D1 teams
    total_teams = pd.read_sql_query("SELECT COUNT(DISTINCT team_id) as total FROM teams", conn)
    print(f"\nTotal Teams in Database: {total_teams['total'][0]}")
    
    conn.close()


def analyze_feature_dataset():
    """Analyze the features dataset used for training"""
    features_path = Path(__file__).parent / "features_dataset.csv"
    
    if not features_path.exists():
        print("\n⚠️ features_dataset.csv not found!")
        return
    
    print("\n" + "="*70)
    print("📊 FEATURES DATASET ANALYSIS")
    print("="*70)
    
    df = pd.read_csv(features_path)
    
    print(f"\nDataset Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    
    # Check target variables
    print("\n--- TARGET VARIABLES ---")
    if 'home_won' in df.columns:
        print(f"home_won distribution:")
        print(f"  Home wins: {df['home_won'].sum()}")
        print(f"  Away wins: {len(df) - df['home_won'].sum()}")
        print(f"  Home win %: {df['home_won'].mean():.1%}")
    
    if 'point_margin' in df.columns:
        print(f"\npoint_margin stats:")
        print(f"  Mean: {df['point_margin'].mean():.2f}")
        print(f"  Std: {df['point_margin'].std():.2f}")
        print(f"  Min: {df['point_margin'].min():.2f}")
        print(f"  Max: {df['point_margin'].max():.2f}")
        print(f"  Median: {df['point_margin'].median():.2f}")
    
    if 'total_points' in df.columns:
        print(f"\ntotal_points stats:")
        print(f"  Mean: {df['total_points'].mean():.2f}")
        print(f"  Std: {df['total_points'].std():.2f}")
        print(f"  Min: {df['total_points'].min():.2f}")
        print(f"  Max: {df['total_points'].max():.2f}")
        print(f"  Median: {df['total_points'].median():.2f}")
    
    # Check for missing values
    print("\n--- MISSING VALUES ---")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(1)
    missing_df = pd.DataFrame({
        'Column': missing.index,
        'Missing': missing.values,
        'Percent': missing_pct.values
    })
    missing_df = missing_df[missing_df['Missing'] > 0].sort_values('Percent', ascending=False)
    
    if len(missing_df) > 0:
        print(f"\nColumns with missing values:")
        print(missing_df.head(20).to_string(index=False))
    else:
        print("✅ No missing values!")
    
    # Check feature distributions
    print("\n--- KEY FEATURE DISTRIBUTIONS ---")
    feature_cols = [c for c in df.columns if c.startswith(('home_', 'away_', 'diff_'))]
    feature_cols = [c for c in feature_cols if c not in ['home_team', 'away_team', 'home_won', 'home_score', 'away_score']]
    
    if len(feature_cols) > 0:
        print(f"\nFeature statistics (first 10 features):")
        stats = df[feature_cols[:10]].describe().T[['mean', 'std', 'min', 'max']]
        print(stats.to_string())
    
    # Check for constant features
    constant_features = []
    for col in feature_cols:
        if df[col].nunique() == 1:
            constant_features.append(col)
    
    if constant_features:
        print(f"\n⚠️ Constant features (no variance):")
        for feat in constant_features[:10]:
            print(f"  - {feat}")
    
    # Check for extreme values
    print("\n--- CHECKING FOR EXTREME VALUES ---")
    for col in feature_cols[:10]:
        q99 = df[col].quantile(0.99)
        q01 = df[col].quantile(0.01)
        outliers = ((df[col] > q99 * 10) | (df[col] < q01 * 10)).sum()
        if outliers > 0:
            print(f"  {col}: {outliers} potential outliers")
    
    # Check data by season
    print("\n--- DATA BY SEASON ---")
    if 'season' in df.columns:
        season_stats = df.groupby('season').agg({
            'game_id': 'count',
            'home_won': 'mean',
            'point_margin': ['mean', 'std'],
            'total_points': ['mean', 'std']
        }).round(2)
        print(season_stats)


def check_training_test_split():
    """Analyze the train/test split"""
    features_path = Path(__file__).parent / "features_dataset.csv"
    
    if not features_path.exists():
        return
    
    print("\n" + "="*70)
    print("🔍 TRAIN/TEST SPLIT ANALYSIS")
    print("="*70)
    
    df = pd.read_csv(features_path)
    df['game_date'] = pd.to_datetime(df['game_date'])
    
    # Season 2024 split (used for training)
    season_2024 = df[df['season'] == 2024]
    
    if len(season_2024) > 0:
        train_cutoff = pd.to_datetime('2024-02-01')
        val_cutoff = pd.to_datetime('2024-03-15')
        
        train = season_2024[season_2024['game_date'] < train_cutoff]
        val = season_2024[(season_2024['game_date'] >= train_cutoff) & (season_2024['game_date'] < val_cutoff)]
        test = season_2024[season_2024['game_date'] >= val_cutoff]
        
        print(f"\nSeason 2024 (2023-24) Split:")
        print(f"  Train: {len(train)} games (before {train_cutoff.date()})")
        print(f"  Val:   {len(val)} games ({train_cutoff.date()} to {val_cutoff.date()})")
        print(f"  Test:  {len(test)} games (after {val_cutoff.date()})")
        
        if len(train) > 0:
            print(f"\nTrain set target distributions:")
            print(f"  Home win %: {train['home_won'].mean():.1%}")
            print(f"  Avg margin: {train['point_margin'].mean():.2f}")
            print(f"  Avg total: {train['total_points'].mean():.2f}")


def main():
    print("\n" + "="*70)
    print("🔬 NCAA BASKETBALL DATA ANALYSIS")
    print("="*70)
    
    check_games_coverage()
    check_player_data_quality()
    analyze_feature_dataset()
    check_training_test_split()
    
    print("\n" + "="*70)
    print("💡 ANALYSIS COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()

