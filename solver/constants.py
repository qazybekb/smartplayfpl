from __future__ import annotations

from dataclasses import dataclass


BINARY_THRESHOLD = 0.5

SQUAD_SIZE = 15
LINEUP_SIZE = 11
MAX_GAMEWEEK = 38
MAX_PLAYERS_PER_TEAM = 3

# Bench slots: 0 = bench GK, 1..3 = outfield bench order.
BENCH_ORDER = (0, 1, 2, 3)

# Default objective weights (legacy-compatible).
DEFAULT_BENCH_WEIGHTS: dict[int, float] = {0: 0.03, 1: 0.21, 2: 0.06, 3: 0.002}
DEFAULT_VCAP_WEIGHT = 0.1
DEFAULT_HIT_COST = 4.0
DEFAULT_ITB_VALUE = 0.02

# 2024/25+ rule: max 5 free transfers (modeled as states 0..5).
FT_STATES = (0, 1, 2, 3, 4, 5)
DEFAULT_FT_VALUE = 1.5

# Configurable “special FT week” mechanism (legacy default includes AFCON week).
DEFAULT_SPECIAL_FT_WEEKS: dict[int, int] = {16: 5}

# Big-M used in the legacy solver for FT carry constraints.
DEFAULT_BIG_M_FT = 20

# Per-position pool caps applied after the coarse EV/minutes filters. Sized so
# every realistic candidate survives; the cut is EV-dominated tail players.
DEFAULT_POOL_TOP_N_PER_POS: dict[str, int] = {"GKP": 12, "DEF": 30, "MID": 35, "FWD": 22}
# Cheapest playing players kept per position regardless of EV (budget enablers).
DEFAULT_POOL_CHEAP_PER_POS = 5

# Global-field posture tilt (protect|chase) — max multiplicative EV adjustment
# from overall ownership. Small by design: a tie-breaker, not a new objective.
DEFAULT_POSTURE_TILT = 0.12


@dataclass(frozen=True)
class ChipKeys:
    wc: str = "wc"
    fh: str = "fh"
    bb: str = "bb"
    tc: str = "tc"


FPL_CHIP_TO_SOLVER_KEY = {
    "wildcard": ("wc", "use_wc"),
    "freehit": ("fh", "use_fh"),
    "bboost": ("bb", "use_bb"),
    "3xc": ("tc", "use_tc"),
}

