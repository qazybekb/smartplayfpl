#!/usr/bin/env python3
"""
Incremental updater for smartplay_data.csv.

Detects which gameweeks are missing from the public CSV and appends them
using FPL API (element-summary) + Understat (understatapi) data.

The output schema matches the 115-column format produced by
python/ml/data/pipeline/create_merged_dataset.py.

Usage:
    python update_smartplay_data.py                     # auto-detect missing GWs
    python update_smartplay_data.py --dry-run            # show what would be added
    python update_smartplay_data.py --season 2025-26     # only update this season
"""

import argparse
import ast
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SCRIPT_DIR = Path(__file__).parent
DATA_CSV = SCRIPT_DIR / "smartplay_data.csv"
MAPPINGS_DIR = SCRIPT_DIR / "mappings"

FPL_BASE = "https://fantasy.premierleague.com/api"
RATE_LIMIT_SLEEP = 0.35  # seconds between FPL API calls

# ---------- Column order (matches create_merged_dataset.py output) ----------

COLUMN_ORDER = [
    "season", "gameweek", "fpl_code", "understat_id", "element",
    "player_name", "team_name", "is_home", "match_date", "us_opponent",
    "name", "position", "team", "fixture", "opponent_team", "was_home",
    "kickoff_time", "total_points", "minutes", "goals_scored", "assists",
    "clean_sheets", "goals_conceded", "own_goals", "penalties_saved",
    "penalties_missed", "yellow_cards", "red_cards", "saves", "bonus", "bps",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "xP", "ict_index", "influence", "creativity",
    "threat", "value", "selected", "transfers_in", "transfers_out",
    "transfers_balance", "expected_points_pre_deadline", "expected_points",
    "expected_points_source", "cache_price", "cache_ownership_pct",
    "cache_transfers_in", "cache_transfers_out", "cache_form", "cache_status",
    "cache_chance_next_round", "cache_snapshot_datetime_utc",
    "us_team_xG", "us_team_xGA", "us_team_npxGD", "us_ppda", "us_opp_ppda",
    "us_deep", "us_deep_allowed",
    "team_a_score", "team_h_score", "GW", "starts",
    "mng_clean_sheets", "mng_draw", "mng_goals_scored", "mng_loss",
    "mng_underdog_draw", "mng_underdog_win", "mng_win", "modified",
    "clearances_blocks_interceptions", "defensive_contribution",
    "recoveries", "tackles", "opponent_team_name",
    "us_match_id", "us_position", "us_minutes", "us_goals", "us_assists",
    "us_shots", "us_key_passes", "us_xG", "us_xA", "us_npg", "us_npxG",
    "us_xGChain", "us_xGBuildup",
    "us_team_name", "team_xG_avg", "team_xGA_avg", "team_npxG_avg",
    "team_npxGA_avg", "team_deep_avg", "team_deep_allowed_avg",
    "team_goals_season", "team_conceded_season", "team_ppda_avg",
    "team_ppda_allowed_avg",
    "us_xG_per90", "us_xA_per90", "us_npxG_per90", "us_shots_per90",
    "us_key_passes_per90", "us_xGChain_per90", "us_xGBuildup_per90",
    "team_xGD_avg", "points_per_million", "goals_vs_xG", "assists_vs_xA",
]


# ============================================================================
#  FPL API helpers
# ============================================================================

def fpl_get(endpoint: str) -> dict:
    """GET from FPL API with retry."""
    url = f"{FPL_BASE}/{endpoint}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return {}


def load_bootstrap() -> dict:
    """Load FPL bootstrap-static and return parsed dicts."""
    data = fpl_get("bootstrap-static")
    return data


