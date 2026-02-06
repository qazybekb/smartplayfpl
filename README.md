# SmartPlayFPL — Public Release

This folder is a self-contained, public-friendly release of SmartPlayFPL’s open models and dataset.

- Start here: `models/README.md`
- Git LFS required (for `data/smartplay_data.csv`)
- License: CC BY-NC 4.0 (see `LICENSE`)
- Includes:
  - `models/openfpl_model/` — OpenFPL inference wrapper (downloads upstream models on first run)
  - `models/smartplay_model/` — SmartPlay v9 pre-trained XGBoost weights + runner
  - `data/smartplay_data.csv` — training/evaluation dataset (Git LFS)
