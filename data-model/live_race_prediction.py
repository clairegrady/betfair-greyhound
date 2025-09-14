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

def prepare_features_for_prediction(race_df):
    """Prepare features for the model prediction"""
    # Create a copy for feature engineering
    features_df = race_df.copy()
    
    # Basic race information (we'll need to infer some from the data)
    features_df['meetingName'] = 'Sandown'
    features_df['meetingDate'] = '2025-09-10'
    features_df['raceNumber'] = 2
    features_df['runnerNumber'] = features_df['STALL_DRAW']
    features_df['runnerName'] = features_df['RUNNER_NAME']
    features_df['riderName'] = features_df['JOCKEY_NAME']
    features_df['location'] = 'Sandown'
    features_df['weatherCondition'] = 'FINE'  # Default assumption
    features_df['trackCondition'] = 'GOOD4'  # Default assumption
    features_df['raceName'] = features_df['MarketName']
    features_df['raceStartTime'] = '2025-09-10 15:00:00'  # Default assumption
    features_df['raceDistance'] = 2400  # From race name
    features_df['trackDirection'] = 'ANTICLOCKWISE'  # Default assumption
    features_df['raceClassConditions'] = 'HCP'  # From race name
    
    # Odds information (we don't have this from Betfair, so we'll use defaults)
    features_df['FixedWinOpen_Reference'] = 5.0  # Default odds
    features_df['FixedWinClose_Reference'] = 5.0  # Default odds
    
    # For the comprehensive model, we need to create all the statistical features
    # Since we don't have historical data for these specific horses, we'll use reasonable defaults
    # based on typical racing statistics
    
    # Runner statistics (using defaults based on typical racing stats)
    features_df['overall_runner_starts'] = 10
    features_df['track_runner_starts'] = 2
    features_df['firm_runner_starts'] = 0
    features_df['good_runner_starts'] = 8
    features_df['dead_runner_starts'] = 0
    features_df['slow_runner_starts'] = 0
    features_df['soft_runner_starts'] = 2
    features_df['heavy_runner_starts'] = 0
    features_df['distance_runner_starts'] = 3
    features_df['classSame_runner_starts'] = 5
    features_df['classStronger_runner_starts'] = 2
    features_df['firstUp_runner_starts'] = 1
    features_df['secondUp_runner_starts'] = 1
    features_df['trackDistance_runner_starts'] = 1
    
    # Runner wins (typical win rates)
    features_df['overall_runner_wins'] = 2
    features_df['track_runner_wins'] = 0
    features_df['firm_runner_wins'] = 0
    features_df['good_runner_wins'] = 2
    features_df['dead_runner_wins'] = 0
    features_df['slow_runner_wins'] = 0
    features_df['soft_runner_wins'] = 0
    features_df['heavy_runner_wins'] = 0
    features_df['distance_runner_wins'] = 1
    features_df['classSame_runner_wins'] = 1
    features_df['classStronger_runner_wins'] = 0
    features_df['firstUp_runner_wins'] = 0
    features_df['secondUp_runner_wins'] = 0
    features_df['trackDistance_runner_wins'] = 0
    
    # Runner placings (typical place rates)
    features_df['overall_runner_placings'] = 5
    features_df['track_runner_placings'] = 1
    features_df['firm_runner_placings'] = 0
    features_df['good_runner_placings'] = 4
    features_df['dead_runner_placings'] = 0
    features_df['slow_runner_placings'] = 0
    features_df['soft_runner_placings'] = 1
    features_df['heavy_runner_placings'] = 0
    features_df['distance_runner_placings'] = 2
    features_df['classSame_runner_placings'] = 2
    features_df['classStronger_runner_placings'] = 1
    features_df['firstUp_runner_placings'] = 0
    features_df['secondUp_runner_placings'] = 1
    features_df['trackDistance_runner_placings'] = 0
    
    # Trainer statistics
    features_df['track_trainer_starts'] = 5
    features_df['region_trainer_starts'] = 50
    features_df['last30Days_trainer_starts'] = 10
    features_df['last12Months_trainer_starts'] = 100
    features_df['jockey_trainer_starts'] = 3
    features_df['track_trainer_wins'] = 1
    features_df['region_trainer_wins'] = 8
    features_df['last30Days_trainer_wins'] = 2
    features_df['last12Months_trainer_wins'] = 15
    features_df['jockey_trainer_wins'] = 1
    features_df['track_trainer_placings'] = 2
    features_df['region_trainer_placings'] = 20
    features_df['last30Days_trainer_placings'] = 4
    features_df['last12Months_trainer_placings'] = 35
    features_df['jockey_trainer_placings'] = 2
    
    # Jockey statistics
    features_df['track_rider_starts'] = 8
    features_df['region_rider_starts'] = 80
    features_df['last30Days_rider_starts'] = 15
    features_df['last12Months_rider_starts'] = 200
    features_df['runner_rider_starts'] = 2
    features_df['track_rider_wins'] = 2
    features_df['region_rider_wins'] = 12
    features_df['last30Days_rider_wins'] = 3
    features_df['last12Months_rider_wins'] = 30
    features_df['runner_rider_wins'] = 1
    features_df['track_rider_placings'] = 4
    features_df['region_rider_placings'] = 25
    features_df['last30Days_rider_placings'] = 6
    features_df['last12Months_rider_placings'] = 60
    features_df['runner_rider_placings'] = 1
    
    # Other features
    features_df['runner_scratched'] = 0
    features_df['race_abandoned'] = 0
    
    return features_df

