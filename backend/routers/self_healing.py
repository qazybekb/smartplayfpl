# backend/routers/self_healing.py
"""
Self-Healing API Router

Provides endpoints for:
- Manual trigger of self-healing
- Health checks with auto-healing
- Error and action history
- Statistics and monitoring
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.self_healing_service import get_self_healing_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class HealRequest(BaseModel):
    """Request to manually trigger healing."""
    error_type: str
    error_message: str
    component: str
    stack_trace: Optional[str] = None
    context: Optional[dict] = None
    auto_execute: bool = True


class HealResponse(BaseModel):
    """Response from healing operation."""
    error_id: str
    severity: str
    resolved: bool
    diagnosis: dict
    actions_taken: list


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/health-check")
async def run_health_check():
    """
    Run comprehensive health check with auto-healing.

    This endpoint:
    1. Checks all system components (FPL API, KG, ML, DB)
    2. Automatically heals any issues found
    3. Returns status and actions taken

    Use this for monitoring and automated health checks.
    """
    try:
        service = get_self_healing_service()
        result = await service.run_health_check()

        return {
            "status": "healthy" if result["healthy"] else "unhealthy",
            **result
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heal", response_model=HealResponse)
async def trigger_healing(request: HealRequest):
    """
    Manually trigger self-healing for a specific error.

    This endpoint allows external systems or error handlers
    to report errors and trigger AI-powered healing.

    The system will:
    1. Log the error
    2. Use Claude AI to diagnose the root cause
    3. Execute safe healing actions automatically

    Args:
        request: Error details and options

    Returns:
        Diagnosis and healing actions taken
    """
    try:
        service = get_self_healing_service()
        result = await service.heal(
            error_type=request.error_type,
            error_message=request.error_message,
            component=request.component,
            stack_trace=request.stack_trace,
            context=request.context,
            auto_execute=request.auto_execute,
        )

        return HealResponse(**result)

    except Exception as e:
        logger.error(f"Healing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors")
async def get_error_history(
    limit: int = Query(20, ge=1, le=100, description="Number of errors to return")
):
    """
    Get recent error history.

    Returns the most recent errors detected by the self-healing system,
    including their resolution status.
    """
    try:
        service = get_self_healing_service()
        errors = service.get_error_history(limit=limit)

        return {
            "total": len(errors),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Failed to get error history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions")
async def get_action_history(
    limit: int = Query(20, ge=1, le=100, description="Number of actions to return")
):
    """
    Get recent healing action history.

    Returns the most recent healing actions taken by the system,
    including whether they were auto-executed and their success status.
    """
    try:
        service = get_self_healing_service()
        actions = service.get_action_history(limit=limit)

        return {
            "total": len(actions),
            "actions": actions
        }
    except Exception as e:
        logger.error(f"Failed to get action history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_healing_stats():
    """
    Get self-healing statistics.

    Returns metrics about:
    - Error counts (hourly/daily)
    - Resolution rates
    - Auto-healing success rate
    """
    try:
        service = get_self_healing_service()
        stats = service.get_stats()

        return {
            "status": "operational",
            **stats
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnose")
async def diagnose_only(request: HealRequest):
    """
    Get AI diagnosis without executing healing actions.

    Useful for previewing what the AI would recommend
    before actually executing the fixes.
    """
    try:
        service = get_self_healing_service()

        # Detect error
        error = service.detect_error(
            error_type=request.error_type,
            error_message=request.error_message,
            component=request.component,
            stack_trace=request.stack_trace,
            context=request.context,
        )

        # Get diagnosis only
        diagnosis = await service.diagnose_error(error)

        return {
            "error_id": error.error_id,
            "severity": error.severity.value,
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "explanation": diagnosis.explanation,
                "confidence": diagnosis.confidence,
                "recommended_actions": diagnosis.recommended_actions,
            }
        }
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-cooldowns")
async def reset_cooldowns():
    """
    Reset all action cooldowns.

    Use this if you need to force re-execution of healing actions
    that are currently on cooldown.
    """
    try:
        service = get_self_healing_service()
        service._action_cooldowns.clear()

        return {
            "status": "success",
            "message": "All action cooldowns have been reset"
        }
    except Exception as e:
        logger.error(f"Failed to reset cooldowns: {e}")
        raise HTTPException(status_code=500, detail=str(e))
