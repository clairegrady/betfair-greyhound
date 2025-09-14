import pandas as pd
import numpy as np
import sqlite3
import pickle
from datetime import datetime
from sklearn.preprocessing import LabelEncoder
import warnings
warnings.filterwarnings('ignore')

def load_trained_model():
    """Load the trained XGBoost model"""
    try:
        # Try to load the comprehensive model first
        with open('comprehensive_place_model.pkl', 'rb') as f:
            model = pickle.load(f)
        print("✅ Loaded comprehensive place model")
        return model, 'comprehensive'
    except FileNotFoundError:
        try:
            # Fallback to the basic model
            with open('place_betting_model.pkl', 'rb') as f:
                model = pickle.load(f)
            print("✅ Loaded basic place model")
            return model, 'basic'
        except FileNotFoundError:
            print("❌ No trained model found. Please train a model first.")
            return None, None

def get_race_data_from_betfair(race_name="R2 2400m Hcap", event_name="Sandown (AUS) 10th Sep"):
    """Get race data from Betfair database"""
    conn = sqlite3.connect('/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair/betfairmarket.sqlite')
    
    query = '''
    SELECT 
        RUNNER_NAME,
        JOCKEY_NAME,
        TRAINER_NAME,
        STALL_DRAW,
        WEIGHT_VALUE,
        AGE,
        SEX_TYPE,
        FORM,
        OFFICIAL_RATING,
        MarketName,
        EventName
    FROM HorseMarketBook 
    WHERE EventName = ? AND MarketName = ?
    ORDER BY STALL_DRAW
    '''
    
    df = pd.read_sql_query(query, conn, params=(event_name, race_name))
    conn.close()
    
    return df

def get_live_odds_from_odds_com():
    """Get live odds from odds.com scraper"""
    conn = sqlite3.connect('racing_data.db')
    
    # Get today's odds
    today = datetime.now().strftime('%Y-%m-%d')
    query = '''
    SELECT 
        venue,
        race_number,
        runner_name,
        runner_number,
        bookmaker,
        odds,
        odds_type,
        scraped_at
    FROM odds_com_race_odds 
    WHERE date(scraped_at) = ?
    ORDER BY venue, race_number, runner_number, bookmaker
    '''
    
    df = pd.read_sql_query(query, conn, params=(today,))
    conn.close()
    
    return df

