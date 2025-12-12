"""
Feedback API Router
Handles user feedback submission and admin retrieval.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import os
import hashlib

from database import get_db, UserFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


# =============================================================================
# Pydantic Models
# =============================================================================

class FeedbackSubmission(BaseModel):
    """Request model for feedback submission."""
    team_id: int = Field(..., ge=1, le=100_000_000)
    gameweek: int = Field(..., ge=1, le=38)
    feature_type: str = Field(..., min_length=1, max_length=50)
    rating: int = Field(..., ge=1, le=5)
    would_recommend: Optional[int] = Field(None, ge=0, le=10)
    comment: Optional[str] = Field(None, max_length=1000)
    followed_advice: Optional[bool] = None


class ComprehensiveFeedbackSubmission(BaseModel):
    """Request model for comprehensive feedback with multiple feature ratings."""
    team_id: int = Field(..., ge=1, le=100_000_000)
    gameweek: int = Field(..., ge=1, le=38)
    # Individual feature ratings (1-5, optional)
    ai_squad_analysis_rating: Optional[int] = Field(None, ge=1, le=5)
    transfer_suggestions_rating: Optional[int] = Field(None, ge=1, le=5)
    lineup_recommendation_rating: Optional[int] = Field(None, ge=1, le=5)
    captain_selection_rating: Optional[int] = Field(None, ge=1, le=5)
    overall_experience_rating: Optional[int] = Field(None, ge=1, le=5)
    # Followed advice: "yes", "no", "partially"
    followed_advice: Optional[str] = Field(None, pattern="^(yes|no|partially)$")
    # NPS score 0-10
    would_recommend: Optional[int] = Field(None, ge=0, le=10)
    # Additional comments
    comment: Optional[str] = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    """Response model for a single feedback entry."""
    id: int
    team_id: int
    gameweek: int
    feature_type: str
    rating: int
    would_recommend: Optional[int]
    comment: Optional[str]
    followed_advice: Optional[bool]
    created_at: datetime


class FeedbackStats(BaseModel):
    """Aggregated feedback statistics."""
    total_submissions: int
    avg_rating: float
    avg_nps: Optional[float]
    rating_distribution: dict
    feature_breakdown: dict
    recent_comments: list


class FeatureRanking(BaseModel):
    """Ranking for a single feature."""
    feature_type: str
    avg_rating: float
    total_ratings: int
    rating_distribution: dict  # {1: count, 2: count, ...}


class CommentEntry(BaseModel):
    """A single comment entry."""
    id: int
    team_id: int
    gameweek: int
    feature_type: str
    rating: int
    comment: str
    created_at: datetime


class AdminDashboard(BaseModel):
    """Enhanced admin dashboard with all stats."""
    # Overview
    unique_users: int
    total_submissions: int
    avg_overall_rating: float
    avg_nps: Optional[float]

    # Feature rankings (sorted by avg rating desc)
    feature_rankings: list[FeatureRanking]

    # NPS breakdown
    nps_promoters: int  # 9-10
    nps_passives: int   # 7-8
    nps_detractors: int # 0-6

    # Followed advice stats
    followed_yes: int
    followed_no: int
    followed_partially: int  # NULL values


class CommentsResponse(BaseModel):
    """Response for comments endpoint."""
    comments: list[CommentEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


class FeedbackListResponse(BaseModel):
    """Response for feedback list endpoint."""
    feedback: list[FeedbackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Admin Authentication
# =============================================================================

# Simple password-based authentication for admin
# In production, use a proper auth system
ADMIN_PASSWORD_HASH = os.getenv(
    "ADMIN_PASSWORD_HASH",
    # Default hash for "smartplay2024" - CHANGE THIS IN PRODUCTION
    hashlib.sha256("smartplay2024".encode()).hexdigest()
)


def verify_admin_password(password: str) -> bool:
    """Verify admin password."""
    return hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH


def require_admin(x_admin_password: str = Header(..., alias="X-Admin-Password")) -> bool:
    """Dependency to require admin authentication."""
    if not verify_admin_password(x_admin_password):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return True


# =============================================================================
# Public Endpoints
# =============================================================================

@router.post("/submit", response_model=dict)
async def submit_feedback(
    feedback: FeedbackSubmission,
    user_agent: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Submit user feedback for a feature.
    Public endpoint - no authentication required.
    """
    try:
        db_feedback = UserFeedback(
            team_id=feedback.team_id,
            gameweek=feedback.gameweek,
            feature_type=feedback.feature_type,
            rating=feedback.rating,
            would_recommend=feedback.would_recommend,
            comment=feedback.comment,
            followed_advice=feedback.followed_advice,
            user_agent=user_agent[:500] if user_agent else None
        )
        db.add(db_feedback)
        db.commit()
        db.refresh(db_feedback)

        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "id": db_feedback.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.post("/submit-comprehensive", response_model=dict)
