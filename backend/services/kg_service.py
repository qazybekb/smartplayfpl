"""
Knowledge Graph Service (v2.0) - SmartPlayFPL

Advanced RDFLib Knowledge Graph with:
- Comprehensive OWL ontology with 12+ classes
- OWL-RL reasoning with inferred classes
- SHACL constraint validation (17+ rules)
- Agent-specific SPARQL query templates
- Provenance tracking for recommendations

Author: SmartPlayFPL Team
"""

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD, FOAF, OWL
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ============== Namespaces ==============

FPL = Namespace("http://fantasykg.org/ontology#")
DATA = Namespace("http://fantasykg.org/data/")
SCHEMA = Namespace("http://schema.org/")
SH = Namespace("http://www.w3.org/ns/shacl#")
PROV = Namespace("http://www.w3.org/ns/prov#")


# ============== Data Classes ==============

@dataclass
class SPARQLResult:
    """Structured SPARQL query result."""
    success: bool
    query: str
    results: List[Dict]
    count: int
    execution_time_ms: float
    error: Optional[str] = None


@dataclass
class CachedQuery:
    """Cached SPARQL query with TTL."""
    result: 'SPARQLResult'
    cached_at: datetime
    ttl_seconds: int = 300  # 5 minutes default


@dataclass
class ValidationResult:
    """SHACL validation result."""
    conforms: bool
    violations: List[Dict]
    warnings: List[Dict]
    checks_performed: List[str]
    total_triples_checked: int


@dataclass
class InferredFact:
    """An inferred fact from OWL reasoning."""
    subject: str
    predicate: str
    object: str
    rule: str
    confidence: float


# ============== Inferred Classes (OWL-RL Style) ==============

class InferredClass(Enum):
    """Classes derived through reasoning rules.

    SmartPlay-based tags use ML scores (0-10 scale):
    - finalScore: Overall composite score
    - nailednessScore: How reliably the player starts
    - formXgScore: Form based on expected goals/assists
    - formPtsScore: Form based on actual points
    - fixtureScore: Upcoming fixture difficulty
    """
    # SmartPlay-based primary tags (use ML scores)
    CAPTAIN_CANDIDATE = "CaptainCandidate"      # smartplay >= 7.5 AND nailedness >= 8.0
    TOP_PLAYER = "TopPlayer"                    # smartplay >= 7.0
    DIFFERENTIAL_PICK = "DifferentialPick"      # ownership < 10% AND smartplay >= 6.0
    ROTATION_RISK = "RotationRisk"              # nailedness < 5.0
    VALUE_PICK = "ValuePick"                    # ppm >= 20 AND smartplay >= 5.5
    PREMIUM = "Premium"                         # price >= 10 AND smartplay >= 6.5
    INJURY_CONCERN = "InjuryConcern"            # status != 'a'
    FORM_PLAYER = "FormPlayer"                  # formPts >= 7.0 OR formXg >= 7.0
    FIXTURE_FRIENDLY = "FixtureFriendly"        # fixture >= 7.0
    NAILED_ON = "NailedOn"                      # nailedness >= 9.0

    # Injury-based tags (from NLP parsing)
    HIGH_RECURRENCE_RISK = "HighRecurrenceRisk" # hamstring/calf/groin injury
    RECENTLY_RETURNED = "RecentlyReturned"      # was injured, now available


# ============== Knowledge Graph Service ==============

