from __future__ import annotations

import math
import time
from dataclasses import asdict
from typing import Any

import highspy
import pandas as pd

from .constants import (
    BENCH_ORDER,
    BINARY_THRESHOLD,
    DEFAULT_BENCH_WEIGHTS,
    DEFAULT_BIG_M_FT,
    DEFAULT_FT_VALUE,
    DEFAULT_HIT_COST,
    DEFAULT_ITB_VALUE,
    DEFAULT_SPECIAL_FT_WEEKS,
    DEFAULT_VCAP_WEIGHT,
    FT_STATES,
    LINEUP_SIZE,
    MAX_GAMEWEEK,
    MAX_PLAYERS_PER_TEAM,
    SQUAD_SIZE,
    FPL_CHIP_TO_SOLVER_KEY,
)
from .prep import PreparedData


def _chip_text(wc: float, fh: float, bb: float, tc_gw: float) -> str:
    if wc > BINARY_THRESHOLD:
        return "WC"
    if fh > BINARY_THRESHOLD:
        return "FH"
    if bb > BINARY_THRESHOLD:
        return "BB"
    if tc_gw > BINARY_THRESHOLD:
        return "TC"
    return ""


def _detect_active_chip(team_json: dict[str, Any]) -> tuple[str, str] | None:
    for chip in team_json.get("chips", []) or []:
        if not isinstance(chip, dict):
            continue
        if chip.get("status_for_entry") != "active":
            continue
        name = str(chip.get("name") or "")
        if name in FPL_CHIP_TO_SOLVER_KEY:
            return FPL_CHIP_TO_SOLVER_KEY[name]
    return None


def _as_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out: list[int] = []
        for item in value:
            try:
                out.append(int(item))
            except Exception:
                continue
        return out
    try:
        return [int(value)]
    except Exception:
        return []


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        n = float(value)
    except Exception:
        return fallback
    return n if math.isfinite(n) else fallback


