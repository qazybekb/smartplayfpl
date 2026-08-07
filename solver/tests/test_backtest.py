from __future__ import annotations

import json

import pandas as pd
import pytest

from solver.backtest import BacktestCase, SettingsProfile, case_from_dict, evaluate_solution, run_case, summarize_results


def test_evaluate_solution_uses_actual_multipliers_and_hit_cost() -> None:
    case = BacktestCase(
        name="fake",
        current_gw=1,
        horizon=1,
        team_json={"picks": [], "transfers": {"bank": 0, "limit": 1, "made": 0}, "chips": []},
        data_df=pd.DataFrame(),
        fpl_elements_df=pd.DataFrame(),
        fpl_teams_df=pd.DataFrame(),
        actual_points={1: {1: 10.0, 2: 5.0}},
    )
    solution = {
        "picks": pd.DataFrame(
            [
                {"week": 1, "id": 1, "lineup": 1, "captain": 1, "vicecaptain": 0, "multiplier": 2},
                {"week": 1, "id": 2, "lineup": 1, "captain": 0, "vicecaptain": 1, "multiplier": 1},
            ]
        ),
        "statistics": {1: {"xP": 17.0, "pt": 1, "nt": 2}},
    }

    [gw] = evaluate_solution(solution, case, hit_cost=4.0)

    assert gw.projected_points == 17.0
    assert gw.actual_points == 25.0
    assert gw.net_points == 21.0
    assert gw.hits == 1
    assert gw.transfer_count == 2
    assert gw.missing_actuals == 0


def test_run_case_smoke_solves_synthetic_case() -> None:
    pytest.importorskip("highspy")
    case = _synthetic_case()

    result = run_case(case, SettingsProfile("baseline", {"secs": 2, "gap": 0, "weekly_hit_limit": 0}))

    assert result.status == "ok", result.error
    assert result.projected_points > 0
    assert result.actual_points > 0
    assert result.missing_actuals == 0
    assert result.hits == 0
    json.dumps(result.to_dict())


def test_summarize_results_ranks_successful_profiles() -> None:
    pytest.importorskip("highspy")
    case = _synthetic_case()
    results = [
        run_case(case, SettingsProfile("baseline", {"secs": 2, "gap": 0, "weekly_hit_limit": 0})),
        run_case(case, SettingsProfile("same_again", {"secs": 2, "gap": 0, "weekly_hit_limit": 0})),
    ]

    summary = summarize_results(results)

    assert [row["profile"] for row in summary] == ["baseline", "same_again"]
    assert all(row["ok"] == 1 for row in summary)


def _synthetic_case():
    next_gw = 1
    teams = [{"id": i, "name": f"Team{i}"} for i in range(1, 21)]

    players = []
    pid = 1
    for _ in range(2):
        players.append({"id": pid, "web_name": f"GK{pid}", "team": pid, "element_type": 1, "now_cost": 45})
        pid += 1
    for _ in range(5):
        players.append({"id": pid, "web_name": f"DEF{pid}", "team": pid, "element_type": 2, "now_cost": 50})
        pid += 1
    for _ in range(5):
        players.append({"id": pid, "web_name": f"MID{pid}", "team": pid, "element_type": 3, "now_cost": 75})
        pid += 1
    for _ in range(3):
        players.append({"id": pid, "web_name": f"FWD{pid}", "team": pid, "element_type": 4, "now_cost": 80})
        pid += 1

    projections = []
    actuals = []
    for player in players:
        element_type = int(player["element_type"])
        pos = {1: "G", 2: "D", 3: "M", 4: "F"}[element_type]
        xpts = 3.0 if element_type == 1 else 2.0
        projections.append(
            {
                "ID": player["id"],
                "Name": player["web_name"],
                "Pos": pos,
                "Value": round(player["now_cost"] / 10, 1),
                "Team": f"T{player['team']}",
                f"{next_gw}_Pts": xpts,
                f"{next_gw}_xMins": 90,
            }
        )
        actuals.append({"gw": next_gw, "id": player["id"], "points": xpts, "minutes": 90})

    team_json = {
        "picks": [
            {
                "element": player["id"],
                "selling_price": player["now_cost"],
                "purchase_price": player["now_cost"],
                "multiplier": 1,
                "is_captain": False,
                "is_vice_captain": False,
            }
            for player in players
        ],
        "transfers": {"bank": 0, "limit": 1, "made": 0},
        "chips": [],
    }

    return case_from_dict(
        {
            "name": "synthetic-gw1",
            "current_gw": next_gw,
            "horizon": 1,
            "team_json": team_json,
            "data": projections,
            "elements": players,
            "teams": teams,
            "actuals": actuals,
            "options": {"keep_top_ev_percent": 100, "xmin_lb": 0, "chip_limits": {"wc": 0, "fh": 0, "bb": 0, "tc": 0}},
        }
    )
