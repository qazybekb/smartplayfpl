# mappings

Golden-record CSVs that link FPL player/club IDs to Understat IDs. These mappings are critical for joining FPL data with Understat xG data.

## Files

| File | Rows | Description |
|---|---|---|
| `players_golden_record.csv` | ~1,601 | FPL player code → Understat player ID mapping |
| `clubs_golden_record.csv` | 30 | FPL club → Understat team mapping, current for 2026-27 |
| `update_golden_records.py` | Script | Fetches latest data from 3 sources and updates both CSVs |

> **Promoted clubs break this file every August.** Three clubs go up each
> season and are absent from the previous season's club mapping, so any join
> keyed on it silently drops their players — or fails outright, depending on how
> strict your pipeline is. This is the single most reliable way to break an FPL
> data pipeline, and it happens on a schedule.
>
> `clubs_golden_record.csv` here now includes **Coventry City** and **Hull City**
> for 2026-27. If you are reading this in a later season, run
> `update_golden_records.py` before trusting it, and assert that every club in
> the current FPL bootstrap has a row.

## players_golden_record.csv

| Column | Description |
|---|---|
| `fpl_code` | Stable FPL player identifier (persists across seasons) |
| `fpl_player_name` | FPL web name |
| `fpl_first_name` | FPL first name |
| `fpl_second_name` | FPL surname |
| `fpl_position` | Position code: GKP, DEF, MID, FWD |
| `understat_player_id` | Understat player ID (empty if unmapped) |
| `understat_first_name` | Understat first name |
| `understat_second_name` | Understat surname |
| `understat_web_name` | Understat display name |
| `confidence_level` | `HIGH` (confirmed match), `MEDIUM` (ID from ChrisMusson but player not in current Understat season), `NONE` (no Understat ID found) |

## clubs_golden_record.csv

| Column | Description |
|---|---|
| `club_name` | FPL club name (e.g. "Man City") |
| `club_short` | FPL short code (e.g. "MCI") |
| `fpl_team_code` | FPL team code |
| `understat_name` | Understat team name (e.g. "Manchester City") |
| `understat_team_id` | Understat team ID |

## update_golden_records.py

Cross-references three data sources to keep mappings current:

1. **[ChrisMusson/FPL-ID-Map](https://github.com/ChrisMusson/FPL-ID-Map)** — community-maintained FPL code ↔ Understat ID CSV
2. **FPL bootstrap-static API** — current-season players and teams
3. **Understat league API** — player names/teams for current + previous season

### What It Does

- Adds new players that appear in FPL but not yet in the golden record
- Backfills missing `understat_player_id` for existing players when ChrisMusson's map gets updated
- Backfills missing Understat names for players that already have an ID
- Adds newly promoted clubs
- Handles FPL → Understat name mismatches (e.g. "Nott'm Forest" → "Nottingham Forest")

### Usage

```bash
python update_golden_records.py                    # auto-detect current season
python update_golden_records.py --season 2025       # override Understat season
python update_golden_records.py --dry-run            # preview changes without writing
```

### When to Run

Run before `update_smartplay_data.py` so that new player/club mappings are available when appending new gameweek data. Recommended: once per gameweek, or whenever the transfer window is active (new signings).
