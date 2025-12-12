"""
Step 2: Exploratory Data Analysis (EDA) for FPL ML Model
========================================================

This script analyzes the collected FPL data to understand:
- Distribution of points
- Correlations between features and target
- Missing values
- Position-specific patterns
- Home vs Away effects

Usage:
    cd backend
    python ml/02_eda.py

Prerequisites:
    Run 01_data_collection.py first

Output:
    ml/data/eda_report.md
    ml/data/correlation_matrix.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

# Configuration
DATA_DIR = Path(__file__).parent / "data"
# Use CLEAN data (after data cleaning step)
INPUT_FILE = DATA_DIR / "fpl_gameweek_data_clean.csv"


def load_data():
    """Load the collected data."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Data file not found: {INPUT_FILE}\n"
            "Run 01_data_collection.py first!"
        )
    return pd.read_csv(INPUT_FILE)


def basic_stats(df: pd.DataFrame) -> str:
    """Generate basic statistics."""
    output = []
    output.append("## 1. Basic Statistics\n")
    output.append(f"- **Total records**: {len(df):,}")
    output.append(f"- **Unique players**: {df['player_id'].nunique()}")
    output.append(f"- **Gameweeks**: {df['gameweek'].min()} to {df['gameweek'].max()}")
    output.append(f"- **Total columns**: {len(df.columns)}")
    output.append("")
    
    # Position breakdown
    output.append("### Records by Position\n")
    output.append("| Position | Count | % |")
    output.append("|----------|-------|---|")
    pos_counts = df.groupby("position").size()
    for pos, count in pos_counts.items():
        pct = count / len(df) * 100
        output.append(f"| {pos} | {count:,} | {pct:.1f}% |")
    output.append("")
    
    return "\n".join(output)


def target_analysis(df: pd.DataFrame) -> str:
    """Analyze the target variable (total_points)."""
    output = []
    output.append("## 2. Target Variable Analysis (total_points)\n")
    
    points = df["total_points"]
    
    output.append("### Distribution Statistics\n")
    output.append(f"- **Mean**: {points.mean():.2f}")
    output.append(f"- **Median**: {points.median():.2f}")
    output.append(f"- **Std Dev**: {points.std():.2f}")
    output.append(f"- **Min**: {points.min()}")
    output.append(f"- **Max**: {points.max()}")
    output.append(f"- **Skewness**: {points.skew():.2f}")
    output.append("")
    
    # Points distribution buckets
    output.append("### Points Distribution\n")
    output.append("| Points Range | Count | % |")
    output.append("|--------------|-------|---|")
    
    buckets = [
        ("0 points", points == 0),
        ("1-2 points", (points >= 1) & (points <= 2)),
        ("3-5 points", (points >= 3) & (points <= 5)),
        ("6-9 points", (points >= 6) & (points <= 9)),
        ("10-14 points", (points >= 10) & (points <= 14)),
        ("15+ points", points >= 15),
    ]
    
    for label, mask in buckets:
        count = mask.sum()
        pct = count / len(df) * 100
        output.append(f"| {label} | {count:,} | {pct:.1f}% |")
    output.append("")
    
    # Zero points analysis
    zero_count = (points == 0).sum()
    zero_pct = zero_count / len(df) * 100
    output.append(f"### Zero Points Analysis\n")
    output.append(f"- **Players with 0 points**: {zero_count:,} ({zero_pct:.1f}%)")
    
    # Of those with 0 points, how many had 0 minutes?
    zero_points_df = df[df["total_points"] == 0]
    zero_minutes = (zero_points_df["minutes"] == 0).sum()
    zero_minutes_pct = zero_minutes / len(zero_points_df) * 100 if len(zero_points_df) > 0 else 0
    output.append(f"- **Of those, 0 minutes played**: {zero_minutes:,} ({zero_minutes_pct:.1f}%)")
    output.append("")
    
    # Points by position
    output.append("### Average Points by Position\n")
    output.append("| Position | Mean | Median | Std | Max |")
    output.append("|----------|------|--------|-----|-----|")
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_points = df[df["position"] == pos]["total_points"]
        output.append(f"| {pos} | {pos_points.mean():.2f} | {pos_points.median():.1f} | {pos_points.std():.2f} | {pos_points.max()} |")
    output.append("")
    
    return "\n".join(output)


