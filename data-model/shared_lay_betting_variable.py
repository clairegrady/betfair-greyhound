"""
Shared lay betting functionality with variable max odds and std thresholds
Based on field size for optimal performance across all race types
"""
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional


class LayBettingStrategyVariable:
    """
    Lay betting strategy with variable max odds and std thresholds based on field size
    """
    
    def __init__(self, base_std_threshold: float = 1.0, base_max_odds: float = 30.0):
        """
        Initialize the variable strategy
        
        Args:
            base_std_threshold: Base std threshold for 12-horse field (default: 1.0)
            base_max_odds: Base max odds for 12-horse field (default: 30.0)
        """
        self.base_std_threshold = base_std_threshold
        self.base_max_odds = base_max_odds
    
    def calculate_variable_max_odds(self, field_size: int) -> float:
        """
        Calculate max odds based on field size
        Formula: MaxOddsAllowed = base_max_odds × (field_size / 12)
        
        Examples:
        - 6 horses → 30 × (6/12) = 15.0
        - 12 horses → 30 × (12/12) = 30.0  
        - 18 horses → 30 × (18/12) = 45.0
        """
        return self.base_max_odds * (field_size / 12.0)
    
    def calculate_variable_std_threshold(self, field_size: int) -> float:
        """
        Calculate std threshold based on field size
        Formula: StdThreshold = base_std × (field_size / 12)
        
        Examples:
        - 6 horses → 1.0 × (6/12) = 0.5
        - 12 horses → 1.0 × (12/12) = 1.0
        - 18 horses → 1.0 × (18/12) = 1.5
        """
        return self.base_std_threshold * (field_size / 12.0)
    
    def analyze_race_eligibility(self, race_data: pd.DataFrame, odds_column: str = 'FixedWinOpen_Reference') -> Tuple[bool, str, Optional[pd.DataFrame], Optional[float], Optional[float]]:
        """
        Check if a race meets our lay betting criteria with variable max odds AND std threshold
        
        Args:
            race_data: DataFrame with race odds data
            odds_column: Column name containing the odds (for flexibility)
            
        Returns:
            tuple: (is_eligible, reason, eligible_horses, variable_max_odds, variable_std_threshold)
        """
        # Filter out horses without odds for analysis
        horses_with_odds = race_data.dropna(subset=[odds_column])
        
        # Check 1: Must have at least 6 horses total
        if len(race_data) < 6:
            return False, f"Less than 6 horses (total: {len(race_data)})", None, None, None
        
        # Check 2: Must have at least 6 horses with odds
        if len(horses_with_odds) < 6:
            return False, f"Less than 6 horses with odds (total: {len(race_data)}, with odds: {len(horses_with_odds)})", None, None, None
        
        # Calculate variable parameters based on field size
        field_size = len(horses_with_odds)
        variable_max_odds = self.calculate_variable_max_odds(field_size)
        variable_std_threshold = self.calculate_variable_std_threshold(field_size)
        
        # Sort by odds (lowest first)
        horses_with_odds = horses_with_odds.sort_values(odds_column)
        
        # Check 3: Get top half horses (lowest odds)
        top_half_count = len(horses_with_odds) // 2
        top_half = horses_with_odds.head(top_half_count)
        
        # Check 4: Calculate odds variance in top half
        top_half_odds = top_half[odds_column].values
        odds_std = np.std(top_half_odds)
        
        # If standard deviation is less than variable threshold, odds are too similar
        if odds_std < variable_std_threshold:
            return False, f"Top half odds too similar (std: {odds_std:.2f} < {variable_std_threshold:.2f})", None, variable_max_odds, variable_std_threshold
        
        # Check 5: Get bottom half horses (highest odds)
        bottom_half = horses_with_odds.iloc[top_half_count:]  # Bottom half (0-indexed)
        
        # Check 6: Filter bottom half horses with odds <= variable_max_odds
        eligible_horses = bottom_half[bottom_half[odds_column] <= variable_max_odds]
        
        if len(eligible_horses) == 0:
            return False, f"No horses in bottom half with odds <= {variable_max_odds:.1f}:1 (field size: {field_size})", None, variable_max_odds, variable_std_threshold
        
        return True, f"Eligible - {len(eligible_horses)} horses to lay (max odds: {variable_max_odds:.1f}:1, std: {variable_std_threshold:.1f})", eligible_horses, variable_max_odds, variable_std_threshold
    
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
        return f"Variable lay betting strategy: Base std={self.base_std_threshold}, Base max odds={self.base_max_odds}:1 (scales with field size)"


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
