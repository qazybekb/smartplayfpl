from __future__ import annotations

import itertools
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .prep import prepare_data
from .solve import solve_multi_period_fpl


DEFAULT_SOLVER_OPTIONS: dict[str, Any] = {
    "objective": "decay",
    "decay_base": 0.9,
    "secs": 20,
    "gap": 0.01,
    "itb_value": 0.02,
    "ft_value_list": {"2": 2.0, "3": 1.6, "4": 1.3, "5": 1.1},
    "weekly_hit_limit": None,
    "hit_limit": None,
    "chip_limits": {"wc": 0, "fh": 0, "bb": 0, "tc": 0},
}

@dataclass(frozen=True)
class SettingsProfile:
    """Named solver-option override used by the calibration runner."""

    name: str
    options: Mapping[str, Any] = field(default_factory=dict)


DEFAULT_PROFILES = (
    SettingsProfile("prod_current", {}),
    SettingsProfile("shorter_decay", {"decay_base": 0.84}),
    SettingsProfile("longer_decay", {"decay_base": 0.94}),
    SettingsProfile("lower_ft_value", {"ft_value_list": {"2": 1.5, "3": 1.2, "4": 1.0, "5": 0.8}}),
    SettingsProfile("higher_ft_value", {"ft_value_list": {"2": 2.5, "3": 2.0, "4": 1.6, "5": 1.3}}),
    SettingsProfile("no_itb_value", {"itb_value": 0.0}),
    SettingsProfile("conservative_hits", {"hit_cost": 5.0}),
    SettingsProfile("aggressive_hits", {"hit_cost": 3.0}),
    SettingsProfile("stronger_bench", {"bench_weights": {"0": 0.05, "1": 0.32, "2": 0.1, "3": 0.02}}),
)


@dataclass
class BacktestCase:
    """All inputs needed to replay one historical solver decision."""

    name: str
    current_gw: int
    horizon: int
    team_json: dict[str, Any]
    data_df: pd.DataFrame
    fpl_elements_df: pd.DataFrame
    fpl_teams_df: pd.DataFrame
    actual_points: dict[int, dict[int, float]]
    actual_minutes: dict[int, dict[int, float]] = field(default_factory=dict)
    fixtures: list[dict[str, Any]] = field(default_factory=list)
    base_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GwEvaluation:
    gw: int
    projected_points: float
    actual_points: float
    hits: int
    net_points: float
    transfer_count: int
    missing_actuals: int
    chip: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gw": self.gw,
            "projected_points": round(self.projected_points, 4),
            "actual_points": round(self.actual_points, 4),
            "hits": self.hits,
            "net_points": round(self.net_points, 4),
            "transfer_count": self.transfer_count,
            "missing_actuals": self.missing_actuals,
            "chip": self.chip,
        }


@dataclass(frozen=True)
class BacktestResult:
    case: str
    profile: str
    status: str
    projected_points: float = 0.0
    actual_points: float = 0.0
    net_points: float = 0.0
    hits: int = 0
    transfer_count: int = 0
    missing_actuals: int = 0
    solve_time_ms: int = 0
    score: float | None = None
    error: str | None = None
    gw_results: tuple[GwEvaluation, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "profile": self.profile,
            "status": self.status,
            "projected_points": round(self.projected_points, 4),
            "actual_points": round(self.actual_points, 4),
            "net_points": round(self.net_points, 4),
            "hits": self.hits,
            "transfer_count": self.transfer_count,
            "missing_actuals": self.missing_actuals,
            "solve_time_ms": self.solve_time_ms,
            "score": self.score,
            "error": self.error,
            "gw_results": [gw.to_dict() for gw in self.gw_results],
            "options": _serializable_options(self.options),
        }


def load_cases(path: str | Path) -> list[BacktestCase]:
    """Load backtest cases from a JSON file.

    Supported shape:

      {
        "cases": [
          {
            "name": "team-123-gw24",
            "current_gw": 24,
            "horizon": 3,
            "team_json": {...},
            "data": [{... solver projection rows ...}],
            "elements": [{... bootstrap element rows ...}],
            "teams": [{... bootstrap team rows ...}],
            "actuals": [{"gw": 24, "id": 1, "points": 6, "minutes": 90}]
          }
        ]
      }
    """

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("cases", raw) if isinstance(raw, dict) else raw
    if isinstance(items, Mapping):
        items = [items]
    if not isinstance(items, list):
        raise ValueError("Backtest JSON must contain a case object or a list of cases")
    return [case_from_dict(item) for item in items]


