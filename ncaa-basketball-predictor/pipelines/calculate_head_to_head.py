"""
Head-to-Head Calculator - Enterprise Grade

Calculates historical matchup data between teams:
- Games played history
- Win/loss records
- Average margins
- Rivalry indicators
- Conference matchups

Design Principles:
- Proper error handling
- Logging for debugging
- Efficient database queries with proper joins
- Type hints
- Comprehensive validation
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "ncaa_basketball.db"


class HeadToHeadCalculator:
    """Calculates head-to-head matchup history"""
    
    def __init__(self, db_path: Path = DB_PATH, lookback_seasons: int = 5):
        self.db_path = db_path
        self.lookback_seasons = lookback_seasons
        self.conn = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_matchup_games(
        self, 
        team1_id: int, 
        team2_id: int
    ) -> list:
        """Get all games between two teams (last N seasons)"""
        cursor = self.conn.cursor()
        
        # Get current max season
        max_season_query = "SELECT MAX(season) as max_season FROM games"
        max_season = cursor.execute(max_season_query).fetchone()['max_season']
        min_season = max_season - self.lookback_seasons
        
        query = """
            SELECT 
                game_date,
                season,
                home_team_id,
                away_team_id,
                home_score,
                away_score,
                neutral_site
            FROM games
            WHERE ((home_team_id = ? AND away_team_id = ?) OR 
                   (home_team_id = ? AND away_team_id = ?))
                AND home_score IS NOT NULL
                AND away_score IS NOT NULL
                AND season >= ?
            ORDER BY game_date
        """
        
        results = cursor.execute(
            query, 
            (team1_id, team2_id, team2_id, team1_id, min_season)
        ).fetchall()
        
        return [dict(row) for row in results]
    
    def calculate_h2h_metrics(
        self, 
        team1_id: int, 
        team2_id: int, 
        games: list
    ) -> Optional[Dict[str, Any]]:
        """Calculate head-to-head metrics"""
        if not games:
            return None
        
        games_played = len(games)
        team1_wins = 0
        team2_wins = 0
        margins = []
        
        for game in games:
            # Determine winner from team1's perspective
            if game['home_team_id'] == team1_id:
                margin = game['home_score'] - game['away_score']
                if game['home_score'] > game['away_score']:
                    team1_wins += 1
                else:
                    team2_wins += 1
            else:  # team1 is away
                margin = game['away_score'] - game['home_score']
                if game['away_score'] > game['home_score']:
                    team1_wins += 1
                else:
                    team2_wins += 1
            
            margins.append(margin)
        
        avg_margin = sum(margins) / len(margins) if margins else 0
        last_meeting_date = games[-1]['game_date']
        last_winner = team1_id if margins[-1] > 0 else team2_id
        
        # Rivalry indicator: 5+ games in lookback period
        is_rivalry = 1 if games_played >= 5 else 0
        
        return {
            'games_played': games_played,
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'avg_margin': round(avg_margin, 2),
            'last_meeting_date': last_meeting_date,
            'last_meeting_winner': last_winner,
            'is_rivalry': is_rivalry
        }
    
    def check_same_conference(
        self, 
        team1_id: int, 
        team2_id: int
    ) -> int:
        """Check if teams are in same conference"""
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                (SELECT conference FROM teams WHERE team_id = ?) = 
                (SELECT conference FROM teams WHERE team_id = ?) as same_conf
        """
        
        result = cursor.execute(query, (team1_id, team2_id)).fetchone()
        return result['same_conf'] if result and result['same_conf'] else 0
    
    def insert_h2h_record(
        self,
        team1_id: int,
        team2_id: int,
        metrics: Dict[str, Any],
        same_conference: int
    ) -> bool:
        """Insert head-to-head record into database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO head_to_head (
                    team1_id, team2_id,
                    games_played, team1_wins, team2_wins,
                    avg_margin, last_meeting_date, last_meeting_winner,
                    is_rivalry, same_conference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team1_id, team2_id,
                metrics['games_played'], metrics['team1_wins'], metrics['team2_wins'],
                metrics['avg_margin'], metrics['last_meeting_date'], 
                metrics['last_meeting_winner'],
                metrics['is_rivalry'], same_conference
            ))
            return True
        except Exception as e:
            logger.error(f"Error inserting H2H record: {e}")
            return False
    
    def get_unique_matchups(self) -> list:
        """Get all unique team matchups from recent games"""
        cursor = self.conn.cursor()
        
        # Get current max season
        max_season_query = "SELECT MAX(season) as max_season FROM games"
        max_season = cursor.execute(max_season_query).fetchone()['max_season']
        min_season = max_season - self.lookback_seasons
        
        query = """
            SELECT DISTINCT
                CASE WHEN home_team_id < away_team_id THEN home_team_id ELSE away_team_id END as team1_id,
                CASE WHEN home_team_id < away_team_id THEN away_team_id ELSE home_team_id END as team2_id
            FROM games
            WHERE home_score IS NOT NULL
                AND season >= ?
            ORDER BY team1_id, team2_id
        """
        
        results = cursor.execute(query, (min_season,)).fetchall()
        return [(row['team1_id'], row['team2_id']) for row in results]
    
    def run(self) -> Dict[str, int]:
        """Main execution - calculate H2H for all matchups"""
        logger.info(f"Starting Head-to-Head Calculation (last {self.lookback_seasons} seasons)")
        
        # Get all unique matchups
        matchups = self.get_unique_matchups()
        logger.info(f"Processing {len(matchups)} unique matchups")
        
        inserted = 0
        skipped = 0
        errors = 0
        rivalries = 0
        
        # Process each matchup
        for team1_id, team2_id in tqdm(matchups, desc="Calculating H2H"):
            try:
                # Get games between these teams
                games = self.get_matchup_games(team1_id, team2_id)
                
                if not games:
                    skipped += 1
                    continue
                
                # Calculate metrics
                metrics = self.calculate_h2h_metrics(team1_id, team2_id, games)
                if not metrics:
                    skipped += 1
                    continue
                
                # Check conference
                same_conf = self.check_same_conference(team1_id, team2_id)
                
                # Insert
                if self.insert_h2h_record(team1_id, team2_id, metrics, same_conf):
                    inserted += 1
                    if metrics['is_rivalry']:
                        rivalries += 1
                else:
                    errors += 1
                    
            except Exception as e:
                logger.error(f"Error processing matchup {team1_id} vs {team2_id}: {e}")
                errors += 1
            
            # Commit periodically
            if inserted % 100 == 0:
                self.conn.commit()
        
        # Final commit
        self.conn.commit()
        
        # Verify
        cursor = self.conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM head_to_head").fetchone()[0]
        
        results = {
            'inserted': inserted,
            'skipped': skipped,
            'errors': errors,
            'rivalries': rivalries,
            'total_rows': count
        }
        
        logger.info(f"✅ Head-to-Head Complete: {results}")
        return results


def main():
    """Entry point"""
    print("\n" + "="*70)
    print("🏀 NCAA BASKETBALL - HEAD-TO-HEAD CALCULATOR")
    print("="*70)
    
    with HeadToHeadCalculator(lookback_seasons=5) as calculator:
        results = calculator.run()
    
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"✅ Inserted: {results['inserted']:,}")
    print(f"🏆 Rivalries: {results['rivalries']:,} (5+ games)")
    print(f"⏭️  Skipped: {results['skipped']:,}")
    print(f"❌ Errors: {results['errors']:,}")
    print(f"💾 Total Rows: {results['total_rows']:,}")
    print("="*70)


if __name__ == "__main__":
    main()

