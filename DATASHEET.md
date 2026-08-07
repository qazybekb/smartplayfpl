# Datasheet for SmartPlayFPL Dataset

_Following the framework proposed by [Gebru et al. (2021)](https://doi.org/10.1145/3458723), "Datasheets for Datasets," Communications of the ACM, 64(12), 86–92._

---

## Motivation

**1. For what purpose was the dataset created?**

The dataset was created to train and evaluate machine learning models that predict Fantasy Premier League (FPL) player points per fixture. The specific gap it fills is merging two public but separate data sources — the official FPL API and Understat's advanced football statistics — into a single, model-ready table with consistent player/club identifiers across seasons.

**2. Who created the dataset and on behalf of which entity?**

The dataset was created by the SmartPlay team as part of the SmartPlayFPL project.

**3. Who funded the creation of the dataset?**

The dataset was self-funded. No grants or external funding were involved.

**4. Any other comments?**

The feature engineering builds on [OpenFPL](https://github.com/daniegr/OpenFPL) by Daniel Groos (Groos Analytics). SmartPlay adds 16 additional features (availability rolling stats, market data, venue/rank interactions) on top of OpenFPL's 235-column base.

---

## Composition

**5. What do the instances that comprise the dataset represent?**

Each instance is one player in one Premier League fixture — a single player-fixture pair. A player who appears in gameweek 10 of the 2023-24 season has one row regardless of whether they played 90 minutes or 0 minutes.

**6. How many instances are there in total?**

151,498 rows across six seasons (2020-21 through 2025-26, up to GW24 of the season 2025-26).

**7. Does the dataset contain all possible instances or is it a sample from a larger set?**

The dataset aims to contain all FPL-registered players for every fixture in the covered seasons. It is not a sample — it is a census of every player-fixture combination where FPL recorded data. However, it may exclude players who were registered but had no FPL data (e.g., unsigned youth players).

**8. What data does each instance consist of?**

Each instance consists of 115 columns grouped into:

| Column group | Count | Examples |
|---|---|---|
| Identity | 8 | `season`, `gameweek`, `fpl_code`, `player_name`, `team_name`, `position` |
| Match context | 6 | `is_home`, `match_date`, `opponent_team`, `fixture` |
| FPL actuals | 15 | `total_points`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `bonus` |
| FPL expected | 5 | `expected_goals`, `expected_assists`, `expected_goal_involvements`, `xP` |
| FPL ICT index | 4 | `ict_index`, `influence`, `creativity`, `threat` |
| FPL market data | 5 | `value`, `selected`, `transfers_in`, `transfers_out` |
| FPL projections (see Q13 — mixed provenance) | 3 | `expected_points_pre_deadline`, `expected_points`, `expected_points_source` |
| Pipeline snapshot | 8 | `cache_price`, `cache_ownership_pct`, `cache_form`, `cache_status` |
| Understat player | 13 | `us_xG`, `us_xA`, `us_npxG`, `us_shots`, `us_key_passes`, `us_xGChain` |
| Understat team match | 7 | `us_team_xG`, `us_team_xGA`, `us_ppda`, `us_deep` |
| Understat team season | 10 | `team_xG_avg`, `team_xGA_avg`, `team_ppda_avg` |
| Derived per-90 | 7 | `us_xG_per90`, `us_xA_per90`, `us_shots_per90` |
| Other derived | 4 | `points_per_million`, `goals_vs_xG`, `assists_vs_xA` |
| Match scores | 2 | `team_a_score`, `team_h_score` |
| Manager stats | 7 | `mng_win`, `mng_loss`, `mng_clean_sheets` |
| Defensive stats | 4 | `clearances_blocks_interceptions`, `recoveries`, `tackles` |
| Metadata | 5 | `name`, `team`, `was_home`, `GW`, `modified` |

All data is numeric or categorical (text labels). There are no images, audio, or free-text fields.

**9. Is there a label or target associated with each instance?**

Yes. The primary prediction target is `total_points` — the FPL points a player scored in that fixture. Secondary targets include `minutes` (for starting probability models) and the four outcome buckets used by SmartPlay v9 (Zeros/Blanks/Tickers/Haulers, derived from `total_points`).

**10. Is any information missing from individual instances?**

Yes. Several columns have systematic NaN values:
- **Understat player data** (`us_xG`, `us_xA`, etc.) is NaN for players without an Understat mapping (~5% of players, typically fringe squad members).
- **Pipeline snapshot columns** (`cache_*`) are only populated for the current season's active pipeline runs.
- **Manager and defensive stats** (`mng_*`, `clearances_blocks_interceptions`, etc.) are NaN for rows added via the incremental updater (they require the full pipeline).
- **`xP`** is NaN for incrementally updated rows (sourced from the vaastav FPL dataset).

These gaps are documented and handled by the models via NaN-aware XGBoost.

**11. Are relationships between individual instances made explicit?**

Partially. The `fixture` column groups two instances (home team player + away team player) into the same match. The `fpl_code` column links the same player across seasons and fixtures. The `team_name` and `opponent_team` columns encode the adversarial relationship. However, within-team relationships (e.g., which players are on the same squad) are not explicit — they must be inferred from shared `team_name` and `gameweek`.

**12. Are there recommended data splits?**

Yes. The dataset is designed for temporal cross-validation: train on earlier seasons, test on a later season the model has never seen. The recommended splits are:

| Split | Train | Test |
|---|---|---|
| CV1 | 2020-21 to 2022-23 | 2023-24 |
| CV2 | 2020-21 to 2023-24 | 2024-25 |
| CV3 | 2020-21 to 2024-25 | 2025-26 |

Evaluation metrics are Spearman correlation (ranking quality) and MAE (point prediction accuracy), computed per gameweek on starters only (players with `minutes >= 60`).

**13. Are there any errors, sources of noise, or redundancies in the data?**

- **Understat-FPL matching noise:** Player-to-Understat mappings are maintained in `data/mappings/players_golden_record.csv` with a `confidence_level` field (HIGH/MEDIUM/NONE). ~5% of mappings are MEDIUM or NONE confidence, which may cause misattribution of xG/xA stats.
- **Double gameweeks:** Players who play two fixtures in one gameweek have two separate rows. Models must handle this correctly.
- **Column redundancy:** Some columns are near-duplicates kept for compatibility (e.g., `is_home` vs `was_home`, `gameweek` vs `GW`, `team_name` vs `team`, `player_name` vs `name`).
- **Promoted team distribution shift:** Newly promoted teams have no historical Understat season-level stats in their first season, causing NaN in `team_xG_avg` etc. for early gameweeks.
- **`expected_points` mixes incompatible sources.** This column is FPL's own projection and is the natural baseline to benchmark a model against, which makes the following a trap rather than a footnote. It is assembled from three regimes recorded in `expected_points_source`: `fplcache_ep_next` (read from the FPL API by our pipeline), `vaastav_xP` (mirrored from a third-party archive), and `imputed_0` (a placeholder, not a projection). The two real sources measure very differently. In 2024-25 only GW20-24 use `fplcache_ep_next` while the surrounding gameweeks use `vaastav_xP`; scoring each gameweek's projection against actual points for players who started (60+ minutes) gives a mean Spearman of **0.512** on the `vaastav_xP` gameweeks and **0.217** on the `fplcache_ep_next` ones — same season, same players, consecutive weeks. We have not established which represents a genuine pre-deadline projection; the likely cause is a difference in capture time relative to the deadline, and the mirror's capture time cannot be verified. Segment by `expected_points_source` before scoring, and never compare a model measured on one source against a baseline measured on the other. Two related hazards: 2025-26 GW25 stores a single constant value for every player, so rank correlation is `NaN` and one such gameweek will poison a season-wide average; and a genuine `0.0` is a real projection for a player FPL does not expect to feature, so exclude `imputed_0` by source rather than by dropping zeros.

**14. Is the dataset self-contained, or does it link to or otherwise rely on external resources?**

The CSV file is self-contained for training and evaluation. However, to update the dataset with new gameweeks, the following external resources are required:
- **FPL API** (`fantasy.premierleague.com`) — public, no authentication required
- **Understat API** (via `understatapi` Python package) — public, no authentication required
- **ChrisMusson/FPL-ID-Map** (GitHub) — public CSV mapping FPL to Understat player IDs

There are no guarantees these external resources will remain available indefinitely.

**15. Does the dataset contain data that might be considered confidential?**

No. All data is derived from publicly available APIs. Player names and statistics are public information published by the Premier League and Understat.

**16. Does the dataset contain data that, if viewed directly, might be offensive, insulting, threatening, or might otherwise cause anxiety?**

No. The dataset contains only football statistics and player metadata.

**17. Does the dataset identify any subpopulations?**

Yes. Players are identified by `position` (GK, DEF, MID, FWD) and `team_name`. The models are trained per-position. No demographic subpopulations (age, nationality, ethnicity) are included in the dataset, though player names could be used to infer some demographic attributes.

**18. Is it possible to identify individuals from the dataset?**

Yes. The dataset contains `player_name` and `fpl_code` which directly identify professional footballers. However, these are public figures whose performance statistics are publicly available. No private individuals are included.

**19. Does the dataset contain data that might be considered sensitive?**

No. The dataset contains only professional performance statistics that are already publicly available.

**20. Any other comments?**

None.

---

## Collection Process

**21. How was the data associated with each instance acquired?**

The data was acquired programmatically from two public APIs:
- **FPL API** (`https://fantasy.premierleague.com/api/`): Player identity, match results, points, market data, ICT index, expected stats.
- **Understat API** (via the `understatapi` Python package): Player-level xG, xA, shot data, and team-level match statistics (xG, xGA, PPDA, deep completions).

Both APIs return structured JSON. The data was directly observable (actual match results, not survey responses or inferred values).

**22. What mechanisms or procedures were used to collect the data?**

Custom Python scripts make API calls, parse JSON responses, and merge the two sources using player/club ID mappings. The key scripts are:
- `data/update_smartplay_data.py` — fetches FPL API data and appends new gameweeks
- `data/mappings/update_golden_records.py` — updates FPL-to-Understat ID mappings

Rate limiting is applied (0.35 seconds between FPL API calls) to avoid overloading the public APIs.

**23. If the dataset is a sample from a larger set, what was the sampling strategy?**

Not applicable — the dataset is a census, not a sample.

**24. Who was involved in the data collection process and how were they compensated?**

Data collection was fully automated via scripts. No crowdworkers or manual annotators were involved.

**25. Over what timeframe was the data collected?**

The dataset covers six Premier League seasons: 2020-21, 2021-22, 2022-23, 2023-24, 2024-25, and 2025-26 (up to GW24). Data is collected after each gameweek's matches are completed (typically within 24 hours of the last match).

**26. Were any ethical review processes conducted?**

No formal ethical review was conducted. The dataset uses only publicly available sports statistics from official APIs. No private or sensitive data is collected.

**27. Did you collect the data from the individuals in question directly, or obtain it via third parties or other sources?**

The data was obtained via third-party APIs:
- FPL API (operated by the Premier League)
- Understat (independent football analytics platform)
- ChrisMusson/FPL-ID-Map (open-source GitHub repository for ID mappings)

No data was collected directly from the football players themselves.

**28. Were the individuals in question notified about the data collection?**

Not applicable. The individuals are professional footballers whose performance statistics are published by the Premier League as part of their public-facing Fantasy Premier League game. The data is inherently public.

**29. Did the individuals in question consent to the collection and use of their data?**

Professional footballers' performance statistics are published by the Premier League under its own terms. SmartPlay accesses this data through the publicly available FPL API. No additional consent was sought.

**30. If consent was obtained, were the consenting individuals provided a mechanism to revoke their consent in the future or for certain uses?**

Not applicable — see above.

**31. Has an analysis of the potential impact of the dataset and its use on data subjects been conducted?**

No formal impact analysis was conducted. The data subjects are professional athletes whose statistics are already widely published and analysed by media, fans, and commercial services.

**32. Any other comments?**

None.

---

## Preprocessing/Cleaning/Labelling

**33. Was any preprocessing/cleaning/labelling of the data done?**

Yes. The following preprocessing steps are applied:
1. **ID mapping:** FPL player codes are mapped to Understat player IDs using `players_golden_record.csv`. Unmatched players retain FPL data but have NaN Understat columns.
2. **Club name normalisation:** FPL and Understat use different club names (e.g., "Man City" vs "Manchester City"). These are harmonised via `clubs_golden_record.csv`.
3. **Position mapping:** FPL uses `GKP` for goalkeepers; this is mapped to `GK` for consistency with Understat and OpenFPL conventions.
4. **Deduplication:** Rows are keyed on `(season, fixture, fpl_code)` to prevent duplicates.
5. **Per-90 derivation:** Understat stats are normalised to per-90-minute rates (e.g., `us_xG_per90 = us_xG / (us_minutes / 90)`).
6. **Team season aggregates:** Rolling team-level averages (`team_xG_avg`, `team_xGA_avg`, etc.) are computed from Understat match data.
7. **Derived metrics:** `points_per_million`, `goals_vs_xG` (goals - xG), and `assists_vs_xA` (assists - xA) are computed from raw columns.

**34. Was the "raw" data saved in addition to the preprocessed/cleaned/labelled data?**

No. The raw API responses are not saved. However, the preprocessing is deterministic and can be reproduced by re-running the collection scripts against the same API endpoints (subject to API availability).

**35. Is the software that was used to preprocess/clean/label the data available?**

Yes. All preprocessing code is included in this repository:
- `data/update_smartplay_data.py` — collection and preprocessing
- `data/mappings/update_golden_records.py` — ID mapping maintenance
- `models/openfpl_model/feature_engineering.py` — rolling feature computation (used at model inference time, not baked into the CSV)

**36. Any other comments?**

The CSV contains pre-computed features up to the point of collection. Additional rolling features (player rolling averages, league ranks, team rolling stats) are computed at inference time by the model runners, using a `shift(1)` convention to prevent data leakage. These rolling features are not stored in the CSV.

---

## Uses

**37. Has the dataset been used for any tasks already?**

Yes. The dataset is used to train and evaluate two FPL prediction models:
- **SmartPlay v9** — multi-bucket mixture XGBoost (28 models: 4 positions x 7 model types). Achieves 0.730 Spearman correlation on 2025-26 starters.
- **OpenFPL** — ensemble XGBoost reimplementation (~200 models). Achieves 0.696 Spearman correlation on the same test set.

Both models are included in this repository with pre-trained weights and evaluation scripts.

**38. Is there a repository that links to any or all papers or systems that use this dataset?**

This repository itself. The OpenFPL model is based on the research described in [Groos, D. (2025). "OpenFPL: A Comprehensive Open-Source Framework for FPL Prediction." arXiv:2508.09992](https://arxiv.org/abs/2508.09992).

**39. What (other) tasks could the dataset be used for?**

- **Player valuation modelling:** Predicting FPL price changes from `transfers_in`, `transfers_out`, and performance data.
- **Starting XI prediction:** Using `minutes`, `cache_status`, and `cache_chance_next_round` to predict which players will start.
- **Team strength estimation:** Using Understat team-level metrics for Elo-style team rating systems.
- **Fixture difficulty modelling:** Analysing `us_team_xGA`, `us_ppda`, and opponent strength to estimate fixture difficulty.
- **Academic research:** Benchmarking time-series prediction methods on a well-structured sports dataset.

**40. Is there anything about the composition of the dataset or the way it was collected and preprocessed/cleaned/labelled that might impact future uses?**

- **Premier League only:** The dataset covers only the English Premier League. Models trained on this data may not transfer to other leagues.
- **Promoted/relegated teams:** Teams that get promoted or relegated create distribution shifts. Newly promoted teams have no historical Understat averages.
- **API dependency for updates:** Keeping the dataset current requires the FPL and Understat APIs to remain available and maintain their current schemas.
- **Understat coverage gaps:** ~5% of players lack Understat mappings. Models should handle NaN Understat features gracefully.
- **Evaluation convention:** Published metrics are computed on starters only (`minutes >= 60`), excluding bench cameos. This is a methodological choice that affects reported accuracy.

**41. Are there tasks for which the dataset should not be used?**

- **Gambling or betting:** This dataset should not be used to build systems optimised for sports betting markets. See the project's [Ethics page](https://smartplayfpl.com/ethics).
- **Player evaluation for real-world decisions:** The data reflects Fantasy Premier League scoring, not real-world football performance. FPL points are an imperfect proxy for actual player quality.
- **Demographic inference:** While player names are included, the dataset should not be used to infer or predict demographic attributes.

**42. Any other comments?**

None.

---

## Distribution

**43. Will the dataset be distributed to third parties outside of the entity on behalf of which the dataset was created?**

Yes. The dataset is publicly available in this GitHub repository.

**44. How will the dataset be distributed?**

The dataset is distributed as a CSV file (`smartplay_data.csv`, 88 MB) tracked with Git LFS in a public GitHub repository. Pre-trained model weights and inference code are distributed alongside it.

**45. When will the dataset be released/first distributed?**

February 2026.

**46. Will the dataset be distributed under a copyright or other intellectual property (IP) licence, and/or under applicable terms of use (ToU)?**

Yes. The dataset is distributed under the **[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)** licence. This permits sharing and adaptation for non-commercial purposes with attribution. Commercial use is prohibited.

**47. Have any third parties imposed IP-based or other restrictions on the data associated with the instances?**

The underlying data originates from:
- **FPL API** — publicly available, but the Premier League retains IP rights over the data. Users should review the [FPL Terms of Service](https://fantasy.premierleague.com/).
- **Understat** — publicly available football statistics.
- **ChrisMusson/FPL-ID-Map** — open-source (MIT licence).

**48. Do any export controls or other regulatory restrictions apply to the dataset or to individual instances?**

No.

**49. Any other comments?**

None.

---

## Maintenance

**50. Who will be supporting/hosting/maintaining the dataset?**

The SmartPlay team. Contact: [hello@smartplayfpl.com](mailto:hello@smartplayfpl.com).

**51. How can the owner/curator/manager of the dataset be contacted?**

Email: [hello@smartplayfpl.com](mailto:hello@smartplayfpl.com)

**52. Is there an erratum?**

Not at the time of initial release. Errata will be documented in this repository's issue tracker.

**53. Will the dataset be updated?**

Yes. New gameweeks are appended throughout the active Premier League season (typically August to May). Updates can be performed by users themselves using the included scripts:
```bash
python data/update_smartplay_data.py
```

**54. If the dataset relates to people, are there applicable limits on the retention of the data associated with the instances?**

The data relates to professional athletes' public performance statistics. No specific retention limits apply as the data is already in the public domain.

**55. Will older versions of the dataset continue to be supported/hosted/maintained?**

Older versions may be available via Git history. There is no formal versioning policy beyond Git commits.

**56. If others want to extend/augment/build on/contribute to the dataset, is there a mechanism for them to do so?**

Yes. The repository includes scripts for extending the dataset:
- `data/update_smartplay_data.py` — append new gameweeks
- `data/mappings/update_golden_records.py` — add new player/club mappings

Contributions can be submitted via pull requests. The maintainers will review submissions for data quality and consistency.

**57. Any other comments?**

None.

---

_Datasheet created: February 2026._
_Reference: Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J.W., Wallach, H., Daume III, H., & Crawford, K. (2021). Datasheets for Datasets. Communications of the ACM, 64(12), 86–92._
