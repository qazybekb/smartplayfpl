"""
OpenFPL prediction engine.

Loads pre-trained XGBoost/RandomForest models from daniegr/OpenFPL and runs
ensemble inference on 235-column sample DataFrames.
"""

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from .constants import POSITIONS, NUM_CV_FOLDS


class OpenFPLPredictor:
    """Loads 200 pre-trained models (4 positions x 5 CV folds x ~10 candidates)
    and runs median-ensemble prediction.

    Usage:
        predictor = OpenFPLPredictor(Path('openfpl_model/models'))
        preds = predictor.predict(samples_df)
        result_df = predictor.predict_df(samples_df)
    """

    def __init__(self, models_dir: Path):
        models_dir = Path(models_dir)

        # Load scalers and feature selection
        self.xscaler = joblib.load(models_dir / 'xscaler.save')
        self.yscaler = joblib.load(models_dir / 'yscaler.save')
        self.features = joblib.load(models_dir / 'features.save')
        self.xscaler_features = list(self.xscaler.feature_names_in_)
        self.pos_feature_indices = {}
        for position in POSITIONS:
            missing = [f for f in self.features[position] if f not in self.xscaler_features]
            if missing:
                raise ValueError(
                    f"OpenFPL feature list for position={position} contains "
                    f"{len(missing)} unknown features (first 10): {missing[:10]}"
                )
            self.pos_feature_indices[position] = [
                self.xscaler_features.index(f) for f in self.features[position]
            ]

        # Load all models: {cv: {position: [model, ...]}}
        self.models = {
            cv: {pos: [] for pos in POSITIONS}
            for cv in range(1, NUM_CV_FOLDS + 1)
        }

        for cv in range(1, NUM_CV_FOLDS + 1):
            for position in POSITIONS:
                search_dir = models_dir / f'cv{cv}_{position}'
                search_log = (search_dir / 'search.txt').read_text()
                # Parse top candidates from final population in search log
                candidates = [
                    x.split(' ')[0]
                    for x in search_log.split('The population is:')[-1].split('Candidate ')[1:]
                ]
                for candidate_num in candidates:
                    candidate_dir = search_dir / candidate_num
                    model_file = list(candidate_dir.iterdir())[0]
                    self.models[cv][position].append(joblib.load(model_file))

        self.total_models = sum(
            len(self.models[cv][pos])
            for cv in self.models
            for pos in self.models[cv]
        )

    def predict(self, samples_df: pd.DataFrame) -> np.ndarray:
        """Predict expected points for each row in samples_df.

        Args:
            samples_df: DataFrame with 235+ columns (7 metadata + 228 features).
                Must have a 'position' column with values in {GK, DEF, MID, FWD}.

        Returns:
            1D array of predicted points, same length as samples_df.
        """
        results = np.zeros(len(samples_df))

        for position in POSITIONS:
            mask = samples_df['position'] == position
            pos_samples = samples_df[mask]
            if len(pos_samples) == 0:
                continue

            # Build feature matrix in scaler column order (preserves feature names to avoid
            # scikit-learn warnings and reduces the chance of misalignment).
            pos_features = (
                pos_samples.reindex(columns=self.xscaler_features, fill_value=0)
                .fillna(0)
                .astype('float32')
            )

            # Scale inputs
            feature_data_scaled = np.nan_to_num(self.xscaler.transform(pos_features)).astype('float32')

            # Select position-specific feature subset
            pos_data = feature_data_scaled[:, self.pos_feature_indices[position]]

            # Ensemble prediction: median across all CV folds and candidates
            all_preds = []
            for cv in range(1, NUM_CV_FOLDS + 1):
                for model in self.models[cv][position]:
                    preds = model.predict(pos_data)
                    preds = self.yscaler.inverse_transform(preds.reshape(-1, 1)).reshape(-1)
                    all_preds.append(preds)

            ensemble = np.median(all_preds, axis=0)
            results[mask.values] = ensemble

        return results

    def predict_df(self, samples_df: pd.DataFrame) -> pd.DataFrame:
        """Predict and return a DataFrame with metadata and openfpl_xpts column.

        Args:
            samples_df: Same as predict(). Must also have '_element' metadata column.

        Returns:
            DataFrame with columns: element, player, position, team, opponent,
            home, gw, openfpl_xpts, and any '_'-prefixed metadata columns.
        """
        preds = self.predict(samples_df)

        result = pd.DataFrame({
            'element': samples_df['_element'].astype(int).values,
            'player': samples_df['player'].values,
            'position': samples_df['position'].values,
            'team': samples_df['team'].values,
            'opponent': samples_df['opponent'].values,
            'home': samples_df['home'].values,
            'gw': samples_df['gw'].astype(int).values,
            'openfpl_xpts': preds,
        })

        # Include metadata columns with standard names
        meta_rename = {
            '_total_points': 'actual_points',
            '_minutes': 'minutes',
            '_ep_next': 'ep_next',
        }
        for col in samples_df.columns:
            if col.startswith('_') and col != '_element':
                out_name = meta_rename.get(col, col.lstrip('_'))
                result[out_name] = samples_df[col].values

        return result
