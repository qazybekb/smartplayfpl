"""
Step 2c: Pipeline Improvements & Additional Analysis
====================================================

This script addresses gaps identified in the pipeline:
1. Feature Leakage Analysis - What can/cannot be used for prediction
2. Fixture Context Analysis - Opponent strength
3. Team-Level Analysis - Team form and style
4. Player Segmentation - Price tiers, ownership
5. Baseline Models - What we need to beat
6. Pre-Prediction Feature Analysis - Beyond correlation
7. Sample Distribution - Training data balance

Usage:
    cd backend
    python ml/02c_pipeline_improvements.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILE = DATA_DIR / "fpl_gameweek_data_clean.csv"


def load_data():
    return pd.read_csv(INPUT_FILE)


def feature_leakage_analysis(df: pd.DataFrame) -> str:
    """Identify features that leak target information."""
    output = []
    output.append("## 1. Feature Leakage Analysis\n")
    output.append("**Critical: Which features can we actually use for PREDICTION?**\n")
    
    # Categorize features
    pre_match_features = {
        "Available BEFORE match (✅ CAN USE)": [
            "player_id", "player_name", "position", "team_id", "team_name",
            "gameweek", "opponent_team_id", "opponent_name", "was_home",
            "value",  # Price is known before
            # Historical averages (need to calculate):
            # "form_avg", "xg_avg", "xa_avg", "ict_avg", "minutes_avg"
        ],
        "Only known AFTER match (❌ CANNOT USE)": [
            "total_points",  # TARGET
            "minutes",  # Exact minutes only known after
            "goals_scored", "assists", "clean_sheets", "goals_conceded",
            "own_goals", "penalties_saved", "penalties_missed",
            "yellow_cards", "red_cards", "saves",
            "bonus", "bps",
            "influence", "creativity", "threat", "ict_index",
            "expected_goals", "expected_assists",  # Post-match xG
            "selected", "transfers_in", "transfers_out",  # During GW
        ],
    }
    
    for category, features in pre_match_features.items():
        output.append(f"### {category}\n")
        for f in features:
            if f in df.columns:
                output.append(f"- `{f}`")
            else:
                output.append(f"- `{f}` (derived)")
        output.append("")
    
    output.append("### ⚠️ Key Insight\n")
    output.append("Most highly correlated features (bps, influence, bonus) are **POST-MATCH**!")
    output.append("For prediction, we must use **HISTORICAL AVERAGES** of these features.\n")
    
    output.append("### Features to CREATE for Prediction:\n")
    output.append("```python")
    output.append("# Rolling averages of post-match features (from PREVIOUS GWs)")
    output.append("form_3gw = rolling_mean(total_points, window=3, shift=1)")
    output.append("xg_avg = rolling_mean(expected_goals, window=5, shift=1)")
    output.append("ict_avg = rolling_mean(ict_index, window=5, shift=1)")
    output.append("minutes_avg = rolling_mean(minutes, window=5, shift=1)")
    output.append("bonus_rate = cumulative_sum(bonus) / cumulative_count(appearances)")
    output.append("```")
    output.append("")
    
    return "\n".join(output)


def fixture_context_analysis(df: pd.DataFrame) -> str:
    """Analyze opponent strength and fixture context."""
    output = []
    output.append("## 2. Fixture Context Analysis\n")
    
    # Calculate team defensive/offensive strength
    team_stats = df.groupby("opponent_team_id").agg({
        "goals_scored": "sum",  # Goals conceded BY opponent
        "clean_sheets": "sum",  # Clean sheets AGAINST opponent
        "total_points": "mean",  # Avg points vs this opponent
        "player_id": "count"
    }).rename(columns={
        "goals_scored": "goals_conceded_total",
        "clean_sheets": "cs_against_total",
        "total_points": "avg_points_against",
        "player_id": "sample_size"
    })
    
    output.append("### Points Scored AGAINST Each Team (Defensive Weakness)\n")
    output.append("| Team ID | Avg Pts Against | Goals Conceded | Sample |")
    output.append("|---------|-----------------|----------------|--------|")
    
    # Sort by avg points against (worst defense = highest points against)
    team_stats_sorted = team_stats.sort_values("avg_points_against", ascending=False)
    
    for team_id, row in team_stats_sorted.head(10).iterrows():
        output.append(f"| {team_id} | {row['avg_points_against']:.2f} | {row['goals_conceded_total']} | {row['sample_size']} |")
    
    output.append("")
    output.append("**Insight**: Teams with high 'Avg Pts Against' are weak defensively → good to attack\n")
    
    # Home vs Away by opponent
    output.append("### Home vs Away Effect by Opponent Strength\n")
    
    # Classify opponents as "easy" or "hard" based on avg points against
    median_pts = team_stats["avg_points_against"].median()
    easy_opponents = team_stats[team_stats["avg_points_against"] >= median_pts].index.tolist()
    
    output.append(f"- Easy opponents (above median): {len(easy_opponents)} teams")
    output.append(f"- Hard opponents (below median): {len(team_stats) - len(easy_opponents)} teams\n")
    
    df["opponent_difficulty"] = df["opponent_team_id"].apply(
        lambda x: "Easy" if x in easy_opponents else "Hard"
    )
    
    cross_tab = df[df["minutes"] > 0].groupby(["was_home", "opponent_difficulty"])["total_points"].mean().unstack()
    
    output.append("| Scenario | Avg Points |")
    output.append("|----------|------------|")
    for home in [True, False]:
        for diff in ["Easy", "Hard"]:
            if home in cross_tab.index and diff in cross_tab.columns:
                pts = cross_tab.loc[home, diff]
                label = f"{'Home' if home else 'Away'} vs {diff}"
                output.append(f"| {label} | {pts:.2f} |")
    
    output.append("")
    output.append("**Recommendation**: Create `opponent_strength` feature from historical data\n")
    
    return "\n".join(output)


def player_segmentation_analysis(df: pd.DataFrame) -> str:
    """Analyze players by different segments."""
    output = []
    output.append("## 3. Player Segmentation Analysis\n")
    
    # Get latest price per player
    player_latest = df.sort_values("gameweek").groupby("player_id").last()
    
    # Price tiers
    output.append("### Price Tier Analysis\n")
    
    def price_tier(price):
        if price < 5:
            return "Budget (<5m)"
        elif price < 8:
            return "Mid (5-8m)"
        else:
            return "Premium (8m+)"
    
    player_latest["price_tier"] = player_latest["value"].apply(price_tier)
    
    output.append("| Price Tier | Players | Avg Points | Avg xG | Avg Bonus |")
    output.append("|------------|---------|------------|--------|-----------|")
    
    for tier in ["Budget (<5m)", "Mid (5-8m)", "Premium (8m+)"]:
        tier_players = player_latest[player_latest["price_tier"] == tier]
        if len(tier_players) > 0:
            # Get all GW data for these players
            tier_ids = tier_players.index.tolist()
            tier_data = df[df["player_id"].isin(tier_ids) & (df["minutes"] > 0)]
            
            avg_pts = tier_data["total_points"].mean()
            avg_xg = tier_data["expected_goals"].mean()
            avg_bonus = tier_data["bonus"].mean()
            
            output.append(f"| {tier} | {len(tier_players)} | {avg_pts:.2f} | {avg_xg:.3f} | {avg_bonus:.2f} |")
    
    output.append("")
    
    # Position × Price interaction
    output.append("### Position × Price Tier (Avg Points)\n")
    output.append("| Position | Budget | Mid | Premium |")
    output.append("|----------|--------|-----|---------|")
    
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        row = f"| {pos} |"
        for tier in ["Budget (<5m)", "Mid (5-8m)", "Premium (8m+)"]:
            tier_players = player_latest[(player_latest["price_tier"] == tier) & 
                                          (player_latest["position"] == pos)]
            tier_ids = tier_players.index.tolist()
            tier_data = df[df["player_id"].isin(tier_ids) & (df["minutes"] > 0)]
            
            if len(tier_data) > 10:
                avg_pts = tier_data["total_points"].mean()
                row += f" {avg_pts:.2f} |"
            else:
                row += " - |"
        output.append(row)
    
    output.append("")
    output.append("**Insight**: Premium players score more, but value (pts/price) may differ\n")
    
    return "\n".join(output)


def baseline_model_analysis(df: pd.DataFrame) -> str:
    """Establish baseline predictions to beat."""
    output = []
    output.append("## 4. Baseline Models (What We Need to Beat)\n")
    
    # Filter to played games
    df_played = df[df["minutes"] > 0].copy()
    
    # Baseline 1: Predict mean
    mean_pts = df_played["total_points"].mean()
    baseline1_mae = (df_played["total_points"] - mean_pts).abs().mean()
    
    output.append("### Baseline 1: Predict Global Mean\n")
    output.append(f"- Prediction: {mean_pts:.2f} for everyone")
    output.append(f"- MAE: {baseline1_mae:.2f}")
    output.append("")
    
    # Baseline 2: Predict position mean
    pos_means = df_played.groupby("position")["total_points"].mean()
    df_played["baseline2_pred"] = df_played["position"].map(pos_means)
    baseline2_mae = (df_played["total_points"] - df_played["baseline2_pred"]).abs().mean()
    
    output.append("### Baseline 2: Predict Position Mean\n")
    for pos, mean in pos_means.items():
        output.append(f"- {pos}: {mean:.2f}")
    output.append(f"- MAE: {baseline2_mae:.2f}")
    output.append("")
    
    # Baseline 3: Predict player's own mean
    player_means = df_played.groupby("player_id")["total_points"].transform("mean")
    baseline3_mae = (df_played["total_points"] - player_means).abs().mean()
    
    output.append("### Baseline 3: Predict Player's Season Average\n")
    output.append(f"- MAE: {baseline3_mae:.2f}")
    output.append("")
    
    # Baseline 4: Predict last GW points
    df_sorted = df_played.sort_values(["player_id", "gameweek"])
    df_sorted["last_gw_pts"] = df_sorted.groupby("player_id")["total_points"].shift(1)
    df_with_lag = df_sorted.dropna(subset=["last_gw_pts"])
    baseline4_mae = (df_with_lag["total_points"] - df_with_lag["last_gw_pts"]).abs().mean()
    
    output.append("### Baseline 4: Predict Last GW Points\n")
    output.append(f"- MAE: {baseline4_mae:.2f}")
    output.append("")
    
    # Summary
    output.append("### Summary: Baselines to Beat\n")
    output.append("| Baseline | MAE | Description |")
    output.append("|----------|-----|-------------|")
    output.append(f"| Global Mean | {baseline1_mae:.2f} | Predict {mean_pts:.1f} for all |")
    output.append(f"| Position Mean | {baseline2_mae:.2f} | Predict position average |")
    output.append(f"| Player Mean | {baseline3_mae:.2f} | Predict player's avg |")
    output.append(f"| Last GW | {baseline4_mae:.2f} | Predict previous points |")
    output.append("")
    output.append(f"**Target**: Our model should achieve MAE < {baseline3_mae:.2f} (beat player mean)")
    output.append("")
    
    return "\n".join(output)


def sample_distribution_analysis(df: pd.DataFrame) -> str:
    """Analyze training data balance and potential biases."""
    output = []
    output.append("## 5. Sample Distribution Analysis\n")
    
    # Points distribution for training
    output.append("### Points Distribution (Training Data)\n")
    
    df_played = df[df["minutes"] > 0]
    
    buckets = [
        (0, 0, "0 pts"),
        (1, 2, "1-2 pts"),
        (3, 5, "3-5 pts"),
        (6, 9, "6-9 pts"),
        (10, 14, "10-14 pts"),
        (15, 100, "15+ pts"),
    ]
    
    output.append("| Points Range | Count | % | Note |")
    output.append("|--------------|-------|---|------|")
    
    for low, high, label in buckets:
        count = ((df_played["total_points"] >= low) & (df_played["total_points"] <= high)).sum()
        pct = count / len(df_played) * 100
        
        if pct > 40:
            note = "⚠️ Dominant class"
        elif pct < 5:
            note = "⚠️ Rare events"
        else:
            note = ""
        
        output.append(f"| {label} | {count} | {pct:.1f}% | {note} |")
    
    output.append("")
    output.append("**Challenge**: Most samples are 1-2 points. High scorers (10+) are rare.\n")
    
    # Gameweek distribution
    output.append("### Gameweek Distribution\n")
    gw_counts = df_played.groupby("gameweek").size()
    output.append(f"- Min samples per GW: {gw_counts.min()}")
    output.append(f"- Max samples per GW: {gw_counts.max()}")
    output.append(f"- Std dev: {gw_counts.std():.1f}")
    output.append("")
    
    # Position distribution
    output.append("### Position Distribution\n")
    pos_counts = df_played.groupby("position").size()
    for pos, count in pos_counts.items():
        pct = count / len(df_played) * 100
        output.append(f"- {pos}: {count} ({pct:.1f}%)")
    output.append("")
    
    output.append("**Recommendation**: Consider stratified sampling or class weights for rare events\n")
    
    return "\n".join(output)


def feature_importance_preview(df: pd.DataFrame) -> str:
    """Quick feature importance using simple methods."""
    output = []
    output.append("## 6. Feature Importance Preview (Pre-Model)\n")
    
    df_played = df[df["minutes"] > 0].copy()
    
    # Use only features we can derive from historical data
    potential_features = ["value", "was_home"]
    
    # Add rolling averages simulation (using same-GW data as proxy)
    for col in ["expected_goals", "expected_assists", "ict_index", "minutes"]:
        if col in df.columns:
            potential_features.append(col)
    
    output.append("### Correlation with Points (Features We Can Use)\n")
    output.append("| Feature | Correlation | Usable? |")
    output.append("|---------|-------------|---------|")
    
    for feat in potential_features:
        if feat in df_played.columns:
            corr = df_played[feat].corr(df_played["total_points"])
            usable = "✅ Historical avg" if feat not in ["value", "was_home"] else "✅ Known before"
            output.append(f"| {feat} | {corr:+.3f} | {usable} |")
    
    output.append("")
    
    # Variance check
    output.append("### Variance Check (Low Variance = Less Useful)\n")
    output.append("| Feature | Std Dev | Unique Values |")
    output.append("|---------|---------|---------------|")
    
    for feat in potential_features:
        if feat in df_played.columns:
            std = df_played[feat].std()
            unique = df_played[feat].nunique()
            output.append(f"| {feat} | {std:.2f} | {unique} |")
    
    output.append("")
    
    return "\n".join(output)


def recommendations_summary() -> str:
    """Summary of all recommendations."""
    output = []
    output.append("## 7. Pipeline Improvement Recommendations\n")
    
    output.append("### Must Fix Before Modeling\n")
    output.append("1. **Create lagged features** - Don't use same-GW bps/influence/xG")
    output.append("2. **Add opponent strength** - Calculate from historical data")
    output.append("3. **Establish baselines** - Track MAE vs player mean (~2.4)")
    output.append("")
    
    output.append("### Should Add\n")
    output.append("4. **Price tier features** - Budget/Mid/Premium behave differently")
    output.append("5. **Minutes probability** - Predict if player will play")
    output.append("6. **Sample weights** - Recent GWs may be more relevant")
    output.append("")
    
    output.append("### Nice to Have\n")
    output.append("7. **FDR from API** - Official fixture difficulty ratings")
    output.append("8. **Team-level features** - Team's overall form")
    output.append("9. **Fixture congestion** - Days since last game")
    output.append("")
    
    output.append("### Technical Debt\n")
    output.append("10. Set random seeds for reproducibility")
    output.append("11. Add unit tests for data quality")
    output.append("12. Version control data with DVC")
    output.append("")
    
    return "\n".join(output)


def run_pipeline_improvements():
    """Run all improvement analyses."""
    print("=" * 60)
    print("FPL ML PIPELINE IMPROVEMENT ANALYSIS")
    print("=" * 60)
    print()
    
    print("📥 Loading clean data...")
    df = load_data()
    print(f"   Loaded {len(df):,} records")
    print()
    
    print("📊 Running improvement analyses...")
    
    sections = []
    sections.append("# FPL ML - Pipeline Improvement Analysis\n")
    sections.append(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*\n")
    sections.append("---\n")
    
    sections.append(feature_leakage_analysis(df))
    print("   ✓ Feature leakage analysis")
    
    sections.append(fixture_context_analysis(df))
    print("   ✓ Fixture context analysis")
    
    sections.append(player_segmentation_analysis(df))
    print("   ✓ Player segmentation analysis")
    
    sections.append(baseline_model_analysis(df))
    print("   ✓ Baseline model analysis")
    
    sections.append(sample_distribution_analysis(df))
    print("   ✓ Sample distribution analysis")
    
    sections.append(feature_importance_preview(df))
    print("   ✓ Feature importance preview")
    
    sections.append(recommendations_summary())
    print("   ✓ Recommendations summary")
    
    # Save report
    report = "\n".join(sections)
    report_path = DATA_DIR / "pipeline_improvements_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    print()
    print(f"💾 Report saved to: {report_path}")
    print()
    print("🎉 Pipeline improvement analysis complete!")
    
    return df, report


if __name__ == "__main__":
    df, report = run_pipeline_improvements()











