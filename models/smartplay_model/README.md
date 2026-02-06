# smartplay_model

SmartPlay v9 — a multi-bucket mixture XGBoost model for FPL expected points prediction.

## What This Does

Predicts expected FPL points per fixture using a two-stage architecture: first estimates whether a player will play 60+ minutes, then uses calibrated bucket probabilities to weight per-bucket point predictions.

## Architecture

```
Per position (GKP, DEF, MID, FWD):
  ┌─ p60 classifier ──────── P(minutes >= 60)
  │
  ├─ non60 regressor ─────── E[points | minutes < 60]
  │
  ├─ bucket classifier ────── P(bucket=k | minutes >= 60)
  │   bucket 0: points <= 0
  │   bucket 1: 1–2 points
  │   bucket 2: 3–9 points (tickers)
  │   bucket 3: >= 10 points (haulers)
  │
  └─ bucket regressors (×4) ─ E[points | minutes >= 60, bucket=k]

Final prediction:
  pred_if60 = Σ_k  calibrated_p_k × pred_bucket_k
  pred      = p60 × pred_if60 + (1 - p60) × pred_non60
```

This gives **28 XGBoost models** total (4 positions × 7 model types) plus a calibration parameter file.

### Bucket Calibration

Raw bucket probabilities are calibrated using a power-law transform with per-bucket weights:

```
p_adjusted_k = (p_raw_k ^ gamma) × w_k
p_calibrated_k = p_adjusted_k / sum(p_adjusted)
```

Parameters (`gamma`, `w0`–`w3`) are stored per position in `bucket_calibration.json`.

## Files

| File | Description |
|---|---|
| `__init__.py` | Package exports: `SmartPlayPredictor`, `build_v9_features` |
| `__main__.py` | Enables `python -m smartplay_model` |
| `run.py` | CLI entry point — loads data, builds features, runs inference, evaluates |
| `predictor.py` | `SmartPlayPredictor` class — loads 24 XGBoost JSON models + calibration |
| `feature_engineering.py` | Builds 16 v9-specific features on top of openfpl_model's rolling features |
| `requirements.txt` | Package-specific dependencies |
| `models/` | Pre-trained XGBoost JSON weights (~21 MB, committed) |

## Feature Engineering

SmartPlay v9 builds on `openfpl_model`'s feature engineering (rolling player + team + opponent features) and adds **16 additional features**:

| Group | Features | Description |
|---|---|---|
| Availability (9) | `p_any_{3,5,10}`, `p60_{3,5,10}`, `e_minutes_{3,5,10}` | Rolling probability of playing / playing 60+ min / expected minutes, using 3/5/10 match windows |
| Market (4) | `expected_points_pre_deadline`, `value`, `selected`, `transfers_balance` | FPL market data at time of prediction |
| Venue + rank (3) | `is_home_num`, `status_league_rank`, `opp_status_league_rank` | Home/away flag and league table position |

Total feature count: **251 columns** (stored in `models/feature_cols.json`).

### Availability Feature Details

- Grouped by `(fpl_code, season)` and shifted by 1 (`shift(1)`) to prevent leakage
- NaN values (start of season) filled with position-specific base rates:
  - GKP: p_any=0.50, p60=0.48, e_minutes=45.0
  - DEF: p_any=0.55, p60=0.42, e_minutes=42.0
  - MID: p_any=0.52, p60=0.38, e_minutes=38.0
  - FWD: p_any=0.50, p60=0.35, e_minutes=35.0

## Pre-trained Models

The `models/` directory contains 30 files (~21 MB total), committed to git:

- `feature_cols.json` — ordered list of 251 feature column names
- `bucket_calibration.json` — per-position calibration parameters
- `p60_{GKP,DEF,MID,FWD}.json` — 4 P(60+ minutes) classifiers
- `non60_{GKP,DEF,MID,FWD}.json` — 4 E[points | <60 min] regressors
- `bucket_{GKP,DEF,MID,FWD}.json` — 4 bucket classifiers
- `bucketreg_{GKP,DEF,MID,FWD}_{0,1,2,3}.json` — 16 per-bucket regressors

## Usage

```bash
# From models/
python -m smartplay_model.run                                              # 2025-26 GW1-24
python -m smartplay_model.run --season 2025-26 --gw-start 1 --gw-end 24
python -m smartplay_model.run --data /path/to/custom_data.csv
```

## Evaluation Output

Prints per-GW starters-only (minutes >= 60) metrics:
- **Spearman correlation** — rank agreement between predictions and actuals
- **RMSE** — root mean squared error
- **MAE** — mean absolute error
- **Bucket RMSE breakdown** — RMSE split by actual-point buckets (zeros, blanks, tickers, haulers)

## Dependency on openfpl_model

`smartplay_model` imports from `openfpl_model` at runtime:
- `load_data` — loads and prepares smartplay_data.csv
- `build_opponent_lookup` — pairs home/away teams
- `compute_league_ranks` — pre-match league table positions
- `compute_team_rolling` — 60 team rolling features
- `compute_player_rolling` — 115 player rolling features

Both packages must be importable from the same working directory (`models/`).
