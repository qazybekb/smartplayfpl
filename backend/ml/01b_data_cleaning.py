"""
Step 1b: Data Cleaning for FPL ML Model
=======================================

This script performs data quality checks and cleaning:
1. Check for missing values
2. Detect and handle duplicates
3. Validate data types
4. Check value ranges (sanity checks)
5. Identify data inconsistencies
6. Handle anomalies
7. Create clean dataset

Should run BEFORE EDA!

Usage:
    cd backend
    python ml/01b_data_cleaning.py

Output:
    ml/data/fpl_gameweek_data_clean.csv
    ml/data/data_cleaning_report.md
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILE = DATA_DIR / "fpl_gameweek_data.csv"
OUTPUT_FILE = DATA_DIR / "fpl_gameweek_data_clean.csv"
REPORT_FILE = DATA_DIR / "data_cleaning_report.md"


def load_data():
    """Load the raw collected data."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {INPUT_FILE}")
    return pd.read_csv(INPUT_FILE)


def check_missing_values(df: pd.DataFrame) -> tuple:
    """Check for missing values."""
    output = []
    output.append("## 1. Missing Values Analysis\n")
    
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    
    missing_df = pd.DataFrame({
        "Column": missing.index,
        "Missing Count": missing.values,
        "Missing %": missing_pct.values
    })
    missing_df = missing_df[missing_df["Missing Count"] > 0]
    
    if len(missing_df) == 0:
        output.append("✅ **No missing values found!**\n")
        issues = []
    else:
        output.append("⚠️ **Missing values detected:**\n")
        output.append("| Column | Missing Count | Missing % |")
        output.append("|--------|---------------|-----------|")
        for _, row in missing_df.iterrows():
            output.append(f"| {row['Column']} | {row['Missing Count']} | {row['Missing %']}% |")
        output.append("")
        issues = missing_df.to_dict('records')
    
    return "\n".join(output), issues


def check_duplicates(df: pd.DataFrame) -> tuple:
    """Check for duplicate records."""
    output = []
    output.append("## 2. Duplicate Records Analysis\n")
    
    # Check for exact duplicates
    exact_dupes = df.duplicated().sum()
    
    # Check for duplicates on key columns (player + gameweek should be unique)
    key_dupes = df.duplicated(subset=["player_id", "gameweek"]).sum()
    
    output.append(f"- **Exact duplicate rows**: {exact_dupes}")
    output.append(f"- **Duplicate (player_id, gameweek) pairs**: {key_dupes}")
    output.append("")
    
    if exact_dupes == 0 and key_dupes == 0:
        output.append("✅ **No duplicates found!**\n")
        issues = []
    else:
        output.append("⚠️ **Duplicates detected - will be removed**\n")
        if key_dupes > 0:
            dupes = df[df.duplicated(subset=["player_id", "gameweek"], keep=False)]
            output.append("Sample duplicates:")
            output.append("```")
            output.append(dupes[["player_name", "gameweek", "total_points"]].head(10).to_string())
            output.append("```")
        issues = [{"exact_dupes": exact_dupes, "key_dupes": key_dupes}]
    
    return "\n".join(output), issues