def infer_season() -> str:
    """Infer current FPL season string (e.g. '2025-26')."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    year = now.year
    if now.month >= 7:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


# ============================================================================
#  Mappings
# ============================================================================

def load_player_golden_record() -> pd.DataFrame:
    """Load players golden record for fpl_code -> understat_id mapping."""
    path = MAPPINGS_DIR / "players_golden_record.csv"
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df


def load_clubs_golden_record() -> pd.DataFrame:
    """Load clubs golden record for team name mappings."""
    path = MAPPINGS_DIR / "clubs_golden_record.csv"
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return pd.DataFrame()
    return pd.read_csv(path)


def build_team_lookups(bootstrap: dict, clubs_gr: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Build team lookup dicts.

    Returns:
        fpl_team_id_to_name: {1: 'Arsenal', ...}
        fpl_team_name_to_us: {'Arsenal': 'Arsenal', 'Man City': 'Manchester City', ...}
        fpl_team_code_to_name: {3: 'Arsenal', ...}
    """
    teams = bootstrap.get("teams", [])
    fpl_team_id_to_name = {t["id"]: t["name"] for t in teams}
    fpl_team_code_to_name = {t["code"]: t["name"] for t in teams}

    # Build FPL name -> Understat name from clubs GR
    fpl_team_name_to_us = {}
    if len(clubs_gr) > 0:
        for _, row in clubs_gr.iterrows():
            fpl_team_name_to_us[row["club_name"]] = row["understat_name"]

    return fpl_team_id_to_name, fpl_team_name_to_us, fpl_team_code_to_name


# ============================================================================
#  Understat
# ============================================================================

