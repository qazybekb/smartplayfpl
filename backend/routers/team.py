"""Team analysis router."""

import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter for AI endpoints (more restrictive than global limit)
limiter = Limiter(key_func=get_remote_address)

from models import (
    TeamAnalysisResponse, SquadData, PlayerSummary, Gameweek,
    RivalIntelligenceResponse, LeagueStanding, RivalInsightCard, PlayerInsight,
    PlayerPlannerResponse, PlayerPlannerEntry, FixtureInfo,
    CrowdInsightsResponse,
    CrowdIntelligenceResponse, CrowdIntelligenceCard, CrowdPlayer,
    GWReviewResponse, GWInsight,
    TransferSuggestionsResponse, TransferSuggestion, TransferPlayerOut, TransferPlayerIn, TransferAlternative,
    AlertsResponse, Alert,
    LineupResponse, LineupPlayer, BenchPlayer, CaptainPick, ViceCaptainPick,
    LineupStrategiesResponse, FormationStrategy,
    ChipAdviceResponse, ChipRecommendation,
    DecisionQualityResponse,
    SquadAnalysisResponse,
)
from services.fpl_service import fpl_service
from services.crowd_insights_service import CrowdInsightsService
from services.transfer_workflow_service import TransferWorkflowService
from services.decision_quality_service import decision_quality_service
from services.claude_service import claude_service
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["team"])

# Constants
TOTAL_FPL_MANAGERS = 11_000_000


@router.get("/team/{team_id}", response_model=TeamAnalysisResponse)
async def get_team_analysis(team_id: int):
    """
    Get full team analysis for a manager.
    
    This is the main endpoint that powers the Team Analysis page.
    """
    try:
        # Fetch manager info
        manager = await fpl_service.get_manager_info(team_id)

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Try to fetch picks for current gameweek, fallback to manager's last played GW
        # This handles the case where the deadline for next GW hasn't passed yet
        # and picks don't exist for the upcoming gameweek
        picks_gw = current_gw.id
        try:
            picks = await fpl_service.get_manager_picks(team_id, picks_gw)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and manager.current_event:
                # Picks don't exist for next GW, use last played GW
                picks_gw = manager.current_event
                picks = await fpl_service.get_manager_picks(team_id, picks_gw)
            else:
                raise
        
        # Fetch manager's history to get bank/value
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        
        # Fetch leagues
        leagues = await fpl_service.get_manager_leagues(team_id)

        # Fetch live GW points for all players (use the same GW as picks)
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)
        
        # Build squad data
        starting = []
        bench = []
        captain_id = 0
        vice_captain_id = 0
        
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue
            
            # Get GW points from live data
            gw_pts = gw_points_map.get(player.id, 0)
            
            player_summary = PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            )
            
            if pick.is_captain:
                captain_id = player.id
            if pick.is_vice_captain:
                vice_captain_id = player.id
            
            if pick.position <= 11:
                starting.append(player_summary)
            else:
                bench.append(player_summary)
        
        squad = SquadData(
            starting=starting,
            bench=bench,
            captain_id=captain_id,
            vice_captain_id=vice_captain_id,
        )
        
        # Calculate team value and bank
        team_value = (latest_history.value / 10) if latest_history else 100.0
        bank = (latest_history.bank / 10) if latest_history else 0.0

        # Get the gameweek object that matches the picks (GW15 if fallback was used)
        display_gw = fpl_service.get_gameweek_by_id(picks_gw) or current_gw

        return TeamAnalysisResponse(
            manager=manager,
            gameweek=display_gw,
            squad=squad,
            team_value=team_value,
            bank=bank,
            free_transfers=1,  # Default, could be fetched from transfers endpoint
            gw_rank=manager.summary_event_rank,
            overall_rank=manager.summary_overall_rank,
            leagues=leagues,
        )
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
        logger.error(f"FPL API error: {e}")
        raise HTTPException(status_code=502, detail="Error fetching data from FPL API")
    except Exception as e:
        logger.error(f"Error analyzing team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players")
async def get_players(limit: int = 0):
    """Get all players with full stats for faceted search.
    
    Args:
        limit: Max players to return. 0 = all players.
    """
    players = fpl_service.get_all_players()
    
    # Apply limit if specified
    if limit > 0:
        players = players[:limit]
    
    return {
        "players": [
            {
                "id": p.id,
                "name": f"{p.first_name} {p.second_name}",
                "webName": p.web_name,
                "team": {
                    "id": p.team,
                    "name": fpl_service.get_team(p.team).name if fpl_service.get_team(p.team) else p.team_name,
                    "shortName": p.team_name or "",
                },
                "teamId": p.team,
                "position": p.position or "???",
                "price": p.price,
                "form": p.form_float,
                "totalPoints": p.total_points,
                "pointsPerGame": round(p.total_points / max(1, p.minutes / 90), 2) if p.minutes > 0 else 0,
                "ownership": p.ownership,
                "status": p.status,
                "chanceOfPlaying": p.chance_of_playing_next_round,
                "news": p.news or "",
                "xG": float(p.expected_goals) if p.expected_goals else 0,
                "xA": float(p.expected_assists) if p.expected_assists else 0,
                "goals": p.goals_scored,
                "assists": p.assists,
                "cleanSheets": p.clean_sheets,
                "minutes": p.minutes,
                "bonus": p.bonus,
                "ictIndex": float(p.ict_index) if p.ict_index else 0,
                "netTransfersGW": p.transfers_in_event - p.transfers_out_event,
            }
            for p in players
        ],
        "count": len(players),
    }


@router.get("/gameweek/current")
async def get_current_gameweek():
    """Get current gameweek info."""
    gw = fpl_service.get_current_gameweek()
    if not gw:
        raise HTTPException(status_code=500, detail="Could not determine current gameweek")
    return gw


