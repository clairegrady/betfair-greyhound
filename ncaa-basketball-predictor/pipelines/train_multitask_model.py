"""
Phase 2: Multi-Task Neural Network Training
Trains a neural network to predict winner, margin, and total points simultaneously
with confidence intervals using quantile regression.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
import logging
import json
from models.multitask_model import create_model, MultiTaskLoss

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NCAADataset(Dataset):
    """PyTorch Dataset for NCAA basketball games"""
    
    def __init__(self, X, y_winner, y_margin, y_totals):
        self.X = torch.FloatTensor(X)
        self.y_winner = torch.FloatTensor(y_winner)
        self.y_margin = torch.FloatTensor(y_margin)
        self.y_totals = torch.FloatTensor(y_totals)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return (
            self.X[idx],
            {
                'winner': self.y_winner[idx],
                'margin': self.y_margin[idx],
                'totals': self.y_totals[idx]
            }
        )


def train_epoch(model, dataloader, loss_fn, optimizer, device):
    """Train for one epoch"""
    model.train()
    total_loss = 0.0
    winner_loss_sum = 0.0
    margin_loss_sum = 0.0
    totals_loss_sum = 0.0
    
    for X_batch, y_batch in dataloader:
        X_batch = X_batch.to(device)
        y_batch = {k: v.to(device) for k, v in y_batch.items()}
        
        optimizer.zero_grad()
        predictions = model(X_batch)
        losses = loss_fn(predictions, y_batch)
        
        losses['total'].backward()
        optimizer.step()
        
        total_loss += losses['total'].item()
        winner_loss_sum += losses['winner'].item()
        margin_loss_sum += losses['margin'].item()
        totals_loss_sum += losses['totals'].item()
    
    n_batches = len(dataloader)
    return {
        'total': total_loss / n_batches,
        'winner': winner_loss_sum / n_batches,
        'margin': margin_loss_sum / n_batches,
        'totals': totals_loss_sum / n_batches
    }


def evaluate(model, dataloader, loss_fn, device):
    """Evaluate model on validation/test set"""
    model.eval()
    total_loss = 0.0
    winner_loss_sum = 0.0
    margin_loss_sum = 0.0
    totals_loss_sum = 0.0
    
    all_predictions = []
    all_targets = []
    
    with torch.no_grad():
        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(device)
            y_batch = {k: v.to(device) for k, v in y_batch.items()}
            
            predictions = model(X_batch)
            losses = loss_fn(predictions, y_batch)
            
            total_loss += losses['total'].item()
            winner_loss_sum += losses['winner'].item()
            margin_loss_sum += losses['margin'].item()
            totals_loss_sum += losses['totals'].item()
            
            # Store predictions for metrics
            all_predictions.append({
                'winner': predictions['winner'].cpu().numpy(),
                'margin': predictions['margin'][:, 1].cpu().numpy(),  # Median
                'totals': predictions['totals'][:, 1].cpu().numpy()
            })
            all_targets.append({
                'winner': y_batch['winner'].cpu().numpy(),
                'margin': y_batch['margin'].cpu().numpy(),
                'totals': y_batch['totals'].cpu().numpy()
            })
    
    n_batches = len(dataloader)
    losses = {
        'total': total_loss / n_batches,
        'winner': winner_loss_sum / n_batches,
        'margin': margin_loss_sum / n_batches,
        'totals': totals_loss_sum / n_batches
    }
    
    # Calculate metrics
    all_pred_winner = np.concatenate([p['winner'] for p in all_predictions])
    all_true_winner = np.concatenate([t['winner'] for t in all_targets])
    all_pred_margin = np.concatenate([p['margin'] for p in all_predictions])
    all_true_margin = np.concatenate([t['margin'] for t in all_targets])
    all_pred_totals = np.concatenate([p['totals'] for p in all_predictions])
    all_true_totals = np.concatenate([t['totals'] for t in all_targets])
    
    winner_acc = ((all_pred_winner > 0.5).squeeze() == all_true_winner).mean()
    margin_mae = np.abs(all_pred_margin - all_true_margin).mean()
    totals_mae = np.abs(all_pred_totals - all_true_totals).mean()
    
    return losses, {
        'winner_accuracy': winner_acc,
        'margin_mae': margin_mae,
        'totals_mae': totals_mae
    }


def main():
    logger.info("\n" + "="*70)
    logger.info("PHASE 2: MULTI-TASK NEURAL NETWORK TRAINING")
    logger.info("="*70)
    
    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Load features
    features_path = Path(__file__).parent.parent / "features_dataset.csv"
    logger.info(f"\nLoading features from: {features_path}")
    df = pd.read_csv(features_path)
    logger.info(f"Loaded {len(df):,} games")
    
    # Filter to games with player data
    df = df.dropna(subset=['home_avg_player_ortg', 'away_avg_player_ortg'])
    logger.info(f"After filtering: {len(df):,} games with player data")
    
    # Fill remaining NaNs
    df = df.fillna(0)
    
    # Time-based split (using season 2025 data - 24-25 season)
    df['game_date'] = pd.to_datetime(df['game_date'])
    season_2024_df = df[df['season'] == 2025]  # 2025 = 24-25 season
    
    # Split: Train (Nov 2024 - Jan 2025), Val (Feb 2025), Test (Mar 2025+)
    train_df = season_2024_df[season_2024_df['game_date'] < '2025-02-01']
    val_df = season_2024_df[
        (season_2024_df['game_date'] >= '2025-02-01') & 
        (season_2024_df['game_date'] < '2025-03-01')
    ]
    test_df = season_2024_df[season_2024_df['game_date'] >= '2025-03-01']
    
    logger.info(f"\nData split:")
    logger.info(f"  Train: {len(train_df):,} games")
    logger.info(f"  Val: {len(val_df):,} games")
    logger.info(f"  Test: {len(test_df):,} games")
    
    if len(train_df) == 0 or len(val_df) == 0:
        logger.error("Insufficient data for training. Check data collection.")
        return
    
    # Define features
    exclude_cols = ['game_id', 'game_date', 'season', 'home_team', 'away_team', 
                   'home_won', 'point_margin', 'total_points']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    logger.info(f"\nUsing {len(feature_cols)} features")
    
    # Prepare data
    X_train = train_df[feature_cols].values
    y_train_winner = train_df['home_won'].values
    y_train_margin = train_df['point_margin'].values
    y_train_totals = train_df['total_points'].values
    
    X_val = val_df[feature_cols].values
    y_val_winner = val_df['home_won'].values
    y_val_margin = val_df['point_margin'].values
    y_val_totals = val_df['total_points'].values
    
    X_test = test_df[feature_cols].values
    y_test_winner = test_df['home_won'].values
    y_test_margin = test_df['point_margin'].values
    y_test_totals = test_df['total_points'].values
    
    # Standardize features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)
    
    # Create datasets
    train_dataset = NCAADataset(X_train, y_train_winner, y_train_margin, y_train_totals)
    val_dataset = NCAADataset(X_val, y_val_winner, y_val_margin, y_val_totals)
    test_dataset = NCAADataset(X_test, y_test_winner, y_test_margin, y_test_totals)
    
    # Create dataloaders
    batch_size = 64
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    test_loader = DataLoader(test_dataset, batch_size=batch_size)
    
    # Create model
    input_dim = X_train.shape[1]
    model, loss_fn = create_model(input_dim, device=device)
    
    logger.info(f"\nModel architecture:")
    logger.info(f"  Input dimension: {input_dim}")
    logger.info(f"  Hidden layers: [256, 128, 64]")
    logger.info(f"  Dropout: 0.3")
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"  Total parameters: {total_params:,}")
    
    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    
    # Training loop
    num_epochs = 100
    best_val_loss = float('inf')
    patience = 15
    patience_counter = 0
    
    logger.info(f"\n" + "="*70)
    logger.info("TRAINING")
    logger.info("="*70)
    
    for epoch in range(num_epochs):
        train_losses = train_epoch(model, train_loader, loss_fn, optimizer, device)
        val_losses, val_metrics = evaluate(model, val_loader, loss_fn, device)
        
        # Learning rate scheduling
        scheduler.step(val_losses['total'])
        
        # Log progress
        if (epoch + 1) % 5 == 0 or epoch == 0:
            logger.info(f"\nEpoch {epoch+1}/{num_epochs}")
            logger.info(f"  Train Loss: {train_losses['total']:.4f} "
                       f"(W:{train_losses['winner']:.4f}, "
                       f"M:{train_losses['margin']:.4f}, "
                       f"T:{train_losses['totals']:.4f})")
            logger.info(f"  Val Loss: {val_losses['total']:.4f} "
                       f"(W:{val_losses['winner']:.4f}, "
                       f"M:{val_losses['margin']:.4f}, "
                       f"T:{val_losses['totals']:.4f})")
            logger.info(f"  Val Metrics: Accuracy={val_metrics['winner_accuracy']:.3f}, "
                       f"Margin MAE={val_metrics['margin_mae']:.2f}, "
                       f"Totals MAE={val_metrics['totals_mae']:.2f}")
        
        # Early stopping
        if val_losses['total'] < best_val_loss:
            best_val_loss = val_losses['total']
            patience_counter = 0
            # Save best model
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scaler_mean': scaler.mean_,
                'scaler_scale': scaler.scale_,
                'feature_cols': feature_cols,
                'val_loss': val_losses['total'],
                'val_metrics': val_metrics
            }, Path(__file__).parent.parent / 'models' / 'multitask_model_best.pth')
            logger.info(f"  ✅ New best model saved!")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"\nEarly stopping triggered after {epoch+1} epochs")
                break
    
    # Load best model and evaluate on test set
    logger.info(f"\n" + "="*70)
    logger.info("TEST SET EVALUATION")
    logger.info("="*70)
    
    checkpoint = torch.load(
        Path(__file__).parent.parent / 'models' / 'multitask_model_best.pth',
        weights_only=False
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    
    test_losses, test_metrics = evaluate(model, test_loader, loss_fn, device)
    
    logger.info(f"\nTest Results:")
    logger.info(f"  Loss: {test_losses['total']:.4f}")
    logger.info(f"  Winner Accuracy: {test_metrics['winner_accuracy']:.1%}")
    logger.info(f"  Margin MAE: {test_metrics['margin_mae']:.2f} points")
    logger.info(f"  Totals MAE: {test_metrics['totals_mae']:.2f} points")
    
    # Save results
    results = {
        'test_loss': test_losses['total'],
        'test_winner_accuracy': float(test_metrics['winner_accuracy']),
        'test_margin_mae': float(test_metrics['margin_mae']),
        'test_totals_mae': float(test_metrics['totals_mae']),
        'best_val_loss': float(best_val_loss),
        'num_epochs': epoch + 1,
        'num_features': len(feature_cols),
        'train_size': len(train_df),
        'val_size': len(val_df),
        'test_size': len(test_df)
    }
    
    with open(Path(__file__).parent.parent / 'models' / 'multitask_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✅ Phase 2 training complete!")
    logger.info(f"   Model saved: models/multitask_model_best.pth")
    logger.info(f"   Results saved: models/multitask_results.json")


if __name__ == '__main__':
    main()

