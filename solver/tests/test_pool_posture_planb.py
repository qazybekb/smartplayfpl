"""Tests for the Aug-2026 solver improvements: per-position pool cap,
global-field posture tilt, and the Plan-B warm re-solve."""

from __future__ import annotations

import pandas as pd
import pytest

from solver.prep import prepare_data
from solver.solve import solve_multi_period_fpl

NEXT_GW = 10
HORIZON = 2
GWS = list(range(NEXT_GW, NEXT_GW + HORIZON))

# Squad: 2 GKP + 5 DEF + 5 MID + 3 FWD, each on his own club (ids 1..15).
SQUAD_SPECS = (
    [(1, 1, 45)] * 1 + [(2, 1, 40)] * 1          # GKP
    + [(pid, 2, 45) for pid in (3, 4, 5, 6, 7)]   # DEF
    + [(pid, 3, 60) for pid in (8, 9, 10, 11, 12)]  # MID
    + [(pid, 4, 65) for pid in (13, 14, 15)]      # FWD
)
STAR_ID = 100        # unowned cheap MID with huge EV — the obvious buy
DEAD_MID_ID = 12     # owned MID projected at zero — the obvious sell


def _fixture(*, star_pts: float = 12.0, selected: dict[int, float] | None = None):
    specs = []
    for i, (pid, et, cost) in enumerate(SQUAD_SPECS):
        specs.append({"id": pid, "et": et, "cost": cost, "team": pid, "pts": 3.0})
    # Extra pool players (unowned), clubs 16..20 to stay inside 3-per-club.
    extras = [
        {"id": 20, "et": 1, "cost": 40, "team": 16, "pts": 3.0},
        {"id": 21, "et": 2, "cost": 40, "team": 16, "pts": 2.5},
        {"id": 22, "et": 2, "cost": 39, "team": 17, "pts": 2.0},
        {"id": 23, "et": 3, "cost": 55, "team": 17, "pts": 3.5},
        {"id": 24, "et": 3, "cost": 50, "team": 18, "pts": 3.0},
        {"id": STAR_ID, "et": 3, "cost": 58, "team": 18, "pts": star_pts},
        {"id": 26, "et": 4, "cost": 60, "team": 19, "pts": 3.0},
        {"id": 27, "et": 4, "cost": 45, "team": 19, "pts": 2.0},
        {"id": 28, "et": 4, "cost": 44, "team": 20, "pts": 1.5},
    ]
    specs.extend(extras)

    sel = selected or {}
    elements = pd.DataFrame([
        {
            "id": s["id"], "web_name": f"P{s['id']}", "team": s["team"],
            "element_type": s["et"], "now_cost": s["cost"],
            "selected_by_percent": sel.get(s["id"], 10.0),
        }
        for s in specs
    ])
    teams = pd.DataFrame([{"id": t, "name": f"T{t}"} for t in range(1, 21)])
    pos_name = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    rows = []
    for s in specs:
        pts = 0.0 if s["id"] == DEAD_MID_ID else s["pts"]
        row = {"ID": s["id"], "Pos": pos_name[s["et"]], "Name": f"P{s['id']}"}
        for gw in GWS:
            row[f"{gw}_Pts"] = pts
            row[f"{gw}_xMins"] = 90.0
        rows.append(row)
    data_df = pd.DataFrame(rows)

    team_json = {
        "picks": [
            {"element": pid, "selling_price": cost, "position": i + 1}
            for i, (pid, _et, cost) in enumerate(SQUAD_SPECS)
        ],
        "transfers": {"bank": 0, "limit": 1, "made": 0},
        "chips": [],
    }
    options = {
        "fpl_elements_df": elements,
        "fpl_teams_df": teams,
        "data_df": data_df,
        "override_next_gw": NEXT_GW,
        "horizon": HORIZON,
        "fixtures": [],
        "secs": 10,
        "gap": 0.05,
        "chip_limits": {"wc": 0, "fh": 0, "bb": 0, "tc": 0},
    }
    return team_json, options


