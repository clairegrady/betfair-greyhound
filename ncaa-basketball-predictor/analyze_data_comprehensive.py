#!/usr/bin/env python3
"""
Comprehensive data analysis for NCAA Basketball database
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    
    print("\n" + "="*80)
    print("🏀 NCAA BASKETBALL DATABASE - COMPREHENSIVE DATA ANALYSIS")
    print("="*80 + "\n")
    
    # =========================================================================
    # 1. DATABASE OVERVIEW
    # =========================================================================
    print("📊 1. DATABASE OVERVIEW")
    print("-" * 80)
    
    cursor = conn.cursor()
    
    # Get table sizes
    tables = ['teams', 'players', 'player_stats', 'games']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:20s}: {count:,} rows")
    
    # =========================================================================
    # 2. PLAYER_STATS - DETAILED BREAKDOWN BY SEASON
    # =========================================================================
    print("\n📈 2. PLAYER_STATS - BY SEASON")
    print("-" * 80)
    
    player_stats_df = pd.read_sql_query("""
        SELECT 
            season,
            COUNT(*) as total_players,
            COUNT(DISTINCT player_id) as unique_players,
            
            -- KenPom metrics (advanced efficiency stats)
            COUNT(CASE WHEN offensive_rating IS NOT NULL THEN 1 END) as have_orating,
            COUNT(CASE WHEN usage_rate IS NOT NULL THEN 1 END) as have_usage,
            COUNT(CASE WHEN assist_rate IS NOT NULL THEN 1 END) as have_assist_rate,
            COUNT(CASE WHEN turnover_rate IS NOT NULL THEN 1 END) as have_to_rate,
            COUNT(CASE WHEN minutes_played IS NOT NULL THEN 1 END) as have_minutes,
            
            -- Traditional box score stats (from NCAA.com/Sports Reference)
            COUNT(CASE WHEN points_per_game IS NOT NULL THEN 1 END) as have_ppg,
            COUNT(CASE WHEN rebounds_per_game IS NOT NULL THEN 1 END) as have_rpg,
            COUNT(CASE WHEN assists_per_game IS NOT NULL THEN 1 END) as have_apg,
            COUNT(CASE WHEN steals_per_game IS NOT NULL THEN 1 END) as have_spg,
            COUNT(CASE WHEN blocks_per_game IS NOT NULL THEN 1 END) as have_bpg,
            COUNT(CASE WHEN fg_pct IS NOT NULL THEN 1 END) as have_fg_pct,
            
            -- Physical attributes
            COUNT(CASE WHEN height_inches IS NOT NULL THEN 1 END) as have_height,
            COUNT(CASE WHEN weight IS NOT NULL THEN 1 END) as have_weight,
            COUNT(CASE WHEN position IS NOT NULL THEN 1 END) as have_position,
            COUNT(CASE WHEN class_year IS NOT NULL THEN 1 END) as have_class
        FROM player_stats
        GROUP BY season
        ORDER BY season
    """, conn)
    
    for _, row in player_stats_df.iterrows():
        season_label = f"{int(row['season'])-1}-{str(int(row['season']))[2:]}"
        total = row['total_players']
        print(f"\n  Season {season_label} ({int(row['season'])}):")
        print(f"    Total entries: {total:,} ({row['unique_players']:,} unique players)")
        print(f"\n    KenPom Advanced Metrics:")
        print(f"      Offensive Rating:   {row['have_orating']:5,} ({100*row['have_orating']/total:5.1f}%)")
        print(f"      Usage Rate:         {row['have_usage']:5,} ({100*row['have_usage']/total:5.1f}%)")
        print(f"      Assist Rate:        {row['have_assist_rate']:5,} ({100*row['have_assist_rate']/total:5.1f}%)")
        print(f"      Turnover Rate:      {row['have_to_rate']:5,} ({100*row['have_to_rate']/total:5.1f}%)")
        print(f"      Minutes Played:     {row['have_minutes']:5,} ({100*row['have_minutes']/total:5.1f}%)")
        print(f"\n    Traditional Box Score Stats:")
        print(f"      Points Per Game:    {row['have_ppg']:5,} ({100*row['have_ppg']/total:5.1f}%)")
        print(f"      Rebounds Per Game:  {row['have_rpg']:5,} ({100*row['have_rpg']/total:5.1f}%)")
        print(f"      Assists Per Game:   {row['have_apg']:5,} ({100*row['have_apg']/total:5.1f}%)")
        print(f"      Steals Per Game:    {row['have_spg']:5,} ({100*row['have_spg']/total:5.1f}%)")
        print(f"      Blocks Per Game:    {row['have_bpg']:5,} ({100*row['have_bpg']/total:5.1f}%)")
        print(f"      Field Goal %:       {row['have_fg_pct']:5,} ({100*row['have_fg_pct']/total:5.1f}%)")
        print(f"\n    Physical Attributes:")
        print(f"      Height:             {row['have_height']:5,} ({100*row['have_height']/total:5.1f}%)")
        print(f"      Weight:             {row['have_weight']:5,} ({100*row['have_weight']/total:5.1f}%)")
        print(f"      Position:           {row['have_position']:5,} ({100*row['have_position']/total:5.1f}%)")
        print(f"      Class Year:         {row['have_class']:5,} ({100*row['have_class']/total:5.1f}%)")
    
    # =========================================================================
    # 3. DATA QUALITY ASSESSMENT
    # =========================================================================
    print("\n\n🔍 3. DATA QUALITY ASSESSMENT")
    print("-" * 80)
    
    # Check for players with complete vs incomplete data
    cursor.execute("""
        SELECT 
            season,
            COUNT(*) as total,
            COUNT(CASE WHEN offensive_rating IS NOT NULL AND points_per_game IS NOT NULL THEN 1 END) as complete,
            COUNT(CASE WHEN offensive_rating IS NOT NULL AND points_per_game IS NULL THEN 1 END) as kenpom_only,
            COUNT(CASE WHEN offensive_rating IS NULL AND points_per_game IS NOT NULL THEN 1 END) as boxscore_only,
            COUNT(CASE WHEN offensive_rating IS NULL AND points_per_game IS NULL THEN 1 END) as neither
        FROM player_stats
        GROUP BY season
    """)
    
    print("\n  Data Completeness Breakdown:")
    print("  " + "-" * 76)
    print(f"  {'Season':<15} {'Total':>8} {'Complete':>10} {'KenPom Only':>15} {'BoxScore Only':>15} {'Neither':>10}")
    print("  " + "-" * 76)
    for row in cursor.fetchall():
        season_label = f"{row[0]-1}-{str(row[0])[2:]}"
        print(f"  {season_label:<15} {row[1]:>8,} {row[2]:>10,} {row[3]:>15,} {row[4]:>15,} {row[5]:>10,}")
    
    # =========================================================================
    # 4. STATISTICAL DISTRIBUTIONS
    # =========================================================================
    print("\n\n📊 4. STATISTICAL DISTRIBUTIONS (Non-Null Values)")
    print("-" * 80)
    
    stats_df = pd.read_sql_query("SELECT * FROM player_stats", conn)
    
    key_stats = {
        'minutes_played': 'Minutes Played',
        'offensive_rating': 'Offensive Rating',
        'usage_rate': 'Usage Rate',
        'points_per_game': 'Points Per Game',
        'rebounds_per_game': 'Rebounds Per Game',
        'assists_per_game': 'Assists Per Game',
    }
    
    for col, label in key_stats.items():
        if col in stats_df.columns:
            data = stats_df[col].dropna()
            if len(data) > 0:
                print(f"\n  {label}:")
                print(f"    Count:   {len(data):,}")
                print(f"    Min:     {data.min():.2f}")
                print(f"    25%:     {data.quantile(0.25):.2f}")
                print(f"    Median:  {data.median():.2f}")
                print(f"    75%:     {data.quantile(0.75):.2f}")
                print(f"    Max:     {data.max():.2f}")
                print(f"    Mean:    {data.mean():.2f}")
                print(f"    Std Dev: {data.std():.2f}")
    
    # =========================================================================
    # 5. GAMES ANALYSIS
    # =========================================================================
    print("\n\n🏀 5. GAMES ANALYSIS")
    print("-" * 80)
    
    games_df = pd.read_sql_query("""
        SELECT 
            SUBSTR(game_date, 1, 4) as year,
            COUNT(*) as total_games,
            COUNT(CASE WHEN home_score IS NOT NULL THEN 1 END) as completed,
            COUNT(CASE WHEN home_score IS NULL THEN 1 END) as upcoming,
            AVG(CASE WHEN home_score IS NOT NULL THEN home_score + away_score END) as avg_total_points,
            AVG(CASE WHEN home_score IS NOT NULL THEN ABS(home_score - away_score) END) as avg_margin
        FROM games
        GROUP BY SUBSTR(game_date, 1, 4)
        ORDER BY year
    """, conn)
    
    print("\n  Games by Year:")
    print(f"  {'Year':<10} {'Total':>10} {'Completed':>12} {'Upcoming':>10} {'Avg Total':>12} {'Avg Margin':>12}")
    print("  " + "-" * 76)
    for _, row in games_df.iterrows():
        year = row['year'] if pd.notna(row['year']) else 'Unknown'
        print(f"  {year:<10} {row['total_games']:>10,} {row['completed']:>12,} {row['upcoming']:>10,} "
              f"{row['avg_total_points']:>12.1f} {row['avg_margin']:>12.1f}")
    
    # Check for data quality issues in games
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL 
                      AND (home_score + away_score) < 100 THEN 1 END) as low_scoring,
            COUNT(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL 
                      AND (home_score + away_score) > 200 THEN 1 END) as high_scoring,
            COUNT(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL 
                      AND ABS(home_score - away_score) > 50 THEN 1 END) as blowouts
        FROM games
    """)
    
    issues = cursor.fetchone()
    print(f"\n  Potential Data Quality Issues:")
    print(f"    Games with <100 total points (potential errors): {issues[0]:,}")
    print(f"    Games with >200 total points (potential errors): {issues[1]:,}")
    print(f"    Games with >50 point margin (blowouts):          {issues[2]:,}")
    
    # =========================================================================
    # 6. TEAMS ANALYSIS
    # =========================================================================
    print("\n\n🎓 6. TEAMS ANALYSIS")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM teams")
    total_teams = cursor.fetchone()[0]
    print(f"  Total teams in database: {total_teams:,}")
    
    # Teams with players in each season
    cursor.execute("""
        SELECT 
            ps.season,
            COUNT(DISTINCT p.team_id) as teams_with_players
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.player_id AND ps.season = p.season
        GROUP BY ps.season
        ORDER BY ps.season
    """)
    
    print(f"\n  Teams with player data by season:")
    for row in cursor.fetchall():
        season_label = f"{row[0]-1}-{str(row[0])[2:]}"
        print(f"    Season {season_label}: {row[1]:,} teams")
    
    # =========================================================================
    # 7. CRITICAL MISSING DATA
    # =========================================================================
    print("\n\n⚠️  7. CRITICAL MISSING DATA & RECOMMENDATIONS")
    print("-" * 80)
    
    issues = []
    recommendations = []
    
    # Check each season
    for _, row in player_stats_df.iterrows():
        season_label = f"{int(row['season'])-1}-{str(int(row['season']))[2:]}"
        total = row['total_players']
        
        # KenPom coverage
        kenpom_pct = 100 * row['have_orating'] / total
        if kenpom_pct < 95:
            issues.append(f"Season {season_label}: Only {kenpom_pct:.1f}% KenPom coverage")
            recommendations.append(f"Re-scrape KenPom for season {row['season']}")
        
        # Box score coverage
        boxscore_pct = 100 * row['have_ppg'] / total
        if boxscore_pct < 50:
            issues.append(f"Season {season_label}: Only {boxscore_pct:.1f}% box score stats")
            recommendations.append(f"Scrape more NCAA.com/Sports Reference data for season {row['season']}")
    
    if issues:
        print("\n  Issues Found:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
    else:
        print("\n  ✅ No critical issues found!")
    
    if recommendations:
        print("\n  Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. {rec}")
    
    # =========================================================================
    # 8. MODEL READINESS ASSESSMENT
    # =========================================================================
    print("\n\n🤖 8. MODEL READINESS ASSESSMENT")
    print("-" * 80)
    
    # Calculate overall data quality score
    total_players = player_stats_df['total_players'].sum()
    kenpom_complete = player_stats_df['have_orating'].sum()
    boxscore_complete = player_stats_df['have_ppg'].sum()
    
    kenpom_score = 100 * kenpom_complete / total_players
    boxscore_score = 100 * boxscore_complete / total_players
    overall_score = (kenpom_score + boxscore_score) / 2
    
    print(f"\n  Overall Data Quality Scores:")
    print(f"    KenPom Metrics:     {kenpom_score:5.1f}% ({kenpom_complete:,}/{total_players:,})")
    print(f"    Box Score Stats:    {boxscore_score:5.1f}% ({boxscore_complete:,}/{total_players:,})")
    print(f"    Combined Score:     {overall_score:5.1f}%")
    
    print(f"\n  Readiness Assessment:")
    if overall_score >= 80:
        print(f"    ✅ EXCELLENT - Ready for model training")
    elif overall_score >= 70:
        print(f"    ✅ GOOD - Can proceed with model training")
    elif overall_score >= 60:
        print(f"    ⚠️  FAIR - Model training possible but more data recommended")
    else:
        print(f"    ❌ POOR - Need more data before training")
    
    # Check for sufficient historical games
    cursor.execute("SELECT COUNT(*) FROM games WHERE home_score IS NOT NULL")
    completed_games = cursor.fetchone()[0]
    
    print(f"\n  Training Data:")
    print(f"    Completed games: {completed_games:,}")
    if completed_games >= 10000:
        print(f"    ✅ Sufficient historical games for training")
    elif completed_games >= 5000:
        print(f"    ⚠️  Adequate games, but more would be better")
    else:
        print(f"    ❌ Insufficient games for robust training")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    
    print(f"\n  Dataset Size:")
    print(f"    {total_players:,} player-season records")
    print(f"    {completed_games:,} completed games")
    print(f"    {total_teams:,} teams")
    
    print(f"\n  Data Quality:")
    print(f"    KenPom coverage: {kenpom_score:.1f}%")
    print(f"    Box score coverage: {boxscore_score:.1f}%")
    
    print(f"\n  Status: ", end="")
    if overall_score >= 70 and completed_games >= 5000:
        print("✅ READY FOR MODEL TRAINING")
    else:
        print("⚠️  NEEDS MORE DATA")
    
    print("\n" + "="*80 + "\n")
    
    conn.close()


if __name__ == "__main__":
    main()

