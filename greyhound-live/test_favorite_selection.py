"""
Quick test to verify the script picks the RIGHT favorite (lowest lay odds)
"""
import requests
import re

BACKEND_URL = "http://localhost:5173"

# Get a recent greyhound market ID
import sqlite3
conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite")
cursor = conn.cursor()
cursor.execute("""
    SELECT MarketId, EventName, MarketName 
    FROM MarketCatalogue 
    WHERE EventTypeName = 'Greyhound Racing'
    ORDER BY ROWID DESC 
    LIMIT 5
""")
markets = cursor.fetchall()
conn.close()

print("Testing favorite selection logic...\n")

for market_id, event_name, market_name in markets:
    print(f"=" * 80)
    print(f"Market: {event_name} - {market_name}")
    print(f"Market ID: {market_id}")
    print("-" * 80)
    
    # Call the API
    url = f"{BACKEND_URL}/api/GreyhoundMarketBook/market/{market_id}"
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API error: {response.status_code}")
            continue
        
        data = response.json()
        runners = data.get('runners', [])
        
        if not runners:
            print("⚠️  No runners")
            continue
        
        # Build odds map (same logic as script)
        odds_map = []
        for runner in runners:
            selection_id = runner.get('selectionId')
            runner_name = runner.get('runnerName', f'Runner {selection_id}')
            box = runner.get('box')
            ex = runner.get('ex', {})
            available_to_lay = ex.get('availableToLay', [])
            
            if available_to_lay and len(available_to_lay) > 0:
                best_lay = available_to_lay[0]
                odds = best_lay.get('price')
                size = best_lay.get('size', 0)
                
                if odds and odds > 0 and selection_id:
                    clean_name = re.sub(r'^\d+\.\s*', '', runner_name)
                    odds_map.append({
                        'selection_id': selection_id,
                        'odds': odds,
                        'size_available': size,
                        'dog_name': clean_name,
                        'box': box
                    })
        
        if not odds_map:
            print("⚠️  No valid lay odds")
            continue
        
        # Sort by odds (ascending = lowest first)
        odds_map.sort(key=lambda x: x['odds'])
        
        print(f"\n📋 All dogs sorted by LAY odds (lowest = favorite):")
        for i, dog in enumerate(odds_map):
            marker = "👉 FAVORITE" if i == 0 else ""
            print(f"   {i+1}. {dog['dog_name']:30s} @ {dog['odds']:8.2f} {marker}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        continue

print("=" * 80)
print("\n✅ Test complete. Check if the FAVORITE picks look correct.")
print("   (Favorite should be the dog with LOWEST lay odds)")
