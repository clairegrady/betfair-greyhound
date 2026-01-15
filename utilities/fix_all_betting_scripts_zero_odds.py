#!/usr/bin/env python3
"""
Fix all 26 betting scripts to NOT place bets if odds are zero or invalid
"""

import os
import re

def fix_betting_script(filepath):
    """Add odds validation to a betting script"""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already fixed
    if 'Check for zero or invalid odds' in content or 'target_dog[\'odds\'] <= 0' in content:
        print(f"  ⏭️  Already fixed: {filepath}")
        return False
    
    # Find the section where we check max odds and add zero odds check BEFORE it
    pattern = r'(\s+)(# Get the dog at our position\n\s+target_dog = sorted_runners\[POSITION_TO_LAY - 1\]\n\s+\n\s+)(# Check max odds)'
    
    replacement = r'\1\2# Check for zero or invalid odds - DO NOT BET!\n\1if target_dog[\'odds\'] <= 0:\n\1    logger.error(f"❌ SKIPPING - Invalid odds {target_dog[\'odds\']} for {target_dog.get(\'dog_name\', target_dog.get(\'horse_name\', \'Unknown\'))} (Position {POSITION_TO_LAY})")\n\1    return\n\1\n\1\3'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content:
        print(f"  ⚠️  Pattern not found in: {filepath}")
        return False
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"  ✅ Fixed: {filepath}")
    return True

def main():
    print("="*80)
    print("🔧 FIXING ALL BETTING SCRIPTS - ADD ZERO ODDS CHECK")
    print("="*80)
    
    greyhound_dir = "/Users/clairegrady/RiderProjects/betfair/greyhound-predictor/lay_betting"
    horse_dir = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/lay_betting"
    
    total_fixed = 0
    
    print("\n🐕 Greyhound scripts (8):")
    for i in range(1, 9):
        filepath = os.path.join(greyhound_dir, f"lay_position_{i}.py")
        if os.path.exists(filepath):
            if fix_betting_script(filepath):
                total_fixed += 1
    
    print("\n🏇 Horse scripts (18):")
    for i in range(1, 19):
        filepath = os.path.join(horse_dir, f"lay_position_{i}.py")
        if os.path.exists(filepath):
            if fix_betting_script(filepath):
                total_fixed += 1
    
    print("\n" + "="*80)
    print(f"✅ Fixed {total_fixed} betting scripts")
    print("="*80)

if __name__ == "__main__":
    main()
