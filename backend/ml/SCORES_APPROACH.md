# FPL Score-Based Ranking System

## Overview

This document describes a **score-based ranking system** for Fantasy Premier League (FPL) decision-making. Instead of predicting exact points (which is unreliable with ~2+ MAE error), this approach **ranks players on predictable factors** that correlate with performance.

---

## Why This Approach?

### The Problem with Points Prediction

| Issue | Evidence |
|-------|----------|
| **Low accuracy** | Best models achieve ~2.0 MAE (theoretical limit ~1.96) |
| **Negative R²** | Many models explain 0% of variance |
| **Hauls unpredictable** | Even best models have ~4.3 MAE on 10+ point returns |
| **False precision** | "5.2 vs 5.1 expected points" is meaningless noise |

### The Score-Based Alternative

| Advantage | Explanation |
|-----------|-------------|
| **Focuses on predictable factors** | Fixtures, form, playing time are knowable |
| **Transparent** | User sees WHY a player ranks high |
| **Actionable** | Score 38 vs 25 = clear decision |
| **No overfitting** | Simple rules, not trained on noisy outcomes |
| **Robust** | Less likely to break with new data |

---

## The Core Formula

```
TOTAL SCORE = Fixture Score + Form Score + Nailedness Score + Value Score + Ceiling Score
```

Each factor is scored **0-10**, then weighted and summed.

---

## Factor 1: Fixture Score (0-10)

### Basic Version (Using FDR)

| FDR | Score | Meaning |
|-----|-------|---------|
| 1 | 10 | Very easy fixture |
| 2 | 8 | Easy fixture |
| 3 | 5 | Medium fixture |
| 4 | 2 | Hard fixture |
| 5 | 0 | Very hard fixture |

**Bonus:** +1 if home game

### Advanced Version (Using Team Strength)

Replace crude FDR with calculated team strength:

```python
# Calculate from season data
team_attack_strength = team_xG / league_avg_xG
team_defense_weakness = team_xGA / league_avg_xGA

# For attackers (FWD, MID): care about opponent's defense weakness
attacker_fixture_score = opponent_defense_weakness * 5
# Scale: 0.6 weakness = 3, 1.0 = 5, 1.5 = 7.5

# For defenders (DEF, GKP): care about opponent's attack strength
defender_fixture_score = (2 - opponent_attack_strength) * 5
# Scale: 1.8 attack = 1, 1.0 = 5, 0.6 = 7

# Home bonus
fixture_score += 1 if is_home else 0

# Cap at 0-10
fixture_score = max(0, min(10, fixture_score))
```

### Example Calculations

| Player | Position | Opponent | Opp Defense Weakness | Opp Attack Strength | Home? | Score |
|--------|----------|----------|---------------------|---------------------|-------|-------|
| Salah | MID | Ipswich | 1.4 | - | Yes | 1.4×5 + 1 = **8** |
| Salah | MID | Man City | 0.7 | - | No | 0.7×5 = **3.5** |
| TAA | DEF | Ipswich | - | 0.6 | Yes | (2-0.6)×5 + 1 = **8** |
| TAA | DEF | Man City | - | 1.8 | No | (2-1.8)×5 = **1** |

---

## Factor 2: Form Score (0-10)

### Basic Version (Points-Based)

```python
avg_points_last_5 = sum(points_last_5_gws) / 5

form_score = min(10, avg_points_last_5 * 1.5)
# 0 pts/game = 0, 4 pts/game = 6, 7+ pts/game = 10
```

### Advanced Version (xG/xA-Based)

Using underlying stats is more predictive than actual points:

```python
# Expected goal involvement per 90 minutes
xGI_per_90 = (xG + xA) / (minutes / 90)

# Scale to 0-10
form_score = min(10, xGI_per_90 * 10)
# 0.0 xGI/90 = 0, 0.5 xGI/90 = 5, 1.0+ xGI/90 = 10
```

### Why xG/xA is Better

