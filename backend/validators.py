"""
Input validation schemas for SmartPlayFPL API.

Provides Pydantic models with comprehensive validation for all API inputs.
These validators ensure data integrity and provide clear error messages.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# =============================================================================
# BASE VALIDATORS
# =============================================================================

class TeamIdMixin:
    """Mixin for validating FPL team IDs."""

    @field_validator("team_id", mode="before", check_fields=False)
    @classmethod
    def validate_team_id(cls, v):
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Team ID must be a numeric value")
            v = int(v)
        if v < 1:
            raise ValueError("Team ID must be a positive integer")
        if v > 50_000_000:
            raise ValueError("Team ID exceeds maximum valid range")
        return v


class PlayerIdMixin:
    """Mixin for validating FPL player IDs."""

    @field_validator("player_id", mode="before", check_fields=False)
    @classmethod
    def validate_player_id(cls, v):
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Player ID must be a numeric value")
            v = int(v)
        if v < 1:
            raise ValueError("Player ID must be a positive integer")
        if v > 2000:
            raise ValueError("Player ID exceeds maximum valid range")
        return v


class GameweekMixin:
    """Mixin for validating gameweek numbers."""

    @field_validator("gameweek", mode="before", check_fields=False)
    @classmethod
    def validate_gameweek(cls, v):
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Gameweek must be a numeric value")
            v = int(v)
        if v < 1 or v > 38:
            raise ValueError("Gameweek must be between 1 and 38")
        return v


# =============================================================================
# TEAM-RELATED VALIDATORS
# =============================================================================

class TeamRequest(BaseModel, TeamIdMixin):
    """Request schema for team-related endpoints."""
    team_id: int = Field(..., description="FPL Manager Team ID")


class TeamAnalysisRequest(BaseModel, TeamIdMixin, GameweekMixin):
    """Request schema for team analysis endpoints."""
    team_id: int = Field(..., description="FPL Manager Team ID")
    gameweek: Optional[int] = Field(None, description="Gameweek to analyze (defaults to current)")
    include_bench: bool = Field(True, description="Include bench players in analysis")


class TransferRequest(BaseModel, TeamIdMixin):
    """Request schema for transfer analysis."""
    team_id: int = Field(..., description="FPL Manager Team ID")
    player_out_id: Optional[int] = Field(None, description="Player to sell")
    player_in_id: Optional[int] = Field(None, description="Player to buy")
    budget_remaining: Optional[float] = Field(None, ge=0, description="Remaining budget in millions")

    @field_validator("player_out_id", "player_in_id", mode="before")
    @classmethod
    def validate_optional_player_id(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError("Player ID must be a numeric value")
            v = int(v)
        if v < 1 or v > 2000:
            raise ValueError("Player ID must be between 1 and 2000")
        return v


# =============================================================================
# PLAYER-RELATED VALIDATORS
# =============================================================================

class PlayerRequest(BaseModel, PlayerIdMixin):
    """Request schema for player-related endpoints."""
    player_id: int = Field(..., description="FPL Player ID")


class PlayerFilterRequest(BaseModel):
    """Request schema for filtering players."""
    position: Optional[Literal["GKP", "DEF", "MID", "FWD"]] = Field(
        None, description="Position filter"
    )
    team_id: Optional[int] = Field(None, ge=1, le=20, description="Team filter (1-20)")
    min_price: Optional[float] = Field(None, ge=3.5, le=15.0, description="Minimum price")
    max_price: Optional[float] = Field(None, ge=3.5, le=15.0, description="Maximum price")
    min_ownership: Optional[float] = Field(None, ge=0, le=100, description="Minimum ownership %")
    max_ownership: Optional[float] = Field(None, ge=0, le=100, description="Maximum ownership %")
    available_only: bool = Field(True, description="Only show available players")

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.min_price and self.max_price:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")
        return self

    @model_validator(mode="after")
    def validate_ownership_range(self):
        if self.min_ownership and self.max_ownership:
            if self.min_ownership > self.max_ownership:
                raise ValueError("min_ownership cannot be greater than max_ownership")
        return self


class AlternativesRequest(BaseModel, PlayerIdMixin):
    """Request schema for finding player alternatives."""
    player_id: int = Field(..., description="Player ID to find alternatives for")
    max_price: Optional[float] = Field(None, ge=3.5, le=15.0, description="Maximum price filter")
    limit: int = Field(5, ge=1, le=20, description="Number of alternatives to return")


# =============================================================================
# ML PREDICTOR VALIDATORS
# =============================================================================

class ScoreFilterRequest(BaseModel):
    """Request schema for filtering ML scores."""
    position: Optional[Literal["GKP", "DEF", "MID", "FWD"]] = Field(
        None, description="Position filter"
    )
    min_score: Optional[float] = Field(None, ge=0, le=10, description="Minimum score")
    min_nailedness: Optional[float] = Field(None, ge=0, le=10, description="Minimum nailedness")
    limit: int = Field(100, ge=1, le=500, description="Maximum results to return")


class CaptainPicksRequest(BaseModel):
    """Request schema for captain picks."""
    limit: int = Field(10, ge=1, le=25, description="Number of picks to return")
    exclude_player_ids: Optional[List[int]] = Field(
        None, description="Player IDs to exclude"
    )

    @field_validator("exclude_player_ids", mode="before")
    @classmethod
    def validate_exclude_list(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("exclude_player_ids must be a list")
        for pid in v:
            if not isinstance(pid, int) or pid < 1 or pid > 2000:
                raise ValueError(f"Invalid player ID in exclude list: {pid}")
        return v


# =============================================================================
# SQUAD BUILDER VALIDATORS
# =============================================================================

class SquadBuildRequest(BaseModel):
    """Request schema for building squads."""
    strategy: Literal["value", "template", "differential", "balanced"] = Field(
        "balanced", description="Squad building strategy"
    )
    budget: float = Field(100.0, ge=80.0, le=105.0, description="Total budget")
    formation: Optional[str] = Field(
        None, description="Preferred formation (e.g., '3-4-3')"
    )
    required_players: Optional[List[int]] = Field(
        None, description="Player IDs that must be included"
    )
    excluded_players: Optional[List[int]] = Field(
        None, description="Player IDs that must be excluded"
    )
    max_from_team: int = Field(3, ge=1, le=3, description="Max players from one team")

    @field_validator("formation", mode="before")
    @classmethod
    def validate_formation(cls, v):
        if v is None:
            return v
        pattern = r"^[3-5]-[2-5]-[1-3]$"
        if not re.match(pattern, v):
            raise ValueError("Formation must be in format like '3-4-3' or '4-4-2'")
        parts = [int(x) for x in v.split("-")]
        if sum(parts) != 10:
            raise ValueError("Formation must sum to 10 outfield players")
        return v


# =============================================================================
# KNOWLEDGE GRAPH VALIDATORS
# =============================================================================

class KGQueryRequest(BaseModel):
    """Request schema for Knowledge Graph queries."""
    query_type: Literal["player", "team", "fixture", "form", "injury"] = Field(
        ..., description="Type of query"
    )
    entity_id: Optional[int] = Field(None, description="Entity ID (player or team)")
    sparql: Optional[str] = Field(None, max_length=2000, description="Raw SPARQL query")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results")

    @field_validator("sparql", mode="before")
    @classmethod
    def validate_sparql_safety(cls, v):
        if v is None:
            return v
        # Basic SQL injection prevention (not comprehensive)
        dangerous_keywords = ["DELETE", "DROP", "INSERT", "UPDATE", "CLEAR"]
        v_upper = v.upper()
        for keyword in dangerous_keywords:
            if keyword in v_upper:
                raise ValueError(f"SPARQL query contains forbidden keyword: {keyword}")
        return v


# =============================================================================
# AI ANALYSIS VALIDATORS
# =============================================================================

class AIAnalysisRequest(BaseModel, TeamIdMixin):
    """Request schema for AI-powered analysis."""
    team_id: int = Field(..., description="FPL Manager Team ID")
    analysis_type: Literal["squad", "transfers", "captain", "gw_review"] = Field(
        ..., description="Type of analysis"
    )
    context: Optional[str] = Field(
        None, max_length=500, description="Additional context for analysis"
    )
    force_refresh: bool = Field(False, description="Bypass cache for fresh analysis")

    @field_validator("context", mode="before")
    @classmethod
    def sanitize_context(cls, v):
        if v is None:
            return v
        # Basic sanitization - remove potential injection attempts
        v = re.sub(r"[<>{}]", "", v)
        return v.strip()


# =============================================================================
# PAGINATION VALIDATORS
# =============================================================================

class PaginationRequest(BaseModel):
    """Request schema for paginated endpoints."""
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(100, ge=1, le=500, description="Maximum items to return")


# =============================================================================
# CACHE MANAGEMENT VALIDATORS
# =============================================================================

class CacheInvalidateRequest(BaseModel):
    """Request schema for cache invalidation."""
    cache_types: List[Literal["global", "teams", "live", "kg", "claude", "all"]] = Field(
        ["all"], description="Cache types to invalidate"
    )

    @field_validator("cache_types", mode="before")
    @classmethod
    def validate_cache_types(cls, v):
        if isinstance(v, str):
            v = [v]
        return v