@router.get("/rivals/{team_id}", response_model=RivalIntelligenceResponse)
async def get_rival_intelligence(team_id: int, max_rivals: int = 20):
    """
    Get rival intelligence for a manager.

    Analyzes the user's squad vs their mini-league rivals.
    """
    try:
        # Get manager info and leagues
        manager = await fpl_service.get_manager_info(team_id)
        leagues = await fpl_service.get_manager_leagues(team_id)

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get user's picks with fallback to last played GW
        user_picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        user_player_ids = {p.element for p in user_picks}
        
        # Build league standings
        league_standings: list[LeagueStanding] = []
        all_rival_ids: set[int] = set()
        
        for league in leagues[:3]:  # Limit to top 3 leagues
            try:
                standings = await fpl_service.get_league_standings(league.id, limit=20)
                
                # Find user's position and get rivals
                for entry in standings:
                    if entry["entry"] != team_id:
                        all_rival_ids.add(entry["entry"])
                
                league_standings.append(LeagueStanding(
                    league_id=league.id,
                    league_name=league.name,
                    rank=league.entry_rank or 0,
                    total_entries=None,
                ))
            except Exception as e:
                logger.warning(f"Failed to fetch standings for league {league.id}: {e}")
                continue
        
        # Limit rivals
        rival_ids = list(all_rival_ids)[:max_rivals]

        # Fetch rival picks using the same GW as user picks
        rival_picks = await fpl_service.get_rival_picks(rival_ids, picks_gw)
        total_rivals = len(rival_picks)
        
        # Count how many rivals have each player
        player_rival_count: dict[int, int] = {}
        for rival_id, picks in rival_picks.items():
            for player_id in picks:
                player_rival_count[player_id] = player_rival_count.get(player_id, 0) + 1
        
        # Build insights
        insights: list[RivalInsightCard] = []
        
        # 1. Shared Picks - Players you AND rivals have (high overlap)
        shared_picks = []
        for player_id in user_player_ids:
            count = player_rival_count.get(player_id, 0)
            if count >= total_rivals * 0.3:  # At least 30% of rivals have this player
                player = fpl_service.get_player(player_id)
                if player:
                    shared_picks.append(PlayerInsight(
                        id=player.id,
                        name=player.web_name,
                        team=player.team_name or "",
                        ownership=player.ownership,
                        form=player.form_float,
                    ))
        shared_picks.sort(key=lambda p: -p.ownership)
        insights.append(RivalInsightCard(
            title="Shared Picks",
            icon="🤝",
            you_have=True,
            description="Both you & rivals own",
            players=shared_picks[:5],
        ))
        
        # 2. Form Leaders - Rivals' hot picks you don't have (form 6+)
        form_leaders = []
        for player_id, count in player_rival_count.items():
            if player_id not in user_player_ids and count >= 2:
                player = fpl_service.get_player(player_id)
                if player and player.form_float >= 6.0:
                    form_leaders.append(PlayerInsight(
                        id=player.id,
                        name=player.web_name,
                        team=player.team_name or "",
                        ownership=player.ownership,
                        form=player.form_float,
                    ))
        form_leaders.sort(key=lambda p: -p.form)
        
        if form_leaders:
            insights.append(RivalInsightCard(
                title="Form Leaders",
                icon="🔥",
                you_have=False,
                description="Rivals' hot picks (form 6+)",
                players=form_leaders[:5],
            ))
        else:
            insights.append(RivalInsightCard(
                title="Form Leaders",
                icon="🔥",
                you_have=False,
                description="Rivals' hot picks (form 6+)",
                players=[],
            ))
        
        # 3. Your Edge - Players you have that rivals don't
        your_edge = []
        for player_id in user_player_ids:
            count = player_rival_count.get(player_id, 0)
            if count <= total_rivals * 0.1:  # Less than 10% of rivals have this
                player = fpl_service.get_player(player_id)
                if player and player.form_float >= 4.0:
                    your_edge.append(PlayerInsight(
                        id=player.id,
                        name=player.web_name,
                        team=player.team_name or "",
                        ownership=player.ownership,
                        form=player.form_float,
                    ))
        your_edge.sort(key=lambda p: -p.form)
        insights.append(RivalInsightCard(
            title="Your Edge",
            icon="🎯",
            you_have=True,
            description="Rivals don't have these",
            players=your_edge[:5],
        ))
        
        # 4. Hidden Gems - Low-owned, high form players you're missing
        hidden_gems = []
        all_players = fpl_service.get_all_players()
        for player in all_players:
            if (player.id not in user_player_ids and 
                player.ownership < 10 and 
                player.form_float >= 5.0):
                hidden_gems.append(PlayerInsight(
                    id=player.id,
                    name=player.web_name,
                    team=player.team_name or "",
                    ownership=player.ownership,
                    form=player.form_float,
                ))
        hidden_gems.sort(key=lambda p: -p.form)
        insights.append(RivalInsightCard(
            title="Hidden Gems",
            icon="💎",
            you_have=False,
            description="<10% owned, form 5+",
            players=hidden_gems[:5],
        ))
        
        # 5. Rising Picks - Your players being transferred in
        rising_picks = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.transfers_in_event > 30000:
                rising_picks.append(PlayerInsight(
                    id=player.id,
                    name=player.web_name,
                    team=player.team_name or "",
                    ownership=player.ownership,
                    form=player.form_float,
                    transfers_in=player.transfers_in_event,
                ))
        rising_picks.sort(key=lambda p: -p.transfers_in)
        insights.append(RivalInsightCard(
            title="Rising Picks",
            icon="📈",
            you_have=True,
            description="Your picks being bought",
            players=rising_picks[:5],
        ))
        
        # 6. Being Sold - Your players being transferred out
        being_sold = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.transfers_out_event > 30000:
                being_sold.append(PlayerInsight(
                    id=player.id,
                    name=player.web_name,
                    team=player.team_name or "",
                    ownership=player.ownership,
                    form=player.form_float,
                    transfers_out=player.transfers_out_event,
                ))
        being_sold.sort(key=lambda p: -p.transfers_out)
        insights.append(RivalInsightCard(
            title="Being Sold",
            icon="📉",
            you_have=True,
            description="Your picks being sold",
            players=being_sold[:5],
        ))
        
        # 7. Rival Traps - Rivals' bad picks you AVOIDED (form < 4)
        # you_have=False here means "DON'T HAVE" which is GOOD - you avoided them!
        rival_traps = []
        for player_id, count in player_rival_count.items():
            if player_id not in user_player_ids and count >= 3:
                player = fpl_service.get_player(player_id)
                if player and player.form_float < 4.0:
                    rival_traps.append(PlayerInsight(
                        id=player.id,
                        name=player.web_name,
                        team=player.team_name or "",
                        ownership=player.ownership,
                        form=player.form_float,
                    ))
        rival_traps.sort(key=lambda p: p.form)
        insights.append(RivalInsightCard(
            title="Rival Traps",
            icon="🚫",
            you_have=False,  # DON'T HAVE = good, you avoided these!
            description="Rivals' bad picks (form <4)",
            players=rival_traps[:5],
        ))
        
        # 8. Low-Own Punts - Your low-owned performers
        low_own_punts = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.ownership < 15 and player.form_float >= 4.0:
                low_own_punts.append(PlayerInsight(
                    id=player.id,
                    name=player.web_name,
                    team=player.team_name or "",
                    ownership=player.ownership,
                    form=player.form_float,
                ))
        low_own_punts.sort(key=lambda p: -p.form)
        insights.append(RivalInsightCard(
            title="Low-Own Punts",
            icon="🎲",
            you_have=True,
            description="<15% owned, form 4+",
            players=low_own_punts[:5],
        ))
        
        # Calculate differential score
        template_count = len(shared_picks)
        differential_count = len(your_edge) + len(low_own_punts)
        
        if template_count > differential_count:
            strategy = "Very template squad. Need differentials to climb ranks."
        elif differential_count > template_count * 2:
            strategy = "High-risk differential squad. Could swing big either way."
        else:
            strategy = "Good balance of template and differentials."
        
        # Calculate percentile
        gw_rank = manager.summary_event_rank
        percentile = None
        if gw_rank:
            percentile = min(100, max(1, int((gw_rank / TOTAL_FPL_MANAGERS) * 100)))
        
        return RivalIntelligenceResponse(
            gw_rank=gw_rank,
            overall_rank=manager.summary_overall_rank,
            gw_rank_percentile=percentile,
            leagues=league_standings,
            total_rivals=total_rivals,
            insights=insights,
            strategy=strategy,
        )
        
    except Exception as e:
        logger.error(f"Error getting rival intelligence for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crowd-intelligence/{team_id}", response_model=CrowdIntelligenceResponse)
