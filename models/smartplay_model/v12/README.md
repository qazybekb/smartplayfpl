# SmartPlay v12 — direct-blend head

v12 is the model currently generating the expected points published on
[smartplayfpl.com](https://smartplayfpl.com). It is not a new architecture: it is
the v11 calibrated multibucket model with a direct points regressor blended in
for outfield positions.

```
GKP              = v11_multibucket
DEF / MID / FWD  = 0.75 × v11_multibucket  +  0.25 × direct
output clipped at 0.0
```

Goalkeepers stay entirely on the base model because the direct blend did not
improve their validation scores.

## What is in this directory

| File | What it is |
|---|---|
| `direct_DEF.json`, `direct_MID.json`, `direct_FWD.json`, `direct_GKP.json` | The direct XGBoost points regressors, one per position |
| `blend.json` | Blend weights and the exact formula above |
| `feature_cols.json` | The 251 feature columns, in the order the models expect |

`direct_GKP.json` is included for completeness and reproducibility. It is *not*
used at inference — `blend.json` lists GKP under `excluded_positions`.

## What is not here yet

**The v11 multibucket base weights.** They are ~316 MB in XGBoost binary format,
which is too large to commit to a public git repository without breaking the
LFS quota for everyone who clones it. Until they are hosted somewhere sensible,
this directory documents and provides the *new* quarter of v12 rather than a
runnable model.

The parent `models/smartplay_model/` still ships the complete, runnable **v9**
model, and the architecture there is the same shape as the v11 base — a p60
classifier, a non-60 regressor, a bucket classifier and four bucket regressors
per position. With `data/smartplay_data.csv` you can retrain that base yourself.

## Honest evaluation

`evaluation/v12_walk_forward_accuracy.json` in this repository holds the
per-gameweek numbers from four leakage-controlled walk-forward windows over
2025-26 — 25,234 player-gameweeks across 32 gameweeks. Every test gameweek falls
after the data used to train its fold.

| Metric | v12 | v11 |
|---|---|---|
| MAE | **0.979** | 0.994 |
| NDCG@10 | **0.380** | 0.352 |
| Spearman | 0.729 | 0.728 |

Three things worth being clear about, because the headline numbers flatter the
model if you read them alone:

- **Spearman did not improve.** The 95% bootstrap interval on that change
  includes zero. v12 is a consistent error and top-pick improvement, not a
  across-the-board gain.
- **MAE of 0.979 is measured over the whole player pool**, and roughly three in
  five of those rows are players who never came on. Predicting zero for an
  unused substitute is easy and correct, and it pulls the average down. Scored
  only on players who actually started (60+ minutes), the same published
  projections give MAE ≈ 2.35 and Spearman ≈ 0.14. That is the harder number and
  the one that describes picking a captain.
- **GW9-14 are absent** from the evaluation. They were not part of the published
  selection suite, so the four folds cover GW1-8, 15-22, 23-30 and 31-38.

## Licence

CC BY-NC 4.0, same as the rest of the repository. Non-commercial use, with
attribution.