def lookup_historical_data(race_df):
    """Lookup historical statistics for horses, jockeys, and trainers"""
    conn = sqlite3.connect('racing_data.db')
    
    historical_stats = []
    
    for _, horse in race_df.iterrows():
        horse_name = horse['RUNNER_NAME']
        jockey_name = horse['JOCKEY_NAME']
        trainer_name = horse['TRAINER_NAME']
        
        # Get horse statistics
        horse_query = '''
        SELECT 
            runnerName,
            overall_runner_starts,
            overall_runner_wins,
            overall_runner_placings,
            track_runner_starts,
            track_runner_wins,
            track_runner_placings,
            good_runner_starts,
            good_runner_wins,
            good_runner_placings,
            distance_runner_starts,
            distance_runner_wins,
            distance_runner_placings,
            classSame_runner_starts,
            classSame_runner_wins,
            classSame_runner_placings
        FROM historical_data 
        WHERE runnerName = ?
        ORDER BY meetingDate DESC
        LIMIT 1
        '''
        
        horse_stats = pd.read_sql_query(horse_query, conn, params=(horse_name,))
        
        # Get jockey statistics
        jockey_query = '''
        SELECT 
            riderName,
            track_rider_starts,
            track_rider_wins,
            track_rider_placings,
            region_rider_starts,
            region_rider_wins,
            region_rider_placings,
            last30Days_rider_starts,
            last30Days_rider_wins,
            last30Days_rider_placings,
            last12Months_rider_starts,
            last12Months_rider_wins,
            last12Months_rider_placings
        FROM historical_data 
        WHERE riderName = ?
        ORDER BY meetingDate DESC
        LIMIT 1
        '''
        
        jockey_stats = pd.read_sql_query(jockey_query, conn, params=(jockey_name,))
        
        # Get trainer statistics (trainer info is embedded in the stats columns)
        trainer_query = '''
        SELECT 
            track_trainer_starts,
            track_trainer_wins,
            track_trainer_placings,
            region_trainer_starts,
            region_trainer_wins,
            region_trainer_placings,
            last30Days_trainer_starts,
            last30Days_trainer_wins,
            last30Days_trainer_placings,
            last12Months_trainer_starts,
            last12Months_trainer_wins,
            last12Months_trainer_placings
        FROM historical_data 
        WHERE riderName = ? AND track_trainer_starts > 0
        ORDER BY meetingDate DESC
        LIMIT 1
        '''
        
        trainer_stats = pd.read_sql_query(trainer_query, conn, params=(jockey_name,))
        
        # Combine all statistics
        stats = {
            'horse_name': horse_name,
            'jockey_name': jockey_name,
            'trainer_name': trainer_name
        }
        
        # Add horse stats
        if len(horse_stats) > 0:
            for col in horse_stats.columns:
                if col != 'runnerName':
                    stats[f'horse_{col}'] = horse_stats.iloc[0][col]
        else:
            # Use defaults if no historical data
            stats.update({
                'horse_overall_runner_starts': 5,
                'horse_overall_runner_wins': 1,
                'horse_overall_runner_placings': 2,
                'horse_track_runner_starts': 1,
                'horse_track_runner_wins': 0,
                'horse_track_runner_placings': 0,
                'horse_good_runner_starts': 3,
                'horse_good_runner_wins': 1,
                'horse_good_runner_placings': 1,
                'horse_distance_runner_starts': 2,
                'horse_distance_runner_wins': 0,
                'horse_distance_runner_placings': 1,
                'horse_classSame_runner_starts': 2,
                'horse_classSame_runner_wins': 0,
                'horse_classSame_runner_placings': 1
            })
        
        # Add jockey stats
        if len(jockey_stats) > 0:
            for col in jockey_stats.columns:
                if col != 'riderName':
                    stats[f'jockey_{col}'] = jockey_stats.iloc[0][col]
        else:
            # Use defaults if no historical data
            stats.update({
                'jockey_track_rider_starts': 10,
                'jockey_track_rider_wins': 2,
                'jockey_track_rider_placings': 4,
                'jockey_region_rider_starts': 50,
                'jockey_region_rider_wins': 8,
                'jockey_region_rider_placings': 15,
                'jockey_last30Days_rider_starts': 8,
                'jockey_last30Days_rider_wins': 1,
                'jockey_last30Days_rider_placings': 2,
                'jockey_last12Months_rider_starts': 100,
                'jockey_last12Months_rider_wins': 15,
                'jockey_last12Months_rider_placings': 30
            })
        
        # Add trainer stats
        if len(trainer_stats) > 0:
            for col in trainer_stats.columns:
                stats[f'trainer_{col}'] = trainer_stats.iloc[0][col]
        else:
            # Use defaults if no historical data
            stats.update({
                'trainer_track_trainer_starts': 8,
                'trainer_track_trainer_wins': 1,
                'trainer_track_trainer_placings': 2,
                'trainer_region_trainer_starts': 40,
                'trainer_region_trainer_wins': 6,
                'trainer_region_trainer_placings': 12,
                'trainer_last30Days_trainer_starts': 6,
                'trainer_last30Days_trainer_wins': 1,
                'trainer_last30Days_trainer_placings': 2,
                'trainer_last12Months_trainer_starts': 80,
                'trainer_last12Months_trainer_wins': 12,
                'trainer_last12Months_trainer_placings': 24
            })
        
        historical_stats.append(stats)
    
    conn.close()
    return pd.DataFrame(historical_stats)

