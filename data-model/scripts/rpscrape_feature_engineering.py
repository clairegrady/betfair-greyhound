#!/usr/bin/env python3
"""
RPScrape-Only Feature Engineering
Creates features using only the RPScrape racing results data
Much simpler than merging with Betfair data
"""

import pandas as pd
import numpy as np
import sqlite3
import logging
from datetime import datetime
import gc
import os

# Configuration
SAMPLE_MODE = False  # Process full dataset
SAMPLE_SIZE = 1000   # Number of records to process in sample mode (when enabled)
DEBUG_MODE = False   # Add extra debugging output

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rpscrape_feature_engineering.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def connect_to_db():
    """Connect to the racing database"""
    return sqlite3.connect('racing_data.db')

def load_rpscrape_data():
    """Load RPScrape data for feature engineering"""
    logger.info("🏇 Loading RPScrape data...")
    
    conn = connect_to_db()
    
    try:
        if SAMPLE_MODE:
            query = """
                SELECT *
                FROM rpscrape_aus_races
                WHERE horse_name IS NOT NULL
                AND finishing_position IS NOT NULL
                ORDER BY date DESC
                LIMIT ?
            """
            df = pd.read_sql(query, conn, params=[SAMPLE_SIZE])
            logger.info(f"🧪 SAMPLE MODE: Loaded {len(df):,} records (limit: {SAMPLE_SIZE:,})")
        else:
            query = """
                SELECT *
                FROM rpscrape_aus_races
                WHERE horse_name IS NOT NULL
                AND finishing_position IS NOT NULL
                ORDER BY date
            """
            df = pd.read_sql(query, conn)
            logger.info(f"📊 FULL MODE: Loaded {len(df):,} records")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error loading RPScrape data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def create_target_variables(df):
    """Create target variables for prediction"""
    logger.info("🎯 Creating target variables...")
    
    # Win target: 1 if horse won (finishing_position == 1)
    df['target_win'] = (df['finishing_position'] == 1).astype(int)
    
    # Place target: 1 if horse placed (top 3)  
    df['target_place'] = (df['finishing_position'] <= 3).astype(int)
    
    # Show place: 1 if horse showed (top 4 in larger fields)
    df['target_show'] = (df['finishing_position'] <= 4).astype(int)
    
    logger.info(f"🏆 Win rate: {df['target_win'].mean():.3f}")
    logger.info(f"🥉 Place rate: {df['target_place'].mean():.3f}")
    logger.info(f"📊 Show rate: {df['target_show'].mean():.3f}")
    
    return df

def create_time_features(df):
    """Create time-based features"""
    logger.info("🕐 Creating time features...")
    
    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Basic time features
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['day_of_week'] = df['date'].dt.dayofweek
    df['day_of_year'] = df['date'].dt.dayofyear
    df['quarter'] = df['date'].dt.quarter
    
    # Weekend indicator
    df['is_weekend'] = (df['day_of_week'].isin([5, 6])).astype(int)
    
    # Season indicators (Southern Hemisphere)
    df['is_summer'] = df['month'].isin([12, 1, 2]).astype(int)
    df['is_autumn'] = df['month'].isin([3, 4, 5]).astype(int)
    df['is_winter'] = df['month'].isin([6, 7, 8]).astype(int)
    df['is_spring'] = df['month'].isin([9, 10, 11]).astype(int)
    
    # Racing season features
    df['is_carnival_season'] = df['month'].isin([10, 11, 12, 1, 2, 3]).astype(int)  # Spring/Summer racing
    
    logger.info(f"✅ Created {9} time features")
    return df

