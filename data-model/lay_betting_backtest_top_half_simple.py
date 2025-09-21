"""
Lay Betting Backtest Script - SIMPLE TOP HALF VERSION
Always lays $1 on the top half horses (lowest odds) - no filters
Analyzes average odds for wins vs losses by horse count
"""
import pandas as pd
import numpy as np
from shared_lay_betting import LayBettingResults
from collections import defaultdict
import logging
import sqlite3
import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayBettingSimpleTopHalfStrategy:
    """
    Simple lay betting strategy that always bets on the TOP HALF (lowest odds) horses
    No std dev or max odds filters
    """
    
    def __init__(self):
        pass
    
    def analyze_race_eligibility(self, race_data: pd.DataFrame, odds_column: str = 'FixedWinClose_Reference') -> tuple:
        """
        Check if a race meets our simple criteria - just need enough horses
        
        Args:
            race_data: DataFrame with race odds data
            odds_column: Column name containing the odds
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses)
        """
        # Filter out horses without odds for analysis
        horses_with_odds = race_data.dropna(subset=[odds_column])
        
        # Check 1: Must have at least 4 horses total
        if len(race_data) < 4:
            return False, f"Less than 4 horses (total: {len(race_data)})", None
        
        # Check 2: Must have at least 4 horses with odds
        if len(horses_with_odds) < 4:
            return False, f"Less than 4 horses with odds (total: {len(race_data)}, with odds: {len(horses_with_odds)})", None
        
        # Sort by odds (lowest first)
        horses_with_odds = horses_with_odds.sort_values(odds_column)
        
        # Get top half horses (lowest odds) - these are the ones we'll bet on
        total_horses = len(horses_with_odds)
        top_half_count = total_horses // 2
        
        # For odd numbers, bet on the greater half (e.g., 7 horses = bet on top 4)
        if total_horses % 2 == 1:
            top_half_count += 1
            
        top_half = horses_with_odds.head(top_half_count)
        
        return True, f"Eligible - {len(top_half)} horses to lay", top_half
    
    def calculate_lay_bet_profit(self, horse_odds: float, finishing_pos: int, stake: float) -> float:
        """
        Calculate profit from a lay bet
        
        Args:
            horse_odds: The odds we laid at
            finishing_pos: Where the horse finished (1 = won, 2+ = lost)
            stake: Amount we staked
            
        Returns:
            float: Profit (positive if we won the bet, negative if we lost)
        """
        if finishing_pos == 1:  # Horse won - we lose the bet
            # We lose: stake * (odds - 1)
            return -stake * (horse_odds - 1)
        else:  # Horse lost - we win the bet
            # We win: stake
            return stake
    
    def get_strategy_description(self) -> str:
        """Get a description of the strategy"""
        return "Simple Top Half Lay Strategy: Always bet on top half (no filters)"


