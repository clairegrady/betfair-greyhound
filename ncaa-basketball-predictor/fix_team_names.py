"""
Fix team name mismatches between games and teams tables
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ncaa_basketball.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("🔧 FIXING TEAM NAME MISMATCHES\n")

# Get all team names from games table
cursor.execute("""
    SELECT DISTINCT home_team_name FROM games
    UNION
    SELECT DISTINCT away_team_name FROM games
    ORDER BY 1
""")
game_teams = [row[0] for row in cursor.fetchall()]

print(f"Found {len(game_teams)} unique team names in games table")

# For each game team, find or create matching team in teams table
fixed = 0
for game_team in game_teams:
    if not game_team:
        continue
    
    # Extract base name (e.g., "Duke" from "Duke Blue Devils")
    base_name = game_team.split()[0]  # First word
    
    # Check if we have this team
    cursor.execute("SELECT team_id, team_name, kenpom_name FROM teams WHERE team_name = ? OR kenpom_name = ?",
                   (game_team, game_team))
    result = cursor.fetchone()
    
    if result:
        continue  # Already good
    
    # Try to find by base name
    cursor.execute("""
        SELECT team_id, team_name, kenpom_name FROM teams 
        WHERE team_name LIKE ? OR kenpom_name LIKE ?
        LIMIT 1
    """, (f"{base_name}%", f"{base_name}%"))
    
    match = cursor.fetchone()
    
    if match:
        team_id, existing_name, existing_kenpom = match
        # Update to include both names
        if not existing_kenpom or existing_kenpom == existing_name:
            cursor.execute("""
                UPDATE teams 
                SET kenpom_name = ?,
                    team_name = ?
                WHERE team_id = ?
            """, (existing_name, game_team, team_id))
            fixed += 1
            print(f"✅ Linked '{game_team}' to existing '{existing_name}' (team_id={team_id})")

conn.commit()
print(f"\n✅ Fixed {fixed} team name mismatches")

# Now verify by checking how many games can find teams
cursor.execute("""
    SELECT COUNT(*) FROM games g
    WHERE EXISTS (
        SELECT 1 FROM teams t 
        WHERE t.team_name = g.home_team_name OR t.kenpom_name = g.home_team_name
    )
    AND EXISTS (
        SELECT 1 FROM teams t 
        WHERE t.team_name = g.away_team_name OR t.kenpom_name = g.away_team_name  
    )
""")
matched_games = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM games")
total_games = cursor.fetchone()[0]

print(f"\n📊 Verification:")
print(f"   Games with matched teams: {matched_games:,} / {total_games:,} ({matched_games/total_games*100:.1f}%)")

conn.close()

