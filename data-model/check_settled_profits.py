#!/usr/bin/env python3
import pandas as pd

# Read the performance CSV
df = pd.read_csv('simulation_performance.csv')

# Filter to only settled races (those with profit values)
settled_races = df[df['total_profit'].notna()]

print('Settled races with profits:')
for _, row in settled_races.iterrows():
    print(f'{row["venue"]} R{row["race_number"]} - {row["strategy"]} - ${row["total_profit"]:.2f}')

print(f'\nTotal settled race entries: {len(settled_races)}')

# Calculate totals by strategy
print('\nStrategy totals from settled races:')
for strategy in settled_races['strategy'].unique():
    strategy_data = settled_races[settled_races['strategy'] == strategy]
    total_profit = strategy_data['total_profit'].sum()
    total_stake = strategy_data['total_stake'].sum()
    roi = (total_profit / total_stake) * 100 if total_stake > 0 else 0
    print(f'{strategy}: ${total_profit:.2f} profit, ${total_stake:.2f} stake, {roi:.1f}% ROI')

# Overall totals
total_profit = settled_races['total_profit'].sum()
total_stake = settled_races['total_stake'].sum()
overall_roi = (total_profit / total_stake) * 100 if total_stake > 0 else 0
print(f'\nOverall: ${total_profit:.2f} profit, ${total_stake:.2f} stake, {overall_roi:.1f}% ROI')
