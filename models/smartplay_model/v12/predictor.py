"""
SmartPlay v12 prediction engine.

v12 is the v9/v11 calibrated multibucket model with a direct points regressor
blended in for outfield positions:

    GKP              = multibucket
    DEF / MID / FWD  = 0.75 * multibucket + 0.25 * direct
    output clipped at 0.0

Goalkeepers stay on the base because the blend did not improve their validation
scores. The blend weights and the excluded positions are read from
``blend.json`` rather than hardcoded, so a reweighted release needs no code
change here.

The base weights are ~316 MB and live on Hugging Face; the blend heads are
small enough to sit in this repository. ``load_v12`` fetches whatever is
missing and returns a ready predictor.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import xgboost as xgb

from ..predictor import POSITIONS, SmartPlayPredictor

HF_REPO = "Qazybek/smartplay-fpl-v12"
THIS_DIR = Path(__file__).resolve().parent


class SmartPlayV12Predictor(SmartPlayPredictor):
    """Multibucket base plus the position-gated direct blend."""

    def __init__(self, base_dir: Path | str, blend_dir: Path | str) -> None:
        # The Hugging Face base ships XGBoost's binary format.
        super().__init__(base_dir, ext=".ubj")

        blend_dir = Path(blend_dir)
        with open(blend_dir / "blend.json") as f:
            self.blend = json.load(f)

        self.direct: dict[str, xgb.XGBRegressor] = {}
        for pos in POSITIONS:
            if pos in self.blend.get("excluded_positions", []):
                continue
            reg = xgb.XGBRegressor()
            reg.load_model(blend_dir / f"direct_{pos}.json")
            self.direct[pos] = reg

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return *df* with v12 predictions in ``pred``.

        The base multibucket output is preserved in ``pred_multibucket`` and the
        auxiliary head in ``pred_direct`` so the blend can be inspected rather
        than taken on trust.
        """
        out = super().predict(df)
        out["pred_multibucket"] = out["pred"]
        out["pred_direct"] = np.nan

        w_base = float(self.blend["multibucket_weight"])
        w_direct = float(self.blend["direct_weight"])
        clip_min = float(self.blend.get("output_clip_min", 0.0))

        for pos, model in self.direct.items():
            mask = out["position"] == pos
            if not mask.any():
                continue
            X = out.loc[mask, self.feature_cols].fillna(0.0).values
            direct = np.clip(model.predict(X), 0.0, None)
            out.loc[mask, "pred_direct"] = direct
            out.loc[mask, "pred"] = np.clip(
                w_base * out.loc[mask, "pred_multibucket"].values + w_direct * direct,
                clip_min,
                None,
            )

        # Goalkeepers, and any other excluded position, keep the base value.
        out["pred"] = np.clip(out["pred"], clip_min, None)
        return out


def load_v12(base_dir: Path | str | None = None) -> SmartPlayV12Predictor:
    """Build a v12 predictor, downloading the base weights if needed.

    Args:
        base_dir: local directory holding the multibucket ``.ubj`` files. When
            omitted the weights are pulled from Hugging Face and cached there,
            so repeat calls do not re-download.
    """
    if base_dir is None:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:  # pragma: no cover - dependency hint
            raise ImportError(
                "huggingface_hub is required to fetch the v12 base weights.\n"
                "  pip install huggingface_hub\n"
                f"or download {HF_REPO} manually and pass base_dir."
            ) from exc

        snapshot = Path(snapshot_download(HF_REPO))
        return SmartPlayV12Predictor(snapshot / "base", snapshot / "blend")

    return SmartPlayV12Predictor(base_dir, THIS_DIR)
