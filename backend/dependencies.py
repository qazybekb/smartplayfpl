"""
Dependency Injection module for SmartPlayFPL.

Provides standardized FastAPI dependencies for consistent service access
across all endpoints. This centralizes service initialization and
ensures proper cleanup.

Usage in routers:
    from dependencies import get_fpl_service, get_kg_service

    @router.get("/team/{team_id}")
    async def get_team(
        team_id: int,
        fpl: FPLService = Depends(get_fpl_service),
        db: Session = Depends(get_db),
    ):
        ...
"""

from typing import AsyncGenerator, Generator, Optional
from functools import lru_cache
from fastapi import Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session
import logging

from database import SessionLocal

logger = logging.getLogger("smartplayfpl.dependencies")


# =============================================================================
# DATABASE DEPENDENCIES
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Provides a database session for request handling.
    Session is automatically closed after the request.

    Usage:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# SERVICE DEPENDENCIES (Singleton Pattern)
# =============================================================================

# Service singletons stored at module level
_fpl_service_instance = None
_kg_service_instance = None
_predictor_service_instance = None
_claude_service_instance = None


def get_fpl_service():
    """
    Provides the FPL Service singleton.
    Ensures FPL data is available across all endpoints.

    Usage:
        @router.get("/players")
        async def get_players(fpl = Depends(get_fpl_service)):
            return fpl.get_all_players()
    """
    global _fpl_service_instance
    if _fpl_service_instance is None:
        from services.fpl_service import fpl_service
        _fpl_service_instance = fpl_service
    return _fpl_service_instance


def get_kg_service():
    """
    Provides the Knowledge Graph Service singleton.

    Usage:
        @router.get("/kg/query")
        async def query_kg(kg = Depends(get_kg_service)):
            return kg.query(...)
    """
    global _kg_service_instance
    if _kg_service_instance is None:
        from services.kg_service import get_kg_service as _get_kg
        _kg_service_instance = _get_kg()
    return _kg_service_instance


def get_predictor_service():
    """
    Provides the ML Predictor Service singleton.

    Usage:
        @router.get("/predictor/scores")
        async def get_scores(predictor = Depends(get_predictor_service)):
            return predictor.get_scores()
    """
    global _predictor_service_instance
    if _predictor_service_instance is None:
        from services.predictor_service import get_predictor_service as _get_pred
        _predictor_service_instance = _get_pred()
    return _predictor_service_instance


def get_claude_service():
    """
    Provides the Claude AI Service singleton.

    Usage:
        @router.post("/ai/analyze")
        async def analyze(claude = Depends(get_claude_service)):
            return await claude.analyze(...)
    """
    global _claude_service_instance
    if _claude_service_instance is None:
        from services.claude_service import get_claude_service as _get_claude
        _claude_service_instance = _get_claude()
    return _claude_service_instance


# =============================================================================
# COMBINED SERVICE DEPENDENCIES
# =============================================================================

class ServiceBundle:
    """Bundle of commonly used services for convenience."""

    def __init__(
        self,
        fpl,
        kg,
        predictor,
        db: Session,
    ):
        self.fpl = fpl
        self.kg = kg
        self.predictor = predictor
        self.db = db


def get_services(
    fpl=Depends(get_fpl_service),
    kg=Depends(get_kg_service),
    predictor=Depends(get_predictor_service),
    db: Session = Depends(get_db),
) -> ServiceBundle:
    """
    Provides a bundle of all commonly used services.

    Usage:
        @router.get("/dashboard")
        async def dashboard(services: ServiceBundle = Depends(get_services)):
            players = services.fpl.get_all_players()
            ...
    """
    return ServiceBundle(fpl=fpl, kg=kg, predictor=predictor, db=db)


# =============================================================================
# VALIDATION DEPENDENCIES
# =============================================================================

def validate_team_id(team_id: int) -> int:
    """
    Validates that a team ID is in the valid FPL range.
    FPL team IDs are positive integers, typically 1 to ~10 million.
    """
    if team_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Team ID must be a positive integer"
        )
    if team_id > 50_000_000:  # Reasonable upper bound
        raise HTTPException(
            status_code=400,
            detail="Team ID exceeds maximum valid range"
        )
    return team_id


def validate_player_id(player_id: int) -> int:
    """
    Validates that a player ID is in the valid FPL range.
    FPL player IDs are typically 1 to ~1000.
    """
    if player_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Player ID must be a positive integer"
        )
    if player_id > 2000:  # FPL rarely has more than 700 players
        raise HTTPException(
            status_code=400,
            detail="Player ID exceeds maximum valid range"
        )
    return player_id


def validate_gameweek(gameweek: int) -> int:
    """Validates that a gameweek is in the valid range (1-38)."""
    if gameweek < 1 or gameweek > 38:
        raise HTTPException(
            status_code=400,
            detail="Gameweek must be between 1 and 38"
        )
    return gameweek


# =============================================================================
# PAGINATION DEPENDENCIES
# =============================================================================

class PaginationParams:
    """Standard pagination parameters."""

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    ):
        self.skip = skip
        self.limit = limit


def get_pagination(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
) -> PaginationParams:
    """
    Provides standardized pagination parameters.

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends(get_pagination)):
            return items[pagination.skip:pagination.skip + pagination.limit]
    """
    return PaginationParams(skip=skip, limit=limit)


# =============================================================================
# REQUEST CONTEXT DEPENDENCIES
# =============================================================================

def get_request_id(request: Request) -> str:
    """
    Gets the request ID from the request state.
    Set by the error handler middleware.
    """
    return getattr(request.state, "request_id", "unknown")


def get_client_info(request: Request) -> dict:
    """
    Extracts client information from the request.
    Useful for logging and analytics.
    """
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", ""),
        "referer": request.headers.get("referer", ""),
    }


# =============================================================================
# OPTIONAL HEADER DEPENDENCIES
# =============================================================================

def get_api_version(
    x_api_version: Optional[str] = Header(None, alias="X-API-Version")
) -> str:
    """
    Gets the requested API version from headers.
    Defaults to "v1" if not specified.
    """
    return x_api_version or "v1"


# =============================================================================
# INITIALIZATION HELPERS
# =============================================================================

def reset_service_singletons():
    """
    Reset all service singletons.
    Useful for testing or when services need to be reinitialized.
    """
    global _fpl_service_instance, _kg_service_instance
    global _predictor_service_instance, _claude_service_instance

    _fpl_service_instance = None
    _kg_service_instance = None
    _predictor_service_instance = None
    _claude_service_instance = None

    logger.info("Service singletons reset")
