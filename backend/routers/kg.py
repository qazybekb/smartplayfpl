"""Knowledge Graph API Router.

Provides endpoints for:
- SPARQL queries
- Inferred class queries
- KG statistics
- SHACL validation
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from services.kg_service import get_kg_service, InferredClass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


async def ensure_kg_ready():
    """Ensure Knowledge Graph is initialized and has player data.
    
    Returns the KG service instance, auto-rebuilding if needed.
    """
    from services.fpl_service import fpl_service
    
    kg = get_kg_service()
    
    # Auto-rebuild if no player data exists
    if not kg.has_player_data:
        kg.set_fpl_service(fpl_service)
        await kg.rebuild()
    
    return kg


@router.get("/status")
async def get_kg_status():
    """Get Knowledge Graph status and statistics."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        return {
            "status": "not_initialized",
            "message": "Knowledge Graph not yet initialized. Call /kg/rebuild first.",
        }
    
    return {
        "status": "ready",
        "statistics": kg.get_statistics(),
    }


@router.post("/rebuild")
async def rebuild_kg():
    """Rebuild the Knowledge Graph with fresh data from FPL API.
    
    This will:
    1. Fetch all players, teams, fixtures from FPL API
    2. Populate the RDF graph with triples
    3. Run OWL inference rules to classify players
    4. Clear query cache
    """
    from services.fpl_service import fpl_service
    
    kg = get_kg_service()
    
    # Initialize if needed
    if not kg.is_ready:
        kg.initialize()
    
    # Set FPL service and rebuild
    kg.set_fpl_service(fpl_service)
    result = await kg.rebuild()
    
    return {
        "success": True,
        "message": "Knowledge Graph rebuilt successfully",
        "result": result,
        "statistics": kg.get_statistics(),
    }


@router.get("/inferred/{class_name}")
async def get_inferred_players(class_name: str):
    """Get all players of a specific inferred class.

    SmartPlay-based classes (use ML scores):
    - CaptainCandidate: smartplay >= 7.5 AND nailedness >= 8.0
    - TopPlayer: smartplay >= 7.0
    - DifferentialPick: ownership < 10% AND smartplay >= 6.0
    - RotationRisk: nailedness < 5.0
    - ValuePick: ppm >= 20 AND smartplay >= 5.5
    - Premium: price >= 10 AND smartplay >= 6.5
    - InjuryConcern: status != 'a'
    - FormPlayer: formPts >= 7.0 OR formXg >= 7.0
    - FixtureFriendly: fixture >= 7.0
    - NailedOn: nailedness >= 9.0

    Injury-based classes:
    - HighRecurrenceRisk: hamstring/calf/groin injury
    - RecentlyReturned: recently recovered from injury
    """
    kg = await ensure_kg_ready()
    
    # Find the matching inferred class
    inferred_class = None
    for cls in InferredClass:
        if cls.value.lower() == class_name.lower() or cls.name.lower() == class_name.lower():
            inferred_class = cls
            break
    
    if inferred_class is None:
        available = [cls.value for cls in InferredClass]
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown class '{class_name}'. Available: {available}"
        )
    
    players = kg.get_inferred_players(inferred_class)
    
    return {
        "class": inferred_class.value,
        "count": len(players),
        "players": players,
    }


@router.get("/inferred-classes")
async def get_all_inferred_classes():
    """Get list of all available inferred classes with their rules."""
    kg = await ensure_kg_ready()
    return kg.get_inference_summary()


@router.get("/player/{player_id}/classes")
async def get_player_classes(player_id: int):
    """Get all inferred classes for a specific player."""
    kg = await ensure_kg_ready()
    classes = kg.get_all_inferred_classes_for_player(player_id)
    
    return {
        "player_id": player_id,
        "inferred_classes": classes,
        "count": len(classes),
    }


@router.post("/sparql")
async def execute_sparql(
    query: str,
    include_inferred: bool = True,
):
    """Execute a SPARQL query against the Knowledge Graph.

    SECURITY: Only SELECT, ASK, and DESCRIBE queries are allowed.
    Mutation queries (INSERT, DELETE, etc.) are blocked.

    Example queries:

    1. Get top 10 players by form:
    ```sparql
    SELECT ?name ?form ?team WHERE {
        ?player a fpl:Player ;
                foaf:name ?name ;
                fpl:form ?form ;
                fpl:playsFor ?teamUri .
        ?teamUri fpl:shortName ?team .
    }
    ORDER BY DESC(?form)
    LIMIT 10
    ```

    2. Get captain candidates:
    ```sparql
    SELECT ?name ?form ?ownership WHERE {
        ?player a fpl:CaptainCandidate ;
                foaf:name ?name ;
                fpl:form ?form ;
                fpl:ownership ?ownership .
    }
    ```
    """
    from middleware.security import SPARQLQueryValidator

    kg = get_kg_service()

    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")

    # Validate and sanitize SPARQL query for security
    validator = SPARQLQueryValidator(max_results=1000)
    sanitized_query, error = validator.validate_and_sanitize(query)

    if error:
        logger.warning(f"SPARQL query rejected: {error}")
        raise HTTPException(status_code=400, detail=f"Invalid SPARQL query: {error}")

    result = kg.execute_sparql(sanitized_query, use_cache=False, include_inferred=include_inferred)

    if not result.success:
        raise HTTPException(status_code=400, detail=f"SPARQL error: {result.error}")

    return {
        "success": True,
        "count": result.count,
        "execution_time_ms": result.execution_time_ms,
        "results": result.results,
    }


@router.get("/validate")
async def validate_kg():
    """Run SHACL validation on the Knowledge Graph.
    
    Checks:
    - Price range (£3.5m - £15.5m)
    - Ownership (0-100%)
    - Form (0-10)
    - Minutes (0-3420)
    - Goals, assists >= 0
    - xG, xA (0-50)
    - Position pattern (GKP/DEF/MID/FWD)
    - Status pattern (a/i/d/s/u)
    - Player must have team
    """
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    result = kg.validate()
    
    return {
        "conforms": result.conforms,
        "violations_count": len(result.violations),
        "violations": result.violations,
        "warnings": result.warnings,
        "checks_performed": result.checks_performed,
        "total_triples_checked": result.total_triples_checked,
    }