def check_data_types(df: pd.DataFrame) -> tuple:
    """Check and validate data types."""
    output = []
    output.append("## 3. Data Types Validation\n")
    
    expected_types = {
        # IDs should be integers
        "player_id": "int",
        "team_id": "int",
        "opponent_team_id": "int",
        "gameweek": "int",
        
        # Boolean
        "was_home": "bool",
        
        # Integers (counts)
        "total_points": "int",
        "minutes": "int",
        "goals_scored": "int",
        "assists": "int",
        "clean_sheets": "int",
        "goals_conceded": "int",
        "bonus": "int",
        "bps": "int",
        "yellow_cards": "int",
        "red_cards": "int",
        "saves": "int",
        
        # Floats
        "influence": "float",
        "creativity": "float",
        "threat": "float",
        "ict_index": "float",
        "expected_goals": "float",
        "expected_assists": "float",
        "value": "float",
    }
    
    issues = []
    output.append("| Column | Expected | Actual | Status |")
    output.append("|--------|----------|--------|--------|")
    
    for col, expected in expected_types.items():
        if col not in df.columns:
            output.append(f"| {col} | {expected} | MISSING | ❌ |")
            issues.append({"column": col, "issue": "missing"})
            continue
        
        actual = str(df[col].dtype)
        
        if expected == "int" and "int" in actual:
            status = "✅"
        elif expected == "float" and "float" in actual:
            status = "✅"
        elif expected == "bool" and "bool" in actual:
            status = "✅"
        elif expected == "int" and "float" in actual:
            # Float where int expected - check if all are whole numbers
            if df[col].dropna().apply(lambda x: x == int(x)).all():
                status = "⚠️ (can convert)"
            else:
                status = "❌"
                issues.append({"column": col, "issue": f"expected {expected}, got {actual}"})
        else:
            status = "⚠️"
        
        output.append(f"| {col} | {expected} | {actual} | {status} |")
    
    output.append("")
    
    if not issues:
        output.append("✅ **All data types are valid!**\n")
    
    return "\n".join(output), issues


def check_value_ranges(df: pd.DataFrame) -> tuple:
    """Sanity check value ranges."""
    output = []
    output.append("## 4. Value Range Validation\n")
    
    issues = []
    
    # Define expected ranges
    validations = [
        ("gameweek", 1, 38, "Gameweek should be 1-38"),
        ("minutes", 0, 120, "Minutes should be 0-120"),
        ("total_points", -10, 30, "Points typically -10 to 30"),
        ("goals_scored", 0, 10, "Goals should be 0-10"),
        ("assists", 0, 10, "Assists should be 0-10"),
        ("bonus", 0, 3, "Bonus should be 0-3"),
        ("yellow_cards", 0, 2, "Yellow cards should be 0-2"),
        ("red_cards", 0, 1, "Red cards should be 0-1"),
        ("clean_sheets", 0, 1, "Clean sheets should be 0-1"),
        ("expected_goals", 0, 5, "xG should be 0-5"),
        ("expected_assists", 0, 3, "xA should be 0-3"),
        ("value", 3.5, 20, "Price should be 3.5-20m"),
        ("ict_index", 0, 50, "ICT should be 0-50"),
    ]
    
    output.append("| Column | Min | Max | Expected Range | Status |")
    output.append("|--------|-----|-----|----------------|--------|")
    
    for col, exp_min, exp_max, desc in validations:
        if col not in df.columns:
            continue
        
        actual_min = df[col].min()
        actual_max = df[col].max()
        
        violations = ((df[col] < exp_min) | (df[col] > exp_max)).sum()
        
        if violations == 0:
            status = "✅"
        else:
            status = f"⚠️ {violations} violations"
            issues.append({
                "column": col,
                "expected_range": f"{exp_min}-{exp_max}",
                "actual_range": f"{actual_min}-{actual_max}",
                "violations": violations
            })
        
        output.append(f"| {col} | {actual_min} | {actual_max} | {exp_min}-{exp_max} | {status} |")
    
    output.append("")
    
    if not issues:
        output.append("✅ **All values within expected ranges!**\n")
    else:
        output.append(f"⚠️ **{len(issues)} columns have out-of-range values**\n")
    
    return "\n".join(output), issues