async def submit_comprehensive_feedback(
    feedback: ComprehensiveFeedbackSubmission,
    user_agent: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Submit comprehensive feedback with multiple feature ratings.
    Stores each rating as a separate feedback entry for easier analysis.
    Public endpoint - no authentication required.
    """
    try:
        created_ids = []

        # Map of rating fields to feature types
        rating_fields = [
            ("ai_squad_analysis_rating", "AI Squad Analysis"),
            ("transfer_suggestions_rating", "Transfer Suggestions"),
            ("lineup_recommendation_rating", "Lineup Recommendation"),
            ("captain_selection_rating", "Captain Selection"),
            ("overall_experience_rating", "Overall Experience"),
        ]

        # Convert followed_advice string to boolean for storage
        followed_advice_bool = None
        if feedback.followed_advice == "yes":
            followed_advice_bool = True
        elif feedback.followed_advice == "no":
            followed_advice_bool = False
        # "partially" stays as None (ambiguous)

        # Create a feedback entry for each provided rating
        for field_name, feature_type in rating_fields:
            rating_value = getattr(feedback, field_name)
            if rating_value is not None:
                db_feedback = UserFeedback(
                    team_id=feedback.team_id,
                    gameweek=feedback.gameweek,
                    feature_type=feature_type,
                    rating=rating_value,
                    would_recommend=feedback.would_recommend,
                    comment=feedback.comment if feature_type == "Overall Experience" else None,
                    followed_advice=followed_advice_bool,
                    user_agent=user_agent[:500] if user_agent else None
                )
                db.add(db_feedback)
                db.flush()  # Get the ID
                created_ids.append(db_feedback.id)

        # If no ratings were provided, at least create an overall entry with comment
        if not created_ids and (feedback.comment or feedback.would_recommend is not None or feedback.followed_advice):
            db_feedback = UserFeedback(
                team_id=feedback.team_id,
                gameweek=feedback.gameweek,
                feature_type="General",
                rating=3,  # Default neutral rating
                would_recommend=feedback.would_recommend,
                comment=feedback.comment,
                followed_advice=followed_advice_bool,
                user_agent=user_agent[:500] if user_agent else None
            )
            db.add(db_feedback)
            db.flush()
            created_ids.append(db_feedback.id)

        db.commit()

        return {
            "success": True,
            "message": f"Comprehensive feedback submitted successfully ({len(created_ids)} entries)",
            "ids": created_ids,
            "entries_count": len(created_ids)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get("/admin/list", response_model=FeedbackListResponse)
async def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feature_type: Optional[str] = None,
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    gameweek: Optional[int] = Query(None, ge=1, le=38),
    has_comment: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """
    List all feedback with pagination and filters.
    Admin only - requires X-Admin-Password header.
    """
    query = db.query(UserFeedback)

    # Apply filters
    if feature_type:
        query = query.filter(UserFeedback.feature_type == feature_type)
    if min_rating:
        query = query.filter(UserFeedback.rating >= min_rating)
    if max_rating:
        query = query.filter(UserFeedback.rating <= max_rating)
    if gameweek:
        query = query.filter(UserFeedback.gameweek == gameweek)
    if has_comment is not None:
        if has_comment:
            query = query.filter(UserFeedback.comment.isnot(None), UserFeedback.comment != "")
        else:
            query = query.filter((UserFeedback.comment.is_(None)) | (UserFeedback.comment == ""))

    # Get total count
    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    # Apply pagination
    feedback_list = (
        query
        .order_by(desc(UserFeedback.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return FeedbackListResponse(
        feedback=[
            FeedbackResponse(
                id=f.id,
                team_id=f.team_id,
                gameweek=f.gameweek,
                feature_type=f.feature_type,
                rating=f.rating,
                would_recommend=f.would_recommend,
                comment=f.comment,
                followed_advice=f.followed_advice,
                created_at=f.created_at
            )
            for f in feedback_list
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/admin/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """
    Get aggregated feedback statistics.
    Admin only - requires X-Admin-Password header.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Base query for time period
    base_query = db.query(UserFeedback).filter(UserFeedback.created_at >= cutoff_date)

    # Total submissions
    total_submissions = base_query.count()

    if total_submissions == 0:
        return FeedbackStats(
            total_submissions=0,
            avg_rating=0.0,
            avg_nps=None,
            rating_distribution={str(i): 0 for i in range(1, 6)},
            feature_breakdown={},
            recent_comments=[]
        )

    # Average rating
    avg_rating = db.query(func.avg(UserFeedback.rating)).filter(
        UserFeedback.created_at >= cutoff_date
    ).scalar() or 0.0

    # Average NPS
    avg_nps = db.query(func.avg(UserFeedback.would_recommend)).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.would_recommend.isnot(None)
    ).scalar()

    # Rating distribution
    rating_counts = db.query(
        UserFeedback.rating,
        func.count(UserFeedback.id)
    ).filter(
        UserFeedback.created_at >= cutoff_date
    ).group_by(UserFeedback.rating).all()

    rating_distribution = {str(i): 0 for i in range(1, 6)}
    for rating, count in rating_counts:
        rating_distribution[str(rating)] = count

    # Feature breakdown
    feature_counts = db.query(
        UserFeedback.feature_type,
        func.count(UserFeedback.id),
        func.avg(UserFeedback.rating)
    ).filter(
        UserFeedback.created_at >= cutoff_date
    ).group_by(UserFeedback.feature_type).all()

    feature_breakdown = {
        feature: {
            "count": count,
            "avg_rating": round(float(avg or 0), 2)
        }
        for feature, count, avg in feature_counts
    }

    # Recent comments
    recent_with_comments = (
        base_query
        .filter(UserFeedback.comment.isnot(None), UserFeedback.comment != "")
        .order_by(desc(UserFeedback.created_at))
        .limit(10)
        .all()
    )

    recent_comments = [
        {
            "id": f.id,
            "rating": f.rating,
            "feature_type": f.feature_type,
            "comment": f.comment,
            "created_at": f.created_at.isoformat()
        }
        for f in recent_with_comments
    ]

    return FeedbackStats(
        total_submissions=total_submissions,
        avg_rating=round(float(avg_rating), 2),
        avg_nps=round(float(avg_nps), 2) if avg_nps else None,
        rating_distribution=rating_distribution,
        feature_breakdown=feature_breakdown,
        recent_comments=recent_comments
    )


