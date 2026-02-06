"""
Feature engineering for OpenFPL model.
Computes rolling player, team, and opponent features from smartplay_data.csv
and Understat team match data (fetched from API on first run).

Adapted from the private SmartPlayFPL pipeline for public reproducibility.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from .constants import (
    WINDOWS, FPL_TO_UNDERSTAT, POS_MAP,
    PLAYER_FEATURES, PLAYER_FEATURE_ORDER,
    TEAM_FEATURES, TEAM_FEATURE_ORDER, OPPONENT_FEATURE_ORDER,
    MERGED_NUMERIC_COLS, TEAM_MATCHES_NUMERIC_COLS,
)


def fpl_to_us(name: str) -> str:
    """Convert FPL team name to Understat name."""
    return FPL_TO_UNDERSTAT.get(name, name)


def _season_to_understat(season: str) -> str:
    """Convert FPL season format '2024-25' to Understat format '2024'."""
    return season.split('-')[0]


def build_understat_team_matches(smartplay_csv: str) -> pd.DataFrame:
    """Fetch team match data from Understat API for all seasons in smartplay_data.

    Uses the league-level team data endpoint which includes ppda, deep,
    scored, missed, xG, xGA, pts — all fields needed for team rolling features.

    Caches the result as understat_team_matches.csv next to the input CSV.
    On subsequent runs, loads from cache instead of re-fetching.

    Args:
        smartplay_csv: Path to smartplay_data.csv

    Returns:
        DataFrame with columns matching the expected team matches format:
        season, date, scored, missed, xG, xGA, deep, deep_allowed,
        ppda_att, ppda_def, ppda_allowed_att, ppda_allowed_def,
        understat_team, is_home, pts
    """
    cache_path = Path(smartplay_csv).parent / 'understat_team_matches.csv'

    if cache_path.exists():
        print(f"  Loading cached team matches from {cache_path}")
        return pd.read_csv(cache_path)

    print("  Fetching team match data from Understat API...")
    from understatapi import UnderstatClient

    # Read smartplay_data to discover which seasons we need
    sp = pd.read_csv(smartplay_csv, usecols=['season'])
    seasons = sorted(sp['season'].unique())

    all_rows = []
    with UnderstatClient() as client:
        for season in seasons:
            us_season = _season_to_understat(season)
            print(f"  Season {season}...")

            try:
                team_data = client.league(league='EPL').get_team_data(season=us_season)
            except Exception as e:
                print(f"    WARNING: Failed to fetch EPL {us_season}: {e}")
                continue

            for team_id, team_info in team_data.items():
                team_title = team_info['title']  # e.g. "Manchester City"

                for m in team_info['history']:
                    ppda = m.get('ppda', {})
                    ppda_allowed = m.get('ppda_allowed', {})

                    is_home = 1.0 if m.get('h_a') == 'h' else 0.0

                    all_rows.append({
                        'season': season,
                        'date': m['date'],
                        'result': m.get('result', ''),
                        'xG': float(m.get('xG', 0)),
                        'xGA': float(m.get('xGA', 0)),
                        'scored': int(m.get('scored', 0)),
                        'missed': int(m.get('missed', 0)),
                        'deep': int(m.get('deep', 0)),
                        'deep_allowed': int(m.get('deep_allowed', 0)),
                        'ppda_att': float(ppda.get('att', 0)),
                        'ppda_def': float(ppda.get('def', 0)),
                        'ppda_allowed_att': float(ppda_allowed.get('att', 0)),
                        'ppda_allowed_def': float(ppda_allowed.get('def', 0)),
                        'understat_team': team_title,
                        'is_home': is_home,
                        'pts': float(m.get('pts', 0)),
                    })

            print(f"    {len(team_data)} teams, "
                  f"{sum(len(t['history']) for t in team_data.values())} matches")

    df = pd.DataFrame(all_rows)
    df.to_csv(cache_path, index=False)
    print(f"  Cached {len(df)} team match rows to {cache_path}")
    return df


def load_data(smartplay_csv: str):
    """Load and prepare smartplay_data.csv and team match data.

    Args:
        smartplay_csv: Path to smartplay_data.csv

    Returns:
        merged: DataFrame with player-match rows, cross-season player_uid
        team_matches: DataFrame with team-match rows
    """
    # low_memory=False avoids mixed-dtype inference warnings on large CSVs.
    merged = pd.read_csv(smartplay_csv, low_memory=False)
    merged['kickoff_time'] = pd.to_datetime(merged['kickoff_time'], utc=True)
    merged['match_date'] = pd.to_datetime(merged['match_date'])
    merged['team_us'] = merged['team_name'].apply(fpl_to_us)
    merged['opponent_us'] = merged['us_opponent']
    merged['pos'] = merged['position'].map(POS_MAP)

    for col in MERGED_NUMERIC_COLS:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce').fillna(0)
    merged['is_home'] = pd.to_numeric(merged['is_home'], errors='coerce').fillna(0).astype(bool)

    # Cross-season player linking via understat_id (consistent across seasons).
    # Falls back to element+season for players without understat coverage.
    merged['player_uid'] = merged['understat_id'].fillna(
        merged['element'].astype(str) + '_' + merged['season']
    ).astype(str)

    # Fetch/load team matches
    team_matches = build_understat_team_matches(smartplay_csv)
    team_matches['date'] = pd.to_datetime(team_matches['date'])
    team_matches['date_only'] = team_matches['date'].dt.date
    for col in TEAM_MATCHES_NUMERIC_COLS:
        if col in team_matches.columns:
            team_matches[col] = pd.to_numeric(team_matches[col], errors='coerce').fillna(0)

    return merged, team_matches


def build_opponent_lookup(team_matches: pd.DataFrame) -> pd.DataFrame:
    """For each team-match row, identify the opponent team.

    Pairs home/away teams sharing the same date+time using score and xG
    to disambiguate when multiple matches kick off simultaneously.
    """
    tm = team_matches.copy()
    tm['date_str'] = tm['date'].dt.strftime('%Y-%m-%d %H:%M')

    opp_lookup = {}

    for ds in tm['date_str'].unique():
        slot = tm[tm['date_str'] == ds]
        home = slot[slot['is_home'] == 1.0]
        away = slot[slot['is_home'] == 0.0]

        away_matched = set()
        for _, h in home.iterrows():
            best_team = None
            best_diff = float('inf')
            for _, a in away.iterrows():
                if a['understat_team'] in away_matched:
                    continue
                if h['scored'] == a['missed'] and h['missed'] == a['scored']:
                    xg_diff = abs(h['xG'] - a['xGA']) + abs(h['xGA'] - a['xG'])
                    if xg_diff < best_diff:
                        best_diff = xg_diff
                        best_team = a['understat_team']
            if best_team is not None:
                opp_lookup[(h['understat_team'], ds)] = best_team
                opp_lookup[(best_team, ds)] = h['understat_team']
                away_matched.add(best_team)

    tm['opponent'] = tm.apply(
        lambda r: opp_lookup.get((r['understat_team'], r['date_str']), None), axis=1)

    return tm


def compute_league_ranks(team_matches: pd.DataFrame) -> dict:
    """Compute league rank for each team before each match in each season.

    Rank based on points, then goal difference, then goals scored.

    Returns:
        dict of (team, season, date_str) -> rank
    """
    tm = team_matches.sort_values(['season', 'date', 'understat_team']).copy()
    ranks = {}

    for season in tm['season'].unique():
        season_data = tm[tm['season'] == season].copy()
        teams = season_data['understat_team'].unique()
        cumulative = {t: {'gd': 0, 'gs': 0, 'pts': 0} for t in teams}

        dates = sorted(season_data['date'].unique())
        for date in dates:
            # Rank BEFORE this date's matches
            team_stats = [(t, cumulative[t]['gd'], cumulative[t]['gs'], cumulative[t]['pts'])
                          for t in teams]
            team_stats.sort(key=lambda x: (-x[3], -x[1], -x[2]))

            rank_map = {}
            for rank, (team, _, _, _) in enumerate(team_stats, 1):
                rank_map[team] = rank

            date_str = pd.Timestamp(date).strftime('%Y-%m-%d %H:%M')
            date_matches = season_data[season_data['date'] == date]
            for _, row in date_matches.iterrows():
                team = row['understat_team']
                ranks[(team, season, date_str)] = rank_map.get(team, 10)

            # Update cumulative stats after recording ranks
            for _, row in date_matches.iterrows():
                team = row['understat_team']
                cumulative[team]['gd'] += row['scored'] - row['missed']
                cumulative[team]['gs'] += row['scored']
                cumulative[team]['pts'] += row['pts'] if 'pts' in row.index else 0

    return ranks


def compute_team_rolling(team_matches: pd.DataFrame, league_ranks: dict):
    """Compute rolling features for each team.

    Returns:
        tm: DataFrame with rolling columns appended
        rolling_cols: list of column names added
    """
    tm = team_matches.sort_values(['understat_team', 'date']).copy()

    tm['league_rank'] = tm.apply(
        lambda r: league_ranks.get(
            (r['understat_team'], r['season'], r['date'].strftime('%Y-%m-%d %H:%M')), 10),
        axis=1)
    tm['opp_league_rank'] = tm.apply(
        lambda r: league_ranks.get(
            (r['opponent'], r['season'], r['date'].strftime('%Y-%m-%d %H:%M')), 10)
        if pd.notna(r['opponent']) else 10,
        axis=1)

    rolling_cols = []
    for src_col, feat_name in TEAM_FEATURES.items():
        for w in WINDOWS:
            col_name = f'team_{feat_name}_{w}'
            tm[col_name] = (
                tm.groupby('understat_team')[src_col]
                .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
            )
            rolling_cols.append(col_name)

    tm['status_league_rank'] = tm['league_rank']
    tm['status_opp_league_rank'] = tm['opp_league_rank']

    return tm, rolling_cols


def compute_player_rolling(merged: pd.DataFrame):
    """Compute rolling features for each player.

    Uses player_uid (understat_id where available) for cross-season continuity.

    Returns:
        pm: DataFrame with rolling columns appended
        rolling_cols: list of column names added
    """
    pm = merged.sort_values(['player_uid', 'kickoff_time']).copy()

    rolling_cols: list[str] = []
    new_cols: dict[str, np.ndarray] = {}

    for src_col, feat_name in PLAYER_FEATURES.items():
        grouped = pm.groupby('player_uid')[src_col]
        for w in WINDOWS:
            col_name = f'player_{feat_name}_{w}'
            new_cols[col_name] = grouped.transform(
                lambda x: x.shift(1).rolling(w, min_periods=1).mean()
            ).to_numpy()
            rolling_cols.append(col_name)

    # Venue-specific (home/away) relevant FPL points
    grouped_points = pm.groupby(['player_uid', 'is_home'])['total_points']
    for w in WINDOWS:
        col_name = f'player_relevant_fpl_points_{w}'
        new_cols[col_name] = grouped_points.transform(
            lambda x: x.shift(1).rolling(w, min_periods=1).mean()
        ).to_numpy()
        rolling_cols.append(col_name)

    # Add all rolling columns in one concat to avoid DataFrame fragmentation warnings.
    pm = pd.concat([pm, pd.DataFrame(new_cols, index=pm.index)], axis=1)

    return pm, rolling_cols


def build_samples(
    player_df: pd.DataFrame,
    team_df: pd.DataFrame,
    team_rolling_cols: list,
    season: str,
    gws: list,
) -> pd.DataFrame:
    """Build the 235-column OpenFPL samples DataFrame.

    Args:
        player_df: Output from compute_player_rolling
        team_df: Output from compute_team_rolling
        team_rolling_cols: Column names from compute_team_rolling
        season: e.g. '2025-26'
        gws: list of gameweek numbers to include

    Returns:
        DataFrame with 235 feature columns + metadata columns prefixed with '_'
    """
    targets = player_df[
        (player_df['season'] == season) &
        (player_df['gameweek'].isin(gws))
    ].copy()

    targets['match_date_only'] = targets['match_date'].dt.date

    # Prepare team features for join
    team_join = team_df[['understat_team', 'date_only'] + team_rolling_cols +
                        ['status_league_rank', 'status_opp_league_rank']].copy()
    team_join = team_join.drop_duplicates(subset=['understat_team', 'date_only'])

    # Join team rolling features (player's team)
    targets = targets.merge(
        team_join.rename(columns={'understat_team': '_team', 'date_only': '_date'}),
        left_on=['team_us', 'match_date_only'],
        right_on=['_team', '_date'],
        how='left'
    )
    targets.drop(columns=['_team', '_date'], inplace=True, errors='ignore')

    # Join opponent rolling features
    opp_rename = {}
    for col in team_rolling_cols:
        opp_rename[col] = col.replace('team_', 'opp_', 1)
    opp_rename['status_league_rank'] = 'opp_status_league_rank'
    opp_rename['status_opp_league_rank'] = 'opp_status_opp_league_rank'

    opp_join = team_join.rename(columns=opp_rename)
    opp_join = opp_join.rename(columns={'understat_team': '_opp_team', 'date_only': '_opp_date'})

    targets = targets.merge(
        opp_join,
        left_on=['opponent_us', 'match_date_only'],
        right_on=['_opp_team', '_opp_date'],
        how='left'
    )
    targets.drop(columns=['_opp_team', '_opp_date'], inplace=True, errors='ignore')

    # Build the 235-column DataFrame in exact OpenFPL column order
    rows = []
    for _, r in targets.iterrows():
        row = {}
        # 7 metadata columns
        row['season'] = r['season']
        row['gw'] = int(r['gameweek'])
        row['position'] = r['pos']
        row['player'] = r['player_name']
        row['team'] = r['team_us']
        row['opponent'] = r['opponent_us']
        row['home'] = bool(r['is_home'])

        # Player features (23 features x 5 windows = 115 columns)
        for feat in PLAYER_FEATURE_ORDER:
            col_prefix = f'player_{feat}'
            for w in WINDOWS:
                col = f'{col_prefix}_{w}'
                row[f'player {feat.replace("_", " ")} {w}'] = r.get(col, np.nan)

        # Team features (12 features x 5 windows = 60 columns)
        for feat in TEAM_FEATURE_ORDER:
            for w in WINDOWS:
                col = f'team_{feat}_{w}'
                row[f'team {feat.replace("_", " ")} {w}'] = r.get(col, np.nan)

        # Opponent features (10 features x 5 windows = 50 columns)
        for feat in OPPONENT_FEATURE_ORDER:
            for w in WINDOWS:
                col = f'opp_{feat}_{w}'
                row[f'opponent {feat.replace("_", " ")} {w}'] = r.get(col, np.nan)

        # 3 status features
        row['status player availability'] = 1.0
        row['status team league rank'] = r.get('status_league_rank', np.nan)
        row['status opponent league rank'] = r.get('opp_status_league_rank', np.nan)

        # Metadata for downstream comparison (prefixed with '_')
        row['_element'] = r['element']
        row['_total_points'] = r['total_points']
        row['_minutes'] = r['minutes']
        row['_ep_next'] = r.get('expected_points', 0)

        rows.append(row)

    samples = pd.DataFrame(rows)
    return samples
