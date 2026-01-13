"""
Feature Engineering Pipeline for NCAA Basketball Prediction
Generates ~100 features for each game matchup

Features are split into tiers:
- Tier 1: Team efficiency metrics (KenPom)
- Tier 2: Lineup & roster strength (aggregated player data)
- Tier 3: Recent form & momentum
- Tier 4: Matchup-specific features
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


class NCAAFeatureEngineering:
    """Feature engineering for NCAA basketball games"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.team_stats_cache = {}
        self.player_stats_cache = {}
        
    def load_games(self, seasons=[2024, 2025, 2026]):
        """Load all games with scores for specified seasons"""
        
        query = """
            SELECT 
                game_id,
                game_date,
                season,
                home_team_name,
                away_team_name,
                home_score,
                away_score,
                neutral_site,
                tournament
            FROM games
            WHERE season IN ({})
            AND home_score IS NOT NULL
            AND away_score IS NOT NULL
            ORDER BY game_date
        """.format(','.join('?' * len(seasons)))
        
        df = pd.read_sql_query(query, self.conn, params=seasons)
        df['game_date'] = pd.to_datetime(df['game_date'])
        
        logger.info(f"Loaded {len(df):,} games from seasons {seasons}")
        return df
    
    def get_team_player_aggregates(self, team_name, season, as_of_date=None):
        """
        Aggregate player stats to team level for a specific season
        This handles the roster change problem - each season is independent
        
        Improved matching: handles "Duke Blue Devils" -> "Duke" mapping
        """
        
        cache_key = f"{team_name}_{season}_{as_of_date}"
        if cache_key in self.player_stats_cache:
            return self.player_stats_cache[cache_key]
        
        # Try multiple matching strategies
        # 1. Direct match
        # 2. Partial match (e.g., "Duke" in "Duke Blue Devils")
        # 3. Remove mascot (e.g., "Duke Blue Devils" -> "Duke")
        
        # Extract base name (remove common mascots)
        base_name = team_name
        mascots = ['Wildcats', 'Tigers', 'Bulldogs', 'Eagles', 'Panthers', 'Bears', 
                   'Spartans', 'Trojans', 'Huskies', 'Cougars', 'Cardinals', 'Cowboys',
                   'Blue Devils', 'Tar Heels', 'Crimson Tide', 'Volunteers', 'Gators',
                   'Razorbacks', 'Aggies', 'Longhorns', 'Sooners', 'Jayhawks',
                   'Red Storm', 'Hoyas', 'Orangemen', 'Orange', 'Badgers']
        
        for mascot in mascots:
            if team_name.endswith(mascot):
                base_name = team_name.replace(mascot, '').strip()
                break
        
        # Query player_stats using the team_name column (much faster!)
        query = """
            SELECT 
                offensive_rating,
                usage_rate,
                minutes_played,
                assist_rate,
                turnover_rate,
                true_shooting_pct,
                games_played
            FROM player_stats
            WHERE season = ?
            AND offensive_rating IS NOT NULL
            AND (
                team_name = ? OR
                team_name LIKE ? OR
                team_name LIKE ?
            )
        """
        
        # Try various name formats
        like_pattern1 = f"%{base_name}%"
        like_pattern2 = f"%{team_name.split()[0]}%"
        
        df = pd.read_sql_query(query, self.conn, 
                               params=(season, team_name, like_pattern1, like_pattern2))
        
        if len(df) == 0:
            return None
        
        # Calculate team aggregates
        aggregates = {
            'avg_player_ortg': df['offensive_rating'].mean(),
            'top_player_ortg': df['offensive_rating'].max(),
            'top3_avg_ortg': df.nlargest(3, 'offensive_rating')['offensive_rating'].mean(),
            'avg_usage': df['usage_rate'].mean(),
            'avg_assist_rate': df['assist_rate'].mean(),
            'avg_turnover_rate': df['turnover_rate'].mean(),
            'roster_depth': len(df[df['minutes_played'] > 10]),  # Players with significant minutes
            'minutes_concentration': df.nlargest(5, 'minutes_played')['minutes_played'].sum() / df['minutes_played'].sum() if df['minutes_played'].sum() > 0 else 0
        }
        
        self.player_stats_cache[cache_key] = aggregates
        return aggregates
    
    def get_team_lineup_features(self, team_name, game_id):
        """Get lineup-specific features for this game"""
        
        query = """
            SELECT 
                player_name,
                is_starter,
                minutes_played
            FROM game_lineups
            WHERE game_id = ?
            AND team_name LIKE ?
        """
        
        df = pd.read_sql_query(query, self.conn, params=(game_id, f"%{team_name}%"))
        
        if len(df) == 0:
            return {}
        
        starters = df[df['is_starter'] == 1]
        bench = df[df['is_starter'] == 0]
        
        return {
            'num_starters': len(starters),
            'starter_minutes_pct': starters['minutes_played'].sum() / df['minutes_played'].sum() if df['minutes_played'].sum() > 0 else 0,
            'bench_depth': len(bench[bench['minutes_played'] > 5]),
        }
    
    def get_recent_form(self, team_name, current_date, season, num_games=5):
        """Calculate recent form (last N games)"""
        
        # Convert pandas Timestamp to string for SQL
        if isinstance(current_date, pd.Timestamp):
            current_date_str = current_date.strftime('%Y-%m-%d')
        else:
            current_date_str = str(current_date)
        
        query = """
            SELECT 
                game_date,
                CASE 
                    WHEN home_team_name = ? AND home_score > away_score THEN 1
                    WHEN away_team_name = ? AND away_score > home_score THEN 1
                    ELSE 0
                END as won,
                CASE
                    WHEN home_team_name = ? THEN home_score - away_score
                    ELSE away_score - home_score
                END as point_diff
            FROM games
            WHERE season = ?
            AND game_date < ?
            AND (home_team_name = ? OR away_team_name = ?)
            AND home_score IS NOT NULL
            ORDER BY game_date DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, self.conn, 
                               params=(team_name, team_name, team_name, season, 
                                      current_date_str, team_name, team_name, num_games))
        
        if len(df) == 0:
            return {
                f'last{num_games}_win_pct': 0.5,  # Default to 50%
                f'last{num_games}_avg_margin': 0,
                f'games_played': 0
            }
        
        return {
            f'last{num_games}_win_pct': df['won'].mean(),
            f'last{num_games}_avg_margin': df['point_diff'].mean(),
            f'games_played': len(df)
        }
    
    def build_game_features(self, game_row):
        """Build all features for a single game"""
        
        game_id = game_row['game_id']
        game_date = game_row['game_date']
        season = game_row['season']
        home_team = game_row['home_team_name']
        away_team = game_row['away_team_name']
        neutral_site = game_row['neutral_site']
        
        features = {
            'game_id': game_id,
            'game_date': game_date,
            'season': season,
            'home_team': home_team,
            'away_team': away_team,
        }
        
        # Target variables
        features['home_won'] = 1 if game_row['home_score'] > game_row['away_score'] else 0
        features['point_margin'] = game_row['home_score'] - game_row['away_score']
        features['total_points'] = game_row['home_score'] + game_row['away_score']
        
        # Get team player aggregates
        home_players = self.get_team_player_aggregates(home_team, season, game_date)
        away_players = self.get_team_player_aggregates(away_team, season, game_date)
        
        if home_players:
            for key, value in home_players.items():
                features[f'home_{key}'] = value
        
        if away_players:
            for key, value in away_players.items():
                features[f'away_{key}'] = value
        
        # Get lineup features
        home_lineup = self.get_team_lineup_features(home_team, game_id)
        away_lineup = self.get_team_lineup_features(away_team, game_id)
        
        for key, value in home_lineup.items():
            features[f'home_{key}'] = value
        
        for key, value in away_lineup.items():
            features[f'away_{key}'] = value
        
        # Recent form
        home_form_5 = self.get_recent_form(home_team, game_date, season, 5)
        away_form_5 = self.get_recent_form(away_team, game_date, season, 5)
        
        home_form_10 = self.get_recent_form(home_team, game_date, season, 10)
        away_form_10 = self.get_recent_form(away_team, game_date, season, 10)
        
        for key, value in home_form_5.items():
            features[f'home_{key}'] = value
        
        for key, value in away_form_5.items():
            features[f'away_{key}'] = value
        
        for key, value in home_form_10.items():
            features[f'home_{key}'] = value
        
        for key, value in away_form_10.items():
            features[f'away_{key}'] = value
        
        # Situational features
        features['neutral_site'] = 1 if neutral_site else 0
        features['is_tournament'] = 1 if game_row.get('tournament') else 0
        
        # Calculate differentials (matchup features)
        if home_players and away_players:
            features['ortg_diff'] = home_players['avg_player_ortg'] - away_players['avg_player_ortg']
            features['top_player_diff'] = home_players['top_player_ortg'] - away_players['top_player_ortg']
            features['depth_diff'] = home_players['roster_depth'] - away_players['roster_depth']
        
        return features
    
    def build_all_features(self, seasons=[2024, 2025, 2026]):
        """Build features for all games"""
        
        logger.info(f"Building features for seasons: {seasons}")
        
        games_df = self.load_games(seasons)
        
        all_features = []
        
        for idx, game_row in games_df.iterrows():
            if (idx + 1) % 500 == 0:
                logger.info(f"Processing game {idx + 1:,} / {len(games_df):,}")
            
            try:
                features = self.build_game_features(game_row)
                all_features.append(features)
            except Exception as e:
                logger.error(f"Error processing game {game_row['game_id']}: {e}")
                continue
        
        features_df = pd.DataFrame(all_features)
        
        logger.info(f"\n✅ Feature engineering complete!")
        logger.info(f"   Games processed: {len(features_df):,}")
        logger.info(f"   Features created: {len(features_df.columns):,}")
        logger.info(f"   Feature columns: {list(features_df.columns)}")
        
        return features_df
    
    def save_features(self, features_df, output_path="features_dataset.csv"):
        """Save features to CSV"""
        output_file = Path(__file__).parent.parent / output_path
        features_df.to_csv(output_file, index=False)
        logger.info(f"\n💾 Features saved to: {output_file}")
        return output_file


def build_features_for_game(game_id, home_team, away_team, game_date, season):
    """
    Build features for a single game (for live prediction).
    
    Args:
        game_id: Game identifier
        home_team: Home team name
        away_team: Away team name
        game_date: Game date (string or datetime)
        season: Season year
    
    Returns:
        dict: Feature dictionary ready for model input, or None if features can't be built
    """
    try:
        fe = NCAAFeatureEngineering()
        
        # Convert game_date to datetime if it's a string
        if isinstance(game_date, str):
            game_date = pd.to_datetime(game_date)
        
        # Get player aggregates for both teams
        home_aggregates = fe.get_team_player_aggregates(home_team, season, game_date)
        away_aggregates = fe.get_team_player_aggregates(away_team, season, game_date)
        
        if home_aggregates is None or away_aggregates is None:
            logger.warning(f"Missing player aggregates for {home_team} vs {away_team}")
            return None
        
        # Build feature dict
        features = {}
        
        # Home team features
        for key, value in home_aggregates.items():
            features[f'home_{key}'] = value
        
        # Away team features
        for key, value in away_aggregates.items():
            features[f'away_{key}'] = value
        
        # Differential features
        for key in home_aggregates.keys():
            features[f'diff_{key}'] = home_aggregates[key] - away_aggregates[key]
        
        # Fill any missing values with 0
        for key in features:
            if pd.isna(features[key]):
                features[key] = 0.0
        
        logger.debug(f"Built {len(features)} features for {home_team} vs {away_team}")
        return features
        
    except Exception as e:
        logger.error(f"Error building features for game {game_id}: {e}")
        return None


def main():
    """Main execution"""
    
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL FEATURE ENGINEERING")
    print("="*70 + "\n")
    
    fe = NCAAFeatureEngineering()
    
    # Build features for all games
    features_df = fe.build_all_features(seasons=[2024, 2025, 2026])
    
    # Save to CSV
    output_file = fe.save_features(features_df)
    
    # Print summary statistics
    print("\n" + "="*70)
    print("📊 FEATURE SUMMARY")
    print("="*70)
    print(f"Total games: {len(features_df):,}")
    print(f"Total features: {len(features_df.columns):,}")
    print(f"\nFeature categories:")
    
    player_features = [c for c in features_df.columns if 'ortg' in c or 'usage' in c or 'depth' in c]
    lineup_features = [c for c in features_df.columns if 'starter' in c or 'bench' in c]
    form_features = [c for c in features_df.columns if 'last' in c or 'win_pct' in c]
    
    print(f"  Player aggregate features: {len(player_features)}")
    print(f"  Lineup features: {len(lineup_features)}")
    print(f"  Recent form features: {len(form_features)}")
    
    # Check for missing data
    print(f"\nMissing data:")
    missing = features_df.isnull().sum()
    if missing.sum() > 0:
        print(missing[missing > 0])
    else:
        print("  ✅ No missing data!")
    
    print("\n" + "="*70)
    print(f"✅ READY FOR MODEL TRAINING!")
    print(f"   Dataset: {output_file}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