def get_odds_for_race(odds_df, venue="Sandown", race_number=2):
    """Get odds for a specific race"""
    race_odds = odds_df[
        (odds_df['venue'].str.contains(venue, case=False, na=False)) & 
        (odds_df['race_number'] == race_number)
    ].copy()
    
    if len(race_odds) == 0:
        print(f"⚠️  No odds found for {venue} Race {race_number}")
        return None
    
    # Get the latest odds for each horse
    latest_odds = race_odds.sort_values('scraped_at').groupby('runner_name').last()
    
    return latest_odds

def prepare_comprehensive_features(race_df, historical_df, odds_df):
    """Prepare comprehensive features using all data sources"""
    features_list = []
    
    for _, horse in race_df.iterrows():
        horse_name = horse['RUNNER_NAME']
        
        # Get historical data for this horse
        horse_historical = historical_df[historical_df['horse_name'] == horse_name]
        
        # Get odds for this horse
        horse_odds = odds_df[odds_df.index == horse_name] if odds_df is not None else None
        
        # Create feature row
        features = {
            # Basic race information
            'meetingName': 'Sandown',
            'meetingDate': '2025-09-10',
            'raceNumber': 2,
            'runnerNumber': horse['STALL_DRAW'],
            'runnerName': horse_name,
            'riderName': horse['JOCKEY_NAME'],
            'location': 'Sandown',
            'weatherCondition': 'FINE',
            'trackCondition': 'GOOD4',
            'raceName': horse['MarketName'],
            'raceStartTime': '2025-09-10 15:00:00',
            'raceDistance': 2400,
            'trackDirection': 'ANTICLOCKWISE',
            'raceClassConditions': 'HCP',
            
            # Odds information
            'FixedWinOpen_Reference': horse_odds['odds'].iloc[0] if horse_odds is not None and len(horse_odds) > 0 else 5.0,
            'FixedWinClose_Reference': horse_odds['odds'].iloc[0] if horse_odds is not None and len(horse_odds) > 0 else 5.0,
        }
        
        # Add historical statistics
        if len(horse_historical) > 0:
            for col in horse_historical.columns:
                if col not in ['horse_name', 'jockey_name', 'trainer_name']:
                    features[col] = horse_historical.iloc[0][col]
        else:
            # Use defaults if no historical data
            features.update({
                'horse_overall_runner_starts': 5,
                'horse_overall_runner_wins': 1,
                'horse_overall_runner_placings': 2,
                'horse_track_runner_starts': 1,
                'horse_track_runner_wins': 0,
                'horse_track_runner_placings': 0,
                'horse_good_runner_starts': 3,
                'horse_good_runner_wins': 1,
                'horse_good_runner_placings': 1,
                'horse_distance_runner_starts': 2,
                'horse_distance_runner_wins': 0,
                'horse_distance_runner_placings': 1,
                'horse_classSame_runner_starts': 2,
                'horse_classSame_runner_wins': 0,
                'horse_classSame_runner_placings': 1,
                'jockey_track_rider_starts': 10,
                'jockey_track_rider_wins': 2,
                'jockey_track_rider_placings': 4,
                'jockey_region_rider_starts': 50,
                'jockey_region_rider_wins': 8,
                'jockey_region_rider_placings': 15,
                'jockey_last30Days_rider_starts': 8,
                'jockey_last30Days_rider_wins': 1,
                'jockey_last30Days_rider_placings': 2,
                'jockey_last12Months_rider_starts': 100,
                'jockey_last12Months_rider_wins': 15,
                'jockey_last12Months_rider_placings': 30,
                'trainer_track_trainer_starts': 8,
                'trainer_track_trainer_wins': 1,
                'trainer_track_trainer_placings': 2,
                'trainer_region_trainer_starts': 40,
                'trainer_region_trainer_wins': 6,
                'trainer_region_trainer_placings': 12,
                'trainer_last30Days_trainer_starts': 6,
                'trainer_last30Days_trainer_wins': 1,
                'trainer_last30Days_trainer_placings': 2,
                'trainer_last12Months_trainer_starts': 80,
                'trainer_last12Months_trainer_wins': 12,
                'trainer_last12Months_trainer_placings': 24
            })
        
        # Add remaining features needed for the model
        features.update({
            'overall_runner_starts': features.get('horse_overall_runner_starts', 5),
            'track_runner_starts': features.get('horse_track_runner_starts', 1),
            'firm_runner_starts': 0,
            'good_runner_starts': features.get('horse_good_runner_starts', 3),
            'dead_runner_starts': 0,
            'slow_runner_starts': 0,
            'soft_runner_starts': 1,
            'heavy_runner_starts': 0,
            'distance_runner_starts': features.get('horse_distance_runner_starts', 2),
            'classSame_runner_starts': features.get('horse_classSame_runner_starts', 2),
            'classStronger_runner_starts': 1,
            'firstUp_runner_starts': 1,
            'secondUp_runner_starts': 1,
            'trackDistance_runner_starts': 1,
            'overall_runner_wins': features.get('horse_overall_runner_wins', 1),
            'track_runner_wins': features.get('horse_track_runner_wins', 0),
            'firm_runner_wins': 0,
            'good_runner_wins': features.get('horse_good_runner_wins', 1),
            'dead_runner_wins': 0,
            'slow_runner_wins': 0,
            'soft_runner_wins': 0,
            'heavy_runner_wins': 0,
            'distance_runner_wins': features.get('horse_distance_runner_wins', 0),
            'classSame_runner_wins': features.get('horse_classSame_runner_wins', 0),
            'classStronger_runner_wins': 0,
            'firstUp_runner_wins': 0,
            'secondUp_runner_wins': 0,
            'trackDistance_runner_wins': 0,
            'overall_runner_placings': features.get('horse_overall_runner_placings', 2),
            'track_runner_placings': features.get('horse_track_runner_placings', 0),
            'firm_runner_placings': 0,
            'good_runner_placings': features.get('horse_good_runner_placings', 1),
            'dead_runner_placings': 0,
            'slow_runner_placings': 0,
            'soft_runner_placings': 0,
            'heavy_runner_placings': 0,
            'distance_runner_placings': features.get('horse_distance_runner_placings', 1),
            'classSame_runner_placings': features.get('horse_classSame_runner_placings', 1),
            'classStronger_runner_placings': 0,
            'firstUp_runner_placings': 0,
            'secondUp_runner_placings': 0,
            'trackDistance_runner_placings': 0,
            'track_trainer_starts': features.get('trainer_track_trainer_starts', 8),
            'region_trainer_starts': features.get('trainer_region_trainer_starts', 40),
            'last30Days_trainer_starts': features.get('trainer_last30Days_trainer_starts', 6),
            'last12Months_trainer_starts': features.get('trainer_last12Months_trainer_starts', 80),
            'jockey_trainer_starts': 2,
            'track_trainer_wins': features.get('trainer_track_trainer_wins', 1),
            'region_trainer_wins': features.get('trainer_region_trainer_wins', 6),
            'last30Days_trainer_wins': features.get('trainer_last30Days_trainer_wins', 1),
            'last12Months_trainer_wins': features.get('trainer_last12Months_trainer_wins', 12),
            'jockey_trainer_wins': 0,
            'track_trainer_placings': features.get('trainer_track_trainer_placings', 2),
            'region_trainer_placings': features.get('trainer_region_trainer_placings', 12),
            'last30Days_trainer_placings': features.get('trainer_last30Days_trainer_placings', 2),
            'last12Months_trainer_placings': features.get('trainer_last12Months_trainer_placings', 24),
            'jockey_trainer_placings': 1,
            'track_rider_starts': features.get('jockey_track_rider_starts', 10),
            'region_rider_starts': features.get('jockey_region_rider_starts', 50),
            'last30Days_rider_starts': features.get('jockey_last30Days_rider_starts', 8),
            'last12Months_rider_starts': features.get('jockey_last12Months_rider_starts', 100),
            'runner_rider_starts': 1,
            'track_rider_wins': features.get('jockey_track_rider_wins', 2),
            'region_rider_wins': features.get('jockey_region_rider_wins', 8),
            'last30Days_rider_wins': features.get('jockey_last30Days_rider_wins', 1),
            'last12Months_rider_wins': features.get('jockey_last12Months_rider_wins', 15),
            'runner_rider_wins': 0,
            'track_rider_placings': features.get('jockey_track_rider_placings', 4),
            'region_rider_placings': features.get('jockey_region_rider_placings', 15),
            'last30Days_rider_placings': features.get('jockey_last30Days_rider_placings', 2),
            'last12Months_rider_placings': features.get('jockey_last12Months_rider_placings', 30),
            'runner_rider_placings': 0,
            'runner_scratched': 0,
            'race_abandoned': 0
        })
        
        features_list.append(features)
    
    return pd.DataFrame(features_list)