@router.get("/admin/dashboard", response_model=AdminDashboard)
async def get_admin_dashboard(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """
    Enhanced admin dashboard with feature rankings, unique users, and NPS breakdown.
    Admin only - requires X-Admin-Password header.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Unique users (distinct team_ids)
    unique_users = db.query(func.count(func.distinct(UserFeedback.team_id))).filter(
        UserFeedback.created_at >= cutoff_date
    ).scalar() or 0

    # Total submissions
    total_submissions = db.query(UserFeedback).filter(
        UserFeedback.created_at >= cutoff_date
    ).count()

    # Average overall rating
    avg_rating = db.query(func.avg(UserFeedback.rating)).filter(
        UserFeedback.created_at >= cutoff_date
    ).scalar() or 0.0

    # Average NPS
    avg_nps = db.query(func.avg(UserFeedback.would_recommend)).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.would_recommend.isnot(None)
    ).scalar()

    # Feature rankings with rating distribution
    feature_stats = db.query(
        UserFeedback.feature_type,
        func.avg(UserFeedback.rating).label('avg_rating'),
        func.count(UserFeedback.id).label('count')
    ).filter(
        UserFeedback.created_at >= cutoff_date
    ).group_by(UserFeedback.feature_type).all()

    feature_rankings = []
    for feature_type, avg_r, count in feature_stats:
        # Get rating distribution for this feature
        rating_dist = db.query(
            UserFeedback.rating,
            func.count(UserFeedback.id)
        ).filter(
            UserFeedback.created_at >= cutoff_date,
            UserFeedback.feature_type == feature_type
        ).group_by(UserFeedback.rating).all()

        dist_dict = {str(i): 0 for i in range(1, 6)}
        for rating, cnt in rating_dist:
            dist_dict[str(rating)] = cnt

        feature_rankings.append(FeatureRanking(
            feature_type=feature_type,
            avg_rating=round(float(avg_r or 0), 2),
            total_ratings=count,
            rating_distribution=dist_dict
        ))

    # Sort by average rating descending
    feature_rankings.sort(key=lambda x: x.avg_rating, reverse=True)

    # NPS breakdown - count unique submissions (distinct team_id + gameweek combinations)
    # This avoids counting the same NPS score multiple times when comprehensive feedback
    # creates multiple rows (one per feature) with the same NPS value
    nps_promoters = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.would_recommend >= 9
    ).scalar() or 0

    nps_passives = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.would_recommend >= 7,
        UserFeedback.would_recommend <= 8
    ).scalar() or 0

    nps_detractors = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.would_recommend <= 6,
        UserFeedback.would_recommend.isnot(None)
    ).scalar() or 0

    # Followed advice stats - count unique submissions
    followed_yes = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.followed_advice == True
    ).scalar() or 0

    followed_no = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.followed_advice == False
    ).scalar() or 0

    followed_partially = db.query(
        func.count(func.distinct(func.concat(UserFeedback.team_id, '-', UserFeedback.gameweek)))
    ).filter(
        UserFeedback.created_at >= cutoff_date,
        UserFeedback.followed_advice.is_(None)
    ).scalar() or 0

    return AdminDashboard(
        unique_users=unique_users,
        total_submissions=total_submissions,
        avg_overall_rating=round(float(avg_rating), 2),
        avg_nps=round(float(avg_nps), 2) if avg_nps else None,
        feature_rankings=feature_rankings,
        nps_promoters=nps_promoters,
        nps_passives=nps_passives,
        nps_detractors=nps_detractors,
        followed_yes=followed_yes,
        followed_no=followed_no,
        followed_partially=followed_partially
    )


@router.get("/admin/comments", response_model=CommentsResponse)
async def get_comments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feature_type: Optional[str] = None,
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """
    Get all comments with pagination.
    Admin only - requires X-Admin-Password header.
    """
    query = db.query(UserFeedback).filter(
        UserFeedback.comment.isnot(None),
        UserFeedback.comment != ""
    )

    if feature_type:
        query = query.filter(UserFeedback.feature_type == feature_type)
    if min_rating:
        query = query.filter(UserFeedback.rating >= min_rating)

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    comments_list = (
        query
        .order_by(desc(UserFeedback.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CommentsResponse(
        comments=[
            CommentEntry(
                id=c.id,
                team_id=c.team_id,
                gameweek=c.gameweek,
                feature_type=c.feature_type,
                rating=c.rating,
                comment=c.comment,
                created_at=c.created_at
            )
            for c in comments_list
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.delete("/admin/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """
    Delete a specific feedback entry.
    Admin only - requires X-Admin-Password header.
    """
    feedback = db.query(UserFeedback).filter(UserFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    db.delete(feedback)
    db.commit()

    return {"success": True, "message": f"Feedback {feedback_id} deleted"}