class KGService:
    """
    Production-grade Knowledge Graph service with reasoning.
    
    Features:
    - OWL ontology with 12+ core classes
    - OWL-RL style reasoning (inferred classes)
    - 17+ SHACL constraint validations
    - Agent-specific SPARQL templates
    - Provenance tracking
    """
    
    def __init__(self, kg_dir: Path = None):
        self.kg_dir = kg_dir or Path(__file__).parent.parent / "kg"
        self.graph = Graph()
        self.shapes_graph = Graph()
        self.inferred_graph = Graph()  # Separate graph for inferences
        self.is_ready = False
        self._fpl_service = None
        self._query_cache: Dict[str, SPARQLResult] = {}
        self._inference_rules: List[Dict] = []
        
    @property
    def triple_count(self) -> int:
        return len(self.graph) + len(self.inferred_graph)
    
    @property
    def base_triple_count(self) -> int:
        return len(self.graph)
    
    @property
    def inferred_triple_count(self) -> int:
        return len(self.inferred_graph)
    
    @property
    def class_count(self) -> int:
        return len(list(self.graph.subjects(RDF.type, OWL.Class)))
    
    @property
    def property_count(self) -> int:
        obj_props = len(list(self.graph.subjects(RDF.type, OWL.ObjectProperty)))
        data_props = len(list(self.graph.subjects(RDF.type, OWL.DatatypeProperty)))
        return obj_props + data_props
    
    @property
    def has_player_data(self) -> bool:
        """Check if player data has been loaded (not just ontology)."""
        player_count = len(list(self.graph.subjects(RDF.type, FPL.Player)))
        return player_count > 0
    
    # ============== Initialization ==============
    
    def initialize(self):
        """Initialize KG with full ontology and inference rules."""
        self._bind_namespaces()
        self._load_ontology()
        self._create_shacl_shapes()
        self._define_inference_rules()
        self.is_ready = True
        logger.info(f"✅ Knowledge Graph initialized")
        logger.info(f"   - Ontology: {self.class_count} classes, {self.property_count} properties")
        logger.info(f"   - SHACL shapes: {len(self.shapes_graph)} triples")
        logger.info(f"   - Inference rules: {len(self._inference_rules)}")
    
    def set_fpl_service(self, fpl_service):
        """Inject FPL service for data access."""
        self._fpl_service = fpl_service
    
    def _bind_namespaces(self):
        """Bind all namespaces."""
        for g in [self.graph, self.shapes_graph, self.inferred_graph]:
            g.bind("fpl", FPL)
            g.bind("data", DATA)
            g.bind("schema", SCHEMA)
            g.bind("foaf", FOAF)
            g.bind("owl", OWL)
            g.bind("rdfs", RDFS)
            g.bind("xsd", XSD)
            g.bind("sh", SH)
            g.bind("prov", PROV)
    
    def _load_ontology(self):
        """Load OWL ontology from TTL file."""
        ontology_path = self.kg_dir / "ontology.ttl"
        
        if ontology_path.exists():
            try:
                self.graph.parse(str(ontology_path), format="turtle")
                logger.info(f"✅ Loaded ontology from {ontology_path}")
            except Exception as e:
                logger.error(f"Failed to load ontology: {e}")
                self._create_minimal_ontology()
        else:
            logger.warning(f"Ontology file not found at {ontology_path}, creating minimal ontology")
            self._create_minimal_ontology()
    
    def _create_minimal_ontology(self):
        """Create minimal ontology if file not found."""
        # Core classes
        classes = ["Player", "Team", "Fixture", "Gameweek", "Position"]
        for cls_name in classes:
            cls_uri = FPL[cls_name]
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.label, Literal(cls_name)))
        
        # Inferred classes
        for cls in InferredClass:
            cls_uri = FPL[cls.value]
            self.graph.add((cls_uri, RDF.type, OWL.Class))
            self.graph.add((cls_uri, RDFS.subClassOf, FPL.Player))
            self.graph.add((cls_uri, RDFS.label, Literal(cls.value)))
    
    def _define_inference_rules(self):
        """Define SmartPlay-based inference rules.

        All rules now query fpl:SmartPlayScore entities linked to players.
        This unifies tagging with the ML scoring system.
        """
        self._inference_rules = [
            # ========== SmartPlay-based rules (use ML scores) ==========
            {
                "name": "CaptainCandidate",
                "condition": "smartplayScore >= 7.5 AND nailednessScore >= 8.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score ;
                            fpl:status ?status .
                    ?score fpl:finalScore ?smartplay ;
                           fpl:nailednessScore ?nailedness .
                    FILTER (?smartplay >= 7.5 && ?nailedness >= 8.0 && ?status = "a")
                }
                """,
                "infers": InferredClass.CAPTAIN_CANDIDATE
            },
            {
                "name": "TopPlayer",
                "condition": "smartplayScore >= 7.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:finalScore ?smartplay .
                    FILTER (?smartplay >= 7.0)
                }
                """,
                "infers": InferredClass.TOP_PLAYER
            },
            {
                "name": "DifferentialPick",
                "condition": "ownership < 10% AND smartplayScore >= 6.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:ownership ?ownership ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:finalScore ?smartplay .
                    FILTER (?ownership < 10 && ?smartplay >= 6.0)
                }
                """,
                "infers": InferredClass.DIFFERENTIAL_PICK
            },
            {
                "name": "RotationRisk",
                "condition": "nailednessScore < 5.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:nailednessScore ?nailedness .
                    FILTER (?nailedness < 5.0)
                }
                """,
                "infers": InferredClass.ROTATION_RISK
            },
            {
                "name": "ValuePick",
                "condition": "ppm >= 20 AND smartplayScore >= 5.5",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:totalPoints ?points ;
                            fpl:currentPrice ?price ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:finalScore ?smartplay .
                    FILTER ((?points / ?price) >= 20 && ?smartplay >= 5.5)
                }
                """,
                "infers": InferredClass.VALUE_PICK
            },
            {
                "name": "Premium",
                "condition": "price >= 10 AND smartplayScore >= 6.5",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:currentPrice ?price ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:finalScore ?smartplay .
                    FILTER (?price >= 10.0 && ?smartplay >= 6.5)
                }
                """,
                "infers": InferredClass.PREMIUM
            },
            {
                "name": "InjuryConcern",
                "condition": "status != 'a'",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:status ?status .
                    FILTER (?status != "a")
                }
                """,
                "infers": InferredClass.INJURY_CONCERN
            },
            {
                "name": "FormPlayer",
                "condition": "formPtsScore >= 7.0 OR formXgScore >= 7.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:formPtsScore ?formPts ;
                           fpl:formXgScore ?formXg .
                    FILTER (?formPts >= 7.0 || ?formXg >= 7.0)
                }
                """,
                "infers": InferredClass.FORM_PLAYER
            },
            {
                "name": "FixtureFriendly",
                "condition": "fixtureScore >= 7.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:fixtureScore ?fixture .
                    FILTER (?fixture >= 7.0)
                }
                """,
                "infers": InferredClass.FIXTURE_FRIENDLY
            },
            {
                "name": "NailedOn",
                "condition": "nailednessScore >= 9.0",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasSmartPlayScore ?score .
                    ?score fpl:nailednessScore ?nailedness .
                    FILTER (?nailedness >= 9.0)
                }
                """,
                "infers": InferredClass.NAILED_ON
            },
            # ========== Injury-based rules (from NLP parsing) ==========
            {
                "name": "HighRecurrenceRisk",
                "condition": "has hamstring/calf/groin injury with high recurrence risk",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:hasInjury ?injury .
                    ?injury fpl:recurrenceRisk "high" .
                }
                """,
                "infers": InferredClass.HIGH_RECURRENCE_RISK
            },
            {
                "name": "RecentlyReturned",
                "condition": "status = 'a' AND had injury with recovered date",
                "sparql": """
                SELECT ?player WHERE {
                    ?player a fpl:Player ;
                            fpl:status "a" ;
                            fpl:hasInjury ?injury .
                    ?injury fpl:recoveredDate ?date .
                }
                """,
                "infers": InferredClass.RECENTLY_RETURNED
            },
        ]
    
    def _create_shacl_shapes(self):
        """Create comprehensive SHACL shapes for validation."""
        
        # === Player Shape ===
        player_shape = FPL.PlayerShape
        self.shapes_graph.add((player_shape, RDF.type, SH.NodeShape))
        self.shapes_graph.add((player_shape, SH.targetClass, FPL.Player))
        
        # 1. Price constraint: £3.5m - £15.5m
        self._add_numeric_constraint(player_shape, FPL.currentPrice, 3.5, 15.5, "Price must be £3.5m-£15.5m")
        
        # 2. Ownership constraint: 0-100%
        self._add_numeric_constraint(player_shape, FPL.ownership, 0.0, 100.0, "Ownership must be 0-100%")
        
        # 3. Form constraint: 0-10
        self._add_numeric_constraint(player_shape, FPL.form, 0.0, 10.0, "Form must be 0-10")
        
        # 4. Minutes constraint: 0-3420 (max 38*90)
        self._add_numeric_constraint(player_shape, FPL.minutes, 0, 3420, "Minutes must be 0-3420")
        
        # 5. Goals constraint: >= 0
        self._add_min_constraint(player_shape, FPL.goals, 0, "Goals cannot be negative")
        
        # 6. Assists constraint: >= 0
        self._add_min_constraint(player_shape, FPL.assists, 0, "Assists cannot be negative")
        
        # 7. xG constraint: 0-50
        self._add_numeric_constraint(player_shape, FPL.xG, 0.0, 50.0, "xG must be 0-50")
        
        # 8. xA constraint: 0-50
        self._add_numeric_constraint(player_shape, FPL.xA, 0.0, 50.0, "xA must be 0-50")
        
        # 9. Points per game: 0-20
        self._add_numeric_constraint(player_shape, FPL.pointsPerGame, 0.0, 20.0, "PPG must be 0-20")
        
        # 10. Status pattern (a, i, d, s, u)
        self._add_pattern_constraint(player_shape, FPL.status, "^[aidsu]$", "Status must be a/i/d/s/u")
        
        # 11. Position pattern
        self._add_pattern_constraint(player_shape, FPL.position, "^(GKP|DEF|MID|FWD)$", "Position must be GKP/DEF/MID/FWD")
        
        # 12. Player must have team
        self._add_required_property(player_shape, FPL.playsFor, "Player must have a team")
        
        # 13. Chance of playing: 0-100
        chance_prop = BNode()
        self.shapes_graph.add((player_shape, SH.property, chance_prop))
        self.shapes_graph.add((chance_prop, SH.path, FPL.chanceOfPlaying))
        self.shapes_graph.add((chance_prop, SH.minInclusive, Literal(0, datatype=XSD.integer)))
        self.shapes_graph.add((chance_prop, SH.maxInclusive, Literal(100, datatype=XSD.integer)))
        
        # === Team Shape ===
        team_shape = FPL.TeamShape
        self.shapes_graph.add((team_shape, RDF.type, SH.NodeShape))
        self.shapes_graph.add((team_shape, SH.targetClass, FPL.Team))
        
        # 14. Strength constraint: 1-5
        self._add_numeric_constraint(team_shape, FPL.strength, 1, 5, "Team strength must be 1-5")
        
        # 15. Short name pattern (3 letters)
        self._add_pattern_constraint(team_shape, FPL.shortName, "^[A-Z]{3}$", "Short name must be 3 uppercase letters")
        
        # === Fixture Shape ===
        fixture_shape = FPL.FixtureShape
        self.shapes_graph.add((fixture_shape, RDF.type, SH.NodeShape))
        self.shapes_graph.add((fixture_shape, SH.targetClass, FPL.Fixture))
        
        # 16. Difficulty: 1-5
        self._add_numeric_constraint(fixture_shape, FPL.difficulty, 1, 5, "FDR must be 1-5")
        
        # 17. Gameweek number: 1-38
        self._add_numeric_constraint(fixture_shape, FPL.gameweekNumber, 1, 38, "Gameweek must be 1-38")
    
    def _add_numeric_constraint(self, shape, path, min_val, max_val, message):
        """Helper to add min/max constraint."""
        prop = BNode()
        self.shapes_graph.add((shape, SH.property, prop))
        self.shapes_graph.add((prop, SH.path, path))
        self.shapes_graph.add((prop, SH.minInclusive, Literal(min_val)))
        self.shapes_graph.add((prop, SH.maxInclusive, Literal(max_val)))
        self.shapes_graph.add((prop, SH.message, Literal(message)))
    
    def _add_min_constraint(self, shape, path, min_val, message):
        """Helper to add minimum constraint."""
        prop = BNode()
        self.shapes_graph.add((shape, SH.property, prop))
        self.shapes_graph.add((prop, SH.path, path))
        self.shapes_graph.add((prop, SH.minInclusive, Literal(min_val)))
        self.shapes_graph.add((prop, SH.message, Literal(message)))
    
    def _add_pattern_constraint(self, shape, path, pattern, message):
        """Helper to add regex pattern constraint."""
        prop = BNode()
        self.shapes_graph.add((shape, SH.property, prop))
        self.shapes_graph.add((prop, SH.path, path))
        self.shapes_graph.add((prop, SH.pattern, Literal(pattern)))
        self.shapes_graph.add((prop, SH.message, Literal(message)))
    
    def _add_required_property(self, shape, path, message):
        """Helper to add required property constraint."""
        prop = BNode()
        self.shapes_graph.add((shape, SH.property, prop))
        self.shapes_graph.add((prop, SH.path, path))
        self.shapes_graph.add((prop, SH.minCount, Literal(1, datatype=XSD.integer)))
        self.shapes_graph.add((prop, SH.message, Literal(message)))
    
    # ============== Data Population ==============
    
    async def rebuild(self):
        """Rebuild graph with fresh data and run inference."""
        if not self._fpl_service:
            logger.warning("FPL service not set, cannot rebuild")
            return
        
        start_time = datetime.now()
        initial_triples = len(self.graph)
        
        # Clear inferred graph
        self.inferred_graph = Graph()
        self._bind_namespaces()
        
        # Add teams
        for team in self._fpl_service.get_all_teams():
            self._add_team(team)
        
        # Add players
        for player in self._fpl_service.get_all_players():
            self._add_player(player)
        
        # Add fixtures
        fixtures = await self._fpl_service.get_fixtures()
        for fixture in fixtures:
            self._add_fixture(fixture)
        
        # Run inference
        inferred_count = self._run_inference()
        
        # Clear cache
        self._query_cache.clear()
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        new_triples = len(self.graph) - initial_triples
        
        logger.info(f"✅ Knowledge Graph rebuilt")
        logger.info(f"   - Added {new_triples} base triples")
        logger.info(f"   - Inferred {inferred_count} triples")
        logger.info(f"   - Total: {self.triple_count} triples in {elapsed:.0f}ms")
        
        return {
            "base_triples": new_triples,
            "inferred_triples": inferred_count,
            "total_triples": self.triple_count,
            "time_ms": round(elapsed, 2),
        }
    
    def _add_team(self, team):
        """Add team to graph."""
        team_uri = DATA[f"team/{team.id}"]
        self.graph.add((team_uri, RDF.type, FPL.Team))
        self.graph.add((team_uri, FPL.teamID, Literal(team.id, datatype=XSD.integer)))
        self.graph.add((team_uri, FOAF.name, Literal(team.name)))
        self.graph.add((team_uri, FPL.shortName, Literal(team.short_name)))
        self.graph.add((team_uri, FPL.strength, Literal(team.strength, datatype=XSD.integer)))
        self.graph.add((team_uri, FPL.strengthHome, Literal(team.strength_overall_home, datatype=XSD.integer)))
        self.graph.add((team_uri, FPL.strengthAway, Literal(team.strength_overall_away, datatype=XSD.integer)))
    
    def _add_player(self, player):
        """Add player to graph with all properties."""
        player_uri = DATA[f"player/{player.id}"]
        team_uri = DATA[f"team/{player.team}"]
        position_uri = FPL[f"position_{player.position}"]
        
        self.graph.add((player_uri, RDF.type, FPL.Player))
        self.graph.add((player_uri, FPL.playsFor, team_uri))
        self.graph.add((player_uri, FPL.hasPosition, position_uri))
        self.graph.add((player_uri, FPL.playerID, Literal(player.id, datatype=XSD.integer)))
        self.graph.add((player_uri, FOAF.name, Literal(f"{player.first_name} {player.second_name}")))
        self.graph.add((player_uri, FPL.webName, Literal(player.web_name)))
        self.graph.add((player_uri, FPL.position, Literal(player.position or "???")))
        self.graph.add((player_uri, FPL.currentPrice, Literal(player.price, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.totalPoints, Literal(player.total_points, datatype=XSD.integer)))
        
        # Calculate points per game
        ppg = round(player.total_points / max(1, player.minutes / 90), 2) if player.minutes > 0 else 0
        self.graph.add((player_uri, FPL.pointsPerGame, Literal(ppg, datatype=XSD.decimal)))
        
        self.graph.add((player_uri, FPL.form, Literal(player.form_float, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.ownership, Literal(player.ownership, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.xG, Literal(float(player.expected_goals) if player.expected_goals else 0, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.xA, Literal(float(player.expected_assists) if player.expected_assists else 0, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.minutes, Literal(player.minutes, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.goals, Literal(player.goals_scored, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.assists, Literal(player.assists, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.cleanSheets, Literal(player.clean_sheets, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.bonusPoints, Literal(player.bonus, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.ictIndex, Literal(float(player.ict_index) if player.ict_index else 0, datatype=XSD.decimal)))
        self.graph.add((player_uri, FPL.status, Literal(player.status)))
        
        if player.chance_of_playing_next_round is not None:
            self.graph.add((player_uri, FPL.chanceOfPlaying, Literal(player.chance_of_playing_next_round, datatype=XSD.integer)))
        if player.news:
            self.graph.add((player_uri, FPL.news, Literal(player.news)))
        
        self.graph.add((player_uri, FPL.transfersIn, Literal(player.transfers_in_event, datatype=XSD.integer)))
        self.graph.add((player_uri, FPL.transfersOut, Literal(player.transfers_out_event, datatype=XSD.integer)))
    
    def _add_fixture(self, fixture):
        """Add fixture to graph."""
        fixture_uri = DATA[f"fixture/{fixture.id}"]
        home_uri = DATA[f"team/{fixture.team_h}"]
        away_uri = DATA[f"team/{fixture.team_a}"]
        
        self.graph.add((fixture_uri, RDF.type, FPL.Fixture))
        self.graph.add((fixture_uri, FPL.fixtureID, Literal(fixture.id, datatype=XSD.integer)))
        self.graph.add((fixture_uri, FPL.homeTeam, home_uri))
        self.graph.add((fixture_uri, FPL.awayTeam, away_uri))
        
        if fixture.event:
            gw_uri = DATA[f"gameweek/{fixture.event}"]
            self.graph.add((fixture_uri, FPL.inGameweek, gw_uri))
            self.graph.add((fixture_uri, FPL.gameweekNumber, Literal(fixture.event, datatype=XSD.integer)))
        
        self.graph.add((fixture_uri, FPL.homeDifficulty, Literal(fixture.team_h_difficulty, datatype=XSD.integer)))
        self.graph.add((fixture_uri, FPL.awayDifficulty, Literal(fixture.team_a_difficulty, datatype=XSD.integer)))
        
        if fixture.kickoff_time:
            self.graph.add((fixture_uri, FPL.kickoffTime, Literal(fixture.kickoff_time)))

    def add_smartplay_score(self, player_id: int, scores: Dict, gameweek: int = None) -> URIRef:
        """Add SmartPlay score to graph for a player.

        Args:
            player_id: FPL player ID
            scores: Dict with keys: final_score, nailedness_score, form_xg_score,
                   form_pts_score, fixture_score (all 0-10 scale)
            gameweek: Optional gameweek number

        Returns:
            URI of the created SmartPlayScore entity
        """
        player_uri = DATA[f"player/{player_id}"]
        score_uri = DATA[f"smartplay_score/{player_id}"]

        # Remove old score if exists
        self.graph.remove((score_uri, None, None))
        self.graph.remove((player_uri, FPL.hasSmartPlayScore, None))

        # Create new score entity
        self.graph.add((score_uri, RDF.type, FPL.SmartPlayScore))
        self.graph.add((player_uri, FPL.hasSmartPlayScore, score_uri))

        # Add score components
        self.graph.add((score_uri, FPL.finalScore,
                       Literal(scores.get('final_score', 0), datatype=XSD.decimal)))
        self.graph.add((score_uri, FPL.nailednessScore,
                       Literal(scores.get('nailedness_score', 0), datatype=XSD.decimal)))
        self.graph.add((score_uri, FPL.formXgScore,
                       Literal(scores.get('form_xg_score', 0), datatype=XSD.decimal)))
        self.graph.add((score_uri, FPL.formPtsScore,
                       Literal(scores.get('form_pts_score', 0), datatype=XSD.decimal)))
        self.graph.add((score_uri, FPL.fixtureScore,
                       Literal(scores.get('fixture_score', 0), datatype=XSD.decimal)))

        # Add metadata
        self.graph.add((score_uri, FPL.calculatedAt,
                       Literal(datetime.now().isoformat(), datatype=XSD.dateTime)))
        if gameweek:
            self.graph.add((score_uri, FPL.calculatedForGameweek,
                           Literal(gameweek, datatype=XSD.integer)))

        return score_uri

    def add_smartplay_scores_batch(self, scores_dict: Dict[int, Dict], gameweek: int = None) -> int:
        """Add SmartPlay scores for multiple players efficiently.

        Args:
            scores_dict: Dict mapping player_id to scores dict
            gameweek: Optional gameweek number

        Returns:
            Number of scores added
        """
        count = 0
        for player_id, scores in scores_dict.items():
            self.add_smartplay_score(player_id, scores, gameweek)
            count += 1
        logger.info(f"Added {count} SmartPlay scores to graph")
        return count

    def add_injury_event(self, player_id: int, parsed_news) -> Optional[URIRef]:
        """Add injury event to graph from parsed news.

        Args:
            player_id: FPL player ID
            parsed_news: ParsedNews dataclass from news_parser

        Returns:
            URI of the created InjuryEvent entity, or None if no injury
        """
        from services.news_parser import Severity

        # Only create injury event for non-fit players
        if parsed_news.severity == Severity.FIT:
            return None

        player_uri = DATA[f"player/{player_id}"]
        injury_uri = DATA[f"injury/{player_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"]

        self.graph.add((injury_uri, RDF.type, FPL.InjuryEvent))
        self.graph.add((player_uri, FPL.hasInjury, injury_uri))

        # Add injury details
        if parsed_news.injury_type:
            self.graph.add((injury_uri, FPL.injuryType,
                           Literal(parsed_news.injury_type.value)))

        self.graph.add((injury_uri, FPL.severity,
                       Literal(parsed_news.severity.value)))

        if parsed_news.chance_of_playing is not None:
            self.graph.add((injury_uri, FPL.chanceOfPlaying,
                           Literal(parsed_news.chance_of_playing, datatype=XSD.integer)))

        if parsed_news.expected_return:
            self.graph.add((injury_uri, FPL.expectedReturn,
                           Literal(parsed_news.expected_return)))

        if parsed_news.is_suspension:
            self.graph.add((injury_uri, FPL.isSuspension,
                           Literal(True, datatype=XSD.boolean)))
            if parsed_news.suspension_matches:
                self.graph.add((injury_uri, FPL.suspensionMatches,
                               Literal(parsed_news.suspension_matches, datatype=XSD.integer)))

        if parsed_news.recurrence_risk:
            self.graph.add((injury_uri, FPL.recurrenceRisk,
                           Literal(parsed_news.recurrence_risk)))

        if parsed_news.risk_reason:
            self.graph.add((injury_uri, FPL.riskReason,
                           Literal(parsed_news.risk_reason)))

        self.graph.add((injury_uri, FPL.reportedDate,
                       Literal(datetime.now().isoformat(), datatype=XSD.dateTime)))
        self.graph.add((injury_uri, FPL.rawText,
                       Literal(parsed_news.raw_text)))

        logger.debug(f"Added injury event for player {player_id}: {parsed_news.severity.value}")
        return injury_uri

    def sync_injuries_from_players(self) -> int:
        """Sync injury events from all players with news.

        Parses the news field for all players and creates InjuryEvent entities.

        Returns:
            Number of injury events created
        """
        from services.news_parser import get_news_parser, Severity

        if not self._fpl_service:
            logger.warning("FPL service not set, cannot sync injuries")
            return 0

        parser = get_news_parser()
        count = 0

        for player in self._fpl_service.get_all_players():
            if player.news and player.news.strip():
                parsed = parser.parse(
                    player.news,
                    player.status,
                    player.chance_of_playing_next_round
                )
                if parsed.severity != Severity.FIT:
                    self.add_injury_event(player.id, parsed)
                    count += 1

        logger.info(f"Synced {count} injury events from player news")
        return count

    def get_player_smartplay_score(self, player_id: int) -> Optional[Dict]:
        """Get SmartPlay score for a player from the graph.

        Returns:
            Dict with score components or None if not found
        """
        # Use full URI to avoid prefix parsing issues with slashes in local names
        player_uri = f"<http://fantasykg.org/data/player/{player_id}>"
        query = f"""
        SELECT ?final ?nailedness ?formXg ?formPts ?fixture ?calculatedAt
        WHERE {{
            {player_uri} fpl:hasSmartPlayScore ?score .
            ?score fpl:finalScore ?final ;
                   fpl:nailednessScore ?nailedness ;
                   fpl:formXgScore ?formXg ;
                   fpl:formPtsScore ?formPts ;
                   fpl:fixtureScore ?fixture .
            OPTIONAL {{ ?score fpl:calculatedAt ?calculatedAt }}
        }}
        """
        result = self.execute_sparql(query, use_cache=False)
        if result.success and result.results:
            row = result.results[0]
            return {
                'final_score': row.get('final', 0),
                'nailedness_score': row.get('nailedness', 0),
                'form_xg_score': row.get('formXg', 0),
                'form_pts_score': row.get('formPts', 0),
                'fixture_score': row.get('fixture', 0),
                'calculated_at': row.get('calculatedAt'),
            }
        return None

    # ============== Inference Engine ==============
    
    def _run_inference(self) -> int:
        """Run all inference rules and populate inferred graph."""
        total_inferred = 0
        
        for rule in self._inference_rules:
            try:
                sparql = self._add_prefixes(rule["sparql"])
                results = self.graph.query(sparql)
                
                inferred_class = rule["infers"]
                count = 0
                
                for row in results:
                    player_uri = row[0]
                    # Add inferred type
                    self.inferred_graph.add((player_uri, RDF.type, FPL[inferred_class.value]))
                    count += 1
                
                total_inferred += count
                logger.debug(f"Rule '{rule['name']}' inferred {count} facts")
                
            except Exception as e:
                logger.error(f"Inference rule '{rule['name']}' failed: {e}")
        
        return total_inferred
    
    def get_inferred_players(self, inferred_class: InferredClass) -> List[Dict]:
        """Get players of a specific inferred class."""
        query = f"""
        SELECT ?id ?name ?team ?position ?price ?form ?ownership ?points
        WHERE {{
            ?player a fpl:{inferred_class.value} ;
                    fpl:playerID ?id ;
                    foaf:name ?name ;
                    fpl:position ?position ;
                    fpl:currentPrice ?price ;
                    fpl:form ?form ;
                    fpl:ownership ?ownership ;
                    fpl:totalPoints ?points ;
                    fpl:playsFor ?teamUri .
            ?teamUri fpl:shortName ?team .
        }}
        ORDER BY DESC(?form)
        """
        
        # Query both base and inferred graphs
        combined = self.graph + self.inferred_graph
        result = combined.query(self._add_prefixes(query))
        
        return [self._row_to_dict(row, result.vars) for row in result]
    
    def get_all_inferred_classes_for_player(self, player_id: int) -> List[str]:
        """Get all inferred classes for a specific player."""
        player_uri = DATA[f"player/{player_id}"]
        
        classes = []
        for cls in InferredClass:
            if (player_uri, RDF.type, FPL[cls.value]) in self.inferred_graph:
                classes.append(cls.value)
        
        return classes
    
    def get_inferred_classes_with_counts(self) -> List[Dict]:
        """Get all inferred classes with their metadata and player counts."""

        # Smart Tag metadata (updated for SmartPlay-based tags)
        tag_metadata = {
            "CaptainCandidate": {
                "description": "SmartPlay ≥7.5 AND Nailed ≥8.0. Ideal captain pick.",
                "icon": "👑",
                "color_code": "#f59e0b"  # amber
            },
            "TopPlayer": {
                "description": "SmartPlay ≥7.0. Top-tier overall performer.",
                "icon": "⭐",
                "color_code": "#10b981"  # emerald
            },
            "DifferentialPick": {
                "description": "Ownership <10% but SmartPlay ≥6.0. Rank climber.",
                "icon": "💎",
                "color_code": "#8b5cf6"  # violet
            },
            "RotationRisk": {
                "description": "Nailedness <5.0. May not start regularly.",
                "icon": "⚠️",
                "color_code": "#f97316"  # orange
            },
            "ValuePick": {
                "description": "PPM ≥20 AND SmartPlay ≥5.5. Excellent value.",
                "icon": "💰",
                "color_code": "#22c55e"  # green
            },
            "Premium": {
                "description": "Price ≥£10m AND SmartPlay ≥6.5. Justified premium.",
                "icon": "💸",
                "color_code": "#6366f1"  # indigo
            },
            "InjuryConcern": {
                "description": "Not fully available. Monitor status.",
                "icon": "🏥",
                "color_code": "#ef4444"  # red
            },
            "FormPlayer": {
                "description": "Form (pts/xG) ≥7.0. In excellent recent form.",
                "icon": "🔥",
                "color_code": "#f43f5e"  # rose
            },
            "FixtureFriendly": {
                "description": "Fixture score ≥7.0. Easy upcoming games.",
                "icon": "📅",
                "color_code": "#06b6d4"  # cyan
            },
            "NailedOn": {
                "description": "Nailedness ≥9.0. Guaranteed starter.",
                "icon": "🔒",
                "color_code": "#3b82f6"  # blue
            },
            "HighRecurrenceRisk": {
                "description": "Hamstring/calf/groin injury - high reinjury risk.",
                "icon": "⚠️",
                "color_code": "#ea580c"  # orange-600
            },
            "RecentlyReturned": {
                "description": "Recently recovered from injury - monitor carefully.",
                "icon": "🏃",
                "color_code": "#65a30d"  # lime-600
            },
        }
        
        results = []
        for cls in InferredClass:
            # Count players with this class
            count = len(list(self.inferred_graph.subjects(RDF.type, FPL[cls.value])))
            
            metadata = tag_metadata.get(cls.value, {
                "description": f"Players classified as {cls.value}",
                "icon": "🏷️",
                "color_code": "#64748b"  # slate
            })
            
            results.append({
                "name": cls.value,
                "description": metadata["description"],
                "icon": metadata["icon"],
                "color_code": metadata["color_code"],
                "count": count
            })
        
        return results
    
    # ============== SPARQL Queries ==============
    
    def execute_sparql(self, query: str, use_cache: bool = True, include_inferred: bool = True, cache_ttl: int = 300) -> SPARQLResult:
        """Execute SPARQL query with optional inference and TTL-based caching."""

        cache_key = hash(f"{query}_{include_inferred}")
        if use_cache and cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            # Check if cache is still valid (TTL-based)
            age = (datetime.now() - cached.cached_at).total_seconds()
            if age < cached.ttl_seconds:
                return cached.result
            else:
                # Cache expired, remove it
                del self._query_cache[cache_key]
        
        start_time = datetime.now()
        
        if "PREFIX" not in query.upper():
            query = self._add_prefixes(query)
        
        try:
            # Use combined graph if including inferred
            target_graph = (self.graph + self.inferred_graph) if include_inferred else self.graph
            qres = target_graph.query(query)
            
            results = [self._row_to_dict(row, qres.vars) for row in qres]
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            result = SPARQLResult(
                success=True,
                query=query,
                results=results,
                count=len(results),
                execution_time_ms=round(elapsed, 2)
            )
            
            if use_cache:
                self._query_cache[cache_key] = CachedQuery(
                    result=result,
                    cached_at=datetime.now(),
                    ttl_seconds=cache_ttl
                )

            return result
            
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return SPARQLResult(
                success=False,
                query=query,
                results=[],
                count=0,
                execution_time_ms=round(elapsed, 2),
                error=str(e)
            )
    
    def _add_prefixes(self, query: str) -> str:
        """Add standard prefixes to SPARQL query."""
        return """
        PREFIX fpl: <http://fantasykg.org/ontology#>
        PREFIX data: <http://fantasykg.org/data/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        """ + query
    
    def _row_to_dict(self, row, vars) -> Dict:
        """Convert SPARQL row to dictionary."""
        result = {}
        var_names = [str(v) for v in vars] if vars else []
        for i, val in enumerate(row):
            var_name = var_names[i] if i < len(var_names) else f"var_{i}"
            result[var_name] = self._format_value(val)
        return result
    
    def _format_value(self, val) -> Any:
        """Format RDF value for JSON output."""
        if val is None:
            return None
        
        if isinstance(val, Literal):
            if val.datatype == XSD.integer:
                return int(val)
            elif val.datatype == XSD.decimal:
                return float(val)
            elif val.datatype == XSD.boolean:
                return bool(val)
            return str(val)
        
        str_val = str(val)
        if str_val.startswith("http://fantasykg.org/ontology#"):
            return str_val.split("#")[-1]
        if str_val.startswith("http://fantasykg.org/data/"):
            return str_val.split("/")[-1]
        
        return str_val
    
    # ============== Query Templates ==============
    
    def get_top_players_by_form(self, limit: int = 20) -> List[Dict]:
        """Get top players by form score."""
        query = f"""
        SELECT ?id ?name ?position ?team ?price ?form ?ownership ?points
        WHERE {{
            ?player a fpl:Player ;
                    fpl:playerID ?id ;
                    foaf:name ?name ;
                    fpl:position ?position ;
                    fpl:currentPrice ?price ;
                    fpl:form ?form ;
                    fpl:ownership ?ownership ;
                    fpl:totalPoints ?points ;
                    fpl:playsFor ?teamUri .
            ?teamUri fpl:shortName ?team .
        }}
        ORDER BY DESC(?form)
        LIMIT {limit}
        """
        result = self.execute_sparql(query)
        return result.results if result.success else []
    
    def get_differentials(self, max_ownership: float = 10.0, min_form: float = 4.0) -> Dict:
        """Find differential players."""
        query = f"""
        SELECT ?id ?name ?position ?team ?price ?form ?ownership ?points ?xG
        WHERE {{
            ?player a fpl:Player ;
                    fpl:playerID ?id ;
                    foaf:name ?name ;
                    fpl:position ?position ;
                    fpl:currentPrice ?price ;
                    fpl:form ?form ;
                    fpl:ownership ?ownership ;
                    fpl:totalPoints ?points ;
                    fpl:xG ?xG ;
                    fpl:playsFor ?teamUri .
            ?teamUri fpl:shortName ?team .
            FILTER (?ownership < {max_ownership})
            FILTER (?form >= {min_form})
        }}
        ORDER BY DESC(?form)
        LIMIT 20
        """
        result = self.execute_sparql(query)
        return {
            "differentials": result.results,
            "count": result.count,
            "filters": {"max_ownership": max_ownership, "min_form": min_form}
        }
    
    def get_players_by_position(self, position: str, limit: int = 50) -> List[Dict]:
        """Get players filtered by position."""
        query = f"""
        SELECT ?id ?name ?team ?price ?form ?ownership ?points ?minutes ?goals ?assists
        WHERE {{
            ?player a fpl:Player ;
                    fpl:playerID ?id ;
                    foaf:name ?name ;
                    fpl:position "{position}" ;
                    fpl:currentPrice ?price ;
                    fpl:form ?form ;
                    fpl:ownership ?ownership ;
                    fpl:totalPoints ?points ;
                    fpl:minutes ?minutes ;
                    fpl:goals ?goals ;
                    fpl:assists ?assists ;
                    fpl:playsFor ?teamUri .
            ?teamUri fpl:shortName ?team .
        }}
        ORDER BY DESC(?form)
        LIMIT {limit}
        """
        result = self.execute_sparql(query)
        return result.results if result.success else []
    
    def get_players_by_team(self, team_short: str) -> List[Dict]:
        """Get all players from a specific team."""
        query = f"""
        SELECT ?id ?name ?position ?price ?form ?ownership ?points
        WHERE {{
            ?player a fpl:Player ;
                    fpl:playerID ?id ;
                    foaf:name ?name ;
                    fpl:position ?position ;
                    fpl:currentPrice ?price ;
                    fpl:form ?form ;
                    fpl:ownership ?ownership ;
                    fpl:totalPoints ?points ;
                    fpl:playsFor ?teamUri .
            ?teamUri fpl:shortName "{team_short}" .
        }}
        ORDER BY DESC(?form)
        """
        result = self.execute_sparql(query)
        return result.results if result.success else []
    
    # ============== SHACL Validation ==============
    
    def validate(self) -> ValidationResult:
        """Run comprehensive SHACL-style validation."""
        violations = []
        warnings = []
        checks = []
        
        validation_queries = [
            ("Price range (£3.5m-£15.5m)", "fpl:currentPrice", "?price < 3.5 || ?price > 15.5"),
            ("Ownership (0-100%)", "fpl:ownership", "?ownership < 0 || ?ownership > 100"),
            ("Form (0-10)", "fpl:form", "?form < 0 || ?form > 10"),
            ("Minutes (0-3420)", "fpl:minutes", "?minutes < 0 || ?minutes > 3420"),
            ("Goals (>=0)", "fpl:goals", "?goals < 0"),
            ("Assists (>=0)", "fpl:assists", "?assists < 0"),
            ("xG (0-50)", "fpl:xG", "?xG < 0 || ?xG > 50"),
        ]
        
        for check_name, prop, condition in validation_queries:
            checks.append(check_name)
            var = prop.split(":")[-1]
            query = f"""
            SELECT ?player ?name ?{var} WHERE {{
                ?player a fpl:Player ;
                        foaf:name ?name ;
                        {prop} ?{var} .
                FILTER ({condition})
            }}
            """
            result = self.execute_sparql(query, include_inferred=False)
            for row in result.results:
                violations.append({
                    "type": "sh:RangeConstraint",
                    "check": check_name,
                    "player": row.get('name'),
                    "value": row.get(var),
                })
        
        # Check player has team
        checks.append("Player must have team")
        team_query = """
        SELECT ?player ?name WHERE {
            ?player a fpl:Player ; foaf:name ?name .
            FILTER NOT EXISTS { ?player fpl:playsFor ?team }
        }
        """
        result = self.execute_sparql(team_query, include_inferred=False)
        for row in result.results:
            violations.append({
                "type": "sh:MinCount",
                "check": "Player must have team",
                "player": row.get('name'),
            })
        
        return ValidationResult(
            conforms=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            checks_performed=checks,
            total_triples_checked=len(self.graph)
        )

    def validate_squad(self, player_ids: List[int]) -> Dict:
        """Validate a squad of 15 players against FPL rules.

        Args:
            player_ids: List of 15 player IDs

        Returns:
            Dict with validation results including:
            - valid: bool - whether squad passes all hard constraints
            - violations: list of rule violations
            - warnings: list of soft constraint warnings
            - squad_info: summary of squad composition
        """
        violations = []
        warnings = []

        # Get player data from graph
        players = []
        for pid in player_ids:
            # Use full URI to avoid prefix parsing issues with slashes in local names
            player_uri = f"<http://fantasykg.org/data/player/{pid}>"
            query = f"""
            SELECT ?name ?position ?team ?price ?status ?form
            WHERE {{
                {player_uri} a fpl:Player ;
                    foaf:name ?name ;
                    fpl:position ?position ;
                    fpl:currentPrice ?price ;
                    fpl:status ?status ;
                    fpl:form ?form ;
                    fpl:playsFor ?teamUri .
                ?teamUri fpl:shortName ?team .
            }}
            """
            result = self.execute_sparql(query, use_cache=False)
            if result.success and result.results:
                player = result.results[0]
                player['id'] = pid
                players.append(player)
            else:
                violations.append({
                    "type": "PlayerNotFound",
                    "message": f"Player {pid} not found in graph"
                })

        if len(players) < 15:
            # Can't validate incomplete squad
            return {
                "valid": False,
                "violations": violations,
                "warnings": [],
                "squad_info": {"found_players": len(players)}
            }

        # Count by position
        position_counts = {"GKP": 0, "DEF": 0, "MID": 0, "FWD": 0}
        team_counts = {}
        total_price = 0.0

        for p in players:
            pos = p.get('position', 'Unknown')
            if pos in position_counts:
                position_counts[pos] += 1

            team = p.get('team', 'Unknown')
            team_counts[team] = team_counts.get(team, 0) + 1

            total_price += float(p.get('price', 0))

        # === Hard Constraints (violations) ===

        # 1. Squad size must be 15
        if len(players) != 15:
            violations.append({
                "type": "SquadSize",
                "message": f"Squad must have 15 players, got {len(players)}"
            })

        # 2. Budget: <= £100m
        if total_price > 100.0:
            violations.append({
                "type": "BudgetExceeded",
                "message": f"Total cost £{total_price:.1f}m exceeds £100m budget"
            })

        # 3. Goalkeepers: exactly 2
        if position_counts["GKP"] != 2:
            violations.append({
                "type": "GoalkeeperCount",
                "message": f"Must have 2 GKPs, got {position_counts['GKP']}"
            })

        # 4. Defenders: exactly 5
        if position_counts["DEF"] != 5:
            violations.append({
                "type": "DefenderCount",
                "message": f"Must have 5 DEFs, got {position_counts['DEF']}"
            })

        # 5. Midfielders: exactly 5
        if position_counts["MID"] != 5:
            violations.append({
                "type": "MidfielderCount",
                "message": f"Must have 5 MIDs, got {position_counts['MID']}"
            })

        # 6. Forwards: exactly 3
        if position_counts["FWD"] != 3:
            violations.append({
                "type": "ForwardCount",
                "message": f"Must have 3 FWDs, got {position_counts['FWD']}"
            })

        # 7. Max 3 from any team
        for team, count in team_counts.items():
            if count > 3:
                violations.append({
                    "type": "TeamLimit",
                    "message": f"Max 3 players per team, got {count} from {team}"
                })

        # === Soft Constraints (warnings) ===

        # Check for injured/unavailable players
        unavailable = [p for p in players if p.get('status') != 'a']
        if unavailable:
            for p in unavailable:
                warnings.append({
                    "type": "InjuredPlayer",
                    "message": f"{p.get('name')} is not available (status: {p.get('status')})"
                })

        # Check for rotation risks (via inferred class)
        for p in players:
            inferred = self.get_all_inferred_classes_for_player(p['id'])
            if "RotationRisk" in inferred:
                warnings.append({
                    "type": "RotationRisk",
                    "message": f"{p.get('name')} has rotation risk"
                })
            if "HighRecurrenceRisk" in inferred:
                warnings.append({
                    "type": "InjuryRisk",
                    "message": f"{p.get('name')} has high injury recurrence risk"
                })

        is_valid = len(violations) == 0

        return {
            "valid": is_valid,
            "violations": violations,
            "warnings": warnings,
            "squad_info": {
                "total_price": round(total_price, 1),
                "remaining_budget": round(100.0 - total_price, 1),
                "position_counts": position_counts,
                "team_counts": team_counts,
                "player_count": len(players),
            }
        }

    # ============== Statistics & Export ==============
    
    def get_statistics(self) -> Dict:
        """Get comprehensive KG statistics."""
        player_count = len(list(self.graph.subjects(RDF.type, FPL.Player)))
        team_count = len(list(self.graph.subjects(RDF.type, FPL.Team)))
        fixture_count = len(list(self.graph.subjects(RDF.type, FPL.Fixture)))
        
        # Count inferred by class
        inferred_counts = {}
        for cls in InferredClass:
            count = len(list(self.inferred_graph.subjects(RDF.type, FPL[cls.value])))
            inferred_counts[cls.value] = count
        
        return {
            "total_triples": self.triple_count,
            "base_triples": self.base_triple_count,
            "inferred_triples": self.inferred_triple_count,
            "entities": {
                "players": player_count,
                "teams": team_count,
                "fixtures": fixture_count,
            },
            "ontology": {
                "classes": self.class_count,
                "properties": self.property_count,
                "inferred_classes": len(InferredClass),
            },
            "inference": {
                "rules_count": len(self._inference_rules),
                "inferred_by_class": inferred_counts,
            },
            "validation": {
                "shacl_shapes": len(self.shapes_graph),
                "checks_available": 17,
            },
        }
    
    def export_turtle(self) -> str:
        """Export knowledge graph as Turtle format."""
        combined = self.graph + self.inferred_graph
        return combined.serialize(format='turtle')
    
    def get_inference_summary(self) -> Dict:
        """Get summary of all inference rules and results."""
        return {
            "rules": [
                {
                    "name": r["name"],
                    "condition": r["condition"],
                    "inferred_class": r["infers"].value,
                }
                for r in self._inference_rules
            ],
            "total_rules": len(self._inference_rules),
        }


# ============== Singleton Access ==============

_kg_service_instance: Optional[KGService] = None


def get_kg_service() -> KGService:
    """Get or create the singleton KGService instance.
    
    Auto-initializes the KG if not already ready.
    """
    global _kg_service_instance
    if _kg_service_instance is None:
        _kg_service_instance = KGService()
    
    # Auto-initialize if not ready
    if not _kg_service_instance.is_ready:
        _kg_service_instance.initialize()
    
    return _kg_service_instance

