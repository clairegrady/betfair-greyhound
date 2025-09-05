#!/usr/bin/env python3
import sqlite3
import datetime
import sys

def format_currency(amount):
    return f"£{amount:.2f}"

def format_percentage(value):
    return f"{value:.1%}"

def create_simulated_bets_table(cursor):
    """Create the SimulatedBets table if it doesn't exist"""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SimulatedBets (
        Id INTEGER PRIMARY KEY AUTOINCREMENT,
        MarketId TEXT NOT NULL,
        SelectionId INTEGER NOT NULL,
        HorseName TEXT,
        BetType TEXT NOT NULL,
        Stake DECIMAL(10,2) NOT NULL,
        Odds DECIMAL(10,2),
        MLConfidence DECIMAL(5,4),
        MarketPosition INTEGER,
        PlacedAt DATETIME NOT NULL,
        EventTime DATETIME,
        EventName TEXT,
        MarketName TEXT,
        DaysOff INTEGER,
        Status INTEGER NOT NULL,
        Notes TEXT,
        SettledAt DATETIME,
        Result TEXT,
        ProfitLoss DECIMAL(10,2)
    )
    ''')

def place_initial_bets(cursor):
    """Place the initial simulated bets"""
    now = datetime.datetime.now(datetime.UTC)
    
    # Define the initial bets (Canterbury Park race)
    initial_bets = [
        {
            'market_id': '1.246847916',
            'selection_id': 76119457,
            'horse_name': 'Lemon Sohn',
            'stake': 15.0,
            'odds': 3.5,
            'confidence': 0.75,
            'position': 1
        },
        {
            'market_id': '1.246847916', 
            'selection_id': 10189136,
            'horse_name': 'Tygra',
            'stake': 10.0,
            'odds': 4.2,
            'confidence': 0.65,
            'position': 2
        },
        {
            'market_id': '1.246847916',
            'selection_id': 71023278,
            'horse_name': 'Moral Dilemma',
            'stake': 20.0,
            'odds': 2.8,
            'confidence': 0.85,
            'position': 1
        },
        {
            'market_id': '1.246847916',
            'selection_id': 81814574,
            'horse_name': 'Flat Out Blessed',
            'stake': 12.0,
            'odds': 5.5,
            'confidence': 0.60,
            'position': 3
        },
        {
            'market_id': '1.246847916',
            'selection_id': 85872043,
            'horse_name': 'Lazy Y Girvin',
            'stake': 8.0,
            'odds': 6.7,
            'confidence': 0.55,
            'position': 4
        }
    ]
    
    print("🎯 Placing initial simulated bets...")
    
    for i, bet in enumerate(initial_bets, 1):
        cursor.execute('''
            INSERT INTO SimulatedBets (
                MarketId, SelectionId, HorseName, BetType, Stake, Odds, 
                MLConfidence, MarketPosition, PlacedAt, EventTime, 
                EventName, MarketName, Status, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bet['market_id'],
            bet['selection_id'],
            bet['horse_name'],
            'WIN',
            bet['stake'],
            bet['odds'],
            bet['confidence'],
            bet['position'],
            now,
            now + datetime.timedelta(hours=1),
            'Canterbury Park (US) 20th Aug',
            'R2 5f Mdn',
            0,  # Pending status
            f'Initial bet placed with {bet["confidence"]:.1%} confidence'
        ))
        
        print(f"✅ Bet {i}: {bet['horse_name']} - £{bet['stake']} @ {bet['odds']}")