def minutes_analysis(df: pd.DataFrame) -> str:
    """Analyze minutes played."""
    output = []
    output.append("## 3. Minutes Analysis\n")
    
    minutes = df["minutes"]
    
    output.append("### Minutes Distribution\n")
    output.append("| Minutes Range | Count | % | Avg Points |")
    output.append("|---------------|-------|---|------------|")
    
    buckets = [
        ("0 mins (didn't play)", minutes == 0),
        ("1-45 mins (sub)", (minutes >= 1) & (minutes <= 45)),
        ("46-60 mins", (minutes >= 46) & (minutes <= 60)),
        ("61-89 mins", (minutes >= 61) & (minutes <= 89)),
        ("90 mins (full)", minutes == 90),
        ("90+ mins (extra time)", minutes > 90),
    ]
    
    for label, mask in buckets:
        count = mask.sum()
        pct = count / len(df) * 100
        avg_pts = df.loc[mask, "total_points"].mean() if mask.sum() > 0 else 0
        output.append(f"| {label} | {count:,} | {pct:.1f}% | {avg_pts:.2f} |")
    output.append("")
    
    # Correlation between minutes and points
    corr = df["minutes"].corr(df["total_points"])
    output.append(f"**Correlation (minutes vs points)**: {corr:.3f}")
    output.append("")
    
    return "\n".join(output)


def home_away_analysis(df: pd.DataFrame) -> str:
    """Analyze home vs away performance."""
    output = []
    output.append("## 4. Home vs Away Analysis\n")
    
    home = df[df["was_home"] == True]
    away = df[df["was_home"] == False]
    
    output.append("| Metric | Home | Away | Difference |")
    output.append("|--------|------|------|------------|")
    
    metrics = [
        ("Average Points", "total_points", "mean"),
        ("Avg Goals Scored", "goals_scored", "mean"),
        ("Avg Assists", "assists", "mean"),
        ("Avg Clean Sheets", "clean_sheets", "mean"),
        ("Avg Bonus", "bonus", "mean"),
    ]
    
    for label, col, agg in metrics:
        home_val = getattr(home[col], agg)()
        away_val = getattr(away[col], agg)()
        diff = home_val - away_val
        diff_pct = (diff / away_val * 100) if away_val != 0 else 0
        output.append(f"| {label} | {home_val:.3f} | {away_val:.3f} | {diff:+.3f} ({diff_pct:+.1f}%) |")
    output.append("")
    
    # Statistical significance
    t_stat, p_value = stats.ttest_ind(home["total_points"], away["total_points"])
    output.append(f"**T-test (home vs away points)**: t={t_stat:.3f}, p={p_value:.4f}")
    if p_value < 0.05:
        output.append("→ **Statistically significant difference** (p < 0.05)")
    else:
        output.append("→ Not statistically significant (p ≥ 0.05)")
    output.append("")
    
    return "\n".join(output)


def correlation_analysis(df: pd.DataFrame) -> tuple:
    """Analyze correlations with target variable."""
    output = []
    output.append("## 5. Feature Correlations with Points\n")
    
    # Select numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Remove ID columns
    exclude = ["player_id", "team_id", "opponent_team_id", "gameweek"]
    numeric_cols = [c for c in numeric_cols if c not in exclude]
    
    # Calculate correlations with target
    correlations = {}
    for col in numeric_cols:
        if col != "total_points":
            corr = df[col].corr(df["total_points"])
            correlations[col] = corr
    
    # Sort by absolute correlation
    sorted_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
    
    output.append("### Top Correlations with total_points\n")
    output.append("| Feature | Correlation | Interpretation |")
    output.append("|---------|-------------|----------------|")
    
    for col, corr in sorted_corrs[:20]:
        if abs(corr) >= 0.3:
            strength = "Strong"
        elif abs(corr) >= 0.15:
            strength = "Moderate"
        else:
            strength = "Weak"
        
        direction = "+" if corr > 0 else "-"
        output.append(f"| {col} | {corr:+.3f} | {strength} {direction} |")
    output.append("")
    
    # Create correlation matrix for key features
    key_features = [
        "total_points", "minutes", "goals_scored", "assists", "clean_sheets",
        "bonus", "bps", "influence", "creativity", "threat", "ict_index",
        "expected_goals", "expected_assists", "value"
    ]
    key_features = [f for f in key_features if f in df.columns]
    
    corr_matrix = df[key_features].corr()
    
    return "\n".join(output), corr_matrix


