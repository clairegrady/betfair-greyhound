"""
Live Feature Lookup - Match live horses to historical AWS data
"""

import pandas as pd
import sqlite3
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta

DB_PATH = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/horse_racing_ml.db"

class LiveFeatureLookup:
    def __init__(self):
        print("📚 Loading AWS historical data from combined database...")
        conn = sqlite3.connect(DB_PATH)
        # Load from combined_data table (has 161K horses with BSP data too!)
        self.aws_data = pd.read_sql_query("SELECT * FROM combined_data", conn)
        conn.close()
        
        self.aws_data['meetingDate'] = pd.to_datetime(self.aws_data['meetingDate'])
        self.aws_data['meetingName_clean'] = self.aws_data['meetingName'].str.upper().str.strip()
        self.aws_data['runnerName_clean'] = self.aws_data['runnerName'].str.upper().str.strip()
        print(f"   ✅ Loaded {len(self.aws_data):,} historical records from combined database")
    
    def get_features_for_horse(self, horse_name, track_name=None, race_date=None):
        """
        Get latest AWS features for a horse
        
        Args:
            horse_name: Name of horse (will be fuzzy matched)
            track_name: Track name (optional, if None will search all tracks)
            race_date: Date of race (will get most recent historical data before this date)
        
        Returns:
            dict of features or None if not found
        """
        
        if race_date is None:
            race_date = datetime.now()
        
        horse_clean = horse_name.upper().strip()
        
        # Filter to this track if specified
        if track_name:
            track_clean = track_name.upper().strip()
            track_data = self.aws_data[
                self.aws_data['meetingName_clean'].str.contains(track_clean, case=False, na=False) |
                (self.aws_data['meetingName_clean'] == track_clean)
            ]
            
            if track_data.empty:
                # Try fuzzy match on track
                tracks = self.aws_data['meetingName_clean'].unique()
                best_match = max(tracks, key=lambda x: fuzz.ratio(track_clean, x))
                if fuzz.ratio(track_clean, best_match) > 80:
                    track_data = self.aws_data[self.aws_data['meetingName_clean'] == best_match]
            
            if track_data.empty:
                return None
        else:
            # Search all tracks
            track_data = self.aws_data
        
        # Filter to this horse
        horse_data = track_data[
            track_data['runnerName_clean'].str.contains(horse_clean, case=False, na=False) |
            (track_data['runnerName_clean'] == horse_clean)
        ]
        
        if horse_data.empty:
            # Try fuzzy match on horse name
            horses = track_data['runnerName_clean'].unique()
            if len(horses) == 0:
                return None
            best_match = max(horses, key=lambda x: fuzz.ratio(horse_clean, x))
            if fuzz.ratio(horse_clean, best_match) > 85:
                horse_data = track_data[track_data['runnerName_clean'] == best_match]
        
        if horse_data.empty:
            return None
        
        # Get most recent race BEFORE the target date
        # Strip timezone from race_date if it's timezone-aware (database dates are naive)
        race_date_naive = race_date.replace(tzinfo=None) if hasattr(race_date, 'tzinfo') and race_date.tzinfo else race_date
        horse_data = horse_data[horse_data['meetingDate'] < race_date_naive]
        if horse_data.empty:
            return None
        
        # Get most recent record
        latest = horse_data.sort_values('meetingDate', ascending=False).iloc[0]
        
        # Extract all features (excluding target and identifiers)
        feature_cols = [col for col in latest.index if col not in [
            'finishingPosition', 'meetingName', 'meetingDate', 'raceNumber',
            'runnerNumber', 'runnerName', 'riderName', 'location', 'raceName',
            'raceStartTime', 'runner_scratched', 'race_abandoned',
            'meetingName_clean', 'runnerName_clean'
        ]]
        
        features = latest[feature_cols].to_dict()
        features['_matched_horse'] = latest['runnerName']
        features['_matched_track'] = latest['meetingName']
        features['_last_race_date'] = latest['meetingDate']
        # Use naive race_date for days calculation (already converted above)
        features['_days_since_last_run'] = (race_date_naive - latest['meetingDate']).days
        
        return features
    
    def get_features_for_race(self, horses, track_name, race_date=None):
        """
        Get features for all horses in a race
        
        Args:
            horses: List of dicts with keys: selection_id, horse_name
            track_name: Track name
            race_date: Date of race
        
        Returns:
            dict mapping selection_id to features
        """
        results = {}
        
        for horse in horses:
            selection_id = horse['selection_id']
            horse_name = horse['horse_name']
            
            features = self.get_features_for_horse(horse_name, track_name, race_date)
            
            if features:
                results[selection_id] = features
            else:
                print(f"      ⚠️  No features found for {horse_name}")
        
        return results