async def get_crowd_intelligence(team_id: int):
    """
    Get crowd intelligence for a manager - comparing their squad vs the global FPL crowd.

    Shows 8 cards split into:
    - You Have: Shared Picks, Your Edge, Rising, Being Sold
    - You Don't Have: Template Misses, Hidden Gems, Bandwagons, Form Leaders
    """
    try:
        await fpl_service.initialize()

        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get user's picks with fallback to last played GW
        user_picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        user_player_ids = {p.element for p in user_picks}

        # Get all players
        all_players = fpl_service.get_all_players()

        def to_crowd_player(player) -> CrowdPlayer:
            return CrowdPlayer(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                ownership=player.ownership,
                form=player.form_float,
                transfers_in=player.transfers_in_event,
                transfers_out=player.transfers_out_event,
            )

        # ========== YOU HAVE ==========

        # 1. Shared Picks - Template players you have (30%+ owned)
        shared_picks = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.ownership >= 30:
                shared_picks.append(to_crowd_player(player))
        shared_picks.sort(key=lambda p: -p.ownership)

        # 2. Your Edge - Differentials you have (<10% owned)
        your_edge = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.ownership < 10:
                your_edge.append(to_crowd_player(player))
        your_edge.sort(key=lambda p: -p.form)

        # 3. Rising - Your players being transferred IN
        rising = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.transfers_in_event > 30000:
                rising.append(to_crowd_player(player))
        rising.sort(key=lambda p: -p.transfers_in)

        # 4. Being Sold - Your players being transferred OUT
        being_sold = []
        for player_id in user_player_ids:
            player = fpl_service.get_player(player_id)
            if player and player.transfers_out_event > 30000:
                being_sold.append(to_crowd_player(player))
        being_sold.sort(key=lambda p: -p.transfers_out)

        # ========== YOU DON'T HAVE ==========

        # 5. Template Misses - High-owned players you're missing (20%+, form 3+)
        template_misses = []
        for player in all_players:
            if (player.id not in user_player_ids and
                player.ownership >= 20 and
                player.form_float >= 3.0 and
                player.status == 'a'):
                template_misses.append(to_crowd_player(player))
        template_misses.sort(key=lambda p: -p.ownership)

        # 6. Hidden Gems - Low-owned hot players (<10%, form 5+)
        hidden_gems = []
        for player in all_players:
            if (player.id not in user_player_ids and
                player.ownership < 10 and
                player.form_float >= 5.0 and
                player.status == 'a'):
                hidden_gems.append(to_crowd_player(player))
        hidden_gems.sort(key=lambda p: -p.form)

        # 7. Bandwagons - Being heavily transferred in (50k+)
        bandwagons = []
        for player in all_players:
            if (player.id not in user_player_ids and
                player.transfers_in_event > 50000 and
                player.status == 'a'):
                bandwagons.append(to_crowd_player(player))
        bandwagons.sort(key=lambda p: -p.transfers_in)

        # 8. Form Leaders - Top form players available (form 6+)
        form_leaders = []
        for player in all_players:
            if (player.id not in user_player_ids and
                player.form_float >= 6.0 and
                player.status == 'a'):
                form_leaders.append(to_crowd_player(player))
        form_leaders.sort(key=lambda p: -p.form)

        # Calculate differential percentage
        total_ownership = sum(
            fpl_service.get_player(pid).ownership
            for pid in user_player_ids
            if fpl_service.get_player(pid)
        )
        avg_ownership = total_ownership / len(user_player_ids) if user_player_ids else 0
        differential_pct = max(0, min(100, int(100 - avg_ownership)))

        return CrowdIntelligenceResponse(
            differential_percentage=differential_pct,
            shared_picks=CrowdIntelligenceCard(
                title="Shared Picks",
                subtitle="Template · 30%+ owned",
                players=shared_picks[:3],
            ),
            your_edge=CrowdIntelligenceCard(
                title="Your Edge",
                subtitle="Differentials · <10%",
                players=your_edge[:3],
            ),
            rising=CrowdIntelligenceCard(
                title="Rising",
                subtitle="Transfers IN",
                players=rising[:3],
            ),
            being_sold=CrowdIntelligenceCard(
                title="Being Sold",
                subtitle="Transfers OUT",
                players=being_sold[:3],
            ),
            template_misses=CrowdIntelligenceCard(
                title="Template Misses",
                subtitle="20%+ owned · form 3+ · available",
                players=template_misses[:3],
            ),
            hidden_gems=CrowdIntelligenceCard(
                title="Hidden Gems",
                subtitle="<10% owned · form 5+ · available",
                players=hidden_gems[:3],
            ),
            bandwagons=CrowdIntelligenceCard(
                title="Bandwagons",
                subtitle="+50k transfers · available",
                players=bandwagons[:3],
            ),
            form_leaders=CrowdIntelligenceCard(
                title="Form Leaders",
                subtitle="Form 6+ · available",
                players=form_leaders[:3],
            ),
        )

    except Exception as e:
        logger.error(f"Error getting crowd intelligence for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/planner/{team_id}", response_model=PlayerPlannerResponse)