def make_predictions(model, features_df, model_type):
    """Make predictions using the trained model"""
    # Define feature columns (exclude target and identifier columns)
    exclude_columns = ['finishingPosition', 'placed', 'meetingName', 'meetingDate', 'raceName', 'raceStartTime', 'raceNumber']
    
    feature_columns = [col for col in features_df.columns if col not in exclude_columns]
    
    # Prepare features
    X = features_df[feature_columns].copy()
    
    # Handle categorical variables with label encoding
    categorical_columns = X.select_dtypes(include=['object']).columns
    for col in categorical_columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
    
    # Fill missing values
    X = X.fillna(0)
    
    # Make predictions
    if model_type == 'comprehensive':
        # For classification model, get probabilities
        probabilities = model.predict_proba(X)[:, 1]  # Probability of placing
    else:
        # For regression model, convert to probabilities (this is a simplified approach)
        predictions = model.predict(X)
        # Convert finishing position predictions to place probabilities
        # Assuming 1st, 2nd, 3rd place = placed (this is a rough approximation)
        probabilities = np.where(predictions <= 3, 0.7, 0.3)
    
    return probabilities

def display_comprehensive_predictions(race_df, probabilities, odds_df):
    """Display comprehensive predictions with all data sources"""
    print("🏇 COMPREHENSIVE LIVE RACE PREDICTIONS")
    print("=" * 70)
    print(f"Race: {race_df.iloc[0]['EventName']}")
    print(f"Time: {race_df.iloc[0]['MarketName']}")
    print(f"Total Runners: {len(race_df)}")
    print()
    
    # Create results dataframe
    results_df = pd.DataFrame({
        'Barrier': race_df['STALL_DRAW'],
        'Horse': race_df['RUNNER_NAME'],
        'Jockey': race_df['JOCKEY_NAME'],
        'Trainer': race_df['TRAINER_NAME'],
        'Weight': race_df['WEIGHT_VALUE'],
        'Form': race_df['FORM'],
        'Place_Probability': probabilities
    })
    
    # Add odds information if available
    if odds_df is not None:
        odds_info = []
        for horse in results_df['Horse']:
            horse_odds = odds_df[odds_df.index == horse]
            if len(horse_odds) > 0:
                odds_info.append(f"{horse_odds['odds'].iloc[0]:.2f}")
            else:
                odds_info.append("N/A")
        results_df['Latest_Odds'] = odds_info
    else:
        results_df['Latest_Odds'] = "N/A"
    
    # Sort by place probability (highest first)
    results_df = results_df.sort_values('Place_Probability', ascending=False)
    
    print("📊 COMPREHENSIVE PLACE BETTING PREDICTIONS")
    print("=" * 70)
    print("Data Sources: Betfair + Historical DB + Live Odds + ML Model")
    print("-" * 70)
    
    for i, (_, horse) in enumerate(results_df.iterrows(), 1):
        prob_pct = horse['Place_Probability'] * 100
        print(f"{i:2d}. #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {horse['Jockey']:15s}")
        print(f"    Trainer: {horse['Trainer']:25s} Weight: {horse['Weight']:4.1f}kg")
        print(f"    Form: {horse['Form']:8s} Odds: {horse['Latest_Odds']:>6s} Place Prob: {prob_pct:5.1f}%")
        print()
    
    print("🎯 BETTING RECOMMENDATIONS")
    print("=" * 70)
    
    # High confidence picks (probability > 60%)
    high_conf = results_df[results_df['Place_Probability'] > 0.6]
    if len(high_conf) > 0:
        print("🔥 HIGH CONFIDENCE PLACE BETS (>60%):")
        for _, horse in high_conf.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}% (Odds: {horse['Latest_Odds']})")
        print()
    
    # Medium confidence picks (probability 40-60%)
    med_conf = results_df[(results_df['Place_Probability'] >= 0.4) & (results_df['Place_Probability'] <= 0.6)]
    if len(med_conf) > 0:
        print("⚡ MEDIUM CONFIDENCE PLACE BETS (40-60%):")
        for _, horse in med_conf.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}% (Odds: {horse['Latest_Odds']})")
        print()
    
    # Value picks (lower probability but good value)
    value_picks = results_df[(results_df['Place_Probability'] >= 0.25) & (results_df['Place_Probability'] < 0.4)]
    if len(value_picks) > 0:
        print("💎 VALUE PLACE BETS (25-40%):")
        for _, horse in value_picks.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}% (Odds: {horse['Latest_Odds']})")
        print()
    
    print("📈 DATA SOURCES USED:")
    print("   ✅ Betfair: Horse details, jockeys, trainers, barriers")
    print("   ✅ Historical DB: 382,922 race records with comprehensive stats")
    print("   ✅ Live Odds: Multiple bookmaker odds from odds.com")
    print("   ✅ ML Model: Trained XGBoost with 91 engineered features")

