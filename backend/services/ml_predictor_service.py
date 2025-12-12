# backend/services/ml_predictor_service.py
"""
ML Predictor Service for Squad Building

Uses trained models from the ml/ directory:
- Stage 1: Random Forest for P(plays) - probability of playing
- Position-specific scoring: Weighted formula for expected points

This service integrates ML predictions into the squad builder without
requiring model retraining.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    import pickle
    JOBLIB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Position-specific weights from fpl_final_predictor.ipynb
POSITION_WEIGHTS = {
    'GKP': {'nailedness': 0.50, 'form_xg': 0.05, 'form_pts': 0.15, 'fixture': 0.30},
    'DEF': {'nailedness': 0.45, 'form_xg': 0.10, 'form_pts': 0.15, 'fixture': 0.30},
    'MID': {'nailedness': 0.45, 'form_xg': 0.25, 'form_pts': 0.15, 'fixture': 0.15},
    'FWD': {'nailedness': 0.45, 'form_xg': 0.30, 'form_pts': 0.15, 'fixture': 0.10},
}

# Stage 1 features (18 features from fpl_ml_pipeline.ipynb)
STAGE1_FEATURES = [
    'games_so_far', 'is_DEF', 'is_FWD', 'is_GKP', 'is_MID', 'is_home',
    'mins_per_game', 'minutes_avg_last5', 'minutes_lag1', 'minutes_lag2',
    'nailedness_score', 'selected_pct', 'start_rate_overall',
    'starts_lag1', 'starts_lag2', 'starts_rate_last3', 'starts_rate_last5',
    'value_millions'
]


@dataclass
class PlayerPrediction:
    """Prediction for a single player."""
    player_id: int
    player_name: str
    position: str
    team_id: int

    # Core predictions
    p_plays: float  # Probability of playing (0-1)
    ml_score: float  # Position-weighted expected score

    # Score breakdown
    nailedness_score: float
    form_score_xg: float
    form_score_pts: float
    fixture_score: float

    # Availability
    is_available: bool
    availability_reason: str
    chance_of_playing: Optional[int]


class MLPredictorService:
    """
    ML-based predictor service for squad building.

    Loads trained models and provides predictions without retraining.
    """

    MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "models")

    def __init__(self):
        self._fpl_service = None
        self._kg_service = None

        # Models
        self._stage1_model = None
        self._stage1_scaler = None
        self._stage1_features = None
        self._models_loaded = False

        # Team fixture difficulty cache
        self._team_fdr: Dict[int, float] = {}
        self._team_is_home: Dict[int, bool] = {}

        # Load models on init
        self._load_models()

    def set_services(self, fpl_service, kg_service=None):
        """Set FPL and KG services for data access."""
        self._fpl_service = fpl_service
        self._kg_service = kg_service

    def _validate_model_path(self, path: str) -> bool:
        """
        SECURITY: Validate that model path is within allowed directory.

        This prevents path traversal attacks if paths are ever user-influenced.
        """
        # Resolve to absolute paths
        model_dir = os.path.realpath(self.MODEL_DIR)
        resolved_path = os.path.realpath(path)

        # Ensure the path is within MODEL_DIR
        if not resolved_path.startswith(model_dir):
            logger.warning(f"SECURITY: Attempted to load model from outside MODEL_DIR: {path}")
            return False

        # Ensure it's a .pkl file
        if not resolved_path.endswith('.pkl'):
            logger.warning(f"SECURITY: Attempted to load non-pkl file: {path}")
            return False

        return True

    def _secure_load(self, path: str):
        """
        Securely load a pickle file with validation.

        SECURITY NOTE: Pickle deserialization can execute arbitrary code.
        This function only loads files from the trusted MODEL_DIR and
        uses joblib when available (which provides some additional safety).
        """
        if not self._validate_model_path(path):
            raise ValueError(f"Invalid model path: {path}")

        if not os.path.exists(path):
            return None

        # Prefer joblib for scikit-learn models (safer and faster)
        if JOBLIB_AVAILABLE:
            return joblib.load(path)
        else:
            # Fallback to pickle with file properly closed
            # WARNING: pickle.load can execute arbitrary code
            logger.warning("Using pickle fallback - joblib not available")
            with open(path, 'rb') as f:
                return pickle.load(f)

    def _load_models(self):
        """Load trained models from disk using joblib (secure loading)."""
        try:
            # Load Stage 1 model (P(plays) prediction)
            stage1_path = os.path.join(self.MODEL_DIR, "stage1_random_forest.pkl")
            scaler_path = os.path.join(self.MODEL_DIR, "scaler_stage1.pkl")
            features_path = os.path.join(self.MODEL_DIR, "stage1_features.pkl")

            # SECURITY: Validate paths before loading
            if os.path.exists(stage1_path) and self._validate_model_path(stage1_path):
                self._stage1_model = self._secure_load(stage1_path)
                logger.info("Loaded Stage 1 model (Random Forest)")

            if os.path.exists(scaler_path) and self._validate_model_path(scaler_path):
                self._stage1_scaler = self._secure_load(scaler_path)
                logger.info("Loaded Stage 1 scaler")

            if os.path.exists(features_path) and self._validate_model_path(features_path):
                self._stage1_features = self._secure_load(features_path)
                logger.info(f"Loaded Stage 1 features: {len(self._stage1_features)} features")

            self._models_loaded = self._stage1_model is not None

            if self._models_loaded:
                logger.info("ML Predictor Service: Models loaded successfully")
            else:
                logger.warning("ML Predictor Service: No models found, using fallback")

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self._models_loaded = False

    @property
    def is_ready(self) -> bool:
        """Check if service is ready for predictions."""
        return self._fpl_service is not None

    async def update_fixture_data(self):
        """Update fixture difficulty data for current gameweek."""
        if not self._fpl_service:
            return

        fixtures = await self._fpl_service.get_fixtures()
        current_gw_obj = self._fpl_service.get_current_gameweek()
        current_gw = current_gw_obj.id if hasattr(current_gw_obj, 'id') else current_gw_obj

        self._team_fdr = {}
        self._team_is_home = {}

        # Get next 3 GWs for FDR calculation
        gws_to_check = range(current_gw, min(current_gw + 3, 39))

        team_fdrs = {}

        for fixture in fixtures:
            gw = getattr(fixture, 'event', None)
            if gw and gw in gws_to_check:
                home_team = getattr(fixture, 'team_h', None)
                away_team = getattr(fixture, 'team_a', None)
                home_fdr = getattr(fixture, 'team_h_difficulty', 3)
                away_fdr = getattr(fixture, 'team_a_difficulty', 3)

                if home_team:
                    if home_team not in team_fdrs:
                        team_fdrs[home_team] = []
                    team_fdrs[home_team].append(home_fdr)
                    if gw == current_gw:
                        self._team_is_home[home_team] = True

                if away_team:
                    if away_team not in team_fdrs:
                        team_fdrs[away_team] = []
                    team_fdrs[away_team].append(away_fdr)
                    if gw == current_gw:
                        self._team_is_home[away_team] = False

        # Average FDR for each team
        for team_id, fdrs in team_fdrs.items():
            self._team_fdr[team_id] = sum(fdrs) / len(fdrs) if fdrs else 3.0

    def check_availability(self, player) -> Tuple[bool, str]:
        """
        Check if a player is available to play.

        Returns:
            (is_available, reason)
        """
        status = player.status
        chance = player.chance_of_playing_next_round
        news = player.news or ""

        # Hard unavailable statuses
        if status == 'u':
            return False, "Unavailable"
        if status == 's':
            return False, "Suspended"
        if status == 'i':
            return False, f"Injured - {news}" if news else "Injured"

        # Check chance of playing
        if chance is not None:
            if chance == 0:
                return False, f"0% chance - {news}" if news else "0% chance of playing"
            if chance == 25:
                return False, f"25% chance - {news}" if news else "25% chance (likely out)"

        # Available or doubtful
        if status == 'd':
            if chance and chance >= 75:
                return True, f"Doubtful but {chance}% chance"
            return False, f"Doubtful - {news}" if news else "Doubtful"

        return True, "Available"

    def compute_nailedness_score(self, player, current_gw: int) -> float:
        """
        Compute nailedness score (0-1) based on minutes played.

        Higher score = more likely to start regularly.
        """
        minutes = player.minutes or 0

        # Estimate games played so far
        games_so_far = max(1, current_gw - 1)
        mins_per_game = minutes / games_so_far if games_so_far > 0 else 0

        # Nailedness based on minutes per game (90 = 1.0, 0 = 0.0)
        # Players averaging 70+ mins/game are considered nailed
        nailedness = min(1.0, mins_per_game / 70.0)

        # Boost for very high minutes players
        if mins_per_game >= 85:
            nailedness = min(1.0, nailedness * 1.1)

        return round(nailedness, 3)

    def compute_form_score_xg(self, player) -> float:
        """
        Compute form score based on xG/xA (0-1).
        """
        try:
            xg = float(player.expected_goals or 0)
            xa = float(player.expected_assists or 0)
            xgi = float(player.expected_goal_involvements or 0)
        except (ValueError, TypeError):
            xg, xa, xgi = 0, 0, 0

        # Different expectations by position
        position = player.position

        if position == 'FWD':
            # FWDs: xG is king, expect ~0.3-0.5 xG per game
            expected_xg = 0.4 * 15  # ~15 games worth
            score = min(1.0, xg / expected_xg) * 0.7 + min(1.0, xa / 3) * 0.3
        elif position == 'MID':
            # MIDs: balanced xG + xA
            expected_xgi = 0.3 * 15
            score = min(1.0, xgi / expected_xgi)
        elif position == 'DEF':
            # DEFs: lower expectations, more about assists
            score = min(1.0, xa / 2) * 0.6 + min(1.0, xg / 1.5) * 0.4
        else:  # GKP
            # GKPs: xG doesn't matter
            score = 0.5  # Neutral for keepers

        return round(score, 3)

    def compute_form_score_pts(self, player) -> float:
        """
        Compute form score based on recent points (0-1).
        """
        form = player.form_float or 0

        # Form is typically 0-10 range
        # 5+ is good form, 7+ is excellent
        score = min(1.0, form / 7.0)

        return round(score, 3)

    def compute_fixture_score(self, team_id: int) -> float:
        """
        Compute fixture score based on FDR (0-1).

        Lower FDR = easier fixtures = higher score.
        """
        fdr = self._team_fdr.get(team_id, 3.0)

        # FDR is 1-5: 1 = easiest, 5 = hardest
        # Convert to 0-1 score where 1 = easiest fixtures
        score = (5 - fdr) / 4.0

        # Boost for home games
        if self._team_is_home.get(team_id, False):
            score = min(1.0, score * 1.15)

        return round(score, 3)

    def predict_p_plays(self, player, current_gw: int) -> float:
        """
        Predict probability of playing using Stage 1 model or fallback.

        Returns probability 0-1.
        """
        # First check availability status
        is_available, _ = self.check_availability(player)
        if not is_available:
            return 0.0

        # Use chance_of_playing if available
        chance = player.chance_of_playing_next_round
        if chance is not None:
            return chance / 100.0

        # If model is loaded, use it
        if self._models_loaded and self._stage1_model:
            try:
                features = self._build_stage1_features(player, current_gw)
                if self._stage1_scaler:
                    features_scaled = self._stage1_scaler.transform([features])
                else:
                    features_scaled = [features]

                # Get probability from model
                if hasattr(self._stage1_model, 'predict_proba'):
                    proba = self._stage1_model.predict_proba(features_scaled)[0]
                    # Probability of playing (class 1)
                    return float(proba[1]) if len(proba) > 1 else float(proba[0])
                else:
                    # Binary prediction
                    pred = self._stage1_model.predict(features_scaled)[0]
                    return 1.0 if pred == 1 else 0.0

            except Exception as e:
                logger.warning(f"Model prediction failed for {player.web_name}: {e}")

        # Fallback: Use nailedness as proxy
        nailedness = self.compute_nailedness_score(player, current_gw)

        # Adjust based on status
        if player.status == 'd':
            nailedness *= 0.75  # Doubtful penalty

        return min(1.0, max(0.0, nailedness))

    def _build_stage1_features(self, player, current_gw: int) -> List[float]:
        """
        Build feature vector for Stage 1 model.

        Many features need to be approximated from available data.
        """
        games_so_far = max(1, current_gw - 1)
        minutes = player.minutes or 0
        mins_per_game = minutes / games_so_far if games_so_far > 0 else 0

        # Start rate approximation (assuming started if played 60+ mins avg)
        start_rate = min(1.0, mins_per_game / 60.0) if mins_per_game > 0 else 0

        # Nailedness
        nailedness = self.compute_nailedness_score(player, current_gw)

        # Position one-hot
        is_gkp = 1.0 if player.position == 'GKP' else 0.0
        is_def = 1.0 if player.position == 'DEF' else 0.0
        is_mid = 1.0 if player.position == 'MID' else 0.0
        is_fwd = 1.0 if player.position == 'FWD' else 0.0

        # Home/away
        is_home = 1.0 if self._team_is_home.get(player.team, False) else 0.0

        # Build feature vector in expected order
        features = [
            games_so_far,           # games_so_far
            is_def,                 # is_DEF
            is_fwd,                 # is_FWD
            is_gkp,                 # is_GKP
            is_mid,                 # is_MID
            is_home,                # is_home
            mins_per_game,          # mins_per_game
            mins_per_game,          # minutes_avg_last5 (approximation)
            mins_per_game,          # minutes_lag1 (approximation)
            mins_per_game,          # minutes_lag2 (approximation)
            nailedness,             # nailedness_score
            player.ownership / 100, # selected_pct (convert from % to decimal)
            start_rate,             # start_rate_overall
            start_rate,             # starts_lag1 (approximation)
            start_rate,             # starts_lag2 (approximation)
            start_rate,             # starts_rate_last3 (approximation)
            start_rate,             # starts_rate_last5 (approximation)
            player.price,           # value_millions
        ]

        return features

    def compute_ml_score(self, player, current_gw: int) -> Tuple[float, Dict[str, float]]:
        """
        Compute ML-based score using position-specific weights.

        Returns:
            (score, breakdown_dict)
        """
        position = player.position
        weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS['MID'])

        # Compute component scores
        nailedness = self.compute_nailedness_score(player, current_gw)
        form_xg = self.compute_form_score_xg(player)
        form_pts = self.compute_form_score_pts(player)
        fixture = self.compute_fixture_score(player.team)

        # Weighted score
        score = (
            weights['nailedness'] * nailedness +
            weights['form_xg'] * form_xg +
            weights['form_pts'] * form_pts +
            weights['fixture'] * fixture
        )

        # Scale to 0-100 for easier interpretation
        score = score * 100

        breakdown = {
            'nailedness': round(nailedness * 100, 1),
            'form_xg': round(form_xg * 100, 1),
            'form_pts': round(form_pts * 100, 1),
            'fixture': round(fixture * 100, 1),
            'weights': weights,
        }

        return round(score, 1), breakdown

    async def predict_all_players(self) -> List[PlayerPrediction]:
        """
        Generate predictions for all players.

        Returns list sorted by ml_score (descending).
        """
        if not self._fpl_service:
            raise ValueError("FPL service not set")

        # Update fixture data
        await self.update_fixture_data()

        players = self._fpl_service.get_all_players()
        current_gw_obj = self._fpl_service.get_current_gameweek()
        current_gw = current_gw_obj.id if hasattr(current_gw_obj, 'id') else current_gw_obj

        predictions = []

        for player in players:
            # Check availability
            is_available, availability_reason = self.check_availability(player)

            # Predict probability of playing
            p_plays = self.predict_p_plays(player, current_gw)

            # Compute ML score
            ml_score, breakdown = self.compute_ml_score(player, current_gw)

            # Adjust score by probability of playing
            ml_score_adjusted = ml_score * p_plays

            predictions.append(PlayerPrediction(
                player_id=player.id,
                player_name=player.web_name,
                position=player.position,
                team_id=player.team,
                p_plays=round(p_plays, 3),
                ml_score=round(ml_score_adjusted, 1),
                nailedness_score=breakdown['nailedness'],
                form_score_xg=breakdown['form_xg'],
                form_score_pts=breakdown['form_pts'],
                fixture_score=breakdown['fixture'],
                is_available=is_available,
                availability_reason=availability_reason,
                chance_of_playing=player.chance_of_playing_next_round,
            ))

        # Sort by ML score descending
        predictions.sort(key=lambda x: x.ml_score, reverse=True)

        return predictions

    def filter_available_players(self, players: List,
                                  min_p_plays: float = 0.5) -> List:
        """
        Filter players by availability.

        Args:
            players: List of Player objects
            min_p_plays: Minimum P(plays) threshold (default 0.5)

        Returns:
            Filtered list of available players
        """
        if not self._fpl_service:
            return players

        current_gw_obj = self._fpl_service.get_current_gameweek()
        current_gw = current_gw_obj.id if hasattr(current_gw_obj, 'id') else current_gw_obj

        available = []
        for player in players:
            is_available, _ = self.check_availability(player)
            if not is_available:
                continue

            p_plays = self.predict_p_plays(player, current_gw)
            if p_plays >= min_p_plays:
                available.append(player)

        return available

    def get_player_prediction(self, player_id: int) -> Optional[PlayerPrediction]:
        """Get prediction for a single player by ID."""
        if not self._fpl_service:
            return None

        player = self._fpl_service.get_player(player_id)
        if not player:
            return None

        current_gw_obj = self._fpl_service.get_current_gameweek()
        current_gw = current_gw_obj.id if hasattr(current_gw_obj, 'id') else current_gw_obj

        is_available, availability_reason = self.check_availability(player)
        p_plays = self.predict_p_plays(player, current_gw)
        ml_score, breakdown = self.compute_ml_score(player, current_gw)

        return PlayerPrediction(
            player_id=player.id,
            player_name=player.web_name,
            position=player.position,
            team_id=player.team,
            p_plays=round(p_plays, 3),
            ml_score=round(ml_score * p_plays, 1),
            nailedness_score=breakdown['nailedness'],
            form_score_xg=breakdown['form_xg'],
            form_score_pts=breakdown['form_pts'],
            fixture_score=breakdown['fixture'],
            is_available=is_available,
            availability_reason=availability_reason,
            chance_of_playing=player.chance_of_playing_next_round,
        )


# Singleton instance
_ml_predictor_instance: Optional[MLPredictorService] = None


def get_ml_predictor_service() -> MLPredictorService:
    """Get or create the singleton MLPredictorService instance."""
    global _ml_predictor_instance
    if _ml_predictor_instance is None:
        _ml_predictor_instance = MLPredictorService()
    return _ml_predictor_instance