def case_from_dict(raw: Mapping[str, Any]) -> BacktestCase:
    name = str(raw.get("name") or raw.get("id") or f"gw{raw.get('current_gw', raw.get('gw', '?'))}")
    current_gw = int(raw.get("current_gw", raw.get("gw")))
    horizon = int(raw.get("horizon", 3))

    data_rows = _required_records(raw, ("data", "data_df", "projections", "players"))
    element_rows = _required_records(raw, ("elements", "fpl_elements", "fpl_elements_df"))
    team_rows = _required_records(raw, ("teams", "fpl_teams", "fpl_teams_df"))

    actual_points, actual_minutes = _parse_actuals(raw)
    team_json = raw.get("team_json")
    if not isinstance(team_json, dict):
        raise ValueError(f"Case '{name}' must include team_json")

    return BacktestCase(
        name=name,
        current_gw=current_gw,
        horizon=horizon,
        team_json=dict(team_json),
        data_df=pd.DataFrame(data_rows),
        fpl_elements_df=pd.DataFrame(element_rows),
        fpl_teams_df=pd.DataFrame(team_rows),
        actual_points=actual_points,
        actual_minutes=actual_minutes,
        fixtures=list(raw.get("fixtures") or []),
        base_options=dict(raw.get("options") or raw.get("base_options") or {}),
    )


def load_profiles(path: str | Path | None = None) -> list[SettingsProfile]:
    """Load calibration profiles from JSON, or return a small default grid."""

    if path is None:
        return list(DEFAULT_PROFILES)

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [_profile_from_dict(item) for item in raw]
    if not isinstance(raw, dict):
        raise ValueError("Profile JSON must be an object or list")

    profiles: list[SettingsProfile] = []
    if "profiles" in raw:
        profiles.extend(_profile_from_dict(item) for item in raw["profiles"])
    if "grid" in raw:
        profiles.extend(expand_grid(raw["grid"], base_options=raw.get("base_options") or {}))
    if not profiles:
        raise ValueError("Profile JSON must contain 'profiles' or 'grid'")
    return profiles


def expand_grid(
    grid: Mapping[str, Sequence[Any]],
    *,
    base_options: Mapping[str, Any] | None = None,
    name_prefix: str = "grid",
) -> list[SettingsProfile]:
    """Build SettingsProfile values from a JSON-friendly cartesian grid."""

    base_options = dict(base_options or {})
    keys = list(grid.keys())
    values = [list(grid[k]) for k in keys]
    profiles: list[SettingsProfile] = []
    for combo in itertools.product(*values):
        opts = dict(base_options)
        opts.update(dict(zip(keys, combo)))
        name_bits = [f"{k}={_short_value(v)}" for k, v in zip(keys, combo)]
        profiles.append(SettingsProfile(f"{name_prefix}:{','.join(name_bits)}", opts))
    return profiles


def run_backtest(
    cases: Iterable[BacktestCase],
    profiles: Iterable[SettingsProfile],
    *,
    base_options: Mapping[str, Any] | None = None,
) -> list[BacktestResult]:
    results: list[BacktestResult] = []
    cases_list = list(cases)
    profiles_list = list(profiles)
    for case in cases_list:
        for profile in profiles_list:
            results.append(run_case(case, profile, base_options=base_options))
    return results


def run_case(
    case: BacktestCase,
    profile: SettingsProfile,
    *,
    base_options: Mapping[str, Any] | None = None,
) -> BacktestResult:
    options = build_solver_options(case, profile, base_options=base_options)
    start = time.time()
    try:
        prepared = prepare_data(case.team_json, options)
        solution = solve_multi_period_fpl(prepared, case.team_json, options)[0]
        solve_time_ms = int((time.time() - start) * 1000)
        gw_results = evaluate_solution(solution, case, hit_cost=float(options.get("hit_cost", 4.0) or 4.0))

        projected = sum(gw.projected_points for gw in gw_results)
        actual = sum(gw.actual_points for gw in gw_results)
        net = sum(gw.net_points for gw in gw_results)
        hits = sum(gw.hits for gw in gw_results)
        transfer_count = sum(gw.transfer_count for gw in gw_results)
        missing_actuals = sum(gw.missing_actuals for gw in gw_results)

        score = solution.get("score")
        return BacktestResult(
            case=case.name,
            profile=profile.name,
            status="ok",
            projected_points=float(projected),
            actual_points=float(actual),
            net_points=float(net),
            hits=int(hits),
            transfer_count=int(transfer_count),
            missing_actuals=int(missing_actuals),
            solve_time_ms=solve_time_ms,
            score=float(score) if score is not None else None,
            gw_results=tuple(gw_results),
            options=options,
        )
    except Exception as exc:
        return BacktestResult(
            case=case.name,
            profile=profile.name,
            status="error",
            solve_time_ms=int((time.time() - start) * 1000),
            error=f"{type(exc).__name__}: {exc}",
            options=options,
        )