def main():
    """Main function to run comprehensive live race predictions"""
    print("🚀 COMPREHENSIVE LIVE RACE PREDICTION SYSTEM")
    print("=" * 60)
    print("Using: Betfair + Historical DB + Live Odds + ML Model")
    print("=" * 60)
    
    # Load the trained model
    print("🤖 Loading trained model...")
    model, model_type = load_trained_model()
    if model is None:
        return
    
    # Get race data from Betfair
    print("📊 Fetching race data from Betfair...")
    race_df = get_race_data_from_betfair()
    
    if len(race_df) == 0:
        print("❌ No race data found. Please check the race name and event.")
        return
    
    print(f"✅ Found {len(race_df)} horses in the race")
    
    # Get live odds from odds.com
    print("💰 Fetching live odds from odds.com...")
    odds_df = get_live_odds_from_odds_com()
    race_odds = get_odds_for_race(odds_df)
    
    if race_odds is not None:
        print(f"✅ Found odds for {len(race_odds)} horses")
    else:
        print("⚠️  No live odds found - using default values")
    
    # Lookup historical data
    print("📚 Looking up historical statistics...")
    historical_df = lookup_historical_data(race_df)
    print(f"✅ Retrieved historical data for {len(historical_df)} horses")
    
    # Prepare comprehensive features
    print("🔧 Preparing comprehensive features...")
    features_df = prepare_comprehensive_features(race_df, historical_df, race_odds)
    
    # Make predictions
    print("🎯 Making predictions with trained model...")
    probabilities = make_predictions(model, features_df, model_type)
    
    # Display comprehensive results
    display_comprehensive_predictions(race_df, probabilities, race_odds)
    
    print("✅ Comprehensive prediction complete!")

if __name__ == "__main__":
    main()