async def get_player_planner(team_id: int, num_gameweeks: int = 5):
    """
    Get player planner data for a manager's squad.
    
    Shows each player with their upcoming fixtures and key stats.
    """
    try:
        # Ensure data is loaded
        await fpl_service.initialize()
        
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")
        
        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Build player entries
        players: list[PlayerPlannerEntry] = []
        
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue
            
            # Get fixtures for this player's team
            fixtures_data = await fpl_service.get_player_fixtures(player.id, num_gameweeks)
            fixtures = [
                FixtureInfo(
                    gameweek=f["gameweek"],
                    opponent=f["opponent"],
                    is_home=f["is_home"],
                    difficulty=f["difficulty"],
                )
                for f in fixtures_data
            ]
            
            players.append(PlayerPlannerEntry(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                ownership=player.ownership,
                transfers_in=player.transfers_in_event,
                transfers_out=player.transfers_out_event,
                fixtures=fixtures,
            ))
        
        # Sort by position: GKP, DEF, MID, FWD
        position_order = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}
        players.sort(key=lambda p: (position_order.get(p.position, 99), -p.points))
        
        return PlayerPlannerResponse(
            current_gameweek=current_gw.id,
            players=players,
        )
        
    except Exception as e:
        logger.error(f"Error getting player planner for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fixtures/players-fdr")
