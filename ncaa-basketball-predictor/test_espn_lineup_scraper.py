"""
Test ESPN API for game lineups
ESPN has a simpler JSON API that might be easier
"""

import requests
import json


def test_espn_box_score():
    """
    Test ESPN API for box score data
    Known game: Duke vs Houston, March 30, 2024
    Game ID from our database: 401638638
    """
    
    print("\n" + "="*70)
    print("🧪 TEST: ESPN API - Duke vs Houston (2024-03-30)")
    print("="*70 + "\n")
    
    # ESPN game ID from our database
    game_id = "401638638"
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
    
    print(f"URL: {url}\n")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}\n")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if boxscore exists
            if 'boxscore' in data:
                print("✅ Found boxscore data!\n")
                
                boxscore = data['boxscore']
                
                # Navigate to players
                if 'players' in boxscore:
                    print(f"Teams: {len(boxscore['players'])}\n")
                    
                    for team_data in boxscore['players']:
                        team_name = team_data['team']['displayName']
                        print(f"{'='*50}")
                        print(f"TEAM: {team_name}")
                        print(f"{'='*50}\n")
                        
                        # Get player statistics
                        for stat_group in team_data['statistics']:
                            labels = stat_group['names']
                            print(f"Stat columns: {labels}\n")
                            
                            print("STARTERS:")
                            for athlete_data in stat_group['athletes'][:5]:  # Typically first 5 are starters
                                athlete = athlete_data['athlete']
                                stats = athlete_data['stats']
                                starter = athlete_data.get('starter', False)
                                
                                name = athlete['displayName']
                                
                                # Parse stats
                                stat_dict = dict(zip(labels, stats))
                                mins = stat_dict.get('MIN', '0')
                                pts = stat_dict.get('PTS', '0')
                                reb = stat_dict.get('REB', '0')
                                ast = stat_dict.get('AST', '0')
                                
                                marker = "⭐" if starter else "  "
                                print(f"{marker} {name:25} | {mins:>3} min | {pts:>2} pts | {reb:>2} reb | {ast:>2} ast")
                            
                            print("\nBENCH:")
                            for athlete_data in stat_group['athletes'][5:]:
                                athlete = athlete_data['athlete']
                                stats = athlete_data['stats']
                                starter = athlete_data.get('starter', False)
                                
                                name = athlete['displayName']
                                
                                stat_dict = dict(zip(labels, stats))
                                mins = stat_dict.get('MIN', '0')
                                pts = stat_dict.get('PTS', '0')
                                reb = stat_dict.get('REB', '0')
                                ast = stat_dict.get('AST', '0')
                                
                                marker = "⭐" if starter else "  "
                                print(f"{marker} {name:25} | {mins:>3} min | {pts:>2} pts | {reb:>2} reb | {ast:>2} ast")
                            
                            print("\n")
                            break  # Only need first stat group
                        
                else:
                    print("❌ No 'players' section in boxscore")
                    print(f"Available keys: {list(boxscore.keys())}")
            else:
                print("❌ No 'boxscore' in response")
                print(f"Available keys: {list(data.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_espn_box_score()