def test_pool_cap_keeps_owned_and_shrinks_pool() -> None:
    team_json, options = _fixture()
    options["pool_top_n_per_pos"] = {"GKP": 1, "DEF": 1, "MID": 1, "FWD": 1}
    options["pool_cheap_per_pos"] = 1
    prepared = prepare_data(team_json, options)
    pool = set(int(x) for x in prepared.merged_data["ID"].tolist())
    # The whole current squad is protected regardless of caps.
    assert {pid for pid, _et, _c in SQUAD_SPECS} <= pool
    assert prepared.meta["pool_top_n_capped"] is True
    assert prepared.meta["pool_players_after_filter"] < prepared.meta["pool_players_before_filter"]


def test_pool_cap_works_with_production_position_letters() -> None:
    # Production data uses single-letter positions (db_data_loader.POS_MAP);
    # regression for the silent no-op found in review: caps keyed GKP/DEF/…
    # must still bite when the frame says G/D/M/F.
    team_json, options = _fixture()
    options["data_df"] = options["data_df"].copy()
    options["data_df"]["Pos"] = options["data_df"]["Pos"].map(
        {"GKP": "G", "DEF": "D", "MID": "M", "FWD": "F"}
    )
    options["pool_top_n_per_pos"] = {"GKP": 1, "DEF": 1, "MID": 1, "FWD": 1}
    options["pool_cheap_per_pos"] = 1
    prepared = prepare_data(team_json, options)
    assert prepared.meta["pool_top_n_capped"] is True
    assert prepared.meta["pool_players_after_filter"] < prepared.meta["pool_players_before_filter"]


def test_pool_cap_disabled_when_null() -> None:
    team_json, options = _fixture()
    options["pool_top_n_per_pos"] = None
    prepared = prepare_data(team_json, options)
    assert prepared.meta["pool_top_n_capped"] is False


def test_posture_chase_tilts_ev_toward_differentials() -> None:
    selected = {STAR_ID: 5.0, 8: 80.0}  # star is a differential; P8 is template
    team_json, neutral_opts = _fixture(selected=selected)
    _, chase_opts = _fixture(selected=selected)
    chase_opts["posture"] = "chase"

    neutral = prepare_data(team_json, neutral_opts).merged_data
    chase = prepare_data(team_json, chase_opts).merged_data

    col = f"{NEXT_GW}_Pts"
    n_star = float(neutral.loc[neutral["ID"].eq(STAR_ID), col].iloc[0])
    c_star = float(chase.loc[chase["ID"].eq(STAR_ID), col].iloc[0])
    n_temp = float(neutral.loc[neutral["ID"].eq(8), col].iloc[0])
    c_temp = float(chase.loc[chase["ID"].eq(8), col].iloc[0])

    assert c_star > n_star            # low-EO boosted
    assert c_temp < n_temp            # high-EO discounted
    assert c_star == pytest.approx(n_star * (1 + 0.12 * 0.9), rel=1e-6)
    assert c_temp == pytest.approx(n_temp * (1 - 0.12 * 0.6), rel=1e-6)


def test_posture_protect_is_mirror_and_neutral_noop() -> None:
    selected = {STAR_ID: 5.0, 8: 80.0}
    team_json, protect_opts = _fixture(selected=selected)
    protect_opts["posture"] = "protect"
    protect = prepare_data(team_json, protect_opts).merged_data
    col = f"{NEXT_GW}_Pts"
    star = float(protect.loc[protect["ID"].eq(STAR_ID), col].iloc[0])
    assert star == pytest.approx(12.0 * (1 - 0.12 * 0.9), rel=1e-6)

    team_json, neutral_opts = _fixture(selected=selected)
    neutral = prepare_data(team_json, neutral_opts)
    assert neutral.meta["posture_applied"] is False


def test_solver_buys_star_and_plan_b_bans_him() -> None:
    team_json, options = _fixture(star_pts=12.0)
    options["plan_b"] = True
    prepared = prepare_data(team_json, options)
    [solution] = solve_multi_period_fpl(prepared, team_json, options)

    picks = solution["picks"]
    week1 = picks[picks["week"] == NEXT_GW]
    bought = set(week1[week1["transfer_in"] == 1]["id"].astype(int))
    assert STAR_ID in bought

    plan_b = solution["meta"].get("plan_b")
    assert plan_b is not None and "error" not in plan_b
    assert plan_b["banned_id"] == STAR_ID
    assert plan_b["banned_name"] == f"P{STAR_ID}"
    assert f"P{STAR_ID}" not in plan_b["transfers_in"]
    assert plan_b["score_delta"] >= 0  # main plan is at least as good
