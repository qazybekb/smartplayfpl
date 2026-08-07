# solver

The squad optimiser behind [smartplayfpl.com](https://smartplayfpl.com). Given
expected points per player per gameweek, it picks the squad, the starting
eleven, the captain and the transfers that maximise projected points over a
multi-gameweek horizon, subject to every FPL rule.

It is a mixed-integer linear program, solved with
[HiGHS](https://highs.dev) via `highspy`. Self-contained — projections in as a
DataFrame, a team in as a dict, no database and no network.

## Why this is open

The best-known FPL optimiser,
[sertalpbilal/FPL-Optimization-Tools](https://github.com/sertalpbilal/FPL-Optimization-Tools),
is already open and already uses HiGHS. The constraint set is not a secret and
keeping ours closed would protect nothing. What is genuinely hard in this
problem is the projections, and those are published too — see
[the v12 model](https://huggingface.co/Qazybek/smartplay-fpl-v12).

## Run it

```bash
pip install -r ../requirements.txt huggingface_hub highspy
python solver/example.py --season 2025-26 --gameweek 30
```

`example.py` is a wildcard from scratch: it loads the dataset in `data/`,
predicts with v12, reshapes into the projection columns the solver wants, and
solves for the best legal 15 on £100.0m. It needs no FPL entry id, so it runs
for anyone.

## What it models

| Rule | How |
|---|---|
| Squad | 15 players, 2 GKP / 5 DEF / 5 MID / 3 FWD |
| Lineup | 11 starters, legal formation, one captain and one vice |
| Budget | Squad value plus bank, with selling-price accounting |
| Club limit | At most 3 from any one club |
| Transfers | Free-transfer bank as states 0-5, hits at 4 points each |
| Chips | Wildcard, Free Hit, Bench Boost, Triple Captain |
| Bench | Weighted by the chance each slot actually plays |
| Horizon | Multi-gameweek, later weeks discounted by `decay` |

Bench weights, hit cost, decay and the free-transfer valuation are in
`constants.py`. They are defaults, not constants of nature — `DEFAULT_FT_VALUE
= 1.5` says a banked transfer is worth 1.5 projected points, which is a
judgement call you may reasonably disagree with.

## Interface

```python
from solver import prepare_data, solve_multi_period_fpl

prepared  = prepare_data(team_json, options)
solutions = solve_multi_period_fpl(prepared, team_json, options)
best = solutions[0]        # picks (DataFrame), total_xp, statistics, summary
```

`options` must carry `fpl_elements_df`, `fpl_teams_df`, `data_df`,
`fixtures` and `override_next_gw`. Those are required rather than fetched on
your behalf: the solver never calls the FPL API, so what it optimised is
exactly what you handed it. `data_df` needs an `ID` column and, for each
gameweek in the horizon, `{gw}_Pts` and `{gw}_xMins`.

## Performance

A three-gameweek solve over the full player pool takes a few seconds. Longer
horizons and chip combinations cost more, since each chip adds binaries. The
per-position pool caps in `constants.py` exist for that reason — they trim
EV-dominated tail players before the MILP sees them, and in our backtests the
trimmed pool was lossless against the full one while being materially faster.

## Licence

CC BY-NC 4.0, like the rest of this repository.
