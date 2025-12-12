"""
Database configuration and models for SmartPlayFPL
Uses SQLite for simplicity and portability

Data Architecture Improvements:
- Compound indexes for common query patterns
- CheckConstraints for data validation
- Unique constraints to prevent duplicates
- Default values for nullable columns
"""

from sqlalchemy import (
    create_engine, Column, Integer, Float, String, DateTime, Boolean,
    Index, UniqueConstraint, CheckConstraint, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# Database URL - using SQLite (supports PostgreSQL for production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smartplayfpl.db")

# Railway provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    logger.info("Converted Railway postgres:// URL to postgresql://")

# Connection pool settings (configurable via environment)
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes

# Create engine with connection pooling
if "sqlite" in DATABASE_URL:
    # SQLite doesn't support connection pooling the same way
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,  # Verify connections before use
    )
    logger.info("Using SQLite database (no connection pooling)")
else:
    # PostgreSQL/MySQL with full connection pooling
    engine = create_engine(
        DATABASE_URL,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
        pool_pre_ping=True,  # Verify connections before use
        echo=os.getenv("DB_ECHO", "false").lower() == "true",  # SQL logging
    )
    logger.info(f"Database pool configured: size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}")

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# =========================================================================
# Models
# =========================================================================

class MLPlayerScore(Base):
    """
    Stores pre-calculated ML scores for all players.
    Updated periodically (e.g., daily or when fixtures change).
    """
    __tablename__ = "ml_player_scores"
    __table_args__ = (
        # Compound indexes for common query patterns
        Index('ix_ml_scores_gw_position', 'gameweek', 'position'),
        Index('ix_ml_scores_gw_team', 'gameweek', 'team_id'),
        Index('ix_ml_scores_gw_rank', 'gameweek', 'rank'),
        # Data validation constraints
        CheckConstraint('final_score >= 0 AND final_score <= 10', name='ck_final_score_range'),
        CheckConstraint('nailedness_score >= 0 AND nailedness_score <= 10', name='ck_nailedness_range'),
        CheckConstraint('form_xg_score >= 0 AND form_xg_score <= 10', name='ck_form_xg_range'),
        CheckConstraint('form_pts_score >= 0 AND form_pts_score <= 10', name='ck_form_pts_range'),
        CheckConstraint('fixture_score >= 0 AND fixture_score <= 10', name='ck_fixture_range'),
        CheckConstraint('price >= 0', name='ck_price_positive'),
        CheckConstraint('ownership >= 0 AND ownership <= 100', name='ck_ownership_range'),
        CheckConstraint('rank >= 1', name='ck_rank_positive'),
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_gameweek_range'),
    )

    # Primary key
    player_id = Column(Integer, primary_key=True, index=True)

    # Player metadata
    name = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    team = Column(String, nullable=False)
    team_id = Column(Integer, nullable=False)
    position = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    ownership = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    news = Column(String, default="")

    # Component scores (0-10 scale)
    nailedness_score = Column(Float, nullable=False)
    form_xg_score = Column(Float, nullable=False)
    form_pts_score = Column(Float, nullable=False)
    fixture_score = Column(Float, nullable=False)  # 5 GW weighted average (for transfers)
    fixture_now_score = Column(Float, nullable=False, default=5.0)  # Next GW only (for captaincy/lineup)

    # Final score (0-10 scale)
    final_score = Column(Float, nullable=False, index=True)

    # Ranking
    rank = Column(Integer, nullable=False, index=True)

    # Additional context
    avg_minutes = Column(Float, nullable=False)
    avg_points = Column(Float, nullable=False)
    total_points = Column(Integer, nullable=False)
    form = Column(Float, nullable=False)
    next_opponent = Column(String, default="")
    next_fdr = Column(Integer, default=3)
    next_home = Column(Boolean, default=False)

    # Metadata
    gameweek = Column(Integer, nullable=False, index=True)
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CalculationLog(Base):
    """
    Tracks when ML scores were calculated.
    Useful for monitoring and debugging.
    """
    __tablename__ = "calculation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gameweek = Column(Integer, nullable=False, index=True)
    players_scored = Column(Integer, nullable=False)
    elapsed_seconds = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=False)