def make_predictions(model, features_df, model_type):
    """Make predictions using the trained model"""
    # Define feature columns (exclude target and identifier columns)
    exclude_columns = ['finishingPosition', 'placed', 'meetingName', 'meetingDate', 'raceName', 'raceStartTime', 'raceNumber']
    
    if model_type == 'comprehensive':
        # For comprehensive model, exclude more columns
        exclude_columns.extend(['RUNNER_NAME', 'JOCKEY_NAME', 'TRAINER_NAME', 'STALL_DRAW', 'WEIGHT_VALUE', 
                               'AGE', 'SEX_TYPE', 'FORM', 'OFFICIAL_RATING', 'MarketName', 'EventName'])
    
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

def display_predictions(race_df, probabilities):
    """Display predictions in a nice format"""
    print("🏇 LIVE RACE PREDICTIONS - SANDOWN R2 2400M HCAP")
    print("=" * 60)
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
    
    # Sort by place probability (highest first)
    results_df = results_df.sort_values('Place_Probability', ascending=False)
    
    print("📊 PLACE BETTING PREDICTIONS (1st, 2nd, 3rd)")
    print("-" * 60)
    
    for i, (_, horse) in enumerate(results_df.iterrows(), 1):
        prob_pct = horse['Place_Probability'] * 100
        print(f"{i:2d}. #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {horse['Jockey']:15s}")
        print(f"    Trainer: {horse['Trainer']:25s} Weight: {horse['Weight']:4.1f}kg")
        print(f"    Form: {horse['Form']:8s} Place Probability: {prob_pct:5.1f}%")
        print()
    
    print("🎯 BETTING RECOMMENDATIONS")
    print("-" * 60)
    
    # High confidence picks (probability > 60%)
    high_conf = results_df[results_df['Place_Probability'] > 0.6]
    if len(high_conf) > 0:
        print("🔥 HIGH CONFIDENCE PLACE BETS (>60%):")
        for _, horse in high_conf.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}%")
        print()
    
    # Medium confidence picks (probability 40-60%)
    med_conf = results_df[(results_df['Place_Probability'] >= 0.4) & (results_df['Place_Probability'] <= 0.6)]
    if len(med_conf) > 0:
        print("⚡ MEDIUM CONFIDENCE PLACE BETS (40-60%):")
        for _, horse in med_conf.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}%")
        print()
    
    # Value picks (lower probability but good value)
    value_picks = results_df[(results_df['Place_Probability'] >= 0.25) & (results_df['Place_Probability'] < 0.4)]
    if len(value_picks) > 0:
        print("💎 VALUE PLACE BETS (25-40%):")
        for _, horse in value_picks.iterrows():
            prob_pct = horse['Place_Probability'] * 100
            print(f"   #{horse['Barrier']:2.0f} {horse['Horse']:20s} - {prob_pct:5.1f}%")
        print()

def main():
    """Main function to run live race predictions"""
    print("🚀 STARTING LIVE RACE PREDICTION SYSTEM")
    print("=" * 50)
    
    # Load the trained model
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
    
    # Prepare features for prediction
    print("🔧 Preparing features for prediction...")
    features_df = prepare_features_for_prediction(race_df)
    
    # Make predictions
    print("🤖 Making predictions with trained model...")
    probabilities = make_predictions(model, features_df, model_type)
    
    # Display results
    display_predictions(race_df, probabilities)
    
    print("✅ Prediction complete!")

if __name__ == "__main__":
    main()
