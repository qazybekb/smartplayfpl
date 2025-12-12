#!/usr/bin/env python3
"""
Regenerate ML Models for Squad Builder Integration

This script regenerates the Stage 1 (P(plays)) and Stage 2 (points) models
using the existing cleaned and feature-engineered data.
"""

import os
import pickle
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, roc_auc_score, mean_absolute_error, r2_score

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
MODELS_DIR = SCRIPT_DIR / "models"

# Stage 1 features (for P(plays) prediction)
STAGE1_FEATURES = [
    'games_so_far', 'is_DEF', 'is_FWD', 'is_GKP', 'is_MID', 'is_home',
    'mins_per_game', 'minutes_avg_last5', 'minutes_lag1', 'minutes_lag2',
    'nailedness_score', 'selected_pct', 'start_rate_overall',
    'starts_lag1', 'starts_lag2', 'starts_rate_last3', 'starts_rate_last5',
    'value_millions'
]

# Stage 2 features (for points prediction)
STAGE2_FEATURES = [
    'games_so_far', 'is_DEF', 'is_FWD', 'is_GKP', 'is_MID', 'is_home',
    'mins_per_game', 'minutes_avg_last5', 'nailedness_score',
    'selected_pct', 'start_rate_overall', 'value_millions',
    'points_avg_last5', 'bps_avg_last5', 'ict_index_avg_last5',
    'expected_goals_avg_last5', 'expected_assists_avg_last5'
]


def load_data():
    """Load the feature-engineered data."""
    data_path = DATA_DIR / "feature_engineered_data.csv"
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows from {data_path.name}")
    return df


def prepare_stage1_data(df):
    """Prepare data for Stage 1 model (P(plays) classifier)."""
    # Target: whether player played (>=1 minute)
    if 'target_played' in df.columns:
        y = df['target_played'].values
    else:
        y = (df['minutes'] > 0).astype(int).values

    # Features
    available_features = [f for f in STAGE1_FEATURES if f in df.columns]
    missing = set(STAGE1_FEATURES) - set(available_features)
    if missing:
        print(f"Warning: Missing Stage 1 features: {missing}")

    X = df[available_features].copy()

    # Fill missing values
    X = X.fillna(0)

    print(f"Stage 1 data: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Class distribution: {np.bincount(y)}")

    return X, y, available_features


def prepare_stage2_data(df):
    """Prepare data for Stage 2 model (points prediction)."""
    # Filter to only players who played
    df_played = df[df['minutes'] > 0].copy()

    # Target: points
    if 'target_points' in df.columns:
        y = df_played['target_points'].values
    else:
        y = df_played['points'].values

    # Features
    available_features = [f for f in STAGE2_FEATURES if f in df_played.columns]
    missing = set(STAGE2_FEATURES) - set(available_features)
    if missing:
        print(f"Warning: Missing Stage 2 features: {missing}")

    X = df_played[available_features].copy()
    X = X.fillna(0)

    print(f"Stage 2 data: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Points range: {y.min():.1f} to {y.max():.1f}, mean: {y.mean():.2f}")

    return X, y, available_features


def train_stage1_model(X, y, features):
    """Train Stage 1 Random Forest classifier."""
    print("\n" + "="*50)
    print("Training Stage 1 Model (P(plays) Classifier)")
    print("="*50)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)

    print(f"Accuracy: {accuracy:.3f}")
    print(f"AUC-ROC: {auc:.3f}")

    # Feature importance
    print("\nTop 5 Feature Importances:")
    importances = list(zip(features, model.feature_importances_))
    importances.sort(key=lambda x: x[1], reverse=True)
    for feat, imp in importances[:5]:
        print(f"  {feat}: {imp:.3f}")

    return model, scaler, features


def train_stage2_model(X, y, features):
    """Train Stage 2 Ridge regressor for points prediction."""
    print("\n" + "="*50)
    print("Training Stage 2 Model (Points Predictor)")
    print("="*50)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train Ridge regression
    model = Ridge(alpha=1.0)
    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"MAE: {mae:.3f}")
    print(f"R²: {r2:.3f}")

    return model, scaler, features


def save_models(stage1_model, stage1_scaler, stage1_features,
                stage2_model, stage2_scaler, stage2_features):
    """Save all models using joblib (scikit-learn compatible)."""
    print("\n" + "="*50)
    print("Saving Models")
    print("="*50)

    MODELS_DIR.mkdir(exist_ok=True)

    # Save Stage 1
    joblib.dump(stage1_model, MODELS_DIR / 'stage1_random_forest.pkl')
    joblib.dump(stage1_scaler, MODELS_DIR / 'scaler_stage1.pkl')
    joblib.dump(stage1_features, MODELS_DIR / 'stage1_features.pkl')
    print(f"Saved Stage 1 model to {MODELS_DIR}/stage1_random_forest.pkl")

    # Save Stage 2
    joblib.dump(stage2_model, MODELS_DIR / 'stage2_ridge.pkl')
    joblib.dump(stage2_scaler, MODELS_DIR / 'scaler_stage2.pkl')
    joblib.dump(stage2_features, MODELS_DIR / 'stage2_features.pkl')
    print(f"Saved Stage 2 model to {MODELS_DIR}/stage2_ridge.pkl")

    # Verify saved files
    print("\nVerifying saved files...")
    for fname in ['stage1_random_forest.pkl', 'scaler_stage1.pkl', 'stage1_features.pkl',
                  'stage2_ridge.pkl', 'scaler_stage2.pkl', 'stage2_features.pkl']:
        fpath = MODELS_DIR / fname
        try:
            obj = joblib.load(fpath)
            print(f"  ✅ {fname}: {type(obj).__name__}")
        except Exception as e:
            print(f"  ❌ {fname}: {e}")


def main():
    """Main function to regenerate all models."""
    print("="*60)
    print("FPL ML Model Regeneration Script")
    print("="*60)

    # Load data
    df = load_data()

    # Train Stage 1 (P(plays))
    X1, y1, features1 = prepare_stage1_data(df)
    stage1_model, stage1_scaler, stage1_features = train_stage1_model(X1, y1, features1)

    # Train Stage 2 (points)
    X2, y2, features2 = prepare_stage2_data(df)
    stage2_model, stage2_scaler, stage2_features = train_stage2_model(X2, y2, features2)

    # Save models
    save_models(
        stage1_model, stage1_scaler, stage1_features,
        stage2_model, stage2_scaler, stage2_features
    )

    print("\n" + "="*60)
    print("Model regeneration complete!")
    print("="*60)


if __name__ == "__main__":
    main()
