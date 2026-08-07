"""
update_golden_records.py

Updates players_golden_record.csv and clubs_golden_record.csv by
cross-referencing three data sources:

  1. ChrisMusson/FPL-ID-Map  — FPL code ↔ Understat ID mapping
  2. FPL bootstrap-static API — current players & teams
  3. Understat league data    — player names & teams

Run daily (or before each pipeline run) to pick up new signings,
promoted clubs, and ID-map updates.

Usage:
    python update_golden_records.py
    python update_golden_records.py --season 2024   # override Understat season

Dependencies:
    pip install requests understatapi pandas
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from understatapi import UnderstatClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PLAYERS_CSV = SCRIPT_DIR / "players_golden_record.csv"
CLUBS_CSV = SCRIPT_DIR / "clubs_golden_record.csv"

CHRISMUSSON_URL = (
    "https://raw.githubusercontent.com/ChrisMusson/FPL-ID-Map/main/Understat.csv"
)
FPL_BOOTSTRAP_URL = (
    "https://fantasy.premierleague.com/api/bootstrap-static/"
)

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_chrismusson_map() -> pd.DataFrame:
    """Download ChrisMusson's FPL-code-to-Understat-ID map."""
    log.info("Fetching ChrisMusson FPL-ID-Map …")
    df = pd.read_csv(CHRISMUSSON_URL)
    # Columns: code, first_name, second_name, web_name, understat
    df = df.rename(columns={"code": "fpl_code", "understat": "understat_player_id"})
    df["fpl_code"] = df["fpl_code"].astype(int)
    df["understat_player_id"] = pd.to_numeric(
        df["understat_player_id"], errors="coerce"
    )
    log.info(f"  → {len(df)} mappings loaded")
    return df


def fetch_fpl_bootstrap() -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Fetch current FPL players and teams from bootstrap-static."""
    log.info("Fetching FPL bootstrap-static …")
    resp = requests.get(FPL_BOOTSTRAP_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    players = pd.DataFrame(data["elements"])[
        [
            "code",
            "first_name",
            "second_name",
            "web_name",
            "element_type",
            "team_code",
            "status",
        ]
    ].rename(columns={"code": "fpl_code"})
    players["fpl_position"] = players["element_type"].map(POSITION_MAP)
    log.info(f"  → {len(players)} players")

    teams = pd.DataFrame(data["teams"])[["code", "name", "short_name"]].rename(
        columns={"code": "fpl_team_code", "name": "club_name", "short_name": "club_short"}
    )
    log.info(f"  → {len(teams)} teams")

    return players, teams, data.get("events", [])


US_COLUMNS = ["understat_player_id", "player_name", "team_title"]


def fetch_understat_players(season: str) -> pd.DataFrame:
    """Fetch Understat league player data for current + previous season.

    Combines both to maximise coverage — new signings appear in the current
    season, while players who left appear in the previous one.

    A season with no data is skipped rather than fatal. Understat publishes a
    season only once it kicks off, so between late May and the opening weekend
    the current season is simply empty — which is exactly when you most need to
    run this, because that is when the new signings and promoted squads land.
    Crashing here left the golden record frozen for the whole pre-season.

    If neither season returns anything the result is empty, and callers fall
    back to the ChrisMusson ID map alone; those rows are marked MEDIUM
    confidence, which already means "ID known, not seen in the current
    Understat season".
    """
    us = UnderstatClient()
    all_dfs = []

    for s in [season, str(int(season) - 1)]:
        log.info(f"Fetching Understat EPL player data (season={s}) …")
        try:
            raw = us.league(league="EPL").get_player_data(season=s)
        except Exception as exc:  # network, or a season the API rejects outright
            log.warning(f"  → season {s} unavailable ({type(exc).__name__}), skipping")
            continue

        df = pd.DataFrame(raw)
        if df.empty or not {"id", "player_name", "team_title"}.issubset(df.columns):
            log.warning(f"  → season {s} returned no player data, skipping (not yet published?)")
            continue

        df = df[["id", "player_name", "team_title"]].rename(columns={"id": "understat_player_id"})
        df["understat_player_id"] = df["understat_player_id"].astype(int)
        log.info(f"  → {len(df)} players")
        all_dfs.append(df)

    if not all_dfs:
        log.warning(
            "No Understat season returned data. Falling back to the ID map alone; "
            "new mappings will be MEDIUM confidence until Understat publishes."
        )
        return pd.DataFrame(columns=US_COLUMNS)

    # Deduplicate — prefer the current season's record
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset="understat_player_id", keep="first")
    log.info(f"  → {len(combined)} unique players after dedup")
    return combined


def fetch_understat_teams(season: str) -> pd.DataFrame:
    """Fetch Understat team list, falling back to the previous season.

    Same pre-season problem as the player fetch: an unpublished season comes
    back as an empty list rather than the usual id-keyed dict, so indexing it
    raised AttributeError and took the whole run down. Falling back one season
    keeps club names resolvable; the promoted sides are absent either way until
    Understat publishes, which is why clubs_golden_record is maintained by hand
    each August.
    """
    us = UnderstatClient()

    for s in [season, str(int(season) - 1)]:
        log.info(f"Fetching Understat EPL team data (season={s}) …")
        try:
            raw = us.league(league="EPL").get_team_data(season=s)
        except Exception as exc:
            log.warning(f"  → season {s} unavailable ({type(exc).__name__}), skipping")
            continue

        if not isinstance(raw, dict) or not raw:
            log.warning(f"  → season {s} returned no team data, skipping (not yet published?)")
            continue

        df = pd.DataFrame([
            {"understat_name": v["title"], "understat_team_id": int(v["id"])}
            for v in raw.values()
        ])
        log.info(f"  → {len(df)} teams")
        return df

    log.warning("No Understat season returned team data; club names left as-is.")
    return pd.DataFrame(columns=["understat_name", "understat_team_id"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def split_understat_name(name: str) -> tuple[str, str]:
    """Split 'First Last' into (first, last). Handles single names."""
    parts = name.strip().split(" ", 1)
    if len(parts) == 1:
        return "", parts[0]
    return parts[0], parts[1]


def current_understat_season(now: datetime | None = None) -> str:
    """Return the Understat season code for today's date.

    Understat uses the starting year: '2024' means 2024-25.
    The PL season starts in August, so Aug-Dec → current year,
    Jan-Jul → previous year.
    """
    now = now or datetime.now()
    return str(now.year if now.month >= 8 else now.year - 1)


def understat_season_from_fpl_events(
    events: list[dict],
    fallback_now: datetime | None = None,
) -> str:
    """Use FPL's published deadlines as the season boundary when available."""
    deadlines = []
    for event in events:
        raw = event.get("deadline_time") if isinstance(event, dict) else None
        if not raw or not isinstance(raw, str):
            continue
        try:
            deadlines.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            continue
    if deadlines:
        return str(min(deadlines).year)
    return current_understat_season(fallback_now)