def add_additional_bets(cursor):
    """Add bets on different races with real horse names"""
    now = datetime.datetime.now(datetime.UTC)
    
    # Additional bets with real horse data
    additional_bets = [
        {
            'market_id': '1.246847919',
            'selection_id': 86867605,
            'horse_name': 'Little Miss Linda',
            'stake': 25.0,
            'odds': 2.1,
            'confidence': 0.90,
            'position': 1,
            'event_name': 'Penn National (US) 20th Aug',
            'market_name': 'R3 1m Mdn Claim'
        },
        {
            'market_id': '1.246847946',
            'selection_id': 61076936,
            'horse_name': 'Warrior Bernice',
            'stake': 18.0,
            'odds': 3.8,
            'confidence': 0.70,
            'position': 2,
            'event_name': 'Penn National (US) 20th Aug',
            'market_name': 'R4 1m Claim'
        },
        {
            'market_id': '1.246847957',
            'selection_id': 50512666,
            'horse_name': 'Practicality',
            'stake': 30.0,
            'odds': 1.8,
            'confidence': 0.95,
            'position': 1,
            'event_name': 'Presque Isle Downs (US) 20th Aug',
            'market_name': 'R8 6f Claim'
        },
        {
            'market_id': '1.246847958',
            'selection_id': 57385263,
            'horse_name': 'Weekend Concerto',
            'stake': 14.0,
            'odds': 4.5,
            'confidence': 0.68,
            'position': 3,
            'event_name': 'Mountaineer (US) 20th Aug',
            'market_name': 'R1 7f Allw'
        }
    ]
    
    print("\n🎯 Adding bets on additional races...")
    
    for i, bet in enumerate(additional_bets, 1):
        cursor.execute('''
            INSERT INTO SimulatedBets (
                MarketId, SelectionId, HorseName, BetType, Stake, Odds, 
                MLConfidence, MarketPosition, PlacedAt, EventTime, 
                EventName, MarketName, Status, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bet['market_id'],
            bet['selection_id'],
            bet['horse_name'],
            'WIN',
            bet['stake'],
            bet['odds'],
            bet['confidence'],
            bet['position'],
            now,
            now + datetime.timedelta(hours=2),
            bet['event_name'],
            bet['market_name'],
            0,  # Pending status
            f'Additional bet placed with {bet["confidence"]:.1%} confidence'
        ))
        
        print(f"✅ Additional Bet {i}: {bet['horse_name']} - £{bet['stake']} @ {bet['odds']}")

def show_portfolio_summary(cursor):
    """Display comprehensive portfolio summary"""
    print("\n" + "=" * 60)
    print("🎯 SIMULATED BETTING PORTFOLIO SUMMARY")
    print("=" * 60)
    
    # Get all pending bets
    cursor.execute('''
        SELECT HorseName, SelectionId, Stake, Odds, MLConfidence, MarketPosition, 
               EventName, MarketName, PlacedAt
        FROM SimulatedBets 
        WHERE Status = 0
        ORDER BY PlacedAt DESC
    ''')
    
    bets = cursor.fetchall()
    
    if not bets:
        print("No pending bets found.")
        return
    
    print(f"\n📊 Total Bets: {len(bets)}")
    print(f"🏇 Races: {len(set(bet[6] for bet in bets))}")
    
    # Calculate totals
    total_stake = sum(bet[2] for bet in bets)
    total_potential_profit = sum(bet[2] * (bet[3] - 1) for bet in bets)
    avg_confidence = sum(bet[4] for bet in bets) / len(bets)
    
    print(f"💰 Total Stake: {format_currency(total_stake)}")
    print(f"🎯 Potential Profit: {format_currency(total_potential_profit)}")
    print(f"📈 Average Confidence: {format_percentage(avg_confidence)}")
    
    print("\n" + "=" * 60)
    print("INDIVIDUAL BETS")
    print("=" * 60)
    
    # Group bets by race
    races = {}
    for bet in bets:
        event_name = bet[6]
        if event_name not in races:
            races[event_name] = []
        races[event_name].append(bet)
    
    for event_name, race_bets in races.items():
        print(f"\n🏁 {event_name}")
        print("-" * 40)
        
        race_stake = sum(bet[2] for bet in race_bets)
        race_potential = sum(bet[2] * (bet[3] - 1) for bet in race_bets)
        
        for bet in race_bets:
            horse_name, selection_id, stake, odds, confidence, position, _, market_name, placed_at = bet
            potential_profit = stake * (odds - 1)
            
            print(f"  {horse_name} (ID: {selection_id})")
            print(f"    Race: {market_name}")
            print(f"    Stake: {format_currency(stake)} @ {odds}")
            print(f"    Confidence: {format_percentage(confidence)}")
            print(f"    Position: {position}")
            print(f"    Potential: {format_currency(potential_profit)}")
            print()
        
        print(f"  Race Total: {format_currency(race_stake)} stake, {format_currency(race_potential)} potential profit")
    
    print("\n" + "=" * 60)
    print("PERFORMANCE METRICS")
    print("=" * 60)
    
    # Calculate ROI
    roi = (total_potential_profit / total_stake) * 100 if total_stake > 0 else 0
    print(f"📊 ROI: {roi:.1f}%")
    
    # Risk analysis
    high_confidence_bets = [bet for bet in bets if bet[4] >= 0.8]
    medium_confidence_bets = [bet for bet in bets if 0.6 <= bet[4] < 0.8]
    low_confidence_bets = [bet for bet in bets if bet[4] < 0.6]
    
    print(f"🔴 High Confidence (80%+): {len(high_confidence_bets)} bets")
    print(f"🟡 Medium Confidence (60-80%): {len(medium_confidence_bets)} bets")
    print(f"🟢 Low Confidence (<60%): {len(low_confidence_bets)} bets")
    
    # Stake distribution
    high_stakes = sum(bet[2] for bet in bets if bet[2] >= 20)
    medium_stakes = sum(bet[2] for bet in bets if 10 <= bet[2] < 20)
    low_stakes = sum(bet[2] for bet in bets if bet[2] < 10)
    
    print(f"\n💰 Stake Distribution:")
    print(f"  High Stakes (£20+): {format_currency(high_stakes)}")
    print(f"  Medium Stakes (£10-20): {format_currency(medium_stakes)}")
    print(f"  Low Stakes (<£10): {format_currency(low_stakes)}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if len(high_confidence_bets) > len(low_confidence_bets):
        print("✅ Good portfolio balance - more high confidence bets than low confidence")
    else:
        print("⚠️  Consider reducing low confidence bets")
    
    if avg_confidence >= 0.7:
        print("✅ Strong average confidence level")
    else:
        print("⚠️  Consider focusing on higher confidence selections")
    
    if roi >= 100:
        print("🎯 Excellent potential ROI")
    elif roi >= 50:
        print("📈 Good potential ROI")
    else:
        print("⚠️  Consider reviewing bet selection strategy")
    
    if bets:
        best_value = max(bets, key=lambda x: x[2] * (x[3] - 1) / x[2])
        highest_confidence = max(bets, key=lambda x: x[4])
        print(f"\n🎯 Best Value Bet: {best_value[0]}")
        print(f"🏆 Highest Confidence: {highest_confidence[0]} ({format_percentage(highest_confidence[4])})")

def main():
    """Main function to manage simulated betting"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "all"
    
    # Connect to the simulation database
    conn = sqlite3.connect('simulation.db')
    cursor = conn.cursor()
    
    try:
        if command in ["all", "place"]:
            # Create table and place bets
            create_simulated_bets_table(cursor)
            place_initial_bets(cursor)
            add_additional_bets(cursor)
            conn.commit()
            print("\n✅ All bets placed successfully!")
        
        if command in ["all", "summary"]:
            # Show portfolio summary
            show_portfolio_summary(cursor)
        
        if command == "clear":
            # Clear all bets
            cursor.execute("DELETE FROM SimulatedBets")
            conn.commit()
            print("🗑️  All simulated bets cleared!")
        
        if command == "help":
            print("Usage: python3 simulated_betting_manager.py [command]")
            print("Commands:")
            print("  all     - Place bets and show summary (default)")
            print("  place   - Place bets only")
            print("  summary - Show portfolio summary only")
            print("  clear   - Clear all bets")
            print("  help    - Show this help message")
    
    finally:
        conn.close()
    
    print("\n✅ Simulated betting manager complete!")

if __name__ == "__main__":
    main()