@router.get("/query/differentials")
async def get_differentials(
    max_ownership: float = Query(10.0, description="Maximum ownership percentage"),
    min_form: float = Query(4.0, description="Minimum form score"),
):
    """Get differential players (low ownership, high form)."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    return kg.get_differentials(max_ownership, min_form)


@router.get("/query/top-form")
async def get_top_form(limit: int = Query(20, description="Number of players to return")):
    """Get top players by form score."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    players = kg.get_top_players_by_form(limit)
    
    return {
        "count": len(players),
        "players": players,
    }


@router.get("/query/by-position/{position}")
async def get_by_position(
    position: str,
    limit: int = Query(50, description="Number of players to return"),
):
    """Get players filtered by position (GKP, DEF, MID, FWD)."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    position = position.upper()
    if position not in ["GKP", "DEF", "MID", "FWD"]:
        raise HTTPException(status_code=400, detail="Position must be GKP, DEF, MID, or FWD")
    
    players = kg.get_players_by_position(position, limit)
    
    return {
        "position": position,
        "count": len(players),
        "players": players,
    }


@router.get("/query/by-team/{team}")
async def get_by_team(team: str):
    """Get all players from a specific team (e.g., LIV, MCI, ARS)."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    players = kg.get_players_by_team(team.upper())
    
    return {
        "team": team.upper(),
        "count": len(players),
        "players": players,
    }


@router.get("/export/turtle")
async def export_turtle():
    """Export the entire Knowledge Graph as Turtle format."""
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    from fastapi.responses import PlainTextResponse
    
    turtle = kg.export_turtle()
    return PlainTextResponse(content=turtle, media_type="text/turtle")


@router.get("/ontology")
async def get_ontology_info():
    """Get information about the FPL ontology."""
    kg = get_kg_service()
    
    return {
        "name": "SmartPlayFPL Ontology",
        "version": "2.0.0",
        "namespace": "http://fantasykg.org/ontology#",
        "core_classes": [
            "Player", "Team", "Fixture", "Gameweek", "Position",
            "InjuryEvent", "PriceChange", "Recommendation", "Agent"
        ],
        "inferred_classes": [cls.value for cls in InferredClass],
        "inference_rules": kg.get_inference_summary()["rules"] if kg.is_ready else [],
    }


