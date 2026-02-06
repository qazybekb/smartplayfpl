"""
Constants for the OpenFPL prediction model.
Extracted from daniegr/OpenFPL with local adaptations for SmartPlayFPL data format.
"""

# Rolling window sizes used for all feature computations
WINDOWS = [1, 3, 5, 10, 38]

# FPL short team names -> Understat team names
FPL_TO_UNDERSTAT = {
    'Man City': 'Manchester City',
    'Man Utd': 'Manchester United',
    'Newcastle': 'Newcastle United',
    "Nott'm Forest": 'Nottingham Forest',
    'Sheffield Utd': 'Sheffield United',
    'Spurs': 'Tottenham',
    'West Brom': 'West Bromwich Albion',
    'Wolves': 'Wolverhampton Wanderers',
}

# FPL position codes -> OpenFPL position codes
POS_MAP = {'GKP': 'GK', 'DEF': 'DEF', 'MID': 'MID', 'FWD': 'FWD'}

# Positions used for inference (AM models exist but are unused)
POSITIONS = ['GK', 'DEF', 'MID', 'FWD']

NUM_CV_FOLDS = 5

# Player feature mappings: merged CSV column -> OpenFPL feature name
# 22 source columns, each computed over 5 windows = 110 player rolling features
PLAYER_FEATURES = {
    'total_points': 'fpl_points',
    'minutes': 'minutes_played',
    'influence': 'influence',
    'creativity': 'creativity',
    'threat': 'threat',
    'goals_scored': 'goals_scored',
    'penalties_missed': 'penalties_missed',
    'assists': 'assists',
    'goals_conceded': 'goals_conceded',
    'own_goals': 'own_goals',
    'saves': 'saves',
    'penalties_saved': 'penalties_saved',
    'yellow_cards': 'yellow_cards',
    'red_cards': 'red_cards',
    'bps': 'bps',
    'bonus': 'fpl_bonus_points',
    'us_shots': 'shots',
    'us_xG': 'xg',
    'us_xGChain': 'xgchain',
    'us_xGBuildup': 'xgbuildup',
    'us_key_passes': 'key_passes',
    'us_xA': 'xa',
}

# Ordered list for building sample columns (includes relevant_fpl_points)
PLAYER_FEATURE_ORDER = [
    'fpl_points', 'relevant_fpl_points', 'minutes_played', 'influence', 'creativity',
    'threat', 'goals_scored', 'penalties_missed', 'assists', 'goals_conceded',
    'own_goals', 'saves', 'penalties_saved', 'yellow_cards', 'red_cards',
    'bps', 'fpl_bonus_points', 'shots', 'xg', 'xgchain', 'xgbuildup',
    'key_passes', 'xa',
]

# Team feature mappings: understat column -> OpenFPL feature name
# 12 source columns, each over 5 windows = 60 team rolling features
TEAM_FEATURES = {
    'scored': 'goals_scored',
    'missed': 'goals_conceded',
    'league_rank': 'league_rank',
    'opp_league_rank': 'opponent_league_rank',
    'xG': 'xg',
    'deep_allowed': 'deep_allowed',
    'ppda_allowed_att': 'ppda_allowed_att',
    'ppda_allowed_def': 'ppda_allowed_def',
    'xGA': 'xga',
    'deep': 'deep',
    'ppda_att': 'ppda_att',
    'ppda_def': 'ppda_def',
}

TEAM_FEATURE_ORDER = [
    'goals_scored', 'goals_conceded', 'league_rank', 'opponent_league_rank',
    'xg', 'deep_allowed', 'ppda_allowed_att', 'ppda_allowed_def',
    'xga', 'deep', 'ppda_att', 'ppda_def',
]

# Opponent features: subset of team features used for opponent rolling
# 10 features over 5 windows = 50 opponent rolling features
OPPONENT_FEATURE_ORDER = [
    'goals_scored', 'goals_conceded', 'xg', 'deep_allowed',
    'ppda_allowed_att', 'ppda_allowed_def', 'xga', 'deep',
    'ppda_att', 'ppda_def',
]

# Numeric columns to coerce in merged CSV
MERGED_NUMERIC_COLS = [
    'total_points', 'minutes', 'influence', 'creativity', 'threat',
    'goals_scored', 'penalties_missed', 'assists', 'goals_conceded',
    'own_goals', 'saves', 'penalties_saved', 'yellow_cards', 'red_cards',
    'bps', 'bonus', 'us_shots', 'us_xG', 'us_xGChain', 'us_xGBuildup',
    'us_key_passes', 'us_xA', 'us_team_xG', 'us_team_xGA',
    'us_deep', 'us_deep_allowed', 'team_h_score', 'team_a_score',
]

# Numeric columns to coerce in understat team matches CSV
TEAM_MATCHES_NUMERIC_COLS = [
    'scored', 'missed', 'xG', 'xGA', 'deep', 'deep_allowed',
    'ppda_att', 'ppda_def', 'ppda_allowed_att', 'ppda_allowed_def',
]
