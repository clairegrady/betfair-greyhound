"""
Recent Form Calculator - Enterprise Grade

Calculates rolling statistics for team performance:
- Last 5/10 game performance
- Win/loss streaks  
- Rest days
- Momentum indicators

Design Principles:
- Proper error handling
- Logging for debugging
- Efficient database queries
- Type hints for maintainability
- Comprehensive validation
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class RecentFormCalculator:
    """Calculates recent form metrics for teams"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_team_games(
        self, 
        team_id: int, 
        season: int, 
        up_to_date: str,
        limit: int = 10
    ) -> list:
        """Get recent games for a team up to a specific date"""
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                game_date,
                CASE WHEN home_team_id = ? THEN home_score ELSE away_score END as team_score,
                CASE WHEN home_team_id = ? THEN away_score ELSE home_score END as opp_score,
                CASE WHEN home_team_id = ? THEN 1 ELSE 0 END as was_home
            FROM games
            WHERE season = ?
                AND game_date < ?
                AND (home_team_id = ? OR away_team_id = ?)
                AND home_score IS NOT NULL
                AND away_score IS NOT NULL
            ORDER BY game_date DESC
            LIMIT ?
        """
        
        results = cursor.execute(
            query, 
            (team_id, team_id, team_id, season, up_to_date, team_id, team_id, limit)
        ).fetchall()
        
        return [dict(row) for row in results]
    
    def calculate_form_metrics(self, games: list) -> Optional[Dict[str, Any]]:
        """Calculate form metrics from game list"""
        if not games:
            return None
        
        # Last 5 games
        last5 = games[:5]
        last5_wins = sum(1 for g in last5 if g['team_score'] > g['opp_score'])
        last5_losses = len(last5) - last5_wins
        last5_avg_score = sum(g['team_score'] for g in last5) / len(last5)
        last5_avg_allowed = sum(g['opp_score'] for g in last5) / len(last5)
        last5_avg_margin = sum(g['team_score'] - g['opp_score'] for g in last5) / len(last5)
        
        # Last 10 games
        last10 = games[:10]
        last10_wins = sum(1 for g in last10 if g['team_score'] > g['opp_score'])
        last10_losses = len(last10) - last10_wins
        last10_avg_margin = sum(g['team_score'] - g['opp_score'] for g in last10) / len(last10)
        
        # Current streak
        win_streak = 0
        loss_streak = 0
        for game in games:
            won = game['team_score'] > game['opp_score']
            if won:
                if loss_streak > 0:
                    break
                win_streak += 1
            else:
                if win_streak > 0:
                    break
                loss_streak += 1
        
        # Days since last game (games are ordered DESC, so first is most recent)
        days_since = 0
        if games:
            last_game_date = datetime.strptime(games[0]['game_date'], '%Y-%m-%d')
            # Note: We calculate this relative to the game date being processed
            # This will be updated by the caller
            days_since = 0  # Placeholder
        
        return {
            'last5_wins': last5_wins,
            'last5_losses': last5_losses,
            'last5_avg_score': round(last5_avg_score, 2),
            'last5_avg_allowed': round(last5_avg_allowed, 2),
            'last5_avg_margin': round(last5_avg_margin, 2),
            'last10_wins': last10_wins,
            'last10_losses': last10_losses,
            'last10_avg_margin': round(last10_avg_margin, 2),
            'current_win_streak': win_streak,
            'current_loss_streak': loss_streak,
            'days_since_last_game': days_since
        }
    
    def calculate_days_rest(self, last_game_date: str, current_date: str) -> int:
        """Calculate days between games"""
        try:
            last_dt = datetime.strptime(last_game_date, '%Y-%m-%d')
            current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            return (current_dt - last_dt).days
        except Exception as e:
            logger.warning(f"Error calculating rest days: {e}")
            return 0
    
    def insert_form_record(
        self, 
        team_id: int, 
        season: int, 
        as_of_date: str,
        metrics: Dict[str, Any]
    ) -> bool:
        """Insert form metrics into database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO recent_form (
                    team_id, season, as_of_date,
                    last5_wins, last5_losses, last5_avg_score, 
                    last5_avg_allowed, last5_avg_margin,
                    last10_wins, last10_losses, last10_avg_margin,
                    current_win_streak, current_loss_streak,
                    days_since_last_game
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team_id, season, as_of_date,
                metrics['last5_wins'], metrics['last5_losses'],
                metrics['last5_avg_score'], metrics['last5_avg_allowed'],
                metrics['last5_avg_margin'],
                metrics['last10_wins'], metrics['last10_losses'],
                metrics['last10_avg_margin'],
                metrics['current_win_streak'], metrics['current_loss_streak'],
                metrics['days_since_last_game']
            ))
            return True
        except Exception as e:
            logger.error(f"Error inserting form record: {e}")
            return False
    
    def run(self) -> Dict[str, int]:
        """Main execution - calculate form for all teams and dates"""
        logger.info("Starting Recent Form Calculation")
        
        # Get all games to process
        cursor = self.conn.cursor()
        games_query = """
            SELECT DISTINCT game_date, season
            FROM games
            WHERE home_score IS NOT NULL
            ORDER BY season, game_date
        """
        game_dates = cursor.execute(games_query).fetchall()
        
        # Get all teams
        teams_query = "SELECT team_id FROM teams ORDER BY team_id"
        teams = cursor.execute(teams_query).fetchall()
        
        logger.info(f"Processing {len(game_dates)} dates × {len(teams)} teams")
        
        inserted = 0
        skipped = 0
        errors = 0
        
        # Process each date
        for date_row in tqdm(game_dates, desc="Calculating recent form"):
            game_date = date_row['game_date']
            season = date_row['season']
            
            # For each team, calculate form as of this date
            for team_row in teams:
                team_id = team_row['team_id']
                
                try:
                    # Get recent games before this date
                    games = self.get_team_games(team_id, season, game_date, limit=10)
                    
                    if not games:
                        skipped += 1
                        continue
                    
                    # Calculate metrics
                    metrics = self.calculate_form_metrics(games)
                    if not metrics:
                        skipped += 1
                        continue
                    
                    # Calculate rest days
                    metrics['days_since_last_game'] = self.calculate_days_rest(
                        games[0]['game_date'], 
                        game_date
                    )
                    
                    # Insert
                    if self.insert_form_record(team_id, season, game_date, metrics):
                        inserted += 1
                    else:
                        errors += 1
                        
                except Exception as e:
                    logger.error(f"Error processing team {team_id} on {game_date}: {e}")
                    errors += 1
            
            # Commit after each date
            self.conn.commit()
        
        # Final commit
        self.conn.commit()
        
        # Verify
        count = cursor.execute("SELECT COUNT(*) FROM recent_form").fetchone()[0]
        
        results = {
            'inserted': inserted,
            'skipped': skipped,
            'errors': errors,
            'total_rows': count
        }
        
        logger.info(f"✅ Recent Form Complete: {results}")
        return results


def main():
    """Entry point"""
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL - RECENT FORM CALCULATOR")
    print("="*70)
    
    with RecentFormCalculator() as calculator:
        results = calculator.run()
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"✅ Inserted: {results['inserted']:,}")
    print(f"⏭️  Skipped: {results['skipped']:,}")
    print(f"❌ Errors: {results['errors']:,}")
    print(f"💾 Total Rows: {results['total_rows']:,}")
    print("="*70)


if __name__ == "__main__":
    main()

