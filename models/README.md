# SmartPlayFPL Open Models + Data

Two reproducible FPL prediction models and the training/evaluation dataset.

| Package | What it does | Models |
|---|---|---|
| **openfpl_model** | Reimplementation of [daniegr/OpenFPL](https://github.com/daniegr/OpenFPL) — XGBoost per-position models | Downloaded on first run (~722 MB, git-ignored) |
| **smartplay_model** | SmartPlay v9 — multi-bucket mixture XGBoost with calibrated probability buckets | Pre-trained weights committed (~21 MB) |

Both models predict **expected points per fixture** for every Premier League player.

## Quick Start

```bash
# 1. Clone (install Git LFS first — smartplay_data.csv is 88 MB)
git lfs install
git clone <repo-url>
cd <repo>/models

# 2. Install dependencies (Python 3.10+ required)
pip install -r ../requirements.txt

# 3. Run SmartPlay v9
python -m smartplay_model.run

# 4. Run OpenFPL (downloads ~722 MB of models on first run)
python -m openfpl_model.run
```

## Data

### `../data/smartplay_data.csv`

Historical player-fixture dataset covering **2020-21 through 2025-26** (88 MB, tracked with Git LFS).

Each row is one player in one fixture. Key columns:

| Column group | Examples |
|---|---|
| Identity | `season`, `gameweek`, `player_name`, `team_name`, `position` |
| FPL actuals | `total_points`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `bonus` |
| FPL expected | `expected_goals`, `expected_assists`, `expected_goal_involvements`, `xP` |
| Understat player | `us_xG`, `us_xA`, `us_npxG`, `us_shots`, `us_key_passes`, `us_xGChain`, `us_xGBuildup` |
| Understat team | `us_team_xG`, `us_team_xGA`, `us_ppda`, `team_xG_avg`, `team_xGA_avg` |
| Derived | `us_xG_per90`, `points_per_million`, `goals_vs_xG`, `assists_vs_xA` |

See [`../data/README.md`](../data/README.md) for the full 115-column reference.

### Updating the data

```bash
# Update mappings first (picks up new signings)
python ../data/mappings/update_golden_records.py

# Then append new gameweeks
python ../data/update_smartplay_data.py           # auto-detect and append missing GWs
python ../data/update_smartplay_data.py --dry-run  # preview what would be added
```

### `../data/mappings/`

Golden-record CSVs that map FPL player/club IDs to Understat IDs. See [`../data/mappings/README.md`](../data/mappings/README.md).

## Packages

### openfpl_model

Reimplements OpenFPL inference. On first run it downloads the pre-trained models from `daniegr/OpenFPL` into `openfpl_model/models/` (~722 MB, git-ignored).

```bash
python -m openfpl_model.run                                            # default: 2025-26
python -m openfpl_model.run --season 2024-25 --gw-start 1 --gw-end 38  # evaluate on older season
```

> **Note:** OpenFPL models were trained on historical data (2020-2024). Running on the current season works but may show some distribution shift from new players/teams. For evaluation on training-era data, use `--season 2024-25`.

> **Note:** OpenFPL distributes its pre-trained models as `joblib` pickles. Depending on your local `scikit-learn` / `xgboost` versions, you may see version-mismatch warnings when loading them. This is expected; run `python -m openfpl_model.verify` to confirm our outputs match the published OpenFPL reference predictions.

See [`openfpl_model/README.md`](openfpl_model/README.md) for architecture details.

### smartplay_model

SmartPlay v9 uses openfpl_model's feature engineering as a base, then adds 16 v9-specific features (availability rolling stats, market data, venue/rank) and runs multi-bucket mixture inference with calibrated probability outputs.

Pre-trained XGBoost JSON weights are committed in `smartplay_model/models/` (~21 MB).

```bash
python -m smartplay_model.run                                            # default: 2025-26 GW1-24
python -m smartplay_model.run --season 2025-26 --gw-start 1 --gw-end 24
```

See [`smartplay_model/README.md`](smartplay_model/README.md) for architecture details.

## How to Reproduce Results

1. **Install deps**: `pip install -r ../requirements.txt`
2. **Run SmartPlay v9**: `python -m smartplay_model.run`
   - Loads `smartplay_data.csv`
   - Fetches Understat team match data (cached after first run)
   - Builds rolling features via openfpl_model
   - Applies v9 feature engineering + multi-bucket inference
   - Prints per-GW Spearman / RMSE / MAE and bucket breakdowns
3. **Run OpenFPL**: `python -m openfpl_model.run`
   - Same data loading + feature engineering
   - Downloads OpenFPL models on first run
   - Prints per-GW evaluation metrics
4. **Verify OpenFPL**: `python -m openfpl_model.verify`
   - Downloads original OpenFPL samples + predictions
   - Confirms our reimplementation matches within tolerance

## Requirements

- Python 3.10+
- See `../requirements.txt` for package dependencies
- Internet connection on first run (Understat API + OpenFPL model download)

## Attribution

- **OpenFPL** by [daniegr](https://github.com/daniegr/OpenFPL) — original XGBoost FPL model and pre-trained weights
- **FPL-ID-Map** by [ChrisMusson](https://github.com/ChrisMusson/FPL-ID-Map) — FPL-to-Understat player ID mappings
- **Fantasy Premier League API** — official player and fixture data
- **Understat** — advanced football statistics (xG, xA, deep completions, PPDA)

## License

This repository is provided under the **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)** license — **non-commercial use only**. You are free to use, share, and adapt for personal projects, academic research, and educational purposes. You may not use the code, models, or data for any commercial purpose, including but not limited to paid products, services, or consulting. See [`LICENSE`](../LICENSE) for full terms.