def xg_analysis(df: pd.DataFrame) -> str:
    """Analyze expected goals/assists."""
    output = []
    output.append("## 6. Expected Stats Analysis (xG, xA)\n")
    
    # Filter to non-zero xG/xA
    with_xg = df[df["expected_goals"] > 0]
    
    output.append(f"### xG Coverage\n")
    output.append(f"- Records with xG > 0: {len(with_xg):,} ({len(with_xg)/len(df)*100:.1f}%)")
    output.append("")
    
    # Correlation
    xg_corr = df["expected_goals"].corr(df["goals_scored"])
    xa_corr = df["expected_assists"].corr(df["assists"])
    xgi_corr = df["expected_goal_involvements"].corr(df["total_points"])
    
    output.append("### xG/xA Correlations\n")
    output.append(f"- **xG vs Actual Goals**: {xg_corr:.3f}")
    output.append(f"- **xA vs Actual Assists**: {xa_corr:.3f}")
    output.append(f"- **xGI vs Total Points**: {xgi_corr:.3f}")
    output.append("")
    
    # Over/under performance
    if len(with_xg) > 0:
        avg_xg = with_xg["expected_goals"].mean()
        avg_goals = with_xg["goals_scored"].mean()
        output.append(f"### Over/Under Performance\n")
        output.append(f"- Average xG: {avg_xg:.3f}")
        output.append(f"- Average Goals: {avg_goals:.3f}")
        output.append(f"- Difference: {avg_goals - avg_xg:+.3f} (players {'over' if avg_goals > avg_xg else 'under'}performing)")
    output.append("")
    
    return "\n".join(output)


def ict_analysis(df: pd.DataFrame) -> str:
    """Analyze ICT Index."""
    output = []
    output.append("## 7. ICT Index Analysis\n")
    
    output.append("### ICT Components Correlation with Points\n")
    output.append("| Component | Correlation |")
    output.append("|-----------|-------------|")
    
    for col in ["influence", "creativity", "threat", "ict_index"]:
        corr = df[col].corr(df["total_points"])
        output.append(f"| {col.title()} | {corr:+.3f} |")
    output.append("")
    
    # ICT by position
    output.append("### Average ICT by Position\n")
    output.append("| Position | Influence | Creativity | Threat | ICT Index |")
    output.append("|----------|-----------|------------|--------|-----------|")
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = df[df["position"] == pos]
        output.append(f"| {pos} | {pos_df['influence'].mean():.1f} | {pos_df['creativity'].mean():.1f} | {pos_df['threat'].mean():.1f} | {pos_df['ict_index'].mean():.1f} |")
    output.append("")
    
    return "\n".join(output)


def bonus_analysis(df: pd.DataFrame) -> str:
    """Analyze bonus points."""
    output = []
    output.append("## 8. Bonus Points Analysis\n")
    
    bonus = df["bonus"]
    
    output.append("### Bonus Distribution\n")
    output.append("| Bonus | Count | % |")
    output.append("|-------|-------|---|")
    for b in [0, 1, 2, 3]:
        count = (bonus == b).sum()
        pct = count / len(df) * 100
        output.append(f"| {b} | {count:,} | {pct:.1f}% |")
    output.append("")
    
    # BPS correlation
    bps_corr = df["bps"].corr(df["bonus"])
    output.append(f"**BPS vs Bonus Correlation**: {bps_corr:.3f}")
    output.append("")
    
    # Avg bonus by position
    output.append("### Average Bonus by Position\n")
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        avg = df[df["position"] == pos]["bonus"].mean()
        output.append(f"- {pos}: {avg:.3f}")
    output.append("")
    
    return "\n".join(output)


def missing_values_analysis(df: pd.DataFrame) -> str:
    """Check for missing values."""
    output = []
    output.append("## 9. Missing Values Analysis\n")
    
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    
    if len(missing) == 0:
        output.append("✅ **No missing values found!**")
    else:
        output.append("| Column | Missing Count | % |")
        output.append("|--------|---------------|---|")
        for col, count in missing.items():
            pct = count / len(df) * 100
            output.append(f"| {col} | {count:,} | {pct:.1f}% |")
    output.append("")
    
    return "\n".join(output)


