"""Pydantic models for SmartPlayFPL."""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Input Validation Models
# =============================================================================

class TeamIdPath(BaseModel):
    """Validated team_id path parameter."""
    team_id: int = Field(..., ge=1, le=100_000_000, description="FPL Team ID (1-100M)")


class GameweekPath(BaseModel):
    """Validated gameweek path parameter."""
    gameweek: int = Field(..., ge=1, le=38, description="Gameweek number (1-38)")


class PlayerIdPath(BaseModel):
    """Validated player_id path parameter."""
    player_id: int = Field(..., ge=1, le=1000, description="FPL Player ID (1-1000)")


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    page: int = Field(1, ge=1, le=1000, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class PlayerFilterParams(BaseModel):
    """Parameters for filtering players."""
    position: Optional[Literal["GKP", "DEF", "MID", "FWD"]] = Field(None, description="Filter by position")
    team_id: Optional[int] = Field(None, ge=1, le=20, description="Filter by team ID (1-20)")
    min_price: Optional[float] = Field(None, ge=3.5, le=15.0, description="Minimum price (3.5-15.0)")
    max_price: Optional[float] = Field(None, ge=3.5, le=15.5, description="Maximum price (3.5-15.5)")
    min_form: Optional[float] = Field(None, ge=0.0, le=20.0, description="Minimum form score")
    min_ownership: Optional[float] = Field(None, ge=0.0, le=100.0, description="Minimum ownership %")
    max_ownership: Optional[float] = Field(None, ge=0.0, le=100.0, description="Maximum ownership %")
    sort_by: Optional[Literal["form", "price", "ownership", "points", "transfers_in", "smartplay_score"]] = Field(
        "smartplay_score", description="Sort field"
    )
    sort_order: Optional[Literal["asc", "desc"]] = Field("desc", description="Sort order")

    @field_validator('max_price')
    @classmethod
    def max_price_greater_than_min(cls, v, info):
        if info.data.get('min_price') and v and v < info.data['min_price']:
            raise ValueError('max_price must be >= min_price')
        return v


class TransferParams(BaseModel):
    """Parameters for transfer suggestions."""
    max_suggestions: int = Field(5, ge=1, le=15, description="Maximum transfer suggestions (1-15)")
    include_hits: bool = Field(False, description="Include hit-worthy transfers")
    budget_flexibility: float = Field(0.0, ge=0.0, le=5.0, description="Extra budget tolerance in millions")


class LineupParams(BaseModel):
    """Parameters for lineup optimization."""
    strategy: Optional[Literal["balanced", "attacking", "defensive"]] = Field(
        "balanced", description="Lineup strategy"
    )
    bench_boost: bool = Field(False, description="Optimize for bench boost")
    force_captain: Optional[int] = Field(None, ge=1, le=1000, description="Force specific player as captain")


class MLScoreParams(BaseModel):
    """Parameters for ML scoring endpoints."""
    recalculate: bool = Field(False, description="Force recalculation of scores")
    gameweek: Optional[int] = Field(None, ge=1, le=38, description="Specific gameweek to calculate for")


class CacheInvalidationParams(BaseModel):
    """Parameters for cache invalidation."""
    cache_types: list[Literal["global", "teams", "live", "kg", "all"]] = Field(
        ["all"], description="Cache types to invalidate"
    )


# =============================================================================
# FPL Data Models
# =============================================================================

class Team(BaseModel):
    """Premier League team."""
    id: int
    name: str
    short_name: str
    strength: int
    strength_overall_home: int
    strength_overall_away: int
    strength_attack_home: int
    strength_attack_away: int
    strength_defence_home: int
    strength_defence_away: int


class Player(BaseModel):
    """FPL player with key stats."""
    id: int
    web_name: str
    first_name: str
    second_name: str
    team: int
    team_name: Optional[str] = None
    element_type: int  # 1=GKP, 2=DEF, 3=MID, 4=FWD
    position: Optional[str] = None
    now_cost: int  # Price in 0.1m units (e.g., 100 = £10.0m)
    total_points: int
    form: str  # String from API, convert to float
    selected_by_percent: str  # Ownership %
    minutes: int
    goals_scored: int
    assists: int
    clean_sheets: int
    yellow_cards: int
    red_cards: int
    bonus: int
    influence: str
    creativity: str
    threat: str
    ict_index: str
    expected_goals: str
    expected_assists: str
    expected_goal_involvements: str
    expected_goals_conceded: str
    transfers_in_event: int
    transfers_out_event: int
    status: str  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable
    news: str
    chance_of_playing_next_round: Optional[int] = None
    
    @property
    def price(self) -> float:
        """Price in millions (e.g., 10.0)."""
        return self.now_cost / 10
    
    @property
    def form_float(self) -> float:
        """Form as float."""
        try:
            return float(self.form)
        except ValueError:
            return 0.0
    
    @property
    def ownership(self) -> float:
        """Ownership as float percentage."""
        try:
            return float(self.selected_by_percent)
        except ValueError:
            return 0.0


class Fixture(BaseModel):
    """FPL fixture."""
    id: int
    event: Optional[int]  # Gameweek number
    team_h: int  # Home team ID
    team_a: int  # Away team ID
    team_h_difficulty: int  # FDR for home team
    team_a_difficulty: int  # FDR for away team
    finished: bool
    team_h_score: Optional[int] = None
    team_a_score: Optional[int] = None
    kickoff_time: Optional[str] = None


class Gameweek(BaseModel):
    """FPL gameweek."""
    id: int
    name: str
    deadline_time: str
    is_current: bool
    is_next: bool
    finished: bool
    average_entry_score: Optional[int] = None  # Average points for this GW
    highest_score: Optional[int] = None  # Highest score for this GW


class Pick(BaseModel):
    """A player pick in a manager's team."""
    element: int  # Player ID
    position: int  # 1-15 (1-11 starting, 12-15 bench)
    multiplier: int  # 0=benched, 1=starting, 2=captain, 3=triple captain
    is_captain: bool
    is_vice_captain: bool


# =============================================================================
# Manager/Entry Models
# =============================================================================

class ManagerInfo(BaseModel):
    """FPL manager basic info."""
    id: int
    player_first_name: str
    player_last_name: str
    name: str  # Team name
    summary_overall_points: int
    summary_overall_rank: Optional[int]
    summary_event_points: Optional[int]
    summary_event_rank: Optional[int]
    started_event: Optional[int] = None  # GW when team was created
    current_event: Optional[int] = None  # Current GW

    @property
    def manager_name(self) -> str:
        return f"{self.player_first_name} {self.player_last_name}"


class ManagerHistory(BaseModel):
    """Manager's current season history entry."""
    event: int  # Gameweek
    points: int
    total_points: int
    rank: Optional[int]
    overall_rank: Optional[int]
    bank: int  # Money in bank (0.1m units)
    value: int  # Team value (0.1m units)
    event_transfers: int
    event_transfers_cost: int
    points_on_bench: int


class League(BaseModel):
    """Mini-league info."""
    id: int
    name: str
    entry_rank: Optional[int]
    entry_last_rank: Optional[int]


# =============================================================================
# API Response Models
# =============================================================================

class TeamAnalysisRequest(BaseModel):
    """Request for team analysis."""
    team_id: int


class PlayerSummary(BaseModel):
    """Simplified player data for frontend."""
    id: int
    name: str
    team: str
    position: str
    price: float
    form: float
    points: int  # Total season points
    gw_points: int = 0  # Points in this gameweek
    ownership: float
    status: str
    news: str
    is_captain: bool = False
    is_vice_captain: bool = False
    multiplier: int = 1


class SquadData(BaseModel):
    """Manager's squad for a gameweek."""
    starting: list[PlayerSummary]
    bench: list[PlayerSummary]
    captain_id: int
    vice_captain_id: int


class TeamAnalysisResponse(BaseModel):
    """Full team analysis response."""
    # Manager info
    manager: ManagerInfo
    
    # Current gameweek
    gameweek: Gameweek
    
    # Squad
    squad: SquadData
    
    # Team stats
    team_value: float
    bank: float
    free_transfers: int
    
    # Rankings
    gw_rank: Optional[int]
    overall_rank: Optional[int]
    
    # Mini-leagues
    leagues: list[League]


# =============================================================================
# Rival Intelligence Models
# =============================================================================

class RivalEntry(BaseModel):
    """A rival in a mini-league."""
    id: int
    team_name: str
    manager_name: str
    rank: int
    total_points: int
    gw_points: int


class PlayerInsight(BaseModel):
    """Player with insight data for rival comparison."""
    id: int
    name: str
    team: str
    ownership: float
    form: float
    transfers_in: int = 0
    transfers_out: int = 0


class RivalInsightCard(BaseModel):
    """A single insight card (e.g., Shared Picks, Your Edge)."""
    title: str
    icon: str
    you_have: bool  # True = YOU HAVE, False = DON'T HAVE
    description: str
    players: list[PlayerInsight]


class LeagueStanding(BaseModel):
    """User's standing in a specific league."""
    league_id: int
    league_name: str
    rank: int
    total_entries: Optional[int] = None


class RivalIntelligenceResponse(BaseModel):
    """Full rival intelligence response."""
    # Rankings
    gw_rank: Optional[int]
    overall_rank: Optional[int]
    gw_rank_percentile: Optional[int]
    
    # League standings
    leagues: list[LeagueStanding]
    
    # Rival insights
    total_rivals: int
    insights: list[RivalInsightCard]
    
    # Strategy summary
    strategy: str


# =============================================================================
# Crowd Intelligence Models
# =============================================================================

class CrowdPlayer(BaseModel):
    """Player entry in crowd intelligence cards."""
    id: int
    name: str
    team: str
    position: str
    ownership: float
    form: float
    transfers_in: int = 0
    transfers_out: int = 0


class CrowdIntelligenceCard(BaseModel):
    """A card in the crowd intelligence section."""
    title: str
    subtitle: str
    players: list[CrowdPlayer]


class CrowdIntelligenceResponse(BaseModel):
    """Crowd intelligence response - your squad vs the global FPL crowd."""
    differential_percentage: int  # How differential your squad is (0-100)

    # Cards for players you HAVE
    shared_picks: CrowdIntelligenceCard  # Template players (30%+ owned)
    your_edge: CrowdIntelligenceCard      # Differentials (<10% owned)
    rising: CrowdIntelligenceCard         # Being transferred IN
    being_sold: CrowdIntelligenceCard     # Being transferred OUT

    # Cards for players you DON'T have
    template_misses: CrowdIntelligenceCard  # High-owned players you're missing (20%+, form 3+)
    hidden_gems: CrowdIntelligenceCard      # Low-owned hot players (<10%, form 5+)
    bandwagons: CrowdIntelligenceCard       # Being heavily transferred in (50k+)
    form_leaders: CrowdIntelligenceCard     # Top form players available (form 6+)


# =============================================================================
# Decision Quality Models
# =============================================================================

class TransferQuality(BaseModel):
    """Transfer decision quality metrics."""
    success_rate: float  # Percentage of successful transfers (0-100)
    net_points_gained: int  # Total points gained from transfers
    hits_taken: int  # Total transfer cost in points
    total_transfers: int  # Number of transfers analyzed


class CaptainQuality(BaseModel):
    """Captain decision quality metrics."""
    success_rate: float  # Percentage of good captain picks (0-100)
    captain_points: int  # Total points from captain picks
    most_captained: str  # Most frequently captained player
    most_captained_count: int  # Times the top player was captained


class BenchManagement(BaseModel):
    """Bench management quality metrics."""
    points_on_bench: int  # Total points left on bench
    per_gameweek: float  # Average points wasted per gameweek
    insight: str  # Contextual message about bench management


class DecisionQualityResponse(BaseModel):
    """Full decision quality analysis response."""
    overall_score: int  # 0-100 decision score
    overall_insight: str  # Summary insight message
    key_insight: str  # Key actionable insight

    transfer_quality: TransferQuality
    captain_quality: CaptainQuality
    bench_management: BenchManagement

    gameweeks_analyzed: int  # Number of gameweeks in analysis


# =============================================================================
# Player Planner Models
# =============================================================================

class FixtureInfo(BaseModel):
    """Single fixture info for player planner."""
    gameweek: int
    opponent: str
    is_home: bool
    difficulty: int  # 1-5 FDR


class PlayerPlannerEntry(BaseModel):
    """A player entry in the player planner table."""
    id: int
    name: str
    team: str
    position: str
    price: float
    form: float
    points: int
    ownership: float
    transfers_in: int
    transfers_out: int
    fixtures: list[FixtureInfo]


class PlayerPlannerResponse(BaseModel):
    """Response for player planner endpoint."""
    current_gameweek: int
    players: list[PlayerPlannerEntry]


# =============================================================================
# Crowd Insights Models
# =============================================================================

class CrowdInsightPlayer(BaseModel):
    """Player info for crowd insights."""
    id: int
    name: str
    team: str
    price: float
    form: float
    ownership: float
    transfers_in: int
    transfers_out: int
    in_squad: bool = False


class CrowdInsightCard(BaseModel):
    """A single insight card for crowd insights."""
    type: str  # smart_money, under_radar, bandwagon, panic_sell, quick_hit, template_score
    title: str
    icon: str
    tag: str  # BUY, AVOID, CAPTAIN, etc.
    tag_color: str  # green, red, amber, blue
    description: str
    players: list[CrowdInsightPlayer] = []
    value: Optional[str] = None  # For template score: "Punty", "Balanced", "Template"


class CrowdInsightsResponse(BaseModel):
    """Response for crowd insights endpoint."""
    insights: list[CrowdInsightCard]
    template_score: float  # 0-100, higher = more template
    avg_ownership: float


# =============================================================================
# Transfer Workflow Models
# =============================================================================

class GWInsight(BaseModel):
    """A single insight about gameweek performance."""
    type: str  # positive, negative, neutral, warning
    icon: str  # crown, bench, star, alert, trending_down, rank
    text: str


class GWReviewResponse(BaseModel):
    """Response for GW review endpoint."""
    gw_points: int
    gw_rank: Optional[int]
    gw_average: Optional[int] = None
    gw_highest: Optional[int] = None
    rank_percentile: Optional[float] = None  # e.g., 1.8 means top 1.8%
    insights: list[GWInsight]
    summary: str


class TransferPlayerOut(BaseModel):
    """Player to transfer out."""
    id: int
    name: str
    team: str
    position: str
    price: float
    form: float
    reasons: list[str]
    smartplay_score: float = 0.0


class TransferPlayerIn(BaseModel):
    """Player to transfer in."""
    id: int
    name: str
    team: str
    position: str
    price: float
    form: float
    reasons: list[str]


class TransferAlternative(BaseModel):
    """Alternative transfer-in option."""
    id: int
    name: str
    team: str
    position: str
    price: float
    form: float
    total_points: int
    ownership: float
    transfers_in: int
    score: float
    reasons: list[str]
    smartplay_score: float = 0.0


class TransferSuggestion(BaseModel):
    """A single transfer suggestion."""
    out: TransferPlayerOut
    in_player: TransferPlayerIn  # 'in' is reserved keyword
    alternatives: list[TransferAlternative] = []
    cost_change: float
    priority: str  # high, medium, low


class TransferSuggestionsResponse(BaseModel):
    """Response for transfer suggestions endpoint."""
    free_transfers: int
    bank: float
    suggestions: list[TransferSuggestion]
    message: str


# =============================================================================
# Alerts Response Models (Step 2)
# =============================================================================

class Alert(BaseModel):
    """Individual alert for squad issues."""
    type: str  # injury, rotation, price, fixture
    severity: str  # high, medium, warning, info
    player_id: Optional[int]
    player_name: Optional[str]
    team: str
    message: str
    detail: str
    icon: str


class AlertsResponse(BaseModel):
    """Response for alerts endpoint."""
    alerts: list[Alert]
    summary: str


# =============================================================================
# Lineup Response Models (Step 4)
# =============================================================================

class SmartPlayData(BaseModel):
    """SmartPlay score breakdown."""
    final_score: float
    nailedness_score: float
    form_xg_score: float
    form_pts_score: float
    fixture_score: float
    next_opponent: str = ""
    next_fdr: int = 3


class LineupPlayer(BaseModel):
    """Player in lineup recommendation."""
    id: int
    name: str
    position: str
    team: str
    price: float = 0.0
    form: float = 0.0
    ownership: float = 0.0
    points: int = 0
    gw_points: int = 0
    status: str = "a"
    news: str = ""
    is_captain: bool = False
    is_vice_captain: bool = False
    score: float
    reasons: list[str] = []
    smartplay_data: Optional[SmartPlayData] = None


class BenchPlayer(BaseModel):
    """Player on bench with order."""
    id: int
    name: str
    position: str
    team: str
    price: float = 0.0
    form: float = 0.0
    ownership: float = 0.0
    points: int = 0
    gw_points: int = 0
    status: str = "a"
    news: str = ""
    is_captain: bool = False
    is_vice_captain: bool = False
    score: float
    order: int
    smartplay_data: Optional[SmartPlayData] = None


class CaptainPick(BaseModel):
    """Captain recommendation."""
    id: int
    name: str
    score: float
    reasons: list[str] = []


class ViceCaptainPick(BaseModel):
    """Vice captain recommendation."""
    id: int
    name: str
    score: float


class LineupResponse(BaseModel):
    """Response for lineup recommendation endpoint."""
    formation: str
    starting_xi: list[LineupPlayer]
    bench: list[BenchPlayer]
    captain: Optional[CaptainPick]
    vice_captain: Optional[ViceCaptainPick]
    summary: str


class FormationStrategy(BaseModel):
    """A formation strategy option with lineup and SmartPlay score."""
    strategy: str  # balanced, attacking, defensive
    name: str  # Display name
    formation: str  # e.g. "4-4-2"
    total_smartplay_score: float  # Sum of starting XI SmartPlay scores
    avg_smartplay_score: float  # Average SmartPlay score
    starting_xi: list[LineupPlayer]
    bench: list[BenchPlayer]
    captain: Optional[CaptainPick]
    vice_captain: Optional[ViceCaptainPick]
    summary: str
    description: str  # Strategy description


class LineupStrategiesResponse(BaseModel):
    """Response containing all three formation strategies."""
    strategies: list[FormationStrategy]
    recommended: str  # The recommended strategy key


# =============================================================================
# Chip Advice Response Models (Step 5)
# =============================================================================

class ChipRecommendation(BaseModel):
    """Recommendation for a specific chip."""
    chip: str  # wildcard, freehit, bboost, 3xc
    name: str  # Display name
    recommendation: str  # consider, save
    score: int
    reasons: list[str]
    message: str


class ChipAdviceResponse(BaseModel):
    """Response for chip advice endpoint."""
    available_chips: list[str]
    recommendations: list[ChipRecommendation]
    overall_advice: str


# =============================================================================
# Claude AI Analysis Models
# =============================================================================

class SellCandidate(BaseModel):
    """Player analysis for potential sale."""
    id: int
    name: str
    team: str
    position: str
    price: float
    verdict: str  # SELL, HOLD, KEEPER
    priority: str  # critical, high, medium, low
    reasoning: str
    alternative_view: str = ""
    smartplay_score: float = 0.0
    nailedness_score: float = 0.0
    fixture_score: float = 0.0
    form: float = 0.0
    transfers_out: int = 0
    status: str = "a"
    news: str = ""


class SellAnalysisResponse(BaseModel):
    """Response from Claude sell analysis."""
    candidates: list[SellCandidate]
    summary: str
    ai_model: str


class BuyCandidate(BaseModel):
    """Player recommendation for purchase."""
    id: int
    name: str
    team: str
    position: str
    price: float
    verdict: str  # STRONG_BUY, BUY, WATCHLIST
    priority: str  # critical, high, medium, low
    reasoning: str
    form: float = 0.0
    total_points: int = 0
    ownership: float = 0.0
    transfers_in: int = 0
    expected_goals: float = 0.0
    expected_assists: float = 0.0
    ict_index: float = 0.0
    next_fixtures: list = []
    replaces: str = ""
    price_diff: float = 0.0


class BuyAnalysisResponse(BaseModel):
    """Response from Claude buy analysis."""
    recommendations: list[BuyCandidate]
    budget_available: float
    summary: str
    ai_model: str


# =============================================================================
# Squad Analysis Models
# =============================================================================

class SquadOptimizationTip(BaseModel):
    """A single optimization tip for the squad."""
    type: str  # balance, structure, value, risk, opportunity, transfer_chain
    icon: str  # emoji
    title: str
    description: str
    priority: str  # high, medium, low


class ChipStrategy(BaseModel):
    """AI-generated chip strategy recommendation."""
    chip: str  # wildcard, freehit, bboost, 3xc, none
    chip_name: str  # Display name
    should_use: bool  # Whether to use this week
    reasoning: str  # Why to use or not use
    confidence: int  # 0-100 confidence in recommendation


class SquadAnalysisResponse(BaseModel):
    """Response from Claude squad analysis."""
    summary: str  # Overall squad assessment
    score: int  # Squad rating 1-100
    strengths: list[str]  # What's good about the squad
    weaknesses: list[str]  # Areas to improve
    optimization_tips: list[SquadOptimizationTip]
    chip_strategy: Optional[ChipStrategy] = None  # Chip recommendation
    ai_model: str