def create_race_features(df):
    """Create race-specific features"""
    logger.info("🏁 Creating race features...")
    
    # Field size features
    df['field_size_log'] = np.log(df['field_size'].clip(lower=1))
    df['field_size_category'] = pd.cut(df['field_size'], 
                                      bins=[0, 8, 12, 16, 20, 50], 
                                      labels=['small', 'medium', 'large', 'very_large', 'huge']).cat.codes
    
    # Distance features (if available)
    if 'distance_furlongs' in df.columns:
        df['distance_log'] = np.log(df['distance_furlongs'].clip(lower=1))
        df['distance_category'] = pd.cut(df['distance_furlongs'],
                                        bins=[0, 6, 10, 14, 20, 50],
                                        labels=['sprint', 'mile', 'middle', 'staying', 'extreme']).cat.codes
    
    # Prize money features (if available)
    if 'prize_money_numeric' in df.columns:
        df['prize_money_log'] = np.log(df['prize_money_numeric'].clip(lower=1))
        df['prize_money_category'] = pd.cut(df['prize_money_numeric'],
                                           bins=[0, 20000, 50000, 100000, 500000, float('inf')],
                                           labels=['low', 'medium', 'high', 'elite', 'group1']).cat.codes
    
    # Class rating features (if available)
    if 'class_rating_numeric' in df.columns and df['class_rating_numeric'].notna().sum() > 0:
        df['class_rating_scaled'] = df['class_rating_numeric'] / 100  # Normalize class ratings
        df['is_high_class'] = (df['class_rating_numeric'] > 80).astype(int)
    
    # Going features
    if 'going' in df.columns:
        going_mapping = {
            'Good': 1, 'Good to Firm': 2, 'Firm': 3, 'Good to Soft': 4,
            'Soft': 5, 'Heavy': 6, 'Standard': 7, 'Fast': 8
        }
        df['going_encoded'] = df['going'].map(going_mapping).fillna(0)
        df['is_firm_track'] = df['going'].isin(['Good to Firm', 'Firm']).astype(int)
        df['is_soft_track'] = df['going'].isin(['Soft', 'Heavy']).astype(int)
    
    logger.info(f"✅ Created race features")
    return df

def create_horse_features(df):
    """Create horse-specific features"""
    logger.info("🐎 Creating horse features...")
    
    # Age features
    if 'age' in df.columns:
        df['age_category'] = pd.cut(df['age'], 
                                   bins=[0, 3, 5, 8, 20], 
                                   labels=['young', 'prime', 'mature', 'veteran']).cat.codes
        df['is_prime_age'] = (df['age'].between(3, 6)).astype(int)
    
    # Weight features
    if 'weight_carried' in df.columns:
        # Calculate weight relative to field average
        race_groups = df.groupby(['date', 'course', 'race_name'])
        df['weight_advantage'] = df['weight_carried'] - race_groups['weight_carried'].transform('mean')
        df['is_topweight'] = (df['weight_carried'] == race_groups['weight_carried'].transform('max')).astype(int)
    
    # Sex features
    if 'sex' in df.columns:
        df['sex_encoded'] = pd.Categorical(df['sex']).codes
        df['is_male'] = (df['sex'].isin(['C', 'G', 'H'])).astype(int)  # Colt, Gelding, Horse
        df['is_female'] = (df['sex'].isin(['F', 'M'])).astype(int)     # Filly, Mare
    
    logger.info(f"✅ Created horse features")
    return df

def create_odds_features(df):
    """Create odds-based features"""
    logger.info("💰 Creating odds features...")
    
    if 'odds_decimal' in df.columns:
        # Basic odds features
        df['odds_log'] = np.log(df['odds_decimal'].clip(lower=1.01))
        df['implied_probability'] = 1 / df['odds_decimal'].clip(lower=1.01)
        
        # Odds categories
        df['odds_category'] = pd.cut(df['odds_decimal'],
                                    bins=[0, 2.5, 5, 10, 20, float('inf')],
                                    labels=['favourite', 'second_choice', 'medium', 'longshot', 'outsider']).cat.codes
        
        df['is_favourite'] = (df['odds_decimal'] < 3.0).astype(int)
        df['is_longshot'] = (df['odds_decimal'] > 10.0).astype(int)
        
        # Relative odds within race
        race_groups = df.groupby(['date', 'course', 'race_name'])
        df['odds_rank'] = race_groups['odds_decimal'].rank(method='min')
        df['odds_rank_pct'] = df['odds_rank'] / race_groups['odds_decimal'].transform('count')
        df['is_race_favourite'] = (df['odds_rank'] == 1).astype(int)
        df['is_top3_choice'] = (df['odds_rank'] <= 3).astype(int)
        
        # Market share
        df['market_share'] = df['implied_probability'] / race_groups['implied_probability'].transform('sum')
        
        logger.info(f"✅ Created odds features")
    else:
        logger.warning("⚠️ No odds_decimal column found - skipping odds features")
    
    return df

