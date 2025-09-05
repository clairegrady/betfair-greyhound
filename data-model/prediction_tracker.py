#!/usr/bin/env python3
"""
Prediction Tracker for ML Model Validation
Tracks predictions vs actual results to validate model performance
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictionTracker:
    def __init__(self, db_path: str = "prediction_tracking.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the tracking database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                horse_name TEXT NOT NULL,
                selection_id TEXT,
                predicted_probability REAL NOT NULL,
                predicted_rank INTEGER,
                confidence_level TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                model_version TEXT DEFAULT 'v1.0'
            )
        ''')
        
        # Results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                horse_name TEXT NOT NULL,
                selection_id TEXT,
                actual_position INTEGER,
                actual_finish_time REAL,
                placed BOOLEAN,
                won BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                total_predictions INTEGER,
                correct_predictions INTEGER,
                accuracy REAL,
                avg_confidence REAL,
                model_version TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Prediction tracking database initialized")
    
    def log_prediction(self, market_id: str, horse_name: str, selection_id: str, 
                      predicted_prob: float, predicted_rank: int, confidence_level: str):
        """Log a prediction made by the model"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO predictions 
            (market_id, horse_name, selection_id, predicted_probability, predicted_rank, confidence_level)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (market_id, horse_name, selection_id, predicted_prob, predicted_rank, confidence_level))
        
        conn.commit()
        conn.close()
        logger.info(f"📊 Logged prediction: {horse_name} - {predicted_prob:.1%} confidence")
    
    def log_result(self, market_id: str, horse_name: str, selection_id: str,
                  actual_position: int, actual_finish_time: Optional[float] = None):
        """Log actual race result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placed = actual_position <= 3  # Top 3 for place betting
        won = actual_position == 1
        
        cursor.execute('''
            INSERT INTO results 
            (market_id, horse_name, selection_id, actual_position, actual_finish_time, placed, won)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (market_id, horse_name, selection_id, actual_position, actual_finish_time, placed, won))
        
        conn.commit()
        conn.close()
        logger.info(f"🏁 Logged result: {horse_name} - Position {actual_position}")
    
    def calculate_accuracy(self, confidence_threshold: float = 0.6, days: int = 30) -> Dict:
        """Calculate model accuracy for high-confidence predictions"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                p.predicted_probability,
                p.confidence_level,
                r.placed,
                r.won,
                p.horse_name,
                p.market_id
            FROM predictions p
            JOIN results r ON p.market_id = r.market_id AND p.horse_name = r.horse_name
            WHERE p.predicted_probability >= ?
            AND p.timestamp >= datetime('now', '-{} days')
        '''.format(days)
        
        df = pd.read_sql_query(query, conn, params=[confidence_threshold])
        conn.close()
        
        if df.empty:
            return {
                'total_predictions': 0,
                'correct_predictions': 0,
                'accuracy': 0.0,
                'avg_confidence': 0.0,
                'high_confidence_failures': []
            }
        
        # Calculate metrics
        total_predictions = len(df)
        correct_predictions = df['placed'].sum()
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        avg_confidence = df['predicted_probability'].mean()
        
        # Find high-confidence failures
        failures = df[(df['predicted_probability'] >= 0.7) & (~df['placed'])]
        high_confidence_failures = []
        
        for _, row in failures.iterrows():
            high_confidence_failures.append({
                'horse_name': row['horse_name'],
                'market_id': row['market_id'],
                'predicted_probability': row['predicted_probability'],
                'actual_position': 'DNF' if pd.isna(row['placed']) else 'Outside Top 3'
            })
        
        return {
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'accuracy': accuracy,
            'avg_confidence': avg_confidence,
            'high_confidence_failures': high_confidence_failures
        }
    
    def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        conn = sqlite3.connect(self.db_path)
        
        # Recent performance (last 7 days)
        recent_query = '''
            SELECT 
                COUNT(*) as total_predictions,
                SUM(CASE WHEN r.placed THEN 1 ELSE 0 END) as correct_predictions,
                AVG(p.predicted_probability) as avg_confidence
            FROM predictions p
            JOIN results r ON p.market_id = r.market_id AND p.horse_name = r.horse_name
            WHERE p.timestamp >= datetime('now', '-7 days')
        '''
        
        recent_df = pd.read_sql_query(recent_query, conn)
        
        # High confidence performance
        high_conf_query = '''
            SELECT 
                COUNT(*) as total_predictions,
                SUM(CASE WHEN r.placed THEN 1 ELSE 0 END) as correct_predictions,
                AVG(p.predicted_probability) as avg_confidence
            FROM predictions p
            JOIN results r ON p.market_id = r.market_id AND p.horse_name = r.horse_name
            WHERE p.predicted_probability >= 0.6
            AND p.timestamp >= datetime('now', '-7 days')
        '''
        
        high_conf_df = pd.read_sql_query(high_conf_query, conn)
        conn.close()
        
        return {
            'recent_performance': {
                'total_predictions': recent_df['total_predictions'].iloc[0] if not recent_df.empty else 0,
                'correct_predictions': recent_df['correct_predictions'].iloc[0] if not recent_df.empty else 0,
                'accuracy': (recent_df['correct_predictions'].iloc[0] / recent_df['total_predictions'].iloc[0]) if not recent_df.empty and recent_df['total_predictions'].iloc[0] > 0 else 0,
                'avg_confidence': recent_df['avg_confidence'].iloc[0] if not recent_df.empty else 0
            },
            'high_confidence_performance': {
                'total_predictions': high_conf_df['total_predictions'].iloc[0] if not high_conf_df.empty else 0,
                'correct_predictions': high_conf_df['correct_predictions'].iloc[0] if not high_conf_df.empty else 0,
                'accuracy': (high_conf_df['correct_predictions'].iloc[0] / high_conf_df['total_predictions'].iloc[0]) if not high_conf_df.empty and high_conf_df['total_predictions'].iloc[0] > 0 else 0,
                'avg_confidence': high_conf_df['avg_confidence'].iloc[0] if not high_conf_df.empty else 0
            }
        }
    
    def export_failures_report(self, output_file: str = "model_failures.csv"):
        """Export high-confidence failures for analysis"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                p.market_id,
                p.horse_name,
                p.predicted_probability,
                p.confidence_level,
                r.actual_position,
                p.timestamp as prediction_time,
                r.timestamp as result_time
            FROM predictions p
            JOIN results r ON p.market_id = r.market_id AND p.horse_name = r.horse_name
            WHERE p.predicted_probability >= 0.6
            AND r.placed = 0
            ORDER BY p.predicted_probability DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        df.to_csv(output_file, index=False)
        logger.info(f"📄 Exported {len(df)} high-confidence failures to {output_file}")
        return df

# Example usage
if __name__ == "__main__":
    tracker = PredictionTracker()
    
    # Example: Log a prediction
    tracker.log_prediction(
        market_id="1.246844525",
        horse_name="7. Corso Venezia",
        selection_id="87381123.0",
        predicted_prob=0.77,
        predicted_rank=1,
        confidence_level="HIGH"
    )
    
    # Example: Log a result
    tracker.log_result(
        market_id="1.246844525",
        horse_name="7. Corso Venezia",
        selection_id="87381123.0",
        actual_position=8  # Came last
    )
    
    # Get performance summary
    performance = tracker.get_performance_summary()
    print("Performance Summary:", performance)
