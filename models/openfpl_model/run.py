#!/usr/bin/env python3
"""
Run OpenFPL predictions on smartplay_data.csv and compare against actuals.

Downloads pre-trained models from daniegr/OpenFPL on first run (~722MB).
Fetches team match data from Understat API on first run (cached locally).

Usage:
    # From models/
    python -m openfpl_model.run

    # Specify season and GW range
    python -m openfpl_model.run --season 2024-25 --gw-start 1 --gw-end 38

    # Custom data path
    python -m openfpl_model.run --data path/to/smartplay_data.csv
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .feature_engineering import (
    load_data,
    build_opponent_lookup,
    compute_league_ranks,
    compute_team_rolling,
    compute_player_rolling,
    build_samples,
)
from .predictor import OpenFPLPredictor

warnings.filterwarnings("ignore", category=FutureWarning)

OPENFPL_REPO = 'https://github.com/daniegr/OpenFPL.git'


def ensure_models(models_dir: Path) -> None:
    """Download OpenFPL models if not present locally.

    Clones the daniegr/OpenFPL repo (shallow) to a temp directory,
    moves the models/ folder to the target location, then cleans up.
    """
    sentinel = models_dir / 'xscaler.save'
    if sentinel.exists():
        return

    print(f"Models not found at {models_dir}")
    print(f"Downloading from {OPENFPL_REPO} (this may take a few minutes)...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / 'OpenFPL'
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', OPENFPL_REPO, str(tmp_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: git clone failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

        src_models = tmp_path / 'models'
        if not src_models.exists():
            print(f"ERROR: models/ not found in cloned repo at {tmp_path}", file=sys.stderr)
            sys.exit(1)

        models_dir.parent.mkdir(parents=True, exist_ok=True)
        if models_dir.exists():
            shutil.rmtree(models_dir)
        shutil.copytree(str(src_models), str(models_dir))

    print(f"Models saved to {models_dir}")


def spearman_corr(pred, actual):
    if len(pred) < 3:
        return np.nan
    corr, _ = spearmanr(pred, actual)
    return corr


def rmse(pred, actual):
    return np.sqrt(np.mean((np.array(pred) - np.array(actual)) ** 2))


def mae(pred, actual):
    return np.mean(np.abs(np.array(pred) - np.array(actual)))


def top_n_recall(pred, actual, n=10):
    if len(pred) < n:
        return np.nan
    pred_arr = np.array(pred)
    actual_arr = np.array(actual)
    pred_top = set(np.argsort(pred_arr)[-n:])
    actual_top = set(np.argsort(actual_arr)[-n:])
    return len(pred_top & actual_top) / n


def evaluate(pred_df, output_dir):
    """Compare OpenFPL predictions against actuals and ep_next."""
    print("\n" + "=" * 80)
    print("EVALUATION: OpenFPL vs ep_next vs Actuals")
    print("=" * 80)

    gw_agg = pred_df.groupby(['element', 'player', 'gw']).agg({
        'openfpl_xpts': 'sum',
        'actual_points': 'sum',
        'minutes': 'sum',
        'ep_next': 'first',
        'position': 'first',
        'team': 'first',
    }).reset_index()

    starters = gw_agg[gw_agg['minutes'] >= 60].copy()
    print(f"\nTotal player-GW rows: {len(gw_agg)}")
    print(f"Starters (min >= 60): {len(starters)}")

    print(f"\n{'GW':>4} {'N':>5} {'OpenFPL':>10} {'ep_next':>10} | "
          f"{'RMSE_O':>8} {'RMSE_E':>8} | {'MAE_O':>7} {'MAE_E':>7} | "
          f"{'Top10_O':>8} {'Top10_E':>8}")
    print("-" * 100)

    gw_results = []
    for gw in sorted(starters['gw'].unique()):
        gw_data = starters[starters['gw'] == gw]
        n = len(gw_data)
        if n < 10:
            continue

        openfpl_sp = spearman_corr(gw_data['openfpl_xpts'], gw_data['actual_points'])
        has_ep = (gw_data['ep_next'] != 0).any()
        ep_sp = spearman_corr(gw_data['ep_next'], gw_data['actual_points']) if has_ep else np.nan

        openfpl_rmse = rmse(gw_data['openfpl_xpts'], gw_data['actual_points'])
        ep_rmse = rmse(gw_data['ep_next'], gw_data['actual_points']) if has_ep else np.nan

        openfpl_mae = mae(gw_data['openfpl_xpts'], gw_data['actual_points'])
        ep_mae = mae(gw_data['ep_next'], gw_data['actual_points']) if has_ep else np.nan

        openfpl_top10 = top_n_recall(gw_data['openfpl_xpts'].values, gw_data['actual_points'].values)
        ep_top10 = top_n_recall(gw_data['ep_next'].values, gw_data['actual_points'].values) if has_ep else np.nan

        ep_sp_str = f"{ep_sp:.3f}" if not np.isnan(ep_sp) else "N/A"
        ep_rmse_str = f"{ep_rmse:.3f}" if not np.isnan(ep_rmse) else "N/A"
        ep_mae_str = f"{ep_mae:.3f}" if not np.isnan(ep_mae) else "N/A"
        ep_top10_str = f"{ep_top10:.3f}" if not np.isnan(ep_top10) else "N/A"

        print(f"GW{gw:>2} {n:>5} {openfpl_sp:>10.3f} {ep_sp_str:>10} | "
              f"{openfpl_rmse:>8.3f} {ep_rmse_str:>8} | "
              f"{openfpl_mae:>7.3f} {ep_mae_str:>7} | "
              f"{openfpl_top10:>8.3f} {ep_top10_str:>8}")

        gw_results.append({
            'gw': gw, 'n_starters': n,
            'openfpl_spearman': openfpl_sp, 'ep_spearman': ep_sp,
            'openfpl_rmse': openfpl_rmse, 'ep_rmse': ep_rmse,
            'openfpl_mae': openfpl_mae, 'ep_mae': ep_mae,
            'openfpl_top10': openfpl_top10, 'ep_top10': ep_top10,
        })

    results_df = pd.DataFrame(gw_results)
    if len(results_df) == 0:
        print("  No gameweeks with enough starters to evaluate.")
        return results_df

    print("-" * 100)
    avg_o_sp = results_df['openfpl_spearman'].mean()
    avg_e_sp = results_df['ep_spearman'].mean()
    avg_o_rmse = results_df['openfpl_rmse'].mean()
    avg_e_rmse = results_df['ep_rmse'].mean()
    avg_o_mae = results_df['openfpl_mae'].mean()
    avg_e_mae = results_df['ep_mae'].mean()
    avg_o_t10 = results_df['openfpl_top10'].mean()
    avg_e_t10 = results_df['ep_top10'].mean()

    print(f" AVG {'':>5} {avg_o_sp:>10.3f} {avg_e_sp:>10.3f} | "
          f"{avg_o_rmse:>8.3f} {avg_e_rmse:>8.3f} | "
          f"{avg_o_mae:>7.3f} {avg_e_mae:>7.3f} | "
          f"{avg_o_t10:>8.3f} {avg_e_t10:>8.3f}")

    latest_gw = starters['gw'].max()
    latest = starters[starters['gw'] == latest_gw].nlargest(15, 'openfpl_xpts')
    print(f"\nTop 15 OpenFPL predictions for GW{latest_gw} (starters):")
    for _, r in latest.iterrows():
        print(f"  {r['player']:25s} ({r['team']:20s}) "
              f"OpenFPL={r['openfpl_xpts']:.2f}  Actual={r['actual_points']:.0f}")

    # Save outputs
    results_df.to_csv(output_dir / 'evaluation.csv', index=False)
    gw_agg.to_csv(output_dir / 'predictions.csv', index=False)
    print(f"\nResults saved to {output_dir}")

    return results_df


def main():
    parser = argparse.ArgumentParser(
        description='Run OpenFPL model predictions on smartplay_data.csv')
    parser.add_argument(
        '--data', default=None,
        help='Path to smartplay_data.csv (default: ../data/smartplay_data.csv)')
    parser.add_argument('--season', default='2025-26', help='Target season (default: 2025-26)')
    parser.add_argument('--gw-start', type=int, default=1, help='First gameweek (default: 1)')
    parser.add_argument('--gw-end', type=int, default=38, help='Last gameweek (default: 38)')
    parser.add_argument('--output-dir', default=None, help='Output directory')
    args = parser.parse_args()

    pkg_dir = Path(__file__).resolve().parent
    data_dir = pkg_dir.parent.parent / "data"

    # Resolve data path
    if args.data:
        data_path = Path(args.data)
    else:
        data_path = data_dir / 'smartplay_data.csv'

    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    models_dir = pkg_dir / 'models'
    output_dir = Path(args.output_dir) if args.output_dir else pkg_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    gws = list(range(args.gw_start, args.gw_end + 1))

    # Step 1: Ensure models are downloaded
    ensure_models(models_dir)

    # Step 2: Load data
    print("Loading data...")
    merged, team_matches = load_data(str(data_path))

    # Step 3: Feature engineering
    print("Building opponent lookup...")
    team_matches = build_opponent_lookup(team_matches)

    print("Computing league ranks...")
    league_ranks = compute_league_ranks(team_matches)

    print("Computing team rolling features...")
    team_df, team_rolling_cols = compute_team_rolling(team_matches, league_ranks)

    print("Computing player rolling features...")
    player_df, player_rolling_cols = compute_player_rolling(merged)

    print(f"Building samples for {args.season} GW{args.gw_start}-{args.gw_end}...")
    samples = build_samples(player_df, team_df, team_rolling_cols, args.season, gws)
    print(f"  Built {len(samples)} sample rows")

    if len(samples) == 0:
        print(f"ERROR: No samples found for season={args.season} GW{args.gw_start}-{args.gw_end}",
              file=sys.stderr)
        sys.exit(1)

    # Step 4: Prediction
    print("\nLoading OpenFPL models...")
    predictor = OpenFPLPredictor(models_dir)
    print(f"  Loaded {predictor.total_models} models")

    print("Running inference...")
    pred_df = predictor.predict_df(samples)
    print(f"  Generated {len(pred_df)} predictions")

    # Step 5: Evaluation
    evaluate(pred_df, output_dir)


if __name__ == '__main__':
    main()
