"""GraphFPL Backend - FastAPI Application."""

import os
import sys
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("smartplayfpl")

# ============================================================================
# RATE LIMITING
# ============================================================================
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ============================================================================
# ENVIRONMENT & CONFIGURATION
# ============================================================================
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_ORIGINS = [
    "https://smartplayfpl.com",  # Custom domain
    "https://smart-play-fpl-project.vercel.app",
    "https://smartplayfpl.vercel.app",
    "https://frontend-5yi6777dy-qazybekbeken-4130s-projects.vercel.app",  # Vercel deployment URL
    "https://smartplayfpl-500287436620.europe-west1.run.app",
]

# Add localhost in development mode
if DEBUG:
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
    ])

# Track initialization state
_init_state = {
    "routers_loaded": False,
    "router_error": None,
    "fpl_initialized": False,
    "fpl_error": None,
    "kg_initialized": False,
    "kg_error": None,
    "kg_players": 0,
    "started_at": None,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize FPL service and Knowledge Graph on startup."""
    import asyncio
    from database import init_db
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    _init_state["started_at"] = datetime.utcnow().isoformat()
    logger.info("Starting SmartPlayFPL backend...")

    # Initialize database tables (creates new tables like api_call_logs if needed)
    try:
        init_db()
        logger.info("Database tables initialized (including ML versioning tables)")
    except Exception as e:
        logger.warning(f"Database init warning: {e}")

    # Initialize scheduler for automated ML retraining
    scheduler = AsyncIOScheduler()
    _init_state["scheduler_running"] = False

    # Step 1: Initialize FPL service with timeout
    try:
        from services.fpl_service import fpl_service
        logger.info("Initializing FPL service (this may take 10-30 seconds)...")
        try:
            await asyncio.wait_for(fpl_service.initialize(), timeout=60.0)
            _init_state["fpl_initialized"] = True
            logger.info("FPL service initialized successfully")
        except asyncio.TimeoutError:
            _init_state["fpl_error"] = "FPL service initialization timed out after 60 seconds"
            logger.warning("FPL service initialization timed out - will retry on first request")
        except Exception as e:
            _init_state["fpl_error"] = str(e)
            logger.warning(f"FPL init error: {e} - will retry on first request")
            logger.debug(traceback.format_exc())
    except Exception as e:
        _init_state["fpl_error"] = str(e)
        logger.error(f"FPL init critical error: {e}")
        logger.debug(traceback.format_exc())

    # Step 2: Initialize and rebuild Knowledge Graph (skip if SKIP_KG env var is set)
    if _init_state["fpl_initialized"] and not os.getenv("SKIP_KG"):
        try:
            from services.kg_service import get_kg_service
            from services.fpl_service import fpl_service

            logger.info("Building Knowledge Graph (this may take 30-60 seconds)...")
            kg = get_kg_service()
            kg.set_fpl_service(fpl_service)
            try:
                result = await asyncio.wait_for(kg.rebuild(), timeout=120.0)
                _init_state["kg_initialized"] = True
                _init_state["kg_players"] = result.get("base_triples", 0)
                logger.info(f"Knowledge Graph ready: {result.get('total_triples', 0)} triples, {result.get('inferred_triples', 0)} inferences")
            except asyncio.TimeoutError:
                _init_state["kg_error"] = "Knowledge Graph build timed out after 120 seconds"
                logger.warning("Knowledge Graph build timed out - KG features may not be available")
        except Exception as e:
            _init_state["kg_error"] = str(e)
            logger.warning(f"KG init error: {e} - KG features may not be available")
            logger.debug(traceback.format_exc())
    elif os.getenv("SKIP_KG"):
        logger.info("Skipping Knowledge Graph initialization (SKIP_KG set)")

    # Step 3: Start ML auto-improvement scheduler
    if _init_state["fpl_initialized"] and not os.getenv("SKIP_SCHEDULER"):
        try:
            async def scheduled_ml_improvement():
                """Scheduled task for ML model improvement after each gameweek."""
                try:
                    from services.fpl_service import fpl_service
                    from services.ml_predictor_service import get_ml_predictor_service
                    from services.ml_retraining_service import get_ml_retraining_service

                    logger.info("Starting scheduled ML improvement cycle...")

                    predictor = get_ml_predictor_service()
                    predictor.set_services(fpl_service)

                    retraining_service = get_ml_retraining_service()
                    retraining_service.set_services(fpl_service, predictor)

                    # Get current gameweek
                    gw_obj = fpl_service.get_current_gameweek()
                    current_gw = gw_obj.id if hasattr(gw_obj, 'id') else gw_obj

                    # Validate previous GW predictions
                    if current_gw > 1:
                        try:
                            validation = await retraining_service.validate_predictions(current_gw - 1)
                            logger.info(f"GW{current_gw-1} validation: MAE={validation.get('overall_mae', 'N/A')}")

                            # Retrain if accuracy dropped
                            if validation.get("needs_retraining"):
                                retrain_result = await retraining_service.retrain_model(
                                    trigger_type="scheduled"
                                )
                                logger.info(f"Retraining result: deployed={retrain_result.get('deployed')}")
                        except Exception as e:
                            logger.warning(f"Validation failed: {e}")

                    # Log predictions for current GW
                    try:
                        await retraining_service.log_predictions(current_gw)
                        logger.info(f"Logged predictions for GW{current_gw}")
                    except Exception as e:
                        logger.warning(f"Prediction logging failed: {e}")

                except Exception as e:
                    logger.error(f"Scheduled ML improvement failed: {e}")

            # Schedule ML improvement:
            # - Every Wednesday at 18:00 UTC (after most GWs finish)
            # - Also Friday at 06:00 UTC as backup
            scheduler.add_job(
                scheduled_ml_improvement,
                CronTrigger(day_of_week='wed', hour=18, minute=0),
                id='ml_improvement_wed',
                name='ML Improvement (Wednesday)',
                replace_existing=True
            )
            scheduler.add_job(
                scheduled_ml_improvement,
                CronTrigger(day_of_week='fri', hour=6, minute=0),
                id='ml_improvement_fri',
                name='ML Improvement (Friday)',
                replace_existing=True
            )

            # Step 4: Schedule self-healing health checks
            async def scheduled_health_check():
                """Scheduled task for self-healing health checks."""
                try:
                    from services.self_healing_service import get_self_healing_service
                    from services.fpl_service import fpl_service

                    healing_service = get_self_healing_service()
                    healing_service.set_services(fpl_service=fpl_service)

                    logger.info("Running scheduled self-healing health check...")
                    result = await healing_service.run_health_check()

                    if not result["healthy"]:
                        logger.warning(f"Health check found issues: {result['issues_found']}")
                        logger.info(f"Auto-healing actions taken: {len(result['actions_taken'])}")
                    else:
                        logger.info("Health check passed - all systems operational")

                except Exception as e:
                    logger.error(f"Scheduled health check failed: {e}")

            # Run health check every 30 minutes
            from apscheduler.triggers.interval import IntervalTrigger
            scheduler.add_job(
                scheduled_health_check,
                IntervalTrigger(minutes=30),
                id='self_healing_check',
                name='Self-Healing Health Check',
                replace_existing=True
            )

            scheduler.start()
            _init_state["scheduler_running"] = True
            logger.info("ML auto-improvement scheduler started (Wed 18:00, Fri 06:00 UTC)")
            logger.info("Self-healing health checks scheduled (every 30 minutes)")

        except Exception as e:
            logger.warning(f"Failed to start scheduler: {e}")
            logger.debug(traceback.format_exc())
    elif os.getenv("SKIP_SCHEDULER"):
        logger.info("Skipping scheduler initialization (SKIP_SCHEDULER set)")

    logger.info("Server ready! API endpoints are available.")
    yield

    # Shutdown scheduler
    if _init_state.get("scheduler_running"):
        try:
            scheduler.shutdown(wait=False)
            logger.info("ML scheduler stopped")
        except Exception as e:
            logger.warning(f"Scheduler shutdown error: {e}")

    logger.info("Shutting down SmartPlayFPL backend...")

# Create FastAPI app
app = FastAPI(
    title="SmartPlayFPL",
    version="1.0.0",
    description="AI-powered Fantasy Premier League analytics",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register global error handlers for consistent error responses
from middleware.error_handler import register_error_handlers
register_error_handlers(app)

# Add security headers middleware (must be added before CORS)
from middleware.security import add_security_middleware
add_security_middleware(app)

# Configure CORS - restricted to allowed origins
# SECURITY FIX: Removed allow_credentials=True with wildcard headers
# Use specific headers instead of "*" for better security
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # SECURITY: Disabled to prevent CSRF attacks
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Version", "X-Request-ID", "X-Admin-Password"],
)

# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with app status."""
    return {
        "status": "ok",
        "app": "SmartPlayFPL",
        "version": "1.0.0",
        "debug_mode": DEBUG,
        **_init_state
    }


@app.get("/api/health")
async def health():
    """
    Health check endpoint for deployment platforms.
    Returns detailed status of all dependencies.

    Response includes:
    - Overall health status (healthy/degraded/unhealthy)
    - Individual dependency checks
    - Circuit breaker status
    - Resource utilization
    """
    import time
    from services.fpl_service import fpl_service
    from services.kg_service import get_kg_service

    start_time = time.time()
    checks = {}

    # Check FPL service
    fpl_ok = _init_state["fpl_initialized"]
    fpl_players = len(fpl_service._players) if fpl_ok else 0
    fpl_teams = len(fpl_service._teams) if fpl_ok else 0
    checks["fpl_api"] = {
        "ok": fpl_ok,
        "players": fpl_players,
        "teams": fpl_teams,
        "error": _init_state.get("fpl_error"),
    }

    # Check Knowledge Graph
    kg = get_kg_service()
    kg_ok = _init_state["kg_initialized"]
    kg_triples = kg.triple_count if kg_ok else 0
    checks["knowledge_graph"] = {
        "ok": kg_ok,
        "triples": kg_triples,
        "has_data": kg.has_player_data if kg_ok else False,
        "error": _init_state.get("kg_error"),
    }

    # Check database with timing
    db_ok = True
    db_latency_ms = 0
    try:
        from database import SessionLocal
        from sqlalchemy import text
        db_start = time.time()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_latency_ms = (time.time() - db_start) * 1000
    except Exception as e:
        db_ok = False
        logger.warning(f"Database health check failed: {e}")

    checks["database"] = {
        "ok": db_ok,
        "latency_ms": round(db_latency_ms, 2),
    }

    # Check Circuit Breakers
    try:
        from middleware.resilience import circuit_registry
        cb_stats = circuit_registry.get_all_stats()
        checks["circuit_breakers"] = {
            "ok": all(cb["state"] != "open" for cb in cb_stats.values()),
            "breakers": cb_stats,
        }
    except ImportError:
        checks["circuit_breakers"] = {"ok": True, "breakers": {}}

    # Check Scheduler
    scheduler_ok = _init_state.get("scheduler_running", False)
    checks["scheduler"] = {
        "ok": scheduler_ok or os.getenv("SKIP_SCHEDULER"),
        "running": scheduler_ok,
    }

    # Check Claude API (just verify key is configured, don't expose key details)
    claude_configured = bool(os.getenv("ANTHROPIC_API_KEY"))
    checks["claude_ai"] = {
        "ok": True,  # Don't fail health check for missing AI
        "configured": claude_configured,
        # SECURITY: Don't expose any key details in health response
    }

    # Determine overall health
    critical_checks = [checks["fpl_api"]["ok"], checks["database"]["ok"]]
    optional_checks = [checks["knowledge_graph"]["ok"], checks["scheduler"]["ok"]]

    if all(critical_checks):
        if all(optional_checks):
            status = "healthy"
        else:
            status = "degraded"
    else:
        status = "unhealthy"

    # Calculate total check time
    total_time_ms = (time.time() - start_time) * 1000

    return {
        "status": status,
        "checks": checks,
        "timing_ms": round(total_time_ms, 2),
        "version": "1.0.0",
        **_init_state
    }


@app.get("/api/debug")
@limiter.limit("5/minute")
async def debug(request: Request):
    """Debug endpoint with detailed system info (rate limited).

    SECURITY: This endpoint is disabled in production and requires
    X-Debug-Token header matching DEBUG_AUTH_TOKEN env var in development.
    """
    from middleware.security import require_debug_auth, mask_api_key

    # SECURITY: Return 404 in production to hide endpoint existence
    if not DEBUG:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")

    # SECURITY: Require debug token in development too
    debug_token = os.getenv("DEBUG_AUTH_TOKEN")
    if debug_token:
        provided_token = request.headers.get("X-Debug-Token")
        if not provided_token or provided_token != debug_token:
            raise HTTPException(status_code=403, detail="Invalid debug token")

    from services.fpl_service import fpl_service
    from services.kg_service import get_kg_service
    kg = get_kg_service()

    # SECURITY: Mask sensitive information
    return {
        **_init_state,
        "python_version": sys.version.split()[0],  # Only version number
        "debug_mode": DEBUG,
        "allowed_origins": ALLOWED_ORIGINS,
        "players_count": len(fpl_service._players),
        "teams_count": len(fpl_service._teams),
        "kg_has_data": kg.has_player_data,
        "kg_triples": kg.triple_count,
        "api_keys_configured": {
            "anthropic": mask_api_key(os.getenv("ANTHROPIC_API_KEY")),
        }
    }


# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/cache/stats")
@limiter.limit("30/minute")
async def get_cache_stats(request: Request):
    """
    Get current cache statistics.

    Returns:
        Cache sizes, ages, and TTLs for global, team, and live caches
    """
    from services.fpl_service import fpl_service
    from services.kg_service import get_kg_service

    kg = get_kg_service()

    return {
        "fpl_cache": fpl_service.get_cache_stats(),
        "kg_cache": {
            "triples": kg.triple_count,
            "has_data": kg.has_player_data,
        }
    }


@app.post("/api/cache/invalidate")
@limiter.limit("5/minute")
async def invalidate_cache(
    request: Request,
    cache_types: list[str] = ["all"],
):
    """
    Invalidate (clear) specified caches.

    Args:
        cache_types: List of cache types to clear. Options:
            - "global": Clear FPL bootstrap data (players, teams, fixtures)
            - "teams": Clear per-team manager caches
            - "live": Clear live gameweek points cache
            - "kg": Clear and rebuild knowledge graph
            - "all": Clear all caches

    Returns:
        Summary of what was cleared
    """
    from services.fpl_service import fpl_service
    from services.kg_service import get_kg_service

    results = {"invalidated": []}

    # Handle FPL caches
    fpl_types = [t for t in cache_types if t in ["global", "teams", "live", "all"]]
    if fpl_types:
        fpl_result = fpl_service.clear_cache(fpl_types)
        results["fpl"] = fpl_result
        results["invalidated"].extend([f"fpl_{t}" for t in fpl_result["cleared"]])

    # Handle KG cache
    if "kg" in cache_types or "all" in cache_types:
        kg = get_kg_service()
        try:
            rebuild_result = await kg.rebuild()
            results["kg"] = {"rebuilt": True, "triples": rebuild_result.get("total_triples", 0)}
            results["invalidated"].append("kg")
        except Exception as e:
            results["kg"] = {"rebuilt": False, "error": str(e)}

    # Re-initialize FPL if global was cleared
    if "global" in fpl_types or "all" in cache_types:
        await fpl_service.initialize()
        results["reinitialized"] = True

    return results

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================
try:
    logger.info("Loading API routers...")
    from routers import team, kg, build, ml, predictor, self_healing, feedback
    app.include_router(team.router, prefix="/api", tags=["Team Analysis"])
    app.include_router(kg.router, prefix="/api", tags=["Knowledge Graph"])
    app.include_router(build.router, prefix="/api", tags=["Squad Builder"])
    app.include_router(ml.router, prefix="/api", tags=["Machine Learning"])
    app.include_router(predictor.router, prefix="/api", tags=["Predictions"])
    app.include_router(self_healing.router, prefix="/api/healing", tags=["Self-Healing"])
    app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
    _init_state["routers_loaded"] = True
    logger.info("API routers registered successfully")
except Exception as e:
    _init_state["router_error"] = str(e)
    logger.error(f"Failed to load routers: {e}")
    logger.debug(traceback.format_exc())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