def check_consistency(df: pd.DataFrame) -> tuple:
    """Check for data consistency issues."""
    output = []
    output.append("## 5. Data Consistency Checks\n")
    
    issues = []
    
    # Check 1: If minutes = 0, points should be 0 (unless transferred out mid-game)
    zero_mins_nonzero_pts = df[(df["minutes"] == 0) & (df["total_points"] != 0)]
    output.append(f"### Minutes = 0 but Points ≠ 0")
    output.append(f"- Count: {len(zero_mins_nonzero_pts)}")
    if len(zero_mins_nonzero_pts) > 0:
        output.append("- Sample:")
        output.append("```")
        output.append(zero_mins_nonzero_pts[["player_name", "gameweek", "minutes", "total_points"]].head(5).to_string())
        output.append("```")
        issues.append({"check": "zero_mins_nonzero_pts", "count": len(zero_mins_nonzero_pts)})
    output.append("")
    
    # Check 2: Goals/assists should be 0 if minutes = 0
    zero_mins_with_goals = df[(df["minutes"] == 0) & (df["goals_scored"] > 0)]
    output.append(f"### Minutes = 0 but Goals > 0")
    output.append(f"- Count: {len(zero_mins_with_goals)}")
    if len(zero_mins_with_goals) > 0:
        issues.append({"check": "zero_mins_with_goals", "count": len(zero_mins_with_goals)})
    output.append("")
    
    # Check 3: Clean sheet only if goals_conceded = 0
    cs_with_goals_conceded = df[(df["clean_sheets"] == 1) & (df["goals_conceded"] > 0)]
    output.append(f"### Clean Sheet = 1 but Goals Conceded > 0")
    output.append(f"- Count: {len(cs_with_goals_conceded)}")
    if len(cs_with_goals_conceded) > 0:
        issues.append({"check": "cs_with_goals_conceded", "count": len(cs_with_goals_conceded)})
    output.append("")
    
    # Check 4: Each player should appear once per gameweek
    player_gw_counts = df.groupby(["player_id", "gameweek"]).size()
    multiple_appearances = player_gw_counts[player_gw_counts > 1]
    output.append(f"### Players appearing multiple times in same GW")
    output.append(f"- Count: {len(multiple_appearances)}")
    if len(multiple_appearances) > 0:
        issues.append({"check": "multiple_appearances", "count": len(multiple_appearances)})
    output.append("")
    
    # Check 5: Player names should be consistent
    name_variations = df.groupby("player_id")["player_name"].nunique()
    inconsistent_names = name_variations[name_variations > 1]
    output.append(f"### Players with inconsistent names")
    output.append(f"- Count: {len(inconsistent_names)}")
    if len(inconsistent_names) > 0:
        for pid in inconsistent_names.index[:5]:
            names = df[df["player_id"] == pid]["player_name"].unique()
            output.append(f"  - Player {pid}: {names}")
        issues.append({"check": "inconsistent_names", "count": len(inconsistent_names)})
    output.append("")
    
    if not issues:
        output.append("✅ **All consistency checks passed!**\n")
    else:
        output.append(f"⚠️ **{len(issues)} consistency issues found**\n")
    
    return "\n".join(output), issues


def check_outliers(df: pd.DataFrame) -> tuple:
    """Identify statistical outliers."""
    output = []
    output.append("## 6. Statistical Outliers\n")
    
    numeric_cols = ["total_points", "minutes", "goals_scored", "assists", 
                    "bonus", "bps", "ict_index", "expected_goals"]
    
    output.append("| Column | Q1 | Q3 | IQR | Lower | Upper | Outliers |")
    output.append("|--------|-----|-----|-----|-------|-------|----------|")
    
    outlier_info = []
    
    for col in numeric_cols:
        if col not in df.columns:
            continue
        
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        
        outliers = ((df[col] < lower) | (df[col] > upper)).sum()
        outlier_pct = outliers / len(df) * 100
        
        output.append(f"| {col} | {Q1:.1f} | {Q3:.1f} | {IQR:.1f} | {lower:.1f} | {upper:.1f} | {outliers} ({outlier_pct:.1f}%) |")
        
        if outliers > 0:
            outlier_info.append({
                "column": col,
                "count": outliers,
                "percentage": outlier_pct,
                "lower_bound": lower,
                "upper_bound": upper
            })
    
    output.append("")
    output.append("**Note**: Outliers are expected in FPL (hat-tricks, red cards). Review but don't automatically remove.\n")
    
    return "\n".join(output), outlier_info