async def get_players_fdr(player_ids: str, gameweeks: int = 5):
    """Get FDR (Fixture Difficulty Rating) for multiple players.
    
    Args:
        player_ids: Comma-separated list of player IDs
        gameweeks: Number of upcoming gameweeks to analyze (default: 5)
    
    Returns:
        List of players with their fixtures and average difficulty
    """
    try:
        # Parse player IDs
        ids = [int(x.strip()) for x in player_ids.split(",") if x.strip()]
        
        if not ids:
            return {"playersFDR": []}
        
        results = []
        
        for player_id in ids:
            player = fpl_service.get_player(player_id)
            if not player:
                continue
            
            # Get fixtures for this player
            fixtures_data = await fpl_service.get_player_fixtures(player_id, gameweeks)
            
            if not fixtures_data:
                continue
            
            # Calculate average difficulty
            difficulties = [f["difficulty"] for f in fixtures_data]
            avg_difficulty = sum(difficulties) / len(difficulties) if difficulties else 3.0
            
            results.append({
                "playerId": player_id,
                "playerName": player.web_name,
                "teamShort": player.team_name or "",
                "fixtures": [
                    {
                        "gameweek": f["gameweek"],
                        "opponent": f["opponent"],
                        "isHome": f["is_home"],
                        "difficulty": f["difficulty"],
                    }
                    for f in fixtures_data
                ],
                "avgDifficulty": round(avg_difficulty, 2),
            })
        
        return {"playersFDR": results}
        
    except Exception as e:
        logger.error(f"Error getting players FDR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """Get API status and last update time."""
    import datetime
    return {
        "status": "ok",
        "last_updated": datetime.datetime.now().isoformat(),
        "players_count": len(fpl_service.get_all_players()),
        "teams_count": len(fpl_service.get_all_teams()),
    }


@router.get("/crowd-insights/{team_id}", response_model=CrowdInsightsResponse)
async def get_crowd_insights(team_id: int):
    """
    Get crowd insights for a manager.

    Analyzes market movements, transfer trends, and provides insights like:
    - Smart Money Alert: Low ownership players gaining transfers
    - Under-the-Radar Gems: Budget players with excellent form
    - Bandwagon Watch: Massive transfer activity
    - Panic Sell Analysis: Players being dumped
    - Quick Hit: Squad players worth captaining
    - Your Edge: Your differential picks that are performing well
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        squad_player_ids = [p.element for p in picks]

        # Initialize crowd insights service and get insights
        crowd_service = CrowdInsightsService(fpl_service)
        insights = await crowd_service.get_crowd_insights(team_id, squad_player_ids)

        return insights

    except Exception as e:
        logger.error(f"Error getting crowd insights for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crowd-insights-ai/{team_id}", response_model=CrowdInsightsResponse)
@limiter.limit("10/minute")
async def get_crowd_insights_ai(request: Request, team_id: int):
    """
    Get AI-enhanced crowd insights for a manager.

    Uses Claude AI to generate personalized, context-aware insights based on:
    - The manager's current squad
    - Market movements and transfer trends
    - Player form and ownership data

    Returns the same format as /crowd-insights but with AI-generated descriptions.
    """
    try:
        # Check if Claude is available
        if not claude_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI service not available. Please configure ANTHROPIC_API_KEY."
            )

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        squad_player_ids = [p.element for p in picks]

        # Get base insights first
        crowd_service = CrowdInsightsService(fpl_service)
        base_insights = await crowd_service.get_crowd_insights(team_id, squad_player_ids)

        # Build all players data dict for Claude context
        all_players = fpl_service.get_all_players()
        teams_list = fpl_service.get_all_teams()
        team_names = {t.id: t.short_name for t in teams_list}

        all_players_data = {}
        for p in all_players:
            all_players_data[p.id] = {
                "id": p.id,
                "name": p.web_name,
                "team": team_names.get(p.team, "???"),
                "price": p.price,
                "form": p.form_float,
                "ownership": p.ownership,
                "transfers_in": p.transfers_in_event,
                "transfers_out": p.transfers_out_event,
                "in_squad": p.id in squad_player_ids,
            }

        # Generate AI-enhanced insights
        ai_insights = await claude_service.generate_crowd_insights(
            base_insights=base_insights,
            squad_player_ids=squad_player_ids,
            all_players_data=all_players_data,
        )

        return ai_insights

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI crowd insights for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gw-review/{team_id}", response_model=GWReviewResponse)
async def get_gw_review(team_id: int):
    """
    Get AI-generated review of last gameweek performance.

    Analyzes captain choice, bench points, top performers, and underperformers.
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager info
        manager = await fpl_service.get_manager_info(team_id)

        # Try to fetch picks for current gameweek, fallback to manager's last played GW
        picks_gw = current_gw.id
        try:
            picks = await fpl_service.get_manager_picks(team_id, picks_gw)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and manager.current_event:
                picks_gw = manager.current_event
                picks = await fpl_service.get_manager_picks(team_id, picks_gw)
            else:
                raise

        # Get live GW points
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)

        # Get manager history to find bench points
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        bench_points = latest_history.points_on_bench if latest_history else 0

        # Build squad data
        squad = []
        captain_id = 0

        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

            if pick.is_captain:
                captain_id = player.id

        # Initialize service and get review
        workflow_service = TransferWorkflowService(fpl_service)
        review = await workflow_service.get_gw_review(
            team_id=team_id,
            squad=squad,
            gw_points=manager.summary_event_points or 0,
            gw_rank=manager.summary_event_rank,
            captain_id=captain_id,
            bench_points=bench_points,
        )

        # Get GW stats for comparison
        gw_average = current_gw.average_entry_score
        gw_highest = current_gw.highest_score

        # Calculate rank percentile (approx 11M players)
        rank_percentile = None
        if manager.summary_event_rank:
            total_players = 11000000  # Approximate total FPL players
            rank_percentile = round((manager.summary_event_rank / total_players) * 100, 1)

        return GWReviewResponse(
            gw_points=review["gw_points"],
            gw_rank=review["gw_rank"],
            gw_average=gw_average,
            gw_highest=gw_highest,
            rank_percentile=rank_percentile,
            insights=[GWInsight(**i) for i in review["insights"]],
            summary=review["summary"],
        )

    except Exception as e:
        logger.error(f"Error getting GW review for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gw-review-ai/{team_id}")
@limiter.limit("10/minute")
async def get_gw_review_ai(request: Request, team_id: int):
    """
    Get AI-generated review of last gameweek performance.

    Uses Claude AI to analyze captain choice, bench points, top performers,
    and underperformers to generate personalized insights.
    """
    from services.claude_service import claude_service

    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager info
        manager = await fpl_service.get_manager_info(team_id)

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get live GW points (use the fallback GW)
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)

        # Get manager history to find bench points
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        bench_points = latest_history.points_on_bench if latest_history else 0

        # Build squad data
        squad = []
        captain_id = 0
        captain_name = ""
        captain_points = 0

        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)
            is_bench = pick.position > 11

            squad.append({
                "id": player.id,
                "name": player.web_name,
                "team": player.team_name or "",
                "position": player.position or "",
                "price": player.price,
                "form": player.form_float,
                "gw_points": gw_pts,
                "is_captain": pick.is_captain,
                "is_vice_captain": pick.is_vice_captain,
                "multiplier": pick.multiplier,
                "is_bench": is_bench,
            })

            if pick.is_captain:
                captain_id = player.id
                captain_name = player.web_name
                captain_points = gw_pts * pick.multiplier

        # Get GW stats for comparison
        gw_average = current_gw.average_entry_score
        gw_points = manager.summary_event_points or 0
        gw_rank = manager.summary_event_rank

        # Call Claude AI for analysis
        ai_analysis = await claude_service.analyze_gw_performance(
            squad=squad,
            gw_points=gw_points,
            gw_rank=gw_rank,
            gw_average=gw_average,
            captain_id=captain_id,
            captain_name=captain_name,
            captain_points=captain_points,
            bench_points=bench_points,
        )

        return {
            "what_went_well": ai_analysis.get("what_went_well", []),
            "areas_to_address": ai_analysis.get("areas_to_address", []),
            "strengths": ai_analysis.get("strengths", []),
            "weaknesses": ai_analysis.get("weaknesses", []),
            "squad_score": ai_analysis.get("squad_score", {"overall": 70, "attack": 70, "midfield": 70, "defense": 70, "bench": 60}),
            "summary": ai_analysis.get("summary", ""),
            "ai_model": ai_analysis.get("ai_model", "unknown"),
            "gw_points": gw_points,
            "gw_rank": gw_rank,
            "gw_average": gw_average,
        }

    except Exception as e:
        logger.error(f"Error getting AI GW review for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transfer-suggestions/{team_id}", response_model=TransferSuggestionsResponse)
async def get_transfer_suggestions(team_id: int):
    """
    Get smart transfer suggestions based on squad analysis.

    Identifies players to transfer out (poor form, injured) and
    suggests best replacements within budget.
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get manager history to find bank
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        bank = (latest_history.bank / 10) if latest_history else 0.0

        # Calculate free transfers properly (handles late starters + accumulation)
        free_transfers = await fpl_service.calculate_free_transfers(team_id)

        # Get live GW points
        gw_points_map = await fpl_service.get_live_gameweek_points(current_gw.id)

        # Build squad data
        squad = []
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

        # Initialize service and get suggestions
        workflow_service = TransferWorkflowService(fpl_service)
        result = await workflow_service.get_transfer_suggestions(
            team_id=team_id,
            squad=squad,
            bank=bank,
            free_transfers=free_transfers,
        )

        # Convert to response model
        suggestions = []
        for s in result["suggestions"]:
            # Build alternatives list
            alternatives = [
                TransferAlternative(**alt)
                for alt in s.get("alternatives", [])
            ]
            suggestions.append(TransferSuggestion(
                out=TransferPlayerOut(**s["out"]),
                in_player=TransferPlayerIn(**s["in"]),
                alternatives=alternatives,
                cost_change=s["cost_change"],
                priority=s["priority"],
            ))

        return TransferSuggestionsResponse(
            free_transfers=result["free_transfers"],
            bank=result["bank"],
            suggestions=suggestions,
            message=result["message"],
        )

    except Exception as e:
        logger.error(f"Error getting transfer suggestions for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{team_id}", response_model=AlertsResponse)
