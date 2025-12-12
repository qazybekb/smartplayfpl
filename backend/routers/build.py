# backend/routers/build.py
"""
API Router for KG-Powered Squad Builder
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from services.squad_builder import SquadBuilder, Strategy, BuiltSquad, SquadPlayer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/build", tags=["Squad Builder"])


# =========================================================================
# Request/Response Models
# =========================================================================

class StrategyInfo(BaseModel):
    """Information about a strategy."""
    id: str
    name: str
    icon: str
    tagline: str
    description: str
    risk_level: str
    risk_color: str
    benefits: List[str]
    theme: Dict[str, str]  # color theme for UI


class SelectionTraceResponse(BaseModel):
    """Detailed trace of why a player was selected."""
    strategy_score: float
    rank_in_position: int
    total_in_position: int
    score_breakdown: Dict[str, Any]
    tag_bonuses: Dict[str, float]
    tag_penalties: Dict[str, float]
    alternatives: List[Dict[str, Any]]


class InferenceStepResponse(BaseModel):
    """A step in the OWL inference chain."""
    data_field: str
    data_value: str
    inferred_class: str
    rule: str
    contributed_to: str


class MLPredictionResponse(BaseModel):
    """ML prediction scores for a player."""
    p_plays: float  # Probability of playing (0-1)
    ml_score: float  # Overall ML-based score (0-100)
    nailedness_score: float  # How nailed the player is (0-100)
    form_score_xg: float  # Form based on xG/xA (0-100)
    form_score_pts: float  # Form based on points (0-100)
    fixture_score: float  # Fixture difficulty score (0-100)
    is_available: bool
    availability_reason: str


class PlayerResponse(BaseModel):
    """Player in a built squad."""
    id: int
    web_name: str
    full_name: str
    position: str
    team_id: int
    team_short: str
    price: float
    form: float
    ownership: float
    total_points: int
    points_per_million: float
    is_starter: bool
    is_captain: bool
    is_vice_captain: bool
    smart_tags: List[str]
    selection_reason: str
    bench_order: int
    selection_trace: Optional[SelectionTraceResponse] = None
    inference_chain: List[InferenceStepResponse] = []
    ml_prediction: Optional[MLPredictionResponse] = None  # ML prediction scores
    # SmartPlay score fields (0-10 scale)
    smartplay_score: float = 0.0
    nailedness_score: float = 0.0
    form_xg_score: float = 0.0
    form_pts_score: float = 0.0
    fixture_score: float = 0.0


class ConstraintResponse(BaseModel):
    """Constraint validation result."""
    name: str
    passed: bool
    message: str
    severity: str
    value: Optional[str] = None


class ValidationResponse(BaseModel):
    """Full validation result."""
    passed: bool
    hard_constraints: List[ConstraintResponse]
    soft_constraints: List[ConstraintResponse]
    error_count: int
    warning_count: int


class StrategyAnalysisResponse(BaseModel):
    """Strategy-specific analysis."""
    description: str
    metrics: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]


class FormationOptionResponse(BaseModel):
    """Analysis of a single formation option."""
    formation: str
    expected_points: float
    total_form: float
    is_selected: bool
    starters: List[str]
    benched: List[str]
    reasoning: str
    points_breakdown: Dict[str, float]


class FormationAnalysisResponse(BaseModel):
    """Complete formation comparison analysis."""
    selected_formation: str
    options: List[FormationOptionResponse]
    selection_reason: str
    expected_points_formula: str


class BuiltSquadResponse(BaseModel):
    """Complete built squad response."""
    players: List[PlayerResponse]
    formation: str
    total_cost: float
    in_the_bank: float
    validation: ValidationResponse
    strategy_id: str
    strategy_name: str
    strategy_analysis: StrategyAnalysisResponse
    formation_analysis: FormationAnalysisResponse
    sparql_queries: List[str]


class CustomBuildRequest(BaseModel):
    """Request for custom strategy build."""
    include_tags: List[str] = []
    exclude_tags: List[str] = []


class SwapRequest(BaseModel):
    """Request for player swap recommendations."""
    player_ids: List[int]
    player_out_id: int
    strategy_id: str


class ReplacementResponse(BaseModel):
    """Replacement option for a player."""
    player: PlayerResponse
    maintains_constraints: bool
    why_recommended: str


# =========================================================================
# Strategy Definitions
# =========================================================================

STRATEGIES: Dict[str, StrategyInfo] = {
    "smartplay": StrategyInfo(
        id="smartplay",
        name="SmartPlay Choice",
        icon="🤖",
        tagline="AI recommends",
        description="Pure AI optimization. Picks the highest SmartPlay scores without any strategy bias. This is what our system thinks is objectively the best squad right now.",
        risk_level="Medium",
        risk_color="cyan",
        benefits=[
            "Highest SmartPlay scores",
            "No strategy bias or filters",
            "AI's best recommendation"
        ],
        theme={
            "primary": "cyan",
            "gradient_from": "cyan-500",
            "gradient_to": "blue-600",
            "bg_pattern": "circuit",
            "accent": "cyan-400"
        }
    ),
    "template": StrategyInfo(
        id="template",
        name="Template Squad",
        icon="👥",
        tagline="Follow the winners",
        description="Build like the elite. Pick what the top managers own. Safe, proven, and protects your rank when popular players haul.",
        risk_level="Low",
        risk_color="emerald",
        benefits=[
            "High ownership, proven picks",
            "Protected when template hauls",
            "Low risk of falling behind"
        ],
        theme={
            "primary": "emerald",
            "gradient_from": "emerald-500",
            "gradient_to": "teal-600",
            "bg_pattern": "dots",
            "accent": "emerald-400"
        }
    ),
    "premium": StrategyInfo(
        id="premium",
        name="Premium & Punts",
        icon="💎",
        tagline="Stars + enablers",
        description="Load up on 2-3 premium superstars (£10m+) and fill the rest with budget enablers. Maximize points from the elite.",
        risk_level="Medium",
        risk_color="violet",
        benefits=[
            "2-3 premium stars in attack",
            "Budget enablers to fund them",
            "High ceiling from top scorers"
        ],
        theme={
            "primary": "violet",
            "gradient_from": "violet-500",
            "gradient_to": "purple-600",
            "bg_pattern": "stars",
            "accent": "violet-400"
        }
    ),
    "value": StrategyInfo(
        id="value",
        name="Value Hunters",
        icon="💰",
        tagline="Maximum bang for buck",
        description="Find players who punch above their price tag. High points-per-million ensures efficiency and leaves room to upgrade.",
        risk_level="Medium",
        risk_color="amber",
        benefits=[
            "Best points per £m ratio",
            "Budget for future upgrades",
            "Efficient squad structure"
        ],
        theme={
            "primary": "amber",
            "gradient_from": "amber-500",
            "gradient_to": "orange-600",
            "bg_pattern": "coins",
            "accent": "amber-400"
        }
    ),
    "form": StrategyInfo(
        id="form",
        name="Form Riders",
        icon="🔥",
        tagline="Chase the hot streaks",
        description="Ride the momentum. Pick players in blazing form who are returning points week after week. Strike while they're hot.",
        risk_level="Medium-High",
        risk_color="orange",
        benefits=[
            "Players in current hot form",
            "Momentum-based selection",
            "Capture points while they last"
        ],
        theme={
            "primary": "orange",
            "gradient_from": "orange-500",
            "gradient_to": "red-500",
            "bg_pattern": "flames",
            "accent": "orange-400"
        }
    ),
    "balanced": StrategyInfo(
        id="balanced",
        name="Balanced Squad",
        icon="⚖️",
        tagline="Best of all worlds",
        description="A well-rounded squad combining form, value, and reliability. Optimized for consistent returns without extreme risk or conservatism.",
        risk_level="Medium",
        risk_color="indigo",
        benefits=[
            "Mix of template and differentials",
            "Balanced risk-reward ratio",
            "Consistent point potential"
        ],
        theme={
            "primary": "indigo",
            "gradient_from": "indigo-500",
            "gradient_to": "blue-600",
            "bg_pattern": "balance",
            "accent": "indigo-400"
        }
    )
}


# =========================================================================
# Helper Functions
# =========================================================================

async def ensure_kg_ready():
    """Ensure Knowledge Graph is initialized and has player data.
    
    Returns the KG service instance, auto-rebuilding if needed.
    """
    from services.fpl_service import fpl_service
    from services.kg_service import get_kg_service
    
    kg = get_kg_service()
    
    # Auto-rebuild if no player data exists
    if not kg.has_player_data:
        kg.set_fpl_service(fpl_service)
        await kg.rebuild()
    
    return kg


async def get_squad_builder():
    """Get squad builder instance with services, ensuring KG is ready."""
    from services.fpl_service import fpl_service
    from services.ml_predictor_service import get_ml_predictor_service

    kg = await ensure_kg_ready()

    # Get ML predictor for availability filtering
    ml_predictor = get_ml_predictor_service()

    return SquadBuilder(kg, fpl_service, ml_predictor)


def squad_player_to_response(player: SquadPlayer) -> PlayerResponse:
    """Convert SquadPlayer to PlayerResponse."""

    # Convert selection trace if present
    selection_trace = None
    if player.selection_trace:
        selection_trace = SelectionTraceResponse(
            strategy_score=player.selection_trace.strategy_score,
            rank_in_position=player.selection_trace.rank_in_position,
            total_in_position=player.selection_trace.total_in_position,
            score_breakdown=player.selection_trace.score_breakdown,
            tag_bonuses=player.selection_trace.tag_bonuses,
            tag_penalties=player.selection_trace.tag_penalties,
            alternatives=player.selection_trace.alternatives
        )

    # Convert inference chain
    inference_chain = [
        InferenceStepResponse(
            data_field=step.data_field,
            data_value=step.data_value,
            inferred_class=step.inferred_class,
            rule=step.rule,
            contributed_to=step.contributed_to
        )
        for step in player.inference_chain
    ]

    # Convert ML prediction if present
    ml_prediction = None
    if player.ml_prediction:
        ml_prediction = MLPredictionResponse(
            p_plays=player.ml_prediction.p_plays,
            ml_score=player.ml_prediction.ml_score,
            nailedness_score=player.ml_prediction.nailedness_score,
            form_score_xg=player.ml_prediction.form_score_xg,
            form_score_pts=player.ml_prediction.form_score_pts,
            fixture_score=player.ml_prediction.fixture_score,
            is_available=player.ml_prediction.is_available,
            availability_reason=player.ml_prediction.availability_reason
        )

    return PlayerResponse(
        id=player.id,
        web_name=player.web_name,
        full_name=player.full_name,
        position=player.position,
        team_id=player.team_id,
        team_short=player.team_short,
        price=player.price,
        form=player.form,
        ownership=player.ownership,
        total_points=player.total_points,
        points_per_million=player.points_per_million,
        is_starter=player.is_starter,
        is_captain=player.is_captain,
        is_vice_captain=player.is_vice_captain,
        smart_tags=player.smart_tags,
        selection_reason=player.selection_reason,
        bench_order=player.bench_order,
        selection_trace=selection_trace,
        inference_chain=inference_chain,
        ml_prediction=ml_prediction,
        # SmartPlay score fields
        smartplay_score=player.smartplay_score,
        nailedness_score=player.nailedness_score,
        form_xg_score=player.form_xg_score,
        form_pts_score=player.form_pts_score,
        fixture_score=player.fixture_score
    )


def built_squad_to_response(squad: BuiltSquad) -> BuiltSquadResponse:
    """Convert BuiltSquad to BuiltSquadResponse."""
    strategy_info = STRATEGIES.get(squad.strategy.value, STRATEGIES["template"])
    
    # Convert formation options
    formation_options = [
        FormationOptionResponse(
            formation=opt.formation,
            expected_points=opt.expected_points,
            total_form=opt.total_form,
            is_selected=opt.is_selected,
            starters=opt.starters,
            benched=opt.benched,
            reasoning=opt.reasoning,
            points_breakdown=opt.points_breakdown
        ) for opt in squad.formation_analysis.options
    ]
    
    return BuiltSquadResponse(
        players=[squad_player_to_response(p) for p in squad.players],
        formation=squad.formation,
        total_cost=squad.total_cost,
        in_the_bank=squad.in_the_bank,
        validation=ValidationResponse(
            passed=squad.validation.passed,
            hard_constraints=[
                ConstraintResponse(
                    name=c.name,
                    passed=c.passed,
                    message=c.message,
                    severity=c.severity,
                    value=c.value
                ) for c in squad.validation.hard_constraints
            ],
            soft_constraints=[
                ConstraintResponse(
                    name=c.name,
                    passed=c.passed,
                    message=c.message,
                    severity=c.severity,
                    value=c.value
                ) for c in squad.validation.soft_constraints
            ],
            error_count=squad.validation.error_count,
            warning_count=squad.validation.warning_count
        ),
        strategy_id=squad.strategy.value,
        strategy_name=strategy_info.name,
        strategy_analysis=StrategyAnalysisResponse(
            description=squad.strategy_analysis.description,
            metrics=squad.strategy_analysis.metrics,
            strengths=squad.strategy_analysis.strengths,
            weaknesses=squad.strategy_analysis.weaknesses
        ),
        formation_analysis=FormationAnalysisResponse(
            selected_formation=squad.formation_analysis.selected_formation,
            options=formation_options,
            selection_reason=squad.formation_analysis.selection_reason,
            expected_points_formula=squad.formation_analysis.expected_points_formula
        ),
        sparql_queries=squad.sparql_queries
    )


# =========================================================================
# Endpoints
# =========================================================================

@router.get("/strategies", response_model=List[StrategyInfo])
async def get_strategies():
    """Get all available squad building strategies."""
    return list(STRATEGIES.values())


@router.get("/strategies/{strategy_id}", response_model=StrategyInfo)
async def get_strategy(strategy_id: str):
    """Get a specific strategy by ID."""
    if strategy_id not in STRATEGIES:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    return STRATEGIES[strategy_id]


@router.post("/{strategy_id}", response_model=BuiltSquadResponse)
async def build_squad(strategy_id: str):
    """Build a squad using the specified strategy."""
    if strategy_id not in STRATEGIES and strategy_id != "custom":
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
    
    try:
        strategy = Strategy(strategy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy_id}")
    
    builder = await get_squad_builder()
    
    try:
        squad = await builder.build_squad(strategy)
        return built_squad_to_response(squad)
    except Exception as e:
        logger.error(f"Error building squad: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom/build", response_model=BuiltSquadResponse)
async def build_custom_squad(request: CustomBuildRequest):
    """Build a squad using custom tag selection."""
    builder = await get_squad_builder()
    
    try:
        squad = await builder.build_squad(
            Strategy.CUSTOM,
            include_tags=request.include_tags,
            exclude_tags=request.exclude_tags
        )
        return built_squad_to_response(squad)
    except Exception as e:
        logger.error(f"Error building custom squad: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swap", response_model=List[ReplacementResponse])
async def get_swap_options(request: SwapRequest):
    """Get replacement options for a player."""
    if request.strategy_id not in STRATEGIES:
        raise HTTPException(status_code=404, detail=f"Strategy '{request.strategy_id}' not found")
    
    try:
        strategy = Strategy(request.strategy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {request.strategy_id}")
    
    builder = await get_squad_builder()
    
    # Reconstruct squad from player IDs
    from services.fpl_service import fpl_service
    
    kg = await ensure_kg_ready()
    squad_players = []
    
    for player_id in request.player_ids:
        player = fpl_service.get_player(player_id)
        if player:
            tags = kg.get_all_inferred_classes_for_player(player_id)
            squad_players.append(SquadPlayer(
                id=player.id,
                web_name=player.web_name,
                full_name=f"{player.first_name} {player.second_name}",
                position=player.position,
                team_id=player.team,
                team_short=fpl_service.get_team_short_name(player.team),
                price=player.price,
                form=player.form_float or 0,
                ownership=player.ownership or 0,
                total_points=player.total_points or 0,
                points_per_million=round((player.total_points or 0) / max(player.price, 0.1), 1),
                smart_tags=tags,
                selection_reason=""
            ))
    
    try:
        replacements = builder.get_replacements(squad_players, request.player_out_id, strategy)
        return [
            ReplacementResponse(
                player=squad_player_to_response(player),
                maintains_constraints=maintains,
                why_recommended=player.selection_reason
            )
            for player, maintains in replacements
        ]
    except Exception as e:
        logger.error(f"Error getting replacements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tags")
async def get_available_tags():
    """Get all available Smart Tags for custom strategy builder."""
    kg = await ensure_kg_ready()
    tags = kg.get_inferred_classes_with_counts()
    
    # Categorize tags
    include_tags = []
    exclude_tags = []
    
    for tag in tags:
        tag_info = {
            "name": tag["name"],
            "description": tag["description"],
            "count": tag["count"],
            "icon": tag["icon"],
            "color": tag["color_code"]
        }
        
        # Negative tags should be in exclude list
        if tag["name"] in ["InjuryConcern", "RotationRisk", "SellUrgent", "HighRecurrenceRisk"]:
            exclude_tags.append(tag_info)
        else:
            include_tags.append(tag_info)
    
    return {
        "include_options": include_tags,
        "exclude_options": exclude_tags
    }


@router.get("/preview-sparql")
async def preview_sparql(include_tags: str = "", exclude_tags: str = ""):
    """Preview the SPARQL query for custom tag selection."""
    include_list = [t.strip() for t in include_tags.split(",") if t.strip()]
    exclude_list = [t.strip() for t in exclude_tags.split(",") if t.strip()]
    
    # Build SPARQL query
    query_parts = [
        "SELECT ?player ?name ?pos ?price ?form ?ownership ?points WHERE {",
        "  ?player a fpl:Player ;",
        "          fpl:webName ?name ;",
        "          fpl:position ?pos ;",
        "          fpl:currentPrice ?price ;",
        "          fpl:form ?form ;",
        "          fpl:ownership ?ownership ;",
        "          fpl:totalPoints ?points ;",
        "          fpl:status ?status .",
        "  FILTER (?status = \"a\")"
    ]
    
    # Add include filters
    for tag in include_list:
        query_parts.append(f"  ?player a fpl:{tag} .")
    
    # Add exclude filters
    for tag in exclude_list:
        query_parts.append(f"  FILTER NOT EXISTS {{ ?player a fpl:{tag} }}")
    
    query_parts.append("}")
    query_parts.append("ORDER BY DESC(?form)")
    
    return {
        "sparql": "\n".join(query_parts),
        "include_tags": include_list,
        "exclude_tags": exclude_list
    }

