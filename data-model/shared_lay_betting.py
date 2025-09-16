"""
Shared lay betting functionality for both backtesting and live betting
"""
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional


class LayBettingStrategy:
    """
    Shared lay betting strategy logic used by both backtest and live scripts
    """
    
    def __init__(self, std_threshold: float = 1.5, max_odds: float = 25.0):
        self.std_threshold = std_threshold
        self.max_odds = max_odds
    
    def analyze_race_eligibility(self, race_data: pd.DataFrame, odds_column: str = 'FixedWinOpen_Reference') -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Check if a race meets our lay betting criteria
        
        Args:
            race_data: DataFrame with race odds data
            odds_column: Column name containing the odds (for flexibility)
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses)
        """
        # Sort by odds (lowest first)
        race_data = race_data.sort_values(odds_column)
        total_horses = len(race_data)
        
        # Check 1: Must have at least 4 horses (minimum for meaningful analysis)
        if total_horses < 4:
            return False, "Less than 4 horses", None
        
        # Check 2: Get top half horses (lowest odds)
        top_half_count = total_horses // 2
        top_half = race_data.head(top_half_count)
        
        # Check 3: Calculate odds variance in top half
        top_half_odds = top_half[odds_column].values
        odds_std = np.std(top_half_odds)
        
        # If standard deviation is less than threshold, odds are too similar
        if odds_std < self.std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f})", None
        
        # Check 4: Get bottom half horses (highest odds)
        bottom_half = race_data.iloc[top_half_count:]  # Bottom half (0-indexed)
        
        # Check 5: Filter bottom half horses with odds <= max_odds
        eligible_horses = bottom_half[bottom_half[odds_column] <= self.max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {self.max_odds}:1", None
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay", eligible_horses
    
    def calculate_lay_bet_profit(self, horse_odds: float, horse_finished_position: float, stake: float = 1) -> float:
        """
        Calculate lay bet profit/loss
        
        Lay bet: We bet AGAINST the horse winning
        - If horse loses (position > 1): We win the stake
        - If horse wins (position = 1): We lose (odds - 1) * stake
        
        Args:
            horse_odds: The odds of the horse
            horse_finished_position: Where the horse finished (1 = won)
            stake: Amount staked
            
        Returns:
            float: Profit (positive) or loss (negative)
        """
        if horse_finished_position == 1:  # Horse won
            loss = (horse_odds - 1) * stake
            return -loss
        else:  # Horse lost (or scratched/abandoned)
            return stake
    
    def calculate_lay_bet_details(self, horse_odds: float, stake: float = 1) -> Dict[str, float]:
        """
        Calculate lay bet details for live betting
        
        Args:
            horse_odds: The lay odds
            stake: Amount to stake
            
        Returns:
            dict: Bet details including liability
        """
        liability = (horse_odds - 1) * stake
        
        return {
            'stake': stake,
            'odds': horse_odds,
            'liability': liability,
            'potential_profit': stake,
            'potential_loss': liability
        }
    
    def get_strategy_description(self) -> str:
        """Get a description of the current strategy"""
        return f"Lay betting strategy: Std threshold={self.std_threshold}, Max odds={self.max_odds}:1"


class LayBettingResults:
    """
    Container for lay betting results and statistics
    """
    
    def __init__(self):
        self.bets: List[Dict[str, Any]] = []
        self.total_stake: float = 0
        self.total_profit: float = 0
    
    def add_bet(self, bet_data: Dict[str, Any]):
        """Add a bet to the results"""
        self.bets.append(bet_data)
        self.total_stake += bet_data.get('stake', 0)
        self.total_profit += bet_data.get('profit', 0)
    
    def get_statistics(self) -> Dict[str, float]:
        """Calculate and return betting statistics"""
        if not self.bets:
            return {
                'total_bets': 0,
                'total_stake': 0,
                'total_profit': 0,
                'roi': 0,
                'win_rate': 0,
                'avg_profit_per_bet': 0,
                'risk_score': 100
            }
        
        won_bets = len([bet for bet in self.bets if bet.get('won', False)])
        roi = (self.total_profit / self.total_stake * 100) if self.total_stake > 0 else 0
        win_rate = (won_bets / len(self.bets) * 100) if self.bets else 0
        avg_profit_per_bet = self.total_profit / len(self.bets) if self.bets else 0
        risk_score = 100 - roi
        
        return {
            'total_bets': len(self.bets),
            'total_stake': round(self.total_stake, 2),
            'total_profit': round(self.total_profit, 2),
            'roi': round(roi, 2),
            'win_rate': round(win_rate, 2),
            'avg_profit_per_bet': round(avg_profit_per_bet, 2),
            'risk_score': round(risk_score, 2)
        }
    
    def clear(self):
        """Clear all results"""
        self.bets = []
        self.total_stake = 0
        self.total_profit = 0