def load_understat_team_match_data(season_str: str) -> pd.DataFrame:
    """Fetch Understat team match data for the given season.

    Returns DataFrame keyed by (understat_team, is_home, date_only) with columns:
    us_team_xG, us_team_xGA, us_team_npxGD, us_ppda, us_deep, us_deep_allowed
    """
    try:
        from understatapi import UnderstatClient
    except ImportError:
        print("  WARNING: understatapi not installed. Understat team features will be NaN.")
        return pd.DataFrame()

    # Convert season string to Understat format (e.g. '2025-26' -> '2025')
    us_season = season_str.split("-")[0]

    print(f"  Fetching Understat team match data for season {us_season}...")
    try:
        with UnderstatClient() as us:
            raw = us.league(league="EPL").get_match_data(season=us_season)
    except Exception as e:
        print(f"  WARNING: Could not fetch Understat match data: {e}")
        return pd.DataFrame()

    if not raw:
        print("  No Understat match data returned.")
        return pd.DataFrame()

    records = []
    for match in raw:
        date_str = match.get("datetime", "")
        date_only = pd.to_datetime(date_str, errors="coerce")
        if pd.isna(date_only):
            continue
        date_only = date_only.date()

        # isResult indicates the match has been played
        if not match.get("isResult", False):
            continue

        h_team = match.get("h", {}).get("title", "")
        a_team = match.get("a", {}).get("title", "")
        h_xG = float(match.get("xG", {}).get("h", 0) or 0)
        a_xG = float(match.get("xG", {}).get("a", 0) or 0)

        # Extract team-level stats from forecast/statistics if available
        h_stats = match.get("h", {})
        a_stats = match.get("a", {})

        # Home team row
        records.append({
            "understat_team": h_team,
            "is_home": 1,
            "date_only": date_only,
            "us_team_xG": h_xG,
            "us_team_xGA": a_xG,
            "us_team_npxGD": np.nan,  # not available from match endpoint
        })
        # Away team row
        records.append({
            "understat_team": a_team,
            "is_home": 0,
            "date_only": date_only,
            "us_team_xG": a_xG,
            "us_team_xGA": h_xG,
            "us_team_npxGD": np.nan,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["understat_team", "is_home", "date_only"], keep="last")
    print(f"  Loaded {len(df)} Understat team-match rows")
    return df


def load_understat_team_season_stats(season_str: str) -> pd.DataFrame:
    """Fetch Understat team season-aggregate stats.

    Returns DataFrame with columns:
    us_team_name, team_xG_avg, team_xGA_avg, team_npxG_avg, team_npxGA_avg,
    team_deep_avg, team_deep_allowed_avg, team_goals_season, team_conceded_season,
    team_ppda_avg, team_ppda_allowed_avg
    """
    try:
        from understatapi import UnderstatClient
    except ImportError:
        return pd.DataFrame()

    us_season = season_str.split("-")[0]
    print(f"  Fetching Understat team season stats for {us_season}...")

    try:
        with UnderstatClient() as us:
            raw = us.league(league="EPL").get_team_data(season=us_season)
    except Exception as e:
        print(f"  WARNING: Could not fetch Understat team data: {e}")
        return pd.DataFrame()

    if not raw:
        return pd.DataFrame()

    records = []
    # raw is a dict {team_id: {id, title, history: [...]}}
    teams_iter = raw.values() if isinstance(raw, dict) else raw
    for team_data in teams_iter:
        title = team_data.get("title", "")
        history = team_data.get("history", [])
        if not history:
            continue

        hdf = pd.DataFrame(history)

        def _ppda_ratio(val):
            if pd.isna(val) if not isinstance(val, (dict, str)) else False:
                return np.nan
            if isinstance(val, str):
                try:
                    val = ast.literal_eval(val)
                except Exception:
                    return np.nan
            if isinstance(val, dict):
                att = float(val.get("att", 0))
                deff = float(val.get("def", 0))
                return att / deff if deff else np.nan
            return np.nan

        records.append({
            "us_team_name": title,
            "team_xG_avg": pd.to_numeric(hdf.get("xG"), errors="coerce").mean(),
            "team_xGA_avg": pd.to_numeric(hdf.get("xGA"), errors="coerce").mean(),
            "team_npxG_avg": pd.to_numeric(hdf.get("npxG"), errors="coerce").mean(),
            "team_npxGA_avg": pd.to_numeric(hdf.get("npxGA"), errors="coerce").mean(),
            "team_deep_avg": pd.to_numeric(hdf.get("deep"), errors="coerce").mean(),
            "team_deep_allowed_avg": pd.to_numeric(hdf.get("deep_allowed"), errors="coerce").mean(),
            "team_goals_season": pd.to_numeric(hdf.get("scored"), errors="coerce").sum(),
            "team_conceded_season": pd.to_numeric(hdf.get("missed"), errors="coerce").sum(),
            "team_ppda_avg": hdf["ppda"].apply(_ppda_ratio).mean() if "ppda" in hdf.columns else np.nan,
            "team_ppda_allowed_avg": hdf["ppda_allowed"].apply(_ppda_ratio).mean() if "ppda_allowed" in hdf.columns else np.nan,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    print(f"  Loaded season stats for {len(df)} teams")
    return df


def load_understat_match_deep_ppda(season_str: str) -> pd.DataFrame:
    """Fetch per-match deep/ppda from Understat team data history.

    The match endpoint doesn't have deep/ppda, but team history does.
    Returns DataFrame keyed by (understat_team, is_home, date_only).
    """
    try:
        from understatapi import UnderstatClient
    except ImportError:
        return pd.DataFrame()

    us_season = season_str.split("-")[0]
    try:
        with UnderstatClient() as us:
            raw = us.league(league="EPL").get_team_data(season=us_season)
    except Exception:
        return pd.DataFrame()

    if not raw:
        return pd.DataFrame()

    records = []
    teams_iter = raw.values() if isinstance(raw, dict) else raw
    for team_data in teams_iter:
        title = team_data.get("title", "")
        for match in team_data.get("history", []):
            date_str = match.get("date", "")
            date_only = pd.to_datetime(date_str, errors="coerce")
            if pd.isna(date_only):
                continue

            is_home = 1 if str(match.get("h_a", "")).lower() == "h" else 0

            def _ppda_ratio(val):
                if isinstance(val, str):
                    try:
                        val = ast.literal_eval(val)
                    except Exception:
                        return np.nan
                if isinstance(val, dict):
                    att = float(val.get("att", 0))
                    deff = float(val.get("def", 0))
                    return att / deff if deff else np.nan
                return np.nan

            records.append({
                "understat_team": title,
                "is_home": is_home,
                "date_only": date_only.date(),
                "us_deep": pd.to_numeric(match.get("deep"), errors="coerce") if match.get("deep") is not None else np.nan,
                "us_deep_allowed": pd.to_numeric(match.get("deep_allowed"), errors="coerce") if match.get("deep_allowed") is not None else np.nan,
                "us_ppda": _ppda_ratio(match.get("ppda")),
                "us_team_npxGD": pd.to_numeric(match.get("npxGD"), errors="coerce") if match.get("npxGD") is not None else np.nan,
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["understat_team", "is_home", "date_only"], keep="last")
    return df


# ============================================================================
#  Core: fetch missing GW data from FPL API
# ============================================================================

def fetch_missing_gw_data(
    missing_gws: list[int],
    bootstrap: dict,
    fpl_team_id_to_name: dict,
    fpl_team_name_to_us: dict,
    player_gr: pd.DataFrame,
    season: str,
) -> pd.DataFrame:
    """Fetch player-level data for missing gameweeks from FPL element-summary API.

    For each player, we call /api/element-summary/{element_id}/ which returns
    their full history including per-fixture breakdowns.
    """
    elements = bootstrap.get("elements", [])
    events = bootstrap.get("events", [])
    teams = bootstrap.get("teams", [])

    # Build element_id -> player info
    element_info = {}
    for p in elements:
        element_info[p["id"]] = {
            "element": p["id"],
            "fpl_code": p["code"],
            "name": p["web_name"],
            "first_name": p["first_name"],
            "second_name": p["second_name"],
            "position": {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}.get(p["element_type"], "UNK"),
            "team_id": p["team"],
        }

    # Build fpl_code -> understat_id from golden record
    code_to_us_id = {}
    if len(player_gr) > 0:
        for _, row in player_gr.iterrows():
            fpl_code = row.get("fpl_code")
            us_id = row.get("understat_player_id")
            if pd.notna(fpl_code) and pd.notna(us_id):
                code_to_us_id[int(fpl_code)] = int(us_id)

    # Build fixture_id -> fixture info from events/fixtures
    fixture_info = {}
    try:
        fixtures_data = fpl_get("fixtures")
        for f in fixtures_data:
            fixture_info[f["id"]] = {
                "kickoff_time": f.get("kickoff_time"),
                "team_h": f.get("team_h"),
                "team_a": f.get("team_a"),
                "team_h_score": f.get("team_h_score"),
                "team_a_score": f.get("team_a_score"),
                "event": f.get("event"),  # GW number
            }
    except Exception as e:
        print(f"  WARNING: Could not load fixtures: {e}")

    missing_gw_set = set(missing_gws)
    rows = []
    total = len(elements)
    print(f"  Fetching element-summary for {total} players...")

    for i, p in enumerate(elements):
        eid = p["id"]
        if (i + 1) % 50 == 0:
            print(f"    ... {i + 1}/{total}")

        try:
            summary = fpl_get(f"element-summary/{eid}/")
        except Exception as e:
            print(f"    WARNING: Failed to fetch element {eid}: {e}")
            continue

        time.sleep(RATE_LIMIT_SLEEP)

        info = element_info[eid]

        for h in summary.get("history", []):
            gw = h.get("round")
            if gw not in missing_gw_set:
                continue

            fix_id = h.get("fixture")
            fix = fixture_info.get(fix_id, {})
            opp_team_id = h.get("opponent_team")
            opp_team_name = fpl_team_id_to_name.get(opp_team_id, "")
            was_home = h.get("was_home", False)
            is_home = 1 if was_home else 0

            # Derive team from fixture, not bootstrap (handles mid-season transfers)
            if was_home:
                team_name = fpl_team_id_to_name.get(fix.get("team_h"), info["team_id"])
            else:
                team_name = fpl_team_id_to_name.get(fix.get("team_a"), info["team_id"])

            kickoff_time = fix.get("kickoff_time") or h.get("kickoff_time", "")
            kickoff_dt = pd.to_datetime(kickoff_time, utc=True, errors="coerce")
            match_date = str(kickoff_dt.date()) if pd.notna(kickoff_dt) else ""

            us_opponent = fpl_team_name_to_us.get(opp_team_name, opp_team_name)

            row = {
                "season": season,
                "gameweek": gw,
                "fpl_code": info["fpl_code"],
                "understat_id": code_to_us_id.get(info["fpl_code"], np.nan),
                "element": info["element"],
                "player_name": info["name"],
                "team_name": team_name,
                "is_home": is_home,
                "match_date": match_date,
                "us_opponent": us_opponent,
                "name": info["name"],
                "position": info["position"],
                "team": team_name,
                "fixture": fix_id,
                "opponent_team": opp_team_id,
                "was_home": was_home,
                "kickoff_time": kickoff_time,
                "total_points": h.get("total_points"),
                "minutes": h.get("minutes"),
                "goals_scored": h.get("goals_scored"),
                "assists": h.get("assists"),
                "clean_sheets": h.get("clean_sheets"),
                "goals_conceded": h.get("goals_conceded"),
                "own_goals": h.get("own_goals"),
                "penalties_saved": h.get("penalties_saved"),
                "penalties_missed": h.get("penalties_missed"),
                "yellow_cards": h.get("yellow_cards"),
                "red_cards": h.get("red_cards"),
                "saves": h.get("saves"),
                "bonus": h.get("bonus"),
                "bps": h.get("bps"),
                "expected_goals": h.get("expected_goals"),
                "expected_assists": h.get("expected_assists"),
                "expected_goal_involvements": h.get("expected_goal_involvements"),
                "expected_goals_conceded": h.get("expected_goals_conceded"),
                "xP": np.nan,  # not available from element-summary
                "ict_index": h.get("ict_index"),
                "influence": h.get("influence"),
                "creativity": h.get("creativity"),
                "threat": h.get("threat"),
                "value": h.get("value"),
                "selected": h.get("selected"),
                "transfers_in": h.get("transfers_in"),
                "transfers_out": h.get("transfers_out"),
                "transfers_balance": h.get("transfers_balance"),
                "expected_points_pre_deadline": np.nan,
                "expected_points": 0.0,
                "expected_points_source": "imputed_0",
                "cache_price": np.nan,
                "cache_ownership_pct": np.nan,
                "cache_transfers_in": np.nan,
                "cache_transfers_out": np.nan,
                "cache_form": np.nan,
                "cache_status": np.nan,
                "cache_chance_next_round": np.nan,
                "cache_snapshot_datetime_utc": np.nan,
                # Understat team match-level (populated later)
                "us_team_xG": np.nan,
                "us_team_xGA": np.nan,
                "us_team_npxGD": np.nan,
                "us_ppda": np.nan,
                "us_opp_ppda": np.nan,
                "us_deep": np.nan,
                "us_deep_allowed": np.nan,
                # FPL fixture scores
                "team_a_score": fix.get("team_a_score"),
                "team_h_score": fix.get("team_h_score"),
                "GW": gw,
                "starts": h.get("starts"),
                # Manager stats (not available from API)
                "mng_clean_sheets": np.nan,
                "mng_draw": np.nan,
                "mng_goals_scored": np.nan,
                "mng_loss": np.nan,
                "mng_underdog_draw": np.nan,
                "mng_underdog_win": np.nan,
                "mng_win": np.nan,
                "modified": np.nan,
                "clearances_blocks_interceptions": np.nan,
                "defensive_contribution": np.nan,
                "recoveries": np.nan,
                "tackles": np.nan,
                "opponent_team_name": opp_team_name,
                # Understat player match-level (not available via API)
                "us_match_id": np.nan,
                "us_position": np.nan,
                "us_minutes": np.nan,
                "us_goals": np.nan,
                "us_assists": np.nan,
                "us_shots": np.nan,
                "us_key_passes": np.nan,
                "us_xG": np.nan,
                "us_xA": np.nan,
                "us_npg": np.nan,
                "us_npxG": np.nan,
                "us_xGChain": np.nan,
                "us_xGBuildup": np.nan,
                # Understat team season-level (populated later)
                "us_team_name": np.nan,
                "team_xG_avg": np.nan,
                "team_xGA_avg": np.nan,
                "team_npxG_avg": np.nan,
                "team_npxGA_avg": np.nan,
                "team_deep_avg": np.nan,
                "team_deep_allowed_avg": np.nan,
                "team_goals_season": np.nan,
                "team_conceded_season": np.nan,
                "team_ppda_avg": np.nan,
                "team_ppda_allowed_avg": np.nan,
                # Derived (computed after merge)
                "us_xG_per90": np.nan,
                "us_xA_per90": np.nan,
                "us_npxG_per90": np.nan,
                "us_shots_per90": np.nan,
                "us_key_passes_per90": np.nan,
                "us_xGChain_per90": np.nan,
                "us_xGBuildup_per90": np.nan,
                "team_xGD_avg": np.nan,
                "points_per_million": np.nan,
                "goals_vs_xG": np.nan,
                "assists_vs_xA": np.nan,
            }
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=COLUMN_ORDER)

    df = pd.DataFrame(rows)
    print(f"  Fetched {len(df):,} player-fixture rows for GWs {sorted(missing_gws)}")
    return df


# ============================================================================
#  Merge Understat data into new rows
# ============================================================================

def merge_understat_into_rows(
    df: pd.DataFrame,
    season: str,
    fpl_team_name_to_us: dict,
) -> pd.DataFrame:
    """Enrich new rows with Understat team match + season data."""
    if len(df) == 0:
        return df

    # 1. Match-level xG from Understat matches endpoint
    us_matches = load_understat_team_match_data(season)
    # 2. Match-level deep/ppda from Understat team history endpoint
    us_deep_ppda = load_understat_match_deep_ppda(season)
    # 3. Season-level team aggregates
    us_team_season = load_understat_team_season_stats(season)

    df = df.copy()
    df["_team_us"] = df["team_name"].map(lambda x: fpl_team_name_to_us.get(x, x))
    df["_date_only"] = pd.to_datetime(df["match_date"], errors="coerce").dt.date

    # Merge match-level xG
    if len(us_matches) > 0:
        merge_cols = ["us_team_xG", "us_team_xGA", "us_team_npxGD"]
        df = df.drop(columns=merge_cols, errors="ignore")
        df = df.merge(
            us_matches[["understat_team", "is_home", "date_only"] + merge_cols],
            left_on=["_team_us", "is_home", "_date_only"],
            right_on=["understat_team", "is_home", "date_only"],
            how="left",
        ).drop(columns=["understat_team", "date_only"], errors="ignore")

    # Merge match-level deep/ppda
    if len(us_deep_ppda) > 0:
        extra_cols = ["us_deep", "us_deep_allowed", "us_ppda", "us_team_npxGD"]
        # Only merge columns that are still NaN
        cols_to_merge = []
        for c in extra_cols:
            if c in df.columns and df[c].isna().all():
                df = df.drop(columns=[c])
                cols_to_merge.append(c)
            elif c not in df.columns:
                cols_to_merge.append(c)

        if cols_to_merge:
            df = df.merge(
                us_deep_ppda[["understat_team", "is_home", "date_only"] + cols_to_merge],
                left_on=["_team_us", "is_home", "_date_only"],
                right_on=["understat_team", "is_home", "date_only"],
                how="left",
            ).drop(columns=["understat_team", "date_only"], errors="ignore")

        # Opponent ppda
        if "us_ppda" in us_deep_ppda.columns:
            opp_ppda = us_deep_ppda[["understat_team", "is_home", "date_only", "us_ppda"]].copy()
            opp_ppda = opp_ppda.rename(columns={
                "understat_team": "_opp_us",
                "is_home": "_opp_home",
                "us_ppda": "us_opp_ppda",
            })
            df["_opp_us"] = df["us_opponent"].map(lambda x: fpl_team_name_to_us.get(x, x))
            df["_opp_home"] = 1 - df["is_home"]
            df = df.drop(columns=["us_opp_ppda"], errors="ignore")
            df = df.merge(
                opp_ppda,
                left_on=["_opp_us", "_opp_home", "_date_only"],
                right_on=["_opp_us", "_opp_home", "date_only"],
                how="left",
            ).drop(columns=["_opp_us", "_opp_home", "date_only"], errors="ignore")

    # Merge season-level team stats
    if len(us_team_season) > 0:
        season_cols = [
            "us_team_name", "team_xG_avg", "team_xGA_avg", "team_npxG_avg",
            "team_npxGA_avg", "team_deep_avg", "team_deep_allowed_avg",
            "team_goals_season", "team_conceded_season", "team_ppda_avg",
            "team_ppda_allowed_avg",
        ]
        df = df.drop(columns=[c for c in season_cols if c in df.columns], errors="ignore")
        us_team_season = us_team_season.copy()
        us_team_season["_team_us"] = us_team_season["us_team_name"]
        df = df.merge(
            us_team_season,
            on="_team_us",
            how="left",
        )

    # Derived features
    if "team_xG_avg" in df.columns and "team_xGA_avg" in df.columns:
        df["team_xGD_avg"] = df["team_xG_avg"] - df["team_xGA_avg"]

    if "total_points" in df.columns and "value" in df.columns:
        val = pd.to_numeric(df["value"], errors="coerce") / 10
        df["points_per_million"] = pd.to_numeric(df["total_points"], errors="coerce") / val.replace(0, np.nan)

    if "goals_scored" in df.columns and "expected_goals" in df.columns:
        df["goals_vs_xG"] = pd.to_numeric(df["goals_scored"], errors="coerce") - pd.to_numeric(df["expected_goals"], errors="coerce")
    if "assists" in df.columns and "expected_assists" in df.columns:
        df["assists_vs_xA"] = pd.to_numeric(df["assists"], errors="coerce") - pd.to_numeric(df["expected_assists"], errors="coerce")

    # Drop temp columns
    df = df.drop(columns=["_team_us", "_date_only"], errors="ignore")

    return df


# ============================================================================
#  Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Incrementally update smartplay_data.csv")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added without writing")
    parser.add_argument("--season", type=str, default=None, help="Season to update (default: auto-detect current)")
    parser.add_argument("--output", "-o", type=Path, default=DATA_CSV, help="Output CSV path")
    args = parser.parse_args()

    print("=" * 60)
    print("  SmartPlay Data Incremental Updater")
    print("=" * 60)

    # 1. Load existing data
    if not args.output.exists():
        print(f"ERROR: {args.output} not found. Run create_merged_dataset.py first.")
        return 1

    existing = pd.read_csv(args.output, low_memory=False)
    print(f"\nExisting data: {len(existing):,} rows, {len(existing.columns)} columns")
    for s in sorted(existing["season"].unique()):
        sub = existing[existing["season"] == s]
        gws = sorted(sub["gameweek"].unique())
        print(f"  {s}: GW {int(min(gws))}-{int(max(gws))} ({len(gws)} GWs, {len(sub):,} rows)")

    # 2. Determine target season
    season = args.season or infer_season()
    print(f"\nTarget season: {season}")

    # 3. Load FPL bootstrap to find finished GWs
    print("\nFetching FPL API data...")
    bootstrap = load_bootstrap()
    events = bootstrap.get("events", [])
    finished_gws = [e["id"] for e in events if e.get("finished")]
    print(f"  Finished gameweeks: {len(finished_gws)} (GW1-{max(finished_gws) if finished_gws else 0})")

    # 4. Detect missing GWs
    existing_season = existing[existing["season"] == season]
    existing_gws = set(existing_season["gameweek"].unique()) if len(existing_season) > 0 else set()
    missing_gws = sorted(set(finished_gws) - existing_gws)

    if not missing_gws:
        print(f"\nNo missing gameweeks for {season}. Data is up to date!")
        return 0

    print(f"\nMissing gameweeks: {missing_gws}")

    if args.dry_run:
        print("\n[DRY RUN] Would fetch and append data for the above gameweeks.")
        return 0

    # 5. Load mappings
    print("\nLoading mappings...")
    player_gr = load_player_golden_record()
    clubs_gr = load_clubs_golden_record()
    fpl_team_id_to_name, fpl_team_name_to_us, _ = build_team_lookups(bootstrap, clubs_gr)
    print(f"  Players: {len(player_gr)}, Clubs: {len(clubs_gr)}")

    # 6. Fetch FPL data for missing GWs
    print(f"\nFetching FPL data for GWs {missing_gws}...")
    new_rows = fetch_missing_gw_data(
        missing_gws=missing_gws,
        bootstrap=bootstrap,
        fpl_team_id_to_name=fpl_team_id_to_name,
        fpl_team_name_to_us=fpl_team_name_to_us,
        player_gr=player_gr,
        season=season,
    )

    if len(new_rows) == 0:
        print("\nNo new data fetched. This may indicate no matches played yet.")
        return 0

    # 7. Filter out non-player rows
    if "position" in new_rows.columns:
        before = len(new_rows)
        new_rows = new_rows[new_rows["position"].isin(["GKP", "DEF", "MID", "FWD"])].copy()
        removed = before - len(new_rows)
        if removed:
            print(f"  Filtered {removed} non-player rows")

    # 8. Enrich with Understat data
    print("\nEnriching with Understat data...")
    new_rows = merge_understat_into_rows(new_rows, season, fpl_team_name_to_us)

    # 9. Deduplicate (in case of DGW same fixture appearing twice)
    key_cols = ["season", "fixture", "fpl_code"]
    new_rows = new_rows.drop_duplicates(subset=key_cols, keep="last")

    # Also remove any rows that already exist in the existing data
    existing_keys = set(zip(
        existing["season"].astype(str),
        existing["fixture"].astype(str),
        existing["fpl_code"].astype(str),
    ))
    new_rows["_key"] = list(zip(
        new_rows["season"].astype(str),
        new_rows["fixture"].astype(str),
        new_rows["fpl_code"].astype(str),
    ))
    new_rows = new_rows[~new_rows["_key"].isin(existing_keys)].drop(columns=["_key"])

    if len(new_rows) == 0:
        print("\nAll fetched rows already exist in the dataset.")
        return 0

    # 10. Align columns with existing data
    for col in COLUMN_ORDER:
        if col not in new_rows.columns:
            new_rows[col] = np.nan
    new_rows = new_rows[[c for c in COLUMN_ORDER if c in new_rows.columns]]

    # Ensure existing data has same columns
    for col in new_rows.columns:
        if col not in existing.columns:
            existing[col] = np.nan

    # 11. Append and save
    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined = combined.drop_duplicates(subset=["season", "fixture", "fpl_code"], keep="last")

    # Reorder columns to match expected order
    final_cols = [c for c in COLUMN_ORDER if c in combined.columns]
    extra_cols = [c for c in combined.columns if c not in COLUMN_ORDER]
    combined = combined[final_cols + extra_cols]

    combined.to_csv(args.output, index=False)

    print(f"\n{'=' * 60}")
    print(f"  Update complete!")
    print(f"  Added: {len(new_rows):,} rows for GWs {missing_gws}")
    print(f"  Total: {len(combined):,} rows")
    print(f"  Output: {args.output}")
    print(f"{'=' * 60}")

    # Verification
    verify = pd.read_csv(args.output, usecols=["season", "gameweek"], low_memory=False)
    v_season = verify[verify["season"] == season]
    v_gws = sorted(v_season["gameweek"].unique())
    print(f"\nVerification — {season}: GW {int(min(v_gws))}-{int(max(v_gws))} ({len(v_gws)} GWs, {len(v_season):,} rows)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
