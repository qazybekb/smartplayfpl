# openfpl_model

Reimplementation of [daniegr/OpenFPL](https://github.com/daniegr/OpenFPL) inference, adapted to run on `smartplay_data.csv`.

## What This Does

Predicts expected FPL points per fixture for every Premier League player using the original OpenFPL pre-trained ensemble (XGBoost + RandomForest, 200 models total).

## Architecture

```
200 models = 4 positions (GK, DEF, MID, FWD)
           × 5 CV folds
           × ~10 candidate models per fold

Inference:  median-ensemble across all CV folds and candidates per position
```

Each position has a separate feature subset selected during training. Inputs are standardised via `xscaler.save` and outputs are inverse-transformed via `yscaler.save`.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package exports: `OpenFPLPredictor`, feature engineering functions, constants |
| `run.py` | CLI entry point — loads data, builds features, runs inference, evaluates |
| `predictor.py` | `OpenFPLPredictor` class — loads 200 joblib models, runs median-ensemble |
| `feature_engineering.py` | Builds 235-column sample matrix from smartplay_data + Understat API |
| `constants.py` | Feature mappings, rolling windows, position codes, team name lookups |
| `verify.py` | Downloads original OpenFPL samples/predictions, verifies our output matches |
| `requirements.txt` | Package-specific dependencies |
| `.gitignore` | Excludes `models/` (722 MB) and generated CSVs |

## Feature Engineering Pipeline

1. **Load data** — reads `smartplay_data.csv`, coerces numeric columns, builds cross-season `player_uid` via Understat ID
2. **Fetch Understat team matches** — calls Understat API for team-level match data (xG, xGA, deep, ppda, etc.), caches as `understat_team_matches.csv`
3. **Build opponent lookup** — pairs home/away teams by matching `scored/missed` and `xG/xGA` on same date
4. **Compute league ranks** — cumulative points/GD/GS per team before each match
5. **Compute team rolling** — 12 features × 5 windows (1, 3, 5, 10, 38) = 60 rolling team features
6. **Compute player rolling** — 23 features × 5 windows = 115 rolling player features (includes venue-specific `relevant_fpl_points`)
7. **Build samples** — joins player + team + opponent rolling features into a 235-column matrix (115 player + 60 team + 50 opponent + 3 status + 7 metadata)

### Rolling Window Convention

All rolling features use `shift(1)` before `.rolling(w)` — the current match is never included in its own features. This prevents data leakage.

## Models (Downloaded on First Run)

On first run, `run.py` clones `daniegr/OpenFPL` (shallow) and copies the `models/` directory locally (~722 MB). This directory is git-ignored.

Contents: `xscaler.save`, `yscaler.save`, `features.save`, and `cv{1..5}_{GK,DEF,MID,FWD}/` directories each containing candidate model `.joblib` files.

## Usage

```bash
# From models/
python -m openfpl_model.run                                          # 2025-26, all GWs
python -m openfpl_model.run --season 2024-25 --gw-start 1 --gw-end 38
python -m openfpl_model.run --data /path/to/custom_data.csv

# Verify against original OpenFPL predictions
python -m openfpl_model.verify
```

## Evaluation Output

Prints per-GW comparison table: OpenFPL vs `ep_next` (FPL's built-in expected points) on Spearman correlation, RMSE, MAE, and Top-10 recall. Saves `predictions.csv` and `evaluation.csv` (both git-ignored).

## Key Constants

- **Positions**: GK, DEF, MID, FWD (AM models exist in OpenFPL but are unused)
- **Windows**: 1, 3, 5, 10, 38 matches
- **Team name mapping**: `FPL_TO_UNDERSTAT` dict handles short name mismatches (e.g. `"Spurs"` → `"Tottenham"`)
- **Position mapping**: `POS_MAP` converts FPL codes (`GKP`) to OpenFPL codes (`GK`)
