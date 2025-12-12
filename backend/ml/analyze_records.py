import pandas as pd

df = pd.read_csv('ml/data/fpl_gameweek_data_clean.csv')

# Count records per player
records_per_player = df.groupby('player_id').size()

print('=' * 60)
print('RECORDS PER PLAYER ANALYSIS')
print('=' * 60)
print()
print(f'Total players: {df["player_id"].nunique()}')
print(f'Total records: {len(df)}')
print(f'Max possible GWs: 14')
print(f'Theoretical max records: {756 * 14:,} (756 x 14)')
print(f'Actual records: {len(df):,}')
print(f'Missing records: {756 * 14 - len(df)}')
print()
print('Records per player distribution:')
print(records_per_player.describe())
print()
print('Breakdown by GW count:')
for gw_count in sorted(records_per_player.unique()):
    count = (records_per_player == gw_count).sum()
    print(f'  {gw_count:2d} GWs: {count:3d} players ({count/756*100:5.1f}%)')
