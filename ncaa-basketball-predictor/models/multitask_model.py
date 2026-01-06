"""
Multi-Task NCAA Basketball Prediction Model

Predicts:
1. Winner (binary classification)
2. Point Margin (quantile regression: 10th, 50th, 90th percentiles)
3. Total Points (quantile regression: 10th, 50th, 90th percentiles)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class QuantileLoss(nn.Module):
    """
    Quantile loss for confidence interval prediction.
    
    For quantile q:
    - If prediction is too low: penalize by q * error
    - If prediction is too high: penalize by (1-q) * error
    """
    def __init__(self, quantiles=[0.1, 0.5, 0.9]):
        super().__init__()
        self.quantiles = quantiles
    
    def forward(self, preds, target):
        """
        Args:
            preds: (batch_size, 3) - predictions for 10th, 50th, 90th percentiles
            target: (batch_size,) - true values
        """
        losses = []
        for i, q in enumerate(self.quantiles):
            errors = target - preds[:, i]
            losses.append(torch.max((q - 1) * errors, q * errors))
        
        return torch.mean(torch.stack(losses))


class MultiTaskNCAAModel(nn.Module):
    """
    Multi-task neural network for NCAA basketball predictions.
    
    Architecture:
    - Shared feature extraction layers
    - Three task-specific heads:
        1. Winner classification (sigmoid output)
        2. Point margin prediction (3 quantiles)
        3. Total points prediction (3 quantiles)
    """
    
    def __init__(self, input_dim, hidden_dims=[256, 128, 64], dropout_rate=0.3):
        super().__init__()
        
        # Shared feature extraction layers
        self.shared_layers = nn.ModuleList()
        prev_dim = input_dim
        
        for i, hidden_dim in enumerate(hidden_dims):
            self.shared_layers.append(nn.Linear(prev_dim, hidden_dim))
            self.shared_layers.append(nn.ReLU())
            # Decrease dropout in deeper layers
            dropout = dropout_rate * (1 - (i / len(hidden_dims)) * 0.3)
            self.shared_layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        # Task-specific heads
        last_hidden = hidden_dims[-1]
        
        # Winner head (binary classification)
        self.winner_head = nn.Sequential(
            nn.Linear(last_hidden, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
        
        # Margin head (quantile regression - 3 outputs for 10th, 50th, 90th percentiles)
        self.margin_head = nn.Sequential(
            nn.Linear(last_hidden, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 3)  # 3 quantiles
        )
        
        # Totals head (quantile regression - 3 outputs)
        self.totals_head = nn.Sequential(
            nn.Linear(last_hidden, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 3)  # 3 quantiles
        )
    
    def forward(self, x):
        """
        Forward pass through all tasks.
        
        Args:
            x: (batch_size, input_dim) - input features
            
        Returns:
            dict with keys:
                - 'winner': (batch_size, 1) - probability of home win
                - 'margin': (batch_size, 3) - margin quantiles [10th, 50th, 90th]
                - 'totals': (batch_size, 3) - totals quantiles [10th, 50th, 90th]
        """
        # Shared feature extraction
        h = x
        for layer in self.shared_layers:
            h = layer(h)
        
        # Task-specific predictions
        winner_prob = self.winner_head(h)
        margin_quantiles = self.margin_head(h)
        totals_quantiles = self.totals_head(h)
        
        # Ensure quantile ordering (q10 <= q50 <= q90) using cumulative sums
        # This prevents non-monotonic predictions
        margin_quantiles = self._ensure_quantile_order(margin_quantiles)
        totals_quantiles = self._ensure_quantile_order(totals_quantiles)
        
        return {
            'winner': winner_prob,
            'margin': margin_quantiles,
            'totals': totals_quantiles
        }
    
    def _ensure_quantile_order(self, quantiles):
        """
        Ensure quantiles are monotonically increasing: q10 <= q50 <= q90
        
        Method: Use softplus to ensure positive gaps between quantiles
        """
        q10 = quantiles[:, 0:1]  # Keep dimension
        q50 = q10 + F.softplus(quantiles[:, 1:2])  # q50 >= q10
        q90 = q50 + F.softplus(quantiles[:, 2:3])  # q90 >= q50
        
        return torch.cat([q10, q50, q90], dim=1)
    
    def predict_with_confidence(self, x):
        """
        Make predictions with confidence levels.
        
        Args:
            x: input features
            
        Returns:
            dict with predictions and confidence levels
        """
        with torch.no_grad():
            outputs = self.forward(x)
            
            # Calculate confidence from quantile spread
            margin_confidence = self._calculate_confidence(
                outputs['margin'], 
                expected_range=30.0  # Typical margin range in basketball
            )
            
            totals_confidence = self._calculate_confidence(
                outputs['totals'],
                expected_range=40.0  # Typical totals range
            )
            
            return {
                'winner_prob': outputs['winner'].cpu().numpy(),
                'margin_pred': outputs['margin'][:, 1].cpu().numpy(),  # 50th percentile
                'margin_lower': outputs['margin'][:, 0].cpu().numpy(),  # 10th percentile
                'margin_upper': outputs['margin'][:, 2].cpu().numpy(),  # 90th percentile
                'margin_confidence': margin_confidence,
                'totals_pred': outputs['totals'][:, 1].cpu().numpy(),
                'totals_lower': outputs['totals'][:, 0].cpu().numpy(),
                'totals_upper': outputs['totals'][:, 2].cpu().numpy(),
                'totals_confidence': totals_confidence
            }
    
    def _calculate_confidence(self, quantiles, expected_range):
        """
        Calculate confidence level from quantile spread.
        
        Narrow spread = high confidence
        Wide spread = low confidence
        
        Args:
            quantiles: (batch_size, 3) - [q10, q50, q90]
            expected_range: typical range for this prediction type
            
        Returns:
            confidence: (batch_size,) - values between 0 and 1
        """
        q10 = quantiles[:, 0]
        q90 = quantiles[:, 2]
        spread = q90 - q10
        
        # Normalize by expected range and convert to confidence
        # Smaller spread = higher confidence
        confidence = 1.0 - torch.clamp(spread / expected_range, 0.0, 1.0)
        
        return confidence.cpu().numpy()


class MultiTaskLoss(nn.Module):
    """
    Combined loss for multi-task learning.
    
    Weighted combination of:
    - Binary cross-entropy for winner prediction
    - Quantile loss for margin prediction
    - Quantile loss for totals prediction
    """
    
    def __init__(self, 
                 winner_weight=0.3, 
                 margin_weight=0.4, 
                 totals_weight=0.3,
                 quantiles=[0.1, 0.5, 0.9]):
        super().__init__()
        self.winner_weight = winner_weight
        self.margin_weight = margin_weight
        self.totals_weight = totals_weight
        
        self.bce_loss = nn.BCELoss()
        self.margin_quantile_loss = QuantileLoss(quantiles)
        self.totals_quantile_loss = QuantileLoss(quantiles)
    
    def forward(self, predictions, targets):
        """
        Args:
            predictions: dict from model.forward()
            targets: dict with keys 'winner', 'margin', 'totals'
        """
        winner_loss = self.bce_loss(
            predictions['winner'].squeeze(), 
            targets['winner'].float()
        )
        
        margin_loss = self.margin_quantile_loss(
            predictions['margin'],
            targets['margin']
        )
        
        totals_loss = self.totals_quantile_loss(
            predictions['totals'],
            targets['totals']
        )
        
        total_loss = (
            self.winner_weight * winner_loss +
            self.margin_weight * margin_loss +
            self.totals_weight * totals_loss
        )
        
        return {
            'total': total_loss,
            'winner': winner_loss,
            'margin': margin_loss,
            'totals': totals_loss
        }


def create_model(input_dim, device='cpu'):
    """
    Factory function to create and initialize the model.
    
    Args:
        input_dim: number of input features
        device: 'cpu' or 'cuda'
        
    Returns:
        model, loss_fn
    """
    model = MultiTaskNCAAModel(
        input_dim=input_dim,
        hidden_dims=[256, 128, 64],
        dropout_rate=0.3
    ).to(device)
    
    loss_fn = MultiTaskLoss(
        winner_weight=0.3,
        margin_weight=0.4,
        totals_weight=0.3
    )
    
    return model, loss_fn


if __name__ == '__main__':
    # Test the model
    print("Testing MultiTaskNCAAModel...")
    
    # Create dummy data
    batch_size = 32
    input_dim = 50  # Typical number of features
    
    X = torch.randn(batch_size, input_dim)
    targets = {
        'winner': torch.randint(0, 2, (batch_size,)),
        'margin': torch.randn(batch_size) * 10,  # Margins typically -30 to +30
        'totals': torch.randn(batch_size) * 10 + 145  # Totals typically 130-160
    }
    
    # Create model
    model, loss_fn = create_model(input_dim)
    
    # Forward pass
    outputs = model(X)
    print(f"\nOutput shapes:")
    print(f"  Winner: {outputs['winner'].shape}")
    print(f"  Margin: {outputs['margin'].shape}")
    print(f"  Totals: {outputs['totals'].shape}")
    
    # Calculate loss
    losses = loss_fn(outputs, targets)
    print(f"\nLosses:")
    print(f"  Total: {losses['total'].item():.4f}")
    print(f"  Winner: {losses['winner'].item():.4f}")
    print(f"  Margin: {losses['margin'].item():.4f}")
    print(f"  Totals: {losses['totals'].item():.4f}")
    
    # Test prediction with confidence
    predictions = model.predict_with_confidence(X[:5])
    print(f"\nSample predictions (first 5):")
    for i in range(5):
        print(f"\nGame {i+1}:")
        print(f"  Winner prob: {predictions['winner_prob'][i][0]:.3f}")
        print(f"  Margin: {predictions['margin_pred'][i]:.1f} "
              f"[{predictions['margin_lower'][i]:.1f}, {predictions['margin_upper'][i]:.1f}] "
              f"(confidence: {predictions['margin_confidence'][i]:.1%})")
        print(f"  Totals: {predictions['totals_pred'][i]:.1f} "
              f"[{predictions['totals_lower'][i]:.1f}, {predictions['totals_upper'][i]:.1f}] "
              f"(confidence: {predictions['totals_confidence'][i]:.1%})")
    
    print("\n✅ Model test complete!")