@router.get("/player/{player_id}/explain")
async def explain_player_tags(player_id: int):
    """Get detailed explanation of why a player received each Smart Tag.

    Returns the SmartPlay score-based rules that matched and the actual values that triggered them.
    """
    from services.fpl_service import fpl_service
    from services.predictor_service import get_predictor_service
    from database import SessionLocal, MLPlayerScore

    kg = get_kg_service()

    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")

    # Get player data
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    # Calculate derived values
    ppg = round(player.total_points / max(1, player.minutes / 90), 2) if player.minutes > 0 else 0
    ppm = round(player.total_points / player.price, 2) if player.price > 0 else 0

    # Get SmartPlay scores - first try predictor service, then database
    predictor = get_predictor_service()
    ml_data = predictor.get_player_score(player_id)

    # If predictor service doesn't have data, fall back to database
    if not ml_data:
        db = SessionLocal()
        try:
            db_score = db.query(MLPlayerScore).filter(
                MLPlayerScore.player_id == player_id
            ).order_by(MLPlayerScore.calculated_at.desc()).first()

            if db_score:
                # Helper to safely parse values (handles bytes from corrupted DB)
                def safe_float(val, default=0.0):
                    if val is None:
                        return default
                    if isinstance(val, bytes):
                        try:
                            import struct
                            return struct.unpack('<d', val)[0] if len(val) == 8 else default
                        except Exception:
                            return default
                    try:
                        return float(val)
                    except Exception:
                        return default

                ml_data = {
                    'final_score': safe_float(db_score.final_score),
                    'nailedness_score': safe_float(db_score.nailedness_score),
                    'form_xg_score': safe_float(db_score.form_xg_score),
                    'form_pts_score': safe_float(db_score.form_pts_score),
                    'fixture_score': safe_float(db_score.fixture_score),
                }
        except Exception as e:
            logger.warning(f"Error fetching scores from database: {e}")
        finally:
            db.close()

    smartplay = ml_data.get('final_score', 0) if ml_data else 0
    nailedness = ml_data.get('nailedness_score', 0) if ml_data else 0
    form_xg = ml_data.get('form_xg_score', 0) if ml_data else 0
    form_pts = ml_data.get('form_pts_score', 0) if ml_data else 0
    fixture = ml_data.get('fixture_score', 0) if ml_data else 0

    # Generate tags based on SmartPlay scores (matches backend squad_builder.py logic)
    matched_tags = []
    if smartplay >= 7.5 and nailedness >= 8.0:
        matched_tags.append("CaptainCandidate")
    if smartplay >= 7.0:
        matched_tags.append("TopPlayer")
    if nailedness < 5.0:
        matched_tags.append("RotationRisk")
    if form_pts >= 7.0 or form_xg >= 7.0:
        matched_tags.append("FormPlayer")
    if fixture >= 7.0:
        matched_tags.append("FixtureFriendly")
    if ppm >= 20 and smartplay >= 5.5:
        matched_tags.append("ValuePick")
    if player.ownership < 10 and smartplay >= 6.0:
        matched_tags.append("DifferentialPick")
    if player.price >= 10.0 and smartplay >= 6.5:
        matched_tags.append("Premium")
    if nailedness >= 9.0:
        matched_tags.append("NailedOn")
    if player.status not in ("a",):
        matched_tags.append("InjuryConcern")

    # Define SmartPlay-based rules with explanations
    rules_config = {
        "CaptainCandidate": {
            "description": "Elite SmartPlay score AND highly nailed - ideal captain pick",
            "conditions": [
                {"field": "smartplay", "op": ">=", "threshold": 7.5, "value": smartplay, "label": "SmartPlay Score"},
                {"field": "nailedness", "op": ">=", "threshold": 8.0, "value": nailedness, "label": "Nailedness"},
            ]
        },
        "TopPlayer": {
            "description": "High overall SmartPlay score - top tier performer",
            "conditions": [
                {"field": "smartplay", "op": ">=", "threshold": 7.0, "value": smartplay, "label": "SmartPlay Score"},
            ]
        },
        "RotationRisk": {
            "description": "Low nailedness score - may not start regularly",
            "conditions": [
                {"field": "nailedness", "op": "<", "threshold": 5.0, "value": nailedness, "label": "Nailedness"},
            ]
        },
        "FormPlayer": {
            "description": "Strong recent form based on points or expected goals",
            "conditions": [
                {"field": "form_pts", "op": ">=", "threshold": 7.0, "value": form_pts, "label": "Form (Points)", "or_next": True},
                {"field": "form_xg", "op": ">=", "threshold": 7.0, "value": form_xg, "label": "Form (xG)"},
            ]
        },
        "FixtureFriendly": {
            "description": "Favorable upcoming fixtures",
            "conditions": [
                {"field": "fixture", "op": ">=", "threshold": 7.0, "value": fixture, "label": "Fixture Score"},
            ]
        },
        "ValuePick": {
            "description": "Excellent points per million with solid SmartPlay score",
            "conditions": [
                {"field": "ppm", "op": ">=", "threshold": 20, "value": ppm, "label": "Points/£m"},
                {"field": "smartplay", "op": ">=", "threshold": 5.5, "value": smartplay, "label": "SmartPlay Score"},
            ]
        },
        "DifferentialPick": {
            "description": "Low ownership but quality SmartPlay score - rank climbing potential",
            "conditions": [
                {"field": "ownership", "op": "<", "threshold": 10, "value": player.ownership, "label": "Ownership %"},
                {"field": "smartplay", "op": ">=", "threshold": 6.0, "value": smartplay, "label": "SmartPlay Score"},
            ]
        },
        "Premium": {
            "description": "Expensive premium asset with justified SmartPlay score",
            "conditions": [
                {"field": "price", "op": ">=", "threshold": 10.0, "value": player.price, "label": "Price £m"},
                {"field": "smartplay", "op": ">=", "threshold": 6.5, "value": smartplay, "label": "SmartPlay Score"},
            ]
        },
        "NailedOn": {
            "description": "Extremely high nailedness - guaranteed starter",
            "conditions": [
                {"field": "nailedness", "op": ">=", "threshold": 9.0, "value": nailedness, "label": "Nailedness"},
            ]
        },
        "InjuryConcern": {
            "description": "Player flagged as unavailable or doubtful",
            "conditions": [
                {"field": "status", "op": "!=", "threshold": "a", "value": player.status, "label": "Status"},
            ]
        },
    }
    
    explanations = []
    
    for tag_id, config in rules_config.items():
        is_matched = tag_id in matched_tags
        
        conditions_result = []
        for cond in config["conditions"]:
            # Evaluate condition
            if cond["op"] == ">=":
                passed = cond["value"] >= cond["threshold"]
            elif cond["op"] == ">":
                passed = cond["value"] > cond["threshold"]
            elif cond["op"] == "<":
                passed = cond["value"] < cond["threshold"]
            elif cond["op"] == "<=":
                passed = cond["value"] <= cond["threshold"]
            elif cond["op"] == "==":
                passed = cond["value"] == cond["threshold"]
            elif cond["op"] == "!=":
                passed = cond["value"] != cond["threshold"]
            elif cond["op"] == "in":
                passed = cond["value"] in cond["threshold"]
            else:
                passed = False
            
            # Calculate strength (how close to threshold)
            if isinstance(cond["threshold"], (int, float)) and isinstance(cond["value"], (int, float)):
                if cond["op"] in [">=", ">"]:
                    strength = min(100, max(0, (cond["value"] / cond["threshold"]) * 100)) if cond["threshold"] > 0 else 100
                elif cond["op"] in ["<", "<="]:
                    strength = min(100, max(0, (1 - cond["value"] / cond["threshold"]) * 100)) if cond["threshold"] > 0 else 100
                else:
                    strength = 100 if passed else 0
            else:
                strength = 100 if passed else 0
            
            conditions_result.append({
                "label": cond["label"],
                "operator": cond["op"],
                "threshold": cond["threshold"],
                "actual": cond["value"],
                "passed": passed,
                "strength": round(strength, 1),
                "is_or": cond.get("or_next", False),
            })
        
        # Calculate overall tag strength
        if conditions_result:
            avg_strength = sum(c["strength"] for c in conditions_result) / len(conditions_result)
        else:
            avg_strength = 0
        
        explanations.append({
            "tag_id": tag_id,
            "description": config["description"],
            "matched": is_matched,
            "strength": round(avg_strength, 1),
            "conditions": conditions_result,
        })
    
    return {
        "player_id": player_id,
        "player_name": player.web_name,
        "explanations": explanations,
        "matched_tags": matched_tags,
        "player_stats": {
            "form": player.form_float,
            "points": player.total_points,
            "price": player.price,
            "ownership": player.ownership,
            "minutes": player.minutes,
            "status": player.status,
            "ppg": ppg,
            "ppm": ppm,
        },
        "smartplay_scores": {
            "final_score": smartplay,
            "nailedness_score": nailedness,
            "form_xg_score": form_xg,
            "form_pts_score": form_pts,
            "fixture_score": fixture,
        }
    }