| Player | Points Form | xG Form | Reality |
|--------|-------------|---------|---------|
| Lucky striker (1 goal from 0.2 xG) | High (7) | Low (2) | Will regress down |
| Unlucky striker (0 goals from 0.8 xG) | Low (2) | High (8) | Due to score |

**xG captures quality of chances, not lucky/unlucky outcomes.**

---

## Factor 3: Nailedness Score (0-10)

Uses the **Playing Time Prediction Model** (94% AUC).

```python
probability_starts = playing_time_model.predict(player_features)

if probability_starts >= 0.95:
    nailedness_score = 10
elif probability_starts >= 0.85:
    nailedness_score = 8
elif probability_starts >= 0.70:
    nailedness_score = 6
elif probability_starts >= 0.50:
    nailedness_score = 4
elif probability_starts >= 0.30:
    nailedness_score = 2
else:
    nailedness_score = 0
```

### Rotation Risk Adjustments

```python
# Additional factors that increase rotation risk
rotation_risk = 0

if cup_game_in_next_3_days:
    rotation_risk += 0.15
if played_90_mins_last_3_games:
    rotation_risk += 0.10
if fixture_congestion:  # 3+ games in 8 days
    rotation_risk += 0.15
if manager_known_for_rotation:  # e.g., Pep, Slot
    rotation_risk += 0.10
if just_returned_from_injury:
    rotation_risk += 0.15

# Adjust nailedness
nailedness_score = nailedness_score * (1 - rotation_risk)
```

---

## Factor 4: Value Score (0-10)

Measures **efficiency** - points per million spent.

```python
# Season points per million
points_per_million = total_season_points / (price / 10)

# Scale to 0-10 (typical range: 10-30 pts/£m)
value_score = min(10, (points_per_million - 10) / 2)
# 10 pts/£m = 0, 20 pts/£m = 5, 30+ pts/£m = 10
```

### Alternative: xGI per Million

```python
xGI_per_million = total_xGI / (price / 10)
value_score = min(10, xGI_per_million * 5)
```

---

## Factor 5: Ceiling Score (0-10) - For Captain Selection

Measures **upside potential** for big hauls.

```python
ceiling_score = 0

# Position base (attackers have higher ceiling)
if position == 'FWD':
    ceiling_score += 4
elif position == 'MID':
    ceiling_score += 3
elif position == 'DEF':
    ceiling_score += 1.5
else:  # GKP
    ceiling_score += 0.5

# Penalty taker
if is_penalty_taker:
    ceiling_score += 2

# Set piece taker (corners, free kicks)
if takes_set_pieces:
    ceiling_score += 1

# Recent haul history
if scored_10plus_in_last_5_gws:
    ceiling_score += 1.5

# Easy fixture bonus
if fixture_score >= 7:
    ceiling_score += 1.5

ceiling_score = min(10, ceiling_score)
```

---

## Position-Specific Weights

Different positions have different scoring patterns:

| Position | Fixture | Form | Nailedness | Value | Ceiling |
|----------|---------|------|------------|-------|---------|
| **GKP** | 1.5 | 0.5 | 2.0 | 1.0 | 0.5 |
| **DEF** | 1.5 | 1.0 | 1.5 | 1.0 | 0.8 |
| **MID** | 1.2 | 1.5 | 1.2 | 1.0 | 1.2 |
| **FWD** | 1.0 | 1.5 | 1.2 | 0.8 | 1.5 |

```python
def calculate_total_score(player):
    weights = POSITION_WEIGHTS[player.position]

    total = (
        fixture_score * weights['fixture'] +
        form_score * weights['form'] +
        nailedness_score * weights['nailedness'] +
        value_score * weights['value'] +
        ceiling_score * weights['ceiling']
    )

    return total
```

---

## Application to FPL Goals

### Goal 1: Best Squad Selection

**Objective:** Pick 15 players within £100m budget.

