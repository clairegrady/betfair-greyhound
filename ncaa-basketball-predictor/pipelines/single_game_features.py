"""
Single Game Feature Builder - For Real-Time Predictions

Builds features for a single upcoming game using current database state.
Used by paper trading system to evaluate betting opportunities.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parents[1] / "ncaa_basketball.db"


class SingleGameFeatureBuilder:
    """Builds features for a single game for real-time prediction"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
    
    def _get_kenpom_team_name(self, espn_team_name: str) -> str:
        """Map ESPN team name to KenPom name"""
        query = "SELECT kenpom_name FROM teams WHERE team_name = ?"
        result = self.cursor.execute(query, (espn_team_name,)).fetchone()
        return result[0] if result else espn_team_name
    
    def _get_kenpom_features(self, team_name: str, season: int, as_of_date: date):
        """Get latest KenPom features for a team"""
        kenpom_name = self._get_kenpom_team_name(team_name)
        
        query = """
            SELECT 
                adj_em, rank, adj_o, adj_o_rank, adj_d, adj_d_rank,
                adj_tempo, adj_tempo_rank, luck, sos, sos_rank,
                soso, soso_rank, sosd, sosd_rank, ncsos, ncsos_rank
            FROM kenpom_ratings
            WHERE team_name = ? AND season = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """
        
        result = self.cursor.execute(query, (kenpom_name, season)).fetchone()
        
        if result:
            return {
                'kp_adj_em': result[0], 'kp_rank': result[1],
                'kp_adj_oe': result[2], 'kp_adj_oe_rank': result[3],
                'kp_adj_de': result[4], 'kp_adj_de_rank': result[5],
                'kp_adj_tempo': result[6], 'kp_adj_tempo_rank': result[7],
                'kp_luck': result[8],
                'kp_sos': result[9], 'kp_sos_rank': result[10],
                'kp_sos_o': result[11], 'kp_sos_o_rank': result[12],
                'kp_sos_d': result[13], 'kp_sos_d_rank': result[14],
                'kp_ncsos': result[15], 'kp_ncsos_rank': result[16]
            }
        return {}
    
    def _get_recent_form(self, team_name: str, season: int, as_of_date: date):
        """Get recent form metrics"""
        # Get team ID
        query = "SELECT team_id FROM teams WHERE team_name = ?"
        result = self.cursor.execute(query, (team_name,)).fetchone()
        
        if not result:
            return {}
        
        team_id = result[0]
        
        query = """
            SELECT 
                last5_wins, last5_losses, last5_avg_margin, 
                last10_wins, last10_losses, last10_avg_margin,
                current_win_streak, current_loss_streak, days_since_last_game
            FROM recent_form
            WHERE team_id = ? AND season = ?
            ORDER BY as_of_date DESC
            LIMIT 1
        """
        
        result = self.cursor.execute(query, (team_id, season)).fetchone()
        
        if result:
            # Calculate win percentages
            last5_games = result[0] + result[1]
            last10_games = result[3] + result[4]
            last5_wp = result[0] / last5_games if last5_games > 0 else 0.5
            last10_wp = result[3] / last10_games if last10_games > 0 else 0.5
            
            # Net streak (positive for wins, negative for losses)
            streak = result[6] if result[6] > 0 else -result[7]
            
            return {
                'form_last5_wp': last5_wp, 
                'form_last5_margin': result[2] if result[2] else 0,
                'form_last10_wp': last10_wp, 
                'form_last10_margin': result[5] if result[5] else 0,
                'form_streak': streak, 
                'form_rest_days': result[8] if result[8] else 2
            }
        return {}
    
    def _get_lineup_status(self, game_id: str, team_name: str):
        """
        Check lineup status for a team in an upcoming game
        
        Returns:
            dict with lineup_confirmed, missing_starters, lineup_strength
        """
        # Check if we have lineup data for this game
        query = """
            SELECT 
                player_name,
                status,
                position
            FROM starting_lineups
            WHERE game_id = ? AND team_name = ?
        """
        
        result = self.cursor.execute(query, (game_id, team_name)).fetchall()
        
        if not result:
            # No lineup data available
            return {
                'lineup_confirmed': False,
                'missing_starters': 0,
                'lineup_strength': 1.0  # Neutral assumption
            }
        
        # Count players with different statuses
        starters = [r for r in result if r[1] in ('ACTIVE', 'PROBABLE')]
        questionable = [r for r in result if r[1] == 'QUESTIONABLE']
        out = [r for r in result if r[1] in ('OUT', 'DOUBTFUL')]
        
        # Calculate lineup strength penalty
        # Each missing starter = -15% strength
        # Each questionable = -7.5% strength
        missing_penalty = len(out) * 0.15
        questionable_penalty = len(questionable) * 0.075
        lineup_strength = max(0.4, 1.0 - missing_penalty - questionable_penalty)
        
        return {
            'lineup_confirmed': True,
            'missing_starters': len(out),
            'questionable_starters': len(questionable),
            'lineup_strength': lineup_strength
        }
    
    def build_features(self, game_id: str, home_team: str, away_team: str, game_date: date, season: int):
        """
        Build complete feature set for a single game
        
        Args:
            game_id: Game ID for lineup lookup
            home_team: Home team name (ESPN format)
            away_team: Away team name (ESPN format)
            game_date: Date of game
            season: Season year
        
        Returns:
            pandas DataFrame with single row of features, or None if lineups unavailable
        """
        features = {}
        
        # Check lineups first (CRITICAL for betting decision)
        home_lineup = self._get_lineup_status(game_id, home_team)
        away_lineup = self._get_lineup_status(game_id, away_team)
        
        # Add lineup features
        features['home_lineup_strength'] = home_lineup['lineup_strength']
        features['away_lineup_strength'] = away_lineup['lineup_strength']
        features['home_missing_starters'] = home_lineup['missing_starters']
        features['away_missing_starters'] = away_lineup['missing_starters']
        
        # Flag if lineups not confirmed (will be used to skip bet)
        features['lineups_confirmed'] = home_lineup['lineup_confirmed'] and away_lineup['lineup_confirmed']
        
        # Home team features
        home_kp = self._get_kenpom_features(home_team, season, game_date)
        for key, val in home_kp.items():
            features[f'home_{key}'] = val
        
        home_form = self._get_recent_form(home_team, season, game_date)
        for key, val in home_form.items():
            features[f'home_{key}'] = val
        
        # Away team features
        away_kp = self._get_kenpom_features(away_team, season, game_date)
        for key, val in away_kp.items():
            features[f'away_{key}'] = val
        
        away_form = self._get_recent_form(away_team, season, game_date)
        for key, val in away_form.items():
            features[f'away_{key}'] = val
        
        # Matchup features (differences)
        if home_kp and away_kp:
            features['matchup_rank_diff'] = away_kp.get('kp_rank', 180) - home_kp.get('kp_rank', 180)
            features['matchup_em_diff'] = home_kp.get('kp_adj_em', 0) - away_kp.get('kp_adj_em', 0)
            features['matchup_oe_diff'] = home_kp.get('kp_adj_oe', 100) - away_kp.get('kp_adj_oe', 100)
            features['matchup_de_diff'] = away_kp.get('kp_adj_de', 100) - home_kp.get('kp_adj_de', 100)
            features['matchup_tempo_diff'] = home_kp.get('kp_adj_tempo', 68) - away_kp.get('kp_adj_tempo', 68)
        
        if home_form and away_form:
            features['matchup_form_diff'] = home_form.get('form_last10_wp', 0.5) - away_form.get('form_last10_wp', 0.5)
            features['rest_differential'] = home_form.get('form_rest_days', 2) - away_form.get('form_rest_days', 2)
        
        # Lineup differential
        features['lineup_advantage'] = home_lineup['lineup_strength'] - away_lineup['lineup_strength']
        
        # Game context
        features['neutral_site'] = 0  # Assume not neutral unless specified
        features['is_tournament'] = 0  # Assume regular season
        
        # Convert to DataFrame
        df = pd.DataFrame([features])
        
        # Fill missing values with defaults
        df = df.fillna({
            'home_kp_adj_em': 0, 'away_kp_adj_em': 0,
            'home_kp_adj_oe': 100, 'away_kp_adj_oe': 100,
            'home_kp_adj_de': 100, 'away_kp_adj_de': 100,
            'home_kp_rank': 180, 'away_kp_rank': 180,
            'home_form_last10_wp': 0.5, 'away_form_last10_wp': 0.5,
            'home_form_streak': 0, 'away_form_streak': 0,
            'matchup_rank_diff': 0, 'matchup_em_diff': 0,
            'lineup_advantage': 0
        })
        
        return df
    
    def close(self):
        """Close database connection"""
        self.conn.close()

