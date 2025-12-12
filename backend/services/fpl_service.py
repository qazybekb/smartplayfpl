"""FPL API Service - Two-layer caching for optimal performance."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from config import settings
from models import Player, Team, Fixture, Gameweek, Pick, ManagerInfo, ManagerHistory, League

logger = logging.getLogger(__name__)


@dataclass
class TeamCache:
    """Cache entry for per-team data."""
    manager: ManagerInfo
    leagues: list[League]
    history: list[ManagerHistory]
    picks: dict[int, list[Pick]]  # gameweek -> picks
    chips_used: list[str]  # list of chip names that have been used
    timestamp: float


@dataclass
class LeagueStandingsCache:
    """Cache entry for league standings data."""
    standings: list[dict]
    timestamp: float


@dataclass
class RivalPicksCache:
    """Cache entry for rival picks data."""
    picks: dict[int, set[int]]  # rival_id -> set of player_ids
    gameweek: int
    timestamp: float


class FPLService:
    """Service for fetching data from the official FPL API with two-layer caching."""

    # Cache TTLs
    GLOBAL_CACHE_TTL = 900  # 15 minutes for global data
    TEAM_CACHE_TTL = 600    # 10 minutes for per-team data
    LIVE_CACHE_TTL = 60     # 1 minute for live GW points
    LEAGUE_CACHE_TTL = 300  # 5 minutes for league standings
    RIVAL_CACHE_TTL = 300   # 5 minutes for rival picks

    # Concurrency settings
    MAX_CONCURRENT_REQUESTS = 10  # Max parallel API requests for rival picks

    def __init__(self):
        self.base_url = settings.FPL_BASE_URL

        # Global cache (shared by all users)
        self._players: dict[int, Player] = {}
        self._teams: dict[int, Team] = {}
        self._gameweeks: list[Gameweek] = []
        self._fixtures: list[Fixture] = []
        self._current_gameweek: Optional[int] = None
        self._global_cache_timestamp: float = 0
        self._fixtures_cache_timestamp: float = 0

        # Live points cache
        self._live_points: dict[int, int] = {}
        self._live_cache_timestamp: float = 0
        self._live_cache_gw: Optional[int] = None

        # Per-team cache
        self._team_cache: dict[int, TeamCache] = {}

        # League standings cache: league_id -> LeagueStandingsCache
        self._league_cache: dict[int, LeagueStandingsCache] = {}

        # Rival picks cache: (league_id, gameweek) -> RivalPicksCache
        self._rival_cache: dict[tuple[int, int], RivalPicksCache] = {}

        # Position mapping
        self._position_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    
    async def initialize(self) -> None:
        """Initialize the service by fetching bootstrap data."""
        await self._refresh_global_cache()

    def clear_cache(self, cache_types: list[str] | None = None) -> dict:
        """
        Clear specified caches or all caches if none specified.

        Args:
            cache_types: List of cache types to clear. Options:
                - "global": Clear bootstrap data (players, teams, fixtures, gameweeks)
                - "teams": Clear per-team caches
                - "live": Clear live points cache
                - "leagues": Clear league standings cache
                - "rivals": Clear rival picks cache
                - "all": Clear everything

        Returns:
            Dict with counts of cleared items
        """
        result = {"cleared": [], "counts": {}}

        if cache_types is None or "all" in cache_types:
            cache_types = ["global", "teams", "live", "leagues", "rivals"]

        if "global" in cache_types:
            player_count = len(self._players)
            team_count = len(self._teams)
            self._players = {}
            self._teams = {}
            self._gameweeks = []
            self._fixtures = []
            self._current_gameweek = None
            self._global_cache_timestamp = 0
            self._fixtures_cache_timestamp = 0
            result["cleared"].append("global")
            result["counts"]["players"] = player_count
            result["counts"]["teams"] = team_count
            logger.info(f"Cleared global cache ({player_count} players, {team_count} teams)")

        if "teams" in cache_types:
            team_cache_count = len(self._team_cache)
            self._team_cache = {}
            result["cleared"].append("teams")
            result["counts"]["team_caches"] = team_cache_count
            logger.info(f"Cleared {team_cache_count} team caches")

        if "live" in cache_types:
            live_count = len(self._live_points)
            self._live_points = {}
            self._live_cache_timestamp = 0
            self._live_cache_gw = None
            result["cleared"].append("live")
            result["counts"]["live_points"] = live_count
            logger.info(f"Cleared live cache ({live_count} entries)")

        if "leagues" in cache_types:
            league_count = len(self._league_cache)
            self._league_cache = {}
            result["cleared"].append("leagues")
            result["counts"]["league_caches"] = league_count
            logger.info(f"Cleared {league_count} league standing caches")

        if "rivals" in cache_types:
            rival_count = len(self._rival_cache)
            self._rival_cache = {}
            result["cleared"].append("rivals")
            result["counts"]["rival_caches"] = rival_count
            logger.info(f"Cleared {rival_count} rival picks caches")

        return result

    def get_cache_stats(self) -> dict:
        """
        Get current cache statistics.

        Returns:
            Dict with cache statistics including sizes and ages
        """
        now = time.time()
        return {
            "global": {
                "players": len(self._players),
                "teams": len(self._teams),
                "gameweeks": len(self._gameweeks),
                "fixtures": len(self._fixtures),
                "age_seconds": round(now - self._global_cache_timestamp, 1) if self._global_cache_timestamp else None,
                "ttl_seconds": self.GLOBAL_CACHE_TTL,
                "expires_in": max(0, round(self.GLOBAL_CACHE_TTL - (now - self._global_cache_timestamp), 1)) if self._global_cache_timestamp else None,
            },
            "teams": {
                "cached_teams": len(self._team_cache),
                "team_ids": list(self._team_cache.keys())[:10],  # First 10 for display
                "ttl_seconds": self.TEAM_CACHE_TTL,
            },
            "live": {
                "entries": len(self._live_points),
                "gameweek": self._live_cache_gw,
                "age_seconds": round(now - self._live_cache_timestamp, 1) if self._live_cache_timestamp else None,
                "ttl_seconds": self.LIVE_CACHE_TTL,
            },
            "leagues": {
                "cached_leagues": len(self._league_cache),
                "league_ids": list(self._league_cache.keys())[:10],
                "ttl_seconds": self.LEAGUE_CACHE_TTL,
            },
            "rivals": {
                "cached_contexts": len(self._rival_cache),
                "contexts": list(self._rival_cache.keys())[:5],  # (league_id, gw) tuples
                "ttl_seconds": self.RIVAL_CACHE_TTL,
            }
        }

    async def _refresh_global_cache(self) -> None:
        """Fetch all static data from bootstrap-static endpoint."""
        if time.time() - self._global_cache_timestamp < self.GLOBAL_CACHE_TTL:
            return
        
        logger.info("Refreshing global cache (bootstrap data)...")
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/bootstrap-static/",
                )
                response.raise_for_status()
                data = response.json()
            except httpx.TimeoutException:
                logger.error("FPL API request timed out")
                raise
            except httpx.RequestError as e:
                logger.error(f"FPL API request failed: {e}")
                raise
        
        # Parse teams
        self._teams = {}
        for t in data["teams"]:
            self._teams[t["id"]] = Team(
                id=t["id"],
                name=t["name"],
                short_name=t["short_name"],
                strength=t["strength"],
                strength_overall_home=t["strength_overall_home"],
                strength_overall_away=t["strength_overall_away"],
                strength_attack_home=t["strength_attack_home"],
                strength_attack_away=t["strength_attack_away"],
                strength_defence_home=t["strength_defence_home"],
                strength_defence_away=t["strength_defence_away"],
            )
        
        # Parse players
        self._players = {}
        for p in data["elements"]:
            self._players[p["id"]] = Player(
                id=p["id"],
                web_name=p["web_name"],
                first_name=p["first_name"],
                second_name=p["second_name"],
                team=p["team"],
                team_name=self._teams[p["team"]].short_name if p["team"] in self._teams else None,
                element_type=p["element_type"],
                position=self._position_map.get(p["element_type"], "???"),
                now_cost=p["now_cost"],
                total_points=p["total_points"],
                form=p["form"],
                selected_by_percent=p["selected_by_percent"],
                minutes=p["minutes"],
                goals_scored=p["goals_scored"],
                assists=p["assists"],
                clean_sheets=p["clean_sheets"],
                yellow_cards=p["yellow_cards"],
                red_cards=p["red_cards"],
                bonus=p["bonus"],
                influence=p["influence"],
                creativity=p["creativity"],
                threat=p["threat"],
                ict_index=p["ict_index"],
                expected_goals=p["expected_goals"],
                expected_assists=p["expected_assists"],
                expected_goal_involvements=p["expected_goal_involvements"],
                expected_goals_conceded=p["expected_goals_conceded"],
                transfers_in_event=p["transfers_in_event"],
                transfers_out_event=p["transfers_out_event"],
                status=p["status"],
                news=p["news"] or "",
                chance_of_playing_next_round=p["chance_of_playing_next_round"],
            )
        
        # Parse gameweeks
        self._gameweeks = []
        for gw in data["events"]:
            self._gameweeks.append(Gameweek(
                id=gw["id"],
                name=gw["name"],
                deadline_time=gw["deadline_time"],
                is_current=gw["is_current"],
                is_next=gw["is_next"],
                finished=gw["finished"],
                average_entry_score=gw.get("average_entry_score"),
                highest_score=gw.get("highest_score"),
            ))
            if gw["is_current"]:
                self._current_gameweek = gw["id"]
        
        self._global_cache_timestamp = time.time()
        logger.info(f"Global cache refreshed: {len(self._players)} players, {len(self._teams)} teams")
    
    def _is_team_cache_valid(self, team_id: int) -> bool:
        """Check if per-team cache is still valid."""
        if team_id not in self._team_cache:
            return False
        return time.time() - self._team_cache[team_id].timestamp < self.TEAM_CACHE_TTL
    
    async def _fetch_team_data(self, team_id: int) -> None:
        """Fetch and cache all data for a specific team in one go."""
        logger.info(f"Fetching data for team {team_id}...")
        
        async with httpx.AsyncClient() as client:
            # Fetch manager info + leagues (single request)
            entry_resp = await client.get(f"{self.base_url}/entry/{team_id}/", timeout=30.0)
            entry_resp.raise_for_status()
            entry_data = entry_resp.json()
            
            # Fetch history
            history_resp = await client.get(f"{self.base_url}/entry/{team_id}/history/", timeout=30.0)
            history_resp.raise_for_status()
            history_data = history_resp.json()
        
        # Parse manager info
        manager = ManagerInfo(
            id=entry_data["id"],
            player_first_name=entry_data["player_first_name"],
            player_last_name=entry_data["player_last_name"],
            name=entry_data["name"],
            summary_overall_points=entry_data["summary_overall_points"],
            summary_overall_rank=entry_data.get("summary_overall_rank"),
            summary_event_points=entry_data.get("summary_event_points"),
            summary_event_rank=entry_data.get("summary_event_rank"),
            started_event=entry_data.get("started_event"),
            current_event=entry_data.get("current_event"),
        )
        
        # Parse leagues
        leagues = []
        for league in entry_data.get("leagues", {}).get("classic", [])[:5]:
            leagues.append(League(
                id=league["id"],
                name=league["name"],
                entry_rank=league.get("entry_rank"),
                entry_last_rank=league.get("entry_last_rank"),
            ))
        
        # Parse history
        history = []
        for h in history_data.get("current", []):
            history.append(ManagerHistory(
                event=h["event"],
                points=h["points"],
                total_points=h["total_points"],
                rank=h.get("rank"),
                overall_rank=h.get("overall_rank"),
                bank=h["bank"],
                value=h["value"],
                event_transfers=h["event_transfers"],
                event_transfers_cost=h["event_transfers_cost"],
                points_on_bench=h["points_on_bench"],
            ))

        # Parse chips used from history
        chips_used = []
        for chip in history_data.get("chips", []):
            chip_name = chip.get("name", "")
            if chip_name:
                chips_used.append(chip_name)

        # Store in cache
        self._team_cache[team_id] = TeamCache(
            manager=manager,
            leagues=leagues,
            history=history,
            picks={},
            chips_used=chips_used,
            timestamp=time.time(),
        )
        logger.info(f"Team {team_id} cached (2 API calls) - chips used: {chips_used}")
    
    async def get_manager_info(self, team_id: int) -> ManagerInfo:
        """Get manager info (cached)."""
        if not self._is_team_cache_valid(team_id):
            await self._fetch_team_data(team_id)
        return self._team_cache[team_id].manager
    
    async def get_manager_history(self, team_id: int) -> list[ManagerHistory]:
        """Get manager history (cached)."""
        if not self._is_team_cache_valid(team_id):
            await self._fetch_team_data(team_id)
        return self._team_cache[team_id].history
    
    async def get_manager_leagues(self, team_id: int) -> list[League]:
        """Get manager leagues (cached)."""
        if not self._is_team_cache_valid(team_id):
            await self._fetch_team_data(team_id)
        return self._team_cache[team_id].leagues

    async def get_chips_used(self, team_id: int) -> list[str]:
        """Get list of chips already used by this manager (cached)."""
        if not self._is_team_cache_valid(team_id):
            await self._fetch_team_data(team_id)
        return self._team_cache[team_id].chips_used

    async def get_manager_picks(self, team_id: int, gameweek: int) -> list[Pick]:
        """Get manager picks for a gameweek (cached)."""
        if not self._is_team_cache_valid(team_id):
            await self._fetch_team_data(team_id)
        
        cache = self._team_cache[team_id]
        
        # Check if picks for this GW are cached
        if gameweek not in cache.picks:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/entry/{team_id}/event/{gameweek}/picks/",
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
            
            picks = []
            for p in data.get("picks", []):
                picks.append(Pick(
                    element=p["element"],
                    position=p["position"],
                    multiplier=p["multiplier"],
                    is_captain=p["is_captain"],
                    is_vice_captain=p["is_vice_captain"],
                ))
            cache.picks[gameweek] = picks
            logger.info(f"Cached picks for team {team_id} GW{gameweek}")
        
        return cache.picks[gameweek]

    async def get_manager_picks_with_fallback(self, team_id: int, gameweek: int) -> tuple[list[Pick], int]:
        """
        Get manager picks with automatic fallback to last played gameweek.

        Returns (picks, actual_gameweek) - the actual_gameweek may differ from
        the requested gameweek if picks don't exist yet for the upcoming GW.
        """
        try:
            picks = await self.get_manager_picks(team_id, gameweek)
            return picks, gameweek
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Picks don't exist for this GW, try manager's last played GW
                manager = await self.get_manager_info(team_id)
                if manager.current_event and manager.current_event != gameweek:
                    picks = await self.get_manager_picks(team_id, manager.current_event)
                    return picks, manager.current_event
            raise

    async def get_live_gameweek_points(self, gameweek: int) -> dict[int, int]:
        """Get live points for all players (cached 1 min)."""
        now = time.time()
        if (self._live_cache_gw == gameweek and 
            now - self._live_cache_timestamp < self.LIVE_CACHE_TTL):
            return self._live_points
        
        logger.info(f"Fetching live points for GW{gameweek}...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/event/{gameweek}/live/",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
        
        self._live_points = {}
        for element in data.get("elements", []):
            self._live_points[element["id"]] = element.get("stats", {}).get("total_points", 0)
        
        self._live_cache_timestamp = now
        self._live_cache_gw = gameweek
        logger.info(f"Live points cached for GW{gameweek}")

        return self._live_points

    async def calculate_free_transfers(self, team_id: int) -> int:
        """
        Calculate the number of free transfers a manager has.

        Rules:
        - Start with 1 FT
        - If you don't use your FT, you bank +1 (max 5)
        - If you use more than you have, the extras cost -4 points each
        - Teams that start mid-season get bonus FTs (up to 5)
        """
        MAX_FT = 5

        manager = await self.get_manager_info(team_id)
        history = await self.get_manager_history(team_id)
        current_gw = self.get_current_gameweek()

        if not history:
            return 1

        # If team started mid-season, they get bonus free transfers
        # Calculate how many GWs they could have played vs how many they did
        started_event = manager.started_event or 1
        current_event = current_gw.id if current_gw else (manager.current_event or 1)

        # For late starters: in their first GW they have unlimited transfers (effectively 5)
        # Then normal accumulation rules apply

        # Calculate FT by simulating through history
        free_transfers = 1

        # If team started late, give them more initial FT
        # Teams starting mid-season get 5 FT in their first week
        if len(history) == 0:
            return MAX_FT  # New team, max FT

        first_gw_played = history[0].event if history else started_event

        # If they started late and this is their first or second GW
        if first_gw_played > 1 and len(history) <= 2:
            # Late starters get max FT initially
            free_transfers = MAX_FT

        # Simulate through each GW
        for i, gw_history in enumerate(history):
            transfers_made = gw_history.event_transfers

            if i == 0 and first_gw_played > 1:
                # First GW for late starter - they had max FT
                free_transfers = MAX_FT

            # Apply transfers made this GW
            if transfers_made > 0:
                remaining = max(0, free_transfers - transfers_made)
                # Next GW: remaining + 1 (with minimum of 1)
                free_transfers = min(MAX_FT, max(1, remaining + 1))
            else:
                # Didn't use any - bank one more
                free_transfers = min(MAX_FT, free_transfers + 1)

        return free_transfers

    # Convenience methods (use global cache)
    def get_player(self, player_id: int) -> Optional[Player]:
        return self._players.get(player_id)
    
    def get_team(self, team_id: int) -> Optional[Team]:
        return self._teams.get(team_id)
    
    def get_current_gameweek(self) -> Optional[Gameweek]:
        """Get current gameweek, or next upcoming gameweek if current deadline has passed."""
        from datetime import datetime, timezone

        current_gw = None
        for gw in self._gameweeks:
            if gw.is_current:
                current_gw = gw
                break

        if not current_gw:
            return None

        # Check if deadline has passed
        deadline = datetime.fromisoformat(current_gw.deadline_time.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)

        # If deadline has passed, return next gameweek
        if now > deadline:
            next_gw_id = current_gw.id + 1
            for gw in self._gameweeks:
                if gw.id == next_gw_id:
                    return gw

        return current_gw

    def get_gameweek_by_id(self, gw_id: int) -> Optional[Gameweek]:
        """Get a specific gameweek by ID."""
        for gw in self._gameweeks:
            if gw.id == gw_id:
                return gw
        return None

    def get_all_players(self) -> list[Player]:
        return list(self._players.values())
    
    def get_all_teams(self) -> list[Team]:
        return list(self._teams.values())
    
    def get_team_short_name(self, team_id: int) -> str:
        """Get short name for a team (e.g., 'ARS', 'LIV')."""
        team = self._teams.get(team_id)
        return team.short_name if team else "???"
    
    async def get_league_standings(self, league_id: int, limit: int = 20) -> list[dict]:
        """Fetch standings for a classic league (cached).

        Returns list of {entry, entry_name, player_name, rank, total, event_total}
        """
        now = time.time()

        # Check cache first
        if league_id in self._league_cache:
            cache_entry = self._league_cache[league_id]
            if now - cache_entry.timestamp < self.LEAGUE_CACHE_TTL:
                logger.debug(f"League {league_id} standings from cache")
                return cache_entry.standings[:limit]

        # Fetch from API
        logger.info(f"Fetching league {league_id} standings from API...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/leagues-classic/{league_id}/standings/",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        # Parse all standings (we may need different limits later)
        standings = []
        for entry in data.get("standings", {}).get("results", []):
            standings.append({
                "entry": entry["entry"],
                "entry_name": entry["entry_name"],
                "player_name": entry["player_name"],
                "rank": entry["rank"],
                "total": entry["total"],
                "event_total": entry.get("event_total", 0),
            })

        # Cache the full result
        self._league_cache[league_id] = LeagueStandingsCache(
            standings=standings,
            timestamp=now
        )
        logger.info(f"Cached league {league_id} standings ({len(standings)} entries)")

        return standings[:limit]
    
    async def get_rival_picks(
        self,
        rival_ids: list[int],
        gameweek: int,
        league_id: Optional[int] = None
    ) -> dict[int, set[int]]:
        """Fetch picks for multiple rivals concurrently (with caching).

        Uses asyncio.gather for concurrent requests with rate limiting.
        Results are cached by (league_id, gameweek) if league_id is provided.

        Returns dict mapping rival_id -> set of player_ids
        """
        now = time.time()

        # Check cache if league_id provided (allows caching by context)
        if league_id is not None:
            cache_key = (league_id, gameweek)
            if cache_key in self._rival_cache:
                cache_entry = self._rival_cache[cache_key]
                if now - cache_entry.timestamp < self.RIVAL_CACHE_TTL:
                    logger.debug(f"Rival picks for league {league_id} GW{gameweek} from cache")
                    # Return only requested rivals from cache
                    return {rid: cache_entry.picks.get(rid, set()) for rid in rival_ids if rid in cache_entry.picks}

        # Fetch concurrently with semaphore for rate limiting
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        rival_picks: dict[int, set[int]] = {}

        async def fetch_rival(rival_id: int, client: httpx.AsyncClient) -> tuple[int, set[int] | None]:
            """Fetch picks for a single rival."""
            async with semaphore:
                try:
                    response = await client.get(
                        f"{self.base_url}/entry/{rival_id}/event/{gameweek}/picks/",
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()

                    picks = set()
                    for p in data.get("picks", []):
                        picks.add(p["element"])
                    return rival_id, picks
                except Exception as e:
                    logger.warning(f"Failed to fetch picks for rival {rival_id}: {e}")
                    return rival_id, None

        logger.info(f"Fetching {len(rival_ids)} rival picks for GW{gameweek} concurrently...")
        async with httpx.AsyncClient() as client:
            tasks = [fetch_rival(rid, client) for rid in rival_ids]
            results = await asyncio.gather(*tasks)

        # Collect successful results
        for rival_id, picks in results:
            if picks is not None:
                rival_picks[rival_id] = picks

        logger.info(f"Fetched {len(rival_picks)}/{len(rival_ids)} rival picks successfully")

        # Cache results if league_id provided
        if league_id is not None:
            self._rival_cache[(league_id, gameweek)] = RivalPicksCache(
                picks=rival_picks,
                gameweek=gameweek,
                timestamp=now
            )
            logger.info(f"Cached rival picks for league {league_id} GW{gameweek}")

        return rival_picks
    
    async def get_fixtures(self) -> list[Fixture]:
        """Fetch all fixtures (cached)."""
        if time.time() - self._fixtures_cache_timestamp < self.GLOBAL_CACHE_TTL:
            return self._fixtures
        
        logger.info("Fetching fixtures...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/fixtures/",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
        
        self._fixtures = []
        for f in data:
            self._fixtures.append(Fixture(
                id=f["id"],
                event=f.get("event"),
                team_h=f["team_h"],
                team_a=f["team_a"],
                team_h_difficulty=f["team_h_difficulty"],
                team_a_difficulty=f["team_a_difficulty"],
                finished=f["finished"],
                team_h_score=f.get("team_h_score"),
                team_a_score=f.get("team_a_score"),
                kickoff_time=f.get("kickoff_time"),
            ))
        
        self._fixtures_cache_timestamp = time.time()
        logger.info(f"Cached {len(self._fixtures)} fixtures")
        
        return self._fixtures
    
    async def get_player_fixtures(self, player_id: int, num_gameweeks: int = 5) -> list[dict]:
        """Get upcoming fixtures for a player's team.
        
        Returns list of {gameweek, opponent, is_home, difficulty}
        """
        player = self.get_player(player_id)
        if not player:
            return []
        
        team_id = player.team
        fixtures = await self.get_fixtures()
        current_gw = self._current_gameweek or 1
        
        upcoming = []
        for f in fixtures:
            if f.event and current_gw < f.event <= current_gw + num_gameweeks:
                if f.team_h == team_id:
                    opponent = self._teams.get(f.team_a)
                    upcoming.append({
                        "gameweek": f.event,
                        "opponent": opponent.short_name if opponent else "???",
                        "is_home": True,
                        "difficulty": f.team_h_difficulty,
                    })
                elif f.team_a == team_id:
                    opponent = self._teams.get(f.team_h)
                    upcoming.append({
                        "gameweek": f.event,
                        "opponent": opponent.short_name if opponent else "???",
                        "is_home": False,
                        "difficulty": f.team_a_difficulty,
                    })
        
        return sorted(upcoming, key=lambda x: x["gameweek"])


# Global singleton
fpl_service = FPLService()