def create_historical_features(df):
    """Create historical performance features"""
    logger.info("📈 Creating historical features...")
    
    # Sort by horse and date for rolling calculations
    df = df.sort_values(['horse_name', 'date']).reset_index(drop=True)
    
    # Career statistics (cumulative)
    df['career_starts'] = df.groupby('horse_name').cumcount()
    df['career_wins'] = df.groupby('horse_name')['target_win'].cumsum().shift(1).fillna(0)
    df['career_places'] = df.groupby('horse_name')['target_place'].cumsum().shift(1).fillna(0)
    
    # Career rates
    df['career_win_rate'] = df['career_wins'] / (df['career_starts'] + 1)
    df['career_place_rate'] = df['career_places'] / (df['career_starts'] + 1)
    
    # Recent form (last 3 races)
    df['recent_wins_3'] = df.groupby('horse_name')['target_win'].rolling(3, min_periods=1).sum().shift(1).reset_index(0, drop=True).fillna(0)
    df['recent_places_3'] = df.groupby('horse_name')['target_place'].rolling(3, min_periods=1).sum().shift(1).reset_index(0, drop=True).fillna(0)
    
    # Form score (weighted recent performance)
    df['form_score'] = df['recent_wins_3'] * 3 + df['recent_places_3'] * 1
    
    # Days since last race
    df['days_since_last_race'] = df.groupby('horse_name')['date'].diff().dt.days.fillna(365)
    df['is_fresh'] = (df['days_since_last_race'] > 90).astype(int)
    df['is_quick_backup'] = (df['days_since_last_race'] < 14).astype(int)
    
    logger.info(f"✅ Created historical features")
    return df

def create_jockey_trainer_features(df):
    """Create jockey and trainer performance features"""
    logger.info("👤 Creating jockey/trainer features...")
    
    # Sort by date for historical calculations
    df = df.sort_values(['jockey', 'date']).reset_index(drop=True)
    
    # Jockey statistics
    df['jockey_starts'] = df.groupby('jockey').cumcount()
    df['jockey_wins'] = df.groupby('jockey')['target_win'].cumsum().shift(1).fillna(0)
    df['jockey_win_rate'] = df['jockey_wins'] / (df['jockey_starts'] + 1)
    
    # Trainer statistics
    df = df.sort_values(['trainer', 'date']).reset_index(drop=True)
    df['trainer_starts'] = df.groupby('trainer').cumcount()
    df['trainer_wins'] = df.groupby('trainer')['target_win'].cumsum().shift(1).fillna(0)
    df['trainer_win_rate'] = df['trainer_wins'] / (df['trainer_starts'] + 1)
    
    # Top jockey/trainer indicators (based on activity)
    jockey_counts = df['jockey'].value_counts()
    trainer_counts = df['trainer'].value_counts()
    
    top_jockeys = jockey_counts.head(20).index
    top_trainers = trainer_counts.head(20).index
    
    df['is_top_jockey'] = df['jockey'].isin(top_jockeys).astype(int)
    df['is_top_trainer'] = df['trainer'].isin(top_trainers).astype(int)
    
    logger.info(f"✅ Created jockey/trainer features")
    return df

def create_venue_features(df):
    """Create venue-specific features"""
    logger.info("🏟️ Creating venue features...")
    
    # Venue statistics
    venue_stats = df.groupby('course').agg({
        'target_win': ['count', 'mean'],
        'field_size': 'mean',
        'distance_furlongs': 'mean' if 'distance_furlongs' in df.columns else 'size'
    }).reset_index()
    
    venue_stats.columns = ['course', 'venue_races', 'venue_win_rate', 'venue_avg_field', 'venue_avg_distance']
    
    # Venue categories
    venue_stats['venue_size'] = pd.cut(venue_stats['venue_races'],
                                      bins=[0, 50, 200, 500, float('inf')],
                                      labels=['small', 'medium', 'large', 'major']).cat.codes
    
    # Merge back to main dataframe
    df = df.merge(venue_stats, on='course', how='left')
    
    # Top venues
    top_venues = venue_stats.nlargest(10, 'venue_races')['course']
    df['is_major_venue'] = df['course'].isin(top_venues).astype(int)
    
    logger.info(f"✅ Created venue features")
    return df

