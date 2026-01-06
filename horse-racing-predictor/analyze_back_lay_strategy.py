"""
Analyze Back+Lay Strategy (Hedging/Arbitrage)

Strategy: Bet X on back, X on lay, try to profit from the spread
"""
import requests
import json

BACKEND_URL = "http://localhost:5173"

def analyze_market(market_id, market_name):
    """Analyze back/lay spreads for a market"""
    response = requests.get(f"{BACKEND_URL}/api/horse-racing/market-book/{market_id}", timeout=10)
    if response.status_code != 200:
        print(f"Could not fetch market {market_id}")
        return
    
    data = response.json()
    
    print(f"\n{'='*70}")
    print(f"Market: {market_name}")
    print(f"Market ID: {market_id}")
    print(f"Status: {data.get('status')}")
    print(f"{'='*70}\n")
    
    spreads = []
    profitable = []
    
    for runner in data.get('runners', []):
        sid = runner.get('selectionId')
        status = runner.get('status')
        
        if status != 'ACTIVE':
            continue
        
        ex = runner.get('ex', {})
        back_offers = ex.get('availableToBack', [])
        lay_offers = ex.get('availableToLay', [])
        
        if not back_offers or not lay_offers:
            continue
        
        back_price = back_offers[0].get('price')
        lay_price = lay_offers[0].get('price')
        
        if not back_price or not lay_price:
            continue
        
        spread = lay_price - back_price
        spread_pct = (spread / back_price) * 100
        spreads.append(spread_pct)
        
        # Calculate P&L for betting $100 back + $100 lay
        stake = 100
        
        # If horse WINS:
        # - Back wins: stake * (back_price - 1) profit
        # - Lay loses: stake * (lay_price - 1) liability
        # - Net: stake * (back_price - lay_price)
        if_wins = stake * (back_price - lay_price)
        
        # If horse LOSES:
        # - Back loses: -stake
        # - Lay wins: stake (but pay 2-5% commission)
        # - Net: -stake + stake - commission ≈ -commission
        lay_commission_rate = 0.02  # Betfair charges 2% base rate
        if_loses = -stake * lay_commission_rate
        
        # This is ALWAYS a loss because lay > back!
        # You ALWAYS lose if horse wins (negative spread)
        # You ALWAYS lose if horse loses (commission)
        
        print(f"Selection {sid}:")
        print(f"  Back: {back_price:.2f} | Lay: {lay_price:.2f}")
        print(f"  Spread: {spread:.2f} ({spread_pct:.2f}%)")
        print(f"  Betting ${stake} back + ${stake} lay:")
        print(f"    If WINS: ${if_wins:.2f}")
        print(f"    If LOSES: ${if_loses:.2f}")
        print(f"    Expected: GUARANTEED LOSS")
        
        if spread_pct < 5:  # Tight spread
            profitable.append({
                'selection_id': sid,
                'back': back_price,
                'lay': lay_price,
                'spread_pct': spread_pct,
                'if_wins': if_wins,
                'if_loses': if_loses
            })
        
        print()
    
    if spreads:
        print(f"\nSUMMARY:")
        print(f"  Average spread: {sum(spreads)/len(spreads):.2f}%")
        print(f"  Min spread: {min(spreads):.2f}%")
        print(f"  Max spread: {max(spreads):.2f}%")
        
        if profitable:
            print(f"\n  ⚠️  {len(profitable)} horses with spread < 5%")
            print(f"  BUT: All back+lay bets are GUARANTEED LOSSES!")
            print(f"  Reason: Lay price is ALWAYS > Back price (the spread)")
    
    print("\n" + "="*70)
    return spreads

def main():
    """Test on a live market"""
    print("\n" + "="*70)
    print("BACK+LAY STRATEGY ANALYSIS")
    print("="*70)
    
    print("\n📋 THEORY:")
    print("  Back+Lay on the SAME horse in the SAME race is ALWAYS a loss:")
    print("  1. If horse WINS: You profit from back, lose MORE from lay")
    print("  2. If horse LOSES: You break even but pay lay commission")
    print("  3. Result: Guaranteed loss either way (the spread + commission)")
    print()
    print("  The ONLY way back+lay works is:")
    print("  - ARBITRAGE: Back at one bookie, lay at Betfair (rare, <1%)")
    print("  - HEDGING: Back early at high odds, lay later at lower odds")
    print("    (requires odds to SHORTEN significantly)")
    
    # Test on current markets
    test_markets = [
        ("1.252380075", "Townsville R6 WIN"),
        ("1.252380076", "Townsville R6 PLACE"),
    ]
    
    for market_id, name in test_markets:
        analyze_market(market_id, name)
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    print("="*70)
    print("❌ Back+Lay on same horse in same market = GUARANTEED LOSS")
    print("✅ Back EARLY + Lay LATER (hedging) = Can profit if odds shorten")
    print("   But this requires:")
    print("   - Predicting which horses' odds will shorten")
    print("   - Real-time monitoring and fast execution")
    print("   - Odds moving in the right direction (not guaranteed)")
    print()
    print("💡 RECOMMENDATION:")
    print("   Stick with the current PLACE betting strategy.")
    print("   It's simpler and based on proven market edges.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