```python
def select_best_squad(all_players, budget=100.0):
    # Score all players (use 5-week fixture horizon)
    for player in all_players:
        player.squad_score = calculate_score(
            player,
            fixture_horizon=5,  # Next 5 GWs
            include_ceiling=False  # Not needed for squad
        )

    # Optimization: maximize total squad score within constraints
    # Constraints:
    #   - Budget: £100m
    #   - Positions: 2 GKP, 5 DEF, 5 MID, 3 FWD
    #   - Max 3 players per team

    return optimize_squad(all_players, budget, constraints)
```

### Goal 2: Starting XI Selection

**Objective:** Pick best 11 from your 15-player squad.

```python
def select_starting_xi(squad, gameweek):
    # Score squad players for THIS week only
    for player in squad:
        player.weekly_score = calculate_score(
            player,
            fixture_horizon=1,  # This GW only
            include_ceiling=False
        )

    # Sort by score
    ranked = sorted(squad, key=lambda p: p.weekly_score, reverse=True)

    # Pick valid formation (min 1 GKP, 3 DEF, 2 MID, 1 FWD)
    starting_xi = select_valid_formation(ranked)
    bench = [p for p in squad if p not in starting_xi]

    return starting_xi, bench
```

### Goal 3: Transfer Recommendations

**Objective:** Suggest transfers that improve squad.

```python
def recommend_transfers(squad, all_players, free_transfers=1):
    recommendations = []

    for owned_player in squad:
        # Score over next 3 GWs
        owned_score = calculate_score(owned_player, fixture_horizon=3)

        # Find better alternatives
        alternatives = [
            p for p in all_players
            if p.position == owned_player.position
            and p.price <= owned_player.price + bank
            and p not in squad
        ]

        for alt in alternatives:
            alt_score = calculate_score(alt, fixture_horizon=3)
            score_gain = alt_score - owned_score

            if score_gain > 5:  # Significant improvement
                recommendations.append({
                    'out': owned_player,
                    'in': alt,
                    'score_gain': score_gain,
                    'cost': alt.price - owned_player.price
                })

    # Sort by score gain
    return sorted(recommendations, key=lambda x: x['score_gain'], reverse=True)
```

### Goal 4: Captain Selection

**Objective:** Pick captain with highest expected return.

```python
def select_captain(starting_xi, strategy='balanced'):
    for player in starting_xi:
        player.captain_score = calculate_score(
            player,
            fixture_horizon=1,
            include_ceiling=True  # Ceiling matters for captain!
        )

        # Adjust for ownership strategy
        if strategy == 'differential':
            # Bonus for low ownership (high risk, high reward)
            if player.ownership < 10:
                player.captain_score *= 1.2
        elif strategy == 'safe':
            # Bonus for high ownership (protect rank)
            if player.ownership > 30:
                player.captain_score *= 1.1

    ranked = sorted(starting_xi, key=lambda p: p.captain_score, reverse=True)

    return {
        'captain': ranked[0],
        'vice_captain': ranked[1]
    }
```

---

## Special Scenarios

### Double Gameweeks (DGW)

Players with 2 fixtures in one gameweek:

```python
if player.has_double_gameweek:
    # Average the two fixture scores
    fixture_score = (fixture_1_score + fixture_2_score) / 2

    # Apply DGW multiplier (not 2x due to rotation risk)
    dgw_multiplier = 1.7

    total_score *= dgw_multiplier
```

### Blank Gameweeks (BGW)

Players with 0 fixtures:

```python
if player.has_blank_gameweek:
    total_score = 0  # Cannot score points
```

### Price Changes

Add urgency factor for transfer timing:

```python
def get_transfer_urgency(player, owned=False):
    urgency = 0

    if not owned and player.price_rising_tonight:
        urgency += 3  # Buy before price rise

    if owned and player.price_falling_tonight:
        urgency += 3  # Sell before price drop

    return urgency

# Add to transfer recommendations
total_transfer_value = score_gain + transfer_urgency
```

