# backend/routers/ml.py
"""
API Router for Machine Learning Model

Provides endpoints for:
- Model training (data collection + fitting)
- Predictions for all players
- Model performance metrics
- Feature importance visualization data
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging

from services.ml_service import get_ml_service, ModelCoefficients, ModelPrediction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


# =========================================================================
# Response Models
# =========================================================================

class ModelStatusResponse(BaseModel):
    """Current status of the ML model."""
    is_trained: bool
    training_samples: int
    model_type: str
    last_trained: Optional[str]
    r_squared: Optional[float]
    mae: Optional[float]
    rmse: Optional[float]


class CollectDataResponse(BaseModel):
    """Response from data collection."""
    success: bool
    players_collected: int
    total_samples: int
    errors: int
    positions: Dict[str, int]
    message: str


class TrainModelResponse(BaseModel):
    """Response from model training."""
    success: bool
    message: str
    coefficients: Optional[Dict[str, float]]
    metrics: Optional[Dict[str, float]]
    feature_importance: Optional[List[Dict[str, Any]]]


class PredictionResponse(BaseModel):
    """Single player prediction."""
    player_id: int
    player_name: str
    position: str
    team: str
    expected_points: float
    confidence_low: float
    confidence_high: float
    form: float
    next_opponent: str
    fdr: float
    is_home: bool
    contributions: Dict[str, float]


class PredictionsResponse(BaseModel):
    """All predictions response."""
    success: bool
    count: int
    model_r_squared: float
    predictions: List[PredictionResponse]


class FeatureImportanceResponse(BaseModel):
    """Feature importance data for visualization."""
    features: List[Dict[str, Any]]
    interpretation: Dict[str, str]


# =========================================================================
# Endpoints
# =========================================================================

@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status():
    """Get current status of the ML model."""
    ml = get_ml_service()
    coef = ml.coefficients
    
    return ModelStatusResponse(
        is_trained=ml.is_trained,
        training_samples=ml.training_data_size,
        model_type="Ridge Regression (L2 regularized)",
        last_trained=coef.trained_at if coef else None,
        r_squared=coef.r_squared if coef else None,
        mae=coef.mae if coef else None,
        rmse=coef.rmse if coef else None,
    )


@router.post("/collect-data", response_model=CollectDataResponse)
async def collect_training_data(max_players: int = 150):
    """
    Collect historical gameweek data for model training.
    
    This fetches data from the FPL API for each player's past gameweeks.
    
    Args:
        max_players: Maximum number of players to collect (default 150)
    """
    from services.fpl_service import fpl_service
    
    ml = get_ml_service()
    ml.set_fpl_service(fpl_service)
    
    try:
        result = await ml.collect_training_data(max_players=max_players)
        
        return CollectDataResponse(
            success=True,
            players_collected=result["players_collected"],
            total_samples=result["total_samples"],
            errors=result["errors"],
            positions=result["positions"],
            message=f"Collected {result['total_samples']} samples from {result['players_collected']} players",
        )
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train", response_model=TrainModelResponse)
async def train_model():
    """
    Train the ML model on collected data.
    
    Must call /collect-data first to gather training samples.
    """
    ml = get_ml_service()
    
    if ml.training_data_size < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough training data. Have {ml.training_data_size}, need at least 100. Call /collect-data first."
        )
    
    try:
        coefficients = ml.train_model()
        
        # Calculate feature importance (absolute coefficient values)
        feature_importance = [
            {"feature": "Form (recent performance)", "coefficient": coefficients.form, "importance": abs(coefficients.form)},
            {"feature": "Fixture Difficulty (FDR)", "coefficient": coefficients.fdr, "importance": abs(coefficients.fdr)},
            {"feature": "Home Advantage", "coefficient": coefficients.is_home, "importance": abs(coefficients.is_home)},
            {"feature": "Minutes Played %", "coefficient": coefficients.minutes_pct, "importance": abs(coefficients.minutes_pct)},
            {"feature": "Expected Goals (xG)", "coefficient": coefficients.xg, "importance": abs(coefficients.xg)},
            {"feature": "Expected Assists (xA)", "coefficient": coefficients.xa, "importance": abs(coefficients.xa)},
            {"feature": "ICT Index", "coefficient": coefficients.ict, "importance": abs(coefficients.ict)},
            {"feature": "Position: MID", "coefficient": coefficients.pos_mid, "importance": abs(coefficients.pos_mid)},
            {"feature": "Position: FWD", "coefficient": coefficients.pos_fwd, "importance": abs(coefficients.pos_fwd)},
            {"feature": "Position: GKP", "coefficient": coefficients.pos_gkp, "importance": abs(coefficients.pos_gkp)},
        ]
        feature_importance.sort(key=lambda x: x["importance"], reverse=True)
        
        return TrainModelResponse(
            success=True,
            message=f"Model trained successfully on {coefficients.n_samples} samples",
            coefficients={
                "intercept": coefficients.intercept,
                "form": coefficients.form,
                "fdr": coefficients.fdr,
                "is_home": coefficients.is_home,
                "minutes_pct": coefficients.minutes_pct,
                "xg": coefficients.xg,
                "xa": coefficients.xa,
                "ict": coefficients.ict,
                "pos_mid": coefficients.pos_mid,
                "pos_fwd": coefficients.pos_fwd,
                "pos_gkp": coefficients.pos_gkp,
            },
            metrics={
                "r_squared": coefficients.r_squared,
                "mae": coefficients.mae,
                "rmse": coefficients.rmse,
                "n_samples": coefficients.n_samples,
            },
            feature_importance=feature_importance,
        )
    except Exception as e:
        logger.error(f"Model training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions", response_model=PredictionsResponse)
async def get_predictions():
    """
    Get expected points predictions for all players.
    
    Model must be trained first via /train endpoint.
    """
    from services.fpl_service import fpl_service
    
    ml = get_ml_service()
    
    if not ml.is_trained:
        raise HTTPException(
            status_code=400,
            detail="Model not trained. Call /collect-data then /train first."
        )
    
    ml.set_fpl_service(fpl_service)
    
    try:
        predictions = await ml.predict_all_players()
        
        return PredictionsResponse(
            success=True,
            count=len(predictions),
            model_r_squared=ml.coefficients.r_squared if ml.coefficients else 0,
            predictions=[
                PredictionResponse(
                    player_id=p.player_id,
                    player_name=p.player_name,
                    position=p.position,
                    team=p.team,
                    expected_points=p.expected_points,
                    confidence_low=p.confidence_low,
                    confidence_high=p.confidence_high,
                    form=p.form,
                    next_opponent=p.next_opponent,
                    fdr=p.fdr,
                    is_home=p.is_home,
                    contributions={
                        "form": p.contribution_form,
                        "fdr": p.contribution_fdr,
                        "home": p.contribution_home,
                        "position": p.contribution_position,
                        "base": p.contribution_other,
                    },
                )
                for p in predictions
            ],
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
async def get_feature_importance():
    """
    Get feature importance data for visualization.
    
    Shows which features have the most impact on predictions.
    """
    ml = get_ml_service()
    
    if not ml.is_trained or not ml.coefficients:
        raise HTTPException(
            status_code=400,
            detail="Model not trained. Call /collect-data then /train first."
        )
    
    c = ml.coefficients
    
    features = [
        {
            "name": "Form",
            "coefficient": round(c.form, 4),
            "importance": round(abs(c.form), 4),
            "direction": "positive" if c.form > 0 else "negative",
            "description": "Recent average points. Higher form = more expected points.",
        },
        {
            "name": "Fixture Difficulty",
            "coefficient": round(c.fdr, 4),
            "importance": round(abs(c.fdr), 4),
            "direction": "positive" if c.fdr > 0 else "negative",
            "description": "FDR 1-5 scale. Negative coefficient = harder fixtures reduce points.",
        },
        {
            "name": "Home Advantage",
            "coefficient": round(c.is_home, 4),
            "importance": round(abs(c.is_home), 4),
            "direction": "positive" if c.is_home > 0 else "negative",
            "description": "Bonus for playing at home.",
        },
        {
            "name": "Minutes %",
            "coefficient": round(c.minutes_pct, 4),
            "importance": round(abs(c.minutes_pct), 4),
            "direction": "positive" if c.minutes_pct > 0 else "negative",
            "description": "Percentage of game played. More minutes = more points.",
        },
        {
            "name": "xG (Expected Goals)",
            "coefficient": round(c.xg, 4),
            "importance": round(abs(c.xg), 4),
            "direction": "positive" if c.xg > 0 else "negative",
            "description": "Quality of goal-scoring chances created.",
        },
        {
            "name": "xA (Expected Assists)",
            "coefficient": round(c.xa, 4),
            "importance": round(abs(c.xa), 4),
            "direction": "positive" if c.xa > 0 else "negative",
            "description": "Quality of assist chances created.",
        },
        {
            "name": "ICT Index",
            "coefficient": round(c.ict, 4),
            "importance": round(abs(c.ict), 4),
            "direction": "positive" if c.ict > 0 else "negative",
            "description": "FPL's Influence + Creativity + Threat metric.",
        },
        {
            "name": "Midfielder Bonus",
            "coefficient": round(c.pos_mid, 4),
            "importance": round(abs(c.pos_mid), 4),
            "direction": "positive" if c.pos_mid > 0 else "negative",
            "description": "Position adjustment for midfielders vs defenders.",
        },
        {
            "name": "Forward Bonus",
            "coefficient": round(c.pos_fwd, 4),
            "importance": round(abs(c.pos_fwd), 4),
            "direction": "positive" if c.pos_fwd > 0 else "negative",
            "description": "Position adjustment for forwards vs defenders.",
        },
        {
            "name": "Goalkeeper Adjustment",
            "coefficient": round(c.pos_gkp, 4),
            "importance": round(abs(c.pos_gkp), 4),
            "direction": "positive" if c.pos_gkp > 0 else "negative",
            "description": "Position adjustment for goalkeepers vs defenders.",
        },
    ]
    
    # Sort by importance
    features.sort(key=lambda x: x["importance"], reverse=True)
    
    interpretation = {
        "model_type": "Ridge Regression (L2 regularization)",
        "r_squared": f"{c.r_squared:.1%} of variance explained",
        "mae": f"Average error: ±{c.mae:.2f} points",
        "rmse": f"Typical error: ±{c.rmse:.2f} points",
        "baseline": f"Intercept (base points): {c.intercept:.2f}",
        "sample_size": f"Trained on {c.n_samples:,} gameweek samples",
    }
    
    return FeatureImportanceResponse(
        features=features,
        interpretation=interpretation,
    )


@router.post("/train-full")
async def train_full_pipeline(max_players: int = 150):
    """
    Run the full training pipeline: collect data + train model.

    Convenience endpoint that combines /collect-data and /train.
    """
    from services.fpl_service import fpl_service

    ml = get_ml_service()
    ml.set_fpl_service(fpl_service)

    # Step 1: Collect data
    try:
        collect_result = await ml.collect_training_data(max_players=max_players)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data collection failed: {e}")

    # Step 2: Train model
    try:
        coefficients = ml.train_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training failed: {e}")

    return {
        "success": True,
        "data_collection": {
            "players": collect_result["players_collected"],
            "samples": collect_result["total_samples"],
        },
        "model": {
            "r_squared": coefficients.r_squared,
            "mae": coefficients.mae,
            "rmse": coefficients.rmse,
        },
        "message": f"Model trained on {collect_result['total_samples']} samples with R²={coefficients.r_squared:.3f}",
    }


# =========================================================================
# Model Versioning & Accuracy Tracking Endpoints
# =========================================================================

@router.get("/versions")
async def get_model_versions(limit: int = 10):
    """
    Get history of ML model versions.

    Returns list of all model versions with their metrics and status.
    """
    from services.ml_retraining_service import get_ml_retraining_service

    retraining_service = get_ml_retraining_service()
    versions = retraining_service.get_model_history(limit=limit)

    return {
        "success": True,
        "count": len(versions),
        "versions": versions
    }


@router.get("/accuracy")
async def get_accuracy_reports(model_version: Optional[str] = None, limit: int = 10):
    """
    Get accuracy reports showing prediction performance per gameweek.

    Args:
        model_version: Filter by specific model version (optional)
        limit: Maximum number of reports to return
    """
    from services.ml_retraining_service import get_ml_retraining_service

    retraining_service = get_ml_retraining_service()
    reports = retraining_service.get_accuracy_history(model_version=model_version, limit=limit)

    return {
        "success": True,
        "count": len(reports),
        "reports": reports
    }


@router.get("/retraining-history")
async def get_retraining_history(limit: int = 10):
    """
    Get history of model retraining events.

    Shows when models were retrained, why, and whether improvements were deployed.
    """
    from services.ml_retraining_service import get_ml_retraining_service

    retraining_service = get_ml_retraining_service()
    history = retraining_service.get_retraining_history(limit=limit)

    return {
        "success": True,
        "count": len(history),
        "history": history
    }


@router.get("/performance-summary")
async def get_performance_summary():
    """
    Get overall ML performance summary.

    Returns:
        - Current production model info
        - Latest accuracy metrics
        - Trend analysis (improving/degrading)
        - Recommendations for action
    """
    from services.ml_retraining_service import get_ml_retraining_service

    retraining_service = get_ml_retraining_service()
    summary = retraining_service.get_performance_summary()

    return {
        "success": True,
        **summary
    }


@router.post("/log-predictions/{gameweek}")
async def log_predictions(gameweek: int):
    """
    Log predictions for an upcoming gameweek.

    Call this before the gameweek starts to record predictions
    for later accuracy validation.
    """
    from services.fpl_service import fpl_service
    from services.ml_predictor_service import get_ml_predictor_service
    from services.ml_retraining_service import get_ml_retraining_service

    predictor = get_ml_predictor_service()
    predictor.set_services(fpl_service)

    retraining_service = get_ml_retraining_service()
    retraining_service.set_services(fpl_service, predictor)

    try:
        result = await retraining_service.log_predictions(gameweek)
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Failed to log predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-predictions/{gameweek}")
async def validate_predictions(gameweek: int):
    """
    Validate predictions against actual gameweek results.

    Call this after a gameweek completes to measure accuracy
    and detect if retraining is needed.
    """
    from services.fpl_service import fpl_service
    from services.ml_predictor_service import get_ml_predictor_service
    from services.ml_retraining_service import get_ml_retraining_service

    predictor = get_ml_predictor_service()
    predictor.set_services(fpl_service)

    retraining_service = get_ml_retraining_service()
    retraining_service.set_services(fpl_service, predictor)

    try:
        result = await retraining_service.validate_predictions(gameweek)
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Failed to validate predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrain")
async def retrain_model(
    trigger_type: str = "manual",
    force: bool = False
):
    """
    Trigger model retraining.

    Args:
        trigger_type: Reason for retraining ("manual", "scheduled", "accuracy_drop")
        force: Force retraining even if accuracy is acceptable

    Returns:
        Retraining results including whether new model was deployed
    """
    from services.fpl_service import fpl_service
    from services.ml_predictor_service import get_ml_predictor_service
    from services.ml_retraining_service import get_ml_retraining_service

    predictor = get_ml_predictor_service()
    predictor.set_services(fpl_service)

    retraining_service = get_ml_retraining_service()
    retraining_service.set_services(fpl_service, predictor)

    try:
        result = await retraining_service.retrain_model(
            trigger_type=trigger_type,
            force=force
        )
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-improve")
async def run_auto_improvement_cycle():
    """
    Run the full auto-improvement cycle:
    1. Validate recent predictions
    2. Retrain if accuracy dropped
    3. Log predictions for next GW

    This is the main endpoint for continuous model improvement.
    Call after each gameweek completes.
    """
    from services.fpl_service import fpl_service
    from services.ml_predictor_service import get_ml_predictor_service
    from services.ml_retraining_service import get_ml_retraining_service

    predictor = get_ml_predictor_service()
    predictor.set_services(fpl_service)

    retraining_service = get_ml_retraining_service()
    retraining_service.set_services(fpl_service, predictor)

    # Get current gameweek
    gw_obj = fpl_service.get_current_gameweek()
    current_gw = gw_obj.id if hasattr(gw_obj, 'id') else gw_obj

    results = {
        "gameweek": current_gw,
        "steps": []
    }

    try:
        # Step 1: Validate predictions for previous GW
        if current_gw > 1:
            prev_gw = current_gw - 1
            try:
                validation = await retraining_service.validate_predictions(prev_gw)
                results["steps"].append({
                    "step": "validate_predictions",
                    "gameweek": prev_gw,
                    "success": True,
                    "mae": validation.get("overall_mae"),
                    "needs_retraining": validation.get("needs_retraining", False)
                })

                # Step 2: Retrain if needed
                if validation.get("needs_retraining"):
                    retrain_result = await retraining_service.retrain_model(
                        trigger_type="accuracy_drop"
                    )
                    results["steps"].append({
                        "step": "retrain",
                        "success": retrain_result.get("retrained", False),
                        "deployed": retrain_result.get("deployed", False),
                        "new_version": retrain_result.get("new_version"),
                        "improvement_pct": retrain_result.get("improvement_pct")
                    })
            except Exception as e:
                results["steps"].append({
                    "step": "validate_predictions",
                    "success": False,
                    "error": str(e)
                })

        # Step 3: Log predictions for current/next GW
        try:
            log_result = await retraining_service.log_predictions(current_gw)
            results["steps"].append({
                "step": "log_predictions",
                "gameweek": current_gw,
                "success": True,
                "predictions_logged": log_result.get("predictions_logged")
            })
        except Exception as e:
            results["steps"].append({
                "step": "log_predictions",
                "success": False,
                "error": str(e)
            })

        # Get performance summary
        results["performance_summary"] = retraining_service.get_performance_summary()

        return {
            "success": True,
            **results
        }

    except Exception as e:
        logger.error(f"Auto-improvement cycle failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))