def build_solver_options(
    case: BacktestCase,
    profile: SettingsProfile,
    *,
    base_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    options = dict(DEFAULT_SOLVER_OPTIONS)
    options.update(base_options or {})
    options.update(case.base_options)
    options.update(profile.options)

    options["horizon"] = int(options.get("horizon", case.horizon) or case.horizon)
    options["current_gw"] = int(options.get("current_gw", case.current_gw) or case.current_gw)
    options["override_next_gw"] = int(options.get("override_next_gw", case.current_gw) or case.current_gw)
    options["data_df"] = case.data_df.copy()
    options["fpl_elements_df"] = case.fpl_elements_df.copy()
    options["fpl_teams_df"] = case.fpl_teams_df.copy()
    options["fixtures"] = list(case.fixtures)
    return options


def evaluate_solution(solution: Mapping[str, Any], case: BacktestCase, *, hit_cost: float = 4.0) -> list[GwEvaluation]:
    picks = solution.get("picks")
    if not isinstance(picks, pd.DataFrame):
        picks = pd.DataFrame(picks or [])
    statistics = solution.get("statistics") or {}

    out: list[GwEvaluation] = []
    for gw in _case_gws(case):
        rows = picks[picks["week"].astype(int) == int(gw)] if not picks.empty and "week" in picks.columns else pd.DataFrame()
        projected = _projected_points(rows, statistics, gw)
        actual, missing = _actual_points(rows, case.actual_points.get(gw, {}), case.actual_minutes.get(gw, {}))
        stat = _get_gw_stat(statistics, gw)
        hits = int(round(float(stat.get("pt", stat.get("Hits", 0)) or 0)))
        transfer_count = int(round(float(stat.get("nt", stat.get("transfer_count", 0)) or 0)))
        chip = stat.get("chip")
        net = float(actual) - hit_cost * hits
        out.append(
            GwEvaluation(
                gw=int(gw),
                projected_points=float(projected),
                actual_points=float(actual),
                hits=hits,
                net_points=float(net),
                transfer_count=transfer_count,
                missing_actuals=missing,
                chip=str(chip) if chip else None,
            )
        )
    return out


def summarize_results(results: Sequence[BacktestResult]) -> list[dict[str, Any]]:
    by_profile: dict[str, list[BacktestResult]] = {}
    for result in results:
        by_profile.setdefault(result.profile, []).append(result)

    rows: list[dict[str, Any]] = []
    for profile, items in by_profile.items():
        ok = [r for r in items if r.status == "ok"]
        failed = [r for r in items if r.status != "ok"]
        rows.append(
            {
                "profile": profile,
                "cases": len(items),
                "ok": len(ok),
                "failed": len(failed),
                "projected_points": round(sum(r.projected_points for r in ok), 4),
                "actual_points": round(sum(r.actual_points for r in ok), 4),
                "net_points": round(sum(r.net_points for r in ok), 4),
                "avg_net_points": round(_safe_mean(r.net_points for r in ok), 4),
                "hits": int(sum(r.hits for r in ok)),
                "transfers": int(sum(r.transfer_count for r in ok)),
                "missing_actuals": int(sum(r.missing_actuals for r in ok)),
                "avg_solve_time_ms": round(_safe_mean(r.solve_time_ms for r in ok), 1),
            }
        )

    rows.sort(key=lambda r: (r["ok"], r["net_points"], -r["missing_actuals"]), reverse=True)
    return rows


def _required_records(raw: Mapping[str, Any], keys: Sequence[str]) -> list[dict[str, Any]]:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, list):
                raise ValueError(f"'{key}' must be a list of row objects")
            return list(value)
    raise ValueError(f"Case is missing one of: {', '.join(keys)}")


def _parse_actuals(raw: Mapping[str, Any]) -> tuple[dict[int, dict[int, float]], dict[int, dict[int, float]]]:
    value = raw.get("actuals", raw.get("actual_points", {}))
    if isinstance(value, list):
        points: dict[int, dict[int, float]] = {}
        minutes: dict[int, dict[int, float]] = {}
        for item in value:
            if not isinstance(item, Mapping):
                continue
            gw = _first_int(item, ("gw", "week", "gameweek"))
            pid = _first_int(item, ("id", "element", "player_id", "fpl_element_id"))
            if gw is None or pid is None:
                continue
            if "points" in item or "actual_points" in item:
                points.setdefault(gw, {})[pid] = _finite_float(item.get("points", item.get("actual_points")), 0.0)
            if "minutes" in item or "actual_minutes" in item:
                minutes.setdefault(gw, {})[pid] = _finite_float(item.get("minutes", item.get("actual_minutes")), 0.0)
        return points, minutes

    if isinstance(value, Mapping):
        return _nested_number_map(value), _nested_number_map(raw.get("actual_minutes", {}))

    return {}, {}


