#!/usr/bin/env python3
"""
Run SmartPlay v9 predictions on smartplay_data.csv and compare against actuals.

Uses pre-trained XGBoost models committed in this package (~27 MB).
Fetches Understat team match data on first run (cached locally).

Usage:
    # From models/
    python -m smartplay_model.run

    # Specify season and GW range
    python -m smartplay_model.run --season 2025-26 --gw-start 1 --gw-end 24

    # Custom data path
    python -m smartplay_model.run --data path/to/smartplay_data.csv
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from openfpl_model import (
    load_data,
    build_opponent_lookup,
    compute_league_ranks,
    compute_team_rolling,
    compute_player_rolling,
)
from .feature_engineering import build_v9_features
from .predictor import SmartPlayPredictor

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _spearman(pred, actual):
    if len(pred) < 3:
        return np.nan
    corr, _ = spearmanr(pred, actual)
    return corr


def _rmse(pred, actual):
    return np.sqrt(np.mean((np.array(pred) - np.array(actual)) ** 2))


def _mae(pred, actual):
    return np.mean(np.abs(np.array(pred) - np.array(actual)))


def _bucket_breakdown(df, pred_col="pred", actual_col="actual_points"):
    """Print RMSE breakdown by point bucket."""
    y = df[actual_col].astype(float)
    p = df[pred_col].astype(float)
    buckets = [
        ("zeros (<=0)", y <= 0),
        ("blanks (1-2)", (y >= 1) & (y <= 2)),
        ("tickers (3-9)", (y >= 3) & (y <= 9)),
        ("haulers (>=10)", y >= 10),
    ]
    for name, mask in buckets:
        n = mask.sum()
        if n == 0:
            continue
        r = _rmse(p[mask].values, y[mask].values)
        print(f"    {name:20s}  N={n:>6d}  RMSE={r:.4f}")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(pred_df: pd.DataFrame, season: str, gw_start: int, gw_end: int):
    """Per-GW starters evaluation table + bucket breakdown."""
    gw_agg = (
        pred_df.groupby(["element", "gameweek"], as_index=False)
        .agg(
            pred=("pred", "sum"),
            actual_points=("actual_points", "sum"),
            minutes=("minutes", "sum"),
        )
    )

    starters = gw_agg[gw_agg["minutes"] >= 60].copy()
    print(f"\nTotal fixture-level rows : {len(pred_df)}")
    print(f"Total player-GW rows    : {len(gw_agg)}")
    print(f"Starters (min >= 60)    : {len(starters)}")

    print(f"\n{'GW':>4} {'N':>5} {'Spearman':>10} {'RMSE':>8} {'MAE':>8}")
    print("-" * 40)

    gw_results = []
    for gw in sorted(starters["gameweek"].unique()):
        gw_data = starters[starters["gameweek"] == gw]
        n = len(gw_data)
        if n < 10:
            continue
        sp = _spearman(gw_data["pred"].values, gw_data["actual_points"].values)
        r = _rmse(gw_data["pred"].values, gw_data["actual_points"].values)
        m = _mae(gw_data["pred"].values, gw_data["actual_points"].values)

        print(f"GW{gw:>2} {n:>5} {sp:>10.4f} {r:>8.4f} {m:>8.4f}")
        gw_results.append({"gw": gw, "n": n, "spearman": sp, "rmse": r, "mae": m})

    if not gw_results:
        print("  No gameweeks with enough starters.")
        return

    results = pd.DataFrame(gw_results)
    print("-" * 40)
    print(
        f" AVG {'':>5} {results['spearman'].mean():>10.4f} "
        f"{results['rmse'].mean():>8.4f} {results['mae'].mean():>8.4f}"
    )

    # Bucket breakdown on fixture-level starters
    fixture_starters = pred_df[pred_df["minutes"] >= 60]
    print(f"\n  Bucket RMSE breakdown (fixture-level starters, N={len(fixture_starters)}):")
    _bucket_breakdown(fixture_starters)

    # All-players fixture-level summary
    print(f"\n  All players fixture-level (N={len(pred_df)}):")
    sp_all = _spearman(pred_df["pred"].values, pred_df["actual_points"].values)
    r_all = _rmse(pred_df["pred"].values, pred_df["actual_points"].values)
    print(f"    Spearman={sp_all:.4f}  RMSE={r_all:.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run SmartPlay v9 model predictions on smartplay_data.csv",
    )
    parser.add_argument(
        "--data", default=None,
        help="Path to smartplay_data.csv (default: ../data/smartplay_data.csv)",
    )
    parser.add_argument("--season", default="2025-26", help="Target season (default: 2025-26)")
    parser.add_argument("--gw-start", type=int, default=1, help="First gameweek (default: 1)")
    parser.add_argument("--gw-end", type=int, default=24, help="Last gameweek (default: 24)")
    args = parser.parse_args()

    pkg_dir = Path(__file__).resolve().parent
    data_dir = pkg_dir.parent.parent / "data"

    if args.data:
        data_path = Path(args.data)
    else:
        data_path = data_dir / "smartplay_data.csv"

    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    models_dir = pkg_dir / "models"
    gws = list(range(args.gw_start, args.gw_end + 1))

    # Step 1: Load data (openfpl_model handles Understat fetch + caching)
    print("Loading data...")
    merged, team_matches = load_data(str(data_path))

    # Step 2: Feature engineering (openfpl_model base features)
    print("Building opponent lookup...")
    team_matches = build_opponent_lookup(team_matches)

    print("Computing league ranks...")
    league_ranks = compute_league_ranks(team_matches)

    print("Computing team rolling features...")
    team_df, team_rolling_cols = compute_team_rolling(team_matches, league_ranks)

    print("Computing player rolling features...")
    player_df, _ = compute_player_rolling(merged)

    # Step 3: v9 feature engineering
    print("Building v9 feature table...")
    feat_df = build_v9_features(player_df, team_df, team_rolling_cols)
    feat_df = feat_df[feat_df["position"].isin(["GKP", "DEF", "MID", "FWD"])].copy()

    # Filter to target season + GWs
    target = feat_df[
        (feat_df["season"] == args.season) & (feat_df["gameweek"].isin(gws))
    ].copy()
    print(f"  Target rows: {len(target)} ({args.season} GW{args.gw_start}-{args.gw_end})")

    if len(target) == 0:
        print(
            f"ERROR: No rows for season={args.season} GW{args.gw_start}-{args.gw_end}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 4: Prediction
    print("\nLoading SmartPlay v9 models...")
    predictor = SmartPlayPredictor(models_dir)
    print(f"  Feature columns: {len(predictor.feature_cols)}")

    print("Running inference...")
    result = predictor.predict(target)
    print(f"  Generated {len(result)} predictions")

    # Step 5: Evaluate
    evaluate(result, args.season, args.gw_start, args.gw_end)


if __name__ == "__main__":
    main()