def key_insights(df: pd.DataFrame) -> str:
    """Generate key insights summary."""
    output = []
    output.append("## 10. Key Insights for Modeling\n")
    
    # Calculate key metrics
    zero_pct = (df["total_points"] == 0).sum() / len(df) * 100
    zero_mins_pct = (df["minutes"] == 0).sum() / len(df) * 100
    home_avg = df[df["was_home"]]["total_points"].mean()
    away_avg = df[~df["was_home"]]["total_points"].mean()
    
    # Top correlations
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    correlations = {c: df[c].corr(df["total_points"]) for c in numeric_cols if c != "total_points"}
    top_corrs = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    
    output.append("### Findings\n")
    output.append(f"1. **{zero_pct:.1f}% of records have 0 points** - mostly due to not playing ({zero_mins_pct:.1f}% had 0 minutes)")
    output.append(f"2. **Home advantage exists**: {home_avg:.2f} avg pts at home vs {away_avg:.2f} away (+{home_avg-away_avg:.2f})")
    output.append(f"3. **Top predictors**: {', '.join([f'{c[0]} ({c[1]:+.2f})' for c in top_corrs])}")
    output.append(f"4. **Target is right-skewed**: Mean {df['total_points'].mean():.2f}, Median {df['total_points'].median():.0f}")
    output.append("")
    
    output.append("### Recommendations\n")
    output.append("1. **Filter out 0-minute records** for training (no signal)")
    output.append("2. **Include home/away as feature** (significant effect)")
    output.append("3. **Use ICT components** - strong correlation with points")
    output.append("4. **Create rolling features** (form_3gw, form_5gw)")
    output.append("5. **Consider position-specific models** or strong position features")
    output.append("")
    
    return "\n".join(output)


def run_eda():
    """Run complete EDA."""
    print("=" * 60)
    print("FPL ML EXPLORATORY DATA ANALYSIS")
    print("=" * 60)
    print()
    
    # Load data
    print("📥 Loading data...")
    df = load_data()
    print(f"   Loaded {len(df):,} records")
    print()
    
    # Generate report sections
    print("📊 Analyzing data...")
    
    sections = []
    sections.append("# FPL ML - Exploratory Data Analysis Report\n")
    sections.append(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*\n")
    sections.append("---\n")
    
    sections.append(basic_stats(df))
    print("   ✓ Basic statistics")
    
    sections.append(target_analysis(df))
    print("   ✓ Target variable analysis")
    
    sections.append(minutes_analysis(df))
    print("   ✓ Minutes analysis")
    
    sections.append(home_away_analysis(df))
    print("   ✓ Home vs away analysis")
    
    corr_section, corr_matrix = correlation_analysis(df)
    sections.append(corr_section)
    print("   ✓ Correlation analysis")
    
    sections.append(xg_analysis(df))
    print("   ✓ xG/xA analysis")
    
    sections.append(ict_analysis(df))
    print("   ✓ ICT analysis")
    
    sections.append(bonus_analysis(df))
    print("   ✓ Bonus analysis")
    
    sections.append(missing_values_analysis(df))
    print("   ✓ Missing values check")
    
    sections.append(key_insights(df))
    print("   ✓ Key insights")
    
    # Save report
    report = "\n".join(sections)
    report_path = DATA_DIR / "eda_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print()
    print(f"💾 Report saved to: {report_path}")
    
    # Save correlation matrix
    corr_path = DATA_DIR / "correlation_matrix.csv"
    corr_matrix.to_csv(corr_path)
    print(f"💾 Correlation matrix saved to: {corr_path}")
    
    # Print summary to console
    print()
    print("=" * 60)
    print("QUICK SUMMARY")
    print("=" * 60)
    print(f"Total records: {len(df):,}")
    print(f"Records with 0 points: {(df['total_points'] == 0).sum():,} ({(df['total_points'] == 0).sum()/len(df)*100:.1f}%)")
    print(f"Records with 0 minutes: {(df['minutes'] == 0).sum():,}")
    print(f"Home avg points: {df[df['was_home']]['total_points'].mean():.2f}")
    print(f"Away avg points: {df[~df['was_home']]['total_points'].mean():.2f}")
    print()
    print("Top 5 correlations with points:")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    correlations = {c: df[c].corr(df["total_points"]) for c in numeric_cols if c != "total_points"}
    for col, corr in sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
        print(f"  {col}: {corr:+.3f}")
    
    print()
    print("🎉 EDA complete! Check eda_report.md for full analysis.")
    
    return df, report


if __name__ == "__main__":
    df, report = run_eda()

