"""
SmartPlay v9 prediction engine.

Loads 24 pre-trained XGBoost models (4 positions x 6 model types) plus
calibration parameters.  Runs multi-bucket mixture inference to produce
per-fixture xPts predictions.

Model architecture per position (GKP / DEF / MID / FWD):
  1. p60 classifier     — P(minutes >= 60 | features)
  2. non60 regressor    — E[points | minutes < 60, features]
  3. bucket classifier  — P(bucket=k | minutes >= 60, features)
     bucket 0: points <= 0
     bucket 1: 1–2
     bucket 2: 3–9
     bucket 3: >= 10
  4. bucket regressors  — E[points | minutes >= 60 AND bucket=k, features]

Final prediction:
  pred_if60 = Σ_k  p_cal_k * pred_bucket_k
  pred      = p60 * pred_if60 + (1 - p60) * pred_non60
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import xgboost as xgb

POSITIONS = ["GKP", "DEF", "MID", "FWD"]


def _apply_bucket_calibration(p_raw: np.ndarray, gamma: float, w: np.ndarray) -> np.ndarray:
    """Calibrate raw bucket probabilities with power-law + re-weighting."""
    p = np.clip(p_raw, 1e-12, 1.0)
    p_adj = (p ** gamma) * w[None, :]
    denom = np.sum(p_adj, axis=1, keepdims=True)
    denom = np.where(denom <= 0, 1.0, denom)
    return p_adj / denom


class SmartPlayPredictor:
    """Load 24 XGBoost models + calibration and run multi-bucket inference.

    Usage::

        predictor = SmartPlayPredictor(Path("smartplay_model/models"))
        result_df = predictor.predict(feature_df)
    """

    def __init__(self, models_dir: Path | str, ext: str = ".json") -> None:
        """Args:
            models_dir: directory holding the per-position model files.
            ext: model file extension. v9 ships ``.json``; the v12 base on
                Hugging Face ships ``.ubj``, which is the same trees in
                XGBoost's binary encoding and roughly a third smaller.
        """
        models_dir = Path(models_dir)

        # Feature column order (251 features)
        feature_path = models_dir / "feature_cols.json"
        if not feature_path.exists():
            # The Hugging Face layout keeps the feature order beside the blend
            # heads rather than the base weights.
            feature_path = models_dir.parent / "blend" / "feature_cols.json"
        with open(feature_path) as f:
            self.feature_cols: List[str] = json.load(f)

        # Bucket calibration parameters per position
        with open(models_dir / "bucket_calibration.json") as f:
            self.calibration: Dict[str, Dict[str, float]] = json.load(f)

        # Per-position models
        self.p60: Dict[str, xgb.XGBClassifier] = {}
        self.non60: Dict[str, xgb.XGBRegressor] = {}
        self.bucket: Dict[str, xgb.XGBClassifier] = {}
        self.bucketreg: Dict[str, Dict[int, xgb.XGBRegressor]] = {}

        for pos in POSITIONS:
            clf = xgb.XGBClassifier()
            clf.load_model(models_dir / f"p60_{pos}{ext}")
            self.p60[pos] = clf

            reg = xgb.XGBRegressor()
            reg.load_model(models_dir / f"non60_{pos}{ext}")
            self.non60[pos] = reg

            bcl = xgb.XGBClassifier()
            bcl.load_model(models_dir / f"bucket_{pos}{ext}")
            self.bucket[pos] = bcl

            self.bucketreg[pos] = {}
            for k in range(4):
                breg = xgb.XGBRegressor()
                breg.load_model(models_dir / f"bucketreg_{pos}_{k}{ext}")
                self.bucketreg[pos][k] = breg

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run multi-bucket mixture inference.

        Args:
            df: DataFrame with a ``position`` column and all columns
                listed in ``self.feature_cols``.

        Returns:
            Copy of *df* with added columns: ``pred``, ``p60``,
            ``pred_non60``, ``pred_if60``, ``p_bucket_0..3``,
            ``pred_bucket_0..3``.
        """
        out = df.copy()
        out["p60"] = 0.0
        out["pred_non60"] = 0.0
        out["pred_if60"] = 0.0
        out["pred"] = 0.0
        for k in range(4):
            out[f"p_bucket_{k}"] = 0.0
            out[f"pred_bucket_{k}"] = 0.0

        for pos in POSITIONS:
            mask = out["position"] == pos
            if not mask.any():
                continue

            X = out.loc[mask, self.feature_cols].fillna(0.0).values

            # 1) P(minutes >= 60)
            p60 = self.p60[pos].predict_proba(X)[:, 1]

            # 2) E[points | minutes < 60]
            pred_non60 = np.clip(self.non60[pos].predict(X), 0.0, None)

            # 3) Raw bucket probabilities + calibration
            p_raw = self.bucket[pos].predict_proba(X)
            cal = self.calibration[pos]
            w_vec = np.array([cal["w0"], cal["w1"], cal["w2"], cal["w3"]], dtype=float)
            p_cal = _apply_bucket_calibration(p_raw, gamma=float(cal["gamma"]), w=w_vec)

            # 4) Per-bucket point predictions
            pred_b = np.zeros((len(X), 4), dtype=float)
            for k in range(4):
                pred_b[:, k] = np.clip(self.bucketreg[pos][k].predict(X), 0.0, None)

            # 5) Aggregate
            pred_if60 = np.sum(p_cal * pred_b, axis=1)
            pred = p60 * pred_if60 + (1.0 - p60) * pred_non60

            out.loc[mask, "p60"] = p60
            out.loc[mask, "pred_non60"] = pred_non60
            out.loc[mask, "pred_if60"] = pred_if60
            out.loc[mask, "pred"] = pred
            for k in range(4):
                out.loc[mask, f"p_bucket_{k}"] = p_cal[:, k]
                out.loc[mask, f"pred_bucket_{k}"] = pred_b[:, k]

        return out
