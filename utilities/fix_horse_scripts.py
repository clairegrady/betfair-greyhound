#!/usr/bin/env python3
"""
Fix all horse betting scripts (positions 2-18) to match the PostgreSQL updates in position 1
"""
import shutil

source = "/Users/clairegrady/RiderProjects/betfair/horse-simulated/lay_betting/lay_position_1.py"
base_dir = "/Users/clairegrady/RiderProjects/betfair/horse-simulated/lay_betting"

# Read the fixed position 1 script
with open(source, 'r') as f:
    template = f.read()

print("Fixing horse betting scripts 2-18...")
print("=" * 60)

for position in range(2, 19):
    target = f"{base_dir}/lay_position_{position}.py"
    
    # Create the script by replacing position 1 with the new position
    content = template.replace(
        "POSITION_TO_LAY = 1  # Laying the FAVORITE",
        f"POSITION_TO_LAY = {position}  # Laying position {position}"
    )
    content = content.replace(
        "Horse Racing Lay Betting - Position 1 (Favorite)",
        f"Horse Racing Lay Betting - Position {position}"
    )
    content = content.replace(
        "Lays the FAVORITE in every horse race",
        f"Lays position {position} in every horse race"
    )
    
    # Write the fixed script
    with open(target, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed lay_position_{position}.py")

print("=" * 60)
print(f"✅ All 17 scripts fixed! (positions 2-18)")
print("\nAll horse scripts now use PostgreSQL:")
print("  - get_db_connection('betfair_races') for race times")
print("  - get_db_connection('betfairmarket') for market data")
print("  - get_db_connection('betfair_trades') for paper trades")
print("  - %s placeholders instead of ?")
print("  - Lowercase table/column names")
