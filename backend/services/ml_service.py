# backend/services/ml_service.py
"""
Machine Learning Service for FPL Expected Points Prediction

This module provides a transparent, data-driven approach to predicting
Fantasy Premier League player points using linear regression.

The model learns from historical gameweek data to understand:
- How fixture difficulty affects scoring
- Home vs away impact
- Position-specific patterns
- The relationship between form and future performance
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Try to import sklearn, fall back to manual implementation if not available
try:
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available, using manual linear regression")


@dataclass
class PlayerGameweek:
    """A single player's performance in one gameweek."""
    player_id: int
    player_name: str
    position: str
    team_id: int
    gameweek: int
    
    # Target variable
    total_points: int
    
    # Features
    minutes: int
    was_home: bool
    opponent_team: int
    opponent_fdr: float  # 1-5 scale
    
    # Performance metrics
    goals_scored: int
    assists: int
    clean_sheets: int
    bonus: int
    bps: int
    
    # Expected stats (xG, xA)
    expected_goals: float
    expected_assists: float
    ict_index: float
    
    # Context
    price: float  # In millions
    form: float  # Rolling 5-game average at that point
    ownership: float  # Percentage


@dataclass
class ModelCoefficients:
    """Learned coefficients from the regression model."""
    intercept: float
    form: float
    fdr: float
    is_home: float
    minutes_pct: float
    xg: float
    xa: float
    ict: float
    
    # Position coefficients (relative to baseline)
    pos_mid: float
    pos_fwd: float
    pos_gkp: float
    
    # Metadata
    r_squared: float
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Squared Error
    n_samples: int
    trained_at: str


@dataclass
class ModelPrediction:
    """Prediction for a single player."""
    player_id: int
    player_name: str
    position: str
    team: str
    
    # Prediction
    expected_points: float
    confidence_low: float  # 80% confidence interval
    confidence_high: float
    
    # Feature contributions (transparency!)
    contribution_form: float
    contribution_fdr: float
    contribution_home: float
    contribution_position: float
    contribution_xg: float
    contribution_other: float
    
    # Context
    form: float
    next_opponent: str
    fdr: float
    is_home: bool