def _parse_league_context(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("version") != 1:
        return None
    mode = value.get("mode")
    if mode not in {"protect", "balanced", "chase"}:
        return None
    ownership = value.get("ownership_by_element_id")
    if not isinstance(ownership, dict) or not ownership:
        return None

    weight = _clamp(_as_float(value.get("weight"), 0.0), 0.0, 2.0)
    rivals_analyzed = int(_as_float(value.get("rivals_analyzed"), 0.0))
    if weight <= 0 or rivals_analyzed < 3:
        return None

    return {
        "league_id": value.get("league_id"),
        "league_name": str(value.get("league_name") or ""),
        "mode": mode,
        "label": str(value.get("label") or mode),
        "weight": weight,
        "rivals_analyzed": rivals_analyzed,
        "sample_kind": str(value.get("sample_kind") or ""),
        "points_band": value.get("points_band"),
        "ownership_by_element_id": ownership,
    }


def _league_ownership(context: dict[str, Any], player_id: int) -> dict[str, float]:
    ownership = context.get("ownership_by_element_id") or {}
    raw = ownership.get(str(player_id)) if isinstance(ownership, dict) else None
    if not isinstance(raw, dict):
        return {"squad": 0.0, "starting": 0.0, "captain": 0.0}
    return {
        "squad": _clamp(_as_float(raw.get("squad"), 0.0), 0.0, 1.0),
        "starting": _clamp(_as_float(raw.get("starting"), 0.0), 0.0, 1.0),
        "captain": _clamp(_as_float(raw.get("captain"), 0.0), 0.0, 1.0),
    }


def _league_signal(mode: str, ownership: float) -> float:
    # Positive signal means "this player helps the league-state objective".
    # Protect rewards template cover. Chase/balanced reward separation.
    if mode == "protect":
        return _clamp((ownership - 0.5) * 2.0, -1.0, 1.0)
    return _clamp((0.5 - ownership) * 2.0, -1.0, 1.0)


def solve_multi_period_fpl(prepared: PreparedData, team_json: dict[str, Any], options: dict[str, Any]) -> list[dict[str, Any]]:
    """
    First-party SmartPlay MILP solver (legacy-compatible behavior).

    Returns a list of solution dicts with keys:
      - picks: pandas DataFrame
      - statistics: dict
      - score: float
      - summary: str
      - total_xp: float
      - meta: dict
    """

    solve_started = time.time()

    next_gw = int(prepared.next_gw)
    horizon = int(options.get("horizon", len(range(next_gw, MAX_GAMEWEEK + 1))))
    last_gw = min(MAX_GAMEWEEK, next_gw + max(0, horizon - 1))
    gws = list(range(next_gw, last_gw + 1))
    horizon = len(gws)
    all_gw = [next_gw - 1, *gws]

    objective = str(options.get("objective", "decay") or "decay")
    decay_base = float(options.get("decay_base", 0.84) or 0.84)

    bench_weights_raw = options.get("bench_weights") or DEFAULT_BENCH_WEIGHTS
    bench_weights = {int(k): float(v) for k, v in dict(bench_weights_raw).items()}

    ft_value = float(options.get("ft_value", DEFAULT_FT_VALUE) or DEFAULT_FT_VALUE)
    ft_value_list = options.get("ft_value_list") or {}
    if not isinstance(ft_value_list, dict):
        ft_value_list = {}

    itb_value = float(options.get("itb_value", DEFAULT_ITB_VALUE) or DEFAULT_ITB_VALUE)
    hit_cost = float(options.get("hit_cost", DEFAULT_HIT_COST) or DEFAULT_HIT_COST)
    vcap_weight = float(options.get("vcap_weight", DEFAULT_VCAP_WEIGHT) or DEFAULT_VCAP_WEIGHT)

    ft_use_penalty = options.get("ft_use_penalty")
    ft_use_penalty = float(ft_use_penalty) if ft_use_penalty is not None else 0.0

    itb_loss_per_transfer = options.get("itb_loss_per_transfer")
    itb_loss_per_transfer = float(itb_loss_per_transfer) if itb_loss_per_transfer is not None else 0.0

    league_context = _parse_league_context(options.get("league_context"))
    league_mode = str(league_context.get("mode")) if league_context else ""
    league_weight = float(league_context.get("weight")) if league_context else 0.0

    weekly_hit_limit = options.get("weekly_hit_limit", None)
    hit_limit = options.get("hit_limit", None)

    chip_limits = options.get("chip_limits") or {}
    if not isinstance(chip_limits, dict):
        chip_limits = {}

    allowed_chip_gws = options.get("allowed_chip_gws") or {}
    forced_chip_gws = options.get("forced_chip_gws") or {}
    if not isinstance(allowed_chip_gws, dict):
        allowed_chip_gws = {}
    if not isinstance(forced_chip_gws, dict):
        forced_chip_gws = {}

    booked_transfers = options.get("booked_transfers") or []
    if not isinstance(booked_transfers, list):
        booked_transfers = []

    special_ft_weeks = options.get("special_ft_weeks") or DEFAULT_SPECIAL_FT_WEEKS
    if not isinstance(special_ft_weeks, dict):
        special_ft_weeks = DEFAULT_SPECIAL_FT_WEEKS
    special_ft_weeks = {int(k): int(v) for k, v in special_ft_weeks.items()}

    players = [int(x) for x in prepared.merged_data.index.to_list()]
    order = list(BENCH_ORDER)
    ft_states = list(FT_STATES)

    type_data = prepared.type_data
    el_types = [int(x) for x in type_data.index.to_list()]
    teams = [str(x) for x in prepared.team_data["team_name"].to_list()]

    merged = prepared.merged_data
    player_type = {int(pid): int(merged.loc[pid, "element_type"]) for pid in players}
    player_team = {int(pid): str(merged.loc[pid, "team_name"]) for pid in players}
    players_by_team: dict[str, list[int]] = {}
    for pid in players:
        players_by_team.setdefault(player_team[pid], []).append(pid)

    # Clamp forced chip windows into the solve horizon (legacy behavior).
    gws_set = set(gws)
    forced_chip_gws = {
        str(k): [int(w) if int(w) in gws_set else next_gw for w in (v or [])]
        for k, v in forced_chip_gws.items()
        if isinstance(v, (list, tuple))
    }

    highs = highspy.Highs()

    verbose = bool(options.get("verbose", False))
    highs.setOptionValue("log_to_console", bool(verbose))
    # threads=1 disables HiGHS parallelism — the right mode when several solver
    # sidecars share a small container (HiGHS itself recommends single-thread
    # instances for concurrent independent solves). 0 = HiGHS decides.
    solver_threads = int(options.get("threads", 0) or 0)
    if solver_threads == 1:
        highs.setOptionValue("parallel", "off")
        highs.setOptionValue("threads", 1)
    else:
        highs.setOptionValue("parallel", "on")
        if solver_threads > 1:
            highs.setOptionValue("threads", solver_threads)
    highs.setOptionValue("random_seed", int(options.get("random_seed", 0) or 0))
    highs.setOptionValue("presolve", str(options.get("presolve", "on") or "on"))
    highs.setOptionValue("time_limit", float(options.get("secs", 60) or 60))
    highs.setOptionValue("mip_rel_gap", float(options.get("gap", 0) or 0))

    # -------------------
    # Variables
    # -------------------

    squad = highs.addBinaries(players, all_gw, name_prefix="squad")
    squad_fh = highs.addBinaries(players, gws, name_prefix="squad_fh")
    lineup = highs.addBinaries(players, gws, name_prefix="lineup")
    captain = highs.addBinaries(players, gws, name_prefix="captain")
    vicecap = highs.addBinaries(players, gws, name_prefix="vicecap")
    bench = highs.addBinaries(players, gws, order, name_prefix="bench")

    transfer_in = highs.addBinaries(players, gws, name_prefix="tr_in")
    transfer_out_regular = highs.addBinaries(players, gws, name_prefix="tr_out_reg")

    price_modified_players = list(prepared.price_modified_players)
    price_modified_set = set(price_modified_players)
    transfer_out_first = (
        highs.addBinaries(price_modified_players, gws, name_prefix="tr_out_first")
        if price_modified_players
        else {}
    )

    def transfer_out(p: int, w: int):
        if p in price_modified_set:
            return transfer_out_regular[p, w] + transfer_out_first[p, w]
        return transfer_out_regular[p, w]

    in_the_bank = highs.addVariables(all_gw, lb=0.0, ub=highspy.kHighsInf, name_prefix="itb")
    fts = highs.addVariables(all_gw, lb=0.0, ub=5.0, type=highspy.HighsVarType.kInteger, name_prefix="ft")

    ft_above = highs.addBinaries(gws, name_prefix="ft_above")
    ft_below = highs.addBinaries(gws, name_prefix="ft_below")
    ft_state = highs.addBinaries(gws, ft_states, name_prefix="ft_state")

    penalized_transfers = highs.addVariables(gws, lb=0.0, ub=float(SQUAD_SIZE), type=highspy.HighsVarType.kInteger, name_prefix="pt")
    transfer_count = highs.addVariables(gws, lb=0.0, ub=float(SQUAD_SIZE), type=highspy.HighsVarType.kInteger, name_prefix="trc")

    use_wc = highs.addBinaries(gws, name_prefix="use_wc")
    use_bb = highs.addBinaries(gws, name_prefix="use_bb")
    use_fh = highs.addBinaries(gws, name_prefix="use_fh")
    use_tc = highs.addBinaries(players, gws, name_prefix="use_tc")

    # Optional edge-case relaxation (invalid current squad).
    no_transfer_relax = None
    if int(prepared.max_players_from_team) > MAX_PLAYERS_PER_TEAM:
        no_transfer_relax = highs.addBinaries(gws, name_prefix="no_tr_relax")

    # -------------------
    # Initial conditions
    # -------------------

    initial_squad = set(int(x) for x in prepared.initial_squad)
    missing_count = SQUAD_SIZE - len(initial_squad)
    for p in players:
        if p in initial_squad:
            highs.addConstr(squad[p, next_gw - 1] == 1)
        elif missing_count == 0:
            # Normal case: force non-squad players to 0
            highs.addConstr(squad[p, next_gw - 1] == 0)
        # When missing_count > 0, non-initial players are left free at
        # next_gw - 1 so the solver can fill the gap(s). Whether that fill is
        # budget-constrained depends on WHY the squad is short (see below).

    # There are two ways the boundary squad can be short, and they need
    # different treatment:
    #
    #  (draft) initial_squad is empty — a build-from-scratch request. Nothing was
    #          owned, so the whole squad must be bought within the budget.
    #  (b)     prep.py dropped squad member(s) absent from the projection pool
    #          and CREDITED their selling price to the bank (meta
    #          "missing_squad_members" > 0). The replacement(s) must be bought
    #          from that credited bank — otherwise the manager keeps the credit
    #          AND gets the fill free (a bounded over-budget of ~one player's
    #          price). This is the paid-solver double-credit fix.
    #  (a)     the caller simply passed fewer than 15 picks with no credit (e.g.
    #          the backtest harness pre-filtering its reduced per-GW pool). Here
    #          the original free fill is the feasibility escape valve — there is
    #          no credited budget to pay from — so it is left unchanged.
    #
    # For (draft) and (b) we pin a full squad plus budget conservation:
    #   sum(buy_price * squad[next_gw-1]) + bank == itb + sum(buy_price[owned]).
    # The owned members' buy_price cancels (they are forced to 1 on the LHS too),
    # leaving  sum(buy_price * fills) + bank == itb  (itb already includes the
    # credit in case (b)). bank >= 0 makes this an effective <= itb cap, so it
    # stays feasible whenever an affordable formation-completing fill exists —
    # which the credit guarantees. Case (a) and complete squads are untouched.
    credited_missing = int((prepared.meta or {}).get("missing_squad_members", 0) or 0)
    if len(initial_squad) == 0 or credited_missing > 0:
        highs.addConstr(sum(squad[p, next_gw - 1] for p in players) == SQUAD_SIZE)
        highs.addConstr(
            sum(prepared.buy_price[p] * squad[p, next_gw - 1] for p in players)
            + in_the_bank[next_gw - 1]
            == float(prepared.itb) + sum(prepared.buy_price[p] for p in initial_squad)
        )
    else:
        highs.addConstr(in_the_bank[next_gw - 1] == float(prepared.itb))

    initial_ft = max(0, int(prepared.ft))
    ft_base = int(prepared.ft_base)
    highs.addConstr(fts[next_gw] == initial_ft * (1 - use_wc[next_gw]) + ft_base * use_wc[next_gw])

    for w in gws:
        if w > next_gw:
            highs.addConstr(fts[w] >= 1)

    # -------------------
    # Core constraints
    # -------------------

    # Transfer direction constraints (FPL rules):
    # - You can only buy a player you didn't own in the previous GW.
    # - You can only sell a player you owned in the previous GW.
    #
    # These also prevent "in and out in the same GW" loopholes that could
    # satisfy booked transfers without actually changing the squad.
    for w in gws:
        for p in players:
            highs.addConstr(transfer_in[p, w] <= 1 - squad[p, w - 1])
            highs.addConstr(transfer_out(p, w) <= squad[p, w - 1])

    # Squad sizes
    for w in gws:
        highs.addConstr(sum(squad[p, w] for p in players) == SQUAD_SIZE)
        highs.addConstr(sum(squad_fh[p, w] for p in players) == SQUAD_SIZE * use_fh[w])

        highs.addConstr(sum(lineup[p, w] for p in players) == LINEUP_SIZE + (SQUAD_SIZE - LINEUP_SIZE) * use_bb[w])

        highs.addConstr(sum(bench[p, w, 0] for p in players if player_type[p] == 1) == 1 - use_bb[w])
        for o in (1, 2, 3):
            highs.addConstr(sum(bench[p, w, o] for p in players) == 1 - use_bb[w])

        highs.addConstr(sum(captain[p, w] for p in players) == 1)
        highs.addConstr(sum(vicecap[p, w] for p in players) == 1)

        for p in players:
            highs.addConstr(lineup[p, w] <= squad[p, w] + use_fh[w])
            highs.addConstr(lineup[p, w] <= squad_fh[p, w] + 1 - use_fh[w])

            for o in order:
                highs.addConstr(bench[p, w, o] <= squad[p, w] + use_fh[w])
                highs.addConstr(bench[p, w, o] <= squad_fh[p, w] + 1 - use_fh[w])

            highs.addConstr(captain[p, w] <= lineup[p, w])
            highs.addConstr(vicecap[p, w] <= lineup[p, w])
            highs.addConstr(captain[p, w] + vicecap[p, w] <= 1)

            highs.addConstr(lineup[p, w] + sum(bench[p, w, o] for o in order) <= 1)

    # Formation rules
    for w in gws:
        for t in el_types:
            lineup_t = sum(lineup[p, w] for p in players if player_type[p] == t)
            highs.addConstr(lineup_t >= int(type_data.loc[t, "squad_min_play"]))
            highs.addConstr(lineup_t <= int(type_data.loc[t, "squad_max_play"]) + use_bb[w])

            squad_t = sum(squad[p, w] for p in players if player_type[p] == t)
            highs.addConstr(squad_t == int(type_data.loc[t, "squad_select"]))

            squad_fh_t = sum(squad_fh[p, w] for p in players if player_type[p] == t)
            highs.addConstr(squad_fh_t == int(type_data.loc[t, "squad_select"]) * use_fh[w])

    # Team limits
    if no_transfer_relax is not None:
        for w in gws:
            highs.addConstr(transfer_count[w] <= SQUAD_SIZE * (1 - no_transfer_relax[w]))
            highs.addConstr(transfer_count[w] >= 1 - SQUAD_SIZE * no_transfer_relax[w])

        for t, team_players in players_by_team.items():
            for w in gws:
                highs.addConstr(sum(squad[p, w] for p in team_players) <= MAX_PLAYERS_PER_TEAM + no_transfer_relax[w])
    else:
        for t, team_players in players_by_team.items():
            for w in all_gw:
                highs.addConstr(sum(squad[p, w] for p in team_players) <= MAX_PLAYERS_PER_TEAM)

    for t, team_players in players_by_team.items():
        for w in gws:
            highs.addConstr(sum(squad_fh[p, w] for p in team_players) <= MAX_PLAYERS_PER_TEAM * use_fh[w])

    # Transfer mechanics
    for w in gws:
        for p in players:
            highs.addConstr(squad[p, w] == squad[p, w - 1] + transfer_in[p, w] - transfer_out(p, w))

    buy_price = prepared.buy_price
    sell_price = prepared.sell_price

    def sold_amount(w: int):
        profit_sell = sum(sell_price[p] * transfer_out_first[p, w] for p in price_modified_players)
        regular_sell = sum(buy_price[p] * transfer_out_regular[p, w] for p in players)
        return profit_sell + regular_sell

    def bought_amount(w: int):
        return sum(buy_price[p] * transfer_in[p, w] for p in players)

    for w in gws:
        loss = (transfer_count[w] * itb_loss_per_transfer) if w > next_gw else 0
        highs.addConstr(in_the_bank[w] == in_the_bank[w - 1] + sold_amount(w) - bought_amount(w) - loss)

    fh_sell_price = {p: (sell_price[p] if p in price_modified_players else buy_price[p]) for p in players}
    for w in gws:
        lhs = sum(fh_sell_price[p] * squad[p, w - 1] for p in players) + in_the_bank[w - 1]
        rhs = sum(fh_sell_price[p] * squad_fh[p, w] for p in players)
        highs.addConstr(lhs >= rhs)

    for w in gws:
        for p in players:
            highs.addConstr(transfer_in[p, w] <= 1 - use_fh[w])
            highs.addConstr(transfer_out(p, w) <= 1 - use_fh[w])

    # Free transfers (carry / cap) + state encoding for FT value
    big_m = int(options.get("big_m_ft", DEFAULT_BIG_M_FT) or DEFAULT_BIG_M_FT)

    raw_ft = {}
    for w in gws:
        base = special_ft_weeks.get(w + 1, 1)
        raw_ft[w] = fts[w] - transfer_count[w] + base - use_wc[w] - use_fh[w]

        highs.addConstr(raw_ft[w] >= 6 - big_m * (1 - ft_above[w]))
        highs.addConstr(raw_ft[w] <= 5 + big_m * ft_above[w])

        highs.addConstr(raw_ft[w] <= 0 + big_m * (1 - ft_below[w]))
        highs.addConstr(raw_ft[w] >= 1 - big_m * ft_below[w])

    for w in gws:
        if w + 1 not in gws_set:
            continue
        highs.addConstr(fts[w + 1] <= 5 + big_m * (1 - ft_above[w]))
        highs.addConstr(fts[w + 1] >= 5 - big_m * (1 - ft_above[w]))

        highs.addConstr(fts[w + 1] <= 1 + big_m * (1 - ft_below[w]))
        highs.addConstr(fts[w + 1] >= 1 - big_m * (1 - ft_below[w]))

        highs.addConstr(fts[w + 1] - raw_ft[w] <= big_m * (ft_above[w] + ft_below[w]))
        highs.addConstr(raw_ft[w] - fts[w + 1] <= big_m * (ft_above[w] + ft_below[w]))

    for w in gws:
        highs.addConstr(fts[w] == sum(ft_state[w, s] * s for s in ft_states))
        highs.addConstr(sum(ft_state[w, s] for s in ft_states) == 1)

    # Penalized transfers (hits) accounting
    num_transfers = {w: sum(transfer_out(p, w) for p in players) for w in gws}
    transfer_diff = {w: num_transfers[w] - fts[w] - SQUAD_SIZE * use_wc[w] for w in gws}
    for w in gws:
        highs.addConstr(penalized_transfers[w] >= transfer_diff[w])

    # Chip rules
    use_tc_gw = {w: sum(use_tc[p, w] for p in players) for w in gws}
    for w in gws:
        highs.addConstr(use_wc[w] + use_fh[w] + use_bb[w] + use_tc_gw[w] <= 1)
        for p in players:
            highs.addConstr(use_tc[p, w] <= captain[p, w])
            highs.addConstr(squad_fh[p, w] <= use_fh[w])

    # Forced active chip (from entry state) in starting GW.
    active_chip = _detect_active_chip(team_json)
    if active_chip is not None:
        chip_key, _opt_key = active_chip
        if chip_key == "wc":
            highs.addConstr(use_wc[next_gw] == 1)
            chip_limits["wc"] = max(int(chip_limits.get("wc", 0) or 0), 1)
        elif chip_key == "fh":
            highs.addConstr(use_fh[next_gw] == 1)
            chip_limits["fh"] = max(int(chip_limits.get("fh", 0) or 0), 1)
        elif chip_key == "bb":
            highs.addConstr(use_bb[next_gw] == 1)
            chip_limits["bb"] = max(int(chip_limits.get("bb", 0) or 0), 1)
        elif chip_key == "tc":
            highs.addConstr(use_tc_gw[next_gw] == 1)
            chip_limits["tc"] = max(int(chip_limits.get("tc", 0) or 0), 1)

    # Direct chip forcing options (legacy-compatible)
    for gw in _as_int_list(options.get("use_wc")):
        if gw in gws_set:
            highs.addConstr(use_wc[gw] == 1)
            chip_limits["wc"] = max(int(chip_limits.get("wc", 0) or 0), 1)

    for gw in _as_int_list(options.get("use_bb")):
        if gw in gws_set:
            highs.addConstr(use_bb[gw] == 1)
            chip_limits["bb"] = max(int(chip_limits.get("bb", 0) or 0), 1)

    for gw in _as_int_list(options.get("use_fh")):
        if gw in gws_set:
            highs.addConstr(use_fh[gw] == 1)
            chip_limits["fh"] = max(int(chip_limits.get("fh", 0) or 0), 1)

    for gw in _as_int_list(options.get("use_tc")):
        if gw in gws_set:
            highs.addConstr(use_tc_gw[gw] == 1)
            chip_limits["tc"] = max(int(chip_limits.get("tc", 0) or 0), 1)

    # Allowed chip windows
    for chip_code, var_dict in (("wc", use_wc), ("fh", use_fh), ("bb", use_bb)):
        allowed = allowed_chip_gws.get(chip_code) or []
        if not allowed:
            continue
        allowed_set = {int(x) for x in allowed}
        for w in gws:
            if w not in allowed_set:
                highs.addConstr(var_dict[w] == 0)
        chip_limits[chip_code] = max(int(chip_limits.get(chip_code, 0) or 0), 1)

    allowed_tc = allowed_chip_gws.get("tc") or []
    if allowed_tc:
        allowed_set = {int(x) for x in allowed_tc}
        for w in gws:
            if w not in allowed_set:
                highs.addConstr(use_tc_gw[w] == 0)
        chip_limits["tc"] = max(int(chip_limits.get("tc", 0) or 0), 1)

    # Forced chip windows via forced_chip_gws
    for chip_code, forced in forced_chip_gws.items():
        forced_list = [int(x) for x in forced]
        forced_list = [w if w in gws_set else next_gw for w in forced_list]
        if not forced_list:
            continue
        if chip_code == "wc":
            highs.addConstr(sum(use_wc[w] for w in forced_list) == 1)
            chip_limits["wc"] = max(int(chip_limits.get("wc", 0) or 0), 1)
        elif chip_code == "fh":
            highs.addConstr(sum(use_fh[w] for w in forced_list) == 1)
            chip_limits["fh"] = max(int(chip_limits.get("fh", 0) or 0), 1)
        elif chip_code == "bb":
            highs.addConstr(sum(use_bb[w] for w in forced_list) == 1)
            chip_limits["bb"] = max(int(chip_limits.get("bb", 0) or 0), 1)
        elif chip_code == "tc":
            highs.addConstr(sum(use_tc_gw[w] for w in forced_list) == 1)
            chip_limits["tc"] = max(int(chip_limits.get("tc", 0) or 0), 1)

    highs.addConstr(sum(use_wc[w] for w in gws) <= int(chip_limits.get("wc", 0) or 0))
    highs.addConstr(sum(use_bb[w] for w in gws) <= int(chip_limits.get("bb", 0) or 0))
    highs.addConstr(sum(use_fh[w] for w in gws) <= int(chip_limits.get("fh", 0) or 0))
    highs.addConstr(sum(use_tc_gw[w] for w in gws) <= int(chip_limits.get("tc", 0) or 0))

    # Multi-sell constraints for price-modified players (prevents arbitrage)
    for p in price_modified_players:
        for w in gws:
            highs.addConstr(transfer_out_first[p, w] + transfer_out_regular[p, w] <= 1)

        for wbar in gws:
            lhs = horizon * sum(transfer_out_first[p, w] for w in gws if w <= wbar)
            rhs = sum(transfer_out_regular[p, w] for w in gws if w >= wbar)
            highs.addConstr(lhs >= rhs)

    # Transfer-count constraints (wildcard treated as “free transfers”)
    for w in gws:
        highs.addConstr(transfer_count[w] >= num_transfers[w] - SQUAD_SIZE * use_wc[w])
        highs.addConstr(transfer_count[w] <= num_transfers[w])
        highs.addConstr(transfer_count[w] <= SQUAD_SIZE * (1 - use_wc[w]))

    # Optional constraints from worker/UI settings
    banned = _as_int_list(options.get("banned"))
    if banned:
        for p in banned:
            if p not in players:
                continue
            highs.addConstr(sum(squad[p, w] for w in gws) == 0)
            highs.addConstr(sum(squad_fh[p, w] for w in gws) == 0)

    locked = _as_int_list(options.get("locked"))
    if locked:
        for p in locked:
            if p not in players:
                continue
            for w in gws:
                highs.addConstr(squad[p, w] + squad_fh[p, w] == 1)

    if options.get("no_future_transfer") is True:
        for w in gws:
            if w <= next_gw:
                continue
            highs.addConstr(sum(transfer_in[p, w] for p in players) <= SQUAD_SIZE * use_wc[w])

    no_transfer_last_gws = options.get("no_transfer_last_gws")
    if no_transfer_last_gws is not None:
        n_last = int(no_transfer_last_gws)
        if horizon > n_last:
            for w in gws:
                if w > last_gw - n_last:
                    highs.addConstr(sum(transfer_in[p, w] for p in players) <= SQUAD_SIZE * use_wc[w])

    if hit_limit is not None and hit_limit != 0:
        highs.addConstr(sum(penalized_transfers[w] for w in gws) <= int(hit_limit))

    if weekly_hit_limit is not None:
        lim = int(weekly_hit_limit)
        for w in gws:
            highs.addConstr(penalized_transfers[w] <= lim)

    no_transfer_gws = _as_int_list(options.get("no_transfer_gws"))
    if no_transfer_gws:
        for w in no_transfer_gws:
            if w in gws_set:
                highs.addConstr(sum(transfer_in[p, w] for p in players) == 0)

    # Booked transfers
    for bt in booked_transfers:
        if not isinstance(bt, dict):
            continue
        gw = bt.get("gw")
        try:
            gw_i = int(gw)
        except Exception:
            continue
        if gw_i not in gws_set:
            continue
        p_in = bt.get("transfer_in")
        p_out = bt.get("transfer_out")
        if p_in is not None:
            for pid in _as_int_list(p_in):
                if pid in players:
                    highs.addConstr(transfer_in[pid, gw_i] == 1)
        if p_out is not None:
            for pid in _as_int_list(p_out):
                if pid in players:
                    highs.addConstr(transfer_out(pid, gw_i) == 1)

    if options.get("only_booked_transfers") is True:
        forced_in: set[int] = set()
        forced_out: set[int] = set()
        for bt in booked_transfers:
            if not isinstance(bt, dict):
                continue
            if int(bt.get("gw", -1)) != next_gw:
                continue
            if bt.get("transfer_in") is not None:
                forced_in.update(_as_int_list(bt.get("transfer_in")))
            if bt.get("transfer_out") is not None:
                forced_out.update(_as_int_list(bt.get("transfer_out")))

        for p in players:
            highs.addConstr(transfer_in[p, next_gw] == (1 if p in forced_in else 0))
            highs.addConstr(transfer_out(p, next_gw) == (1 if p in forced_out else 0))

    # -------------------
    # Objective
    # -------------------

    points = {}
    for p in players:
        for w in gws:
            v = float(merged.loc[p, f"{w}_Pts"])
            points[p, w] = v if math.isfinite(v) else 0.0

    # Captain conditional xPts: use xpts_if60 for captain term in next GW
    # (xpts_if60 = expected points given 60+ minutes — better for captain picks)
    has_if60 = "xpts_if60" in merged.columns
    captain_points = {}
    for p in players:
        for w in gws:
            if has_if60 and w == next_gw:
                v60 = float(merged.loc[p, "xpts_if60"]) if pd.notna(merged.loc[p, "xpts_if60"]) else 0.0
                captain_points[p, w] = v60 if (math.isfinite(v60) and v60 > 0) else points[p, w]
            else:
                captain_points[p, w] = points[p, w]

    # Dynamic bench weights: scale by squad fragility (avg p_any)
    has_p_any = "p_any" in merged.columns
    if has_p_any:
        avg_p_any = float(merged["p_any"].mean())
        avg_p_any = avg_p_any if math.isfinite(avg_p_any) else 0.85
        fragility_scale = max(1.0, 2.0 - avg_p_any)
        bench_weights = {k: v * fragility_scale for k, v in bench_weights.items()}

    # FT state values are cumulative by state index (legacy behavior).
    ft_state_value: dict[int, float] = {}
    for s in ft_states:
        inc = float(ft_value_list.get(str(s), ft_value))
        ft_state_value[s] = ft_state_value.get(s - 1, 0.0) + inc

    gw_ft_value = {w: sum(ft_state_value[s] * ft_state[w, s] for s in ft_states) for w in gws}
    gw_ft_gain = {w: gw_ft_value[w] - (gw_ft_value.get(w - 1, 0) if (w - 1) in gws_set else 0) for w in gws}

    gw_xp = {}
    for w in gws:
        xp = 0
        for p in players:
            xp = xp + (
                points[p, w] * (
                    lineup[p, w]
                    + vcap_weight * vicecap[p, w]
                    + sum(bench_weights[o] * bench[p, w, o] for o in order)
                )
                + captain_points[p, w] * (captain[p, w] + use_tc[p, w])
            )
        gw_xp[w] = xp

    league_obj = {w: 0.0 for w in gws}
    if league_context:
        # Mini-league context is a soft tie-breaker around the core xPts model.
        # It only affects the next visible GW because rival squads/captains become
        # stale quickly; future GWs should still be driven by projections.
        for p in players:
            ownership = _league_ownership(league_context, p)
            squad_signal = _league_signal(league_mode, ownership["squad"])
            starting_signal = _league_signal(league_mode, max(ownership["starting"], ownership["squad"] * 0.65))
            captain_signal = _league_signal(league_mode, ownership["captain"])
            league_obj[next_gw] = league_obj[next_gw] + league_weight * (
                0.16 * starting_signal * lineup[p, next_gw]
                + 0.72 * captain_signal * captain[p, next_gw]
                + 0.28 * squad_signal * transfer_in[p, next_gw]
                - 0.18 * squad_signal * transfer_out(p, next_gw)
            )

    ft_penalty = {w: ft_use_penalty * transfer_count[w] for w in gws} if ft_use_penalty else {w: 0 for w in gws}

    gw_total = {
        w: gw_xp[w]
        + league_obj[w]
        - hit_cost * penalized_transfers[w]
        + gw_ft_gain[w]
        - ft_penalty[w]
        + itb_value * in_the_bank[w]
        for w in gws
    }

    if objective == "regular":
        objective_expr = sum(gw_total[w] for w in gws)
    else:
        objective_expr = sum(gw_total[w] * math.pow(decay_base, w - next_gw) for w in gws)

    # Solve
    highs.maximize(objective_expr)

    status = highs.getModelStatus()
    if status in {highspy.HighsModelStatus.kInfeasible, highspy.HighsModelStatus.kUnbounded, highspy.HighsModelStatus.kUnboundedOrInfeasible}:
        raise RuntimeError(f"MILP infeasible (status={status})")

    # -------------------
    # Extract solution
    # -------------------

    def bval(var) -> int:
        return 1 if float(highs.val(var)) > BINARY_THRESHOLD else 0

    picks: list[dict[str, Any]] = []
    for w in gws:
        tc_gw_val = float(highs.val(use_tc_gw[w]))
        for p in players:
            if float(highs.val(squad[p, w])) + float(highs.val(squad_fh[p, w])) + float(highs.val(transfer_out(p, w))) <= BINARY_THRESHOLD:
                continue

            is_fh = float(highs.val(use_fh[w])) > BINARY_THRESHOLD
            is_squad = 1 if ((not is_fh and bval(squad[p, w]) == 1) or (is_fh and bval(squad_fh[p, w]) == 1)) else 0

            bench_slot = -1
            for o in order:
                if bval(bench[p, w, o]) == 1:
                    bench_slot = int(o)
                    break

            is_transfer_in = bval(transfer_in[p, w])
            is_transfer_out = 1 if float(highs.val(transfer_out(p, w))) > BINARY_THRESHOLD else 0
            sold_price = 0.0
            if is_transfer_out:
                sold_price = (
                    sell_price.get(p, buy_price[p])
                    if (p in price_modified_players and float(highs.val(transfer_out_first[p, w])) > BINARY_THRESHOLD)
                    else buy_price[p]
                )

            buy_p = float(buy_price[p]) if is_transfer_in else 0.0

            is_lineup = bval(lineup[p, w])
            is_captain = bval(captain[p, w])
            is_tc = bval(use_tc[p, w])
            multiplier = (1 if is_lineup else 0) + (1 if is_captain else 0) + (1 if is_tc else 0)

            pt = float(points[p, w])
            cpt = float(captain_points[p, w])
            xp_cont = pt * (1 if is_lineup else 0) + cpt * ((1 if is_captain else 0) + (1 if is_tc else 0))

            chip_text = _chip_text(
                wc=float(highs.val(use_wc[w])),
                fh=float(highs.val(use_fh[w])),
                bb=float(highs.val(use_bb[w])),
                tc_gw=float(tc_gw_val),
            )
            if chip_text == "TC" and is_tc != 1:
                chip_text = ""
            if chip_text != "TC" and is_tc == 1:
                chip_text = "TC"

            picks.append(
                {
                    "id": int(p),
                    "week": int(w),
                    "name": str(merged.loc[p, "web_name"]),
                    "pos": str(type_data.loc[player_type[p], "singular_name_short"]),
                    "type": int(player_type[p]),
                    "team": str(player_team[p]),
                    "buy_price": float(buy_p),
                    "sell_price": float(sold_price),
                    "xP": round(float(pt), 2),
                    "xMin": int(round(float(merged.loc[p, f"{w}_xMins"]))),
                    "squad": int(is_squad),
                    "lineup": int(is_lineup),
                    "bench": int(bench_slot),
                    "captain": int(is_captain),
                    "vicecaptain": int(bval(vicecap[p, w])),
                    "transfer_in": int(is_transfer_in),
                    "transfer_out": int(is_transfer_out),
                    "multiplier": int(multiplier),
                    "xp_cont": float(xp_cont),
                    "chip": str(chip_text),
                    "ft": int(round(float(highs.val(fts[w])))),
                    "transfer_count": float(highs.val(num_transfers[w])),
                }
            )

    picks_df = pd.DataFrame(picks)
    if len(picks_df) == 0:
        raise RuntimeError("Solver returned empty picks")

    picks_df.sort_values(by=["week", "squad", "lineup", "bench", "type"], ascending=[True, False, False, True, True], inplace=True)

    # Summary + per-GW stats
    statistics: dict[int, dict[str, Any]] = {int(next_gw - 1): {"itb": float(highs.val(in_the_bank[next_gw - 1])), "ft": float(highs.val(fts[next_gw - 1]))}}
    summary_lines: list[str] = []

    for w in gws:
        chip_decision = _chip_text(
            wc=float(highs.val(use_wc[w])),
            fh=float(highs.val(use_fh[w])),
            bb=float(highs.val(use_bb[w])),
            tc_gw=float(highs.val(use_tc_gw[w])),
        )
        summary_lines.append(f"** GW {w}:")
        if chip_decision:
            summary_lines.append(f"CHIP {chip_decision}")

        summary_lines.append(
            "ITB="
            + f"{round(float(highs.val(in_the_bank[w - 1])), 1)}->{round(float(highs.val(in_the_bank[w])), 1)}, "
            + f"FT={int(round(float(highs.val(fts[w]))))}, "
            + f"PT={int(round(float(highs.val(penalized_transfers[w]))))}, "
            + f"NT={int(round(float(highs.val(num_transfers[w]))))}"
        )

        for p in players:
            if bval(transfer_in[p, w]) == 1:
                summary_lines.append(f"Buy {p} - {merged.loc[p, 'web_name']}")
        for p in players:
            if float(highs.val(transfer_out(p, w))) > BINARY_THRESHOLD:
                summary_lines.append(f"Sell {p} - {merged.loc[p, 'web_name']}")

        lineup_players = picks_df[(picks_df["week"] == w) & (picks_df["lineup"] == 1)]
        bench_players = picks_df[(picks_df["week"] == w) & (picks_df["bench"] >= 0)]

        summary_lines.append("")
        summary_lines.append("Lineup:")

        def _disp(row: pd.Series) -> str:
            suffix = ""
            if int(row.get("captain", 0)) == 1:
                suffix += ", C"
            if int(row.get("vicecaptain", 0)) == 1:
                suffix += ", V"
            return f"{row['name']} ({row['xP']}{suffix})"

        for t in (1, 2, 3, 4):
            rows = lineup_players[lineup_players["type"] == t]
            entries = [_disp(r) for _, r in rows.iterrows()]
            summary_lines.append("\t" + ", ".join(entries))

        bench_entries = [_disp(r) for _, r in bench_players.iterrows()]
        summary_lines.append("Bench:")
        summary_lines.append("\t" + ", ".join(bench_entries))
        summary_lines.append(f"Lineup xPts: {round(float(lineup_players['xp_cont'].sum()), 2)}")

        # Objective contribution (non-decayed)
        # Compute using solved variable values for transparency.
        gw_xp_val = float(highs.val(gw_xp[w]))
        league_obj_val = float(highs.val(league_obj[w])) if league_context and w == next_gw else 0.0
        gw_total_val = (
            gw_xp_val
            + league_obj_val
            - hit_cost * float(highs.val(penalized_transfers[w]))
            + float(highs.val(gw_ft_gain[w]))
            - float(highs.val(ft_penalty[w]))
            + itb_value * float(highs.val(in_the_bank[w]))
        )

        statistics[int(w)] = {
            "itb": float(highs.val(in_the_bank[w])),
            "ft": float(highs.val(fts[w])),
            "pt": float(highs.val(penalized_transfers[w])),
            "nt": float(highs.val(num_transfers[w])),
            "xP": float(lineup_players["xp_cont"].sum()),
            "obj": round(float(gw_total_val), 2),
            "chip": chip_decision if chip_decision else None,
            **({"league_obj": round(float(league_obj_val), 2)} if league_context and w == next_gw else {}),
        }

        summary_lines.append("")

    score = float(highs.getObjectiveValue())
    solve_time_ms = int((time.time() - solve_started) * 1000)

    # Total_xp mirrors legacy: sum of (lineup + captain) points, no vice/bench.
    total_xp = 0.0
    for w in gws:
        for p in players:
            total_xp += float(points[p, w]) * (float(highs.val(lineup[p, w])) + float(highs.val(captain[p, w])))

    result = {
        "picks": picks_df,
        "statistics": statistics,
        "score": score,
        "summary": "\n".join(summary_lines).strip(),
        "total_xp": float(total_xp),
        "meta": {
            **(prepared.meta or {}),
            "solve_time_ms": solve_time_ms,
            "highs_status": str(status),
            **({
                "league_context": {
                    "enabled": True,
                    "league_id": league_context.get("league_id"),
                    "league_name": league_context.get("league_name"),
                    "mode": league_context.get("mode"),
                    "label": league_context.get("label"),
                    "weight": league_context.get("weight"),
                    "rivals_analyzed": league_context.get("rivals_analyzed"),
                    "sample_kind": league_context.get("sample_kind"),
                    "points_band": league_context.get("points_band"),
                },
            } if league_context else {}),
        },
    }

    # Plan-B: warm re-solve with the headline transfer-in banned, so the product
    # can show the next-best plan and the EV gap behind the recommendation.
    # Runs after all reads of the main solution; must never fail the main solve.
    if bool(options.get("plan_b")):
        try:
            first_ins = [
                p for p in players
                if float(highs.val(transfer_in[p, next_gw])) > BINARY_THRESHOLD
            ]
        except Exception:
            first_ins = []
        if first_ins:
            try:
                ban = max(first_ins, key=lambda p: float(merged.loc[p, "total_ev"]))
                for w in gws:
                    highs.addConstr(squad[ban, w] == 0)
                    highs.addConstr(squad_fh[ban, w] == 0)
                    highs.addConstr(transfer_in[ban, w] == 0)
                highs.setOptionValue("time_limit", float(options.get("plan_b_secs", 10) or 10))
                highs.setOptionValue("mip_rel_gap", float(options.get("plan_b_gap", 0.02) or 0.02))
                highs.run()
                alt_status = highs.getModelStatus()
                bad = {
                    highspy.HighsModelStatus.kInfeasible,
                    highspy.HighsModelStatus.kUnbounded,
                    highspy.HighsModelStatus.kUnboundedOrInfeasible,
                }
                if alt_status not in bad:
                    alt_score = float(highs.getObjectiveValue())
                    alt_in = [
                        int(p) for p in players
                        if float(highs.val(transfer_in[p, next_gw])) > BINARY_THRESHOLD
                    ]
                    alt_out = [
                        int(p) for p in players
                        if float(highs.val(transfer_out(p, next_gw))) > BINARY_THRESHOLD
                    ]

                    def _names(ids: list[int]) -> list[str]:
                        return [str(merged.loc[p, "web_name"]) for p in ids if p in merged.index]

                    result["meta"]["plan_b"] = {
                        "banned_id": int(ban),
                        "banned_name": str(merged.loc[ban, "web_name"]),
                        "transfers_in": _names(alt_in),
                        "transfers_out": _names(alt_out),
                        "score_delta": round(score - alt_score, 3),
                    }
            except Exception as exc:
                result["meta"]["plan_b"] = {"error": str(exc)[:200]}

    return [result]