class APICallLog(Base):
    """
    Logs all API calls for observability and debugging.
    Useful for monitoring endpoint usage, performance, and errors.
    """
    __tablename__ = "api_call_logs"
    __table_args__ = (
        # Compound indexes for common query patterns
        Index('ix_api_logs_created_status', 'created_at', 'status_code'),
        Index('ix_api_logs_path_created', 'path', 'created_at'),
        Index('ix_api_logs_team_created', 'team_id', 'created_at'),
        # Data validation constraints
        CheckConstraint('status_code >= 100 AND status_code < 600', name='ck_valid_status_code'),
        CheckConstraint('response_time_ms >= 0', name='ck_response_time_positive'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Request info
    request_id = Column(String(8), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False, index=True)
    query_params = Column(String, nullable=True)
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Response info
    status_code = Column(Integer, nullable=False, index=True)
    response_time_ms = Column(Float, nullable=False)
    error_code = Column(String(50), nullable=True)
    error_message = Column(String, nullable=True)

    # Context
    team_id = Column(Integer, nullable=True, index=True)  # Extracted from path if present
    is_ai_endpoint = Column(Boolean, default=False, index=True)  # For Claude AI endpoints

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# =========================================================================
# ML Versioning & Accuracy Models
# =========================================================================

class ModelVersion(Base):
    """
    Tracks ML model versions for versioning and rollback capability.
    Each training run creates a new version.
    """
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Version identifier (e.g., "v1", "v2_gw16_2025-12-12")
    version = Column(String(100), nullable=False, unique=True, index=True)

    # Training context
    gameweek = Column(Integer, nullable=False, index=True)
    training_samples = Column(Integer, nullable=False)

    # Model metrics at training time
    r_squared = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)

    # Position-specific MAE
    mae_gkp = Column(Float, nullable=True)
    mae_def = Column(Float, nullable=True)
    mae_mid = Column(Float, nullable=True)
    mae_fwd = Column(Float, nullable=True)

    # Model file paths (relative to ml/models/)
    model_path = Column(String(255), nullable=True)
    scaler_path = Column(String(255), nullable=True)
    config_path = Column(String(255), nullable=True)

    # Model weights (JSON serialized)
    position_weights = Column(String, nullable=True)  # JSON: {"GKP": {...}, "DEF": {...}, ...}

    # Production status
    is_production = Column(Boolean, default=False, index=True)
    is_tested = Column(Boolean, default=False)

    # Timestamps
    trained_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)

    # Notes for manual tracking
    notes = Column(String, nullable=True)


