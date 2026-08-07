# SmartPlay v12

v12 generates the expected points published on
[smartplayfpl.com](https://smartplayfpl.com). It is the v11 calibrated
multibucket model with a direct points regressor blended in for outfield
positions.

```
GKP              = v11_multibucket
DEF / MID / FWD  = 0.75 × v11_multibucket  +  0.25 × direct
output clipped at 0.0
```

Goalkeepers stay on the base model because the blend did not improve their
validation scores.

## The full weights are on Hugging Face

**[huggingface.co/Qazybek/smartplay-fpl-v12](https://huggingface.co/Qazybek/smartplay-fpl-v12)**

That is the complete, runnable model: the 28 multibucket base models, the
calibration file, the direct-blend heads, the feature order, and a worked
inference example. It lives there rather than here because the base weights are
~316 MB, and putting that in git LFS would burn the bandwidth quota for
everyone who clones this repository.

```python
from huggingface_hub import snapshot_download
path = snapshot_download("Qazybek/smartplay-fpl-v12")
```

## What is in this directory

The direct-blend heads, small enough to keep alongside the code:

| File | What it is |
|---|---|
| `direct_{GKP,DEF,MID,FWD}.json` | The direct XGBoost points regressors |
| `blend.json` | Blend weights and the exact formula above |
| `feature_cols.json` | The 251 features, in the order the models expect |

`direct_GKP.json` is here for reproducibility but is not used at inference —
`blend.json` lists GKP under `excluded_positions`.

## Format

XGBoost's own formats: `.ubj` binary for the base, `.json` text for the blend
heads. Not pickle. Both load with `Booster.load_model` on any XGBoost ≥ 2.0 and
contain no executable code, so running them does not require trusting us.

## Evaluation

See [`../../../evaluation/`](../../../evaluation/) for the per-gameweek
walk-forward numbers and, more importantly, the three ways those headline
figures mislead when quoted alone.
