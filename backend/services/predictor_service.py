"""
FPL Predictor Service

This service provides ML-based player scores from the fpl_final_predictor notebook.
It calculates a comprehensive player score based on:
- Nailedness (45-50%): Can't score if you don't play
- Form xG (5-30%): Underlying performance quality
- Form Points (15%): Recent actual returns
- Fixture Difficulty (10-30%): Easier opponents = more points

The weights vary by position:
- GKP: 50% Nailedness, 20% Form, 30% Fixture
- DEF: 45% Nailedness, 25% Form, 30% Fixture
- MID: 45% Nailedness, 40% Form, 15% Fixture
- FWD: 45% Nailedness, 45% Form, 10% Fixture
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import time
import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Position-specific weights
POSITION_WEIGHTS = {
    'GKP': {'nailedness': 0.50, 'form_xg': 0.05, 'form_pts': 0.15, 'fixture': 0.30},
    'DEF': {'nailedness': 0.45, 'form_xg': 0.10, 'form_pts': 0.15, 'fixture': 0.30},
    'MID': {'nailedness': 0.45, 'form_xg': 0.25, 'form_pts': 0.15, 'fixture': 0.15},
    'FWD': {'nailedness': 0.45, 'form_xg': 0.30, 'form_pts': 0.15, 'fixture': 0.10},
}

# Captain-specific bonus multipliers
CAPTAIN_BONUSES = {
    'penalty_taker': 1.15,      # +15% for primary penalty taker
    'set_piece_taker': 1.08,    # +8% for corners/free kicks taker
    'home_game': 1.05,          # +5% for playing at home
    'easy_fixture': 1.05,       # +5% for FDR 1-2 (very easy/easy)
}

# FDR to score mapping
FDR_TO_SCORE = {
    1: 10.0,  # Very easy
    2: 8.0,   # Easy
    3: 5.0,   # Medium
    4: 2.5,   # Hard
    5: 0.5,   # Very hard
}

FPL_API = "https://fantasy.premierleague.com/api"


class PredictorService:
    """Service for calculating ML-based player scores."""

    def __init__(self):
        self._scores: Dict[int, Dict[str, Any]] = {}  # player_id -> score data
        self._last_update: Optional[datetime] = None
        self._current_gw: Optional[int] = None
        self._team_fixture_scores: Dict[int, float] = {}  # 5 GW weighted (for transfers)
        self._team_fixture_now_scores: Dict[int, float] = {}  # Next GW only (for captaincy/lineup)
        self._team_fixture_data: Dict[int, list] = {}
        self._history_df: Optional[pd.DataFrame] = None

    @property
    def is_initialized(self) -> bool:
        return len(self._scores) > 0

    @property
    def player_count(self) -> int:
        return len(self._scores)

    def get_player_score(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get ML score data for a specific player."""
        return self._scores.get(player_id)

    def get_all_scores(self) -> Dict[int, Dict[str, Any]]:
        """Get all player scores."""
        return self._scores

    def get_scores_by_position(self, position: str) -> list:
        """Get top players for a position, sorted by score."""
        players = [
            {**data, 'player_id': pid}
            for pid, data in self._scores.items()
            if data.get('position') == position
        ]
        return sorted(players, key=lambda x: x.get('final_score', 0), reverse=True)

    def get_top_captain_picks(self, limit: int = 10) -> list:
        """Get top captain picks sorted by captain_score."""
        players = [
            {**data, 'player_id': pid}
            for pid, data in self._scores.items()
            if data.get('status') == 'a'  # Only available players
        ]
        return sorted(players, key=lambda x: x.get('captain_score', 0), reverse=True)[:limit]

    def get_captain_picks_for_squad(self, squad_player_ids: list[int], limit: int = 5) -> list:
        """Get top captain picks from a specific squad."""
        players = [
            {**data, 'player_id': pid}
            for pid, data in self._scores.items()
            if pid in squad_player_ids and data.get('status') == 'a'
        ]
        return sorted(players, key=lambda x: x.get('captain_score', 0), reverse=True)[:limit]

    async def calculate_scores(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Calculate ML scores for all players.
        This is the main method that runs the prediction pipeline.

        Args:
            db: Optional database session to save scores to database
        """
        logger.info("Starting ML score calculation...")
        start_time = time.time()

        try:
            # Step 1: Fetch FPL data
            players_df, teams_df, fixtures_df, current_gw = await self._fetch_fpl_data()
            self._current_gw = current_gw

            # Step 2: Calculate fixture scores for all teams
            self._calculate_fixture_scores(teams_df, fixtures_df, current_gw)

            # Step 3: Fetch player histories
            await self._fetch_player_histories(players_df)

            # Step 4: Calculate scores for all players
            self._calculate_player_scores(players_df)

            # Step 5: Save to database if provided
            if db:
                self._save_to_database(db, current_gw)

            self._last_update = datetime.now()

            elapsed = time.time() - start_time
            logger.info(f"ML score calculation complete: {len(self._scores)} players in {elapsed:.1f}s")

            return {
                "success": True,
                "players_scored": len(self._scores),
                "gameweek": current_gw,
                "elapsed_seconds": round(elapsed, 1),
                "last_update": self._last_update.isoformat(),
            }

        except Exception as e:
            logger.error(f"ML score calculation failed: {e}")
            raise

    def _save_to_database(self, db: Session, gameweek: int):
        """Save calculated scores to database."""
        from database import MLPlayerScore as DBMLPlayerScore
        from database import clear_old_scores

        logger.info(f"Saving {len(self._scores)} scores to database for GW{gameweek}")

        # Clear old scores for this gameweek
        clear_old_scores(db, gameweek)

        # Prepare batch insert
        db_scores = []
        now = datetime.utcnow()

        for player_id, score_data in self._scores.items():
            db_score = DBMLPlayerScore(
                player_id=int(player_id),
                name=str(score_data['name']),
                full_name=str(score_data['full_name']),
                team=str(score_data['team']),
                team_id=int(score_data['team_id']),
                position=str(score_data['position']),
                price=float(score_data['price']),
                ownership=float(score_data['ownership']),
                status=str(score_data['status']),
                news=str(score_data['news']),
                nailedness_score=float(score_data['nailedness_score']),
                form_xg_score=float(score_data['form_xg_score']),
                form_pts_score=float(score_data['form_pts_score']),
                fixture_score=float(score_data['fixture_score']),
                fixture_now_score=float(score_data['fixture_now_score']),
                final_score=float(score_data['final_score']),
                rank=int(score_data['rank']),
                avg_minutes=float(score_data['avg_minutes']),
                avg_points=float(score_data['avg_points']),
                total_points=int(score_data['total_points']),
                form=float(score_data['form']),
                next_opponent=str(score_data['next_opponent']),
                next_fdr=int(score_data['next_fdr']),
                next_home=bool(score_data['next_home']),
                gameweek=int(gameweek),
                calculated_at=now,
                updated_at=now,
            )
            db_scores.append(db_score)

        # Bulk insert
        db.bulk_save_objects(db_scores)
        db.commit()
        logger.info(f"Successfully saved {len(db_scores)} scores to database")

    async def _fetch_fpl_data(self) -> tuple:
        """Fetch bootstrap and fixtures data from FPL API."""
        logger.info("Fetching FPL data...")

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            # Fetch bootstrap data
            response = await client.get(f"{FPL_API}/bootstrap-static/")
            response.raise_for_status()
            data = response.json()

            players_df = pd.DataFrame(data['elements'])
            teams_df = pd.DataFrame(data['teams'])
            events_df = pd.DataFrame(data['events'])

            # Find current gameweek
            next_gw = events_df[events_df['is_next'] == True]
            current_gw = events_df[events_df['is_current'] == True]

            if len(next_gw) > 0:
                gw_number = int(next_gw.iloc[0]['id'])  # Convert numpy.int64 to Python int
            elif len(current_gw) > 0:
                gw_number = int(current_gw.iloc[0]['id'])  # Convert numpy.int64 to Python int
            else:
                gw_number = 1

            # Fetch fixtures
            fixtures_response = await client.get(f"{FPL_API}/fixtures/")
            fixtures_response.raise_for_status()
            fixtures_df = pd.DataFrame(fixtures_response.json())

            # Create team mappings
            team_id_to_name = dict(zip(teams_df['id'], teams_df['short_name']))

            # Add team names and position mapping
            players_df['team_name'] = players_df['team'].map(team_id_to_name)
            position_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
            players_df['position'] = players_df['element_type'].map(position_map)

            logger.info(f"Fetched {len(players_df)} players for GW{gw_number}")

            return players_df, teams_df, fixtures_df, gw_number

    def _calculate_fixture_scores(self, teams_df: pd.DataFrame, fixtures_df: pd.DataFrame, current_gw: int):
        """Calculate fixture difficulty scores for all teams."""
        logger.info("Calculating fixture scores...")

        team_id_to_name = dict(zip(teams_df['id'], teams_df['short_name']))

        for team_id in teams_df['id']:
            fixtures = self._get_team_fixtures(team_id, fixtures_df, current_gw, team_id_to_name)
            self._team_fixture_data[team_id] = fixtures
            self._team_fixture_scores[team_id] = self._calculate_fixture_score(fixtures)
            self._team_fixture_now_scores[team_id] = self._calculate_fixture_now_score(fixtures)

    def _get_team_fixtures(self, team_id: int, fixtures_df: pd.DataFrame, current_gw: int, team_id_to_name: dict, num_gws: int = 5) -> list:
        """Get fixture difficulty for a team over next N gameweeks."""
        team_fixtures = []

        for gw in range(current_gw, current_gw + num_gws):
            gw_fixtures = fixtures_df[fixtures_df['event'] == gw]

            # Home game
            home_match = gw_fixtures[gw_fixtures['team_h'] == team_id]
            if len(home_match) > 0:
                match = home_match.iloc[0]
                opponent_id = match['team_a']
                fdr = match['team_h_difficulty']
                team_fixtures.append({
                    'gw': gw,
                    'opponent_id': opponent_id,
                    'opponent': team_id_to_name.get(opponent_id, 'Unknown'),
                    'fdr': fdr,
                    'is_home': True
                })

            # Away game
            away_match = gw_fixtures[gw_fixtures['team_a'] == team_id]
            if len(away_match) > 0:
                match = away_match.iloc[0]
                opponent_id = match['team_h']
                fdr = match['team_a_difficulty']
                team_fixtures.append({
                    'gw': gw,
                    'opponent_id': opponent_id,
                    'opponent': team_id_to_name.get(opponent_id, 'Unknown'),
                    'fdr': fdr,
                    'is_home': False
                })

        return team_fixtures

    def _calculate_fixture_score(self, team_fixtures: list) -> float:
        """Calculate fixture score (0-10) based on upcoming fixtures."""
        if not team_fixtures:
            return 5.0

        gw_weights = [0.35, 0.25, 0.20, 0.12, 0.08]

        total_score = 0
        total_weight = 0

        for i, fixture in enumerate(team_fixtures[:5]):
            fdr = fixture['fdr']
            is_home = fixture['is_home']

            base_score = FDR_TO_SCORE.get(fdr, 5.0)

            if is_home:
                base_score += 0.5

            weight = gw_weights[i] if i < len(gw_weights) else 0.05
            total_score += base_score * weight
            total_weight += weight

        if total_weight > 0:
            return min(10, max(0, total_score / total_weight))
        return 5.0

    def _calculate_fixture_now_score(self, team_fixtures: list) -> float:
        """Calculate fixture score (0-10) based on ONLY the next fixture.

        This is used for immediate decisions like captaincy and starting XI.
        """
        if not team_fixtures:
            return 5.0

        # Only use the first (next) fixture
        fixture = team_fixtures[0]
        fdr = fixture['fdr']
        is_home = fixture['is_home']

        base_score = FDR_TO_SCORE.get(fdr, 5.0)

        if is_home:
            base_score += 0.5  # Home game bonus

        return min(10, max(0, base_score))

    async def _fetch_player_histories(self, players_df: pd.DataFrame):
        """Fetch historical gameweek data for all players."""
        logger.info("Fetching player histories (this may take a minute)...")

        all_histories = []
        total_players = len(players_df)

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for idx, row in players_df.iterrows():
                player_id = row['id']

                if (idx + 1) % 100 == 0:
                    logger.info(f"Progress: {idx+1}/{total_players} players...")

                try:
                    url = f"{FPL_API}/element-summary/{player_id}/"
                    response = await client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        for gw in data.get('history', []):
                            gw['player_id'] = player_id
                            all_histories.append(gw)
                except Exception:
                    pass  # Skip failed requests

                # Small delay every 50 players to avoid rate limiting
                if (idx + 1) % 50 == 0:
                    await asyncio.sleep(0.2)

        self._history_df = pd.DataFrame(all_histories)
        logger.info(f"Fetched {len(self._history_df)} gameweek records")

    def _calculate_player_scores(self, players_df: pd.DataFrame):
        """Calculate final scores for all players."""
        logger.info("Calculating player scores...")

        self._scores = {}

        for _, player in players_df.iterrows():
            player_id = player['id']
            team_id = player['team']
            position = player['position']

            # Get player history
            if self._history_df is not None and len(self._history_df) > 0:
                player_history = self._history_df[self._history_df['player_id'] == player_id].copy()
            else:
                player_history = pd.DataFrame()

            # Calculate component scores
            nailedness = self._calculate_nailedness(
                player_history,
                player.get('status', 'a'),
                player.get('chance_of_playing_next_round')
            )
            form_xg = self._calculate_form_xg(player_history)
            form_pts = self._calculate_form_pts(player_history)
            fixture = self._calculate_fixture_for_player(team_id, position)
            fixture_now = self._calculate_fixture_now_for_player(team_id, position)

            # Calculate final score (0-10 scale)
            weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS['MID'])
            final_score = (
                weights['nailedness'] * nailedness +
                weights['form_xg'] * form_xg +
                weights['form_pts'] * form_pts +
                weights['fixture'] * fixture
            )
            # Clamp final score to 0-10 range
            final_score = max(0, min(10, final_score))

            # Get fixture info
            team_fixtures = self._team_fixture_data.get(team_id, [])
            next_fixture = team_fixtures[0] if team_fixtures else None

            # Recent stats
            if len(player_history) > 0:
                recent = player_history.sort_values('round', ascending=False).head(5)
                avg_minutes = float(recent['minutes'].mean())
                avg_points = float(recent['total_points'].mean())
            else:
                avg_minutes = 0.0
                avg_points = 0.0

            # Detect penalty/set piece takers from FPL API
            # penalties_order: 1 = primary taker, 2 = secondary, etc.
            penalties_order = player.get('penalties_order', None)
            is_penalty_taker = penalties_order is not None and penalties_order == 1

            # corners_and_indirect_freekicks_order: 1 = primary taker
            set_piece_order = player.get('corners_and_indirect_freekicks_order', None)
            is_set_piece_taker = set_piece_order is not None and set_piece_order <= 2

            # Get fixture info
            next_home = next_fixture['is_home'] if next_fixture else False
            next_fdr = next_fixture['fdr'] if next_fixture else 3

            # Calculate captain score with bonuses
            # Captain score uses fixture_now more heavily (single GW decision)
            captain_score, captain_bonuses = self._calculate_captain_score(
                final_score=final_score,
                is_penalty_taker=is_penalty_taker,
                is_set_piece_taker=is_set_piece_taker,
                is_home=next_home,
                next_fdr=next_fdr,
                position=position,
                fixture_now_score=fixture_now,
                fixture_score=fixture,
            )

            self._scores[player_id] = {
                'name': player['web_name'],
                'full_name': f"{player.get('first_name', '')} {player.get('second_name', '')}".strip(),
                'team': player['team_name'],
                'team_id': team_id,
                'position': position,
                'price': player['now_cost'] / 10,
                'ownership': float(player.get('selected_by_percent', 0)),
                'status': player.get('status', 'a'),
                'news': player.get('news', ''),
                # Component scores
                'nailedness_score': round(nailedness, 2),
                'form_xg_score': round(form_xg, 2),
                'form_pts_score': round(form_pts, 2),
                'fixture_score': round(fixture, 2),  # 5 GW weighted (for transfers)
                'fixture_now_score': round(fixture_now, 2),  # Next GW only (for captaincy/lineup)
                # Final score (0-10 scale)
                'final_score': round(final_score, 2),
                # Captain-specific score and bonuses
                'captain_score': captain_score,
                'captain_bonuses': captain_bonuses,
                'is_penalty_taker': is_penalty_taker,
                'is_set_piece_taker': is_set_piece_taker,
                # Additional info
                'avg_minutes': round(avg_minutes, 1),
                'avg_points': round(avg_points, 1),
                'total_points': player.get('total_points', 0),
                'form': float(player.get('form', 0)),
                'next_opponent': next_fixture['opponent'] if next_fixture else '',
                'next_fdr': next_fdr,
                'next_home': next_home,
            }

        # Calculate ranks (overall)
        sorted_players = sorted(
            self._scores.items(),
            key=lambda x: x[1]['final_score'],
            reverse=True
        )
        for rank, (player_id, _) in enumerate(sorted_players, 1):
            self._scores[player_id]['rank'] = rank

        # Calculate captain ranks (separate ranking for captain picks)
        sorted_by_captain = sorted(
            self._scores.items(),
            key=lambda x: x[1]['captain_score'],
            reverse=True
        )
        for captain_rank, (player_id, _) in enumerate(sorted_by_captain, 1):
            self._scores[player_id]['captain_rank'] = captain_rank

    def _calculate_nailedness(self, player_history: pd.DataFrame, status: str, chance_of_playing: Optional[float]) -> float:
        """Calculate nailedness score (0-10)."""
        if len(player_history) > 0:
            recent = player_history.sort_values('round', ascending=False).head(5)
            avg_minutes = recent['minutes'].mean()
            base_score = min(10, avg_minutes / 9)

            games_started = (recent['minutes'] >= 60).sum()
            if games_started == 5:
                base_score = min(10, base_score + 0.5)
        else:
            base_score = 0

        # Availability adjustment
        if status == 'i':  # Injured
            base_score *= 0.0
        elif status == 'd':  # Doubtful
            base_score *= (chance_of_playing or 50) / 100
        elif status == 's':  # Suspended
            base_score *= 0.0
        elif status == 'u':  # Unavailable
            base_score *= 0.0
        elif chance_of_playing is not None and chance_of_playing < 100:
            base_score *= chance_of_playing / 100

        return base_score

    def _calculate_form_xg(self, player_history: pd.DataFrame) -> float:
        """Calculate xG-based form score (0-10)."""
        if len(player_history) == 0:
            return 0

        recent = player_history.sort_values('round', ascending=False).head(5)
        played = recent[recent['minutes'] > 0]

        if len(played) == 0:
            return 0

        xg = played['expected_goals'].astype(float).mean() if 'expected_goals' in played else 0
        xa = played['expected_assists'].astype(float).mean() if 'expected_assists' in played else 0
        xgi = xg + xa

        # Clamp to 0-10 range
        return max(0, min(10, xgi * 10))

    def _calculate_form_pts(self, player_history: pd.DataFrame) -> float:
        """Calculate points-based form score (0-10)."""
        if len(player_history) == 0:
            return 0

        recent = player_history.sort_values('round', ascending=False).head(5)
        avg_points = recent['total_points'].mean()

        # Clamp to 0-10 range (negative points possible from red cards, own goals)
        return max(0, min(10, avg_points * 1.5))

    def _calculate_fixture_for_player(self, team_id: int, position: str) -> float:
        """Get fixture score for a player's team (5 GW weighted - for transfers)."""
        base_score = self._team_fixture_scores.get(team_id, 5.0)

        # Defenders benefit more from easy fixtures
        if position in ['GKP', 'DEF']:
            if base_score > 5:
                return min(10, base_score * 1.1)
            else:
                return max(0, base_score * 0.9)

        # Clamp to 0-10 range
        return max(0, min(10, base_score))

    def _calculate_fixture_now_for_player(self, team_id: int, position: str) -> float:
        """Get fixture_now score for a player's team (next GW only - for captaincy/lineup)."""
        base_score = self._team_fixture_now_scores.get(team_id, 5.0)

        # Defenders benefit more from easy fixtures
        if position in ['GKP', 'DEF']:
            if base_score > 5:
                return min(10, base_score * 1.1)
            else:
                return max(0, base_score * 0.9)

        # Clamp to 0-10 range
        return max(0, min(10, base_score))

    def _calculate_captain_score(
        self,
        final_score: float,
        is_penalty_taker: bool,
        is_set_piece_taker: bool,
        is_home: bool,
        next_fdr: int,
        position: str,
        fixture_now_score: float = 5.0,
        fixture_score: float = 5.0,
    ) -> tuple[float, list[str]]:
        """
        Calculate captain-specific score with bonuses.
        For captaincy, fixture_now (next GW only) is weighted more heavily than
        the 5-GW fixture average since captain choices are single-GW decisions.

        Returns:
            tuple: (captain_score, list of applied bonuses)
        """
        bonuses_applied = []

        # Goalkeepers shouldn't be captained (very rare hauls)
        if position == 'GKP':
            return round(final_score * 0.3, 2), ['GKP penalty']

        # For captain score, we want to weight fixture_now more heavily
        # Replace the fixture component in final_score with fixture_now
        # The final_score uses fixture_score (5 GW weighted), but for captaincy
        # we want to emphasize fixture_now (next GW only)
        #
        # Calculate the fixture adjustment: how much better/worse is fixture_now vs fixture_score
        fixture_adjustment = (fixture_now_score - fixture_score) / 10  # Scale to 0-1 range
        # Apply fixture adjustment as a multiplier (e.g., +0.2 fixture_now -> +2% boost)
        captain_score = final_score * (1 + fixture_adjustment * 0.15)

        if abs(fixture_adjustment) > 0.1:
            if fixture_adjustment > 0:
                bonuses_applied.append('fixture_now_boost')
            else:
                bonuses_applied.append('fixture_now_penalty')

        # Penalty taker bonus (+15%)
        if is_penalty_taker:
            captain_score *= CAPTAIN_BONUSES['penalty_taker']
            bonuses_applied.append('penalty_taker')

        # Set piece taker bonus (+8%)
        if is_set_piece_taker:
            captain_score *= CAPTAIN_BONUSES['set_piece_taker']
            bonuses_applied.append('set_piece_taker')

        # Home game bonus (+5%)
        if is_home:
            captain_score *= CAPTAIN_BONUSES['home_game']
            bonuses_applied.append('home_game')

        # Easy fixture bonus (+5% for FDR 1-2)
        if next_fdr <= 2:
            captain_score *= CAPTAIN_BONUSES['easy_fixture']
            bonuses_applied.append('easy_fixture')

        return round(captain_score, 2), bonuses_applied


# Need asyncio import for the async functions
import asyncio

# Singleton instance
_predictor_service: Optional[PredictorService] = None


def get_predictor_service() -> PredictorService:
    """Get the singleton predictor service instance."""
    global _predictor_service
    if _predictor_service is None:
        _predictor_service = PredictorService()
    return _predictor_service