def create_advanced_features(df):
    """Create advanced racing features"""
    logger.info("🧠 Creating advanced features...")
    
    # Breeding features (if sire/dam available)
    if 'sire' in df.columns and df['sire'].notna().sum() > 0:
        # Sire statistics
        sire_stats = df.groupby('sire').agg({
            'target_win': ['count', 'mean'],
            'target_place': 'mean'
        }).reset_index()
        sire_stats.columns = ['sire', 'sire_offspring_count', 'sire_win_rate', 'sire_place_rate']
        
        # Only keep sires with sufficient offspring
        sire_stats = sire_stats[sire_stats['sire_offspring_count'] >= 5]
        df = df.merge(sire_stats, on='sire', how='left')
        
        # Top sire indicators
        top_sires = sire_stats.nlargest(20, 'sire_win_rate')['sire']
        df['is_top_sire'] = df['sire'].isin(top_sires).astype(int)
        
        logger.info(f"   🧬 Added sire features")
    
    # Race sequence features
    df = df.sort_values(['date', 'course', 'race_name']).reset_index(drop=True)
    
    # Race quality indicators
    race_groups = df.groupby(['date', 'course', 'race_name'])
    
    # Average field quality (based on career win rates)
    df['field_avg_win_rate'] = race_groups['career_win_rate'].transform('mean')
    df['field_quality_score'] = race_groups['career_win_rate'].transform('sum')
    df['is_quality_race'] = (df['field_avg_win_rate'] > df['field_avg_win_rate'].median()).astype(int)
    
    # Horse's relative quality in field
    df['win_rate_vs_field'] = df['career_win_rate'] - df['field_avg_win_rate']
    df['is_class_horse'] = (df['career_win_rate'] > df['field_avg_win_rate'] * 1.5).astype(int)
    
    # Distance suitability (based on horse's distance performance)
    if 'distance_furlongs' in df.columns:
        horse_distance_stats = df.groupby(['horse_name', 'distance_category']).agg({
            'target_win': ['count', 'mean'],
            'target_place': 'mean'
        }).reset_index()
        horse_distance_stats.columns = ['horse_name', 'distance_category', 'distance_starts', 
                                       'distance_win_rate', 'distance_place_rate']
        
        # Only keep horses with sufficient starts at distance
        horse_distance_stats = horse_distance_stats[horse_distance_stats['distance_starts'] >= 2]
        
        df = df.merge(horse_distance_stats, on=['horse_name', 'distance_category'], how='left')
        df['distance_suited'] = (df['distance_win_rate'] > df['career_win_rate']).astype(int)
        
        logger.info(f"   📏 Added distance suitability features")
    
    # Track condition suitability
    if 'going_encoded' in df.columns:
        horse_going_stats = df.groupby(['horse_name', 'going_encoded']).agg({
            'target_win': ['count', 'mean'],
            'target_place': 'mean'
        }).reset_index()
        horse_going_stats.columns = ['horse_name', 'going_encoded', 'going_starts', 
                                    'going_win_rate', 'going_place_rate']
        
        horse_going_stats = horse_going_stats[horse_going_stats['going_starts'] >= 2]
        
        df = df.merge(horse_going_stats, on=['horse_name', 'going_encoded'], how='left')
        df['going_suited'] = (df['going_win_rate'] > df['career_win_rate']).astype(int)
        
        logger.info(f"   🌧️ Added track condition suitability features")
    
    # Venue suitability
    horse_venue_stats = df.groupby(['horse_name', 'course']).agg({
        'target_win': ['count', 'mean'],
        'target_place': 'mean'
    }).reset_index()
    horse_venue_stats.columns = ['horse_name', 'course', 'horse_venue_starts', 'horse_venue_win_rate', 'horse_venue_place_rate']
    
    horse_venue_stats = horse_venue_stats[horse_venue_stats['horse_venue_starts'] >= 2]
    
    df = df.merge(horse_venue_stats, on=['horse_name', 'course'], how='left')
    df['horse_venue_suited'] = (df['horse_venue_win_rate'] > df['career_win_rate']).astype(int)
    
    # Jockey-Trainer combination features
    jt_combo_stats = df.groupby(['jockey', 'trainer']).agg({
        'target_win': ['count', 'mean'],
        'target_place': 'mean'
    }).reset_index()
    jt_combo_stats.columns = ['jockey', 'trainer', 'jt_combo_starts', 'jt_combo_win_rate', 'jt_combo_place_rate']
    
    jt_combo_stats = jt_combo_stats[jt_combo_stats['jt_combo_starts'] >= 3]
    
    df = df.merge(jt_combo_stats, on=['jockey', 'trainer'], how='left')
    df['is_jt_combo'] = (df['jt_combo_starts'] >= 3).astype(int)
    
    # Seasonal performance patterns
    horse_seasonal_stats = df.groupby(['horse_name', 'quarter']).agg({
        'target_win': ['count', 'mean'],
        'target_place': 'mean'
    }).reset_index()
    horse_seasonal_stats.columns = ['horse_name', 'quarter', 'seasonal_starts', 'seasonal_win_rate', 'seasonal_place_rate']
    
    horse_seasonal_stats = horse_seasonal_stats[horse_seasonal_stats['seasonal_starts'] >= 2]
    
    df = df.merge(horse_seasonal_stats, on=['horse_name', 'quarter'], how='left')
    df['seasonal_suited'] = (df['seasonal_win_rate'] > df['career_win_rate']).astype(int)
    
    # Race pattern features
    df['race_number'] = df.groupby(['date', 'course']).cumcount() + 1
    df['is_early_race'] = (df['race_number'] <= 3).astype(int)
    df['is_late_race'] = (df['race_number'] >= 7).astype(int)
    
    # Weight-for-age adjustments (simplified)
    if 'age' in df.columns and 'weight_carried' in df.columns:
        # Younger horses get weight allowances
        df['weight_adjusted'] = df['weight_carried'] - (5 - df['age'].clip(upper=5)) * 2
        df['weight_burden_score'] = df['weight_carried'] / df['age']
    
    # Market movements (if multiple odds available - placeholder for future)
    if 'odds_decimal' in df.columns:
        # Firmness of market position
        df['market_confidence'] = 1 / (df['odds_decimal'] * df['field_size'])
        df['value_rating'] = df['implied_probability'] * df['career_win_rate']
    
    logger.info(f"✅ Created advanced features")
    return df

