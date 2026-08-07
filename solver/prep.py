from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .constants import (
    DEFAULT_POOL_CHEAP_PER_POS,
    DEFAULT_POOL_TOP_N_PER_POS,
    DEFAULT_POSTURE_TILT,
    MAX_GAMEWEEK,
)


def _default_element_types_df() -> pd.DataFrame:
    return (
        pd.DataFrame(
            [
                {"id": 1, "singular_name_short": "GKP", "squad_select": 2, "squad_min_play": 1, "squad_max_play": 1},
                {"id": 2, "singular_name_short": "DEF", "squad_select": 5, "squad_min_play": 3, "squad_max_play": 5},
                {"id": 3, "singular_name_short": "MID", "squad_select": 5, "squad_min_play": 2, "squad_max_play": 5},
                {"id": 4, "singular_name_short": "FWD", "squad_select": 3, "squad_min_play": 1, "squad_max_play": 3},
            ]
        )
        .set_index("id")
    )


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


def _parse_locked_next_gw(value: Any) -> list[int]:
    """Legacy compatibility: locked_next_gw may be [pid] or [[pid,gw], ...]."""
    if not value:
        return []
    out: list[int] = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (list, tuple)) and item:
                try:
                    out.append(int(item[0]))
                except Exception:
                    continue
            else:
                try:
                    out.append(int(item))
                except Exception:
                    continue
    return out


def _extract_pick_price_safe_players(merged: pd.DataFrame, pick_prices: dict[str, Any] | None) -> list[int]:
    if not pick_prices:
        return []
    safe: list[int] = []
    for pos, raw in pick_prices.items():
        if raw is None or raw == "":
            continue
        try:
            points = [float(x) for x in str(raw).split(",")]
        except Exception:
            continue
        try:
            mask = (merged["Pos"] == str(pos)) & ((merged["now_cost"] / 10).isin(points))
            safe.extend([int(x) for x in merged.loc[mask, "ID"].tolist()])
        except Exception:
            continue
    return safe


@dataclass(frozen=True)
class PreparedData:
    merged_data: pd.DataFrame
    team_data: pd.DataFrame
    type_data: pd.DataFrame
    fixtures: list[dict[str, Any]]
    next_gw: int
    initial_squad: list[int]
    buy_price: dict[int, float]
    sell_price: dict[int, float]
    price_modified_players: list[int]
    itb: float
    ft: int
    ft_base: int
    max_players_from_team: int
    meta: dict[str, Any]


