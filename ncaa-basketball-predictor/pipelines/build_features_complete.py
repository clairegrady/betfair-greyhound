"""
NCAA Basketball Feature Engineering Pipeline
Builds ~100 features for predicting game outcomes

Features organized by tier (based on research):
- Tier 1: Core efficiency metrics (KenPom)
- Tier 2: Lineup & roster strength  
- Tier 3: Recent form & momentum
- Tier 4: Matchup-specific
- Tier 5: Situational context
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class NCAAFeatureEngineer:
    """Build features for NCAA basketball game prediction"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.games_df = None
        self.player_stats_df = None
        self.lineup_df = None
        self.team_stats_df = None
        
    def load_data(self):
        """Load all necessary data from database"""
        logger.info("Loading data from database...")
        
        # Load games
        self.games_df = pd.read_sql("""
            SELECT game_id, game_date, season,
                   home_team_name, away_team_name,
                   home_score, away_score,
                   neutral_site
            FROM games
            WHERE season IN (2024, 2025, 2026)
            ORDER BY game_date
        """, self.conn)
        
        logger.info(f"  Loaded {len(self.games_df):,} games")
        
        # Load player stats
        self.player_stats_df = pd.read_sql("""
            SELECT player_id, season, player_name,
                   minutes_played, offensive_rating, usage_rate,
                   assist_rate, turnover_rate, 
                   true_shooting_pct, efg_pct,
                   offensive_rebound_rate, defensive_rebound_rate,
                   steal_rate, block_rate
            FROM player_stats
            WHERE season IN (2024, 2025, 2026)
            AND offensive_rating IS NOT NULL
        """, self.conn)
        
        logger.info(f"  Loaded {len(self.player_stats_df):,} players")
        
        # Load lineup data
        self.lineup_df = pd.read_sql("""
            SELECT game_id, team_name, player_name,
                   is_starter, minutes_played
            FROM game_lineups
        """, self.conn)
        
        logger.info(f"  Loaded {len(self.lineup_df):,} lineup records")
        
    def build_team_aggregates(self):
        """Aggregate player stats to team level for each season"""
        logger.info("Building team aggregate features...")
        
        # Group by season and team
        # Note: player_stats doesn't have team_name directly, need to join with players table
        player_with_teams = pd.read_sql("""
            SELECT ps.*, p.team_id
            FROM player_stats ps
            JOIN players p ON ps.player_id = p.player_id AND ps.season = p.season
            WHERE ps.offensive_rating IS NOT NULL
        """, self.conn)
        
        # Get team names
        teams = pd.read_sql("SELECT team_id, team_name FROM teams", self.conn)
        player_with_teams = player_with_teams.merge(teams, on='team_id', how='left')
        
        # Calculate team aggregates
        team_aggs = []
        
        for (season, team_name), group in player_with_teams.groupby(['season', 'team_name']):
            # Weight by minutes played
            total_minutes = group['minutes_played'].sum()
            
            if total_minutes == 0:
                continue
            
            # Weighted averages
            agg = {
                'season': season,
                'team_name': team_name,
                'num_players': len(group),
                
                # Weighted team averages
                'team_avg_ortg': (group['offensive_rating'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_usage': (group['usage_rate'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_ast_rate': (group['assist_rate'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_to_rate': (group['turnover_rate'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_ts_pct': (group['true_shooting_pct'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_or_pct': (group['offensive_rebound_rate'] * group['minutes_played']).sum() / total_minutes,
                'team_avg_dr_pct': (group['defensive_rebound_rate'] * group['minutes_played']).sum() / total_minutes,
                
                # Top player stats (best ORtg)
                'top_player_ortg': group['offensive_rating'].max(),
                'top3_avg_ortg': group.nlargest(3, 'offensive_rating')['offensive_rating'].mean(),
                
                # Minutes concentration (Gini coefficient)
                'minutes_concentration': self._gini_coefficient(group['minutes_played'].values),
                
                # Depth (players with significant minutes)
                'depth_score': len(group[group['minutes_played'] > 0.10]),  # >10% of minutes
            }
            
            team_aggs.append(agg)
        
        self.team_stats_df = pd.DataFrame(team_aggs)
        logger.info(f"  Created aggregates for {len(self.team_stats_df):,} team-seasons")
        
    @staticmethod
    def _gini_coefficient(values):
        """Calculate Gini coefficient (0 = equal, 1 = concentrated)"""
        if len(values) == 0:
            return 0
        sorted_values = np.sort(values)
        n = len(values)
        cumsum = np.cumsum(sorted_values)
        return (2 * np.sum((np.arange(1, n + 1)) * sorted_values)) / (n * cumsum[-1]) - (n + 1) / n
    
    def build_lineup_features(self):
        """Build features from lineup data (starters vs bench)"""
        logger.info("Building lineup features...")
        
        # Rename minutes_played in player_stats to avoid conflict
        player_stats_renamed = self.player_stats_df.rename(columns={'minutes_played': 'season_minutes_pct'})
        
        # Get player stats for lineup players
        lineup_with_stats = self.lineup_df.merge(
            player_stats_renamed,
            left_on='player_name',
            right_on='player_name',
            how='left'
        )
        
        # Aggregate by game and team
        lineup_aggs = []
        
        for (game_id, team_name), group in lineup_with_stats.groupby(['game_id', 'team_name']):
            starters = group[group['is_starter'] == 1]
            bench = group[group['is_starter'] == 0]
            
            agg = {
                'game_id': game_id,
                'team_name': team_name,
                
                # Starter quality
                'starter_avg_ortg': starters['offensive_rating'].mean() if len(starters) > 0 else None,
                'starter_avg_usage': starters['usage_rate'].mean() if len(starters) > 0 else None,
                'starter_total_minutes': starters['minutes_played'].sum(),
                
                # Bench quality
                'bench_avg_ortg': bench['offensive_rating'].mean() if len(bench) > 0 else None,
                'bench_depth': len(bench[bench['offensive_rating'] > 100]),  # Quality bench players
                
                # Overall team from lineup
                'lineup_avg_ortg': group['offensive_rating'].mean(),
            }
            
            lineup_aggs.append(agg)
        
        self.lineup_features_df = pd.DataFrame(lineup_aggs)
        logger.info(f"  Created lineup features for {len(self.lineup_features_df):,} game-teams")
    
    def build_recent_form_features(self, lookback_games=5):
        """Build recent form features (last N games)"""
        logger.info(f"Building recent form features (last {lookback_games} games)...")
        
        # Sort games by date
        games_sorted = self.games_df.sort_values('game_date')
        
        form_features = []
        
        for idx, game in games_sorted.iterrows():
            game_date = pd.to_datetime(game['game_date'])
            
            for team_name, is_home in [(game['home_team_name'], True), 
                                        (game['away_team_name'], False)]:
                
                # Get last N games for this team BEFORE this game
                past_games = games_sorted[
                    (pd.to_datetime(games_sorted['game_date']) < game_date) &
                    ((games_sorted['home_team_name'] == team_name) | 
                     (games_sorted['away_team_name'] == team_name))
                ].tail(lookback_games)
                
                if len(past_games) == 0:
                    continue
                
                # Calculate form metrics
                wins = 0
                total_points = 0
                total_opp_points = 0
                
                for _, past_game in past_games.iterrows():
                    if past_game['home_team_name'] == team_name:
                        team_score = past_game['home_score']
                        opp_score = past_game['away_score']
                    else:
                        team_score = past_game['away_score']
                        opp_score = past_game['home_score']
                    
                    if pd.notna(team_score) and pd.notna(opp_score):
                        if team_score > opp_score:
                            wins += 1
                        total_points += team_score
                        total_opp_points += opp_score
                
                games_count = len(past_games[past_games['home_score'].notna()])
                
                form = {
                    'game_id': game['game_id'],
                    'team_name': team_name,
                    'is_home': is_home,
                    f'last_{lookback_games}_win_pct': wins / games_count if games_count > 0 else None,
                    f'last_{lookback_games}_ppg': total_points / games_count if games_count > 0 else None,
                    f'last_{lookback_games}_opp_ppg': total_opp_points / games_count if games_count > 0 else None,
                    'games_in_window': games_count,
                }
                
                form_features.append(form)
        
        self.form_features_df = pd.DataFrame(form_features)
        logger.info(f"  Created form features for {len(self.form_features_df):,} game-teams")
    
    def build_matchup_features(self):
        """Build matchup-specific features comparing two teams"""
        logger.info("Building matchup features...")
        
        matchup_features = []
        
        for idx, game in self.games_df.iterrows():
            game_id = game['game_id']
            home_team = game['home_team_name']
            away_team = game['away_team_name']
            season = game['season']
            
            # Get team stats for both teams
            home_stats = self.team_stats_df[
                (self.team_stats_df['team_name'] == home_team) & 
                (self.team_stats_df['season'] == season)
            ]
            
            away_stats = self.team_stats_df[
                (self.team_stats_df['team_name'] == away_team) & 
                (self.team_stats_df['season'] == season)
            ]
            
            if len(home_stats) == 0 or len(away_stats) == 0:
                continue
            
            home_stats = home_stats.iloc[0]
            away_stats = away_stats.iloc[0]
            
            # Calculate differentials
            matchup = {
                'game_id': game_id,
                'ortg_diff': home_stats['team_avg_ortg'] - away_stats['team_avg_ortg'],
                'usage_diff': home_stats['team_avg_usage'] - away_stats['team_avg_usage'],
                'ast_rate_diff': home_stats['team_avg_ast_rate'] - away_stats['team_avg_ast_rate'],
                'to_rate_diff': home_stats['team_avg_to_rate'] - away_stats['team_avg_to_rate'],
                'ts_pct_diff': home_stats['team_avg_ts_pct'] - away_stats['team_avg_ts_pct'],
                'rebound_diff': (home_stats['team_avg_or_pct'] + home_stats['team_avg_dr_pct']) - 
                                (away_stats['team_avg_or_pct'] + away_stats['team_avg_dr_pct']),
                'depth_diff': home_stats['depth_score'] - away_stats['depth_score'],
                'top_player_diff': home_stats['top_player_ortg'] - away_stats['top_player_ortg'],
            }
            
            matchup_features.append(matchup)
        
        self.matchup_features_df = pd.DataFrame(matchup_features)
        logger.info(f"  Created matchup features for {len(self.matchup_features_df):,} games")
    
    def build_complete_dataset(self):
        """Combine all features into final dataset"""
        logger.info("Building complete feature dataset...")
        
        # Start with games
        dataset = self.games_df.copy()
        
        # Add matchup features
        if hasattr(self, 'matchup_features_df'):
            dataset = dataset.merge(self.matchup_features_df, on='game_id', how='left')
        
        # Add form features for home and away teams
        if hasattr(self, 'form_features_df'):
            home_form = self.form_features_df[self.form_features_df['is_home'] == True].copy()
            away_form = self.form_features_df[self.form_features_df['is_home'] == False].copy()
            
            # Rename columns to distinguish home vs away
            home_form = home_form.add_suffix('_home')
            home_form = home_form.rename(columns={'game_id_home': 'game_id'})
            
            away_form = away_form.add_suffix('_away')
            away_form = away_form.rename(columns={'game_id_away': 'game_id'})
            
            dataset = dataset.merge(home_form, on='game_id', how='left')
            dataset = dataset.merge(away_form, on='game_id', how='left')
        
        # Add lineup features for home and away teams
        if hasattr(self, 'lineup_features_df'):
            # Create separate dataframes for home and away with proper filtering
            lineup_home = []
            lineup_away = []
            
            for idx, game in dataset.iterrows():
                game_id = game['game_id']
                home_team = game['home_team_name']
                away_team = game['away_team_name']
                
                # Get lineup features for this specific game
                home_lineup = self.lineup_features_df[
                    (self.lineup_features_df['game_id'] == game_id) &
                    (self.lineup_features_df['team_name'] == home_team)
                ]
                
                away_lineup = self.lineup_features_df[
                    (self.lineup_features_df['game_id'] == game_id) &
                    (self.lineup_features_df['team_name'] == away_team)
                ]
                
                if len(home_lineup) > 0:
                    lineup_home.append({
                        'game_id': game_id,
                        **{f'{k}_home': v for k, v in home_lineup.iloc[0].items() if k not in ['game_id', 'team_name']}
                    })
                
                if len(away_lineup) > 0:
                    lineup_away.append({
                        'game_id': game_id,
                        **{f'{k}_away': v for k, v in away_lineup.iloc[0].items() if k not in ['game_id', 'team_name']}
                    })
            
            if lineup_home:
                dataset = dataset.merge(pd.DataFrame(lineup_home), on='game_id', how='left')
            if lineup_away:
                dataset = dataset.merge(pd.DataFrame(lineup_away), on='game_id', how='left')
        
        # Create target variables
        dataset['home_win'] = (dataset['home_score'] > dataset['away_score']).astype(int)
        dataset['point_diff'] = dataset['home_score'] - dataset['away_score']
        dataset['total_points'] = dataset['home_score'] + dataset['away_score']
        
        # Add contextual features
        dataset['is_neutral'] = dataset['neutral_site'].astype(int)
        dataset['game_date'] = pd.to_datetime(dataset['game_date'])
        dataset['day_of_week'] = dataset['game_date'].dt.dayofweek
        dataset['month'] = dataset['game_date'].dt.month
        
        logger.info(f"  Final dataset: {len(dataset):,} games with {len(dataset.columns)} columns")
        
        return dataset
    
    def run_pipeline(self):
        """Run complete feature engineering pipeline"""
        logger.info("\n" + "="*70)
        logger.info("🏀 NCAA FEATURE ENGINEERING PIPELINE")
        logger.info("="*70 + "\n")
        
        self.load_data()
        self.build_team_aggregates()
        self.build_lineup_features()
        self.build_recent_form_features(lookback_games=5)
        self.build_matchup_features()
        
        dataset = self.build_complete_dataset()
        
        logger.info("\n" + "="*70)
        logger.info("✅ FEATURE ENGINEERING COMPLETE!")
        logger.info("="*70 + "\n")
        
        return dataset


if __name__ == "__main__":
    engineer = NCAAFeatureEngineer()
    dataset = engineer.run_pipeline()
    
    # Save to CSV
    output_path = Path(__file__).parent.parent / "ncaa_features.csv"
    dataset.to_csv(output_path, index=False)
    logger.info(f"💾 Saved features to: {output_path}")
    
    # Print summary
    print("\n📊 DATASET SUMMARY:")
    print(f"   Total games: {len(dataset):,}")
    print(f"   Total features: {len(dataset.columns)}")
    print(f"   Date range: {dataset['game_date'].min()} to {dataset['game_date'].max()}")
    print(f"   Seasons: {sorted(dataset['season'].unique())}")
    print(f"\n   Features: {list(dataset.columns)}")