def select_modeling_features(df):
    """Select and prepare final features for modeling"""
    logger.info("🎯 Selecting modeling features...")
    
    # Define feature categories
    target_cols = ['target_win', 'target_place', 'target_show']
    
    id_cols = ['date', 'course', 'race_name', 'horse_name', 'jockey', 'trainer', 'finishing_position']
    
    feature_cols = [
        # Time features
        'year', 'month', 'day_of_week', 'quarter', 'is_weekend',
        'is_summer', 'is_autumn', 'is_winter', 'is_spring', 'is_carnival_season',
        
        # Race features  
        'field_size', 'field_size_log', 'field_size_category',
        
        # Horse features
        'age', 'weight_carried',
        
        # Historical features
        'career_starts', 'career_win_rate', 'career_place_rate',
        'recent_wins_3', 'recent_places_3', 'form_score',
        'days_since_last_race', 'is_fresh', 'is_quick_backup',
        
        # Jockey/Trainer features
        'jockey_win_rate', 'trainer_win_rate', 'is_top_jockey', 'is_top_trainer',
        
        # Venue features
        'venue_win_rate', 'venue_avg_field', 'venue_size', 'is_major_venue'
    ]
    
    # Add optional features if they exist
    optional_features = [
        'distance_furlongs', 'distance_log', 'distance_category',
        'prize_money_log', 'prize_money_category',
        'class_rating_scaled', 'is_high_class',
        'going_encoded', 'is_firm_track', 'is_soft_track',
        'age_category', 'is_prime_age', 'weight_advantage', 'is_topweight',
        'sex_encoded', 'is_male', 'is_female',
        'odds_decimal', 'odds_log', 'implied_probability', 'odds_category',
        'is_favourite', 'is_longshot', 'odds_rank', 'odds_rank_pct',
        'is_race_favourite', 'is_top3_choice', 'market_share',
        
        # Advanced features
        'sire_offspring_count', 'sire_win_rate', 'sire_place_rate', 'is_top_sire',
        'field_avg_win_rate', 'field_quality_score', 'is_quality_race',
        'win_rate_vs_field', 'is_class_horse',
        'distance_starts', 'distance_win_rate', 'distance_place_rate', 'distance_suited',
        'going_starts', 'going_win_rate', 'going_place_rate', 'going_suited',
        'horse_venue_starts', 'horse_venue_win_rate', 'horse_venue_place_rate', 'horse_venue_suited',
        'jt_combo_starts', 'jt_combo_win_rate', 'jt_combo_place_rate', 'is_jt_combo',
        'seasonal_starts', 'seasonal_win_rate', 'seasonal_place_rate', 'seasonal_suited',
        'race_number', 'is_early_race', 'is_late_race',
        'weight_adjusted', 'weight_burden_score',
        'market_confidence', 'value_rating'
    ]
    
    for feat in optional_features:
        if feat in df.columns:
            feature_cols.append(feat)
    
    # Select final columns
    final_cols = id_cols + target_cols + feature_cols
    available_cols = [col for col in final_cols if col in df.columns]
    
    df_final = df[available_cols].copy()
    
    # Fill missing values
    numeric_cols = df_final.select_dtypes(include=[np.number]).columns
    df_final[numeric_cols] = df_final[numeric_cols].fillna(0)
    
    categorical_cols = df_final.select_dtypes(include=['object']).columns
    df_final[categorical_cols] = df_final[categorical_cols].fillna('Unknown')
    
    logger.info(f"✅ Selected {len(feature_cols)} features for modeling")
    logger.info(f"📊 Final dataset: {len(df_final):,} rows × {len(df_final.columns)} columns")
    
    return df_final