# ---------------------------------------------------------------------------
# Update logic
# ---------------------------------------------------------------------------


def update_players(
    existing: pd.DataFrame,
    cm_map: pd.DataFrame,
    fpl_players: pd.DataFrame,
    us_players: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all sources and return the updated golden record."""

    # Index existing by fpl_code for fast lookup
    existing_codes = set(existing["fpl_code"].astype(int))

    # Build a lookup: understat_id → understat name info
    us_lookup: dict[int, dict] = {}
    for _, row in us_players.iterrows():
        uid = int(row["understat_player_id"])
        first, last = split_understat_name(row["player_name"])
        us_lookup[uid] = {
            "understat_first_name": first,
            "understat_second_name": last,
            "understat_web_name": last or first,
        }

    # Build a lookup: fpl_code → understat_id from ChrisMusson
    cm_lookup: dict[int, int] = {}
    for _, row in cm_map.iterrows():
        if pd.notna(row["understat_player_id"]):
            cm_lookup[int(row["fpl_code"])] = int(row["understat_player_id"])

    new_rows = []
    updated = 0

    for _, fp in fpl_players.iterrows():
        fpl_code = int(fp["fpl_code"])

        if fpl_code in existing_codes:
            continue  # already mapped

        # Try to find Understat ID from ChrisMusson's map
        us_id = cm_lookup.get(fpl_code)

        us_first = ""
        us_last = ""
        us_web = ""
        confidence = "HIGH" if us_id else "NONE"

        if us_id and us_id in us_lookup:
            info = us_lookup[us_id]
            us_first = info["understat_first_name"]
            us_last = info["understat_second_name"]
            us_web = info["understat_web_name"]
        elif us_id:
            # Have the ID from ChrisMusson but player not in current Understat season
            # (retired / transferred out of PL) — still record the mapping
            confidence = "MEDIUM"

        new_rows.append(
            {
                "fpl_code": fpl_code,
                "fpl_player_name": fp["web_name"],
                "fpl_first_name": fp["first_name"],
                "fpl_second_name": fp["second_name"],
                "fpl_position": fp["fpl_position"],
                "understat_player_id": us_id if us_id else "",
                "understat_first_name": us_first,
                "understat_second_name": us_last,
                "understat_web_name": us_web,
                "confidence_level": confidence,
            }
        )
        updated += 1

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        result = pd.concat([existing, new_df], ignore_index=True)
    else:
        result = existing.copy()

    # Backfill: existing rows with missing FPL names (data quality cleanup)
    fpl_lookup = {
        int(row["fpl_code"]): row for _, row in fpl_players.iterrows()
    }
    for idx, row in result.iterrows():
        if pd.notna(row["fpl_player_name"]) and str(row["fpl_player_name"]).strip():
            continue
        fpl_code = int(row["fpl_code"])
        fp = fpl_lookup.get(fpl_code)
        if fp is not None:
            result.at[idx, "fpl_player_name"] = fp["web_name"]
            result.at[idx, "fpl_first_name"] = fp["first_name"]
            result.at[idx, "fpl_second_name"] = fp["second_name"]
            result.at[idx, "fpl_position"] = fp["fpl_position"]

    # Backfill: existing rows missing understat_player_id — ChrisMusson may have it now
    backfilled_id = 0
    for idx, row in result.iterrows():
        fpl_code = int(row["fpl_code"])
        current_us_id = row["understat_player_id"]

        if pd.notna(current_us_id) and str(current_us_id).strip() not in ("", "nan"):
            continue

        us_id = cm_lookup.get(fpl_code)
        if not us_id:
            continue

        result.at[idx, "understat_player_id"] = us_id
        if us_id in us_lookup:
            info = us_lookup[us_id]
            result.at[idx, "understat_first_name"] = info["understat_first_name"]
            result.at[idx, "understat_second_name"] = info["understat_second_name"]
            result.at[idx, "understat_web_name"] = info["understat_web_name"]
            result.at[idx, "confidence_level"] = "HIGH"
        else:
            result.at[idx, "confidence_level"] = "MEDIUM"
        backfilled_id += 1

    # Backfill: rows that have an understat_player_id but missing Understat names
    backfilled_name = 0
    for idx, row in result.iterrows():
        us_id_raw = row["understat_player_id"]
        if not (pd.notna(us_id_raw) and str(us_id_raw).strip() not in ("", "nan")):
            continue

        us_web = row.get("understat_web_name", "")
        if pd.notna(us_web) and str(us_web).strip() not in ("", "nan"):
            continue  # already has a name

        us_id = int(float(us_id_raw))
        if us_id not in us_lookup:
            continue

        info = us_lookup[us_id]
        result.at[idx, "understat_first_name"] = info["understat_first_name"]
        result.at[idx, "understat_second_name"] = info["understat_second_name"]
        result.at[idx, "understat_web_name"] = info["understat_web_name"]
        if row.get("confidence_level") == "MEDIUM":
            result.at[idx, "confidence_level"] = "HIGH"
        backfilled_name += 1

    log.info(f"  Players: {updated} new, {backfilled_id} IDs backfilled, {backfilled_name} names backfilled")
    return result


def update_clubs(
    existing: pd.DataFrame,
    fpl_teams: pd.DataFrame,
    us_teams: pd.DataFrame,
) -> pd.DataFrame:
    """Add any new clubs (e.g. promoted teams) to the golden record."""

    existing_codes = set(existing["fpl_team_code"].astype(int))

    # Build a lookup for Understat teams by normalised name
    us_lookup: dict[str, dict] = {}
    for _, row in us_teams.iterrows():
        us_lookup[row["understat_name"].lower()] = {
            "understat_name": row["understat_name"],
            "understat_team_id": int(row["understat_team_id"]),
        }

    # Common FPL → Understat name mappings for tricky cases
    NAME_FIXES: dict[str, str] = {
        "man city": "manchester city",
        "man utd": "manchester united",
        "spurs": "tottenham",
        "nott'm forest": "nottingham forest",
        "wolves": "wolverhampton wanderers",
        "brighton": "brighton & hove albion",
        "west ham": "west ham united",
        "newcastle": "newcastle united",
        "leicester": "leicester city",
        "ipswich": "ipswich town",
        "luton": "luton town",
        "sheffield utd": "sheffield united",
        "coventry city": "coventry",
        "hull city": "hull",
    }

    result = existing.copy()
    if "understat_team_id" in result.columns:
        # CSV blanks may infer an Arrow string column under pandas 3. Keep the
        # column assignable when a newly discovered numeric Understat ID lands.
        result["understat_team_id"] = result["understat_team_id"].astype(object)
    new_rows = []
    backfilled = 0
    for _, ft in fpl_teams.iterrows():
        code = int(ft["fpl_team_code"])
        fpl_name = ft["club_name"]
        fpl_lower = fpl_name.lower()

        # Try direct match, then name fixes
        us_key = fpl_lower
        if us_key not in us_lookup:
            us_key = NAME_FIXES.get(fpl_lower, fpl_lower)

        us_info = us_lookup.get(us_key, {})

        if code in existing_codes:
            matches = result.index[result["fpl_team_code"].astype(int) == code]
            if len(matches) == 0:
                continue
            idx = matches[0]
            result.at[idx, "club_name"] = fpl_name
            result.at[idx, "club_short"] = ft["club_short"]

            current_us_name = result.at[idx, "understat_name"]
            missing_us_name = pd.isna(current_us_name) or not str(current_us_name).strip()
            if missing_us_name and us_info:
                result.at[idx, "understat_name"] = us_info["understat_name"]
                result.at[idx, "understat_team_id"] = us_info["understat_team_id"]
                backfilled += 1
            continue

        new_rows.append(
            {
                "club_name": fpl_name,
                "club_short": ft["club_short"],
                "fpl_team_code": code,
                "understat_name": us_info.get("understat_name", ""),
                "understat_team_id": us_info.get("understat_team_id", ""),
            }
        )

    if new_rows:
        result = pd.concat([result, pd.DataFrame(new_rows)], ignore_index=True)

    log.info(f"  Clubs: {len(new_rows)} new added, {backfilled} Understat mappings backfilled")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update players & clubs golden record CSVs"
    )
    parser.add_argument(
        "--season",
        default=None,
        help="Understat season code, e.g. '2024' for 2024-25 (auto-detected if omitted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without writing files",
    )
    args = parser.parse_args()

    # ── Fetch all sources ──
    cm_map = fetch_chrismusson_map()
    fpl_players, fpl_teams, fpl_events = fetch_fpl_bootstrap()
    season = args.season or understat_season_from_fpl_events(fpl_events)
    log.info(f"Season: {season} ({'FPL event deadlines' if not args.season else 'manual'})")
    us_players = fetch_understat_players(season)
    us_teams = fetch_understat_teams(season)

    # ── Load existing golden records ──
    if PLAYERS_CSV.exists():
        existing_players = pd.read_csv(PLAYERS_CSV, dtype={"understat_player_id": str})
        log.info(f"Existing players: {len(existing_players)}")
    else:
        existing_players = pd.DataFrame(
            columns=[
                "fpl_code", "fpl_player_name", "fpl_first_name", "fpl_second_name",
                "fpl_position", "understat_player_id", "understat_first_name",
                "understat_second_name", "understat_web_name", "confidence_level",
            ]
        )
        log.info("No existing players file — starting fresh")

    if CLUBS_CSV.exists():
        existing_clubs = pd.read_csv(CLUBS_CSV)
        log.info(f"Existing clubs: {len(existing_clubs)}")
    else:
        existing_clubs = pd.DataFrame(
            columns=[
                "club_name", "club_short", "fpl_team_code",
                "understat_name", "understat_team_id",
            ]
        )
        log.info("No existing clubs file — starting fresh")

    # ── Update ──
    updated_players = update_players(existing_players, cm_map, fpl_players, us_players)
    updated_clubs = update_clubs(existing_clubs, fpl_teams, us_teams)

    # ── Sort for stable diffs ──
    updated_players = updated_players.sort_values("fpl_code").reset_index(drop=True)
    updated_clubs = updated_clubs.sort_values("club_name").reset_index(drop=True)

    # ── Write ──
    if args.dry_run:
        new_p = len(updated_players) - len(existing_players)
        new_c = len(updated_clubs) - len(existing_clubs)
        log.info(f"DRY RUN — would add {new_p} players, {new_c} clubs")
        if new_p > 0:
            new_codes = set(updated_players["fpl_code"]) - set(existing_players["fpl_code"])
            sample = updated_players[updated_players["fpl_code"].isin(new_codes)].head(10)
            print("\nSample new players:")
            print(sample.to_string(index=False))
    else:
        updated_players.to_csv(PLAYERS_CSV, index=False)
        updated_clubs.to_csv(CLUBS_CSV, index=False)
        log.info(f"Wrote {PLAYERS_CSV.name} ({len(updated_players)} rows)")
        log.info(f"Wrote {CLUBS_CSV.name} ({len(updated_clubs)} rows)")

    log.info("Done.")


if __name__ == "__main__":
    main()
