"""SmartPlay FPL squad solver.

A mixed-integer linear program over expected points: pick the squad, the
starting eleven, the captain and the transfers that maximise projected points
across a multi-gameweek horizon, subject to every FPL rule — budget, three per
club, formation, the transfer bank, hit costs and chips.

Solved with HiGHS via ``highspy``. Self-contained: it takes projections as a
DataFrame and a team as a dict, and touches no database or network.

    from solver import prepare_data, solve_multi_period_fpl

    prepared  = prepare_data(team_json, options)
    solutions = solve_multi_period_fpl(prepared, team_json, options)

See ``README.md`` for the required option keys and a worked example that runs
off this repository's dataset and the published v12 model.
"""

from .prep import PreparedData, prepare_data
from .solve import solve_multi_period_fpl

__all__ = [
    "PreparedData",
    "prepare_data",
    "solve_multi_period_fpl",
]
