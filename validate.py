#!/usr/bin/env python3
"""
Integrity checks for the SmartPlayFPL dataset and mappings.

Every check here exists because the thing it tests has actually gone wrong and
cost somebody real time — either us or, given these files are public, whoever
built on them next. They are cheap to run and they fail loudly.

    python validate.py            # full run
    python validate.py --quick    # skip the slow full-CSV pass

Exit code 0 if everything passes, 1 otherwise, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "smartplay_data.csv"
PLAYERS = ROOT / "data" / "mappings" / "players_golden_record.csv"
CLUBS = ROOT / "data" / "mappings" / "clubs_golden_record.csv"

FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"

# Provenance of the FPL projection column. `imputed_0` is a placeholder, not a
# projection, and the two real sources are not interchangeable — see
# data/README.md.
EXPECTED_POINTS_SOURCES = {"fplcache_ep_next", "vaastav_xP", "imputed_0"}

failures: list[str] = []
notes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{': ' + detail if detail else ''}")
    if not ok:
        failures.append(f"{name}{': ' + detail if detail else ''}")


def note(msg: str) -> None:
    print(f"  ..    {msg}")
    notes.append(msg)


def check_mappings() -> None:
    print("\nmappings")
    players = list(csv.DictReader(PLAYERS.open()))
    clubs = list(csv.DictReader(CLUBS.open()))

    check("players_golden_record is non-empty", len(players) > 1000, f"{len(players)} rows")
    check("clubs_golden_record is non-empty", len(clubs) >= 20, f"{len(clubs)} rows")

    codes = [r["fpl_code"] for r in players]
    check("no duplicate fpl_code", len(codes) == len(set(codes)),
          f"{len(codes) - len(set(codes))} duplicates")

    allowed = {"HIGH", "MEDIUM", "LOW", "NONE"}
    bad = {r["confidence_level"] for r in players} - allowed
    check("confidence_level values are known", not bad, str(bad))

    with_id = sum(1 for r in players if r.get("understat_player_id"))
    note(f"{with_id}/{len(players)} players carry an Understat id")


def check_live_squad_coverage() -> None:
    """The seasonal killer: promoted clubs and new signings with no mapping.

    Three clubs go up every August and none of their players exist in last
    season's golden record. A join keyed on it then drops them silently, or
    dies, depending on how strict the pipeline is.
    """
    print("\nlive FPL squad coverage")
    try:
        import urllib.request

        with urllib.request.urlopen(FPL_BOOTSTRAP, timeout=30) as resp:
            boot = json.loads(resp.read())
    except Exception as exc:
        note(f"skipped — could not reach the FPL API ({type(exc).__name__})")
        return

    mapped = {r["fpl_code"] for r in csv.DictReader(PLAYERS.open())}
    club_names = {r["fpl_club_name"] if "fpl_club_name" in r else next(iter(r.values()))
                  for r in csv.DictReader(CLUBS.open())}

    live_players = [str(e["code"]) for e in boot["elements"]]
    missing = [c for c in live_players if c not in mapped]
    check("every current FPL player has a mapping row",
          not missing, f"{len(missing)} of {len(live_players)} unmapped")

    live_clubs = {t["name"] for t in boot["teams"]}
    missing_clubs = sorted(live_clubs - club_names)
    check("every current PL club is in the club mapping",
          not missing_clubs, ", ".join(missing_clubs))


def check_dataset(quick: bool) -> None:
    print("\ndataset")
    if not DATA.exists():
        note("smartplay_data.csv absent — run `python data/download.py` to check it")
        return
    check("smartplay_data.csv exists", True, str(DATA))
    if DATA.stat().st_size < 1_000_000:
        check("smartplay_data.csv looks complete", False,
              "run `python data/download.py`")
        return
    if quick:
        note("skipped full-CSV checks (--quick)")
        return

    try:
        import pandas as pd
    except ImportError:
        note("skipped — pandas not installed")
        return

    df = pd.read_csv(
        DATA,
        usecols=["season", "gameweek", "fpl_code", "fixture", "total_points",
                 "minutes", "expected_points_source"],
        low_memory=False,
    )
    check("dataset is non-empty", len(df) > 100_000, f"{len(df)} rows")

    dupes = df.duplicated(subset=["season", "fixture", "fpl_code"]).sum()
    check("unique on (season, fixture, fpl_code)", dupes == 0, f"{dupes} duplicates")

    bad_gw = df[~df["gameweek"].between(1, 38)]
    check("gameweeks are within 1-38", bad_gw.empty, f"{len(bad_gw)} rows outside")

    srcs = set(df["expected_points_source"].dropna().unique())
    check("expected_points_source values are known",
          srcs <= EXPECTED_POINTS_SOURCES, str(srcs - EXPECTED_POINTS_SOURCES))

    # A season that stops short is the quiet failure: the file looks complete,
    # the README claims the season, and every model trained on it is short a
    # run-in. The current season is legitimately partial; earlier ones are not.
    per_season = df.groupby("season")["gameweek"].max().sort_index()
    for season, max_gw in per_season.items():
        if season == per_season.index[-1]:
            note(f"{season} reaches GW{max_gw} (current season, may be partial)")
        else:
            check(f"{season} runs to GW38", max_gw == 38, f"stops at GW{max_gw}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip the full-CSV pass")
    args = parser.parse_args()

    print("SmartPlayFPL dataset validation")
    check_mappings()
    check_live_squad_coverage()
    check_dataset(args.quick)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
