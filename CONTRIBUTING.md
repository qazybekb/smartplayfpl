# Contributing

Corrections are more welcome than features. This is a dataset and a model — the
useful contributions are the ones that make them more correct.

## Before opening a PR

```bash
git lfs pull          # the dataset is stored in LFS
pip install pandas
python validate.py    # must pass
```

`validate.py` checks the things that have actually broken before: unmapped
players after a transfer window, missing promoted clubs, duplicate dataset
keys, unknown `expected_points_source` values, and seasons that stop short of
GW38. CI runs it on every change to `data/` and again every Monday, because
mappings rot on the calendar rather than on commits.

## Especially useful

- **Player mapping fixes.** `data/mappings/players_golden_record.csv` carries a
  `confidence_level`; anything `MEDIUM`, `LOW` or `NONE` is a guess or a gap.
  Correcting one to `HIGH` with the right Understat id is a real improvement.
- **Data errors.** A wrong value in `smartplay_data.csv` is worth an issue even
  if you cannot fix it. Say which `(season, fixture, fpl_code)` and what you
  expected.
- **Reproduction failures.** If `python -m smartplay_model.run --model v12`
  does not give you what the evaluation claims, that is a bug and we want to
  know.

## What this repo is not

It is not trying to be the best FPL *dataset*. Two projects already do that
better than we would:
[vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)
for canonical history and
[olbauday/FPL-Core-Insights](https://github.com/olbauday/FPL-Core-Insights) for
current coverage with Elo, cups and twice-daily updates. Use those for data.

What is scarce is a published, runnable points model with an honest account of
where it fails. That is what this repo is for, so contributions that sharpen
the model, the evaluation, or the documented failure modes land best.

## Licence

CC BY-NC 4.0. By contributing you agree your work ships under the same terms.
