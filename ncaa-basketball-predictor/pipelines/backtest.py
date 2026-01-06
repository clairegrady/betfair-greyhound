"""
Backtesting Framework - Enterprise Grade

Simulates paper trading on historical NCAA Basketball games with:
- Kelly Criterion bet sizing
- Realistic odds simulation
- Edge threshold filtering
- ROI, Sharpe Ratio, Max Drawdown calculation

This shows REAL betting performance (not just accuracy)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Tuple
import json
from datetime import datetime
import joblib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "training_data.csv"
MODEL_PATH = Path(__file__).parent.parent / "models"


class OddsSimulator:
    """
    Simulates realistic betting odds for historical games
    
    In real betting, we'd use actual market odds.
    For backtesting, we simulate odds based on true outcome probabilities
    with realistic vig/juice.
    """
    
    def __init__(self, vig: float = 0.045):
        """
        Args:
            vig: Bookmaker's margin (typical: 4-5%)
        """
        self.vig = vig
    
    def probability_to_american_odds(self, prob: float) -> float:
        """
        Convert probability to American odds
        
        Args:
            prob: Probability (0-1)
        
        Returns:
            American odds (e.g., -150, +130)
        """
        # Add vig
        prob_with_vig = prob + (self.vig / 2)
        prob_with_vig = min(prob_with_vig, 0.99)  # Cap at 99%
        
        if prob_with_vig >= 0.5:
            # Favorite (negative odds)
            odds = -100 * prob_with_vig / (1 - prob_with_vig)
        else:
            # Underdog (positive odds)
            odds = 100 * (1 - prob_with_vig) / prob_with_vig
        
        return odds
    
    def american_odds_to_decimal(self, american_odds: float) -> float:
        """Convert American odds to decimal odds"""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def simulate_market_odds(self, true_prob: float) -> Tuple[float, float]:
        """
        Simulate market odds for home team
        
        Args:
            true_prob: True probability of home team winning (unknown in real betting)
        
        Returns:
            (home_decimal_odds, away_decimal_odds)
        """
        # In real betting, market odds are NOISY around true probability
        # We add random noise to simulate market inefficiency
        market_noise = np.random.normal(0, 0.03)  # 3% std dev
        market_prob = np.clip(true_prob + market_noise, 0.1, 0.9)
        
        home_american = self.probability_to_american_odds(market_prob)
        away_american = self.probability_to_american_odds(1 - market_prob)
        
        return (
            self.american_odds_to_decimal(home_american),
            self.american_odds_to_decimal(away_american)
        )


class KellyCriterion:
    """
    Kelly Criterion for optimal bet sizing
    
    Formula: f = (bp - q) / b
    where:
        f = fraction of bankroll to bet
        b = decimal odds - 1
        p = probability of winning
        q = probability of losing (1 - p)
    """
    
    def __init__(self, fractional_kelly: float = 0.25):
        """
        Args:
            fractional_kelly: Fraction of full Kelly to use (0.25 = quarter Kelly)
                              Reduces variance while maintaining positive expectancy
        """
        self.fractional_kelly = fractional_kelly
    
    def calculate_bet_size(
        self, 
        win_probability: float, 
        decimal_odds: float, 
        bankroll: float
    ) -> float:
        """
        Calculate optimal bet size using Kelly Criterion
        
        Args:
            win_probability: Model's estimated probability of winning
            decimal_odds: Decimal odds offered by bookmaker
            bankroll: Current bankroll
        
        Returns:
            Bet size in dollars
        """
        b = decimal_odds - 1  # Net odds
        p = win_probability
        q = 1 - p
        
        # Kelly formula
        kelly_fraction = (b * p - q) / b
        
        # Apply fractional Kelly
        kelly_fraction *= self.fractional_kelly
        
        # Clamp to reasonable limits
        kelly_fraction = max(0, min(kelly_fraction, 0.10))  # Max 10% of bankroll
        
        return kelly_fraction * bankroll


class BacktestEngine:
    """
    Backtesting engine for NCAA Basketball betting strategy
    """
    
    def __init__(
        self, 
        starting_bankroll: float = 10000,
        min_edge: float = 0.05,
        max_bet_pct: float = 0.05,
        fractional_kelly: float = 0.25,
        vig: float = 0.045
    ):
        """
        Args:
            starting_bankroll: Starting bankroll in dollars
            min_edge: Minimum edge required to place bet (5% = 0.05)
            max_bet_pct: Maximum bet as % of bankroll (5% = 0.05)
            fractional_kelly: Fraction of Kelly to use (0.25 = quarter Kelly)
            vig: Bookmaker's vig/juice (4.5% = 0.045)
        """
        self.starting_bankroll = starting_bankroll
        self.min_edge = min_edge
        self.max_bet_pct = max_bet_pct
        self.odds_simulator = OddsSimulator(vig=vig)
        self.kelly = KellyCriterion(fractional_kelly=fractional_kelly)
        
        # Betting log
        self.bets = []
        self.bankroll_history = [starting_bankroll]
        
    def calculate_edge(self, model_prob: float, market_prob: float) -> float:
        """
        Calculate betting edge
        
        Edge = Model's probability - Market's implied probability
        Positive edge = value bet
        """
        return model_prob - market_prob
    
    def should_bet(
        self, 
        model_prob: float, 
        market_prob: float,
        home_favorite: bool
    ) -> bool:
        """
        Determine if we should place a bet
        
        Rules:
        1. Edge must exceed minimum threshold
        2. Don't bet on massive favorites (no value)
        3. Don't bet on massive underdogs (too risky)
        """
        edge = self.calculate_edge(model_prob, market_prob)
        
        # Minimum edge requirement
        if abs(edge) < self.min_edge:
            return False
        
        # Don't bet on games that are too lopsided
        if model_prob > 0.95 or model_prob < 0.05:
            return False
        
        # Don't bet on massive market favorites (typically no value)
        if market_prob > 0.90 or market_prob < 0.10:
            return False
        
        return True
    
    def run_backtest(self, df: pd.DataFrame, model_predictions: np.ndarray) -> Dict:
        """
        Run backtest on historical games
        
        Args:
            df: DataFrame with game results
            model_predictions: Model's predicted probabilities (home win prob)
        
        Returns:
            Dictionary with backtest results
        """
        logger.info("🎲 Starting Backtest Simulation")
        logger.info("=" * 70)
        logger.info(f"Starting Bankroll: ${self.starting_bankroll:,.2f}")
        logger.info(f"Minimum Edge: {self.min_edge:.1%}")
        logger.info(f"Max Bet %: {self.max_bet_pct:.1%}")
        logger.info(f"Kelly Fraction: {self.kelly.fractional_kelly:.2f}")
        logger.info("=" * 70 + "\n")
        
        current_bankroll = self.starting_bankroll
        
        for idx, (_, game) in enumerate(df.iterrows()):
            model_prob = model_predictions[idx]
            true_outcome = game['home_win']
            
            # Simulate market odds (should be based on MODEL, not true outcome!)
            # In reality, market odds approximate the true probability (efficient market)
            # We simulate market as slightly noisy version of model prediction
            home_decimal_odds, away_decimal_odds = self.odds_simulator.simulate_market_odds(
                true_prob=model_prob  # Market approximates model's view
            )
            
            # Calculate market's implied probability
            market_prob = 1 / home_decimal_odds
            
            # Determine if we should bet
            if not self.should_bet(model_prob, market_prob, model_prob >= 0.5):
                continue
            
            # Calculate edge
            edge = self.calculate_edge(model_prob, market_prob)
            
            # Determine bet side
            if edge > 0:
                # Bet on home team
                bet_on_home = True
                win_prob = model_prob
                odds = home_decimal_odds
            else:
                # Bet on away team
                bet_on_home = False
                win_prob = 1 - model_prob
                odds = away_decimal_odds
                edge = abs(edge)
            
            # Calculate bet size using Kelly Criterion
            bet_size = self.kelly.calculate_bet_size(win_prob, odds, current_bankroll)
            
            # Apply maximum bet constraint
            max_bet = current_bankroll * self.max_bet_pct
            bet_size = min(bet_size, max_bet)
            
            # Skip if bet size is too small
            if bet_size < 10:
                continue
            
            # Determine outcome
            bet_won = (bet_on_home and true_outcome == 1) or (not bet_on_home and true_outcome == 0)
            
            # Calculate profit/loss
            if bet_won:
                profit = bet_size * (odds - 1)
            else:
                profit = -bet_size
            
            # Update bankroll
            current_bankroll += profit
            
            # Record bet
            self.bets.append({
                'game_id': game['game_id'],
                'game_date': game['game_date'],
                'home_team': game['home_team_name'],
                'away_team': game['away_team_name'],
                'bet_on_home': bet_on_home,
                'bet_size': bet_size,
                'odds': odds,
                'model_prob': model_prob,
                'market_prob': market_prob,
                'edge': edge,
                'won': bet_won,
                'profit': profit,
                'bankroll_after': current_bankroll
            })
            
            self.bankroll_history.append(current_bankroll)
            
            # Log significant bets
            if abs(profit) > 100:
                logger.debug(f"{'✅ WIN' if bet_won else '❌ LOSS'}: "
                           f"{game['away_team_name']} @ {game['home_team_name']} | "
                           f"Bet ${bet_size:.0f} at {odds:.2f} | "
                           f"Profit: ${profit:+.2f} | "
                           f"Bankroll: ${current_bankroll:,.2f}")
        
        # Calculate metrics
        results = self.calculate_metrics()
        
        return results
    
    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive backtest metrics"""
        if not self.bets:
            logger.warning("No bets placed!")
            return {}
        
        bets_df = pd.DataFrame(self.bets)
        
        # Basic metrics
        total_bets = len(bets_df)
        wins = bets_df['won'].sum()
        losses = total_bets - wins
        win_rate = wins / total_bets
        
        total_wagered = bets_df['bet_size'].sum()
        total_profit = bets_df['profit'].sum()
        roi = total_profit / total_wagered
        
        final_bankroll = self.bankroll_history[-1]
        total_return = (final_bankroll - self.starting_bankroll) / self.starting_bankroll
        
        # Risk metrics
        returns = bets_df['profit'] / bets_df['bet_size']
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Drawdown analysis
        bankroll_series = pd.Series(self.bankroll_history)
        running_max = bankroll_series.expanding().max()
        drawdown = (bankroll_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Winning/losing streaks
        bets_df['streak'] = (bets_df['won'] != bets_df['won'].shift()).cumsum()
        streaks = bets_df.groupby('streak')['won'].agg(['first', 'count'])
        max_win_streak = streaks[streaks['first'] == True]['count'].max() if any(streaks['first'] == True) else 0
        max_loss_streak = streaks[streaks['first'] == False]['count'].max() if any(streaks['first'] == False) else 0
        
        # Average edge on bets placed
        avg_edge = bets_df['edge'].mean()
        
        metrics = {
            'starting_bankroll': self.starting_bankroll,
            'final_bankroll': final_bankroll,
            'total_profit': total_profit,
            'total_return_pct': total_return * 100,
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_wagered': total_wagered,
            'roi': roi,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_win_streak': int(max_win_streak),
            'max_loss_streak': int(max_loss_streak),
            'avg_edge': avg_edge,
            'avg_bet_size': bets_df['bet_size'].mean(),
            'avg_odds': bets_df['odds'].mean()
        }
        
        return metrics
    
    def print_results(self, metrics: Dict):
        """Print backtest results"""
        print("\n" + "=" * 70)
        print("📊 BACKTEST RESULTS")
        print("=" * 70)
        print(f"\n💰 BANKROLL")
        print(f"  Starting: ${metrics['starting_bankroll']:,.2f}")
        print(f"  Final: ${metrics['final_bankroll']:,.2f}")
        print(f"  Profit: ${metrics['total_profit']:+,.2f}")
        print(f"  Return: {metrics['total_return_pct']:+.2f}%")
        
        print(f"\n📈 BETTING ACTIVITY")
        print(f"  Total Bets: {metrics['total_bets']}")
        print(f"  Wins: {metrics['wins']}")
        print(f"  Losses: {metrics['losses']}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        
        print(f"\n💵 FINANCIAL METRICS")
        print(f"  Total Wagered: ${metrics['total_wagered']:,.2f}")
        print(f"  ROI: {metrics['roi']:.2%}")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
        
        print(f"\n🎯 BET QUALITY")
        print(f"  Avg Edge: {metrics['avg_edge']:.2%}")
        print(f"  Avg Bet Size: ${metrics['avg_bet_size']:,.2f}")
        print(f"  Avg Odds: {metrics['avg_odds']:.2f}")
        
        print(f"\n📉 RISK METRICS")
        print(f"  Max Win Streak: {metrics['max_win_streak']}")
        print(f"  Max Loss Streak: {metrics['max_loss_streak']}")
        
        print("=" * 70)


def main():
    """Main backtesting pipeline"""
    print("\n" + "=" * 70)
    print("🎲 NCAA BASKETBALL - BACKTESTING FRAMEWORK")
    print("=" * 70)
    print("Simulating Historical Betting with Kelly Criterion")
    print("=" * 70 + "\n")
    
    # Load data
    logger.info("📂 Loading training data...")
    df = pd.read_csv(DATA_PATH)
    logger.info(f"✅ Loaded {len(df)} games")
    
    # Load trained model
    logger.info("🤖 Loading trained model...")
    model_files = list(MODEL_PATH.glob("ncaa_basketball_model_*.joblib"))
    if not model_files:
        raise FileNotFoundError("No trained model found!")
    
    latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
    model = joblib.load(latest_model)
    logger.info(f"✅ Loaded model: {latest_model.name}")
    
    # Prepare features
    exclude_cols = [
        'game_id', 'game_date', 'season', 
        'home_team_id', 'away_team_id', 
        'home_team_name', 'away_team_name',
        'home_score', 'away_score', 
        'home_win', 'margin'
    ]
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    X = df[feature_cols].fillna(-999)
    
    # Generate predictions
    logger.info("🔮 Generating predictions...")
    predictions = model.predict_proba(X)[:, 1]  # Probability of home win
    logger.info(f"✅ Generated {len(predictions)} predictions")
    
    # Run backtest with different edge thresholds
    edge_thresholds = [0.02, 0.03, 0.05]
    
    for min_edge in edge_thresholds:
        print(f"\n\n{'='*70}")
        print(f"🎯 BACKTEST: Minimum Edge = {min_edge:.1%}")
        print(f"{'='*70}")
        
        engine = BacktestEngine(
            starting_bankroll=10000,
            min_edge=min_edge,
            max_bet_pct=0.05,
            fractional_kelly=0.25,
            vig=0.045
        )
        
        metrics = engine.run_backtest(df, predictions)
        engine.print_results(metrics)
        
        # Save bet log
        if engine.bets:
            bets_df = pd.DataFrame(engine.bets)
            output_path = Path(__file__).parent.parent / f"backtest_bets_edge{int(min_edge*100)}.csv"
            bets_df.to_csv(output_path, index=False)
            logger.info(f"💾 Bet log saved to {output_path}")


if __name__ == "__main__":
    main()

