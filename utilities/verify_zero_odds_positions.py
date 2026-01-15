"""
Verify that zero-odds bets were placed on the correct market positions
(i.e., did we actually bet on the favorite, 2nd favorite, etc.?)
"""

import sqlite3
import sys

PAPER_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/databases/greyhounds/paper_trades_greyhounds.db"
BACKEND_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"

def get_zero_odds_bets():
    """Get all bets with zero odds from today"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, market_id, selection_id, dog_name, position_in_market, venue, race_number, created_at
        FROM paper_trades
        WHERE date = '2026-01-15' AND odds = 0
        ORDER BY created_at
    """)
    
    bets = cursor.fetchall()
    conn.close()
    return bets

def get_market_odds(market_id):
    """Get the best back odds for all runners in a market"""
    conn = sqlite3.connect(BACKEND_DB)
    cursor = conn.cursor()
    
    # Get best available back price for each runner
    cursor.execute("""
        SELECT SelectionId, MAX(Price) as best_price
        FROM GreyhoundMarketBook
        WHERE MarketId = ? 
        AND PriceType = 'AvailableToBack'
        AND Price > 0
        GROUP BY SelectionId
        ORDER BY best_price ASC
    """, (market_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    # Return list of (selection_id, odds) sorted by odds ascending
    return [(sel_id, price) for sel_id, price in results]

def verify_position(bet_selection_id, claimed_position, market_odds):
    """
    Check if the bet was placed on the correct market position
    Returns: (actual_position, actual_odds, is_correct)
    """
    if not market_odds:
        return (None, None, None)  # Can't verify
    
    # Find where this selection_id ranks in the sorted odds
    for idx, (sel_id, odds) in enumerate(market_odds, start=1):
        if sel_id == bet_selection_id:
            actual_position = idx
            actual_odds = odds
            is_correct = (actual_position == claimed_position)
            return (actual_position, actual_odds, is_correct)
    
    # Selection not found in market odds
    return (None, None, False)

def main():
    print("=" * 80)
    print("🔍 VERIFYING ZERO-ODDS BETS - POSITION CHECK")
    print("=" * 80)
    
    zero_odds_bets = get_zero_odds_bets()
    
    if not zero_odds_bets:
        print("✅ No zero-odds bets found!")
        return
    
    print(f"\n📊 Found {len(zero_odds_bets)} bets with zero odds\n")
    
    correct_bets = []
    incorrect_bets = []
    unverifiable_bets = []
    
    # Group by market to avoid repeated queries
    markets_processed = {}
    
    for bet_id, market_id, selection_id, dog_name, claimed_pos, venue, race_num, created_at in zero_odds_bets:
        # Get market odds (cached)
        if market_id not in markets_processed:
            markets_processed[market_id] = get_market_odds(market_id)
        
        market_odds = markets_processed[market_id]
        
        # Verify position
        actual_pos, actual_odds, is_correct = verify_position(selection_id, claimed_pos, market_odds)
        
        bet_info = {
            'id': bet_id,
            'market_id': market_id,
            'selection_id': selection_id,
            'dog_name': dog_name,
            'venue': venue,
            'race_number': race_num,
            'claimed_position': claimed_pos,
            'actual_position': actual_pos,
            'actual_odds': actual_odds,
            'created_at': created_at
        }
        
        if is_correct is None:
            unverifiable_bets.append(bet_info)
        elif is_correct:
            correct_bets.append(bet_info)
        else:
            incorrect_bets.append(bet_info)
    
    # Print summary
    print(f"{'='*80}")
    print(f"📈 SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Correct position bets:   {len(correct_bets)}")
    print(f"❌ Incorrect position bets: {len(incorrect_bets)}")
    print(f"⚠️  Unverifiable bets:      {len(unverifiable_bets)}")
    print(f"{'='*80}\n")
    
    # Show incorrect bets in detail
    if incorrect_bets:
        print(f"{'='*80}")
        print(f"❌ INCORRECT POSITION BETS (SHOULD BE DELETED)")
        print(f"{'='*80}")
        for bet in incorrect_bets:
            print(f"ID: {bet['id']:4} | {bet['venue']:15} R{bet['race_number']} | {bet['dog_name']:20}")
            print(f"       Claimed: Position {bet['claimed_position']} | Actual: Position {bet['actual_position']} @ {bet['actual_odds']:.2f}")
            print()
    
    # Show correct bets summary
    if correct_bets:
        print(f"{'='*80}")
        print(f"✅ CORRECT POSITION BETS (CAN BE BACKFILLED)")
        print(f"{'='*80}")
        print(f"Total: {len(correct_bets)} bets\n")
        
        # Group by position
        by_position = {}
        for bet in correct_bets:
            pos = bet['claimed_position']
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(bet)
        
        for pos in sorted(by_position.keys()):
            bets_at_pos = by_position[pos]
            avg_odds = sum(b['actual_odds'] for b in bets_at_pos) / len(bets_at_pos)
            print(f"Position {pos}: {len(bets_at_pos)} bets | Avg odds: {avg_odds:.2f}")
    
    # Show unverifiable bets
    if unverifiable_bets:
        print(f"\n{'='*80}")
        print(f"⚠️  UNVERIFIABLE BETS (NO ODDS DATA IN BACKEND)")
        print(f"{'='*80}")
        for bet in unverifiable_bets[:10]:  # Show first 10
            print(f"ID: {bet['id']:4} | {bet['venue']:15} R{bet['race_number']} | {bet['dog_name']:20}")
        if len(unverifiable_bets) > 10:
            print(f"... and {len(unverifiable_bets) - 10} more")
    
    # Save IDs to files for easy deletion/backfill
    if incorrect_bets:
        with open('/Users/clairegrady/RiderProjects/betfair/utilities/INCORRECT_BET_IDS.txt', 'w') as f:
            f.write(','.join(str(b['id']) for b in incorrect_bets))
        print(f"\n💾 Incorrect bet IDs saved to: utilities/INCORRECT_BET_IDS.txt")
    
    if correct_bets:
        with open('/Users/clairegrady/RiderProjects/betfair/utilities/CORRECT_BET_IDS_TO_BACKFILL.txt', 'w') as f:
            for bet in correct_bets:
                f.write(f"{bet['id']},{bet['actual_odds']}\n")
        print(f"💾 Correct bet IDs (with odds) saved to: utilities/CORRECT_BET_IDS_TO_BACKFILL.txt")
    
    print(f"\n{'='*80}")
    print(f"🎯 NEXT STEPS:")
    print(f"{'='*80}")
    if incorrect_bets:
        print(f"1. Delete {len(incorrect_bets)} incorrect bets")
    if correct_bets:
        print(f"2. Backfill odds for {len(correct_bets)} correct bets")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