async def get_alerts(team_id: int):
    """
    Get alerts for squad issues: injuries, rotation, price changes, fixtures.

    Step 2 of the workflow - what you need to know before making transfers.
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get live GW points (use the fallback GW)
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)

        # Build squad data
        squad = []
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

        # Initialize service and get alerts
        workflow_service = TransferWorkflowService(fpl_service)
        result = await workflow_service.get_alerts(
            team_id=team_id,
            squad=squad,
        )

        return AlertsResponse(
            alerts=[Alert(**a) for a in result["alerts"]],
            summary=result["summary"],
        )

    except Exception as e:
        logger.error(f"Error getting alerts for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineup/{team_id}", response_model=LineupResponse)
async def get_lineup_recommendation(team_id: int, db: Session = Depends(get_db)):
    """
    Get optimal lineup recommendation using SmartPlay ML scores.

    Step 4 of the workflow - auto-optimized formation, starting XI, captain, bench order.
    Uses SmartPlay scores from the database for optimal player selection.
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get live GW points (use the fallback GW)
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)

        # Build squad data
        squad = []
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

        # Initialize service and get lineup with SmartPlay scores
        workflow_service = TransferWorkflowService(fpl_service)
        result = await workflow_service.get_lineup_recommendation(
            team_id=team_id,
            squad=squad,
            db=db,  # Pass database session for SmartPlay scores
        )

        return LineupResponse(
            formation=result["formation"],
            starting_xi=[LineupPlayer(**p) for p in result["starting_xi"]],
            bench=[BenchPlayer(**p) for p in result["bench"]],
            captain=CaptainPick(**result["captain"]) if result["captain"] else None,
            vice_captain=ViceCaptainPick(**result["vice_captain"]) if result["vice_captain"] else None,
            summary=result["summary"],
        )

    except Exception as e:
        logger.error(f"Error getting lineup for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineup-strategies/{team_id}", response_model=LineupStrategiesResponse)
async def get_lineup_strategies(
    team_id: int,
    db: Session = Depends(get_db),
    transfers_out: str = None,  # Comma-separated player IDs to remove
    transfers_in: str = None,   # Comma-separated player IDs to add
):
    """
    Get all three lineup strategies (Balanced, Attacking, Defensive) with SmartPlay scores.

    Returns three formation options with their total and average SmartPlay scores,
    allowing the user to choose based on their preference.

    Optionally accepts transfers_out and transfers_in as comma-separated player IDs
    to show lineup strategies with applied transfers.
    """
    try:
        # Parse transfer IDs
        out_ids = set()
        in_ids = []
        if transfers_out:
            out_ids = set(int(x) for x in transfers_out.split(",") if x.strip())
        if transfers_in:
            in_ids = [int(x) for x in transfers_in.split(",") if x.strip()]

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get live GW points (use the fallback GW)
        gw_points_map = await fpl_service.get_live_gameweek_points(picks_gw)

        # Build squad data (excluding players transferred out)
        squad = []
        for pick in picks:
            # Skip players that are being transferred out
            if pick.element in out_ids:
                continue

            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

        # Add transferred in players
        for in_id in in_ids:
            player = fpl_service.get_player(in_id)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=False,
                is_vice_captain=False,
                multiplier=1,
            ))

        # Initialize service and get strategies
        workflow_service = TransferWorkflowService(fpl_service)
        result = await workflow_service.get_lineup_strategies(
            team_id=team_id,
            squad=squad,
            db=db,
        )

        return LineupStrategiesResponse(
            strategies=[
                FormationStrategy(
                    strategy=s["strategy"],
                    name=s["name"],
                    formation=s["formation"],
                    total_smartplay_score=s["total_smartplay_score"],
                    avg_smartplay_score=s["avg_smartplay_score"],
                    starting_xi=[LineupPlayer(**p) for p in s["starting_xi"]],
                    bench=[BenchPlayer(**p) for p in s["bench"]],
                    captain=CaptainPick(**s["captain"]) if s["captain"] else None,
                    vice_captain=ViceCaptainPick(**s["vice_captain"]) if s["vice_captain"] else None,
                    summary=s["summary"],
                    description=s["description"],
                )
                for s in result["strategies"]
            ],
            recommended=result["recommended"],
        )

    except Exception as e:
        logger.error(f"Error getting lineup strategies for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chip-advice/{team_id}", response_model=ChipAdviceResponse)
async def get_chip_advice(team_id: int):
    """
    Get chip usage advice.

    Step 5 of the workflow - should you use WC/FH/BB/TC this week?
    """
    try:
        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager info
        manager = await fpl_service.get_manager_info(team_id)

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)

        # Get manager history
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None

        # Calculate free transfers
        free_transfers = 1
        if latest_history and latest_history.event_transfers == 0:
            free_transfers = min(2, free_transfers + 1)

        # Get actual chips used from FPL API
        chips_used = await fpl_service.get_chips_used(team_id)

        # Get live GW points
        gw_points_map = await fpl_service.get_live_gameweek_points(current_gw.id)

        # Build squad data
        squad = []
        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            gw_pts = gw_points_map.get(player.id, 0)

            squad.append(PlayerSummary(
                id=player.id,
                name=player.web_name,
                team=player.team_name or "",
                position=player.position or "",
                price=player.price,
                form=player.form_float,
                points=player.total_points,
                gw_points=gw_pts,
                ownership=player.ownership,
                status=player.status,
                news=player.news,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                multiplier=pick.multiplier,
            ))

        # Initialize service and get chip advice
        workflow_service = TransferWorkflowService(fpl_service)
        result = await workflow_service.get_chip_advice(
            team_id=team_id,
            squad=squad,
            chips_used=chips_used,
            current_gw=current_gw.id,
            free_transfers=free_transfers,
        )

        return ChipAdviceResponse(
            available_chips=result["available_chips"],
            recommendations=[ChipRecommendation(**r) for r in result["recommendations"]],
            overall_advice=result["overall_advice"],
        )

    except Exception as e:
        logger.error(f"Error getting chip advice for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decision-quality/{team_id}", response_model=DecisionQualityResponse)
async def get_decision_quality(team_id: int):
    """
    Get decision quality analysis for a manager.

    Analyzes historical FPL decisions over the last 10 gameweeks:
    - Transfer Quality: Success rate, net points gained, hits taken
    - Captain Quality: Success rate, total captain points, most captained player
    - Bench Management: Points left on bench, average per gameweek

    Returns an overall decision score (0-100) with actionable insights.
    """
    try:
        result = await decision_quality_service.get_decision_quality(team_id)
        return result

    except ValueError as e:
        logger.warning(f"Invalid request for team {team_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting decision quality for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player-alternatives/{player_id}")
