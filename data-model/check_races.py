#!/usr/bin/env python3

import pandas as pd
import sqlite3

# Read the performance CSV to check the data
df = pd.read_csv('simulation_performance.csv')

print("PERFORMANCE CSV ANALYSIS:")
print("=" * 50)

# Count unique races
unique_races = df[['venue', 'race_number', 'race_date']].drop_duplicates()
print(f"Total unique races: {len(unique_races)}")

# Count settled races
settled_races = df[df['total_profit'].notna()][['venue', 'race_number', 'race_date']].drop_duplicates()
print(f"Settled races: {len(settled_races)}")

# Count pending races
pending_races = len(unique_races) - len(settled_races)
print(f"Pending races: {pending_races}")

print(f"\nSettled races breakdown:")
settled_breakdown = settled_races.groupby(['venue']).size().sort_values(ascending=False)
print(settled_breakdown)

print(f"\nPending races breakdown:")
pending_breakdown = unique_races[~unique_races.set_index(['venue', 'race_number', 'race_date']).index.isin(settled_races.set_index(['venue', 'race_number', 'race_date']).index)]
pending_venues = pending_breakdown.groupby(['venue']).size().sort_values(ascending=False)
print(pending_venues)
