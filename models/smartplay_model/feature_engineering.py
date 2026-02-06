"""
Feature engineering for SmartPlay v9 model.

Takes the rolling feature DataFrame produced by ``openfpl_model`` and adds
16 v9-specific features on top:

  Availability (9): p_any_{3,5,10}, p60_{3,5,10}, e_minutes_{3,5,10}
  Market        (4): expected_points_pre_deadline, value, selected, transfers_balance
  Venue + rank  (3): is_home_num, status_league_rank, opp_status_league_rank
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

POSITION_BASE_RATES = {
    "GKP": {"p_any": 0.50, "p60": 0.48, "e_minutes": 45.0},
    "DEF": {"p_any": 0.55, "p60": 0.42, "e_minutes": 42.0},
    "MID": {"p_any": 0.52, "p60": 0.38, "e_minutes": 38.0},
    "FWD": {"p_any": 0.50, "p60": 0.35, "e_minutes": 35.0},
}

AVAILABILITY_WINDOWS = (3, 5, 10)


def _add_availability_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add shifted rolling availability features per player per season."""
    df = df.sort_values(["fpl_code", "season", "kickoff_time"]).copy()
    df["_played"] = (df["minutes"] > 0).astype(float)
    df["_played60"] = (df["minutes"] >= 60).astype(float)

    for w in AVAILABILITY_WINDOWS:
        df[f"p_any_{w}"] = (
            df.groupby(["fpl_code", "season"])["_played"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
        df[f"p60_{w}"] = (
            df.groupby(["fpl_code", "season"])["_played60"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
        df[f"e_minutes_{w}"] = (
            df.groupby(["fpl_code", "season"])["minutes"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )

    # Fill NaN with position-specific base rates
    for pos, base in POSITION_BASE_RATES.items():
        mask = df["position"] == pos
        for w in AVAILABILITY_WINDOWS:
            df.loc[mask, f"p_any_{w}"] = df.loc[mask, f"p_any_{w}"].fillna(base["p_any"])
            df.loc[mask, f"p60_{w}"] = df.loc[mask, f"p60_{w}"].fillna(base["p60"])
            df.loc[mask, f"e_minutes_{w}"] = df.loc[mask, f"e_minutes_{w}"].fillna(base["e_minutes"])

    return df.drop(columns=["_played", "_played60"], errors="ignore")


def build_v9_features(
    player_df: pd.DataFrame,
    team_df: pd.DataFrame,
    team_roll_cols: List[str],
) -> pd.DataFrame:
    """Build the full v9 feature table from openfpl rolling outputs.

    Args:
        player_df: Output of ``openfpl_model.compute_player_rolling()``.
        team_df: Output of ``openfpl_model.compute_team_rolling()``.
        team_roll_cols: Rolling column names from ``compute_team_rolling``.

    Returns:
        DataFrame with all 251 feature columns plus metadata (season,
        gameweek, element, position, minutes, actual_points, etc.).
    """
    df = player_df.copy()
    df["match_date_only"] = df["match_date"].dt.date

    # --- Join team rolling features (player's own team) ---
    team_join = team_df[
        ["understat_team", "date_only"] + team_roll_cols + ["status_league_rank", "status_opp_league_rank"]
    ].drop_duplicates(subset=["understat_team", "date_only"])

    df = df.merge(
        team_join.rename(columns={"understat_team": "_team", "date_only": "_date"}),
        left_on=["team_us", "match_date_only"],
        right_on=["_team", "_date"],
        how="left",
    ).drop(columns=["_team", "_date"], errors="ignore")

    # --- Join opponent rolling features ---
    opp_rename = {col: col.replace("team_", "opp_", 1) for col in team_roll_cols}
    opp_rename["status_league_rank"] = "opp_status_league_rank"
    opp_rename["status_opp_league_rank"] = "opp_status_opp_league_rank"

    opp_join = (
        team_join.rename(columns=opp_rename)
        .rename(columns={"understat_team": "_opp_team", "date_only": "_opp_date"})
    )
    df = df.merge(
        opp_join,
        left_on=["opponent_us", "match_date_only"],
        right_on=["_opp_team", "_opp_date"],
        how="left",
    ).drop(columns=["_opp_team", "_opp_date"], errors="ignore")

    # --- Venue ---
    df["is_home_num"] = df["is_home"].astype(int)

    # --- Actual points target ---
    df["actual_points"] = df["total_points"].astype(float)

    # --- Availability features ---
    df = _add_availability_features(df)

    # --- Market features ---
    for col in ["expected_points_pre_deadline", "value", "selected", "transfers_balance"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # --- Rank features ---
    for col in ["status_league_rank", "opp_status_league_rank"]:
        if col not in df.columns:
            df[col] = np.nan

    return df
