"""
Paper Trading System - MARKET-BASED (NO ML)
Simple rule: Bet on favorites with odds 1.5-3.0 to PLACE
Uses tiered Kelly staking based on proven edges
"""

import pandas as pd
import sqlite3
import requests
import time
import pytz
from datetime import datetime, timedelta
import json

# Configuration
PAPER_TRADES_DB = "/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/paper_trades.db"
BETFAIR_DB = "/Users/clairegrady/RiderProjects/betfair/Betfair/Betfair-Backend/betfairmarket.sqlite"
BACKEND_URL = "http://localhost:5173"

# Paper trading config - MARKET-BASED STRATEGY
PAPER_BANKROLL = 10000
KELLY_FRACTION = 0.25  # 25% Kelly (conservative)

# PROVEN EDGES FROM ANALYSIS (17,446 races):
# Odds 1.5-2.0: +3.96% ROI, 61.6% place rate
# Odds 2.0-3.0: +6.92% ROI, 48.7% place rate
EDGE_BY_ODDS = {
    (1.5, 2.0): 0.0396,  # 3.96% edge
    (2.0, 3.0): 0.0692,  # 6.92% edge
}

MINUTES_BEFORE_RACE = 2 # Bet 2 mins before race

def init_paper_trades_db():
    """Verify paper trades database exists (table should already exist from check_results.py)"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    # Just verify the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='paper_trades'")
    if not cursor.fetchone():
        print("   ⚠️  WARNING: paper_trades table doesn't exist! Run check_results.py first to create it.")
    
    conn.close()

def calculate_kelly_stake(odds, bankroll):
    """
    Calculate stake using Kelly Criterion based on proven edges
    Returns 0 if no edge exists for this odds range
    """
    for (min_odds, max_odds), edge in EDGE_BY_ODDS.items():
        if min_odds <= odds < max_odds:
            # Kelly formula: stake = (edge × bankroll) × kelly_fraction
            # For place betting, we use fractional Kelly to reduce variance
            stake = bankroll * edge * KELLY_FRACTION
            return round(stake, 2)
    
    return 0  # No edge in this odds range

def get_horse_to_bet_on(odds_map):
    """
    Simple market rule: Find the best horse to bet on (sorted by odds)
    
    Strategy:
    1. Sort horses by odds (lowest to highest = favorite to longshot)
    2. Check favorite - if in 1.5-3.0 range, bet on it
    3. If not, check 2nd favorite, then 3rd, etc.
    4. Bet on the FIRST horse we find in the profitable range
    5. Max 1 bet per race
    
    Returns: (selection_id, odds, stake, edge) or None
    """
    if not odds_map:
        return None
    
    # Sort horses by odds (lowest first = favorite first)
    sorted_horses = sorted(odds_map.items(), key=lambda x: x[1]['odds'])
    
    # Check each horse in order (favorite first) until we find one in range
    for selection_id, odds_data in sorted_horses:
        odds = odds_data['odds']
        
        # Check if this horse's odds are in our profitable ranges
        stake = calculate_kelly_stake(odds, PAPER_BANKROLL)
        
        if stake > 0:
            # Get the edge for this range
            for (min_odds, max_odds), edge in EDGE_BY_ODDS.items():
                if min_odds <= odds < max_odds:
                    return (selection_id, odds, stake, edge)
    
    return None

def load_models():
    """NO MODELS - We use pure market analysis instead"""
    print("📊 MARKET-BASED STRATEGY (NO ML MODEL)")
    print("   ✓ Strategy: Bet on best favorite in 1.5-3.0 range to PLACE")
    print("   ✓ Priority: Favorite > 2nd fav > 3rd fav (first one in range)")
    print("   ✓ Proven edges from 17,446 races:")
    print("      • 1.5-2.0 odds: +3.96% ROI, 61.6% place rate")
    print("      • 2.0-3.0 odds: +6.92% ROI, 48.7% place rate")
    print("   ✓ Staking: Tiered Kelly (25% Kelly)")
    print("   ✓ Expected: ~5% ROI overall")
    
    return None  # No models needed!

def get_upcoming_races():
    """Get races from race_times.db and match to markets in betfairmarket.sqlite"""
    from datetime import timezone
    import pytz
    
    print("   🔍 Getting upcoming races from race_times.db...")
    
    # Get actual upcoming races from race_times.db
    race_times_conn = sqlite3.connect("/Users/clairegrady/RiderProjects/betfair/horse-racing-predictor/race_times.db")
    
    race_times_query = """
    SELECT venue, race_number, race_time, race_date
    FROM race_times
    WHERE country = 'AUS'
    ORDER BY race_time
    """
    
    race_times_df = pd.read_sql(race_times_query, race_times_conn)
    race_times_conn.close()
    
    print(f"   📊 Found {len(race_times_df)} races in race_times.db")
    
    if race_times_df.empty:
        return []
    
    # Database times are in Bangkok time (because racenet.com.au shows times in your local timezone)
    # We need to convert to AEST for proper comparison
    bangkok_tz = pytz.timezone('Asia/Bangkok')
    aest_tz = pytz.timezone('Australia/Sydney')
    now_aest = datetime.now(aest_tz)
    upcoming_races = []
    
    for _, row in race_times_df.iterrows():
        # Combine date and time - these are in Bangkok time
        race_datetime_str = f"{row['race_date']} {row['race_time']}"
        try:
            # Parse as naive datetime, localize to Bangkok time, then convert to AEST
            race_datetime_naive = datetime.strptime(race_datetime_str, '%Y-%m-%d %H:%M')
            race_datetime_bangkok = bangkok_tz.localize(race_datetime_naive)
            race_datetime_aest = race_datetime_bangkok.astimezone(aest_tz)
            
            # Calculate minutes until race (both times now in AEST)
            mins_until = (race_datetime_aest - now_aest).total_seconds() / 60
            
            # Only include races that haven't started yet
            if mins_until > -5:  # Allow 5 min grace period for races just started
                upcoming_races.append({
                    'venue': row['venue'],
                    'race_number': row['race_number'],
                    'race_datetime': race_datetime_aest,
                    'mins_until': mins_until
                })
        except Exception as e:
            print(f"Error parsing race time: {e}")
            continue
    
    if not upcoming_races:
        return []
    
    print(f"   📍 {len(upcoming_races)} races in time window, matching with markets...")
    
    # Now match these races to markets in betfairmarket.sqlite
    market_conn = sqlite3.connect(BETFAIR_DB)
    
    # Get today's date for filtering
    day = datetime.now(aest_tz).day
    if day in [1, 21, 31]:
        suffix = "st"
    elif day in [2, 22]:
        suffix = "nd"
    elif day in [3, 23]:
        suffix = "rd"
    else:
        suffix = "th"
    
    today_str = datetime.now(aest_tz).strftime(f"%-d{suffix} %b")  # e.g. "3rd Jan"
    
    matched_races = []
    for race in upcoming_races:
        venue = race['venue']
        race_number = race['race_number']
        
        # Strategy: Find WIN market first (has race number), then find adjacent PLACE market
        # WIN markets have format "R1 ...", "R2 ...", etc.
        # PLACE markets are "To Be Placed" and come right after WIN market
        
        query = """
            SELECT DISTINCT 
                place_mc.MarketId, 
                place_mc.MarketName,
                place_mc.EventName,
                place_mc.OpenDate
            FROM MarketCatalogue place_mc
            WHERE place_mc.EventName LIKE ? 
            AND place_mc.EventName LIKE ?
            AND (place_mc.MarketName LIKE '%To Be Placed%' OR place_mc.MarketName LIKE '%TBP%')
            AND EXISTS (
                SELECT 1 FROM MarketCatalogue win_mc
                WHERE win_mc.EventName = place_mc.EventName
                AND win_mc.MarketName LIKE ?
                AND CAST(SUBSTR(win_mc.MarketId, INSTR(win_mc.MarketId, '.') + 1) AS INTEGER) < 
                    CAST(SUBSTR(place_mc.MarketId, INSTR(place_mc.MarketId, '.') + 1) AS INTEGER)
                AND CAST(SUBSTR(place_mc.MarketId, INSTR(place_mc.MarketId, '.') + 1) AS INTEGER) - 
                    CAST(SUBSTR(win_mc.MarketId, INSTR(win_mc.MarketId, '.') + 1) AS INTEGER) = 1
            )
            LIMIT 1
        """
        
        cursor = market_conn.execute(query, (
            f'%{venue}%',
            f'%{today_str}%',
            f'R{race_number} %'
        ))
        
        row = cursor.fetchone()
        if row:
            matched_races.append({
                'market_id': row[0],
                'market_name': row[1],
                'track': row[2],
                'race_time': row[3],
                'venue': venue,
                'race_number': race_number,
                'mins_until': race['mins_until']
            })
    
    market_conn.close()
    
    print(f"   ✅ Matched {len(matched_races)} PLACE markets")
    return matched_races

def get_current_odds(market_id):
    """Get current odds from Betfair API via backend"""
    try:
        url = f"{BACKEND_URL}/api/horse-racing/market-book/{market_id}"
        print(f"      🔍 Fetching odds from: {url}")
        response = requests.get(url, timeout=10)
        print(f"      📡 Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"      ❌ Bad status code: {response.status_code}")
            return None
        
        data = response.json()
        runners = data.get('runners', [])
        print(f"      👥 Found {len(runners)} runners")
        
        # Build odds map: selection_id -> {odds, status}
        odds_map = {}
        for runner in runners:
            selection_id = runner.get('selectionId')
            status = runner.get('status', 'ACTIVE')
            
            # Get best back price (what we can bet at)
            ex = runner.get('ex', {})
            available_to_back = ex.get('availableToBack', [])
            
            if available_to_back and len(available_to_back) > 0:
                best_back_price = available_to_back[0].get('price')
                if best_back_price and selection_id:
                    odds_map[selection_id] = {
                        'odds': best_back_price,
                        'status': status
                    }
        
        print(f"      💰 Built odds map with {len(odds_map)} runners with odds")
        if odds_map:
            fav = min(odds_map.items(), key=lambda x: x[1]['odds'])
            print(f"      ⭐ Favorite: {fav[1]['odds']}")
        
        return odds_map if odds_map else None
        
    except Exception as e:
        print(f"      ❌ Error getting odds: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_race_features(market_id):
    """Get runner names and basic info from HorseMarketBook"""
    try:
        conn = sqlite3.connect(BETFAIR_DB)
        
        query = """
            SELECT DISTINCT
                hmb.SelectionId,
                hmb.RUNNER_NAME,
                hmb.FORM,
                hmb.DAYS_SINCE_LAST_RUN,
                hmb.WEIGHT_VALUE,
                hmb.OFFICIAL_RATING,
                hmb.AGE,
                hmb.JOCKEY_CLAIM,
                hmb.STALL_DRAW
            FROM HorseMarketBook hmb
            WHERE hmb.MarketId = ?
        """
        
        df = pd.read_sql_query(query, conn, params=(market_id,))
        conn.close()
        
        return df if not df.empty else None
        
    except Exception as e:
        print(f"Error getting race features: {e}")
        return None

def place_paper_bet(bet_type, market_id, selection_id, horse_name, race_time, track, venue, race_number,
                    odds, stake, model_prob, market_prob, edge):
    """Record a paper bet in the database"""
    conn = sqlite3.connect(PAPER_TRADES_DB)
    cursor = conn.cursor()
    
    timestamp = datetime.now(pytz.timezone('Australia/Sydney'))
    
    # Use the correct column names for the existing paper_trades table
    cursor.execute('''
        INSERT INTO paper_trades 
        (bet_type, market_id, selection_id, horse_name, race_time, track, 
         race_number, model_probability, market_probability, edge, odds_taken, stake, 
         result, venue, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        bet_type,
        market_id,
        selection_id,
        horse_name,
        race_time,
        track,
        race_number,
        model_prob,
        market_prob,
        edge,
        odds,
        stake,
        'PENDING',
        venue,
        f'PLACE bet placed at {timestamp.isoformat()}'
    ))
    
    conn.commit()
    conn.close()
    
    print(f"         💾 Bet recorded in database")

def evaluate_and_bet_on_race(market_id, market_name, race_info, models):
    """
    MARKET-BASED BETTING (NO ML)
    Simple rule: Bet on favorite if odds are 1.5-3.0 (PLACE only)
    Uses tiered Kelly staking based on proven edges
    """
    
    # Only bet on PLACE markets
    if 'Place' not in market_name and 'place' not in market_name.lower():
        print(f"\n   ⏭️  SKIPPING: Not a PLACE market")
        return False
    
    # Skip maiden races  
    if 'Mdn' in market_name or 'mdn' in market_name.lower():
        print(f"\n   ⏭️  SKIPPING MAIDEN RACE: {market_name}")
        return False
    
    print(f"\n   📊 Evaluating PLACE market (MARKET-BASED strategy)...")
    
    # Get current odds
    odds_data = get_current_odds(market_id)
    if not odds_data:
        print("      ❌ Could not get odds")
        return False
    
    # Get runner names for display
    runner_data = get_race_features(market_id)
    if runner_data is None or runner_data.empty:
        print("      ❌ Could not get runner names")
        return False
    
    # Build a map of selection_id -> runner_name for display
    runner_names = {}
    for _, runner in runner_data.iterrows():
        runner_names[runner['SelectionId']] = runner['RUNNER_NAME']
    
    # Find the best horse to bet on (sorted by odds, preferring favorites)
    bet = get_horse_to_bet_on(odds_data)
    
    if not bet:
        print(f"      ⏭️  No bet: No horses with odds in profitable range (1.5-3.0)")
        return False
    
    selection_id, odds, stake, edge = bet
    horse_name = runner_names.get(selection_id, f"Selection {selection_id}")
    
    # Determine if this is the favorite, 2nd favorite, etc.
    sorted_horses = sorted(odds_data.items(), key=lambda x: x[1]['odds'])
    rank = next(i for i, (sid, _) in enumerate(sorted_horses, 1) if sid == selection_id)
    rank_str = {1: "FAVORITE", 2: "2nd FAVORITE", 3: "3rd FAVORITE"}.get(rank, f"{rank}th FAVORITE")
    
    # Show bet decision
    print(f"\n      ✅ BET FOUND!")
    print(f"         Horse: {horse_name} ({rank_str})")
    print(f"         Odds: {odds:.2f}")
    print(f"         Edge: {edge*100:.2f}% (proven from 17,446 races)")
    print(f"         Stake: ${stake:.2f} (Kelly: {KELLY_FRACTION*100:.0f}%)")
    print(f"         Potential return: ${stake * odds:.2f}")
    
    # Place the bet
    place_paper_bet(
        bet_type='PLACE',
        market_id=market_id,
        selection_id=selection_id,
        horse_name=horse_name,
        race_time=race_info['race_time'],
        track=race_info.get('track', race_info.get('venue', 'Unknown')),
        venue=race_info.get('venue', 'Unknown'),
        race_number=race_info.get('race_number', 0),
        odds=odds,
        stake=stake,
        model_prob=None,  # No model probability
        market_prob=1/odds,  # Market-implied probability
        edge=edge
    )
    
    print(f"         💾 Bet recorded in database")
    print(f"\n      ✅ Bet placed successfully!")
    return True

def monitor_and_bet():
    """Main monitoring loop - MARKET-BASED PLACE BETTING"""
    print("=" * 70)
    print("🏇 PAPER TRADING SYSTEM - MARKET-BASED (NO ML)")
    print("=" * 70)
    print(f"\nConfig:")
    print(f"   Bankroll: ${PAPER_BANKROLL:,.2f}")
    print(f"   Strategy: Bet on best favorite in 1.5-3.0 range (PLACE only)")
    print(f"   Priority: Favorite > 2nd fav > 3rd fav > etc. (first one in range)")
    print(f"   Proven edges from 17,446 races:")
    print(f"      • 1.5-2.0 odds: +3.96% ROI")
    print(f"      • 2.0-3.0 odds: +6.92% ROI")  
    print(f"   Staking: Tiered Kelly ({KELLY_FRACTION*100:.0f}% Kelly)")
    print(f"   Expected: ~5% ROI overall")
    print(f"   Betting window: Within {MINUTES_BEFORE_RACE} mins of race")
    
    print("\n📦 Initializing database...")
    init_paper_trades_db()
    
    print("📊 Loading strategy (no ML models needed)...")
    models = load_models()
    
    print("\n⏰ Starting monitoring loop (Ctrl+C to stop)...")
    print("   Checking every 30 seconds for upcoming races...\n")
    
    processed_markets = set()
    
    try:
        while True:
            try:
                upcoming = get_upcoming_races()
            except Exception as e:
                print(f"\n❌ Error getting upcoming races: {e}")
                print("   Waiting 30 seconds before retry...")
                time.sleep(30)
                continue
            
            races_evaluated = 0
            for race in upcoming:
                market_id = race['market_id']
                market_name = race['market_name']
                
                # Check if already processed
                if market_id in processed_markets:
                    continue
                
                # Skip races that already started
                if race['mins_until'] < 0:
                    continue
                
                # Only process races within betting window
                if race['mins_until'] > MINUTES_BEFORE_RACE + 0.5:
                    continue
                
                # Mark as processed
                processed_markets.add(market_id)
                
                print(f"\n{'='*70}")
                print(f"🎯 {race['track']} - {market_name}")
                print(f"   Race time: {race['race_time']}")
                print(f"   Time until race: {race['mins_until']:.1f} mins")
                print(f"{'='*70}")
                
                # Evaluate and potentially bet
                evaluate_and_bet_on_race(market_id, market_name, race, models)
                races_evaluated += 1
            
            # Show status if no races were evaluated
            if races_evaluated == 0 and len(upcoming) == 0:
                print(f"   ℹ️  No matching markets found - waiting 30 seconds...")
            
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped")
        print(f"   Total markets processed: {len(processed_markets)}")

def main():
    print("Starting paper trading system...")
    monitor_and_bet()

if __name__ == "__main__":
    print("Script starting...")
    main()
    print("Script ending...")