def prepare_data(team_json: dict[str, Any], options: dict[str, Any]) -> PreparedData:
    """
    Prepare solver inputs in a legacy-compatible way, but with strict no-API rules:
    - requires bootstrap snapshots (elements + teams) in options
    - requires a pre-built projections DataFrame (options['data_df'])
    - requires override_next_gw (so we don't look up "is_next" from the FPL API)
    """

    if team_json is None:
        raise ValueError("team_json is required")

    elements_df = options.get("fpl_elements_df")
    teams_df = options.get("fpl_teams_df")
    if elements_df is None or teams_df is None:
        raise ValueError("fpl_elements_df and fpl_teams_df are required (no FPL API calls allowed)")

    data_df = options.get("data_df")
    if data_df is None:
        raise ValueError("data_df is required (projections must be provided)")

    if options.get("override_next_gw") is None:
        raise ValueError("override_next_gw must be provided (no FPL API calls allowed)")

    next_gw = int(options["override_next_gw"])
    horizon = int(options.get("horizon", 3))

    # Clone frames defensively.
    elements = elements_df.copy()
    teams = teams_df.copy()
    projections = data_df.copy()

    # Normalize expected bootstrap columns.
    required_el_cols = {"id", "web_name", "team", "element_type", "now_cost"}
    missing = required_el_cols - set(elements.columns)
    if missing:
        raise ValueError(f"fpl_elements_df missing columns: {sorted(missing)}")

    required_team_cols = {"id", "name"}
    missing_team = required_team_cols - set(teams.columns)
    if missing_team:
        raise ValueError(f"fpl_teams_df missing columns: {sorted(missing_team)}")

    # Apply any hypothetical price changes.
    for pid, delta in options.get("price_changes", []) or []:
        try:
            pid_i = int(pid)
            delta_i = int(delta)
        except Exception:
            continue
        elements.loc[elements["id"].astype(int) == pid_i, "now_cost"] = elements.loc[elements["id"].astype(int) == pid_i, "now_cost"] + delta_i

    # Merge (elements ⨝ teams) ⨝ projections
    teams = teams.rename(columns={"id": "team_id", "name": "team_name"})
    elements_team = elements.merge(teams, left_on="team", right_on="team_id", how="left")

    if "ID" not in projections.columns:
        raise ValueError("data_df must include column 'ID'")

    merged = elements_team.merge(projections, left_on="id", right_on="ID", how="inner")
    merged = merged.drop_duplicates(subset=["ID"], keep="first").copy()
    merged["id"] = merged["id"].astype(int)
    merged.set_index("id", inplace=True)

    # Validate the GW window columns exist.
    gw_end = min(MAX_GAMEWEEK, next_gw + max(0, horizon - 1))
    for gw in range(next_gw, gw_end + 1):
        if f"{gw}_Pts" not in merged.columns:
            raise ValueError(f"Missing projection column: {gw}_Pts")
        if f"{gw}_xMins" not in merged.columns:
            raise ValueError(f"Missing projection column: {gw}_xMins")

    pts_cols = [c for c in merged.columns if str(c).endswith("_Pts")]
    mins_cols = [c for c in merged.columns if str(c).endswith("_xMins")]
    merged["total_ev"] = merged[pts_cols].sum(axis=1)
    merged["total_min"] = merged[mins_cols].sum(axis=1)

    # Keep-penalties: distribute across the horizon.
    keep_penalties = options.get("keep_penalties") or {}
    if keep_penalties:
        n_gws = max(1, len(pts_cols))
        for pid_str, penalty in keep_penalties.items():
            try:
                pid = int(pid_str)
                penalty_f = float(penalty)
            except Exception:
                continue
            mask = merged["ID"].astype(int) == pid
            if not mask.any():
                continue
            per_gw = penalty_f / n_gws
            for col in pts_cols:
                merged.loc[mask, col] = merged.loc[mask, col] + per_gw
        merged["total_ev"] = merged[pts_cols].sum(axis=1)

    # Low-minutes safety scaling for non-owned players (prevents phantom EV).
    current_ids = {int(p["element"]) for p in (team_json.get("picks") or []) if p and p.get("element") is not None}
    low_min_threshold = 30
    low_min_mask = (merged["total_min"] < low_min_threshold) & (~merged["ID"].astype(int).isin(current_ids))
    if low_min_mask.any():
        scale = merged.loc[low_min_mask, "total_min"].clip(lower=0) / max(low_min_threshold, 1)
        for col in pts_cols:
            merged.loc[low_min_mask, col] = merged.loc[low_min_mask, col] * scale
        merged.loc[low_min_mask, "total_ev"] = merged.loc[low_min_mask, pts_cols].sum(axis=1)

    # Global-field posture tilt (protect|neutral|chase): a small multiplicative
    # EV tilt from overall ownership. Complements — does not replace — the
    # rival-aware league_context objective in solve.py; intended for users with
    # no configured mini-league. Missing ownership data ⇒ neutral per player.
    posture = str(options.get("posture", "neutral") or "neutral").lower()
    posture_tilt = float(options.get("posture_tilt", DEFAULT_POSTURE_TILT) or 0.0)
    posture_applied = False
    if posture in ("protect", "chase") and posture_tilt > 0:
        own_col = next(
            (c for c in ("selected_by_percent", "Selected", "ownership_percent") if c in merged.columns),
            None,
        )
        if own_col is not None:
            eo = pd.to_numeric(merged[own_col], errors="coerce").div(100.0).clip(0.0, 1.0).fillna(0.5)
            direction = 1.0 if posture == "protect" else -1.0
            factor = (1.0 + direction * posture_tilt * (2.0 * eo - 1.0)).clip(
                1.0 - posture_tilt, 1.0 + posture_tilt
            )
            for col in pts_cols:
                merged[col] = merged[col] * factor
            merged["total_ev"] = merged[pts_cols].sum(axis=1)
            posture_applied = True

    merged.sort_values(by=["total_ev"], ascending=[False], inplace=True)

    locked_next_gw = _parse_locked_next_gw(options.get("locked_next_gw"))
    safe_due_price = _extract_pick_price_safe_players(merged, options.get("pick_prices"))

    keep_top_ev_percent = float(options.get("keep_top_ev_percent", 10) or 10)
    cutoff = merged["total_ev"].quantile((100.0 - keep_top_ev_percent) / 100.0)
    safe_due_ev = [int(x) for x in merged.loc[merged["total_ev"] > cutoff, "ID"].tolist()]

    locked = _as_int_list(options.get("locked"))
    keep = _as_int_list(options.get("keep"))
    safe_players = list(current_ids) + locked + keep + locked_next_gw + safe_due_price + safe_due_ev

    for bt in options.get("booked_transfers", []) or []:
        if not isinstance(bt, dict):
            continue
        if bt.get("transfer_in") is not None:
            safe_players.extend(_as_int_list(bt.get("transfer_in")))
        if bt.get("transfer_out") is not None:
            safe_players.extend(_as_int_list(bt.get("transfer_out")))

    safe_players_set = {int(x) for x in safe_players if x is not None}

    xmin_lb = int(options.get("xmin_lb", 100) or 100)
    before = int(len(merged))
    merged = merged[(merged["total_min"] >= xmin_lb) | (merged["ID"].astype(int).isin(safe_players_set))].copy()

    ev_per_price_cutoff = float(options.get("ev_per_price_cutoff", 0) or 0)
    if ev_per_price_cutoff != 0:
        ratio = merged["total_ev"] / merged["now_cost"].replace(0, pd.NA)
        ratio = ratio.fillna(0)
        ratio_cutoff = ratio.quantile(ev_per_price_cutoff / 100.0)
        merged = merged[(ratio > ratio_cutoff) | (merged["ID"].astype(int).isin(safe_players_set))].copy()

    # Per-position pool cap: keep the top-N EV candidates per position, the
    # cheapest playing enablers (budget feasibility), and the protected set.
    # Cuts MILP binaries ~2-3x; dropped players are EV-dominated in-position.
    # Pass pool_top_n_per_pos: null to disable.
    cap_raw = options.get("pool_top_n_per_pos", DEFAULT_POOL_TOP_N_PER_POS)
    pool_capped = False
    if cap_raw and "Pos" in merged.columns:
        # Production data uses single-letter positions (G/D/M/F from
        # db_data_loader.POS_MAP); canonicalise both sides of the lookup so the
        # cap works regardless of which convention supplied the labels.
        pos_canon = {
            "G": "GKP", "GK": "GKP", "GKP": "GKP",
            "D": "DEF", "DEF": "DEF",
            "M": "MID", "MID": "MID",
            "F": "FWD", "FWD": "FWD",
        }
        caps = {
            pos_canon.get(str(k).upper(), str(k).upper()): int(v)
            for k, v in dict(cap_raw).items()
        }
        cheap_keep = int(options.get("pool_cheap_per_pos", DEFAULT_POOL_CHEAP_PER_POS) or 0)
        keep_ids: set[int] = set()
        for pos, grp in merged.groupby("Pos"):
            n = caps.get(pos_canon.get(str(pos).upper(), str(pos).upper()))
            if n is None:
                keep_ids.update(int(x) for x in grp["ID"].tolist())
                continue
            keep_ids.update(int(x) for x in grp.nlargest(n, "total_ev")["ID"].tolist())
            if cheap_keep > 0:
                keep_ids.update(int(x) for x in grp.nsmallest(cheap_keep, "now_cost")["ID"].tolist())
        merged = merged[merged["ID"].astype(int).isin(keep_ids | safe_players_set)].copy()
        pool_capped = True

    after = int(len(merged))
    if after < 15:
        raise ValueError("Player pool too small after filtering")

    # Element types (formation constraints).
    type_data = options.get("element_types_df")
    if type_data is None:
        type_data = _default_element_types_df()
    elif isinstance(type_data, pd.DataFrame) and type_data.index.name != "id" and "id" in type_data.columns:
        type_data = type_data.set_index("id")

    # Prices
    buy_price_raw = (merged["now_cost"] / 10.0).to_dict()
    buy_price = {k: (v if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else 0.0) for k, v in buy_price_raw.items()}
    sell_price = {int(p["element"]): float(p["selling_price"]) / 10.0 for p in (team_json.get("picks") or []) if p and p.get("element") is not None}

    preseason = bool(options.get("preseason", False))
    price_modified: list[int] = []
    if not preseason:
        for p in (team_json.get("picks") or []):
            if not p or p.get("element") is None:
                continue
            pid = int(p["element"])
            if pid in buy_price and pid in sell_price and float(buy_price[pid]) != float(sell_price[pid]):
                price_modified.append(pid)

    # Team budget + FT state
    itb = float(team_json.get("transfers", {}).get("bank", 0) or 0) / 10.0
    transfers_limit = team_json.get("transfers", {}).get("limit")
    transfers_made = int(team_json.get("transfers", {}).get("made", 0) or 0)
    if transfers_limit is None:
        ft = 1
    else:
        ft = int(transfers_limit) - transfers_made
    ft = max(0, int(ft))
    # FPL always resets FTs to 1 after WC/FH — ft_base is the reset value.
    ft_base = 1

    # Max players per team in current squad (for edge-case relaxation).
    element_to_team = elements.set_index("id")["team"].to_dict()
    current_team_counts = Counter([element_to_team.get(int(p["element"])) for p in (team_json.get("picks") or []) if p and p.get("element") is not None])
    max_from_team = max(current_team_counts.values()) if current_team_counts else 3

    fixtures = options.get("fixtures")
    if fixtures is None:
        raise ValueError("fixtures must be provided (no FPL API calls allowed)")

    # Validate initial squad: ensure all picks are in the player pool.
    # If a player is missing (e.g., new signing not in pipeline data), remove
    # them from the initial squad and credit their selling price to the bank
    # so the solver can buy a replacement. This is rare: the pool reduction
    # above always keeps current squad members (safe_players includes
    # current_ids), so a member only goes "missing" when it is entirely absent
    # from the projection data (e.g. added to FPL after the last pipeline run).
    #
    # The number of credited-missing members is reported in meta below. solve.py
    # reads it and, when it is > 0, requires the replacement(s) to be bought from
    # this credited bank (a full-squad + budget-conservation constraint at
    # next_gw-1) rather than filled for free — closing the over-credit where the
    # manager would otherwise keep the credit AND get the fill free. The credit
    # is what keeps that constraint feasible; a short squad WITHOUT a credit
    # (e.g. a caller passing <15 picks) keeps the original free fill.
    pool_ids = set(int(x) for x in merged["ID"].tolist())
    missing_ids = current_ids - pool_ids
    valid_initial = current_ids - missing_ids
    if missing_ids:
        import sys
        print(f"[prep] WARNING: {len(missing_ids)} squad member(s) not in player pool: {sorted(missing_ids)}", file=sys.stderr)
        # Credit missing players' selling prices to the bank
        for p in (team_json.get("picks") or []):
            if not p or p.get("element") is None:
                continue
            pid = int(p["element"])
            if pid in missing_ids:
                sp = float(p.get("selling_price", 0) or 0) / 10.0
                itb += sp
                print(f"[prep] Credited {sp}m to bank for missing player {pid}", file=sys.stderr)

    meta = {
        "pool_players_before_filter": before,
        "pool_players_after_filter": after,
        "pool_xmin_lb": xmin_lb,
        "pool_keep_top_ev_percent": keep_top_ev_percent,
        "pool_ev_per_price_cutoff": ev_per_price_cutoff,
        "pool_safe_players": int(len(safe_players_set)),
        "pool_top_n_capped": pool_capped,
        "posture": posture,
        "posture_applied": posture_applied,
        "missing_squad_members": int(len(missing_ids)),
    }

    return PreparedData(
        merged_data=merged,
        team_data=teams,
        type_data=type_data,
        fixtures=fixtures,
        next_gw=next_gw,
        initial_squad=sorted(list(valid_initial)),
        buy_price={int(k): float(v) for k, v in buy_price.items()},
        sell_price={int(k): float(v) for k, v in sell_price.items()},
        price_modified_players=sorted(price_modified),
        itb=itb,
        ft=ft,
        ft_base=int(ft_base),
        max_players_from_team=int(max_from_team),
        meta=meta,
    )

