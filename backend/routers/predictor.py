"""
API Router for ML Predictor Scores

Provides endpoints for accessing the ML-based player scoring system.
Scores are pre-calculated and stored in database for fast retrieval.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
from sqlalchemy.orm import Session
from datetime import datetime

from services.predictor_service import get_predictor_service
from database import get_db, MLPlayerScore as DBMLPlayerScore, CalculationLog, init_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictor", tags=["ML Predictor"])

# Initialize database on module load
init_db()


# =========================================================================
# Response Models
# =========================================================================

class PlayerScore(BaseModel):
    """ML score data for a single player."""
    player_id: int
    name: str
    full_name: str
    team: str
    team_id: int
    position: str
    price: float
    ownership: float
    status: str
    news: str
    # Component scores (0-10 scale)
    nailedness_score: float
    form_xg_score: float
    form_pts_score: float
    fixture_score: float
    # Final combined score (0-10 scale)
    final_score: float
    # Additional context
    avg_minutes: float
    avg_points: float
    total_points: int
    form: float
    next_opponent: str
    next_fdr: int
    next_home: bool
    rank: int

    class Config:
        from_attributes = True


class PredictorStatusResponse(BaseModel):
    """Status of the predictor service."""
    is_initialized: bool
    player_count: int
    last_update: Optional[str]
    gameweek: Optional[int]


class CalculateResponse(BaseModel):
    """Response from score calculation."""
    success: bool
    players_scored: int
    gameweek: int
    elapsed_seconds: float
    last_update: str


class TopPlayersResponse(BaseModel):
    """Top players by position."""
    position: str
    players: List[PlayerScore]


# =========================================================================
# Endpoints
# =========================================================================

@router.get("/status", response_model=PredictorStatusResponse)
async def get_predictor_status(db: Session = Depends(get_db)):
    """Get the current status of the ML predictor service."""
    # Check if we have scores in database
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if latest_score:
        player_count = db.query(DBMLPlayerScore).filter(
            DBMLPlayerScore.gameweek == latest_score.gameweek
        ).count()

        return PredictorStatusResponse(
            is_initialized=True,
            player_count=player_count,
            last_update=latest_score.calculated_at.isoformat(),
            gameweek=latest_score.gameweek,
        )
    else:
        return PredictorStatusResponse(
            is_initialized=False,
            player_count=0,
            last_update=None,
            gameweek=None,
        )


@router.post("/calculate", response_model=CalculateResponse)
async def calculate_scores(db: Session = Depends(get_db)):
    """
    Calculate/refresh ML scores for all players and save to database.

    This runs the full prediction pipeline:
    1. Fetch FPL data
    2. Calculate fixture difficulty
    3. Fetch player histories
    4. Calculate component and final scores
    5. Save to database

    Takes ~1-2 minutes to complete.
    """
    predictor = get_predictor_service()
    start_time = datetime.utcnow()

    try:
        # Calculate scores and save to database
        result = await predictor.calculate_scores(db=db)

        # Log the calculation
        log_entry = CalculationLog(
            gameweek=result["gameweek"],
            players_scored=result["players_scored"],
            elapsed_seconds=result["elapsed_seconds"],
            success=True,
            error_message=None,
            started_at=start_time,
            completed_at=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()

        return CalculateResponse(**result)

    except Exception as e:
        logger.error(f"Score calculation failed: {e}")

        # Log the failed calculation
        log_entry = CalculationLog(
            gameweek=0,
            players_scored=0,
            elapsed_seconds=(datetime.utcnow() - start_time).total_seconds(),
            success=False,
            error_message=str(e),
            started_at=start_time,
            completed_at=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player/{player_id}", response_model=PlayerScore)
async def get_player_score(player_id: int, db: Session = Depends(get_db)):
    """
    Get ML score for a specific player from database.

    Returns the full score breakdown including:
    - Nailedness score
    - Form (xG) score
    - Form (points) score
    - Fixture score
    - Final combined score
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get player score for latest gameweek
    score = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.player_id == player_id,
        DBMLPlayerScore.gameweek == latest_score.gameweek
    ).first()

    if not score:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    return PlayerScore.from_orm(score)


@router.get("/scores", response_model=List[PlayerScore])
async def get_all_scores(
    limit: int = 100,
    position: Optional[str] = None,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Get ML scores for all players from database.

    Args:
        limit: Maximum number of players to return (default 100)
        position: Filter by position (GKP, DEF, MID, FWD)
        min_score: Minimum final_score to include
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Build query
    query = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek
    )

    if position:
        query = query.filter(DBMLPlayerScore.position == position.upper())

    if min_score is not None:
        query = query.filter(DBMLPlayerScore.final_score >= min_score)

    # Order by final score and apply limit
    scores = query.order_by(DBMLPlayerScore.final_score.desc()).limit(limit).all()

    return [PlayerScore.from_orm(score) for score in scores]


@router.get("/top/{position}", response_model=TopPlayersResponse)
async def get_top_by_position(position: str, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get top players for a specific position from database.

    Args:
        position: Position code (GKP, DEF, MID, FWD)
        limit: Number of players to return (default 10)
    """
    position = position.upper()
    if position not in ['GKP', 'DEF', 'MID', 'FWD']:
        raise HTTPException(status_code=400, detail=f"Invalid position: {position}")

    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get top players for position
    scores = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek,
        DBMLPlayerScore.position == position
    ).order_by(DBMLPlayerScore.final_score.desc()).limit(limit).all()

    return TopPlayersResponse(
        position=position,
        players=[PlayerScore.from_orm(score) for score in scores],
    )


@router.get("/captain-picks", response_model=List[PlayerScore])
async def get_captain_picks(limit: int = 10, db: Session = Depends(get_db)):
    """
    Get recommended captain picks from database.

    Returns players with:
    - High nailedness (>= 8)
    - Attacking positions (MID/FWD preferred)
    - Good overall score
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get captain candidates
    scores = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek,
        DBMLPlayerScore.nailedness_score >= 8,
        DBMLPlayerScore.status == 'a',
        DBMLPlayerScore.position.in_(['MID', 'FWD'])
    ).order_by(DBMLPlayerScore.final_score.desc()).limit(limit).all()

    return [PlayerScore.from_orm(score) for score in scores]