async def get_player_alternatives(
    player_id: int,
    team_id: int,
    limit: int = 3,
):
    """
    Get best alternative players for a specific player.

    This endpoint finds the best replacements for any player in the user's squad,
    considering their budget (current player's price + bank) and form.

    Used when clicking a player on the pitch to see upgrade options.
    """
    try:
        # Get the player to replace
        player = fpl_service.get_player(player_id)
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager's picks with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        squad_player_ids = {p.element for p in picks}

        # Get manager history to find bank
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        bank = (latest_history.bank / 10) if latest_history else 0.0

        # Budget = current player's selling price + bank
        budget = player.price + bank

        # Get all players
        all_players = fpl_service.get_all_players()
        teams_list = fpl_service.get_all_teams()
        team_names = {t.id: t.short_name for t in teams_list}

        # Filter candidates: same position, affordable, not in squad, available
        candidates = [
            p for p in all_players
            if p.position == player.position
            and p.price <= budget
            and p.id not in squad_player_ids
            and p.status == 'a'  # Available
            and p.minutes > 200  # Has played reasonable minutes
        ]

        # Score candidates based on form, ownership, and price efficiency
        scored_candidates = []
        for c in candidates:
            # Score = form * 2 + (ownership / 20) + price_efficiency
            form_score = c.form_float * 2
            ownership_score = min(c.ownership / 20, 2)  # Cap at 2
            price_efficiency = c.form_float / max(c.price, 0.1) * 5

            total_score = form_score + ownership_score + price_efficiency

            # Bonus for better form than current player
            if c.form_float > player.form_float:
                total_score += 1

            # Build reasons
            reasons = []
            if c.form_float >= 6:
                reasons.append(f"Hot form ({c.form_float:.1f})")
            elif c.form_float >= 5:
                reasons.append(f"Good form ({c.form_float:.1f})")

            if c.ownership < 10:
                reasons.append(f"Differential ({c.ownership:.1f}%)")
            elif c.ownership > 30:
                reasons.append(f"Popular ({c.ownership:.1f}%)")

            price_diff = c.price - player.price
            if price_diff < -0.5:
                reasons.append(f"Saves £{abs(price_diff):.1f}m")
            elif price_diff > 0.5:
                reasons.append(f"Premium upgrade")

            if c.total_points > player.total_points:
                reasons.append(f"More points ({c.total_points})")

            scored_candidates.append({
                "player": c,
                "score": total_score,
                "reasons": reasons[:3],  # Max 3 reasons
                "price_diff": price_diff,
            })

        # Sort by score and take top N
        scored_candidates.sort(key=lambda x: -x["score"])
        top_candidates = scored_candidates[:limit]

        # Build response
        alternatives = []
        for idx, candidate in enumerate(top_candidates):
            c = candidate["player"]
            alternatives.append({
                "id": c.id,
                "name": c.web_name,
                "team": team_names.get(c.team, "???"),
                "position": c.position or "",
                "price": c.price,
                "form": c.form_float,
                "total_points": c.total_points,
                "ownership": c.ownership,
                "smartplay_score": 0,  # Would need DB lookup for actual score
                "reasons": candidate["reasons"],
                "price_diff": candidate["price_diff"],
                "rank": idx + 1,
            })

        return {
            "player_id": player_id,
            "player_name": player.web_name,
            "player_team": team_names.get(player.team, "???"),
            "player_position": player.position or "",
            "player_price": player.price,
            "player_form": player.form_float,
            "budget": budget,
            "bank": bank,
            "alternatives": alternatives,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alternatives for player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sell-analysis/{team_id}")
@limiter.limit("10/minute")
async def get_sell_analysis(request: Request, team_id: int):
    """
    Get AI-powered sell analysis for a team's squad using Claude Haiku.

    Analyzes each player and provides personalized sell/hold recommendations
    with reasoning based on form, fixtures, and market trends.
    """
    import asyncio

    try:
        # Check if Claude is available
        if not claude_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI service not available. Please configure API key."
            )

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Parallel data fetching for performance
        picks_task = fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        fixtures_task = fpl_service.get_fixtures()

        (picks, picks_gw), fixtures = await asyncio.gather(picks_task, fixtures_task)
        squad_player_ids = [p.element for p in picks]

        # Get all players data (sync, already cached in memory)
        all_players = fpl_service.get_all_players()
        players_dict = {p.id: p for p in all_players}
        teams_list = fpl_service.get_all_teams()
        team_names = {t.id: t.short_name for t in teams_list}
        squad_players = []
        smartplay_scores = {}

        for pid in squad_player_ids:
            if pid in players_dict:
                p = players_dict[pid]

                # Get upcoming fixtures for this player's team
                team_fixtures = [
                    f for f in fixtures
                    if (f.team_h == p.team or f.team_a == p.team) and f.event and f.event > current_gw.id
                ][:5]

                fixture_info = []
                total_fdr = 0
                for f in team_fixtures:
                    is_home = f.team_h == p.team
                    opponent_id = f.team_a if is_home else f.team_h
                    opponent_name = team_names.get(opponent_id, "???")
                    fdr = f.team_h_difficulty if is_home else f.team_a_difficulty
                    total_fdr += fdr
                    fixture_info.append(f"{opponent_name}({'H' if is_home else 'A'})")

                squad_players.append({
                    "id": p.id,
                    "name": p.web_name,
                    "team": team_names.get(p.team, "???"),
                    "position": p.position or "",
                    "price": p.price,
                    "form": p.form_float,
                    "total_points": p.total_points,
                    "ownership": p.ownership,
                    "status": p.status,
                    "news": p.news or "",
                    "minutes": p.minutes,
                    "transfers_in": p.transfers_in_event,
                    "transfers_out": p.transfers_out_event,
                    "fixtures": ", ".join(fixture_info[:5]),
                    "fixture_difficulty": total_fdr,
                })

                # Build smartplay scores (simplified version)
                smartplay_scores[pid] = {
                    "final_score": p.form_float * 10 + (25 - total_fdr) * 2 if total_fdr else p.form_float * 10,
                    "nailedness_score": min(100, p.minutes / 10) if p.minutes else 50,
                    "fixture_score": max(0, 100 - total_fdr * 4) if total_fdr else 50,
                }

        # Build crowd insights (simplified)
        crowd_insights = {
            "trending_out": [p["name"] for p in sorted(squad_players, key=lambda x: x.get("transfers_out", 0), reverse=True)[:3]],
            "trending_in": [],  # Would need more data
        }

        # Build market context
        market_context = {
            "current_gw": current_gw.id,
            "deadline": str(current_gw.deadline_time) if current_gw.deadline_time else "",
            "chip_usage": {},  # Would need manager-specific data
        }

        # Get AI analysis
        result = await claude_service.analyze_sell_candidates(
            squad_data=squad_players,
            smartplay_scores=smartplay_scores,
            crowd_insights=crowd_insights,
            market_context=market_context,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sell analysis for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/buy-analysis/{team_id}")
@limiter.limit("10/minute")
async def get_buy_analysis(
    request: Request,
    team_id: int,
    sell_ids: str = "",  # Comma-separated player IDs being sold
):
    """
    Get AI-powered buy recommendations using Claude Haiku.

    Based on players being sold, recommends the best replacements
    considering budget, form, fixtures, and team composition.
    """
    try:
        # Check if Claude is available
        if not claude_service.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI service not available. Please configure API key."
            )

        # Parse sell IDs
        sell_player_ids = []
        if sell_ids:
            sell_player_ids = [int(x.strip()) for x in sell_ids.split(",") if x.strip()]

        # Get current gameweek
        current_gw = fpl_service.get_current_gameweek()
        if not current_gw:
            raise HTTPException(status_code=500, detail="Could not determine current gameweek")

        # Get manager data with fallback to last played GW
        picks, picks_gw = await fpl_service.get_manager_picks_with_fallback(team_id, current_gw.id)
        squad_player_ids = {p.element for p in picks}
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None
        bank = (latest_history.bank / 10) if latest_history else 0.0

        # Get all players data
        all_players = fpl_service.get_all_players()
        players_dict = {p.id: p for p in all_players}
        teams_list = fpl_service.get_all_teams()
        team_names = {t.id: t.short_name for t in teams_list}

        # Calculate budget from players being sold
        budget_from_sales = sum(
            players_dict[pid].price for pid in sell_player_ids if pid in players_dict
        )
        total_budget = bank + budget_from_sales

        # Get positions needed and sell candidates info
        positions_needed = []
        sell_candidates = []
        for pid in sell_player_ids:
            if pid in players_dict:
                p = players_dict[pid]
                positions_needed.append(p.position or "")
                sell_candidates.append({
                    "id": p.id,
                    "name": p.web_name,
                    "team": team_names.get(p.team, "???"),
                    "position": p.position or "",
                    "price": p.price,
                })

        # Get fixtures for building available players list
        fixtures = await fpl_service.get_fixtures()

        # Build available players list (non-squad players in needed positions)
        available_players = []
        for p in all_players:
            # Skip if already in squad or injured/unavailable
            if p.id in squad_player_ids:
                continue
            if p.status not in ("a", "d"):  # Only available or doubtful
                continue
            # Filter by position if we have specific positions needed
            if positions_needed and p.position not in positions_needed:
                continue
            # Filter by budget (max price affordable)
            if p.price > total_budget:
                continue

            # Get upcoming fixtures for this player's team
            team_fixtures = [
                f for f in fixtures
                if (f.team_h == p.team or f.team_a == p.team) and f.event and f.event > current_gw.id
            ][:5]

            fixture_info = []
            total_fdr = 0
            for f in team_fixtures:
                is_home = f.team_h == p.team
                opponent_id = f.team_a if is_home else f.team_h
                opponent_name = team_names.get(opponent_id, "???")
                fdr = f.team_h_difficulty if is_home else f.team_a_difficulty
                total_fdr += fdr
                fixture_info.append(f"{opponent_name}({'H' if is_home else 'A'})")

            available_players.append({
                "id": p.id,
                "name": p.web_name,
                "team": team_names.get(p.team, "???"),
                "position": p.position or "",
                "price": p.price,
                "form": p.form_float,
                "total_points": p.total_points,
                "ownership": p.ownership,
                "fixtures": ", ".join(fixture_info[:5]),
                "fixture_difficulty": total_fdr,
            })

        # Sort by form and limit to top 50 per position to avoid huge prompts
        available_players.sort(key=lambda x: x.get("form", 0), reverse=True)
        available_players = available_players[:50]

        # Get AI recommendations
        result = await claude_service.analyze_buy_candidates(
            sell_candidates=sell_candidates,
            available_players=available_players,
            squad_player_ids=list(squad_player_ids),
            budget=total_budget,
            bank=bank,
            positions_needed=positions_needed,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in buy analysis for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/squad-analysis/{team_id}", response_model=SquadAnalysisResponse)
@limiter.limit("10/minute")
async def analyze_squad(request: Request, team_id: int, transfers: list[dict] = None):
    """
    Get AI-powered squad analysis and optimization tips.

    Args:
        team_id: FPL team ID
        transfers: Optional list of planned transfers with format:
                   [{"out_id": 1, "out_name": "Player", "out_team": "ARS",
                     "in_id": 2, "in_name": "Player2", "in_team": "CHE", "price_diff": -0.5}]
    """
    try:
        transfers = transfers or []

        # Get manager info and picks
        picks = await fpl_service.get_manager_picks(team_id, fpl_service.get_current_gameweek().id)
        history = await fpl_service.get_manager_history(team_id)
        latest_history = history[-1] if history else None

        bank = (latest_history.bank / 10) if latest_history else 0.0
        free_transfers = latest_history.event_transfers if latest_history else 1

        # Build squad data
        team_names = {t.id: t.short_name for t in fpl_service.get_all_teams()}
        squad = []

        for pick in picks:
            player = fpl_service.get_player(pick.element)
            if not player:
                continue

            squad.append({
                "id": player.id,
                "name": player.web_name,
                "team": team_names.get(player.team, "???"),
                "position": player.position or "",
                "price": player.price,
                "form": player.form_float,
                "total_points": player.total_points,
            })

        # Get available chips (simplified - assume all chips available if not used)
        # In a full implementation, we'd track chip usage from FPL API
        chips_used: list[str] = []  # TODO: Get from FPL API manager history
        all_chips = ["wildcard", "freehit", "bboost", "3xc"]
        available_chips = [chip for chip in all_chips if chip not in chips_used]

        # Get current gameweek for chip strategy context
        current_gw = fpl_service.get_current_gameweek()

        # Get AI analysis
        result = await claude_service.analyze_squad(
            squad=squad,
            transfers=transfers,
            bank=bank,
            free_transfers=free_transfers,
            available_chips=available_chips,
            gameweek=current_gw,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in squad analysis for team {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Need to import httpx for error handling
import httpx