class LayBettingSimpleTopHalfBacktest:
    """
    Simple lay betting backtest using TOP HALF strategy with no filters
    """
    
    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.strategy = LayBettingSimpleTopHalfStrategy()
        self.results = LayBettingResults()
        self.df = None
        self.race_stats = defaultdict(list)
        self._create_bets_table()
    
    def _create_bets_table(self):
        """Create table to store would-have-placed bets"""
        conn = sqlite3.connect('betting_history.sqlite')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS top_half_strategy_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_name TEXT NOT NULL,
                meeting_date TEXT NOT NULL,
                race_number INTEGER NOT NULL,
                horse_name TEXT,
                cloth_number INTEGER,
                odds REAL NOT NULL,
                stake REAL NOT NULL,
                finishing_position INTEGER,
                profit REAL,
                won BOOLEAN,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _store_bet(self, bet_data):
        """Store a would-have-placed bet in the database"""
        conn = sqlite3.connect('betting_history.sqlite')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO top_half_strategy_bets 
            (meeting_name, meeting_date, race_number, horse_name, cloth_number, 
             odds, stake, finishing_position, profit, won)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bet_data['meeting'],
            bet_data['date'],
            bet_data['race_num'],
            bet_data['horse_name'],
            bet_data['cloth_number'],
            bet_data['odds'],
            bet_data['stake'],
            bet_data['finishing_position'],
            bet_data['profit'],
            bet_data['won']
        ))
        
        conn.commit()
        conn.close()
    
    def load_data(self):
        """Load racing data from CSV"""
        logger.info("📊 Loading racing data...")
        self.df = pd.read_csv(self.csv_file)
        logger.info(f"✅ Loaded {len(self.df)} race entries")
    
    def get_race_groups(self):
        """Group data by race (meeting + date + race number)"""
        return self.df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    
    def run_backtest(self, stake_per_bet: float = 1, verbose: bool = True):
        """
        Run the backtest using SIMPLE TOP HALF strategy
        
        Args:
            stake_per_bet: Amount to stake per bet
            verbose: Whether to print detailed output
        """
        if self.df is None:
            self.load_data()
        
        race_groups = self.get_race_groups()
        total_races = len(race_groups)
        
        if verbose:
            logger.info(f"🏁 Starting SIMPLE TOP HALF backtest on {total_races} races")
            logger.info(f"📋 Strategy: {self.strategy.get_strategy_description()}")
        
        for (meeting, date, race_num), race_data in race_groups:
            # Use strategy to analyze race eligibility
            is_eligible, reason, eligible_horses = self.strategy.analyze_race_eligibility(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                if verbose:
                    logger.debug(f"❌ {meeting} {date} R{race_num}: {reason}")
                continue
            
            # Place lay bets on eligible horses (TOP HALF)
            for _, horse in eligible_horses.iterrows():
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                
                # Calculate profit using strategy
                profit = self.strategy.calculate_lay_bet_profit(
                    horse_odds, finishing_pos, stake_per_bet
                )
                
                won_bet = profit > 0
                
                bet_data = {
                    'meeting': meeting,
                    'date': date,
                    'race_num': race_num,
                    'horse_name': horse.get('runnerName', 'Unknown'),
                    'cloth_number': horse.get('clothNumber', 0),
                    'odds': horse_odds,
                    'finishing_position': finishing_pos,
                    'stake': stake_per_bet,
                    'profit': profit,
                    'won': won_bet
                }
                
                self.results.add_bet(bet_data)
                
                # Store the would-have-placed bet in database
                self._store_bet(bet_data)
                
                if verbose:
                    logger.debug(f"  🐎 {horse.get('clothNumber', 0)}. {horse.get('runnerName', 'Unknown')} - Lay @ {horse_odds:.2f} → {finishing_pos} → ${profit:.2f}")
        
        if verbose:
            stats = self.results.get_statistics()
            logger.info(f"✅ Backtest complete: {stats['total_bets']} bets, ROI: {stats['roi']:.1f}%, Profit: ${stats['total_profit']:.2f}")
    
    def get_stored_bets(self, limit=100):
        """Get stored would-have-placed bets from database"""
        conn = sqlite3.connect('betting_history.sqlite')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM top_half_strategy_bets 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        bets = cursor.fetchall()
        conn.close()
        
        return bets
    
    def get_bet_summary(self):
        """Get summary of stored bets"""
        conn = sqlite3.connect('betting_history.sqlite')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as won_bets,
                SUM(CASE WHEN won = 0 THEN 1 ELSE 0 END) as lost_bets,
                ROUND(AVG(CASE WHEN won = 1 THEN odds END), 2) as avg_odds_wins,
                ROUND(AVG(CASE WHEN won = 0 THEN odds END), 2) as avg_odds_losses,
                ROUND(SUM(profit), 2) as total_profit,
                ROUND(AVG(profit), 2) as avg_profit
            FROM top_half_strategy_bets
        ''')
        
        summary = cursor.fetchone()
        conn.close()
        
        return {
            'total_bets': summary[0],
            'won_bets': summary[1],
            'lost_bets': summary[2],
            'avg_odds_wins': summary[3],
            'avg_odds_losses': summary[4],
            'total_profit': summary[5],
            'avg_profit': summary[6]
        }


def analyze_by_horse_count():
    """Analyze results by number of horses in each race"""
    csv_file = "/Users/clairegrady/RiderProjects/betfair/data-model/Runner_Result_2025-09-07.csv"
    
    logger.info("🔬 ANALYZING TOP HALF LAY BETTING BY HORSE COUNT")
    logger.info("=" * 80)
    
    # Load data
    df = pd.read_csv(csv_file)
    race_groups = df.groupby(['meetingName', 'meetingDate', 'raceNumber'])
    
    results = []
    
    # Group races by horse count
    horse_count_groups = {}
    
    for (meeting, date, race_num), race_data in race_groups:
        horses_with_odds = race_data.dropna(subset=['FixedWinClose_Reference'])
        
        if len(horses_with_odds) < 4:
            continue
            
        horse_count = len(horses_with_odds)
        if horse_count not in horse_count_groups:
            horse_count_groups[horse_count] = []
        horse_count_groups[horse_count].append((meeting, date, race_num, race_data))
    
    # Analyze each horse count group
    for horse_count in sorted(horse_count_groups.keys()):
        logger.info(f"\n📊 ANALYZING RACES WITH {horse_count} HORSES")
        logger.info("=" * 50)
        
        races = horse_count_groups[horse_count]
        logger.info(f"Found {len(races)} races with {horse_count} horses")
        
        # Run backtest for this horse count
        backtest = LayBettingSimpleTopHalfBacktest(csv_file)
        backtest.load_data()
        
        # Filter to only races with this horse count
        filtered_df = backtest.df.copy()
        race_identifiers = [(meeting, date, race_num) for meeting, date, race_num, _ in races]
        
        # Create mask for races with this horse count
        mask = filtered_df.apply(lambda row: 
            (row['meetingName'], row['meetingDate'], row['raceNumber']) in race_identifiers, axis=1)
        filtered_df = filtered_df[mask]
        
        backtest.df = filtered_df
        backtest.run_backtest(stake_per_bet=1, verbose=False)
        
        # Get detailed bet data for odds analysis
        all_bets = []
        for (meeting, date, race_num), race_data in backtest.get_race_groups():
            is_eligible, _, eligible_horses = backtest.strategy.analyze_race_eligibility(
                race_data, 'FixedWinClose_Reference'
            )
            
            if not is_eligible:
                continue
                
            for _, horse in eligible_horses.iterrows():
                horse_odds = horse['FixedWinClose_Reference']
                finishing_pos = horse['finishingPosition']
                profit = backtest.strategy.calculate_lay_bet_profit(horse_odds, finishing_pos, 1)
                won_bet = profit > 0
                
                all_bets.append({
                    'odds': horse_odds,
                    'won': won_bet,
                    'profit': profit
                })
        
        # Calculate average odds for wins and losses
        won_bets = [bet for bet in all_bets if bet['won']]
        lost_bets = [bet for bet in all_bets if not bet['won']]
        
        avg_odds_wins = round(np.mean([bet['odds'] for bet in won_bets]), 2) if won_bets else 0
        avg_odds_losses = round(np.mean([bet['odds'] for bet in lost_bets]), 2) if lost_bets else 0
        
        stats = backtest.results.get_statistics()
        
        result = {
            'horse_count': horse_count,
            'total_races': len(races),
            'eligible_races': len([r for r in races]),  # All races are eligible
            'total_bets': len(all_bets),
            'won_bets': len(won_bets),
            'lost_bets': len(lost_bets),
            'win_rate': round(stats['win_rate'], 2),
            'roi': round(stats['roi'], 2),
            'total_profit': round(stats['total_profit'], 2),
            'avg_odds_wins': avg_odds_wins,
            'avg_odds_losses': avg_odds_losses
        }
        results.append(result)
        
        logger.info(f"  ✅ Races: {len(races)}, Bets: {len(all_bets)}, ROI: {stats['roi']:.1f}%")
        logger.info(f"  📈 Avg odds wins: {avg_odds_wins:.2f}, Avg odds losses: {avg_odds_losses:.2f}")
    
    # Save results to CSV
    df_results = pd.DataFrame(results)
    csv_filename = "lay_analysis_top_half_by_horse_count.csv"
    df_results.to_csv(csv_filename, index=False)
    
    logger.info(f"\n💾 Results saved to {csv_filename}")
    
    # Summary table
    logger.info(f"\n📈 SUMMARY TABLE BY HORSE COUNT")
    logger.info("=" * 120)
    logger.info(f"{'Horses':<7} {'Races':<6} {'Bets':<6} {'Win%':<6} {'ROI':<6} {'Profit':<10} {'Avg Odds Wins':<12} {'Avg Odds Losses':<15}")
    logger.info("-" * 120)
    
    for result in results:
        logger.info(f"{result['horse_count']:<7} {result['total_races']:<6} {result['total_bets']:<6} {result['win_rate']:<6.1f}% {result['roi']:<6.1f}% ${result['total_profit']:<9.2f} {result['avg_odds_wins']:<12.2f} {result['avg_odds_losses']:<15.2f}")
    
    # Best performers by horse count
    logger.info(f"\n🏆 BEST PERFORMANCE BY HORSE COUNT:")
    best_by_count = {}
    for result in results:
        if result['horse_count'] not in best_by_count or result['roi'] > best_by_count[result['horse_count']]['roi']:
            best_by_count[result['horse_count']] = result
    
    for horse_count in sorted(best_by_count.keys()):
        result = best_by_count[horse_count]
        logger.info(f"  {horse_count} horses: ROI {result['roi']:.1f}%, Profit ${result['total_profit']:.2f}")
    
    return results


def main():
    """Main function"""
    results = analyze_by_horse_count()
    return results


if __name__ == "__main__":
    main()
