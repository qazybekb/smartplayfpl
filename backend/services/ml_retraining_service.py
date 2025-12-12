# backend/services/ml_retraining_service.py
"""
ML Retraining Service for SmartPlayFPL

Handles:
- Automatic model retraining after each gameweek
- Prediction accuracy validation against actual results
- Model versioning and performance tracking
- Continuous improvement of SmartPlay Score
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

from database import (
    SessionLocal, ModelVersion, PredictionLog, AccuracyReport, RetrainingLog
)

logger = logging.getLogger(__name__)


class MLRetrainingService:
    """
    Service for automated ML model retraining and accuracy tracking.

    Key responsibilities:
    1. Log predictions before each gameweek
    2. Validate predictions against actual results
    3. Trigger retraining when accuracy drops
    4. Track model versions and performance over time
    """

    # Accuracy thresholds for triggering retraining
    MAE_THRESHOLD = 3.0  # Trigger retraining if MAE exceeds this
    IMPROVEMENT_THRESHOLD = 0.02  # Deploy new model if 2%+ improvement

    def __init__(self):
        self._fpl_service = None
        self._predictor_service = None
        self._current_version: Optional[str] = None

    def set_services(self, fpl_service, predictor_service=None):
        """Set required services."""
        self._fpl_service = fpl_service
        self._predictor_service = predictor_service

    def _get_current_version(self) -> str:
        """Get the current production model version."""
        if self._current_version:
            return self._current_version

        db = SessionLocal()
        try:
            version = db.query(ModelVersion).filter(
                ModelVersion.is_production == True
            ).order_by(ModelVersion.trained_at.desc()).first()

            if version:
                self._current_version = version.version
            else:
                # Create initial version if none exists
                self._current_version = self._create_initial_version()

            return self._current_version
        finally:
            db.close()

    def _create_initial_version(self) -> str:
        """Create the initial model version entry."""
        db = SessionLocal()
        try:
            version_str = "v1_baseline"

            # Get current gameweek
            gw = 1
            if self._fpl_service:
                gw_obj = self._fpl_service.get_current_gameweek()
                gw = gw_obj.id if hasattr(gw_obj, 'id') else gw_obj

            # Create version entry
            version = ModelVersion(
                version=version_str,
                gameweek=gw,
                training_samples=0,
                is_production=True,
                position_weights=json.dumps({
                    'GKP': {'nailedness': 0.50, 'form_xg': 0.05, 'form_pts': 0.15, 'fixture': 0.30},
                    'DEF': {'nailedness': 0.45, 'form_xg': 0.10, 'form_pts': 0.15, 'fixture': 0.30},
                    'MID': {'nailedness': 0.45, 'form_xg': 0.25, 'form_pts': 0.15, 'fixture': 0.15},
                    'FWD': {'nailedness': 0.45, 'form_xg': 0.30, 'form_pts': 0.15, 'fixture': 0.10},
                }),
                notes="Initial baseline model"
            )
            db.add(version)
            db.commit()

            logger.info(f"Created initial model version: {version_str}")
            return version_str
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create initial version: {e}")
            return "v1_baseline"
        finally:
            db.close()

    async def log_predictions(self, gameweek: int) -> Dict:
        """
        Log predictions for all players for the upcoming gameweek.

        Should be called before each gameweek starts.

        Args:
            gameweek: The upcoming gameweek number

        Returns:
            Summary of logged predictions
        """
        if not self._fpl_service or not self._predictor_service:
            raise ValueError("Services not initialized")

        model_version = self._get_current_version()
        predictions = await self._predictor_service.predict_all_players()

        db = SessionLocal()
        logged = 0

        try:
            # Clear any existing predictions for this GW + version
            db.query(PredictionLog).filter(
                PredictionLog.gameweek == gameweek,
                PredictionLog.model_version == model_version
            ).delete()

            for pred in predictions:
                log = PredictionLog(
                    model_version=model_version,
                    gameweek=gameweek,
                    player_id=pred.player_id,
                    player_name=pred.player_name,
                    position=pred.position,
                    team_id=pred.team_id,
                    predicted_score=pred.ml_score,
                    p_plays=pred.p_plays,
                    nailedness_score=pred.nailedness_score,
                    form_xg_score=pred.form_score_xg,
                    form_pts_score=pred.form_score_pts,
                    fixture_score=pred.fixture_score,
                )
                db.add(log)
                logged += 1

            db.commit()

            logger.info(f"Logged {logged} predictions for GW{gameweek} using model {model_version}")

            return {
                "gameweek": gameweek,
                "model_version": model_version,
                "predictions_logged": logged,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log predictions: {e}")
            raise
        finally:
            db.close()

    async def validate_predictions(self, gameweek: int) -> Dict:
        """
        Validate predictions against actual gameweek results.

        Should be called after gameweek completes.

        Args:
            gameweek: The completed gameweek number

        Returns:
            Accuracy report with metrics
        """
        if not self._fpl_service:
            raise ValueError("FPL service not initialized")

        db = SessionLocal()

        try:
            # Get predictions for this gameweek
            predictions = db.query(PredictionLog).filter(
                PredictionLog.gameweek == gameweek,
                PredictionLog.actual_points.is_(None)  # Not yet validated
            ).all()

            if not predictions:
                return {"error": f"No predictions found for GW{gameweek}"}

            model_version = predictions[0].model_version

            # Fetch actual results from FPL API
            players = self._fpl_service.get_all_players()
            player_data = {p.id: p for p in players}

            # Update predictions with actual results
            errors = []
            position_errors = {'GKP': [], 'DEF': [], 'MID': [], 'FWD': []}
            p_plays_correct = 0
            p_plays_total = 0
            false_positives = 0
            false_negatives = 0

            for pred in predictions:
                player = player_data.get(pred.player_id)
                if not player:
                    continue

                # Get actual points for this GW from player history
                # Note: This assumes we have access to GW-specific data
                actual_points = player.event_points if hasattr(player, 'event_points') else 0
                actual_minutes = player.minutes if hasattr(player, 'minutes') else 0

                # For simplicity, use total points / GW as approximation
                # In production, fetch actual GW history
                gw_obj = self._fpl_service.get_current_gameweek()
                current_gw = gw_obj.id if hasattr(gw_obj, 'id') else gw_obj

                if current_gw > gameweek:
                    # GW has completed, we can use player's latest form as proxy
                    # Ideally, fetch from /api/element-summary/{player_id}
                    form_float = player.form_float or 0
                    actual_points = int(form_float * 2)  # Rough approximation

                did_play = actual_minutes > 0 if actual_minutes else pred.p_plays >= 0.5

                # Calculate error
                # Scale predicted score (0-100) to points (0-20 typical)
                predicted_points = pred.predicted_score / 5  # Rough scaling
                error = actual_points - predicted_points
                abs_error = abs(error)

                # Update prediction log
                pred.actual_points = actual_points
                pred.actual_minutes = actual_minutes
                pred.did_play = did_play
                pred.prediction_error = error
                pred.absolute_error = abs_error
                pred.validated_at = datetime.utcnow()

                errors.append(abs_error)
                position_errors[pred.position].append(abs_error)

                # P(plays) accuracy
                predicted_plays = pred.p_plays >= 0.5
                if predicted_plays == did_play:
                    p_plays_correct += 1
                elif predicted_plays and not did_play:
                    false_positives += 1
                elif not predicted_plays and did_play:
                    false_negatives += 1
                p_plays_total += 1

            db.commit()

            # Calculate aggregate metrics
            mae = np.mean(errors) if errors else 0
            rmse = np.sqrt(np.mean([e**2 for e in errors])) if errors else 0
            mean_error = np.mean([p.prediction_error for p in predictions if p.prediction_error]) if predictions else 0

            # Position-specific MAE
            mae_by_pos = {
                pos: np.mean(errs) if errs else None
                for pos, errs in position_errors.items()
            }

            # P(plays) metrics
            p_plays_accuracy = p_plays_correct / p_plays_total if p_plays_total > 0 else 0
            fp_rate = false_positives / p_plays_total if p_plays_total > 0 else 0
            fn_rate = false_negatives / p_plays_total if p_plays_total > 0 else 0

            # Get previous report for comparison
            prev_report = db.query(AccuracyReport).filter(
                AccuracyReport.model_version == model_version,
                AccuracyReport.gameweek < gameweek
            ).order_by(AccuracyReport.gameweek.desc()).first()

            mae_improvement = None
            prev_version = None
            if prev_report:
                mae_improvement = prev_report.overall_mae - mae
                prev_version = model_version

            # Create accuracy report
            report = AccuracyReport(
                model_version=model_version,
                gameweek=gameweek,
                players_evaluated=len(errors),
                overall_mae=mae,
                overall_rmse=rmse,
                mae_gkp=mae_by_pos.get('GKP'),
                mae_def=mae_by_pos.get('DEF'),
                mae_mid=mae_by_pos.get('MID'),
                mae_fwd=mae_by_pos.get('FWD'),
                p_plays_accuracy=p_plays_accuracy,
                false_positive_rate=fp_rate,
                false_negative_rate=fn_rate,
                mae_improvement=mae_improvement,
                previous_version=prev_version,
                mean_error=mean_error,
            )
            db.add(report)
            db.commit()

            logger.info(f"Validated GW{gameweek}: MAE={mae:.2f}, P(plays) accuracy={p_plays_accuracy:.1%}")

            return {
                "gameweek": gameweek,
                "model_version": model_version,
                "players_evaluated": len(errors),
                "overall_mae": round(mae, 3),
                "overall_rmse": round(rmse, 3),
                "mae_by_position": {k: round(v, 3) if v else None for k, v in mae_by_pos.items()},
                "p_plays_accuracy": round(p_plays_accuracy, 3),
                "false_positive_rate": round(fp_rate, 3),
                "false_negative_rate": round(fn_rate, 3),
                "mean_error": round(mean_error, 3),
                "mae_improvement": round(mae_improvement, 3) if mae_improvement else None,
                "needs_retraining": mae > self.MAE_THRESHOLD
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to validate predictions: {e}")
            raise
        finally:
            db.close()

    async def retrain_model(
        self,
        trigger_type: str = "manual",
        force: bool = False
    ) -> Dict:
        """
        Retrain the ML model with latest data.

        Args:
            trigger_type: "scheduled", "manual", or "accuracy_drop"
            force: Force retraining even if accuracy is acceptable

        Returns:
            Retraining results
        """
        if not self._fpl_service:
            raise ValueError("FPL service not initialized")

        started_at = datetime.utcnow()
        old_version = self._get_current_version()

        # Get current gameweek
        gw_obj = self._fpl_service.get_current_gameweek()
        current_gw = gw_obj.id if hasattr(gw_obj, 'id') else gw_obj

        # Generate new version string
        new_version = f"v{current_gw}_gw{current_gw}_{datetime.utcnow().strftime('%Y%m%d')}"

        db = SessionLocal()

        try:
            # Check if retraining is needed
            if not force:
                latest_report = db.query(AccuracyReport).filter(
                    AccuracyReport.model_version == old_version
                ).order_by(AccuracyReport.gameweek.desc()).first()

                if latest_report and latest_report.overall_mae < self.MAE_THRESHOLD:
                    return {
                        "retrained": False,
                        "reason": f"MAE ({latest_report.overall_mae:.2f}) below threshold ({self.MAE_THRESHOLD})",
                        "current_version": old_version
                    }

            # Import ML service for retraining
            from services.ml_service import get_ml_service
            ml_service = get_ml_service()
            ml_service.set_fpl_service(self._fpl_service)

            # Collect fresh training data
            logger.info("Collecting fresh training data...")
            collect_result = await ml_service.collect_training_data(max_players=200)

            # Train new model
            logger.info("Training new model...")
            coefficients = ml_service.train_model()

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Get old model metrics for comparison
            old_metrics = db.query(ModelVersion).filter(
                ModelVersion.version == old_version
            ).first()

            old_mae = old_metrics.mae if old_metrics else None
            new_mae = coefficients.mae

            improvement_pct = None
            if old_mae and new_mae:
                improvement_pct = (old_mae - new_mae) / old_mae * 100

            # Decide whether to deploy
            should_deploy = force or (
                improvement_pct and improvement_pct >= self.IMPROVEMENT_THRESHOLD * 100
            )

            deployment_reason = None
            if should_deploy:
                if force:
                    deployment_reason = "Forced deployment"
                elif improvement_pct:
                    deployment_reason = f"{improvement_pct:.1f}% improvement in MAE"
                else:
                    deployment_reason = "New baseline model"
            else:
                deployment_reason = f"Insufficient improvement ({improvement_pct:.1f}% vs {self.IMPROVEMENT_THRESHOLD*100}% threshold)"

            # Create new model version
            new_model_version = ModelVersion(
                version=new_version,
                gameweek=current_gw,
                training_samples=coefficients.n_samples,
                r_squared=coefficients.r_squared,
                mae=coefficients.mae,
                rmse=coefficients.rmse,
                is_production=should_deploy,
                is_tested=True,
                trained_at=started_at,
                deployed_at=completed_at if should_deploy else None,
                notes=f"Retrained via {trigger_type}"
            )
            db.add(new_model_version)

            # Update old version if deploying new one
            if should_deploy and old_metrics:
                old_metrics.is_production = False
                self._current_version = new_version

            # Log retraining event
            log = RetrainingLog(
                gameweek=current_gw,
                trigger_type=trigger_type,
                old_version=old_version,
                new_version=new_version,
                success=True,
                old_mae=old_mae,
                new_mae=new_mae,
                improvement_pct=improvement_pct,
                deployed=should_deploy,
                deployment_reason=deployment_reason,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration
            )
            db.add(log)
            db.commit()

            logger.info(
                f"Retraining complete: {new_version}, "
                f"R²={coefficients.r_squared:.3f}, MAE={coefficients.mae:.2f}, "
                f"Deployed={should_deploy}"
            )

            return {
                "retrained": True,
                "old_version": old_version,
                "new_version": new_version,
                "training_samples": coefficients.n_samples,
                "metrics": {
                    "r_squared": round(coefficients.r_squared, 4),
                    "mae": round(coefficients.mae, 4),
                    "rmse": round(coefficients.rmse, 4),
                },
                "improvement_pct": round(improvement_pct, 2) if improvement_pct else None,
                "deployed": should_deploy,
                "deployment_reason": deployment_reason,
                "duration_seconds": round(duration, 2)
            }

        except Exception as e:
            db.rollback()

            # Log failed retraining
            log = RetrainingLog(
                gameweek=current_gw,
                trigger_type=trigger_type,
                old_version=old_version,
                success=False,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
            db.add(log)
            db.commit()

            logger.error(f"Retraining failed: {e}")
            raise
        finally:
            db.close()

    def get_model_history(self, limit: int = 10) -> List[Dict]:
        """Get history of model versions."""
        db = SessionLocal()
        try:
            versions = db.query(ModelVersion).order_by(
                ModelVersion.trained_at.desc()
            ).limit(limit).all()

            return [
                {
                    "version": v.version,
                    "gameweek": v.gameweek,
                    "training_samples": v.training_samples,
                    "r_squared": v.r_squared,
                    "mae": v.mae,
                    "rmse": v.rmse,
                    "is_production": v.is_production,
                    "trained_at": v.trained_at.isoformat() if v.trained_at else None,
                }
                for v in versions
            ]
        finally:
            db.close()

    def get_accuracy_history(self, model_version: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get accuracy reports history."""
        db = SessionLocal()
        try:
            query = db.query(AccuracyReport)
            if model_version:
                query = query.filter(AccuracyReport.model_version == model_version)

            reports = query.order_by(AccuracyReport.gameweek.desc()).limit(limit).all()

            return [
                {
                    "gameweek": r.gameweek,
                    "model_version": r.model_version,
                    "players_evaluated": r.players_evaluated,
                    "overall_mae": r.overall_mae,
                    "overall_rmse": r.overall_rmse,
                    "mae_by_position": {
                        "GKP": r.mae_gkp,
                        "DEF": r.mae_def,
                        "MID": r.mae_mid,
                        "FWD": r.mae_fwd,
                    },
                    "p_plays_accuracy": r.p_plays_accuracy,
                    "mae_improvement": r.mae_improvement,
                    "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
                }
                for r in reports
            ]
        finally:
            db.close()

    def get_retraining_history(self, limit: int = 10) -> List[Dict]:
        """Get history of retraining events."""
        db = SessionLocal()
        try:
            logs = db.query(RetrainingLog).order_by(
                RetrainingLog.started_at.desc()
            ).limit(limit).all()

            return [
                {
                    "gameweek": l.gameweek,
                    "trigger_type": l.trigger_type,
                    "old_version": l.old_version,
                    "new_version": l.new_version,
                    "success": l.success,
                    "error_message": l.error_message,
                    "old_mae": l.old_mae,
                    "new_mae": l.new_mae,
                    "improvement_pct": l.improvement_pct,
                    "deployed": l.deployed,
                    "deployment_reason": l.deployment_reason,
                    "duration_seconds": l.duration_seconds,
                    "started_at": l.started_at.isoformat() if l.started_at else None,
                }
                for l in logs
            ]
        finally:
            db.close()

    def get_performance_summary(self) -> Dict:
        """Get overall performance summary across all versions."""
        db = SessionLocal()
        try:
            # Current production model
            current = db.query(ModelVersion).filter(
                ModelVersion.is_production == True
            ).first()

            # Latest accuracy report
            latest_report = db.query(AccuracyReport).order_by(
                AccuracyReport.gameweek.desc()
            ).first()

            # Accuracy trend (last 5 GWs)
            recent_reports = db.query(AccuracyReport).order_by(
                AccuracyReport.gameweek.desc()
            ).limit(5).all()

            mae_trend = [r.overall_mae for r in recent_reports] if recent_reports else []

            # Calculate trend direction
            trend = "stable"
            if len(mae_trend) >= 2:
                if mae_trend[0] < mae_trend[-1]:
                    trend = "improving"
                elif mae_trend[0] > mae_trend[-1]:
                    trend = "degrading"

            return {
                "current_model": {
                    "version": current.version if current else None,
                    "gameweek": current.gameweek if current else None,
                    "r_squared": current.r_squared if current else None,
                    "mae": current.mae if current else None,
                },
                "latest_accuracy": {
                    "gameweek": latest_report.gameweek if latest_report else None,
                    "mae": latest_report.overall_mae if latest_report else None,
                    "p_plays_accuracy": latest_report.p_plays_accuracy if latest_report else None,
                } if latest_report else None,
                "mae_trend": mae_trend,
                "trend_direction": trend,
                "needs_attention": trend == "degrading" or (mae_trend and mae_trend[0] > self.MAE_THRESHOLD)
            }
        finally:
            db.close()


# Singleton instance
_retraining_service: Optional[MLRetrainingService] = None


def get_ml_retraining_service() -> MLRetrainingService:
    """Get or create the singleton MLRetrainingService instance."""
    global _retraining_service
    if _retraining_service is None:
        _retraining_service = MLRetrainingService()
    return _retraining_service