def feature_engineering_pipeline():
    """Main feature engineering pipeline"""
    logger.info("🚀 Starting RPScrape-only feature engineering...")
    
    # Load data
    df = load_rpscrape_data()
    
    if len(df) == 0:
        logger.error("❌ No data loaded - exiting")
        return
    
    logger.info(f"📊 Starting with {len(df):,} records")
    
    # Apply feature engineering steps
    df = create_target_variables(df)
    df = create_time_features(df)
    df = create_race_features(df)
    df = create_horse_features(df)
    df = create_odds_features(df)
    df = create_historical_features(df)
    df = create_jockey_trainer_features(df)
    df = create_venue_features(df)
    df = create_advanced_features(df)
    
    # Select final features
    df_final = select_modeling_features(df)
    
    # Save results
    output_file = 'rpscrape_features.parquet'
    df_final.to_parquet(output_file, index=False)
    
    logger.info(f"💾 Saved to {output_file}")
    
    # Show summary
    logger.info("\n🎉 === FEATURE ENGINEERING COMPLETE ===")
    logger.info(f"📊 Final dataset: {len(df_final):,} records")
    logger.info(f"🎯 Win rate: {df_final['target_win'].mean():.3f}")
    logger.info(f"🥉 Place rate: {df_final['target_place'].mean():.3f}")
    logger.info(f"📈 Show rate: {df_final['target_show'].mean():.3f}")
    
    # Show feature summary
    feature_cols = [col for col in df_final.columns if col not in 
                   ['date', 'course', 'race_name', 'horse_name', 'jockey', 'trainer', 'finishing_position',
                    'target_win', 'target_place', 'target_show']]
    logger.info(f"🛠️ Created {len(feature_cols)} features")
    
    if DEBUG_MODE:
        logger.info(f"📋 Features: {feature_cols}")
    
    return df_final

if __name__ == "__main__":
    feature_engineering_pipeline()
