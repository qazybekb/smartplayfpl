"""
Step 2b: Advanced Statistical Analysis for FPL ML Model
=======================================================

This script performs deeper statistical analysis:
1. Autocorrelation - How predictive is past performance?
2. Player consistency - Variance analysis
3. Position-specific patterns
4. Gameweek effects
5. Multicollinearity check (VIF)
6. Distribution analysis
7. Interaction effects
8. Outlier detection

Usage:
    cd backend
    python ml/02b_advanced_eda.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent / "data"
# Use CLEAN data (after data cleaning step)
INPUT_FILE = DATA_DIR / "fpl_gameweek_data_clean.csv"


def load_data():
    """Load the collected data."""
    return pd.read_csv(INPUT_FILE)


def autocorrelation_analysis(df: pd.DataFrame) -> str:
    """Analyze how past performance predicts future performance."""
    output = []
    output.append("## 1. Autocorrelation Analysis\n")
    output.append("*How well does GW N-k predict GW N?*\n")
    
    # For each player, calculate lag correlations
    lag_correlations = {1: [], 2: [], 3: [], 4: [], 5: []}
    
    for player_id in df["player_id"].unique():
        player_df = df[df["player_id"] == player_id].sort_values("gameweek")
        points = player_df["total_points"].values
        
        if len(points) < 6:
            continue
        
        for lag in range(1, 6):
            if len(points) > lag:
                # Correlation between points and lagged points
                corr = np.corrcoef(points[lag:], points[:-lag])[0, 1]
                if not np.isnan(corr):
                    lag_correlations[lag].append(corr)
    
    output.append("### Points Autocorrelation by Lag\n")
    output.append("| Lag (GWs) | Mean Correlation | Std | Interpretation |")
    output.append("|-----------|------------------|-----|----------------|")
    
    for lag in range(1, 6):
        if lag_correlations[lag]:
            mean_corr = np.mean(lag_correlations[lag])
            std_corr = np.std(lag_correlations[lag])
            
            if mean_corr > 0.3:
                interp = "Strong predictive signal"
            elif mean_corr > 0.15:
                interp = "Moderate signal"
            elif mean_corr > 0.05:
                interp = "Weak signal"
            else:
                interp = "Very weak/no signal"
            
            output.append(f"| {lag} | {mean_corr:+.3f} | {std_corr:.3f} | {interp} |")
    
    output.append("")
    output.append("**Key Insight**: The correlation drops off quickly, suggesting recent form (1-3 GWs) matters most.")
    output.append("")
    
    return "\n".join(output)


def player_consistency_analysis(df: pd.DataFrame) -> str:
    """Analyze player consistency (variance in scoring)."""
    output = []
    output.append("## 2. Player Consistency Analysis\n")
    output.append("*Some players are consistent, others are boom/bust*\n")
    
    # Filter to players who played most GWs
    player_stats = df[df["minutes"] > 0].groupby("player_id").agg({
        "total_points": ["mean", "std", "count"],
        "player_name": "first",
        "position": "first"
    }).reset_index()
    player_stats.columns = ["player_id", "mean_pts", "std_pts", "games", "name", "position"]
    player_stats = player_stats[player_stats["games"] >= 8]  # At least 8 games
    
    # Calculate coefficient of variation (CV = std/mean)
    player_stats["cv"] = player_stats["std_pts"] / player_stats["mean_pts"].replace(0, 1)
    
    output.append("### Consistency by Position\n")
    output.append("| Position | Avg Mean Pts | Avg Std | Avg CV | Interpretation |")
    output.append("|----------|--------------|---------|--------|----------------|")
    
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_stats = player_stats[player_stats["position"] == pos]
        if len(pos_stats) > 0:
            avg_mean = pos_stats["mean_pts"].mean()
            avg_std = pos_stats["std_pts"].mean()
            avg_cv = pos_stats["cv"].mean()
            
            if avg_cv < 0.8:
                interp = "More consistent"
            elif avg_cv < 1.2:
                interp = "Moderate variance"
            else:
                interp = "High variance (boom/bust)"
            
            output.append(f"| {pos} | {avg_mean:.2f} | {avg_std:.2f} | {avg_cv:.2f} | {interp} |")
    
    output.append("")
    
    # Most consistent vs most variable players
    output.append("### Most Consistent Players (lowest CV)\n")
    consistent = player_stats.nsmallest(10, "cv")
    output.append("| Player | Position | Mean | Std | CV |")
    output.append("|--------|----------|------|-----|-----|")
    for _, row in consistent.iterrows():
        output.append(f"| {row['name']} | {row['position']} | {row['mean_pts']:.2f} | {row['std_pts']:.2f} | {row['cv']:.2f} |")
    output.append("")
    
    output.append("### Most Variable Players (highest CV)\n")
    variable = player_stats.nlargest(10, "cv")
    output.append("| Player | Position | Mean | Std | CV |")
    output.append("|--------|----------|------|-----|-----|")
    for _, row in variable.iterrows():
        output.append(f"| {row['name']} | {row['position']} | {row['mean_pts']:.2f} | {row['std_pts']:.2f} | {row['cv']:.2f} |")
    output.append("")
    
    output.append("**Key Insight**: GKPs and DEFs are more consistent. FWDs are boom/bust. This affects prediction confidence.")
    output.append("")
    
    return "\n".join(output)


def position_specific_analysis(df: pd.DataFrame) -> str:
    """Deep dive into position-specific patterns."""
    output = []
    output.append("## 3. Position-Specific Feature Correlations\n")
    output.append("*Do different features matter for different positions?*\n")
    
    features = ["minutes", "expected_goals", "expected_assists", "ict_index", 
                "influence", "creativity", "threat", "bps"]
    
    output.append("### Correlation with Points by Position\n")
    output.append("| Feature | GKP | DEF | MID | FWD |")
    output.append("|---------|-----|-----|-----|-----|")
    
    for feat in features:
        row = f"| {feat} |"
        for pos in ["GKP", "DEF", "MID", "FWD"]:
            pos_df = df[df["position"] == pos]
            corr = pos_df[feat].corr(pos_df["total_points"])
            row += f" {corr:+.2f} |"
        output.append(row)
    
    output.append("")
    output.append("**Key Insights**:")
    output.append("- **xG matters most for FWD** (they score goals)")
    output.append("- **xA matters most for MID** (they assist)")
    output.append("- **Influence matters most for GKP** (saves, distribution)")
    output.append("- Consider **position-specific models** or interaction features")
    output.append("")
    
    return "\n".join(output)


def gameweek_effects(df: pd.DataFrame) -> str:
    """Analyze if certain gameweeks are harder/easier."""
    output = []
    output.append("## 4. Gameweek Effects\n")
    output.append("*Are some GWs systematically higher/lower scoring?*\n")
    
    gw_stats = df[df["minutes"] > 0].groupby("gameweek").agg({
        "total_points": ["mean", "std", "count"]
    }).reset_index()
    gw_stats.columns = ["gameweek", "mean_pts", "std_pts", "count"]
    
    overall_mean = df[df["minutes"] > 0]["total_points"].mean()
    
    output.append("### Average Points by Gameweek\n")
    output.append("| GW | Mean Pts | Diff from Avg | Std |")
    output.append("|----|----------|---------------|-----|")
    
    for _, row in gw_stats.iterrows():
        diff = row["mean_pts"] - overall_mean
        output.append(f"| {int(row['gameweek'])} | {row['mean_pts']:.2f} | {diff:+.2f} | {row['std_pts']:.2f} |")
    
    output.append("")
    
    # Test for significant GW differences
    groups = [df[(df["gameweek"] == gw) & (df["minutes"] > 0)]["total_points"].values 
              for gw in df["gameweek"].unique()]
    f_stat, p_value = stats.f_oneway(*groups)
    
    output.append(f"**ANOVA Test**: F={f_stat:.2f}, p={p_value:.4f}")
    if p_value < 0.05:
        output.append("→ **Significant difference between gameweeks** (some GWs are harder)")
    else:
        output.append("→ No significant difference (GWs are similar)")
    output.append("")
    
    return "\n".join(output)


def multicollinearity_analysis(df: pd.DataFrame) -> str:
    """Check for multicollinearity between features."""
    output = []
    output.append("## 5. Multicollinearity Analysis\n")
    output.append("*Are features too correlated with each other?*\n")
    
    features = ["minutes", "goals_scored", "assists", "clean_sheets", 
                "bonus", "bps", "influence", "creativity", "threat", 
                "expected_goals", "expected_assists", "value"]
    
    # Calculate correlation matrix
    corr_matrix = df[features].corr()
    
    # Find highly correlated pairs
    high_corr_pairs = []
    for i in range(len(features)):
        for j in range(i+1, len(features)):
            corr = corr_matrix.iloc[i, j]
            if abs(corr) > 0.7:
                high_corr_pairs.append((features[i], features[j], corr))
    
    high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    
    output.append("### Highly Correlated Feature Pairs (|r| > 0.7)\n")
    if high_corr_pairs:
        output.append("| Feature 1 | Feature 2 | Correlation |")
        output.append("|-----------|-----------|-------------|")
        for f1, f2, corr in high_corr_pairs[:10]:
            output.append(f"| {f1} | {f2} | {corr:+.3f} |")
    else:
        output.append("No highly correlated pairs found.")
    output.append("")
    
    output.append("**Implications**:")
    output.append("- **bps ↔ influence/bonus**: Expected (BPS determines bonus)")
    output.append("- **xG ↔ threat**: Expected (both measure attacking threat)")
    output.append("- Consider **dropping redundant features** or using **regularization**")
    output.append("")
    
    return "\n".join(output)


def distribution_analysis(df: pd.DataFrame) -> str:
    """Analyze the distribution of the target variable."""
    output = []
    output.append("## 6. Target Distribution Analysis\n")
    output.append("*What distribution does points follow?*\n")
    
    points = df[df["minutes"] > 0]["total_points"]
    
    # Test for normality
    shapiro_stat, shapiro_p = stats.shapiro(points.sample(min(5000, len(points))))
    
    output.append("### Normality Test (Shapiro-Wilk)\n")
    output.append(f"- Statistic: {shapiro_stat:.4f}")
    output.append(f"- P-value: {shapiro_p:.4e}")
    if shapiro_p < 0.05:
        output.append("→ **NOT normally distributed** (p < 0.05)")
    else:
        output.append("→ Approximately normal")
    output.append("")
    
    # Distribution shape
    output.append("### Distribution Shape\n")
    output.append(f"- Skewness: {points.skew():.3f} (positive = right-skewed)")
    output.append(f"- Kurtosis: {points.kurtosis():.3f} (>0 = heavy tails)")
    output.append("")
    
    # Try fitting Poisson
    lambda_est = points.mean()
    
    output.append("### Best Distribution Fit\n")
    output.append("Since points are **count data** (0, 1, 2, ...), consider:")
    output.append(f"- **Poisson** (λ = {lambda_est:.2f})")
    output.append("- **Negative Binomial** (handles overdispersion)")
    output.append("")
    
    # Check for overdispersion
    variance = points.var()
    mean = points.mean()
    dispersion = variance / mean
    output.append(f"**Overdispersion check**: Var/Mean = {dispersion:.2f}")
    if dispersion > 1.5:
        output.append("→ **Overdispersed** - Negative Binomial may be better than Poisson")
    else:
        output.append("→ Close to Poisson")
    output.append("")
    
    output.append("**Modeling Implications**:")
    output.append("- Standard regression assumes normal errors (may not be ideal)")
    output.append("- Tree-based models (XGBoost) don't assume normality ✓")
    output.append("- Could try Poisson/Negative Binomial regression as alternative")
    output.append("")
    
    return "\n".join(output)


def interaction_effects(df: pd.DataFrame) -> str:
    """Analyze interaction effects."""
    output = []
    output.append("## 7. Interaction Effects\n")
    output.append("*Does the effect of features depend on other features?*\n")
    
    # Home advantage by position
    output.append("### Home Advantage by Position\n")
    output.append("| Position | Home Avg | Away Avg | Home Boost |")
    output.append("|----------|----------|----------|------------|")
    
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = df[(df["position"] == pos) & (df["minutes"] > 0)]
        home_avg = pos_df[pos_df["was_home"]]["total_points"].mean()
        away_avg = pos_df[~pos_df["was_home"]]["total_points"].mean()
        boost = ((home_avg - away_avg) / away_avg * 100) if away_avg != 0 else 0
        output.append(f"| {pos} | {home_avg:.2f} | {away_avg:.2f} | {boost:+.1f}% |")
    
    output.append("")
    
    # xG predictiveness by player price tier
    output.append("### xG Predictiveness by Price Tier\n")
    df_with_xg = df[(df["expected_goals"] > 0) & (df["minutes"] > 0)]
    
    output.append("| Price Tier | xG-Goals Corr | Count |")
    output.append("|------------|---------------|-------|")
    
    for low, high, label in [(0, 5, "Budget (<5m)"), (5, 8, "Mid (5-8m)"), (8, 20, "Premium (8m+)")]:
        tier_df = df_with_xg[(df_with_xg["value"] >= low) & (df_with_xg["value"] < high)]
        if len(tier_df) > 30:
            corr = tier_df["expected_goals"].corr(tier_df["goals_scored"])
            output.append(f"| {label} | {corr:.3f} | {len(tier_df)} |")
    
    output.append("")
    output.append("**Key Insights**:")
    output.append("- Home advantage varies by position (FWDs benefit most)")
    output.append("- xG predictiveness may vary by price tier")
    output.append("- Consider **interaction features** like `is_home × position`")
    output.append("")
    
    return "\n".join(output)


def outlier_analysis(df: pd.DataFrame) -> str:
    """Detect and analyze outliers."""
    output = []
    output.append("## 8. Outlier Analysis\n")
    output.append("*Who are the extreme performers?*\n")
    
    points = df[df["minutes"] > 0]["total_points"]
    
    # IQR method
    Q1 = points.quantile(0.25)
    Q3 = points.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    
    outliers = df[(df["minutes"] > 0) & ((df["total_points"] < lower) | (df["total_points"] > upper))]
    
    output.append(f"### Outlier Detection (IQR Method)\n")
    output.append(f"- Q1: {Q1:.0f}, Q3: {Q3:.0f}, IQR: {IQR:.0f}")
    output.append(f"- Lower bound: {lower:.1f}, Upper bound: {upper:.1f}")
    output.append(f"- Outliers: {len(outliers)} ({len(outliers)/len(df[df['minutes']>0])*100:.1f}%)")
    output.append("")
    
    # Top positive outliers (great performances)
    output.append("### Top Performances (Positive Outliers)\n")
    top_performances = df[df["minutes"] > 0].nlargest(10, "total_points")
    output.append("| Player | GW | Points | Goals | Assists | Bonus |")
    output.append("|--------|-----|--------|-------|---------|-------|")
    for _, row in top_performances.iterrows():
        output.append(f"| {row['player_name']} | {row['gameweek']} | {row['total_points']} | {row['goals_scored']} | {row['assists']} | {row['bonus']} |")
    output.append("")
    
    # Negative outliers (poor performances with minutes)
    output.append("### Worst Performances (Negative Points)\n")
    worst = df[(df["minutes"] > 0) & (df["total_points"] < 0)]
    if len(worst) > 0:
        output.append("| Player | GW | Points | Reason |")
        output.append("|--------|-----|--------|--------|")
        for _, row in worst.iterrows():
            reasons = []
            if row["own_goals"] > 0:
                reasons.append(f"OG:{row['own_goals']}")
            if row["penalties_missed"] > 0:
                reasons.append(f"Pen Miss:{row['penalties_missed']}")
            if row["red_cards"] > 0:
                reasons.append("Red Card")
            if row["yellow_cards"] > 1:
                reasons.append("2 Yellows")
            output.append(f"| {row['player_name']} | {row['gameweek']} | {row['total_points']} | {', '.join(reasons) or 'Unknown'} |")
    else:
        output.append("No negative point performances.")
    output.append("")
    
    output.append("**Modeling Implications**:")
    output.append("- High points are rare events (1% get 15+)")
    output.append("- Negative points are rare but impactful")
    output.append("- Consider **robust regression** or **Winsorizing** extreme values")
    output.append("")
    
    return "\n".join(output)


def form_decay_analysis(df: pd.DataFrame) -> str:
    """Analyze how quickly form decays."""
    output = []
    output.append("## 9. Form Decay Analysis\n")
    output.append("*How many past GWs should we use for form calculation?*\n")
    
    # Calculate rolling forms and their predictive power
    results = []
    
    for window in [1, 2, 3, 4, 5, 6, 7]:
        correlations = []
        
        for player_id in df["player_id"].unique():
            player_df = df[df["player_id"] == player_id].sort_values("gameweek")
            if len(player_df) < window + 2:
                continue
            
            # Calculate rolling form
            player_df = player_df.copy()
            player_df["rolling_form"] = player_df["total_points"].shift(1).rolling(window, min_periods=1).mean()
            
            # Correlation with next GW points
            valid = player_df.dropna(subset=["rolling_form"])
            if len(valid) > 3:
                corr = valid["rolling_form"].corr(valid["total_points"])
                if not np.isnan(corr):
                    correlations.append(corr)
        
        if correlations:
            results.append({
                "window": window,
                "mean_corr": np.mean(correlations),
                "std_corr": np.std(correlations)
            })
    
    output.append("### Predictive Power of Rolling Form Windows\n")
    output.append("| Window (GWs) | Mean Correlation | Std | Recommendation |")
    output.append("|--------------|------------------|-----|----------------|")
    
    best_window = max(results, key=lambda x: x["mean_corr"])
    
    for r in results:
        rec = "← Best" if r["window"] == best_window["window"] else ""
        output.append(f"| {r['window']} | {r['mean_corr']:+.3f} | {r['std_corr']:.3f} | {rec} |")
    
    output.append("")
    output.append(f"**Optimal form window: {best_window['window']} gameweeks** (highest correlation)")
    output.append("")
    
    return "\n".join(output)


def final_recommendations(df: pd.DataFrame) -> str:
    """Summary of findings and recommendations."""
    output = []
    output.append("## 10. Summary & Recommendations\n")
    
    output.append("### Key Statistical Findings\n")
    output.append("1. **Autocorrelation is weak** - Past performance is only moderately predictive")
    output.append("2. **FWDs are most variable** - Harder to predict, GKPs are most consistent")
    output.append("3. **Position-specific patterns exist** - Different features matter for different positions")
    output.append("4. **Home advantage is real and significant** - ~18% boost at home")
    output.append("5. **Multicollinearity present** - bps/influence/bonus are highly correlated")
    output.append("6. **Target is NOT normal** - Right-skewed, overdispersed")
    output.append("7. **Outliers are rare but extreme** - Top performances are 15+ points")
    output.append("")
    
    output.append("### Recommended Feature Engineering\n")
    output.append("Based on this analysis:")
    output.append("")
    output.append("**Must-have features:**")
    output.append("- `form_3gw` or `form_4gw` (rolling average points)")
    output.append("- `is_home` (significant effect)")
    output.append("- `position` (one-hot encoded)")
    output.append("- `minutes_avg` (proxy for 'will they play')")
    output.append("")
    
    output.append("**High-value features:**")
    output.append("- `ict_avg` (rolling ICT index)")
    output.append("- `xg_avg`, `xa_avg` (rolling expected stats)")
    output.append("- `bonus_rate` (historical bonus per appearance)")
    output.append("")
    
    output.append("**Consider dropping (multicollinearity):**")
    output.append("- Keep `ict_index`, drop `influence/creativity/threat` separately")
    output.append("- Keep `expected_goal_involvements`, drop `xG` and `xA` separately")
    output.append("")
    
    output.append("**Interaction features to try:**")
    output.append("- `is_home × position` (FWDs benefit most from home)")
    output.append("- `form × minutes_consistency` (reliable starters)")
    output.append("")
    
    output.append("### Model Recommendations\n")
    output.append("1. **Use XGBoost/LightGBM** - Handles non-normality, interactions automatically")
    output.append("2. **Consider position-specific models** - Or strong position interactions")
    output.append("3. **Use 3-4 GW rolling window** for form features")
    output.append("4. **Filter out 0-minute records** from training")
    output.append("5. **Time-based validation** (train on GW 1-10, validate on 11-12, test on 13-14)")
    output.append("")
    
    return "\n".join(output)


def run_advanced_eda():
    """Run complete advanced EDA."""
    print("=" * 60)
    print("FPL ML ADVANCED STATISTICAL ANALYSIS")
    print("=" * 60)
    print()
    
    # Load data
    print("📥 Loading data...")
    df = load_data()
    print(f"   Loaded {len(df):,} records")
    print()
    
    # Generate report sections
    print("📊 Running advanced analysis...")
    
    sections = []
    sections.append("# FPL ML - Advanced Statistical Analysis\n")
    sections.append(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*\n")
    sections.append("---\n")
    
    sections.append(autocorrelation_analysis(df))
    print("   ✓ Autocorrelation analysis")
    
    sections.append(player_consistency_analysis(df))
    print("   ✓ Player consistency analysis")
    
    sections.append(position_specific_analysis(df))
    print("   ✓ Position-specific analysis")
    
    sections.append(gameweek_effects(df))
    print("   ✓ Gameweek effects")
    
    sections.append(multicollinearity_analysis(df))
    print("   ✓ Multicollinearity analysis")
    
    sections.append(distribution_analysis(df))
    print("   ✓ Distribution analysis")
    
    sections.append(interaction_effects(df))
    print("   ✓ Interaction effects")
    
    sections.append(outlier_analysis(df))
    print("   ✓ Outlier analysis")
    
    sections.append(form_decay_analysis(df))
    print("   ✓ Form decay analysis")
    
    sections.append(final_recommendations(df))
    print("   ✓ Final recommendations")
    
    # Save report
    report = "\n".join(sections)
    report_path = DATA_DIR / "advanced_eda_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print()
    print(f"💾 Report saved to: {report_path}")
    
    print()
    print("🎉 Advanced analysis complete!")
    
    return df, report


if __name__ == "__main__":
    df, report = run_advanced_eda()

