# SmartPlayFPL Data

Training and evaluation dataset for both openfpl_model and smartplay_model.

## Files

| File | Size | Description |
|---|---|---|
| `smartplay_data.csv` | 88 MB (Git LFS) | Historical player-fixture data, 2020-21 through 2025-26 |
| `understat_team_matches.csv` | ~400 KB | Cached Understat team match data (auto-generated on first model run) |
| `update_smartplay_data.py` | Script | Incremental updater — appends new GWs from FPL API + Understat |

## smartplay_data.csv

Each row represents **one player in one fixture**. The dataset contains ~115 columns across 6 seasons.

### Column Reference

| Group | Columns | Source |
|---|---|---|
| **Identity** | `season`, `gameweek`, `fpl_code`, `understat_id`, `element`, `player_name`, `team_name`, `position` | FPL API |
| **Match context** | `is_home`, `match_date`, `us_opponent`, `fixture`, `opponent_team`, `kickoff_time` | FPL API |
| **FPL actuals** | `total_points`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `goals_conceded`, `own_goals`, `penalties_saved`, `penalties_missed`, `yellow_cards`, `red_cards`, `saves`, `bonus`, `bps`, `starts` | FPL API |
| **FPL expected** | `expected_goals`, `expected_assists`, `expected_goal_involvements`, `expected_goals_conceded`, `xP` | FPL API |
| **FPL ICT** | `ict_index`, `influence`, `creativity`, `threat` | FPL API |
| **FPL market** | `value`, `selected`, `transfers_in`, `transfers_out`, `transfers_balance` | FPL API |
| **FPL predicted** | `expected_points_pre_deadline`, `expected_points`, `expected_points_source` | FPL API / vaastav |
| **FPL cache** | `cache_price`, `cache_ownership_pct`, `cache_transfers_in`, `cache_transfers_out`, `cache_form`, `cache_status`, `cache_chance_next_round`, `cache_snapshot_datetime_utc` | Pipeline snapshot |
| **Understat player** | `us_match_id`, `us_position`, `us_minutes`, `us_goals`, `us_assists`, `us_shots`, `us_key_passes`, `us_xG`, `us_xA`, `us_npg`, `us_npxG`, `us_xGChain`, `us_xGBuildup` | Understat API |
| **Understat team (match)** | `us_team_xG`, `us_team_xGA`, `us_team_npxGD`, `us_ppda`, `us_opp_ppda`, `us_deep`, `us_deep_allowed` | Understat API |
| **Understat team (season)** | `us_team_name`, `team_xG_avg`, `team_xGA_avg`, `team_npxG_avg`, `team_npxGA_avg`, `team_deep_avg`, `team_deep_allowed_avg`, `team_goals_season`, `team_conceded_season`, `team_ppda_avg`, `team_ppda_allowed_avg` | Understat API |
| **Match scores** | `team_a_score`, `team_h_score` | FPL API |
| **Manager stats** | `mng_clean_sheets`, `mng_draw`, `mng_goals_scored`, `mng_loss`, `mng_underdog_draw`, `mng_underdog_win`, `mng_win` | FPL API |
| **Derived per-90** | `us_xG_per90`, `us_xA_per90`, `us_npxG_per90`, `us_shots_per90`, `us_key_passes_per90`, `us_xGChain_per90`, `us_xGBuildup_per90` | Computed |
| **Other derived** | `team_xGD_avg`, `points_per_million`, `goals_vs_xG`, `assists_vs_xA` | Computed |

### Key Identifiers

- **`fpl_code`** — stable FPL player ID (persists across seasons)
- **`element`** — FPL's within-season player ID (changes each season)
- **`understat_id`** — Understat player ID (mapped via `mappings/players_golden_record.csv`)
- **`fixture`** — FPL's fixture ID

### Deduplication Key

Each row is unique on `(season, fixture, fpl_code)`.

## update_smartplay_data.py

Incrementally appends missing gameweeks to `smartplay_data.csv`.

### How It Works

1. Reads existing CSV to find which `(season, gameweek)` pairs already exist
2. Calls FPL `bootstrap-static` API to find which GWs are finished
3. Computes the difference → missing GWs
4. For each missing GW: calls `element-summary/{id}/` for every player (~800 API calls with 0.35s rate limiting)
5. Enriches rows with Understat team match data (xG, xGA, deep, ppda) and season-level aggregates
6. Deduplicates on `(season, fixture, fpl_code)` and appends to CSV

### Usage

```bash
python update_smartplay_data.py                     # auto-detect and append missing GWs
python update_smartplay_data.py --dry-run            # preview what would be added
python update_smartplay_data.py --season 2025-26     # only update this season
python update_smartplay_data.py -o output.csv        # write to different file
```

### Limitations

- **Understat player-level data** (`us_xG`, `us_xA`, etc.) is set to NaN for newly appended rows. The updater only fetches team-level Understat data. Player-level Understat data requires the full pipeline.
- **Manager stats** (`mng_*`) and **defensive stats** (`clearances_blocks_interceptions`, etc.) are NaN — these come from a separate data source not available via the public FPL API.
- **`xP`** is NaN for new rows — this comes from vaastav's FPL dataset, not the live API.
- **Rate limiting**: fetching all players takes ~5 minutes due to 0.35s sleep between API calls.

## understat_team_matches.csv

Auto-generated cache of Understat team match data. Created by `openfpl_model`'s `build_understat_team_matches()` on first run. Contains per-team per-match: xG, xGA, scored, missed, deep, deep_allowed, ppda_att, ppda_def, ppda_allowed_att, ppda_allowed_def, pts, league rank.

Delete this file to force a fresh fetch from the Understat API.
