import sqlite3
import pandas as pd
from typing import Dict, List, Optional

class LiveBettingLookup:
    """Lookup historical stats for live betting predictions"""
    
    def __init__(self, db_path: str = 'racing_data.db'):
        self.db_path = db_path
    
    def get_runner_stats(self, runner_name: str) -> Dict:
        """Get comprehensive runner statistics"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT 
            runnerName,
            overall_runner_starts,
            overall_runner_wins, 
            overall_runner_placings,
            track_runner_starts,
            track_runner_wins,
            track_runner_placings,
            distance_runner_starts,
            distance_runner_wins,
            distance_runner_placings,
            firstUp_runner_starts,
            firstUp_runner_wins,
            firstUp_runner_placings,
            secondUp_runner_starts,
            secondUp_runner_wins,
            secondUp_runner_placings
        FROM historical_data 
        WHERE runnerName = ? 
        LIMIT 1
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (runner_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'runner_name': result[0],
                'overall_starts': result[1],
                'overall_wins': result[2],
                'overall_placings': result[3],
                'track_starts': result[4],
                'track_wins': result[5],
                'track_placings': result[6],
                'distance_starts': result[7],
                'distance_wins': result[8],
                'distance_placings': result[9],
                'firstup_starts': result[10],
                'firstup_wins': result[11],
                'firstup_placings': result[12],
                'secondup_starts': result[13],
                'secondup_wins': result[14],
                'secondup_placings': result[15]
            }
        return {}
    
    def get_jockey_stats(self, jockey_name: str) -> Dict:
        """Get comprehensive jockey statistics"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
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
        LIMIT 1
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (jockey_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'jockey_name': result[0],
                'track_starts': result[1],
                'track_wins': result[2],
                'track_placings': result[3],
                'region_starts': result[4],
                'region_wins': result[5],
                'region_placings': result[6],
                'last30days_starts': result[7],
                'last30days_wins': result[8],
                'last30days_placings': result[9],
                'last12months_starts': result[10],
                'last12months_wins': result[11],
                'last12months_placings': result[12]
            }
        return {}
    
    def get_runner_track_condition_stats(self, runner_name: str, track_condition: str) -> Dict:
        """Get runner stats for specific track conditions"""
        conn = sqlite3.connect(self.db_path)
        
        # Map track conditions to column names
        condition_columns = {
            'GOOD4': 'good_runner_',
            'GOOD3': 'good_runner_',
            'GOOD': 'good_runner_',
            'SOFT5': 'soft_runner_',
            'SOFT6': 'soft_runner_',
            'SOFT7': 'soft_runner_',
            'HVY8': 'heavy_runner_',
            'HVY9': 'heavy_runner_',
            'HVY10': 'heavy_runner_',
            'DEAD': 'dead_runner_',
            'SLOW': 'slow_runner_',
            'FIRM': 'firm_runner_',
            'AWT': 'firm_runner_'  # All Weather Track
        }
        
        condition_prefix = condition_columns.get(track_condition, 'good_runner_')
        
        query = f"""
        SELECT 
            runnerName,
            {condition_prefix}starts,
            {condition_prefix}wins,
            {condition_prefix}placings
        FROM historical_data 
        WHERE runnerName = ? 
        LIMIT 1
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (runner_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'runner_name': result[0],
                'condition': track_condition,
                'starts': result[1],
                'wins': result[2],
                'placings': result[3]
            }
        return {}
    
    def get_runner_distance_stats(self, runner_name: str, distance: int) -> Dict:
        """Get runner stats for specific distance"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
        SELECT 
            runnerName,
            distance_runner_starts,
            distance_runner_wins,
            distance_runner_placings
        FROM historical_data 
        WHERE runnerName = ? 
        LIMIT 1
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (runner_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'runner_name': result[0],
                'distance': distance,
                'starts': result[1],
                'wins': result[2],
                'placings': result[3]
            }
        return {}
    
    def get_live_race_features(self, runner_name: str, jockey_name: str, 
                             track_condition: str, distance: int) -> Dict:
        """Get all features needed for live betting prediction"""
        
        features = {}
        
        # Get runner stats
        runner_stats = self.get_runner_stats(runner_name)
        if runner_stats:
            features.update(runner_stats)
        
        # Get jockey stats
        jockey_stats = self.get_jockey_stats(jockey_name)
        if jockey_stats:
            features.update(jockey_stats)
        
        # Get track condition specific stats
        condition_stats = self.get_runner_track_condition_stats(runner_name, track_condition)
        if condition_stats:
            features.update(condition_stats)
        
        # Get distance specific stats
        distance_stats = self.get_runner_distance_stats(runner_name, distance)
        if distance_stats:
            features.update(distance_stats)
        
        # Add race context
        features.update({
            'track_condition': track_condition,
            'race_distance': distance
        })
        
        return features

def main():
    """Demo the live betting lookup"""
    lookup = LiveBettingLookup()
    
    print("=== LIVE BETTING LOOKUP DEMO ===")
    
    # Test with a known horse and jockey
    runner_name = "RUBY NOIR"
    jockey_name = "William Pike"
    track_condition = "GOOD4"
    distance = 1600
    
    print(f"\nLooking up stats for:")
    print(f"Runner: {runner_name}")
    print(f"Jockey: {jockey_name}")
    print(f"Track: {track_condition}")
    print(f"Distance: {distance}m")
    
    # Get runner stats
    runner_stats = lookup.get_runner_stats(runner_name)
    if runner_stats:
        print(f"\n=== RUNNER STATS ===")
        print(f"Overall: {runner_stats['overall_starts']} starts, {runner_stats['overall_wins']} wins, {runner_stats['overall_placings']} places")
        print(f"Track: {runner_stats['track_starts']} starts, {runner_stats['track_wins']} wins, {runner_stats['track_placings']} places")
        print(f"Distance: {runner_stats['distance_starts']} starts, {runner_stats['distance_wins']} wins, {runner_stats['distance_placings']} places")
        print(f"First Up: {runner_stats['firstup_starts']} starts, {runner_stats['firstup_wins']} wins, {runner_stats['firstup_placings']} places")
    
    # Get jockey stats
    jockey_stats = lookup.get_jockey_stats(jockey_name)
    if jockey_stats:
        print(f"\n=== JOCKEY STATS ===")
        print(f"Track: {jockey_stats['track_starts']} starts, {jockey_stats['track_wins']} wins, {jockey_stats['track_placings']} places")
        print(f"Last 30 Days: {jockey_stats['last30days_starts']} starts, {jockey_stats['last30days_wins']} wins, {jockey_stats['last30days_placings']} places")
        print(f"Last 12 Months: {jockey_stats['last12months_starts']} starts, {jockey_stats['last12months_wins']} wins, {jockey_stats['last12months_placings']} places")
    
    # Get all features for live betting
    all_features = lookup.get_live_race_features(runner_name, jockey_name, track_condition, distance)
    print(f"\n=== ALL FEATURES FOR LIVE BETTING ===")
    print(f"Total features available: {len(all_features)}")
    for key, value in all_features.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