---

## Confidence Scoring

Add confidence measure for close decisions:

```python
def calculate_confidence(player):
    factors = [
        fixture_score > 6,      # Good fixture
        form_score > 6,         # Good form
        nailedness_score > 8,   # Nailed
    ]

    agreement = sum(factors) / len(factors)

    if agreement >= 0.8:
        return 'HIGH'
    elif agreement >= 0.5:
        return 'MEDIUM'
    else:
        return 'LOW'
```

**Usage:**
```
Player A: Score 35 (HIGH confidence) ✓ Pick this one
Player B: Score 34 (LOW confidence)  ⚠️ Factors disagree
```

---

## Data Requirements

### From FPL API

| Data | Endpoint | Usage |
|------|----------|-------|
| Player info | `/bootstrap-static/` | Price, position, team, form |
| Fixtures | `/fixtures/` | FDR, home/away |
| Player history | `/element-summary/{id}/` | Past points, minutes |
| Live GW data | `/event/{gw}/live/` | Current GW stats |

### From External Sources (Optional)

| Data | Source | Usage |
|------|--------|-------|
| xG / xA | Understat, FBRef | Better form calculation |
| Team strength | Calculated from xG/xGA | Better fixture assessment |
| Price predictions | LiveFPL, FPLStatistics | Transfer timing |

### From Your Model

| Data | Source | Usage |
|------|--------|-------|
| P(starts) | Playing Time Model (94% AUC) | Nailedness score |

---

## Implementation Roadmap

### Phase 1: Basic System (MVP)

1. **Fixture Score** using FDR (simple)
2. **Form Score** using points (simple)
3. **Nailedness Score** using playing time model
4. **Basic weights** (equal)
5. **Starting XI selector**
6. **Captain picker**

### Phase 2: Improvements

1. **Replace FDR** with team attack/defense strength
2. **Replace points form** with xG/xA form
3. **Optimize weights** through backtesting
4. **Position-specific weights**
5. **Transfer recommender**

### Phase 3: Advanced

1. **DGW/BGW handling**
2. **Price change integration**
3. **Confidence scoring**
4. **Rotation risk model**
5. **Multi-week planning view**
6. **Squad optimizer** (budget constraints)

---

## Expected Performance

| Aspect | Expectation |
|--------|-------------|
| **Accuracy vs ML model** | ~80% as good, 20% of complexity |
| **Interpretability** | 100% transparent |
| **Maintenance** | Minimal - no model retraining |
| **User trust** | High - can see reasoning |

---

## Strengths

1. Focuses on predictable factors (fixtures, form, playing time)
2. Simple and interpretable
3. Leverages strong playing time model (94% AUC)
4. No overfitting to noisy point outcomes
5. Easy to maintain and update
6. Transparent decision-making

## Weaknesses

1. Arbitrary weights (until optimized)
2. Linear combination assumption
3. FDR is crude (until replaced with team strength)
4. Form can be misleading (until xG/xA used)
5. No uncertainty quantification
6. Position-blind (until position weights added)

---

## Comparison: Score System vs Points Prediction

| Aspect | Score System | Points Prediction |
|--------|--------------|-------------------|
| **Goal** | Rank players | Predict exact points |
| **Accuracy** | Relative ranking | Absolute value (noisy) |
| **Interpretability** | High | Low (black box) |
| **Actionability** | High | Low (small differences meaningless) |
| **Maintenance** | Low | High (model drift) |
| **Overfitting risk** | Low | High |
| **Best for** | Weekly decisions | Research/analysis |

---

## Conclusion

The score-based ranking system provides a **practical, transparent, and maintainable** approach to FPL decision-making. While it won't predict exact points, it effectively ranks players on factors that correlate with performance, enabling better:

- Squad selection
- Starting XI picks
- Transfer decisions
- Captain choices

The system can be implemented incrementally, starting with a basic MVP and adding improvements over time.