def _nested_number_map(raw: Any) -> dict[int, dict[int, float]]:
    out: dict[int, dict[int, float]] = {}
    if not isinstance(raw, Mapping):
        return out
    for gw_key, players in raw.items():
        try:
            gw = int(gw_key)
        except Exception:
            continue
        if not isinstance(players, Mapping):
            continue
        out[gw] = {}
        for pid_key, value in players.items():
            try:
                pid = int(pid_key)
            except Exception:
                continue
            out[gw][pid] = _finite_float(value, 0.0)
    return out


def _actual_points(
    rows: pd.DataFrame,
    actual_points: Mapping[int, float],
    actual_minutes: Mapping[int, float],
) -> tuple[float, int]:
    if rows.empty:
        return 0.0, 0

    captain_row = _first_row(rows, "captain")
    vice_row = _first_row(rows, "vicecaptain")
    cap_missing = False
    captain_bonus = 0
    if captain_row is not None:
        cap_id = int(captain_row["id"])
        captain_bonus = max(0, int(captain_row.get("multiplier", 0)) - 1)
        if actual_minutes:
            cap_missing = float(actual_minutes.get(cap_id, 0.0) or 0.0) <= 0

    total = 0.0
    missing = 0
    for _, row in rows.iterrows():
        multiplier = int(row.get("multiplier", 0) or 0)
        if cap_missing and int(row.get("captain", 0) or 0) == 1:
            multiplier = max(0, multiplier - captain_bonus)
        if cap_missing and vice_row is not None and int(row["id"]) == int(vice_row["id"]):
            multiplier += captain_bonus
        if multiplier <= 0:
            continue

        pid = int(row["id"])
        if pid not in actual_points:
            missing += 1
            continue
        total += float(actual_points[pid]) * multiplier
    return total, missing


def _projected_points(rows: pd.DataFrame, statistics: Mapping[Any, Any], gw: int) -> float:
    stat = _get_gw_stat(statistics, gw)
    if "xP" in stat and stat["xP"] is not None:
        return _finite_float(stat["xP"], 0.0)
    if rows.empty:
        return 0.0
    total = 0.0
    for _, row in rows.iterrows():
        if int(row.get("lineup", 0) or 0) != 1:
            continue
        total += _finite_float(row.get("xp_cont", row.get("xP", 0.0)), 0.0)
    return total


def _get_gw_stat(statistics: Mapping[Any, Any], gw: int) -> Mapping[str, Any]:
    stat = statistics.get(gw)
    if stat is None:
        stat = statistics.get(str(gw))
    return stat if isinstance(stat, Mapping) else {}


def _case_gws(case: BacktestCase) -> range:
    last = min(38, case.current_gw + max(0, case.horizon - 1))
    return range(case.current_gw, last + 1)


def _profile_from_dict(raw: Mapping[str, Any]) -> SettingsProfile:
    name = str(raw.get("name") or raw.get("id") or "profile")
    options = raw.get("options", raw.get("settings", {}))
    if not isinstance(options, Mapping):
        raise ValueError(f"Profile '{name}' options must be an object")
    return SettingsProfile(name=name, options=dict(options))


def _first_row(rows: pd.DataFrame, flag: str) -> pd.Series | None:
    if flag not in rows.columns:
        return None
    flagged = rows[rows[flag].astype(int) == 1]
    if flagged.empty:
        return None
    return flagged.iloc[0]


def _first_int(raw: Mapping[str, Any], keys: Sequence[str]) -> int | None:
    for key in keys:
        if key in raw and raw[key] is not None:
            try:
                return int(raw[key])
            except Exception:
                return None
    return None


def _finite_float(value: Any, fallback: float) -> float:
    try:
        f = float(value)
    except Exception:
        return fallback
    return f if math.isfinite(f) else fallback


def _safe_mean(values: Iterable[float | int]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / len(vals) if vals else 0.0


def _short_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, Mapping):
        return "map"
    if isinstance(value, Sequence) and not isinstance(value, str):
        return "list"
    return str(value)


def _serializable_options(options: Mapping[str, Any]) -> dict[str, Any]:
    omit = {"data_df", "fpl_elements_df", "fpl_teams_df", "fixtures"}
    out: dict[str, Any] = {}
    for key, value in options.items():
        if key in omit:
            continue
        try:
            json.dumps(value)
            out[key] = value
        except TypeError:
            out[key] = str(value)
    return out