@router.get("/differential-picks", response_model=List[PlayerScore])
async def get_differential_picks(max_ownership: float = 10.0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get differential picks from database - high scoring players with low ownership.

    Args:
        max_ownership: Maximum ownership percentage (default 10%)
        limit: Number of players to return
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get differentials
    scores = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek,
        DBMLPlayerScore.ownership <= max_ownership,
        DBMLPlayerScore.status == 'a',
        DBMLPlayerScore.nailedness_score >= 6
    ).order_by(DBMLPlayerScore.final_score.desc()).limit(limit).all()

    return [PlayerScore.from_orm(score) for score in scores]


@router.get("/value-picks", response_model=List[PlayerScore])
async def get_value_picks(max_price: float = 7.0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Get value picks from database - best score per price players.

    Args:
        max_price: Maximum price in millions (default £7.0m)
        limit: Number of players to return
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get value picks (sorted by final_score / price ratio)
    scores = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek,
        DBMLPlayerScore.price <= max_price,
        DBMLPlayerScore.price > 0,
        DBMLPlayerScore.status == 'a',
        DBMLPlayerScore.nailedness_score >= 6
    ).order_by(
        (DBMLPlayerScore.final_score / DBMLPlayerScore.price).desc()
    ).limit(limit).all()

    return [PlayerScore.from_orm(score) for score in scores]


class AlternativePlayer(BaseModel):
    """Alternative player suggestion with SmartPlay score."""
    player_id: int
    name: str
    full_name: str
    team: str
    team_id: int
    position: str
    price: float
    ownership: float
    form: float
    total_points: int
    final_score: float
    nailedness_score: float
    fixture_score: float
    price_diff: float
    why_recommended: str


class AlternativesResponse(BaseModel):
    """Response for player alternatives."""
    player_id: int
    player_name: str
    position: str
    alternatives: List[AlternativePlayer]


@router.get("/player/{player_id}/alternatives", response_model=AlternativesResponse)
async def get_player_alternatives(
    player_id: int,
    max_price: Optional[float] = None,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """
    Get alternative players based on SmartPlay scores.

    Finds players of the same position with high SmartPlay scores.
    Only includes players with:
    - Same position
    - SmartPlay score >= 5.0
    - Nailedness >= 6.0
    - Status 'a' (available)

    Args:
        player_id: ID of the player to find alternatives for
        max_price: Optional maximum price filter
        limit: Number of alternatives to return (default 5)
    """
    # Get latest gameweek
    latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

    if not latest_score:
        raise HTTPException(
            status_code=400,
            detail="Predictor not initialized. Call POST /calculate first."
        )

    # Get the original player
    player = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.player_id == player_id,
        DBMLPlayerScore.gameweek == latest_score.gameweek
    ).first()

    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    # Build query for alternatives
    query = db.query(DBMLPlayerScore).filter(
        DBMLPlayerScore.gameweek == latest_score.gameweek,
        DBMLPlayerScore.position == player.position,
        DBMLPlayerScore.player_id != player_id,
        DBMLPlayerScore.final_score >= 5.0,  # Minimum quality threshold
        DBMLPlayerScore.nailedness_score >= 6.0,  # Must be reasonably nailed
        DBMLPlayerScore.status == 'a',  # Must be available
    )

    # Apply max price filter if provided
    if max_price is not None:
        query = query.filter(DBMLPlayerScore.price <= max_price)

    # Order by final score descending
    alternatives = query.order_by(DBMLPlayerScore.final_score.desc()).limit(limit).all()

    # Build response
    alt_list = []
    for alt in alternatives:
        price_diff = round(alt.price - player.price, 1)

        # Generate recommendation reason
        reasons = []
        if alt.final_score >= 7.5:
            reasons.append(f"Top SmartPlay score ({alt.final_score:.1f})")
        elif alt.final_score >= 6.5:
            reasons.append(f"Strong SmartPlay score ({alt.final_score:.1f})")
        else:
            reasons.append(f"Decent SmartPlay score ({alt.final_score:.1f})")

        if alt.nailedness_score >= 9.0:
            reasons.append("Highly nailed")

        if alt.fixture_score >= 7.0:
            reasons.append("Great fixtures")

        if price_diff < 0:
            reasons.append(f"Saves £{abs(price_diff)}m")

        why_recommended = " • ".join(reasons[:2])  # Max 2 reasons

        alt_list.append(AlternativePlayer(
            player_id=alt.player_id,
            name=alt.name,
            full_name=alt.full_name,
            team=alt.team,
            team_id=alt.team_id,
            position=alt.position,
            price=alt.price,
            ownership=alt.ownership,
            form=alt.form,
            total_points=alt.total_points,
            final_score=alt.final_score,
            nailedness_score=alt.nailedness_score,
            fixture_score=alt.fixture_score,
            price_diff=price_diff,
            why_recommended=why_recommended,
        ))

    return AlternativesResponse(
        player_id=player_id,
        player_name=player.name,
        position=player.position,
        alternatives=alt_list,
    )
