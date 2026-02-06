#!/usr/bin/env python3
"""
Verify our OpenFPLPredictor reproduces the original daniegr/OpenFPL predictions.

Downloads samples.csv and predictions.csv from the OpenFPL repo,
runs our predictor on the samples, and compares results side-by-side.

Usage:
    cd data
    python -m openfpl_model.verify
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .predictor import OpenFPLPredictor
from .run import ensure_models

warnings.filterwarnings("ignore", category=FutureWarning)

SAMPLES_URL = 'https://raw.githubusercontent.com/daniegr/OpenFPL/main/data/samples.csv'
PREDICTIONS_URL = 'https://raw.githubusercontent.com/daniegr/OpenFPL/main/data/predictions.csv'

METADATA_COLS = ['season', 'gw', 'position', 'player', 'team', 'opponent', 'home']


def main():
    pkg_dir = Path(__file__).resolve().parent
    models_dir = pkg_dir / 'models'

    # Ensure models are available
    ensure_models(models_dir)

    # Load original samples and predictions from the OpenFPL repo
    print("Loading samples and predictions from daniegr/OpenFPL...")
    samples_df = pd.read_csv(SAMPLES_URL)
    original_preds_df = pd.read_csv(PREDICTIONS_URL)

    print(f"  Samples: {len(samples_df)} rows, {len(samples_df.columns)} columns")
    print(f"  Positions: {samples_df['position'].unique().tolist()}")

    # Load our predictor
    print("\nLoading OpenFPL models...")
    predictor = OpenFPLPredictor(models_dir)
    print(f"  Loaded {predictor.total_models} models")

    # Run our prediction
    print("Running inference...")
    our_preds = predictor.predict(samples_df)

    # Build comparison table
    result = samples_df[METADATA_COLS].copy()
    result['prediction_original'] = original_preds_df['prediction'].values
    result['prediction_test'] = our_preds

    # For positions we don't predict (AM), prediction_test will be 0
    player_positions = result['position'].isin(['GK', 'DEF', 'MID', 'FWD'])
    result_players = result[player_positions].copy()
    result_players['diff'] = result_players['prediction_test'] - result_players['prediction_original']
    result_players['pct_diff'] = (
        result_players['diff'].abs() / result_players['prediction_original'].abs() * 100
    )

    print("\n" + "=" * 100)
    print("COMPARISON: prediction_original vs prediction_test")
    print("=" * 100)

    for _, r in result.iterrows():
        marker = ""
        if r['position'] not in ['GK', 'DEF', 'MID', 'FWD']:
            marker = " (skipped - AM position)"
        print(f"  {r['position']:>3} {r['player']:30s} "
              f"original={r['prediction_original']:.6f}  "
              f"test={r['prediction_test']:.6f}{marker}")

    if len(result_players) > 0:
        max_diff = result_players['diff'].abs().max()
        max_pct = result_players['pct_diff'].max()
        print(f"\nMax absolute difference: {max_diff:.10f}")
        print(f"Max percentage difference: {max_pct:.6f}%")

        if max_pct < 0.01:
            print("\nVERIFICATION PASSED: Predictions match within 0.01%")
        elif max_pct < 1.0:
            print("\nVERIFICATION PASSED: Predictions match within 1%")
        else:
            print(f"\nWARNING: Predictions differ by up to {max_pct:.2f}%")

    # Save combined output
    output_path = pkg_dir / 'verification_predictions.csv'
    result.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}")


if __name__ == '__main__':
    main()
