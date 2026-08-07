#!/usr/bin/env python3
"""
Worked example: build a squad from scratch with the v12 model and the solver.

Runs entirely off this repository plus the published weights — no database, no
API key, no account. It is deliberately the *wildcard* case (no existing team,
full budget) because that needs no FPL entry id and so runs for anyone.

    pip install -r ../requirements.txt huggingface_hub highspy
    python solver/example.py --season 2025-26 --gameweek 30

What it does:
  1. loads the merged dataset shipped in data/
  2. builds the 251 features and predicts with v12
  3. reshapes those projections into the {gw}_Pts / {gw}_xMins columns the
     solver expects
  4. solves for the best legal 15 under a £100.0m budget
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "models"))
sys.path.insert(0, str(ROOT))

from solver import prepare_data, solve_multi_period_fpl  # noqa: E402

POSITION_BY_TYPE = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def build_projections(season: str, gameweek: int, horizon: int) -> pd.DataFrame:
    """Predict every player for the horizon, in the solver's wide format."""
    from smartplay_model.feature_engineering import build_v9_features
    from smartplay_model.v12 import load_v12
    from openfpl_model.run import (
        build_opponent_lookup,
        compute_league_ranks,
        compute_player_rolling,
        compute_team_rolling,
        load_data,
    )

    print("Loading dataset and building features …")
    merged, team_matches = load_data(str(ROOT / "data" / "smartplay_data.csv"))
    team_matches = build_opponent_lookup(team_matches)
    ranks = compute_league_ranks(team_matches)
    team_df, team_roll = compute_team_rolling(team_matches, ranks)
    player_df, _ = compute_player_rolling(merged)
    feats = build_v9_features(player_df, team_df, team_roll)
    feats = feats[feats["position"].isin(POSITION_BY_TYPE.values())]

    gws = list(range(gameweek, gameweek + horizon))
    window = feats[(feats["season"] == season) & (feats["gameweek"].isin(gws))].copy()
    if window.empty:
        raise SystemExit(f"No rows for {season} GW{gws[0]}-{gws[-1]}")

    print(f"Predicting {len(window)} player-fixtures with v12 …")
    pred = load_v12().predict(window)

    # A double gameweek is two fixtures for one player; the solver wants one
    # row per player per gameweek, so points add and minutes add.
    per_gw = pred.groupby(["element", "gameweek"], as_index=False).agg(
        pred=("pred", "sum"), minutes=("minutes", "sum")
    )
    wide = per_gw.pivot(index="element", columns="gameweek", values="pred")
    wide.columns = [f"{int(c)}_Pts" for c in wide.columns]
    mins = per_gw.pivot(index="element", columns="gameweek", values="minutes")
    mins.columns = [f"{int(c)}_xMins" for c in mins.columns]

    out = wide.join(mins).fillna(0.0).reset_index().rename(columns={"element": "ID"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", default="2025-26")
    ap.add_argument("--gameweek", type=int, default=30)
    ap.add_argument("--horizon", type=int, default=3)
    ap.add_argument("--budget", type=float, default=100.0, help="in £m")
    args = ap.parse_args()

    projections = build_projections(args.season, args.gameweek, args.horizon)

    # Bootstrap frames, taken from the dataset so the example stays offline.
    data = pd.read_csv(
        ROOT / "data" / "smartplay_data.csv",
        usecols=["season", "gameweek", "element", "player_name", "team", "position", "value"],
        low_memory=False,
    )
    snap = (
        data[(data["season"] == args.season) & (data["gameweek"] == args.gameweek)]
        .drop_duplicates("element")
    )
    type_by_pos = {v: k for k, v in POSITION_BY_TYPE.items()}
    elements = pd.DataFrame({
        "id": snap["element"].astype(int),
        "web_name": snap["player_name"],
        "team": snap["team"].astype("category").cat.codes + 1,
        "element_type": snap["position"].map(type_by_pos),
        "now_cost": snap["value"].astype(float),
    }).dropna()
    teams = pd.DataFrame({
        "id": sorted(elements["team"].unique()),
        "name": [f"T{i}" for i in sorted(elements["team"].unique())],
    })

    # A wildcard: no squad, whole budget, one free transfer state.
    team_json = {
        "picks": [],
        "transfers": {"bank": int(args.budget * 10), "limit": 1, "made": 0},
        "chips": [],
    }
    # prepare_data requires a fixtures frame so it can never be tempted to call
    # the FPL API. Nothing downstream reads it today, but it is built from the
    # dataset rather than stubbed so the example does not teach a bad habit.
    fixtures = (
        data[data["season"] == args.season][["gameweek", "team"]]
        .drop_duplicates()
        .rename(columns={"gameweek": "event"})
        .reset_index(drop=True)
    )

    options = {
        "fpl_elements_df": elements,
        "fpl_teams_df": teams,
        "data_df": projections,
        "fixtures": fixtures,
        "override_next_gw": args.gameweek,
        "horizon": args.horizon,
        "use_wc": True,
        "banked_transfers": 1,
    }

    print(f"Solving GW{args.gameweek}-{args.gameweek + args.horizon - 1} "
          f"on £{args.budget:.1f}m …")
    solutions = solve_multi_period_fpl(prepare_data(team_json, options), team_json, options)
    if not solutions:
        print("No solution found.")
        return 1

    best = solutions[0]
    print(f"\nprojected points over horizon: {best.get('total_xp', float('nan')):.2f}")
    picks = best["picks"]
    cols = [c for c in ("name", "web_name", "pos", "position", "team", "price", "xp", "lineup", "captain")
            if c in picks.columns]
    print(picks[cols].to_string(index=False) if cols else picks.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
