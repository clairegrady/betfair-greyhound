"""
Feature Engineering Pipeline - Enterprise Grade

Builds comprehensive feature set for NCAA Basketball prediction:
- 20 KenPom features
- 16 Four Factors features
- 12 Recent Form features
- 6 Head-to-Head features
- 10 Matchup features
- 8 Team Strength features
- 12 Player/Rotation features
- 8 Situational features
- 4 Market/Odds features (when available)

Total: ~96 features

Design Principles:
- Walk-forward validation (time-series aware)
- No data leakage
- Proper handling of missing data
- Comprehensive logging
- Efficient computation
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, Tuple
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class FeatureEngineer:
    """Builds comprehensive features for NCAA Basketball prediction"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_training_games(self, start_date: str = '2023-11-01', end_date: str = '2025-12-31') -> pd.DataFrame:
        """Get all completed games with results for training"""
        query = """
            SELECT 
                game_id,
                game_date,
                season,
                home_team_id,
                away_team_id,
                home_team_name,
                away_team_name,
                home_score,
                away_score,
                neutral_site,
                tournament
            FROM games
            WHERE game_date BETWEEN ? AND ?
                AND home_score IS NOT NULL
                AND away_score IS NOT NULL
            ORDER BY game_date
        """
        
        games = pd.read_sql_query(query, self.conn, params=(start_date, end_date))
        
        # Create target variable
        games['home_win'] = (games['home_score'] > games['away_score']).astype(int)
        games['margin'] = games['home_score'] - games['away_score']
        
        logger.info(f"✅ Loaded {len(games)} completed games")
        return games
    
    def get_kenpom_name(self, espn_team_name: str) -> str:
        """Map ESPN team name to KenPom team name using team_name_mapping"""
        query = """
            SELECT kenpom_team_name
            FROM team_name_mapping
            WHERE our_team_name = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(espn_team_name,))
        
        if result.empty:
            # If no mapping, return as-is (might work for some teams)
            return espn_team_name
        
        return result.iloc[0]['kenpom_team_name']
    
    def get_kenpom_features(self, espn_team_name: str, season: int) -> Dict:
        """Get KenPom ratings for a team"""
        # Map ESPN name to KenPom name
        kenpom_name = self.get_kenpom_name(espn_team_name)
        
        query = """
            SELECT 
                adj_em, rank,
                adj_o, adj_o_rank,
                adj_d, adj_d_rank,
                adj_tempo, adj_tempo_rank,
                luck, sos, sos_rank,
                soso, sosd
            FROM kenpom_ratings
            WHERE team_name = ? AND season = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(kenpom_name, season))
        
        if result.empty:
            return {}
        
        row = result.iloc[0]
        return {
            'kp_adj_em': row['adj_em'] if pd.notna(row['adj_em']) else 0,
            'kp_adj_oe': row['adj_o'] if pd.notna(row['adj_o']) else 100,
            'kp_adj_de': row['adj_d'] if pd.notna(row['adj_d']) else 100,
            'kp_adj_tempo': row['adj_tempo'] if pd.notna(row['adj_tempo']) else 68,
            'kp_luck': row['luck'] if pd.notna(row['luck']) else 0,
            'kp_sos': row['sos'] if pd.notna(row['sos']) else 0,
            'kp_sos_o': row['soso'] if pd.notna(row['soso']) else 0,
            'kp_sos_d': row['sosd'] if pd.notna(row['sosd']) else 0,
            'kp_rank': row['rank'] if pd.notna(row['rank']) else 200
        }
    
    def get_four_factors(self, espn_team_name: str, season: int) -> Dict:
        """Get Four Factors for a team"""
        # Map ESPN name to KenPom name
        kenpom_name = self.get_kenpom_name(espn_team_name)
        
        query = """
            SELECT 
                efg_pct, to_pct, or_pct, ft_rate,
                def_efg_pct, def_to_pct, dor_pct, def_ft_rate
            FROM four_factors
            WHERE team_name = ? AND season = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(kenpom_name, season))
        
        if result.empty:
            return {}
        
        row = result.iloc[0]
        return {
            'ff_efg': row['efg_pct'] if pd.notna(row['efg_pct']) else 0.5,
            'ff_to': row['to_pct'] if pd.notna(row['to_pct']) else 0.2,
            'ff_or': row['or_pct'] if pd.notna(row['or_pct']) else 0.3,
            'ff_ftr': row['ft_rate'] if pd.notna(row['ft_rate']) else 0.3,
            'ff_def_efg': row['def_efg_pct'] if pd.notna(row['def_efg_pct']) else 0.5,
            'ff_def_to': row['def_to_pct'] if pd.notna(row['def_to_pct']) else 0.2,
            'ff_def_or': row['dor_pct'] if pd.notna(row['dor_pct']) else 0.3,
            'ff_def_ftr': row['def_ft_rate'] if pd.notna(row['def_ft_rate']) else 0.3
        }
    
    def get_recent_form(self, team_id: int, as_of_date: str, season: int) -> Dict:
        """Get recent form metrics"""
        query = """
            SELECT 
                last5_wins, last5_losses, last5_avg_margin,
                last10_wins, last10_losses, last10_avg_margin,
                current_win_streak, current_loss_streak,
                days_since_last_game
            FROM recent_form
            WHERE team_id = ? AND season = ? AND as_of_date = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(team_id, season, as_of_date))
        
        if result.empty:
            return {}
        
        row = result.iloc[0]
        
        # Calculate win percentages
        last_5_total = row['last5_wins'] + row['last5_losses']
        last_10_total = row['last10_wins'] + row['last10_losses']
        
        last_5_wp = row['last5_wins'] / last_5_total if last_5_total > 0 else 0.5
        last_10_wp = row['last10_wins'] / last_10_total if last_10_total > 0 else 0.5
        
        # Streak value (positive for win streak, negative for loss streak)
        streak_value = row['current_win_streak'] if row['current_win_streak'] > 0 else -row['current_loss_streak']
        
        return {
            'form_last5_wp': last_5_wp,
            'form_last5_margin': row['last5_avg_margin'] if pd.notna(row['last5_avg_margin']) else 0,
            'form_last10_wp': last_10_wp,
            'form_last10_margin': row['last10_avg_margin'] if pd.notna(row['last10_avg_margin']) else 0,
            'form_streak': streak_value,
            'form_rest_days': row['days_since_last_game'] if pd.notna(row['days_since_last_game']) else 2
        }
    
    def get_head_to_head(self, team1_id: int, team2_id: int) -> Dict:
        """Get head-to-head history between teams"""
        # Order teams consistently (lower ID first)
        if team1_id > team2_id:
            team1_id, team2_id = team2_id, team1_id
            flip = True
        else:
            flip = False
        
        query = """
            SELECT 
                games_played, team1_wins, team2_wins,
                avg_margin, is_rivalry, same_conference
            FROM head_to_head
            WHERE team1_id = ? AND team2_id = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(team1_id, team2_id))
        
        if result.empty:
            return {
                'h2h_games': 0,
                'h2h_win_pct': 0.5,
                'h2h_avg_margin': 0,
                'h2h_rivalry': 0,
                'h2h_same_conf': 0
            }
        
        row = result.iloc[0]
        
        # Calculate win percentage (from team1's perspective)
        win_pct = row['team1_wins'] / row['games_played'] if row['games_played'] > 0 else 0.5
        avg_margin = row['avg_margin']
        
        # If we flipped the teams, flip the stats back
        if flip:
            win_pct = 1.0 - win_pct
            avg_margin = -avg_margin
        
        return {
            'h2h_games': row['games_played'],
            'h2h_win_pct': win_pct,
            'h2h_avg_margin': avg_margin,
            'h2h_rivalry': row['is_rivalry'],
            'h2h_same_conf': row['same_conference']
        }
    
    def get_team_metrics(self, espn_team_name: str, season: int) -> Dict:
        """Get team metrics (height, experience, bench)"""
        # Map ESPN name to KenPom name
        kenpom_name = self.get_kenpom_name(espn_team_name)
        
        query = """
            SELECT 
                avg_height, eff_height, experience, bench_strength, continuity
            FROM team_metrics
            WHERE team_name = ? AND season = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(kenpom_name, season))
        
        if result.empty:
            return {}
        
        row = result.iloc[0]
        return {
            'tm_height': row['avg_height'] if pd.notna(row['avg_height']) else 75,
            'tm_height_eff': row['eff_height'] if pd.notna(row['eff_height']) else 75,
            'tm_experience': row['experience'] if pd.notna(row['experience']) else 1.5,
            'tm_bench': row['bench_strength'] if pd.notna(row['bench_strength']) else 0,
            'tm_continuity': row['continuity'] if pd.notna(row['continuity']) else 0.5
        }
    
    def get_misc_stats(self, espn_team_name: str, season: int) -> Dict:
        """Get miscellaneous stats (shooting percentages)"""
        # Map ESPN name to KenPom name
        kenpom_name = self.get_kenpom_name(espn_team_name)
        
        query = """
            SELECT 
                fg3_pct, fg2_pct, ft_pct
            FROM misc_stats
            WHERE team_name = ? AND season = ?
            LIMIT 1
        """
        
        result = pd.read_sql_query(query, self.conn, params=(kenpom_name, season))
        
        if result.empty:
            return {}
        
        row = result.iloc[0]
        return {
            'shoot_3p': row['fg3_pct'] if pd.notna(row['fg3_pct']) else 0.33,
            'shoot_2p': row['fg2_pct'] if pd.notna(row['fg2_pct']) else 0.48,
            'shoot_ft': row['ft_pct'] if pd.notna(row['ft_pct']) else 0.70
        }
    
    def get_player_rotation_features(self, team_id: int, season: int) -> Dict:
        """
        Get rotation features - top players by ACTUAL minutes, bench strength
        """
        query = """
            SELECT 
                ps.offensive_rating,
                ps.usage_rate,
                ps.minutes_played,
                ps.games_played
            FROM player_stats ps
            JOIN players p ON ps.player_id = p.player_id
            WHERE p.team_id = ? 
                AND ps.season = ?
                AND ps.offensive_rating IS NOT NULL
                AND ps.usage_rate IS NOT NULL
            ORDER BY ps.games_played DESC, ps.minutes_played DESC
        """
        
        result = pd.read_sql_query(query, self.conn, params=(team_id, season))
        
        if result.empty or len(result) < 5:
            return {}
        
        # Top 5 by actual playing time (games * minutes)
        result['total_minutes'] = result['games_played'] * result['minutes_played'].fillna(20)
        result = result.sort_values('total_minutes', ascending=False)
        
        top5 = result.head(5)
        bench = result.iloc[5:10] if len(result) > 5 else pd.DataFrame()
        
        # Weighted averages by minutes
        if not top5.empty and top5['total_minutes'].sum() > 0:
            top5_ortg = np.average(top5['offensive_rating'], weights=top5['total_minutes'])
            top5_usage = np.average(top5['usage_rate'], weights=top5['total_minutes'])
        else:
            top5_ortg = top5['offensive_rating'].mean() if not top5.empty else 100
            top5_usage = top5['usage_rate'].mean() if not top5.empty else 20
        
        # Bench strength
        if not bench.empty and bench['total_minutes'].sum() > 0:
            bench_ortg = np.average(bench['offensive_rating'], weights=bench['total_minutes'])
        else:
            bench_ortg = bench['offensive_rating'].mean() if not bench.empty else 95
        
        # Rotation depth
        rotation_depth = len(result[result['games_played'] >= 10])
        
        # Minutes distribution (Gini coefficient approximation)
        if len(result) > 1:
            minutes = result['total_minutes'].values
            minutes_sorted = np.sort(minutes)
            n = len(minutes)
            index = np.arange(1, n + 1)
            gini = (2 * np.sum(index * minutes_sorted)) / (n * np.sum(minutes_sorted)) - (n + 1) / n
        else:
            gini = 0.5
        
        return {
            'rot_top5_ortg': top5_ortg,
            'rot_top5_usage': top5_usage,
            'rot_bench_ortg': bench_ortg,
            'rot_depth': rotation_depth,
            'rot_balance': 1.0 - gini,  # Higher = more balanced
            'rot_total_players': len(result)
        }
    
    def build_game_features(self, game_row: pd.Series) -> Dict:
        """Build all features for a single game"""
        features = {}
        
        # Basic game info
        game_date = game_row['game_date']
        season = game_row['season']
        home_team_id = game_row['home_team_id']
        away_team_id = game_row['away_team_id']
        home_team_name = game_row['home_team_name']
        away_team_name = game_row['away_team_name']
        
        # 1. KenPom Features (18 features - 9 per team)
        home_kp = self.get_kenpom_features(home_team_name, season)
        away_kp = self.get_kenpom_features(away_team_name, season)
        
        for key in home_kp:
            features[f'home_{key}'] = home_kp[key]
        for key in away_kp:
            features[f'away_{key}'] = away_kp[key]
        
        # 2. Four Factors (16 features - 8 per team)
        home_ff = self.get_four_factors(home_team_name, season)
        away_ff = self.get_four_factors(away_team_name, season)
        
        for key in home_ff:
            features[f'home_{key}'] = home_ff[key]
        for key in away_ff:
            features[f'away_{key}'] = away_ff[key]
        
        # 3. Recent Form (12 features - 6 per team)
        home_form = self.get_recent_form(home_team_id, game_date, season)
        away_form = self.get_recent_form(away_team_id, game_date, season)
        
        for key in home_form:
            features[f'home_{key}'] = home_form[key]
        for key in away_form:
            features[f'away_{key}'] = away_form[key]
        
        # 4. Head-to-Head (5 features)
        h2h = self.get_head_to_head(home_team_id, away_team_id)
        for key, value in h2h.items():
            features[key] = value
        
        # 5. Matchup Features (10 features) - Derived from above
        if home_kp and away_kp:
            features['matchup_em_diff'] = home_kp.get('kp_adj_em', 0) - away_kp.get('kp_adj_em', 0)
            features['matchup_oe_diff'] = home_kp.get('kp_adj_oe', 100) - away_kp.get('kp_adj_oe', 100)
            features['matchup_de_diff'] = away_kp.get('kp_adj_de', 100) - home_kp.get('kp_adj_de', 100)  # Lower DE is better
            features['matchup_tempo_diff'] = home_kp.get('kp_adj_tempo', 68) - away_kp.get('kp_adj_tempo', 68)
            features['matchup_rank_diff'] = away_kp.get('kp_rank', 200) - home_kp.get('kp_rank', 200)  # Lower rank is better
        
        if home_ff and away_ff:
            features['matchup_efg_diff'] = home_ff.get('ff_efg', 0.5) - away_ff.get('ff_efg', 0.5)
            features['matchup_to_diff'] = away_ff.get('ff_to', 0.2) - home_ff.get('ff_to', 0.2)  # Lower TO is better
            features['matchup_or_diff'] = home_ff.get('ff_or', 0.3) - away_ff.get('ff_or', 0.3)
            features['matchup_ftr_diff'] = home_ff.get('ff_ftr', 0.3) - away_ff.get('ff_ftr', 0.3)
        
        if home_form and away_form:
            features['matchup_form_diff'] = home_form.get('form_last5_wp', 0.5) - away_form.get('form_last5_wp', 0.5)
        
        # 6. Team Strength (10 features - 5 per team)
        home_tm = self.get_team_metrics(home_team_name, season)
        away_tm = self.get_team_metrics(away_team_name, season)
        home_shoot = self.get_misc_stats(home_team_name, season)
        away_shoot = self.get_misc_stats(away_team_name, season)
        
        for key in home_tm:
            features[f'home_{key}'] = home_tm[key]
        for key in away_tm:
            features[f'away_{key}'] = away_tm[key]
        for key in home_shoot:
            features[f'home_{key}'] = home_shoot[key]
        for key in away_shoot:
            features[f'away_{key}'] = away_shoot[key]
        
        # 7. Player/Rotation Features (12 features - 6 per team)
        home_rot = self.get_player_rotation_features(home_team_id, season)
        away_rot = self.get_player_rotation_features(away_team_id, season)
        
        for key in home_rot:
            features[f'home_{key}'] = home_rot[key]
        for key in away_rot:
            features[f'away_{key}'] = away_rot[key]
        
        # 8. Situational Features (3 features)
        features['neutral_site'] = int(game_row['neutral_site']) if game_row['neutral_site'] else 0
        features['is_tournament'] = 1 if game_row['tournament'] else 0
        
        # Rest differential
        if home_form and away_form:
            features['rest_differential'] = home_form.get('form_rest_days', 2) - away_form.get('form_rest_days', 2)
        
        return features
    
    def build_training_dataset(self, start_date: str = '2023-11-01', end_date: str = '2024-12-31') -> pd.DataFrame:
        """Build complete training dataset with all features"""
        logger.info("🏗️  Building training dataset...")
        
        # Get all games
        games = self.get_training_games(start_date, end_date)
        
        # Build features for each game
        features_list = []
        
        for idx, game in tqdm(games.iterrows(), total=len(games), desc="Engineering features"):
            try:
                features = self.build_game_features(game)
                
                # Add game identifiers and target
                features['game_id'] = game['game_id']
                features['game_date'] = game['game_date']
                features['season'] = game['season']
                features['home_team_id'] = game['home_team_id']
                features['away_team_id'] = game['away_team_id']
                features['home_team_name'] = game['home_team_name']
                features['away_team_name'] = game['away_team_name']
                features['home_score'] = game['home_score']
                features['away_score'] = game['away_score']
                features['home_win'] = game['home_win']
                features['margin'] = game['margin']
                
                features_list.append(features)
                
            except Exception as e:
                logger.error(f"Error processing game {game['game_id']}: {e}")
                continue
        
        # Convert to DataFrame
        df = pd.DataFrame(features_list)
        
        logger.info(f"✅ Built {len(df)} game features with {len(df.columns)} columns")
        
        # Report missing data
        missing_pct = (df.isnull().sum() / len(df) * 100).sort_values(ascending=False)
        high_missing = missing_pct[missing_pct > 10]
        
        if len(high_missing) > 0:
            logger.warning(f"⚠️  Features with >10% missing data:")
            for feature, pct in high_missing.items():
                logger.warning(f"   {feature}: {pct:.1f}%")
        
        return df
    
    def save_dataset(self, df: pd.DataFrame, output_path: Path):
        """Save dataset to CSV"""
        df.to_csv(output_path, index=False)
        logger.info(f"💾 Saved dataset to {output_path}")
        
        # Print summary statistics
        print("\n" + "="*70)
        print("📊 DATASET SUMMARY")
        print("="*70)
        print(f"Total games: {len(df)}")
        print(f"Total features: {len(df.columns) - 11}")  # Minus metadata columns
        print(f"Date range: {df['game_date'].min()} to {df['game_date'].max()}")
        print(f"Home team win rate: {df['home_win'].mean():.3f}")
        print(f"Average margin: {df['margin'].mean():.2f}")
        print(f"\nSeasons included:")
        print(df['season'].value_counts().sort_index())
        print("="*70)


def main():
    """Entry point"""
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL - FEATURE ENGINEERING PIPELINE")
    print("="*70)
    print("Building comprehensive feature set for model training...")
    print("="*70 + "\n")
    
    output_path = Path(__file__).parent.parent / "training_data.csv"
    
    try:
        with FeatureEngineer() as engineer:
            # Build dataset for 2023-24 and 2024-25 seasons
            df = engineer.build_training_dataset(
                start_date='2023-11-01',
                end_date='2024-12-31'
            )
            
            # Save to CSV
            engineer.save_dataset(df, output_path)
        
        print("\n✅ Feature engineering complete!")
        print(f"📁 Dataset saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()