class MLService:
    """
    Machine Learning service for FPL predictions.
    
    Uses Ridge Regression (L2 regularization) for stability.
    Provides full transparency into learned coefficients.
    """
    
    MODEL_FILE = "ml_model.json"  # Saved model coefficients
    
    def __init__(self):
        self._fpl_service = None
        self._training_data: List[PlayerGameweek] = []
        self._coefficients: Optional[ModelCoefficients] = None
        self._scaler = None
        self._model = None
        self._is_trained = False
        self._team_fdr_map: Dict[int, float] = {}
        self._team_names: Dict[int, str] = {}
        
        # Try to load saved model on init
        self._load_model()
        
    def set_fpl_service(self, fpl_service):
        """Set the FPL service for data access."""
        self._fpl_service = fpl_service
    
    def _load_model(self):
        """Load saved model coefficients from file."""
        import os
        model_path = os.path.join(os.path.dirname(__file__), "..", self.MODEL_FILE)
        
        if os.path.exists(model_path):
            try:
                with open(model_path, "r") as f:
                    data = json.load(f)
                
                self._coefficients = ModelCoefficients(
                    intercept=data["intercept"],
                    form=data["form"],
                    fdr=data["fdr"],
                    is_home=data["is_home"],
                    minutes_pct=data["minutes_pct"],
                    xg=data["xg"],
                    xa=data["xa"],
                    ict=data["ict"],
                    pos_mid=data["pos_mid"],
                    pos_fwd=data["pos_fwd"],
                    pos_gkp=data["pos_gkp"],
                    r_squared=data["r_squared"],
                    mae=data["mae"],
                    rmse=data["rmse"],
                    n_samples=data["n_samples"],
                    trained_at=data["trained_at"],
                )
                self._is_trained = True
                logger.info(f"Loaded saved ML model (R²={self._coefficients.r_squared:.3f})")
            except Exception as e:
                logger.warning(f"Failed to load saved model: {e}")
    
    def _save_model(self):
        """Save model coefficients to file."""
        if not self._coefficients:
            return
        
        import os
        model_path = os.path.join(os.path.dirname(__file__), "..", self.MODEL_FILE)
        
        data = {
            "intercept": self._coefficients.intercept,
            "form": self._coefficients.form,
            "fdr": self._coefficients.fdr,
            "is_home": self._coefficients.is_home,
            "minutes_pct": self._coefficients.minutes_pct,
            "xg": self._coefficients.xg,
            "xa": self._coefficients.xa,
            "ict": self._coefficients.ict,
            "pos_mid": self._coefficients.pos_mid,
            "pos_fwd": self._coefficients.pos_fwd,
            "pos_gkp": self._coefficients.pos_gkp,
            "r_squared": self._coefficients.r_squared,
            "mae": self._coefficients.mae,
            "rmse": self._coefficients.rmse,
            "n_samples": self._coefficients.n_samples,
            "trained_at": self._coefficients.trained_at,
        }
        
        with open(model_path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved ML model to {model_path}")
        
    @property
    def is_trained(self) -> bool:
        return self._is_trained
    
    @property
    def coefficients(self) -> Optional[ModelCoefficients]:
        return self._coefficients
    
    @property
    def training_data_size(self) -> int:
        return len(self._training_data)
    
    async def collect_training_data(self, max_players: int = 100) -> Dict:
        """
        Collect historical gameweek data for training.
        
        Args:
            max_players: Limit number of players to fetch (for speed)
            
        Returns:
            Summary of collected data
        """
        if not self._fpl_service:
            raise ValueError("FPL service not set")
        
        import httpx
        
        self._training_data = []
        players = self._fpl_service.get_all_players()
        teams = self._fpl_service.get_all_teams()
        
        # Build team name and FDR maps
        self._team_names = {t.id: t.short_name for t in teams}
        
        # Get fixtures to calculate FDR
        fixtures = self._fpl_service.get_fixtures()
        team_difficulties = {}
        for fixture in fixtures:
            if fixture.get("event") and fixture.get("finished"):
                team_h = fixture.get("team_h")
                team_a = fixture.get("team_a")
                if team_h:
                    if team_h not in team_difficulties:
                        team_difficulties[team_h] = []
                    team_difficulties[team_h].append(fixture.get("team_h_difficulty", 3))
                if team_a:
                    if team_a not in team_difficulties:
                        team_difficulties[team_a] = []
                    team_difficulties[team_a].append(fixture.get("team_a_difficulty", 3))
        
        self._team_fdr_map = {
            team_id: sum(fdrs) / len(fdrs) if fdrs else 3.0
            for team_id, fdrs in team_difficulties.items()
        }
        
        # Filter to players with significant minutes
        active_players = [p for p in players if (p.minutes or 0) > 200]
        active_players = sorted(active_players, key=lambda x: x.total_points or 0, reverse=True)
        active_players = active_players[:max_players]
        
        collected = 0
        errors = 0
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for player in active_players:
                try:
                    # Fetch player's GW history
                    response = await client.get(
                        f"https://fantasy.premierleague.com/api/element-summary/{player.id}/",
                        headers={"User-Agent": "GraphFPL-ML-Model"}
                    )
                    
                    if response.status_code != 200:
                        errors += 1
                        continue
                    
                    data = response.json()
                    history = data.get("history", [])
                    
                    # Calculate rolling form for each GW
                    points_history = []
                    
                    for gw_data in history:
                        gw = gw_data.get("round", 0)
                        minutes = gw_data.get("minutes", 0)
                        
                        # Skip GWs with no minutes
                        if minutes == 0:
                            points_history.append(0)
                            continue
                        
                        # Calculate form (avg of previous 5 GWs)
                        if len(points_history) >= 5:
                            form = sum(points_history[-5:]) / 5
                        elif len(points_history) > 0:
                            form = sum(points_history) / len(points_history)
                        else:
                            form = 0
                        
                        opponent = gw_data.get("opponent_team", 0)
                        opponent_fdr = self._team_fdr_map.get(opponent, 3.0)
                        
                        gw_record = PlayerGameweek(
                            player_id=player.id,
                            player_name=player.web_name,
                            position=player.position,
                            team_id=player.team,
                            gameweek=gw,
                            total_points=gw_data.get("total_points", 0),
                            minutes=minutes,
                            was_home=gw_data.get("was_home", False),
                            opponent_team=opponent,
                            opponent_fdr=opponent_fdr,
                            goals_scored=gw_data.get("goals_scored", 0),
                            assists=gw_data.get("assists", 0),
                            clean_sheets=gw_data.get("clean_sheets", 0),
                            bonus=gw_data.get("bonus", 0),
                            bps=gw_data.get("bps", 0),
                            expected_goals=float(gw_data.get("expected_goals", 0) or 0),
                            expected_assists=float(gw_data.get("expected_assists", 0) or 0),
                            ict_index=float(gw_data.get("ict_index", 0) or 0),
                            price=gw_data.get("value", 0) / 10,
                            form=form,
                            ownership=gw_data.get("selected", 0) / 100000,  # Normalize
                        )
                        
                        self._training_data.append(gw_record)
                        points_history.append(gw_data.get("total_points", 0))
                    
                    collected += 1
                    
                except Exception as e:
                    logger.warning(f"Error fetching player {player.id}: {e}")
                    errors += 1
        
        return {
            "players_collected": collected,
            "total_samples": len(self._training_data),
            "errors": errors,
            "positions": self._count_by_position(),
        }
    
    def _count_by_position(self) -> Dict[str, int]:
        """Count samples by position."""
        counts = {}
        for gw in self._training_data:
            counts[gw.position] = counts.get(gw.position, 0) + 1
        return counts
    
    def train_model(self) -> ModelCoefficients:
        """
        Train the regression model on collected data.
        
        Uses Ridge Regression (L2 regularization) for stability.
        
        Returns:
            ModelCoefficients with learned weights
        """
        if len(self._training_data) < 100:
            raise ValueError(f"Not enough training data: {len(self._training_data)} samples")
        
        # Prepare features and target
        X, y, feature_names = self._prepare_features()
        
        if SKLEARN_AVAILABLE:
            # Use sklearn Ridge Regression
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)
            
            self._model = Ridge(alpha=1.0)
            self._model.fit(X_scaled, y)
            
            # Cross-validation for metrics
            cv_scores = cross_val_score(self._model, X_scaled, y, cv=5, scoring='r2')
            r_squared = np.mean(cv_scores)
            
            # Predictions for error metrics
            y_pred = self._model.predict(X_scaled)
            mae = np.mean(np.abs(y - y_pred))
            rmse = np.sqrt(np.mean((y - y_pred) ** 2))
            
            # Get coefficients (unscaled for interpretability)
            coef = self._model.coef_
            intercept = self._model.intercept_
            
        else:
            # Manual Ridge Regression implementation
            # Add regularization term: (X'X + λI)^-1 X'y
            lambda_reg = 1.0
            X_with_intercept = np.column_stack([np.ones(X.shape[0]), X])
            
            XtX = X_with_intercept.T @ X_with_intercept
            XtX += lambda_reg * np.eye(XtX.shape[0])
            Xty = X_with_intercept.T @ y
            
            weights = np.linalg.solve(XtX, Xty)
            intercept = weights[0]
            coef = weights[1:]
            
            # Calculate metrics
            y_pred = X_with_intercept @ weights
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)
            mae = np.mean(np.abs(y - y_pred))
            rmse = np.sqrt(np.mean((y - y_pred) ** 2))
        
        # Map coefficients to named features
        coef_dict = dict(zip(feature_names, coef))
        
        self._coefficients = ModelCoefficients(
            intercept=float(intercept),
            form=coef_dict.get("form", 0),
            fdr=coef_dict.get("fdr", 0),
            is_home=coef_dict.get("is_home", 0),
            minutes_pct=coef_dict.get("minutes_pct", 0),
            xg=coef_dict.get("xg", 0),
            xa=coef_dict.get("xa", 0),
            ict=coef_dict.get("ict", 0),
            pos_mid=coef_dict.get("pos_MID", 0),
            pos_fwd=coef_dict.get("pos_FWD", 0),
            pos_gkp=coef_dict.get("pos_GKP", 0),
            r_squared=float(r_squared),
            mae=float(mae),
            rmse=float(rmse),
            n_samples=len(self._training_data),
            trained_at=datetime.now().isoformat(),
        )
        
        self._is_trained = True
        logger.info(f"Model trained: R²={r_squared:.3f}, MAE={mae:.2f}, RMSE={rmse:.2f}")
        
        # Save model for persistence
        self._save_model()
        
        return self._coefficients
    
    def _prepare_features(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare feature matrix and target vector."""
        
        feature_names = [
            "form", "fdr", "is_home", "minutes_pct",
            "xg", "xa", "ict",
            "pos_MID", "pos_FWD", "pos_GKP"
        ]
        
        X = []
        y = []
        
        for gw in self._training_data:
            # Skip samples with 0 minutes (no data to learn from)
            if gw.minutes == 0:
                continue
            
            features = [
                gw.form,
                gw.opponent_fdr,
                1.0 if gw.was_home else 0.0,
                gw.minutes / 90.0,  # Normalize to 0-1
                gw.expected_goals,
                gw.expected_assists,
                gw.ict_index / 10.0,  # Normalize
                1.0 if gw.position == "MID" else 0.0,
                1.0 if gw.position == "FWD" else 0.0,
                1.0 if gw.position == "GKP" else 0.0,
            ]
            
            X.append(features)
            y.append(gw.total_points)
        
        return np.array(X), np.array(y), feature_names
    
    async def predict_all_players(self) -> List[ModelPrediction]:
        """
        Generate predictions for all current players.
        
        Returns:
            List of predictions sorted by expected points
        """
        if not self._is_trained:
            raise ValueError("Model not trained yet")
        
        if not self._fpl_service:
            raise ValueError("FPL service not set")
        
        players = self._fpl_service.get_all_players()
        fixtures = self._fpl_service.get_fixtures()
        current_gw = self._fpl_service.get_current_gameweek()
        
        # Get next fixture for each team
        team_next_fixture = {}
        for fixture in fixtures:
            gw = fixture.get("event")
            if gw == current_gw:
                team_h = fixture.get("team_h")
                team_a = fixture.get("team_a")
                if team_h and team_h not in team_next_fixture:
                    team_next_fixture[team_h] = {
                        "opponent": team_a,
                        "is_home": True,
                        "fdr": fixture.get("team_h_difficulty", 3),
                    }
                if team_a and team_a not in team_next_fixture:
                    team_next_fixture[team_a] = {
                        "opponent": team_h,
                        "is_home": False,
                        "fdr": fixture.get("team_a_difficulty", 3),
                    }
        
        predictions = []
        
        for player in players:
            # Skip unavailable players
            if player.status not in ("a", "d"):
                continue
            
            fixture_info = team_next_fixture.get(player.team, {})
            if not fixture_info:
                continue
            
            form = player.form_float or 0
            fdr = fixture_info.get("fdr", 3)
            is_home = fixture_info.get("is_home", False)
            opponent_id = fixture_info.get("opponent", 0)
            
            # Build feature vector
            features = np.array([[
                form,
                fdr,
                1.0 if is_home else 0.0,
                1.0,  # Assume full minutes
                0.0,  # xG not available for prediction
                0.0,  # xA not available
                (player.ict_index or 0) / 10.0,
                1.0 if player.position == "MID" else 0.0,
                1.0 if player.position == "FWD" else 0.0,
                1.0 if player.position == "GKP" else 0.0,
            ]])
            
            # Make prediction
            if SKLEARN_AVAILABLE and self._scaler and self._model:
                features_scaled = self._scaler.transform(features)
                expected = self._model.predict(features_scaled)[0]
            else:
                # Manual prediction
                expected = self._coefficients.intercept
                expected += form * self._coefficients.form
                expected += fdr * self._coefficients.fdr
                expected += (1.0 if is_home else 0.0) * self._coefficients.is_home
                expected += 1.0 * self._coefficients.minutes_pct
                expected += (player.ict_index or 0) / 10.0 * self._coefficients.ict
                if player.position == "MID":
                    expected += self._coefficients.pos_mid
                elif player.position == "FWD":
                    expected += self._coefficients.pos_fwd
                elif player.position == "GKP":
                    expected += self._coefficients.pos_gkp
            
            # Calculate confidence interval (using RMSE)
            rmse = self._coefficients.rmse if self._coefficients else 2.5
            confidence_low = max(0, expected - 1.28 * rmse)  # 80% CI
            confidence_high = expected + 1.28 * rmse
            
            # Calculate feature contributions
            c = self._coefficients
            contribution_form = form * c.form if c else 0
            contribution_fdr = fdr * c.fdr if c else 0
            contribution_home = (1.0 if is_home else 0.0) * c.is_home if c else 0
            
            pos_contrib = 0
            if player.position == "MID" and c:
                pos_contrib = c.pos_mid
            elif player.position == "FWD" and c:
                pos_contrib = c.pos_fwd
            elif player.position == "GKP" and c:
                pos_contrib = c.pos_gkp
            
            predictions.append(ModelPrediction(
                player_id=player.id,
                player_name=player.web_name,
                position=player.position,
                team=self._fpl_service.get_team_short_name(player.team),
                expected_points=round(expected, 2),
                confidence_low=round(confidence_low, 2),
                confidence_high=round(confidence_high, 2),
                contribution_form=round(contribution_form, 2),
                contribution_fdr=round(contribution_fdr, 2),
                contribution_home=round(contribution_home, 2),
                contribution_position=round(pos_contrib, 2),
                contribution_xg=0,  # Not available for future predictions
                contribution_other=round(c.intercept if c else 0, 2),
                form=form,
                next_opponent=self._team_names.get(opponent_id, "???"),
                fdr=fdr,
                is_home=is_home,
            ))
        
        # Sort by expected points descending
        predictions.sort(key=lambda x: x.expected_points, reverse=True)
        
        return predictions


# Singleton instance
_ml_service_instance: Optional[MLService] = None


def get_ml_service() -> MLService:
    """Get or create the singleton MLService instance."""
    global _ml_service_instance
    if _ml_service_instance is None:
        _ml_service_instance = MLService()
    return _ml_service_instance

