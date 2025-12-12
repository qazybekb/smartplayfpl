# backend/services/squad_builder.py
"""
SmartPlay Score-Powered Squad Builder Service

Builds FPL squads using pre-calculated ML scores from the database.
All player selection is based on SmartPlay scores (0-10 scale).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class Strategy(Enum):
    """Available squad building strategies."""
    SMARTPLAY_CHOICE = "smartplay"  # Pure AI optimization
    TEMPLATE = "template"
    PREMIUM_PUNTS = "premium"
    VALUE_HUNTERS = "value"
    FORM_RIDERS = "form"
    BALANCED = "balanced"


@dataclass
class SelectionTrace:
    """Detailed trace of why a player was selected."""
    strategy_score: float  # Final score for this strategy
    rank_in_position: int  # e.g., #2 of 47 MIDs
    total_in_position: int  # Total eligible players at position
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    tag_bonuses: Dict[str, float] = field(default_factory=dict)
    tag_penalties: Dict[str, float] = field(default_factory=dict)
    alternatives: List[Dict] = field(default_factory=list)


@dataclass
class InferenceStep:
    """A step in the OWL inference chain."""
    data_field: str
    data_value: str
    inferred_class: str
    rule: str
    contributed_to: str


@dataclass
class MLPrediction:
    """ML prediction for a player."""
    p_plays: float
    ml_score: float
    nailedness_score: float
    form_score_xg: float
    form_score_pts: float
    fixture_score: float
    is_available: bool
    availability_reason: str


@dataclass
class SquadPlayer:
    """A player in a built squad."""
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
    is_starter: bool = False
    is_captain: bool = False
    is_vice_captain: bool = False
    smart_tags: List[str] = field(default_factory=list)
    selection_reason: str = ""
    bench_order: int = 0
    selection_trace: Optional[SelectionTrace] = None
    inference_chain: List[InferenceStep] = field(default_factory=list)
    ml_prediction: Optional[MLPrediction] = None
    # SmartPlay score fields
    smartplay_score: float = 0.0
    nailedness_score: float = 0.0
    form_xg_score: float = 0.0
    form_pts_score: float = 0.0
    fixture_score: float = 0.0


@dataclass
class ConstraintResult:
    """Result of a single constraint validation."""
    name: str
    passed: bool
    message: str
    severity: str
    value: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result for a squad."""
    passed: bool
    hard_constraints: List[ConstraintResult]
    soft_constraints: List[ConstraintResult]

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.hard_constraints if not c.passed)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.soft_constraints if not c.passed and c.severity == "warning")


@dataclass
class FormationOption:
    """Analysis of a single formation option."""
    formation: str
    expected_points: float
    total_form: float
    is_selected: bool
    starters: List[str]
    benched: List[str]
    reasoning: str
    points_breakdown: Dict[str, float]


@dataclass
class FormationAnalysis:
    """Complete formation comparison analysis."""
    selected_formation: str
    options: List[FormationOption]
    selection_reason: str
    expected_points_formula: str


@dataclass
class StrategyAnalysis:
    """Strategy-specific analysis of the built squad."""
    strategy: Strategy
    metrics: Dict[str, Any]
    description: str
    strengths: List[str]
    weaknesses: List[str]


@dataclass
class BuiltSquad:
    """A complete built squad with all metadata."""
    players: List[SquadPlayer]
    formation: str
    total_cost: float
    in_the_bank: float
    validation: ValidationResult
    strategy: Strategy
    strategy_analysis: StrategyAnalysis
    formation_analysis: FormationAnalysis
    sparql_queries: List[str]

    @property
    def starters(self) -> List[SquadPlayer]:
        return [p for p in self.players if p.is_starter]

    @property
    def bench(self) -> List[SquadPlayer]:
        return sorted([p for p in self.players if not p.is_starter], key=lambda x: x.bench_order)

    @property
    def captain(self) -> Optional[SquadPlayer]:
        return next((p for p in self.players if p.is_captain), None)

    @property
    def vice_captain(self) -> Optional[SquadPlayer]:
        return next((p for p in self.players if p.is_vice_captain), None)


# Valid formations: (DEF, MID, FWD)
VALID_FORMATIONS = [
    (3, 4, 3),  # 3-4-3
    (3, 5, 2),  # 3-5-2
    (4, 3, 3),  # 4-3-3
    (4, 4, 2),  # 4-4-2
    (4, 5, 1),  # 4-5-1
    (5, 3, 2),  # 5-3-2
    (5, 4, 1),  # 5-4-1
]


# Minimum SmartPlay score thresholds by strategy
MIN_SCORE_THRESHOLDS = {
    Strategy.SMARTPLAY_CHOICE: 5.5,  # Pure optimization needs high quality
    Strategy.TEMPLATE: 5.0,       # Template picks need decent scores
    Strategy.PREMIUM_PUNTS: 5.5,  # Premiums should be quality
    Strategy.VALUE_HUNTERS: 4.5,  # Value picks can be slightly lower
    Strategy.FORM_RIDERS: 5.5,    # Form riders need high form
    Strategy.BALANCED: 5.0,       # Balanced needs good quality across the board
}

# Position value weights for SmartPlay Choice
# Attackers tend to score more FPL points, so we weight them higher
POSITION_VALUE_WEIGHTS = {
    "GKP": 0.92,  # GKs score fewer points
    "DEF": 1.00,  # Baseline
    "MID": 1.06,  # Mids score more (assists, goals)
    "FWD": 1.10,  # Forwards have highest ceiling
}

# Ownership bracket average PPG (based on historical analysis)
# Players who outperform their bracket are "hidden gems"
OWNERSHIP_BRACKET_AVG_PPG = {
    "elite": 5.37,        # >30% ownership
    "popular": 5.09,      # 10-30% ownership
    "mid": 4.29,          # 5-10% ownership
    "differential": 4.09, # 1-5% ownership
    "extreme": 3.54,      # <1% ownership
}

def get_ownership_bracket(ownership: float) -> str:
    """Get ownership bracket name for a player."""
    if ownership > 30:
        return "elite"
    elif ownership >= 10:
        return "popular"
    elif ownership >= 5:
        return "mid"
    elif ownership >= 1:
        return "differential"
    else:
        return "extreme"