def clean_data(df: pd.DataFrame) -> tuple:
    """Apply cleaning transformations."""
    output = []
    output.append("## 7. Cleaning Actions Taken\n")
    
    original_len = len(df)
    df_clean = df.copy()
    actions = []
    
    # Action 1: Remove exact duplicates
    dupes_before = df_clean.duplicated().sum()
    if dupes_before > 0:
        df_clean = df_clean.drop_duplicates()
        actions.append(f"- Removed {dupes_before} exact duplicate rows")
    
    # Action 2: Remove duplicate (player_id, gameweek) - keep first
    key_dupes = df_clean.duplicated(subset=["player_id", "gameweek"]).sum()
    if key_dupes > 0:
        df_clean = df_clean.drop_duplicates(subset=["player_id", "gameweek"], keep="first")
        actions.append(f"- Removed {key_dupes} duplicate (player_id, gameweek) rows")
    
    # Action 3: Convert float columns that should be int
    int_cols = ["goals_scored", "assists", "clean_sheets", "goals_conceded",
                "bonus", "yellow_cards", "red_cards", "saves", "own_goals",
                "penalties_saved", "penalties_missed", "starts"]
    for col in int_cols:
        if col in df_clean.columns and df_clean[col].dtype == "float64":
            df_clean[col] = df_clean[col].fillna(0).astype(int)
    actions.append(f"- Converted {len(int_cols)} float columns to int")
    
    # Action 4: Fill missing xG/xA with 0 (some players may not have)
    xg_cols = ["expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded"]
    for col in xg_cols:
        if col in df_clean.columns:
            missing_before = df_clean[col].isnull().sum()
            if missing_before > 0:
                df_clean[col] = df_clean[col].fillna(0)
                actions.append(f"- Filled {missing_before} missing values in {col} with 0")
    
    # Action 5: Ensure boolean types
    if "was_home" in df_clean.columns:
        df_clean["was_home"] = df_clean["was_home"].astype(bool)
        actions.append("- Converted was_home to boolean")
    
    # Summary
    final_len = len(df_clean)
    rows_removed = original_len - final_len
    
    output.append(f"**Original rows**: {original_len:,}")
    output.append(f"**Final rows**: {final_len:,}")
    output.append(f"**Rows removed**: {rows_removed}")
    output.append("")
    output.append("**Actions performed:**")
    for action in actions:
        output.append(action)
    output.append("")
    
    return "\n".join(output), df_clean


def run_data_cleaning():
    """Run complete data cleaning pipeline."""
    print("=" * 60)
    print("FPL ML DATA CLEANING")
    print("=" * 60)
    print()
    
    # Load data
    print("📥 Loading raw data...")
    df = load_data()
    print(f"   Loaded {len(df):,} records")
    print()
    
    # Generate report
    sections = []
    sections.append("# FPL ML - Data Cleaning Report\n")
    sections.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    sections.append("---\n")
    
    # Run all checks
    print("🔍 Running data quality checks...")
    
    section, issues = check_missing_values(df)
    sections.append(section)
    print(f"   ✓ Missing values check")
    
    section, issues = check_duplicates(df)
    sections.append(section)
    print(f"   ✓ Duplicate records check")
    
    section, issues = check_data_types(df)
    sections.append(section)
    print(f"   ✓ Data types validation")
    
    section, issues = check_value_ranges(df)
    sections.append(section)
    print(f"   ✓ Value range validation")
    
    section, issues = check_consistency(df)
    sections.append(section)
    print(f"   ✓ Consistency checks")
    
    section, outliers = check_outliers(df)
    sections.append(section)
    print(f"   ✓ Outlier detection")
    
    # Clean data
    print()
    print("🧹 Cleaning data...")
    section, df_clean = clean_data(df)
    sections.append(section)
    print(f"   ✓ Cleaning complete")
    
    # Save cleaned data
    df_clean.to_csv(OUTPUT_FILE, index=False)
    print()
    print(f"💾 Cleaned data saved to: {OUTPUT_FILE}")
    
    # Save report
    report = "\n".join(sections)
    with open(REPORT_FILE, "w") as f:
        f.write(report)
    print(f"💾 Report saved to: {REPORT_FILE}")
    
    # Print summary
    print()
    print("=" * 60)
    print("DATA CLEANING SUMMARY")
    print("=" * 60)
    print(f"Original records: {len(df):,}")
    print(f"Cleaned records: {len(df_clean):,}")
    print(f"Removed: {len(df) - len(df_clean)}")
    print()
    
    return df_clean


if __name__ == "__main__":
    df_clean = run_data_cleaning()
    print("🎉 Data cleaning complete! Run 02_eda.py next on the clean data.")











