"""
OpenFPL model package.

Provides OpenFPLPredictor for inference and feature engineering utilities
for building input samples from smartplay_data.csv + Understat API data.
"""

from .predictor import OpenFPLPredictor
from .feature_engineering import (
    load_data,
    build_understat_team_matches,
    build_opponent_lookup,
    compute_league_ranks,
    compute_team_rolling,
    compute_player_rolling,
    build_samples,
    fpl_to_us,
)
from .constants import WINDOWS, POSITIONS, FPL_TO_UNDERSTAT, POS_MAP