@router.get("/player/{player_id}/similar")
async def get_similar_players(
    player_id: int,
    limit: int = Query(5, description="Number of similar players to return")
):
    """Find semantically similar players using SPARQL.
    
    Similarity is based on:
    - Same position
    - Similar price bracket (±£1.5m)
    - Similar form (±2.0)
    - Shared Smart Tags
    """
    from services.fpl_service import fpl_service
    
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    # Get player data
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    # Get player's tags
    player_tags = set(kg.get_all_inferred_classes_for_player(player_id))
    
    # SPARQL query to find similar players
    price_min = player.price - 1.5
    price_max = player.price + 1.5
    form_min = max(0, player.form_float - 2.0)
    form_max = min(10, player.form_float + 2.0)
    
    query = f"""
    SELECT ?id ?name ?team ?price ?form ?ownership ?points
    WHERE {{
        ?player a fpl:Player ;
                fpl:playerID ?id ;
                foaf:name ?name ;
                fpl:position "{player.position}" ;
                fpl:currentPrice ?price ;
                fpl:form ?form ;
                fpl:ownership ?ownership ;
                fpl:totalPoints ?points ;
                fpl:playsFor ?teamUri .
        ?teamUri fpl:shortName ?team .
        FILTER (?id != {player_id})
        FILTER (?price >= {price_min} && ?price <= {price_max})
        FILTER (?form >= {form_min} && ?form <= {form_max})
    }}
    ORDER BY DESC(?form)
    LIMIT 20
    """
    
    result = kg.execute_sparql(query)
    
    if not result.success:
        return {"similar_players": [], "error": result.error}
    
    # Score and rank by similarity
    similar = []
    for row in result.results:
        pid = row.get("id")
        if pid:
            other_tags = set(kg.get_all_inferred_classes_for_player(int(pid)))
            shared_tags = player_tags & other_tags
            
            # Similarity score
            price_diff = abs(float(row.get("price", 0)) - player.price)
            form_diff = abs(float(row.get("form", 0)) - player.form_float)
            tag_overlap = len(shared_tags) / max(1, len(player_tags | other_tags))
            
            similarity_score = (
                (1 - price_diff / 3) * 30 +  # Price similarity (max 30)
                (1 - form_diff / 4) * 30 +   # Form similarity (max 30)
                tag_overlap * 40              # Tag overlap (max 40)
            )
            
            similar.append({
                "id": pid,
                "name": row.get("name"),
                "team": row.get("team"),
                "price": row.get("price"),
                "form": row.get("form"),
                "ownership": row.get("ownership"),
                "points": row.get("points"),
                "shared_tags": list(shared_tags),
                "similarity_score": round(similarity_score, 1),
            })
    
    # Sort by similarity and limit
    similar.sort(key=lambda x: x["similarity_score"], reverse=True)
    similar = similar[:limit]
    
    return {
        "player_id": player_id,
        "player_name": player.web_name,
        "position": player.position,
        "price": player.price,
        "player_tags": list(player_tags),
        "similar_players": similar,
        "query_used": query.strip(),
    }


