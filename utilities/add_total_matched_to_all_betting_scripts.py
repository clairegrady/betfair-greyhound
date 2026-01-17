#!/usr/bin/env python3
"""
Utility script to add total_matched tracking to all greyhound and horse betting scripts.
Updates the place_lay_bet function to fetch TotalMatched from MarketCatalogue and include it in INSERT.
"""

import os
import re

# Define paths
GREYHOUND_DIR = "/Users/clairegrady/RiderProjects/betfair/greyhound-simulated/lay_betting"
HORSE_DIR = "/Users/clairegrady/RiderProjects/betfair/horse-simulated/lay_betting"

def update_greyhound_script(filepath):
    """Update a greyhound betting script to include total_matched"""
    print(f"Processing: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern to find the place_lay_bet function
    old_pattern = r'''    def place_lay_bet\(self, race_info: Dict, dog: Dict, position: int\):
        """Record a lay bet"""
        try:
            conn = sqlite3\.connect\(DB_PATH\)
            cursor = conn\.cursor\(\)
            
            liability = FLAT_STAKE \* \(dog\['odds'\] - 1\)
            
            cursor\.execute\("""
                INSERT INTO paper_trades
                \(date, venue, country, race_number, market_id, selection_id, dog_name, box_number,
                 position_in_market, odds, stake, liability, finishing_position, result\)
                VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?\)
            """, \(
                datetime\.now\(\)\.strftime\('%Y-%m-%d'\),
                race_info\['venue'\],
                race_info\['country'\],
                race_info\['race_number'\],
                race_info\['market_id'\],
                dog\['selection_id'\],
                dog\['dog_name'\],
                dog\.get\('box'\),  # Get box number from dog data
                position,
                dog\['odds'\],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending'
            \)\)
            
            conn\.commit\(\)'''
    
    new_code = '''    def place_lay_bet(self, race_info: Dict, dog: Dict, position: int):
        """Record a lay bet"""
        try:
            # Get total matched from MarketCatalogue
            total_matched = None
            try:
                betfair_conn = sqlite3.connect(BETFAIR_DB)
                betfair_cursor = betfair_conn.cursor()
                betfair_cursor.execute("""
                    SELECT TotalMatched FROM MarketCatalogue WHERE MarketId = ?
                """, (race_info['market_id'],))
                result = betfair_cursor.fetchone()
                if result:
                    total_matched = result[0]
                betfair_conn.close()
            except Exception as e:
                logger.debug(f"Could not fetch TotalMatched: {e}")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            liability = FLAT_STAKE * (dog['odds'] - 1)
            
            cursor.execute("""
                INSERT INTO paper_trades
                (date, venue, country, race_number, market_id, selection_id, dog_name, box_number,
                 position_in_market, odds, stake, liability, finishing_position, result, total_matched)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                race_info['venue'],
                race_info['country'],
                race_info['race_number'],
                race_info['market_id'],
                dog['selection_id'],
                dog['dog_name'],
                dog.get('box'),  # Get box number from dog data
                position,
                dog['odds'],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending',
                total_matched
            ))
            
            conn.commit()'''
    
    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_code, content)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Updated: {filepath}")
        return True
    elif 'total_matched' in content:
        print(f"⏭️  Already updated: {filepath}")
        return True
    else:
        print(f"❌ Pattern not found in: {filepath}")
        return False

def update_horse_script(filepath):
    """Update a horse betting script to include total_matched"""
    print(f"Processing: {filepath}")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern for horse scripts (barrier_number instead of box_number)
    old_pattern = r'''    def place_lay_bet\(self, race_info: Dict, horse: Dict, position: int\):
        """Record a lay bet"""
        try:
            conn = sqlite3\.connect\(DB_PATH\)
            cursor = conn\.cursor\(\)
            
            liability = FLAT_STAKE \* \(horse\['odds'\] - 1\)
            
            cursor\.execute\("""
                INSERT INTO paper_trades
                \(date, venue, country, race_number, market_id, selection_id, horse_name, barrier_number,
                 position_in_market, odds, stake, liability, finishing_position, result\)
                VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?, \?\)
            """, \(
                datetime\.now\(\)\.strftime\('%Y-%m-%d'\),
                race_info\['venue'\],
                race_info\['country'\],
                race_info\['race_number'\],
                race_info\['market_id'\],
                horse\['selection_id'\],
                horse\['horse_name'\],
                horse\.get\('barrier'\),
                position,
                horse\['odds'\],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending'
            \)\)
            
            conn\.commit\(\)'''
    
    new_code = '''    def place_lay_bet(self, race_info: Dict, horse: Dict, position: int):
        """Record a lay bet"""
        try:
            # Get total matched from MarketCatalogue
            total_matched = None
            try:
                betfair_conn = sqlite3.connect(BETFAIR_DB)
                betfair_cursor = betfair_conn.cursor()
                betfair_cursor.execute("""
                    SELECT TotalMatched FROM MarketCatalogue WHERE MarketId = ?
                """, (race_info['market_id'],))
                result = betfair_cursor.fetchone()
                if result:
                    total_matched = result[0]
                betfair_conn.close()
            except Exception as e:
                logger.debug(f"Could not fetch TotalMatched: {e}")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            liability = FLAT_STAKE * (horse['odds'] - 1)
            
            cursor.execute("""
                INSERT INTO paper_trades
                (date, venue, country, race_number, market_id, selection_id, horse_name, barrier_number,
                 position_in_market, odds, stake, liability, finishing_position, result, total_matched)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime('%Y-%m-%d'),
                race_info['venue'],
                race_info['country'],
                race_info['race_number'],
                race_info['market_id'],
                horse['selection_id'],
                horse['horse_name'],
                horse.get('barrier'),
                position,
                horse['odds'],
                FLAT_STAKE,
                liability,
                0,  # Will be updated later
                'pending',
                total_matched
            ))
            
            conn.commit()'''
    
    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_code, content)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Updated: {filepath}")
        return True
    elif 'total_matched' in content:
        print(f"⏭️  Already updated: {filepath}")
        return True
    else:
        print(f"❌ Pattern not found in: {filepath}")
        return False

def main():
    print("🔧 Adding total_matched tracking to all betting scripts...\n")
    
    # Update greyhound scripts
    print("📊 Updating Greyhound Scripts:")
    greyhound_success = 0
    for i in range(1, 9):
        filepath = os.path.join(GREYHOUND_DIR, f"lay_position_{i}.py")
        if os.path.exists(filepath):
            if update_greyhound_script(filepath):
                greyhound_success += 1
    
    print(f"\n✅ Greyhound scripts updated: {greyhound_success}/8\n")
    
    # Update horse scripts
    print("🐴 Updating Horse Scripts:")
    horse_success = 0
    for i in range(1, 19):
        filepath = os.path.join(HORSE_DIR, f"lay_position_{i}.py")
        if os.path.exists(filepath):
            if update_horse_script(filepath):
                horse_success += 1
    
    print(f"\n✅ Horse scripts updated: {horse_success}/18\n")
    print(f"🎉 Total scripts updated: {greyhound_success + horse_success}/26")

if __name__ == '__main__':
    main()
