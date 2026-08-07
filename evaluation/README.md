# Evaluation

Published accuracy numbers for the SmartPlay model, so the claims on the
website can be checked rather than taken on trust.

## `v12_walk_forward_accuracy.json`

Per-gameweek metrics from four leakage-controlled walk-forward windows over
2025-26: **25,234 player-gameweeks across 32 gameweeks**. Each fold trains only
on data available before its test window, so no test result reaches its own
features or training labels.

| Field | Meaning |
|---|---|
| `summary.v12`, `summary.v11` | Mean of the per-gameweek metrics for each model |
| `pairedDeltas` | Paired per-gameweek differences with 95% bootstrap intervals |
| `rows` | Every evaluated gameweek, both models, so you can recompute the summary |
| `folds` | Which gameweeks belong to which fold, and the row count of each |

Folds cover GW1-8, GW15-22, GW23-30 and GW31-38. GW9-14 were not part of the
published selection suite and are not included.

### Reading it without being misled

**The decision score is `0.5 × Spearman + 0.5 × NDCG@10`**, computed within a
gameweek and then averaged unweighted across gameweeks. MAE is not in it.

**Spearman did not improve** between v11 and v12 — the bootstrap interval on
that delta includes zero, which is why `pairedDeltas.spearman.bootstrap95Ci`
straddles it. Any summary claiming a broad accuracy jump is overreading this
file.

**MAE is computed over the full player pool.** About 61% of rows are players
with zero minutes, and predicting zero for them is easy, so the pooled MAE of
0.979 is much lower than the model's error on players who actually featured.
Restricted to 60+ minute starters, the same projections give MAE ≈ 2.35 and
Spearman ≈ 0.14. Neither number is wrong; they measure different populations,
and comparing one model on one population against another model on the other
is the most common way to get this wrong.

## Benchmarking against FPL's own projection

If you want to compare a model against the `ep_next` figure the FPL API
publishes, read the `expected_points` warning in
[`../data/README.md`](../data/README.md) first. That column mixes sources that
are not interchangeable, and pooling them produces a benchmark that is wrong in
a way that is easy to miss.