class PredictionLog(Base):
    """
    Logs predictions for each player per gameweek.
    Used to compare predicted vs actual points after GW completes.
    """
    __tablename__ = "prediction_logs"
    __table_args__ = (
        # Unique constraint: one prediction per player per gameweek per model
        UniqueConstraint('model_version', 'gameweek', 'player_id', name='uq_prediction_per_player_gw'),
        # Compound indexes for common query patterns
        Index('ix_predictions_gw_position', 'gameweek', 'position'),
        Index('ix_predictions_validated', 'gameweek', 'validated_at'),
        # Data validation constraints
        CheckConstraint('predicted_score >= 0 AND predicted_score <= 100', name='ck_pred_score_range'),
        CheckConstraint('p_plays >= 0 AND p_plays <= 1', name='ck_p_plays_range'),
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_pred_gw_range'),
        CheckConstraint('actual_minutes IS NULL OR (actual_minutes >= 0 AND actual_minutes <= 120)', name='ck_actual_minutes_range'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiers
    model_version = Column(String(100), nullable=False, index=True)
    gameweek = Column(Integer, nullable=False, index=True)
    player_id = Column(Integer, nullable=False, index=True)

    # Player context
    player_name = Column(String(100), nullable=False)
    position = Column(String(10), nullable=False)
    team_id = Column(Integer, nullable=False)

    # Prediction details
    predicted_score = Column(Float, nullable=False)  # SmartPlay Score (0-100)
    predicted_points = Column(Float, nullable=True)  # Expected GW points
    p_plays = Column(Float, nullable=False)  # Probability of playing

    # Component scores
    nailedness_score = Column(Float, nullable=True)
    form_xg_score = Column(Float, nullable=True)
    form_pts_score = Column(Float, nullable=True)
    fixture_score = Column(Float, nullable=True)

    # Actual outcome (filled after GW completes)
    actual_points = Column(Integer, nullable=True)
    actual_minutes = Column(Integer, nullable=True)
    did_play = Column(Boolean, nullable=True)

    # Error metrics (calculated after GW)
    prediction_error = Column(Float, nullable=True)  # actual - predicted
    absolute_error = Column(Float, nullable=True)  # |actual - predicted|

    # Timestamps
    predicted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)


class AccuracyReport(Base):
    """
    Aggregate accuracy metrics per gameweek per model version.
    Computed after each gameweek completes for performance tracking.
    """
    __tablename__ = "accuracy_reports"
    __table_args__ = (
        # Unique constraint: one report per model per gameweek
        UniqueConstraint('model_version', 'gameweek', name='uq_accuracy_per_model_gw'),
        # Compound index for trend analysis
        Index('ix_accuracy_model_gw', 'model_version', 'gameweek'),
        # Data validation constraints
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_accuracy_gw_range'),
        CheckConstraint('players_evaluated >= 0', name='ck_players_positive'),
        CheckConstraint('overall_mae >= 0', name='ck_mae_positive'),
        CheckConstraint('p_plays_accuracy IS NULL OR (p_plays_accuracy >= 0 AND p_plays_accuracy <= 100)', name='ck_p_plays_acc_range'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiers
    model_version = Column(String(100), nullable=False, index=True)
    gameweek = Column(Integer, nullable=False, index=True)

    # Overall metrics
    players_evaluated = Column(Integer, nullable=False)
    overall_mae = Column(Float, nullable=False)
    overall_rmse = Column(Float, nullable=True)
    overall_r_squared = Column(Float, nullable=True)

    # Position-specific MAE
    mae_gkp = Column(Float, nullable=True)
    mae_def = Column(Float, nullable=True)
    mae_mid = Column(Float, nullable=True)
    mae_fwd = Column(Float, nullable=True)

    # P(plays) accuracy
    p_plays_accuracy = Column(Float, nullable=True)  # % correctly predicted playing/not
    false_positive_rate = Column(Float, nullable=True)  # Predicted play but didn't
    false_negative_rate = Column(Float, nullable=True)  # Predicted not play but did

    # Comparison to previous version
    mae_improvement = Column(Float, nullable=True)  # Positive = better
    previous_version = Column(String(100), nullable=True)

    # Bias detection
    mean_error = Column(Float, nullable=True)  # Systematic over/under prediction

    # Timestamps
    calculated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RetrainingLog(Base):
    """
    Logs automatic retraining events.
    Tracks when models were retrained and why.
    """
    __tablename__ = "retraining_logs"
    __table_args__ = (
        # Compound index for history queries
        Index('ix_retrain_gw_trigger', 'gameweek', 'trigger_type'),
        Index('ix_retrain_success_deployed', 'success', 'deployed'),
        # Data validation constraints
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_retrain_gw_range'),
        CheckConstraint("trigger_type IN ('scheduled', 'manual', 'accuracy_drop')", name='ck_valid_trigger_type'),
        CheckConstraint('duration_seconds IS NULL OR duration_seconds >= 0', name='ck_duration_positive'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trigger information
    gameweek = Column(Integer, nullable=False, index=True)
    trigger_type = Column(String(50), nullable=False)  # "scheduled", "manual", "accuracy_drop"

    # Old vs new version
    old_version = Column(String(100), nullable=True)
    new_version = Column(String(100), nullable=True)

    # Training results
    success = Column(Boolean, nullable=False)
    error_message = Column(String, nullable=True)

    # Performance comparison
    old_mae = Column(Float, nullable=True)
    new_mae = Column(Float, nullable=True)
    improvement_pct = Column(Float, nullable=True)

    # Decision
    deployed = Column(Boolean, default=False)  # Was new model deployed?
    deployment_reason = Column(String, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)


# =========================================================================
# Data Collection & Pipeline Tracking
# =========================================================================

class DataCollectionCheckpoint(Base):
    """
    Tracks data collection progress for idempotent pipelines.
    Enables checkpoint-based resume after failures.
    """
    __tablename__ = "data_collection_checkpoints"
    __table_args__ = (
        UniqueConstraint('pipeline_name', 'gameweek', name='uq_checkpoint_pipeline_gw'),
        Index('ix_checkpoint_status', 'status'),
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_checkpoint_gw_range'),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'failed')", name='ck_valid_checkpoint_status'),
        CheckConstraint('progress_pct >= 0 AND progress_pct <= 100', name='ck_progress_range'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Pipeline identification
    pipeline_name = Column(String(100), nullable=False, index=True)  # e.g., "player_history", "fixture_data"
    gameweek = Column(Integer, nullable=False, index=True)

    # Progress tracking
    status = Column(String(20), nullable=False, default='pending')  # pending, in_progress, completed, failed
    progress_pct = Column(Float, default=0.0)
    items_processed = Column(Integer, default=0)
    items_total = Column(Integer, nullable=True)

    # Checkpoint data (JSON serialized state for resume)
    checkpoint_data = Column(String, nullable=True)  # JSON: {"last_player_id": 123, "batch": 5, ...}

    # Error tracking
    retry_count = Column(Integer, default=0)
    last_error = Column(String, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserFeedback(Base):
    """
    Stores user feedback for features and recommendations.
    Used for analytics and improving the product.
    """
    __tablename__ = "user_feedback"
    __table_args__ = (
        Index('ix_feedback_feature_created', 'feature_type', 'created_at'),
        Index('ix_feedback_team_gw', 'team_id', 'gameweek'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='ck_rating_range'),
        CheckConstraint('would_recommend IS NULL OR (would_recommend >= 0 AND would_recommend <= 10)', name='ck_nps_range'),
        CheckConstraint('gameweek >= 1 AND gameweek <= 38', name='ck_feedback_gw_range'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Context
    team_id = Column(Integer, nullable=False, index=True)
    gameweek = Column(Integer, nullable=False, index=True)
    feature_type = Column(String(50), nullable=False, index=True)  # transfer_advice, captain_picks, lineup, etc.

    # Ratings
    rating = Column(Integer, nullable=False)  # 1-5 stars
    would_recommend = Column(Integer, nullable=True)  # NPS score 0-10

    # Details
    comment = Column(String(1000), nullable=True)
    followed_advice = Column(Boolean, nullable=True)  # Did user follow the advice?

    # Metadata
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class DataLineage(Base):
    """
    Tracks data lineage for audit and debugging.
    Records where data came from and when it was last refreshed.
    """
    __tablename__ = "data_lineage"
    __table_args__ = (
        UniqueConstraint('data_type', 'source_identifier', name='uq_lineage_type_source'),
        Index('ix_lineage_refreshed', 'last_refreshed_at'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Data identification
    data_type = Column(String(50), nullable=False, index=True)  # e.g., "player", "team", "fixture"
    source_identifier = Column(String(100), nullable=False)  # e.g., player_id, team_id, "bootstrap"

    # Source tracking
    source_api = Column(String(100), nullable=False, default='fpl_api')  # fpl_api, understat, etc.
    source_endpoint = Column(String(255), nullable=True)

    # Version tracking
    data_hash = Column(String(64), nullable=True)  # SHA256 of data for change detection
    record_count = Column(Integer, default=0)

    # Timestamps
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_refreshed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_changed_at = Column(DateTime, nullable=True)  # When data actually changed


# =========================================================================
# Database initialization
# =========================================================================

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency for FastAPI routes.
    Provides a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================================
# Helper functions
# =========================================================================

def get_latest_calculation_gameweek(db) -> int | None:
    """Get the gameweek of the most recent calculation."""
    score = db.query(MLPlayerScore).order_by(MLPlayerScore.calculated_at.desc()).first()
    return score.gameweek if score else None


def clear_old_scores(db, gameweek: int):
    """Clear scores from a specific gameweek (for recalculation)."""
    db.query(MLPlayerScore).filter(MLPlayerScore.gameweek == gameweek).delete()
    db.commit()