class SquadBuilder:
    """
    Builds FPL squads using SmartPlay scores from the database.

    All player selection is based on pre-calculated ML scores:
    - final_score: Overall SmartPlay score (0-10)
    - nailedness_score: How nailed the player is
    - form_xg_score: Form based on xG/xA
    - form_pts_score: Form based on points
    - fixture_score: Upcoming fixture difficulty
    """

    def __init__(self, kg_service, fpl_service, ml_predictor=None):
        self._kg = kg_service
        self._fpl = fpl_service
        self._ml_predictor = ml_predictor
        self._budget = 100.0
        self._ml_scores: Dict[int, Dict] = {}  # Cache of ML scores

    def _generate_smartplay_tags(self, player, ml_data: Dict) -> List[str]:
        """
        Generate Smart Tags based on SmartPlay scores instead of KG inference.

        Tags are assigned based on ML-calculated scores:
        - CaptainCandidate: SmartPlay >= 7.5 AND nailedness >= 8.0
        - TopPlayer: SmartPlay >= 7.0
        - ValuePick: Good points/million with decent SmartPlay
        - RotationRisk: nailedness < 5.0
        - FormPlayer: High form scores
        - FixtureFriendly: Good upcoming fixtures
        - DifferentialPick: Low ownership with good score
        - Premium: High price with good score
        """
        tags = []

        smartplay = ml_data.get('final_score', 0)
        nailedness = ml_data.get('nailedness_score', 0)
        form_xg = ml_data.get('form_xg_score', 0)
        form_pts = ml_data.get('form_pts_score', 0)
        fixture = ml_data.get('fixture_score', 0)

        ownership = player.ownership or 0
        price = player.price or 0
        total_points = player.total_points or 0
        ppm = total_points / max(price, 0.1) if total_points else 0

        # CaptainCandidate: Elite players who are nailed
        if smartplay >= 7.5 and nailedness >= 8.0:
            tags.append("CaptainCandidate")

        # TopPlayer: High SmartPlay score
        if smartplay >= 7.0:
            tags.append("TopPlayer")

        # RotationRisk: Not nailed on
        if nailedness < 5.0:
            tags.append("RotationRisk")

        # FormPlayer: In hot form
        if form_pts >= 7.0 or form_xg >= 7.0:
            tags.append("FormPlayer")

        # FixtureFriendly: Good upcoming fixtures
        if fixture >= 7.0:
            tags.append("FixtureFriendly")

        # ValuePick: Good points per million with decent score
        if ppm >= 20 and smartplay >= 5.5:
            tags.append("ValuePick")

        # DifferentialPick: Low ownership but quality
        if ownership < 10 and smartplay >= 6.0:
            tags.append("DifferentialPick")

        # Premium: Expensive quality player
        if price >= 10.0 and smartplay >= 6.5:
            tags.append("Premium")

        # NailedOn: Very secure starter
        if nailedness >= 9.0:
            tags.append("NailedOn")

        # InjuryConcern: Check player status from FPL API
        if player.status not in ("a",):  # Not fully available
            tags.append("InjuryConcern")

        return tags

    def _load_ml_scores_from_db(self) -> Dict[int, Dict]:
        """Load all ML scores from database."""
        from database import SessionLocal, MLPlayerScore

        scores = {}
        db = SessionLocal()
        try:
            # Get latest gameweek scores
            latest = db.query(MLPlayerScore).order_by(
                MLPlayerScore.calculated_at.desc()
            ).first()

            if not latest:
                logger.warning("No ML scores in database - will generate fallback scores")
                return {}

            # Get all scores for latest gameweek
            all_scores = db.query(MLPlayerScore).filter(
                MLPlayerScore.gameweek == latest.gameweek
            ).all()

            for score in all_scores:
                scores[score.player_id] = {
                    'final_score': float(score.final_score),
                    'nailedness_score': float(score.nailedness_score),
                    'form_xg_score': float(score.form_xg_score),
                    'form_pts_score': float(score.form_pts_score),
                    'fixture_score': float(score.fixture_score),
                    'avg_minutes': float(score.avg_minutes),
                    'avg_points': float(score.avg_points),
                    'rank': int(score.rank),
                    'next_opponent': score.next_opponent,
                    'next_fdr': int(score.next_fdr),
                    'next_home': bool(score.next_home),
                    'status': score.status,
                }

            logger.info(f"Loaded {len(scores)} ML scores from database (GW{latest.gameweek})")
            return scores

        except Exception as e:
            logger.error(f"Failed to load ML scores from database: {e}")
            return {}
        finally:
            db.close()

    def _generate_fallback_scores(self, players) -> Dict[int, Dict]:
        """
        Generate basic scores when ML database is empty.
        Uses form, total points, and ownership as proxies.
        """
        logger.info("Generating fallback scores for squad builder")
        scores = {}

        for player in players:
            if player.status not in ("a", "d"):
                continue

            # Basic scoring based on available data
            form = player.form_float or 0
            total_points = player.total_points or 0
            minutes = player.minutes or 0
            ownership = player.ownership or 0

            # Calculate basic nailedness from minutes (0-10 scale)
            # Assuming ~16 gameweeks, 90 mins = 1440 total possible
            games_possible = 16
            nailedness = min(10.0, (minutes / (games_possible * 90)) * 10) if minutes > 0 else 5.0

            # Form score (0-10 scale) - form is typically 0-10 in FPL
            form_score = min(10.0, form)

            # Points-based score (0-10 scale) - normalize by position avg
            position_avg = {"GKP": 60, "DEF": 70, "MID": 90, "FWD": 80}.get(player.position, 75)
            pts_score = min(10.0, (total_points / position_avg) * 5) if total_points > 0 else 4.0

            # Fixture score - default to middle value without FDR data
            fixture_score = 6.0

            # Final score: weighted average
            final_score = (
                nailedness * 0.25 +
                form_score * 0.35 +
                pts_score * 0.30 +
                fixture_score * 0.10
            )

            scores[player.id] = {
                'final_score': round(final_score, 2),
                'nailedness_score': round(nailedness, 2),
                'form_xg_score': round(form_score * 0.8, 2),  # Approximate
                'form_pts_score': round(pts_score, 2),
                'fixture_score': round(fixture_score, 2),
                'avg_minutes': round(minutes / max(games_possible, 1), 1),
                'avg_points': round(total_points / max(games_possible, 1), 1),
                'rank': 0,
                'next_opponent': 'TBD',
                'next_fdr': 3,
                'next_home': True,
                'status': player.status,
            }

        logger.info(f"Generated fallback scores for {len(scores)} players")
        return scores

    # =========================================================================
    # Main Build Method
    # =========================================================================

    async def build_squad(self, strategy: Strategy,
                          include_tags: List[str] = None,
                          exclude_tags: List[str] = None,
                          use_ml_filter: bool = True) -> BuiltSquad:
        """
        Build a complete 15-player squad using SmartPlay scores.
        """
        logger.info(f"Building squad with strategy: {strategy.value}")

        # Get all players from FPL service first (needed for fallback)
        all_players = self._fpl.get_all_players()

        # Load ML scores from database
        self._ml_scores = self._load_ml_scores_from_db()

        # If no ML scores in database, generate fallback scores
        if not self._ml_scores:
            logger.warning("No ML scores in database - generating fallback scores")
            self._ml_scores = self._generate_fallback_scores(all_players)

        # Generate SmartPlay-based tags for each player
        player_tags = {}
        for player in all_players:
            ml_data = self._ml_scores.get(player.id, {})
            # Use SmartPlay-based tags instead of KG inference
            tags = self._generate_smartplay_tags(player, ml_data)
            player_tags[player.id] = tags

        # Filter and score players based on strategy + ML scores
        scored_players = self._score_players_with_ml(
            all_players, player_tags, strategy, include_tags, exclude_tags
        )

        # Build squad using greedy algorithm
        squad_players, sparql_queries = self._greedy_build(scored_players, strategy)

        # Select optimal formation with analysis
        formation, formation_analysis = await self._select_formation(squad_players)

        # Assign starters based on formation
        squad_players = self._assign_starters(squad_players, formation)

        # Select captain and vice-captain
        squad_players = self._select_captains(squad_players, strategy)

        # Calculate costs
        total_cost = sum(p.price for p in squad_players)
        in_the_bank = self._budget - total_cost

        # Validate squad
        validation = self._validate_squad(squad_players, strategy)

        # Generate strategy analysis
        analysis = self._analyze_strategy(squad_players, strategy)

        return BuiltSquad(
            players=squad_players,
            formation=formation,
            total_cost=round(total_cost, 1),
            in_the_bank=round(in_the_bank, 1),
            validation=validation,
            strategy=strategy,
            strategy_analysis=analysis,
            formation_analysis=formation_analysis,
            sparql_queries=sparql_queries
        )

    # =========================================================================
    # Player Scoring with ML Scores
    # =========================================================================

    def _score_players_with_ml(self, players, player_tags: Dict, strategy: Strategy,
                                include_tags: List[str] = None,
                                exclude_tags: List[str] = None) -> List[Tuple]:
        """
        Score all players based on SmartPlay ML scores + strategy modifiers.

        Returns list of (player, score, reason, tags, breakdown, tag_bonuses, tag_penalties, rank, total)
        """
        min_score = MIN_SCORE_THRESHOLDS.get(strategy, 4.0)
        scored = []

        for player in players:
            # Skip unavailable players
            if player.status not in ("a", "d"):
                continue

            # Get ML scores for this player
            ml_data = self._ml_scores.get(player.id, {})
            smartplay_score = ml_data.get('final_score', 0.0)
            nailedness = ml_data.get('nailedness_score', 0.0)
            form_xg = ml_data.get('form_xg_score', 0.0)
            form_pts = ml_data.get('form_pts_score', 0.0)
            fixture = ml_data.get('fixture_score', 0.0)

            # CRITICAL: Skip players with low SmartPlay scores
            if smartplay_score < min_score:
                continue

            # Skip players with very low nailedness (rotation risks)
            if nailedness < 4.0:
                continue

            tags = player_tags.get(player.id, [])

            # Apply tag filters for custom strategy
            if include_tags:
                if not any(tag in tags for tag in include_tags):
                    continue

            if exclude_tags:
                if any(tag in tags for tag in exclude_tags):
                    continue

            # Skip injury concerns for pre-built strategies
            if not include_tags and "InjuryConcern" in tags:
                continue

            # Calculate strategy-specific score using ML data
            score, reason, breakdown, tag_bonuses, tag_penalties = self._calculate_ml_score(
                player, ml_data, tags, strategy
            )

            if score > 0:
                scored.append((
                    player, score, reason, tags, breakdown,
                    tag_bonuses, tag_penalties, ml_data
                ))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Add rank information for each position
        position_totals = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        position_current_rank = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}

        # Count totals per position
        for item in scored:
            position_totals[item[0].position] += 1

        # Assign ranks within position
        result = []
        for player, score, reason, tags, breakdown, tag_bonuses, tag_penalties, ml_data in scored:
            pos = player.position
            position_current_rank[pos] += 1
            result.append((
                player, score, reason, tags, breakdown, tag_bonuses, tag_penalties,
                position_current_rank[pos], position_totals[pos], ml_data
            ))

        return result

    def _calculate_ml_score(self, player, ml_data: Dict, tags: List[str],
                            strategy: Strategy) -> Tuple[float, str, Dict, Dict, Dict]:
        """
        Calculate player score using ML data + strategy modifiers.

        The base score is the SmartPlay score, with strategy-specific adjustments.
        """
        smartplay_score = ml_data.get('final_score', 0.0)
        nailedness = ml_data.get('nailedness_score', 0.0)
        form_xg = ml_data.get('form_xg_score', 0.0)
        form_pts = ml_data.get('form_pts_score', 0.0)
        fixture = ml_data.get('fixture_score', 0.0)

        ownership = player.ownership or 0
        ppm = player.total_points / max(player.price, 0.1) if player.total_points else 0

        breakdown = {
            "smartplay_score": round(smartplay_score, 2),
            "nailedness": round(nailedness, 2),
            "form_xg": round(form_xg, 2),
            "form_pts": round(form_pts, 2),
            "fixture": round(fixture, 2),
        }
        tag_bonuses = {}
        tag_penalties = {}

        # Base score is the SmartPlay score (0-10 scale, multiply for differentiation)
        base_score = smartplay_score * 10

        if strategy == Strategy.SMARTPLAY_CHOICE:
            # SmartPlay + position weight (attackers score more FPL points)
            pos_weight = POSITION_VALUE_WEIGHTS.get(player.position, 1.0)
            score = base_score * pos_weight
            breakdown["position_weight"] = round(pos_weight, 2)

            # OUTPERFORMER DETECTION: Boost players who outperform their ownership bracket
            # This finds "hidden gems" - low ownership players who are actually performing well
            minutes = player.minutes or 0
            form = player.form_float or 0

            outperformer_bonus = 0.0
            stability_bonus = 0.0

            if minutes >= 450:  # At least 5 full games played
                # Calculate points per game
                games_played = minutes / 90
                ppg = player.total_points / games_played if games_played > 0 else 0

                # Get expected PPG for this ownership bracket
                bracket = get_ownership_bracket(ownership)
                bracket_avg_ppg = OWNERSHIP_BRACKET_AVG_PPG.get(bracket, 4.0)

                # Only boost if: (1) outperforming bracket by 20%+, (2) in good form
                if ppg > bracket_avg_ppg * 1.2 and form >= 5.0:
                    # Bonus scales with how much they outperform
                    outperformance_ratio = (ppg - bracket_avg_ppg) / bracket_avg_ppg
                    raw_bonus = min(outperformance_ratio * 10, 8)  # Cap at 8 points

                    # SAMPLE SIZE CONFIDENCE: Scale bonus by games played
                    # Full confidence at 10+ games, reduced for fewer games
                    sample_confidence = min(games_played / 10, 1.0)
                    outperformer_bonus = raw_bonus * sample_confidence

                    breakdown["ppg"] = round(ppg, 2)
                    breakdown["bracket_avg_ppg"] = round(bracket_avg_ppg, 2)
                    breakdown["games_played"] = round(games_played, 1)
                    breakdown["sample_confidence"] = round(sample_confidence, 2)
                    breakdown["outperformer_bonus"] = round(outperformer_bonus, 1)
                    tag_bonuses["Outperformer"] = round(outperformer_bonus, 1)

                # STABILITY BONUS: Reward proven production (total points)
                # Players with more total points have demonstrated consistency
                # Max +1.0 bonus for 100+ points
                stability_bonus = min(player.total_points / 100, 1.0)
                breakdown["stability_bonus"] = round(stability_bonus, 2)
                tag_bonuses["Stable"] = round(stability_bonus, 2)

            score += outperformer_bonus + stability_bonus

            reason = f"SmartPlay {smartplay_score:.1f}"
            if pos_weight != 1.0:
                reason += f", {player.position} ×{pos_weight:.2f}"
            if outperformer_bonus > 0:
                reason += f", +{outperformer_bonus:.1f} outperformer"
            if stability_bonus > 0.5:
                reason += f", +{stability_bonus:.1f} stable"

        elif strategy == Strategy.TEMPLATE:
            # Template: Prefer high ownership + high SmartPlay score
            ownership_bonus = min(ownership * 0.5, 20)  # Cap at 20
            score = base_score + ownership_bonus
            breakdown["ownership_bonus"] = round(ownership_bonus, 1)
            reason = f"SmartPlay {smartplay_score:.1f}, {ownership:.0f}% owned"

        elif strategy == Strategy.PREMIUM_PUNTS:
            # Premium: Boost premiums with good scores
            if player.price >= 10.0:
                premium_bonus = 15
                score = base_score + premium_bonus
                breakdown["premium_bonus"] = premium_bonus
                reason = f"Premium £{player.price}m, SmartPlay {smartplay_score:.1f}"
            else:
                # Value enablers: need good value AND decent score
                value_bonus = min(ppm * 2, 10)
                score = base_score + value_bonus
                breakdown["value_bonus"] = round(value_bonus, 1)
                reason = f"Enabler {ppm:.1f} pts/£m, SmartPlay {smartplay_score:.1f}"

        elif strategy == Strategy.VALUE_HUNTERS:
            # Value: Prioritize points per million + SmartPlay
            value_bonus = min(ppm * 3, 15)
            score = base_score + value_bonus
            breakdown["value_bonus"] = round(value_bonus, 1)
            reason = f"{ppm:.1f} pts/£m, SmartPlay {smartplay_score:.1f}"

        elif strategy == Strategy.FORM_RIDERS:
            # Form: Heavily weight form scores
            form_boost = (form_xg + form_pts) * 2
            score = base_score + form_boost
            breakdown["form_boost"] = round(form_boost, 1)
            reason = f"Form {form_pts:.1f}, SmartPlay {smartplay_score:.1f}"

        elif strategy == Strategy.BALANCED:
            # Balanced: Weight all factors equally
            # Mix of ownership (moderate), value, and form
            ownership_factor = min(ownership * 0.2, 8)  # Moderate ownership bonus
            value_factor = min(ppm * 1.5, 8)  # Value bonus
            form_factor = (form_xg + form_pts) * 0.5  # Form bonus

            score = base_score + ownership_factor + value_factor + form_factor
            breakdown["ownership_factor"] = round(ownership_factor, 1)
            breakdown["value_factor"] = round(value_factor, 1)
            breakdown["form_factor"] = round(form_factor, 1)
            reason = f"SmartPlay {smartplay_score:.1f}, balanced mix"

        # Bonus for very nailed players
        if nailedness >= 9.0:
            score += 5
            tag_bonuses["HighlyNailed"] = 5

        # Bonus for great fixtures
        if fixture >= 8.0:
            score += 5
            tag_bonuses["GreatFixtures"] = 5

        # Penalty for rotation risks (shouldn't happen due to filter, but safety)
        if nailedness < 5.0:
            score -= 10
            tag_penalties["RotationRisk"] = -10

        return score, reason, breakdown, tag_bonuses, tag_penalties

    # =========================================================================
    # Greedy Squad Building
    # =========================================================================

    def _greedy_build(self, scored_players, strategy: Strategy) -> Tuple[List[SquadPlayer], List[str]]:
        """Build squad using greedy selection with constraints."""

        squad = []
        team_counts = {}
        position_counts = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        position_targets = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
        remaining_budget = self._budget

        # Reserve minimum budget for each position
        min_prices = {"GKP": 4.0, "DEF": 4.0, "MID": 4.5, "FWD": 4.5}

        # Get threshold for this strategy
        min_score = MIN_SCORE_THRESHOLDS.get(strategy, 4.0)

        # Generate selection criteria description
        selection_criteria = f"""SMARTPLAY SELECTION CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strategy: {strategy.value.upper()}
Minimum SmartPlay Score: {min_score}
Minimum Nailedness: 4.0
Budget: £{self._budget}m

POSITION REQUIREMENTS:
  GKP: 2 players (min £4.0m each)
  DEF: 5 players (min £4.0m each)
  MID: 5 players (min £4.5m each)
  FWD: 3 players (min £4.5m each)

CONSTRAINTS:
  • Max 3 players per team
  • Players must be available (status 'a' or 'd')
  • No injured players selected
  • Budget must not exceed £100m

SCORING FORMULA ({strategy.value}):
  Base Score = SmartPlay Score × 10"""

        if strategy == Strategy.SMARTPLAY_CHOICE:
            selection_criteria += """

  Pure AI optimization - no strategy bonuses.
  Simply picks the highest SmartPlay scores."""
        elif strategy == Strategy.TEMPLATE:
            selection_criteria += """
  + Ownership Bonus (max 20)

  Prioritizes proven, highly-owned players."""
        elif strategy == Strategy.PREMIUM_PUNTS:
            selection_criteria += """
  + Premium Bonus (15 for £10m+ players)
  + Value Bonus for budget enablers

  Prioritizes premium stars with budget enablers."""
        elif strategy == Strategy.VALUE_HUNTERS:
            selection_criteria += """
  + Value Bonus = Points/Million × 3 (max 15)

  Prioritizes best value for money."""
        elif strategy == Strategy.FORM_RIDERS:
            selection_criteria += """
  + Form Boost = (Form_xG + Form_Pts) × 2

  Prioritizes players in hot form."""
        elif strategy == Strategy.BALANCED:
            selection_criteria += """
  + Ownership Factor (max 8)
  + Value Factor = Pts/£m × 1.5 (max 8)
  + Form Factor = (Form_xG + Form_Pts) × 0.5

  Balanced mix of ownership, value, and form."""

        sparql_queries = [selection_criteria]

        # Sort scored players by position
        by_position = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
        for item in scored_players:
            player = item[0]
            by_position[player.position].append(item)

        # For Premium & Punts, pick premiums first
        if strategy == Strategy.PREMIUM_PUNTS:
            premium_count = 0
            for pos in ["MID", "FWD"]:
                for item in by_position[pos]:
                    player = item[0]
                    score = item[1]
                    reason = item[2]
                    tags = item[3]
                    breakdown = item[4]
                    tag_bonuses = item[5]
                    tag_penalties = item[6]
                    rank = item[7]
                    total = item[8]
                    ml_data = item[9]

                    if premium_count >= 3:
                        break
                    if player.price >= 10.0 and remaining_budget >= player.price:
                        if team_counts.get(player.team, 0) < 3:
                            squad_player = self._create_squad_player_with_trace(
                                player, tags, reason, score, breakdown,
                                tag_bonuses, tag_penalties, rank, total, [], ml_data
                            )
                            squad.append(squad_player)
                            team_counts[player.team] = team_counts.get(player.team, 0) + 1
                            position_counts[pos] += 1
                            remaining_budget -= player.price
                            premium_count += 1

        # Fill each position
        for position in ["GKP", "DEF", "MID", "FWD"]:
            target = position_targets[position]
            skipped_players = []

            for item in by_position[position]:
                player = item[0]
                score = item[1]
                reason = item[2]
                tags = item[3]
                breakdown = item[4]
                tag_bonuses = item[5]
                tag_penalties = item[6]
                rank = item[7]
                total = item[8]
                ml_data = item[9]

                if position_counts[position] >= target:
                    break

                # Check constraints
                if player.id in [p.id for p in squad]:
                    continue
                if team_counts.get(player.team, 0) >= 3:
                    skipped_players.append({
                        "name": player.web_name,
                        "score": round(score, 1),
                        "reason": "Team limit (3 max)",
                        "price": player.price
                    })
                    continue

                # Calculate reserved budget for remaining positions
                reserved_budget = 0
                for pos in ["GKP", "DEF", "MID", "FWD"]:
                    remaining_needed = position_targets[pos] - position_counts[pos]
                    if pos == position:
                        remaining_needed -= 1
                    reserved_budget += remaining_needed * min_prices[pos]

                # Check if we can afford this player
                if remaining_budget - player.price < reserved_budget:
                    skipped_players.append({
                        "name": player.web_name,
                        "score": round(score, 1),
                        "reason": f"Budget (need £{reserved_budget:.1f}m)",
                        "price": player.price
                    })
                    continue

                # Add player with trace
                alternatives = skipped_players[:3] if skipped_players else []
                squad_player = self._create_squad_player_with_trace(
                    player, tags, reason, score, breakdown,
                    tag_bonuses, tag_penalties, rank, total, alternatives, ml_data
                )
                squad.append(squad_player)
                team_counts[player.team] = team_counts.get(player.team, 0) + 1
                position_counts[position] += 1
                remaining_budget -= player.price

        # Fallback: if any position not filled, use lower threshold
        for position in ["GKP", "DEF", "MID", "FWD"]:
            target = position_targets[position]
            if position_counts[position] < target:
                logger.warning(f"Fallback needed for {position}: {position_counts[position]}/{target}")

                # Get all available players at position with any positive ML score
                fallback_players = [
                    (p, self._ml_scores.get(p.id, {}).get('final_score', 0))
                    for p in self._fpl.get_all_players()
                    if p.position == position and p.status in ("a", "d")
                    and p.id not in [sp.id for sp in squad]
                    and team_counts.get(p.team, 0) < 3
                    and p.price <= remaining_budget
                    and self._ml_scores.get(p.id, {}).get('final_score', 0) > 0
                ]
                fallback_players.sort(key=lambda x: x[1], reverse=True)

                for player, ml_score in fallback_players:
                    if position_counts[position] >= target:
                        break

                    ml_data = self._ml_scores.get(player.id, {})
                    # Use SmartPlay-based tags instead of KG
                    tags = self._generate_smartplay_tags(player, ml_data)

                    squad_player = self._create_squad_player_with_trace(
                        player, tags, f"Fallback (SmartPlay {ml_score:.1f})",
                        ml_score * 10, {}, {}, {}, 0, 0, [], ml_data
                    )
                    squad.append(squad_player)
                    team_counts[player.team] = team_counts.get(player.team, 0) + 1
                    position_counts[position] += 1
                    remaining_budget -= player.price

        return squad, sparql_queries

    def _create_squad_player_with_trace(self, player, tags: List[str], reason: str,
                                        score: float, breakdown: Dict, tag_bonuses: Dict,
                                        tag_penalties: Dict, rank: int, total: int,
                                        alternatives: List[Dict], ml_data: Dict = None) -> SquadPlayer:
        """Create a SquadPlayer with full selection trace and ML data."""

        ml_data = ml_data or {}

        # Build inference chain from tags
        inference_chain = self._build_inference_chain(player, tags)

        # Create selection trace
        selection_trace = SelectionTrace(
            strategy_score=round(score, 1),
            rank_in_position=rank,
            total_in_position=total,
            score_breakdown=breakdown,
            tag_bonuses=tag_bonuses,
            tag_penalties=tag_penalties,
            alternatives=alternatives
        )

        # Create ML prediction from database scores
        ml_prediction = None
        if ml_data:
            nailedness = ml_data.get('nailedness_score', 0)
            # Estimate p_plays from nailedness (0-10 scale -> 0-1)
            p_plays = min(1.0, nailedness / 10.0)

            ml_prediction = MLPrediction(
                p_plays=round(p_plays, 3),
                ml_score=round(ml_data.get('final_score', 0) * 10, 1),
                nailedness_score=round(nailedness * 10, 1),  # Scale to 0-100
                form_score_xg=round(ml_data.get('form_xg_score', 0) * 10, 1),
                form_score_pts=round(ml_data.get('form_pts_score', 0) * 10, 1),
                fixture_score=round(ml_data.get('fixture_score', 0) * 10, 1),
                is_available=player.status == 'a',
                availability_reason="Available" if player.status == 'a' else "Doubtful"
            )

        return SquadPlayer(
            id=player.id,
            web_name=player.web_name,
            full_name=f"{player.first_name} {player.second_name}",
            position=player.position,
            team_id=player.team,
            team_short=self._fpl.get_team_short_name(player.team),
            price=player.price,
            form=player.form_float or 0,
            ownership=player.ownership or 0,
            total_points=player.total_points or 0,
            points_per_million=round((player.total_points or 0) / max(player.price, 0.1), 1),
            smart_tags=tags,
            selection_reason=reason,
            selection_trace=selection_trace,
            inference_chain=inference_chain,
            ml_prediction=ml_prediction,
            smartplay_score=ml_data.get('final_score', 0),
            nailedness_score=ml_data.get('nailedness_score', 0),
            form_xg_score=ml_data.get('form_xg_score', 0),
            form_pts_score=ml_data.get('form_pts_score', 0),
            fixture_score=ml_data.get('fixture_score', 0),
        )

    def _build_inference_chain(self, player, tags: List[str]) -> List[InferenceStep]:
        """Build inference chain showing how data led to Smart Tags."""
        chain = []

        ml_data = self._ml_scores.get(player.id, {})
        smartplay = ml_data.get('final_score', 0)
        nailedness = ml_data.get('nailedness_score', 0)

        # Add SmartPlay-based inferences
        if smartplay >= 7.0:
            chain.append(InferenceStep(
                data_field="smartplay_score",
                data_value=f"{smartplay:.1f}",
                inferred_class="TopPlayer",
                rule="smartplay_score >= 7.0",
                contributed_to="Selection"
            ))

        if nailedness >= 9.0:
            chain.append(InferenceStep(
                data_field="nailedness",
                data_value=f"{nailedness:.1f}",
                inferred_class="HighlyNailed",
                rule="nailedness >= 9.0",
                contributed_to="Selection"
            ))

        # Add tag-based inferences
        for tag in tags:
            if tag == "CaptainCandidate":
                chain.append(InferenceStep(
                    data_field="smartplay_score",
                    data_value=f"{smartplay:.1f}",
                    inferred_class="CaptainCandidate",
                    rule="High SmartPlay + nailed",
                    contributed_to="CaptainCandidate"
                ))

        return chain

    # =========================================================================
    # Formation Selection
    # =========================================================================

    async def _get_team_fdr_map(self) -> Dict[int, float]:
        """Get average FDR (next 3 GWs) for each team."""
        try:
            fixtures = await self._fpl.get_fixtures()
            current_gw_obj = self._fpl.get_current_gameweek()
            current_gw = current_gw_obj.id if hasattr(current_gw_obj, 'id') else current_gw_obj

            team_fdrs: Dict[int, List[int]] = {}

            for fixture in fixtures:
                gw = getattr(fixture, 'event', None)
                if gw is None or gw < current_gw or gw > current_gw + 3:
                    continue

                home_team = getattr(fixture, 'team_h', None)
                away_team = getattr(fixture, 'team_a', None)
                home_fdr = getattr(fixture, 'team_h_difficulty', 3)
                away_fdr = getattr(fixture, 'team_a_difficulty', 3)

                if home_team:
                    if home_team not in team_fdrs:
                        team_fdrs[home_team] = []
                    team_fdrs[home_team].append(home_fdr)

                if away_team:
                    if away_team not in team_fdrs:
                        team_fdrs[away_team] = []
                    team_fdrs[away_team].append(away_fdr)

            return {
                team_id: sum(fdrs) / len(fdrs) if fdrs else 3.0
                for team_id, fdrs in team_fdrs.items()
            }
        except Exception as e:
            logger.warning(f"Could not get FDR data: {e}")
            return {}

    async def _select_formation(self, squad: List[SquadPlayer]) -> Tuple[str, FormationAnalysis]:
        """Select the best formation based on SmartPlay scores."""

        by_position = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
        for p in squad:
            by_position[p.position].append(p)

        # Sort by SmartPlay score (primary) then form (secondary)
        for pos in by_position:
            by_position[pos].sort(
                key=lambda x: (x.smartplay_score * 10 + x.form),
                reverse=True
            )

        team_fdr = await self._get_team_fdr_map()

        formation_options = []

        POSITION_FACTOR = {"GKP": 0.95, "DEF": 1.00, "MID": 1.05, "FWD": 1.08}

        for def_count, mid_count, fwd_count in VALID_FORMATIONS:
            if len(by_position["DEF"]) < def_count:
                continue
            if len(by_position["MID"]) < mid_count:
                continue
            if len(by_position["FWD"]) < fwd_count:
                continue

            formation_str = f"{def_count}-{mid_count}-{fwd_count}"

            gkp_starters = by_position["GKP"][:1]
            def_starters = by_position["DEF"][:def_count]
            mid_starters = by_position["MID"][:mid_count]
            fwd_starters = by_position["FWD"][:fwd_count]

            all_starters = gkp_starters + def_starters + mid_starters + fwd_starters
            benched = [p for p in squad if p not in all_starters]

            # Use SmartPlay scores for expected points
            total_smartplay = sum(p.smartplay_score for p in all_starters)

            def calc_expected(player, position):
                fdr = team_fdr.get(player.team_id, 3.0)
                fixture_factor = 1 + (3 - fdr) * 0.1
                position_factor = POSITION_FACTOR.get(position, 1.0)
                # Use SmartPlay score as base (it already incorporates form)
                return player.smartplay_score * fixture_factor * position_factor

            gkp_pts = sum(calc_expected(p, "GKP") for p in gkp_starters)
            def_pts = sum(calc_expected(p, "DEF") for p in def_starters)
            mid_pts = sum(calc_expected(p, "MID") for p in mid_starters)
            fwd_pts = sum(calc_expected(p, "FWD") for p in fwd_starters)
            base_points = gkp_pts + def_pts + mid_pts + fwd_pts

            # Captain bonus
            non_gkp = def_starters + mid_starters + fwd_starters
            player_expected = [(p, calc_expected(p, p.position)) for p in non_gkp]
            best_captain = max(player_expected, key=lambda x: x[1], default=(None, 0))
            captain_bonus = best_captain[1]

            expected_points = base_points + captain_bonus
            captain_name = best_captain[0].web_name if best_captain[0] else "N/A"

            avg_fdr = sum(team_fdr.get(p.team_id, 3.0) for p in all_starters) / len(all_starters) if all_starters else 3.0
            fixture_quality = "easy" if avg_fdr < 2.5 else "tough" if avg_fdr > 3.5 else "mixed"

            if fwd_count == 3:
                reasoning = f"Aggressive - 3 FWDs"
            elif fwd_count == 1:
                reasoning = f"Defensive - 1 FWD"
            elif mid_count == 5:
                reasoning = f"Midfield-heavy - 5 MIDs"
            elif def_count == 5:
                reasoning = f"5 DEFs"
            else:
                reasoning = f"Balanced"

            reasoning += f" | Fixtures: {fixture_quality} | 👑 {captain_name}"

            formation_options.append(FormationOption(
                formation=formation_str,
                expected_points=round(expected_points, 1),
                total_form=round(total_smartplay, 1),
                is_selected=False,
                starters=[p.web_name for p in all_starters],
                benched=[p.web_name for p in benched],
                reasoning=reasoning,
                points_breakdown={
                    "GKP": round(gkp_pts, 1),
                    "DEF": round(def_pts, 1),
                    "MID": round(mid_pts, 1),
                    "FWD": round(fwd_pts, 1),
                    "👑": round(captain_bonus, 1),
                }
            ))

        # Sort by expected points (highest first)
        formation_options.sort(key=lambda x: x.expected_points, reverse=True)

        # The best formation is the first one after sorting by expected_points
        if formation_options:
            best_formation = formation_options[0].formation
            formation_options[0].is_selected = True
            selection_reason = f"{best_formation} selected: {formation_options[0].expected_points:.1f} expected pts"
        else:
            best_formation = "3-4-3"
            selection_reason = "Default formation selected"

        formula = """SMARTPLAY FORMATION SCORE MODEL

Formula: score = smartplay_score × fixture_factor × position_factor

Fixture Factor (FDR 1-5):
  FDR 1: ×1.20 | FDR 2: ×1.10 | FDR 3: ×1.00 | FDR 4: ×0.90 | FDR 5: ×0.80

Position Factor:
  GKP: ×0.95 | DEF: ×1.00 | MID: ×1.05 | FWD: ×1.08

Captain Bonus: Best player's score added again (2× captain)

Note: This is a relative score for comparing formations, not actual FPL points."""

        return best_formation or "3-4-3", FormationAnalysis(
            selected_formation=best_formation or "3-4-3",
            options=formation_options,
            selection_reason=selection_reason,
            expected_points_formula=formula
        )

    def _assign_starters(self, squad: List[SquadPlayer], formation: str) -> List[SquadPlayer]:
        """Assign starter status based on formation."""
        parts = formation.split("-")
        targets = {
            "GKP": 1,
            "DEF": int(parts[0]),
            "MID": int(parts[1]),
            "FWD": int(parts[2])
        }

        by_position = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
        for p in squad:
            by_position[p.position].append(p)

        # Sort by SmartPlay score
        for pos in by_position:
            by_position[pos].sort(key=lambda x: x.smartplay_score, reverse=True)

        for pos in by_position:
            for i, player in enumerate(by_position[pos]):
                if i < targets[pos]:
                    player.is_starter = True
                    player.bench_order = 0
                else:
                    player.is_starter = False
                    if pos == "GKP":
                        player.bench_order = 1
                    else:
                        player.bench_order = 2 + i - targets[pos]

        return squad

    # =========================================================================
    # Captain Selection
    # =========================================================================

    def _select_captains(self, squad: List[SquadPlayer], strategy: Strategy) -> List[SquadPlayer]:
        """
        Select captain and vice-captain.

        Simple approach: SmartPlay score × position weight, with nailedness check.
        """
        starters = [p for p in squad if p.is_starter and p.position != "GKP"]

        def captain_score(p: SquadPlayer) -> float:
            # Attackers have higher ceiling for captain points
            pos_weight = {"FWD": 1.1, "MID": 1.05, "DEF": 0.9}
            score = p.smartplay_score * pos_weight.get(p.position, 1.0)

            # Captain must actually play - penalize rotation risks
            if p.nailedness_score < 7.0:
                score *= 0.8

            return score

        starters.sort(key=captain_score, reverse=True)

        if len(starters) >= 2:
            starters[0].is_captain = True
            starters[1].is_vice_captain = True
        elif len(starters) == 1:
            starters[0].is_captain = True
            starters[0].is_vice_captain = True

        return squad

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_squad(self, squad: List[SquadPlayer], strategy: Strategy) -> ValidationResult:
        """Validate squad against constraints."""
        hard_constraints = []
        soft_constraints = []

        total_cost = sum(p.price for p in squad)
        team_counts = {}
        for p in squad:
            team_counts[p.team_id] = team_counts.get(p.team_id, 0) + 1
        max_team_count = max(team_counts.values()) if team_counts else 0

        position_counts = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        starter_position_counts = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        for p in squad:
            position_counts[p.position] += 1
            if p.is_starter:
                starter_position_counts[p.position] += 1

        starters = [p for p in squad if p.is_starter]
        captain = next((p for p in squad if p.is_captain), None)
        vice_captain = next((p for p in squad if p.is_vice_captain), None)

        # Hard constraints
        hard_constraints.append(ConstraintResult(
            name="Budget",
            passed=total_cost <= 100.0,
            message=f"£{total_cost:.1f}m / £100.0m",
            severity="error",
            value=f"£{total_cost:.1f}m"
        ))

        hard_constraints.append(ConstraintResult(
            name="Squad Size",
            passed=len(squad) == 15,
            message=f"{len(squad)} / 15 players",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Goalkeepers",
            passed=position_counts["GKP"] == 2,
            message=f"{position_counts['GKP']} / 2 GKPs",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Defenders",
            passed=position_counts["DEF"] == 5,
            message=f"{position_counts['DEF']} / 5 DEFs",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Midfielders",
            passed=position_counts["MID"] == 5,
            message=f"{position_counts['MID']} / 5 MIDs",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Forwards",
            passed=position_counts["FWD"] == 3,
            message=f"{position_counts['FWD']} / 3 FWDs",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Team Limit",
            passed=max_team_count <= 3,
            message=f"Max {max_team_count} from one team",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Starting XI",
            passed=len(starters) == 11,
            message=f"{len(starters)} / 11 starters",
            severity="error"
        ))

        formation_valid = (
            3 <= starter_position_counts["DEF"] <= 5 and
            2 <= starter_position_counts["MID"] <= 5 and
            1 <= starter_position_counts["FWD"] <= 3
        )
        hard_constraints.append(ConstraintResult(
            name="Valid Formation",
            passed=formation_valid,
            message=f"{starter_position_counts['DEF']}-{starter_position_counts['MID']}-{starter_position_counts['FWD']}",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Captain",
            passed=captain is not None and captain.is_starter,
            message="Captain assigned" if captain else "No captain",
            severity="error"
        ))

        hard_constraints.append(ConstraintResult(
            name="Vice-Captain",
            passed=vice_captain is not None and vice_captain.is_starter,
            message="Vice-captain assigned" if vice_captain else "No vice-captain",
            severity="error"
        ))

        # Soft constraints - SmartPlay based
        avg_smartplay = sum(p.smartplay_score for p in starters) / len(starters) if starters else 0
        soft_constraints.append(ConstraintResult(
            name="Squad Quality",
            passed=avg_smartplay >= 6.0,
            message=f"Avg SmartPlay: {avg_smartplay:.1f}",
            severity="warning" if avg_smartplay < 6.0 else "info"
        ))

        low_nailed = [p for p in starters if p.nailedness_score < 6.0]
        soft_constraints.append(ConstraintResult(
            name="Nailed Starters",
            passed=len(low_nailed) == 0,
            message=f"{len(low_nailed)} rotation risks" if low_nailed else "All starters nailed",
            severity="warning"
        ))

        captain_score = captain.smartplay_score if captain else 0
        soft_constraints.append(ConstraintResult(
            name="Captain Quality",
            passed=captain_score >= 7.0,
            message=f"Captain SmartPlay: {captain_score:.1f}",
            severity="info"
        ))

        all_hard_passed = all(c.passed for c in hard_constraints)

        return ValidationResult(
            passed=all_hard_passed,
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints
        )

    # =========================================================================
    # Strategy Analysis
    # =========================================================================

    def _analyze_strategy(self, squad: List[SquadPlayer], strategy: Strategy) -> StrategyAnalysis:
        """Generate strategy-specific analysis."""
        starters = [p for p in squad if p.is_starter]

        avg_ownership = sum(p.ownership for p in squad) / len(squad) if squad else 0
        avg_smartplay = sum(p.smartplay_score for p in starters) / len(starters) if starters else 0
        avg_ppm = sum(p.points_per_million for p in squad) / len(squad) if squad else 0
        total_points = sum(p.total_points for p in squad)

        high_ownership = [p for p in squad if p.ownership > 15]
        differentials = [p for p in squad if p.ownership < 10]
        premiums = [p for p in squad if p.price >= 10]
        budget_players = [p for p in squad if p.price < 6]
        top_players = [p for p in squad if p.smartplay_score >= 7.0]

        # Calculate average form for starters
        avg_form = sum(p.form for p in starters) / len(starters) if starters else 0

        # Calculate total squad value
        total_value = sum(p.price for p in squad)
        remaining_budget = 100 - total_value

        metrics = {
            "avg_ownership": round(avg_ownership, 1),
            "avg_smartplay_score": round(avg_smartplay, 2),
            "avg_points_per_million": round(avg_ppm, 1),
            "avg_form": round(avg_form, 1),
            "squad_value": round(total_value, 1),
            "remaining_budget": round(remaining_budget, 1),
            "high_ownership_count": len(high_ownership),
            "differential_count": len(differentials),
            "premium_count": len(premiums),
            "budget_count": len(budget_players),
            "top_players_count": len(top_players),
        }

        if strategy == Strategy.SMARTPLAY_CHOICE:
            description = "AI-optimized squad with highest SmartPlay scores"
            top_names = [p.web_name for p in sorted(starters, key=lambda x: x.smartplay_score, reverse=True)[:3]]
            strengths = [
                f"Avg SmartPlay: {avg_smartplay:.1f} (maximized)",
                f"{len(top_players)} top-tier players (7.0+)",
                f"Top picks: {', '.join(top_names)}"
            ]
            weaknesses = [
                f"May not align with popular picks",
            ]

        elif strategy == Strategy.TEMPLATE:
            description = "Template squad with proven, highly-owned picks"
            strengths = [
                f"{len(high_ownership)} template players (>15% owned)",
                f"Avg SmartPlay: {avg_smartplay:.1f}",
                f"{len(top_players)} top-tier players"
            ]
            weaknesses = [
                f"Limited differential upside",
                f"Hard to climb ranks quickly"
            ]

        elif strategy == Strategy.PREMIUM_PUNTS:
            description = "Premium stars with budget enablers"
            premium_names = [p.web_name for p in premiums[:3]]
            strengths = [
                f"{len(premiums)} premiums: {', '.join(premium_names)}",
                f"Avg SmartPlay: {avg_smartplay:.1f}",
                f"{len(budget_players)} budget enablers"
            ]
            weaknesses = [
                f"Weak bench for auto-subs",
                f"Dependent on premiums"
            ]

        elif strategy == Strategy.VALUE_HUNTERS:
            description = "Maximum points per pound"
            strengths = [
                f"Average {avg_ppm:.1f} pts/£m",
                f"Avg SmartPlay: {avg_smartplay:.1f}",
                f"Room for upgrades"
            ]
            weaknesses = [
                f"May miss premium must-haves",
            ]

        elif strategy == Strategy.FORM_RIDERS:
            description = "Chasing hot streaks"
            hot_players = [p for p in starters if p.form_pts_score >= 7.0]
            strengths = [
                f"{len(hot_players)} players in hot form",
                f"Avg SmartPlay: {avg_smartplay:.1f}",
                f"Riding momentum"
            ]
            weaknesses = [
                f"Form can be temporary",
            ]

        elif strategy == Strategy.BALANCED:
            description = "Well-rounded squad with balanced risk"
            mid_ownership = [p for p in starters if 8 <= p.ownership <= 25]
            strengths = [
                f"Avg SmartPlay: {avg_smartplay:.1f}",
                f"{len(mid_ownership)} balanced picks (8-25% owned)",
                f"Mix of reliability and upside"
            ]
            weaknesses = [
                f"May not maximize any single factor",
            ]

        return StrategyAnalysis(
            strategy=strategy,
            metrics=metrics,
            description=description,
            strengths=strengths,
            weaknesses=weaknesses
        )

    # =========================================================================
    # Replacement Suggestions
    # =========================================================================

    def get_replacements(self, squad: List[SquadPlayer], player_out_id: int,
                         strategy: Strategy) -> List[Tuple[SquadPlayer, str]]:
        """Get replacement options for a player using SmartPlay scores."""

        player_out = next((p for p in squad if p.id == player_out_id), None)
        if not player_out:
            return []

        # Load ML scores if not cached
        if not self._ml_scores:
            self._ml_scores = self._load_ml_scores_from_db()

        current_cost = sum(p.price for p in squad)
        available_budget = 100.0 - current_cost + player_out.price

        team_counts = {}
        for p in squad:
            if p.id != player_out_id:
                team_counts[p.team_id] = team_counts.get(p.team_id, 0) + 1

        all_players = self._fpl.get_all_players()
        candidates = [
            p for p in all_players
            if p.position == player_out.position
            and p.id not in [sp.id for sp in squad]
            and p.status == "a"
            and p.price <= available_budget
            and team_counts.get(p.team, 0) < 3
            and self._ml_scores.get(p.id, {}).get('final_score', 0) >= 5.0
        ]

        scored = []
        for player in candidates:
            ml_data = self._ml_scores.get(player.id, {})
            smartplay = ml_data.get('final_score', 0)
            # Use SmartPlay-based tags instead of KG
            tags = self._generate_smartplay_tags(player, ml_data)

            squad_player = self._create_squad_player_with_trace(
                player, tags, f"SmartPlay {smartplay:.1f}",
                smartplay * 10, {}, {}, {}, 0, 0, [], ml_data
            )

            maintains = (
                team_counts.get(player.team, 0) < 3 and
                player.price <= available_budget and
                "InjuryConcern" not in tags
            )

            scored.append((squad_player, maintains, smartplay))

        scored.sort(key=lambda x: x[2], reverse=True)
        return [(p, m) for p, m, _ in scored[:5]]