@router.get("/player/{player_id}/provenance")
async def get_player_provenance(player_id: int):
    """Get data provenance for a player - where each piece of data came from."""
    from services.fpl_service import fpl_service
    import datetime
    
    kg = get_kg_service()
    
    if not kg.is_ready:
        raise HTTPException(status_code=400, detail="Knowledge Graph not initialized")
    
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    # Get inferred classes
    inferred_classes = kg.get_all_inferred_classes_for_player(player_id)
    
    now = datetime.datetime.now().isoformat()
    
    provenance = {
        "player_id": player_id,
        "player_name": player.web_name,
        "data_sources": [
            {
                "field": "form",
                "value": player.form_float,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
            {
                "field": "total_points",
                "value": player.total_points,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
            {
                "field": "price",
                "value": player.price,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
            {
                "field": "ownership",
                "value": player.ownership,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
            {
                "field": "xG",
                "value": float(player.expected_goals) if player.expected_goals else 0,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
            {
                "field": "status",
                "value": player.status,
                "source": "FPL Bootstrap API",
                "source_type": "api",
                "uri": "https://fantasy.premierleague.com/api/bootstrap-static/",
                "updated": now,
            },
        ],
        "inferred_data": [
            {
                "field": f"rdf:type fpl:{tag}",
                "value": True,
                "source": "OWL-RL Inference Engine",
                "source_type": "inference",
                "rule": f"SPARQL rule for {tag}",
                "updated": now,
            }
            for tag in inferred_classes
        ],
        "calculated_data": [
            {
                "field": "points_per_game",
                "value": round(player.total_points / max(1, player.minutes / 90), 2) if player.minutes > 0 else 0,
                "source": "Calculated",
                "source_type": "derived",
                "formula": "total_points / (minutes / 90)",
                "updated": now,
            },
            {
                "field": "points_per_million",
                "value": round(player.total_points / player.price, 2) if player.price > 0 else 0,
                "source": "Calculated",
                "source_type": "derived",
                "formula": "total_points / price",
                "updated": now,
            },
        ],
        "rdf_triples_count": kg.triple_count,
        "kg_namespace": "http://fantasykg.org/data/",
        "player_uri": f"http://fantasykg.org/data/player/{player_id}",
    }
    
    return provenance


@router.get("/player/{player_id}/wikidata")
async def get_player_wikidata(player_id: int):
    """Fetch external data from Wikidata for a player.
    
    Links FPL player to Wikidata entity and retrieves:
    - Nationality / country of citizenship
    - Date of birth / age
    - Place of birth
    - Height
    - Position (from Wikidata)
    - National team
    - Image URL
    - Wikidata entity ID
    
    Uses Wikidata Search API first (fast), then SPARQL for details.
    """
    import httpx
    from services.fpl_service import fpl_service
    
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    # Get full name and web_name for matching
    full_name = f"{player.first_name} {player.second_name}"
    web_name = player.web_name
    
    wikidata_endpoint = "https://query.wikidata.org/sparql"
    wikidata_search_api = "https://www.wikidata.org/w/api.php"
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Step 1: Use Wikidata Search API (much faster than SPARQL text search)
            # Search with full name first (more specific), then web_name, then surname
            search_names = [full_name, web_name, player.second_name]
            wikidata_id = None
            matched_name = None
            
            def name_matches(result_label: str, search_term: str) -> bool:
                """Check if the Wikidata result label actually matches our search."""
                result_lower = result_label.lower()
                search_lower = search_term.lower()
                
                # Direct match or contains the search term
                if search_lower in result_lower:
                    return True
                
                # Check if surname matches (most important part)
                search_parts = search_lower.split()
                result_parts = result_lower.split()
                
                # The surname (last name) should match
                if search_parts and result_parts:
                    # Check if any significant part of the name matches
                    for search_part in search_parts:
                        if len(search_part) > 2:  # Skip short parts like "de", "van"
                            if any(search_part in rp or rp in search_part for rp in result_parts):
                                return True
                
                return False
            
            for search_name in search_names:
                if wikidata_id:
                    break
                    
                search_response = await client.get(
                    wikidata_search_api,
                    params={
                        "action": "wbsearchentities",
                        "search": search_name,
                        "language": "en",
                        "type": "item",
                        "limit": 10,  # Get more results to find best match
                        "format": "json",
                    },
                    headers={"User-Agent": "SmartPlayFPL/1.0 (Fantasy Football Assistant)"}
                )
                
                if search_response.status_code == 200:
                    search_data = search_response.json()
                    search_results = search_data.get("search", [])
                    
                    # Find a footballer whose name actually matches
                    for result in search_results:
                        desc = result.get("description", "").lower()
                        label = result.get("label", "")
                        
                        # Must be a footballer
                        is_footballer = any(kw in desc for kw in [
                            "football", "soccer", "midfielder", "forward", 
                            "defender", "goalkeeper", "winger", "striker"
                        ])
                        
                        if not is_footballer:
                            continue
                        
                        # The label (actual name) must match our search
                        # This prevents matching aliases like "Haaland of temu" for Højlund
                        if name_matches(label, search_name):
                            wikidata_id = result.get("id")
                            matched_name = label
                            break
            
            if not wikidata_id:
                return {
                    "player_id": player_id,
                    "player_name": player.web_name,
                    "full_name": full_name,
                    "found": False,
                    "searched_name": web_name,
                    "message": "No Wikidata entity found for this player",
                }
            
            # Step 2: Fetch detailed data using SPARQL (fast because we have the exact entity ID)
            detail_query = f"""
            SELECT ?personLabel ?countryLabel ?birthDate ?birthPlaceLabel ?height ?nationalTeamLabel ?image ?positionLabel
            WHERE {{
              BIND(wd:{wikidata_id} AS ?person)
              
              OPTIONAL {{ wd:{wikidata_id} wdt:P27 ?country . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P569 ?birthDate . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P19 ?birthPlace . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P2048 ?height . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P54 ?nationalTeam . ?nationalTeam wdt:P31 wd:Q6979593 . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P18 ?image . }}
              OPTIONAL {{ wd:{wikidata_id} wdt:P413 ?position . }}
              
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 1
            """
            
            response = await client.get(
                wikidata_endpoint,
                params={"query": detail_query, "format": "json"},
                headers={"User-Agent": "SmartPlayFPL/1.0 (Fantasy Football Assistant)"}
            )
            
            if response.status_code != 200:
                return {
                    "player_id": player_id,
                    "player_name": player.web_name,
                    "full_name": full_name,
                    "found": True,
                    "wikidata_id": wikidata_id,
                    "wikidata_url": f"https://www.wikidata.org/wiki/{wikidata_id}",
                    "error": f"Could not fetch details (status {response.status_code})",
                }
            
            data = response.json()
            results = data.get("results", {}).get("bindings", [])
            
            # Parse result (we already have wikidata_id from search)
            result = results[0] if results else {}
            
            # Calculate age from birth date
            birth_date = result.get("birthDate", {}).get("value", "")
            age = None
            if birth_date:
                try:
                    from datetime import datetime
                    birth = datetime.fromisoformat(birth_date.split("T")[0])
                    today = datetime.now()
                    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
                except Exception:
                    pass
            
            # Parse height (convert from meters if needed)
            height_raw = result.get("height", {}).get("value", "")
            height_cm = None
            if height_raw:
                try:
                    height_m = float(height_raw)
                    height_cm = int(height_m * 100) if height_m < 3 else int(height_m)
                except Exception:
                    pass
            
            # Flatten the response for easier frontend consumption
            return {
                "player_id": player_id,
                "player_name": player.web_name,
                "full_name": full_name,
                "found": True,  # Frontend checks this field
                "wikidata_id": wikidata_id,
                "wikidata_url": f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else None,
                "wikipedia_url": f"https://en.wikipedia.org/wiki/{full_name.replace(' ', '_')}" if wikidata_id else None,
                # Flattened fields for frontend
                "nationality": result.get("countryLabel", {}).get("value"),
                "birth_date": birth_date.split("T")[0] if birth_date else None,
                "age": age,
                "birth_place": result.get("birthPlaceLabel", {}).get("value"),
                "height": f"{height_cm} cm" if height_cm else None,
                "position": result.get("positionLabel", {}).get("value"),
                "national_team": result.get("nationalTeamLabel", {}).get("value"),
                "image": result.get("image", {}).get("value"),
            }
            
    except httpx.TimeoutException:
        return {
            "player_id": player_id,
            "player_name": player.web_name,
            "full_name": full_name,
            "found": False,
            "searched_name": web_name,
            "error": "Wikidata query timed out - try again",
        }
    except Exception as e:
        logger.error(f"Wikidata query failed: {e}")
        return {
            "player_id": player_id,
            "player_name": player.web_name,
            "full_name": full_name,
            "found": False,
            "searched_name": web_name,
            "error": str(e),
        }


@router.get("/player/{player_id}/injury-analysis")
async def get_injury_analysis(player_id: int):
    """Get detailed injury analysis for a player.
    
    Parses the FPL API `news` field to extract:
    - Injury type (hamstring, knee, calf, etc.)
    - Severity classification
    - Expected return date
    - Recurrence risk assessment (based on medical data)
    - Suspension information
    
    This demonstrates text-to-structured-data extraction from semi-structured news.
    """
    from services.fpl_service import fpl_service
    from services.news_parser import get_news_parser, InjuryType
    
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    parser = get_news_parser()
    parsed = parser.parse(
        news=player.news or "",
        status=player.status,
        chance_api=player.chance_of_playing_next_round
    )
    
    # Get detailed injury info if applicable
    injury_info = None
    if parsed.injury_type:
        injury_info = parser.get_injury_info(parsed.injury_type)
    
    # Build response
    response = {
        "player_id": player_id,
        "player_name": player.web_name,
        "team": player.team_name or f"Team {player.team}",
        
        # Raw data from FPL API
        "fpl_api_data": {
            "news": player.news,
            "status": player.status,
            "status_meaning": _get_status_meaning(player.status),
            "chance_of_playing_next_round": player.chance_of_playing_next_round,
        },
        
        # Parsed/extracted data
        "parsed": {
            "injury_type": parsed.injury_type.value if parsed.injury_type else None,
            "injury_type_display": _format_injury_type(parsed.injury_type),
            "severity": parsed.severity.value,
            "severity_display": _format_severity(parsed.severity),
            "chance_of_playing": parsed.chance_of_playing,
            "expected_return": parsed.expected_return,
            "is_suspension": parsed.is_suspension,
            "suspension_matches": parsed.suspension_matches,
            "is_illness": parsed.is_illness,
        },
        
        # Risk assessment
        "risk_assessment": {
            "recurrence_risk": parsed.recurrence_risk,
            "recurrence_risk_display": _format_risk_level(parsed.recurrence_risk),
            "risk_reason": parsed.risk_reason,
            "medical_info": injury_info,
        },
        
        # Recommendations
        "recommendations": _generate_recommendations(parsed, player),
        
        # For Knowledge Graph
        "rdf_potential": {
            "can_create_injury_event": parsed.severity != parsed.severity.FIT,
            "suggested_triples": _suggest_triples(player_id, parsed) if parsed.severity != parsed.severity.FIT else [],
        },
    }
    
    return response


def _get_status_meaning(status: str) -> str:
    """Convert status code to human-readable meaning."""
    meanings = {
        "a": "Available",
        "d": "Doubtful (75% chance)",
        "i": "Injured (25% chance or less)",
        "s": "Suspended",
        "u": "Unavailable",
        "n": "Not in squad",
    }
    return meanings.get(status, "Unknown")


def _format_injury_type(injury_type) -> Optional[str]:
    """Format injury type for display."""
    if injury_type is None:
        return None
    
    display_names = {
        "hamstring": "🦵 Hamstring",
        "knee": "🦿 Knee",
        "ankle": "🦶 Ankle",
        "calf": "🦵 Calf",
        "groin": "🩹 Groin",
        "muscle": "💪 Muscle",
        "back": "🔙 Back",
        "hip": "🦴 Hip",
        "thigh": "🦵 Thigh/Quad",
        "foot": "🦶 Foot",
        "shoulder": "💪 Shoulder",
        "head": "🤕 Head/Concussion",
        "illness": "🤒 Illness",
        "knock": "🤕 Knock",
        "unknown": "❓ Unknown",
    }
    return display_names.get(injury_type.value, injury_type.value.title())


def _format_severity(severity) -> str:
    """Format severity for display."""
    display = {
        "fit": "✅ Fit",
        "minor": "🟡 Minor",
        "doubtful": "🟠 Doubtful",
        "major": "🔴 Major",
        "out": "⛔ Out",
        "suspended": "🚫 Suspended",
    }
    return display.get(severity.value, severity.value.title())


def _format_risk_level(risk: Optional[str]) -> Optional[str]:
    """Format risk level for display."""
    if risk is None:
        return None
    display = {
        "high": "🔴 High Risk",
        "medium": "🟠 Medium Risk",
        "low": "🟢 Low Risk",
    }
    return display.get(risk, risk.title())


def _generate_recommendations(parsed, player) -> list:
    """Generate actionable recommendations based on injury analysis."""
    recommendations = []
    
    if parsed.severity.value == "fit":
        return [{"type": "positive", "text": "Player is fit and available. No concerns."}]
    
    if parsed.is_suspension:
        matches = parsed.suspension_matches or 1
        recommendations.append({
            "type": "warning",
            "text": f"Suspended for {matches} match{'es' if matches > 1 else ''}. Plan your transfers accordingly.",
        })
        return recommendations
    
    if parsed.recurrence_risk == "high":
        recommendations.append({
            "type": "danger",
            "text": f"⚠️ HIGH RECURRENCE RISK: {parsed.injury_type.value.title()} injuries have ~30% reinjury rate. Consider not captaining for 2-3 GWs after return.",
        })
    
    if parsed.severity.value == "out":
        recommendations.append({
            "type": "danger",
            "text": "Player is OUT. Consider transferring if you need the spot.",
        })
        if parsed.expected_return:
            recommendations.append({
                "type": "info",
                "text": f"Expected return: {parsed.expected_return}. Evaluate if worth holding.",
            })
    elif parsed.severity.value in ["major", "doubtful"]:
        recommendations.append({
            "type": "warning",
            "text": f"Player is doubtful ({parsed.chance_of_playing or '?'}% chance). Have a playing bench ready.",
        })
    elif parsed.severity.value == "minor":
        recommendations.append({
            "type": "info",
            "text": f"Minor concern ({parsed.chance_of_playing or 75}% chance). Likely to play but monitor news.",
        })
    
    if parsed.is_illness:
        recommendations.append({
            "type": "info",
            "text": "Illness - usually short-term. Check press conference for updates.",
        })
    
    return recommendations


def _suggest_triples(player_id: int, parsed) -> list:
    """Suggest RDF triples for the Knowledge Graph."""
    from datetime import datetime
    
    triples = []
    injury_uri = f"fpl:injury/{player_id}_{datetime.now().strftime('%Y%m%d')}"
    player_uri = f"fpl:player/{player_id}"
    
    triples.append({
        "subject": injury_uri,
        "predicate": "rdf:type",
        "object": "fpl:InjuryEvent",
    })
    triples.append({
        "subject": player_uri,
        "predicate": "fpl:hasInjury",
        "object": injury_uri,
    })
    
    if parsed.injury_type:
        triples.append({
            "subject": injury_uri,
            "predicate": "fpl:injuryType",
            "object": f'"{parsed.injury_type.value}"',
        })
    
    triples.append({
        "subject": injury_uri,
        "predicate": "fpl:severity",
        "object": f'"{parsed.severity.value}"',
    })
    
    if parsed.recurrence_risk:
        triples.append({
            "subject": injury_uri,
            "predicate": "fpl:recurrenceRisk",
            "object": f'"{parsed.recurrence_risk}"',
        })
    
    return triples


@router.get("/player/{player_id}/neighborhood")
async def get_player_neighborhood(player_id: int):
    """Get player's neighborhood graph for visualization.
    
    Returns nodes and links representing the player's immediate connections
    in the Knowledge Graph: team, position, Smart Tags, similar players.
    
    Designed for force-graph visualization (5-15 nodes).
    """
    from services.fpl_service import fpl_service
    
    kg = get_kg_service()
    
    player = fpl_service.get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    nodes = []
    links = []
    
    # Central node: the player
    player_node_id = f"player_{player_id}"
    nodes.append({
        "id": player_node_id,
        "label": player.web_name,
        "type": "player",
        "color": "#6366f1",  # Indigo
        "size": 20,
        "isCenter": True,
    })
    
    # Team node
    team_node_id = f"team_{player.team}"
    team_name = player.team_name or f"Team {player.team}"
    nodes.append({
        "id": team_node_id,
        "label": team_name,
        "type": "team",
        "color": "#10b981",  # Emerald
        "size": 14,
    })
    links.append({
        "source": player_node_id,
        "target": team_node_id,
        "label": "playsFor",
        "color": "#10b981",
    })
    
    # Position node
    position_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    position = position_map.get(player.element_type, "UNK")
    position_node_id = f"position_{position}"
    nodes.append({
        "id": position_node_id,
        "label": position,
        "type": "position",
        "color": "#f59e0b",  # Amber
        "size": 12,
    })
    links.append({
        "source": player_node_id,
        "target": position_node_id,
        "label": "hasPosition",
        "color": "#f59e0b",
    })
    
    # Price tier node
    price = player.now_cost / 10
    if price >= 10:
        price_tier = "Premium (£10m+)"
        price_color = "#ef4444"  # Red
    elif price >= 7:
        price_tier = "Mid-Range (£7-10m)"
        price_color = "#f97316"  # Orange
    else:
        price_tier = "Budget (<£7m)"
        price_color = "#22c55e"  # Green
    
    price_node_id = f"price_{price_tier.split()[0].lower()}"
    nodes.append({
        "id": price_node_id,
        "label": f"£{price:.1f}m",
        "type": "price",
        "color": price_color,
        "size": 10,
    })
    links.append({
        "source": player_node_id,
        "target": price_node_id,
        "label": "costs",
        "color": price_color,
    })
    
    # Smart Tags (inferred classes)
    inferred_classes = kg.get_all_inferred_classes_for_player(player_id)
    
    tag_colors = {
        "CaptainCandidate": "#eab308",    # Yellow
        "TransferTarget": "#22c55e",       # Green
        "DifferentialPick": "#a855f7",     # Purple
        "RotationRisk": "#f97316",         # Orange
        "ValuePick": "#3b82f6",            # Blue
        "PremiumAsset": "#fbbf24",         # Amber
        "InjuryConcern": "#ef4444",        # Red
        "FormDifferential": "#6366f1",     # Indigo
        "MustBuy": "#10b981",              # Emerald
        "SellUrgent": "#dc2626",           # Red-600
        "HighRecurrenceRisk": "#f97316",   # Orange
        "RecentlyReturned": "#06b6d4",     # Cyan
    }
    
    tag_icons = {
        "CaptainCandidate": "👑",
        "TransferTarget": "🎯",
        "DifferentialPick": "💎",
        "RotationRisk": "🔄",
        "ValuePick": "📈",
        "PremiumAsset": "⭐",
        "InjuryConcern": "🏥",
        "FormDifferential": "📊",
        "MustBuy": "✅",
        "SellUrgent": "🚨",
        "HighRecurrenceRisk": "⚠️",
        "RecentlyReturned": "🔄",
    }
    
    for tag in inferred_classes[:4]:  # Limit to 4 tags
        tag_node_id = f"tag_{tag}"
        icon = tag_icons.get(tag, "🏷️")
        nodes.append({
            "id": tag_node_id,
            "label": f"{icon} {tag}",
            "type": "tag",
            "color": tag_colors.get(tag, "#6b7280"),
            "size": 11,
        })
        links.append({
            "source": player_node_id,
            "target": tag_node_id,
            "label": "hasTag",
            "color": tag_colors.get(tag, "#6b7280"),
        })
    
    # Ownership tier node
    try:
        ownership = float(player.selected_by_percent)
        if ownership >= 25:
            ownership_tier = "Template"
            ownership_color = "#ef4444"  # Red
        elif ownership >= 10:
            ownership_tier = "Popular"
            ownership_color = "#f97316"  # Orange
        else:
            ownership_tier = "Differential"
            ownership_color = "#a855f7"  # Purple
    except Exception:
        ownership_tier = "Unknown"
        ownership_color = "#6b7280"
    
    ownership_node_id = "ownership_tier"
    nodes.append({
        "id": ownership_node_id,
        "label": f"📊 {ownership_tier} ({ownership:.0f}%)" if ownership else ownership_tier,
        "type": "ownership",
        "color": ownership_color,
        "size": 10,
    })
    links.append({
        "source": player_node_id,
        "target": ownership_node_id,
        "label": "hasOwnership",
        "color": ownership_color,
    })
    
    # Form indicator node
    try:
        form = float(player.form)
        if form >= 7:
            form_label = f"🔥 Hot ({form:.1f})"
            form_color = "#ef4444"
        elif form >= 4:
            form_label = f"📊 Good ({form:.1f})"
            form_color = "#f59e0b"
        else:
            form_label = f"❄️ Cold ({form:.1f})"
            form_color = "#3b82f6"
    except Exception:
        form_label = "📊 Form"
        form_color = "#6b7280"
    
    form_node_id = "form_indicator"
    nodes.append({
        "id": form_node_id,
        "label": form_label,
        "type": "stat",
        "color": form_color,
        "size": 10,
    })
    links.append({
        "source": player_node_id,
        "target": form_node_id,
        "label": "hasForm",
        "color": form_color,
    })
    
    return {
        "player_id": player_id,
        "player_name": player.web_name,
        "nodes": nodes,
        "links": links,
        "node_count": len(nodes),
        "link_count": len(links),
    }


# ============== SmartPlay Score Integration ==============

@router.post("/sync-smartplay-scores")
async def sync_smartplay_scores():
    """Sync SmartPlay scores from database to Knowledge Graph.

    Loads all ML scores from the database and persists them as RDF entities
    in the Knowledge Graph, enabling SmartPlay-based inference rules.
    """
    from database import SessionLocal, MLPlayerScore

    kg = await ensure_kg_ready()

    db = SessionLocal()
    try:
        # Get latest gameweek scores
        latest = db.query(MLPlayerScore).order_by(
            MLPlayerScore.calculated_at.desc()
        ).first()

        if not latest:
            return {
                "success": False,
                "message": "No ML scores in database. Run /api/predictor/calculate first.",
                "scores_synced": 0
            }

        # Get all scores for latest gameweek
        all_scores = db.query(MLPlayerScore).filter(
            MLPlayerScore.gameweek == latest.gameweek
        ).all()

        scores_dict = {}
        for score in all_scores:
            scores_dict[score.player_id] = {
                'final_score': float(score.final_score),
                'nailedness_score': float(score.nailedness_score),
                'form_xg_score': float(score.form_xg_score),
                'form_pts_score': float(score.form_pts_score),
                'fixture_score': float(score.fixture_score),
            }

        # Add to KG
        count = kg.add_smartplay_scores_batch(scores_dict, latest.gameweek)

        # Re-run inference with new scores
        inferred_count = kg._run_inference()
        kg._query_cache.clear()

        return {
            "success": True,
            "message": f"Synced {count} SmartPlay scores and re-ran inference",
            "gameweek": latest.gameweek,
            "scores_synced": count,
            "inferred_facts": inferred_count,
        }

    finally:
        db.close()


@router.post("/sync-injuries")
async def sync_injuries():
    """Sync injury events from player news to Knowledge Graph.

    Parses the news field for all players with news and creates
    InjuryEvent entities in the graph for injured/suspended players.
    """
    kg = await ensure_kg_ready()

    count = kg.sync_injuries_from_players()

    # Re-run inference to update HighRecurrenceRisk and RecentlyReturned tags
    inferred_count = kg._run_inference()
    kg._query_cache.clear()

    return {
        "success": True,
        "message": f"Synced {count} injury events and re-ran inference",
        "injuries_synced": count,
        "inferred_facts": inferred_count,
    }


@router.post("/validate-squad")
async def validate_squad(player_ids: list[int]):
    """Validate a squad of 15 players against FPL rules.

    Checks:
    - Squad size (15 players)
    - Budget (£100m max)
    - Position counts (2 GKP, 5 DEF, 5 MID, 3 FWD)
    - Team limit (max 3 from any team)
    - Player availability (warnings for injured players)
    - Smart Tag warnings (rotation risk, injury risk)

    Request body:
        player_ids: List of 15 FPL player IDs

    Returns:
        valid: bool - whether squad passes all hard constraints
        violations: list - hard constraint violations
        warnings: list - soft constraint warnings
        squad_info: dict - squad composition summary
    """
    kg = await ensure_kg_ready()

    if len(player_ids) != 15:
        return {
            "valid": False,
            "violations": [{
                "type": "SquadSize",
                "message": f"Must provide exactly 15 player IDs, got {len(player_ids)}"
            }],
            "warnings": [],
            "squad_info": {"provided_count": len(player_ids)}
        }

    result = kg.validate_squad(player_ids)
    return result


@router.get("/player/{player_id}/smartplay-score")
async def get_player_smartplay_score(player_id: int):
    """Get SmartPlay score for a player from the Knowledge Graph.

    Returns the 5 component scores if available:
    - final_score: Overall composite score (0-10)
    - nailedness_score: How reliably the player starts
    - form_xg_score: Form based on xG/xA
    - form_pts_score: Form based on actual points
    - fixture_score: Upcoming fixture difficulty

    Note: Scores must be synced first via /kg/sync-smartplay-scores
    """
    kg = await ensure_kg_ready()

    score = kg.get_player_smartplay_score(player_id)

    if score:
        return {
            "player_id": player_id,
            "found": True,
            "scores": score,
            "source": "knowledge_graph"
        }
    else:
        # Fall back to database
        from database import SessionLocal, MLPlayerScore

        db = SessionLocal()
        try:
            db_score = db.query(MLPlayerScore).filter(
                MLPlayerScore.player_id == player_id
            ).order_by(MLPlayerScore.calculated_at.desc()).first()

            if db_score:
                return {
                    "player_id": player_id,
                    "found": True,
                    "scores": {
                        'final_score': float(db_score.final_score),
                        'nailedness_score': float(db_score.nailedness_score),
                        'form_xg_score': float(db_score.form_xg_score),
                        'form_pts_score': float(db_score.form_pts_score),
                        'fixture_score': float(db_score.fixture_score),
                    },
                    "source": "database",
                    "note": "Score found in database but not yet synced to KG"
                }
        finally:
            db.close()

        return {
            "player_id": player_id,
            "found": False,
            "message": "No SmartPlay score found. Run /api/predictor/calculate first."
        }

