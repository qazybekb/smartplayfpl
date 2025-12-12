"""Transfer Workflow Service - GW Review & Transfer Recommendations."""

import logging
from typing import Optional, Dict, Any, List
from models import Player, PlayerSummary
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TransferWorkflowService:
    """Service for transfer workflow: GW review and transfer suggestions."""

    def __init__(self, fpl_service):
        self.fpl = fpl_service
        self._ml_scores: Dict[int, Dict] = {}
        self._claude_service = None
        self._crowd_service = None

    def _get_claude_service(self):
        """Lazy load Claude service to avoid circular imports."""
        if self._claude_service is None:
            from services.claude_service import claude_service
            self._claude_service = claude_service
        return self._claude_service

    def _get_crowd_service(self):
        """Lazy load Crowd insights service."""
        if self._crowd_service is None:
            from services.crowd_insights_service import CrowdInsightsService
            self._crowd_service = CrowdInsightsService(self.fpl)
        return self._crowd_service

    def _load_ml_scores(self) -> Dict[int, Dict]:
        """Load ML scores from database."""
        from database import SessionLocal, MLPlayerScore

        if self._ml_scores:
            return self._ml_scores

        scores = {}
        db = SessionLocal()
        try:
            # Get latest gameweek scores
            latest = db.query(MLPlayerScore).order_by(
                MLPlayerScore.calculated_at.desc()
            ).first()

            if not latest:
                logger.warning("No ML scores in database")
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
                }

            self._ml_scores = scores
            logger.info(f"Loaded {len(scores)} ML scores for transfers")
            return scores

        except Exception as e:
            logger.error(f"Failed to load ML scores: {e}")
            return {}
        finally:
            db.close()

    def _build_squad_data_for_claude(
        self,
        squad: List[PlayerSummary],
        players_dict: Dict[int, Player],
        team_names: Dict[int, str],
    ) -> List[Dict]:
        """Build comprehensive squad data for Claude analysis."""
        ml_scores = self._load_ml_scores()
        fixtures = self.fpl.get_fixtures()
        current_gw = self.fpl.get_current_gameweek()

        # Build team fixtures lookup
        team_fixtures = {}
        for f in fixtures:
            if f.event and f.event > current_gw.id:
                # Home team
                if f.team_h not in team_fixtures:
                    team_fixtures[f.team_h] = []
                team_fixtures[f.team_h].append({
                    'gw': f.event,
                    'opponent': team_names.get(f.team_a, '???'),
                    'home': True,
                    'fdr': f.team_h_difficulty,
                })
                # Away team
                if f.team_a not in team_fixtures:
                    team_fixtures[f.team_a] = []
                team_fixtures[f.team_a].append({
                    'gw': f.event,
                    'opponent': team_names.get(f.team_h, '???'),
                    'home': False,
                    'fdr': f.team_a_difficulty,
                })

        # Sort fixtures by gameweek
        for team_id in team_fixtures:
            team_fixtures[team_id].sort(key=lambda x: x['gw'])

        squad_data = []
        for idx, p in enumerate(squad):
            player_full = players_dict.get(p.id)
            if not player_full:
                continue

            ml_data = ml_scores.get(p.id, {})

            # Get next 5 fixtures for player's team
            player_fixtures = team_fixtures.get(player_full.team, [])[:5]

            squad_data.append({
                'id': p.id,
                'name': p.name,
                'full_name': f"{player_full.first_name} {player_full.second_name}",
                'team': p.team,
                'position': p.position,
                'price': p.price,
                'form': p.form,
                'total_points': p.points,
                'gw_points': p.gw_points,
                'ownership': p.ownership,
                'status': p.status,
                'news': p.news,
                'chance_of_playing': player_full.chance_of_playing_next_round,
                'minutes': player_full.minutes,
                'goals_scored': player_full.goals_scored,
                'assists': player_full.assists,
                'clean_sheets': player_full.clean_sheets,
                'yellow_cards': player_full.yellow_cards,
                'red_cards': player_full.red_cards,
                'bonus': player_full.bonus,
                'bps': getattr(player_full, 'bps', 0),
                'expected_goals': float(player_full.expected_goals) if player_full.expected_goals else 0,
                'expected_assists': float(player_full.expected_assists) if player_full.expected_assists else 0,
                'expected_goal_involvements': float(player_full.expected_goal_involvements) if player_full.expected_goal_involvements else 0,
                'ict_index': float(player_full.ict_index) if player_full.ict_index else 0,
                'influence': float(player_full.influence) if player_full.influence else 0,
                'creativity': float(player_full.creativity) if player_full.creativity else 0,
                'threat': float(player_full.threat) if player_full.threat else 0,
                'transfers_in': player_full.transfers_in_event,
                'transfers_out': player_full.transfers_out_event,
                'is_captain': p.is_captain,
                'is_vice_captain': p.is_vice_captain,
                'position_in_squad': idx + 1,  # 1-11 starting, 12-15 bench
                'next_fixtures': player_fixtures,
                'smartplay_score': ml_data.get('final_score', 0),
                'nailedness_score': ml_data.get('nailedness_score', 0),
                'fixture_score': ml_data.get('fixture_score', 0),
            })

        return squad_data

    def _get_market_context(self, players_dict: Dict[int, Player], team_names: Dict[int, str]) -> Dict:
        """Get market context: top transfers, form leaders, etc."""
        all_players = list(players_dict.values())

        # Top transfers in
        top_in = sorted(all_players, key=lambda x: x.transfers_in_event, reverse=True)[:15]
        # Top transfers out
        top_out = sorted(all_players, key=lambda x: x.transfers_out_event, reverse=True)[:15]
        # Form leaders
        form_leaders = sorted(all_players, key=lambda x: x.form_float, reverse=True)[:20]

        def player_to_dict(p):
            return {
                'id': p.id,
                'name': p.web_name,
                'team': team_names.get(p.team, '???'),
                'position': {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}.get(p.element_type, '???'),
                'price': p.price,
                'form': p.form_float,
                'ownership': p.ownership,
                'total_points': p.total_points,
                'transfers_in': p.transfers_in_event,
                'transfers_out': p.transfers_out_event,
                'status': p.status,
                'news': p.news,
            }

        return {
            'top_transfers_in': [player_to_dict(p) for p in top_in],
            'top_transfers_out': [player_to_dict(p) for p in top_out],
            'form_leaders': [player_to_dict(p) for p in form_leaders],
        }

    async def get_gw_review(
        self,
        team_id: int,
        squad: list[PlayerSummary],
        gw_points: int,
        gw_rank: Optional[int],
        captain_id: int,
        bench_points: int,
    ) -> dict:
        """Generate AI-style review of gameweek performance."""

        insights = []

        # Find captain and their points
        captain = next((p for p in squad if p.id == captain_id), None)
        if captain:
            captain_pts = captain.gw_points * captain.multiplier
            if captain_pts >= 12:
                insights.append({
                    "type": "positive",
                    "icon": "crown",
                    "text": f"{captain.name} (C) delivered {captain_pts}pts - excellent captain choice!"
                })
            elif captain_pts >= 6:
                insights.append({
                    "type": "neutral",
                    "icon": "crown",
                    "text": f"{captain.name} (C) returned {captain_pts}pts - solid but not spectacular."
                })
            else:
                insights.append({
                    "type": "negative",
                    "icon": "crown",
                    "text": f"{captain.name} (C) only managed {captain_pts}pts - captain pick didn't pay off."
                })

        # Check bench points
        if bench_points >= 10:
            insights.append({
                "type": "negative",
                "icon": "bench",
                "text": f"Left {bench_points}pts on the bench - consider your starting XI choices."
            })
        elif bench_points <= 2:
            insights.append({
                "type": "positive",
                "icon": "bench",
                "text": f"Only {bench_points}pts on bench - good squad management."
            })

        # Find top performer
        starting = [p for p in squad if p.multiplier > 0]
        if starting:
            top_scorer = max(starting, key=lambda p: p.gw_points)
            if top_scorer.gw_points >= 10 and top_scorer.id != captain_id:
                insights.append({
                    "type": "positive",
                    "icon": "star",
                    "text": f"{top_scorer.name} was your star with {top_scorer.gw_points}pts - consider for captaincy next week."
                })

        # Find underperformers (0-2 pts, started)
        underperformers = [p for p in starting if p.gw_points <= 2 and p.id != captain_id]
        if underperformers:
            names = ", ".join([p.name for p in underperformers[:2]])
            if len(underperformers) > 2:
                names += f" (+{len(underperformers) - 2} more)"
            insights.append({
                "type": "warning",
                "icon": "alert",
                "text": f"{names} blanked this week - monitor their form."
            })

        # Find players with bad form (form < 3) in squad
        poor_form = [p for p in squad if p.form < 3.0 and p.multiplier > 0]
        if poor_form:
            worst = min(poor_form, key=lambda p: p.form)
            insights.append({
                "type": "warning",
                "icon": "trending_down",
                "text": f"{worst.name} has {worst.form:.1f} form - strong transfer candidate."
            })

        # Rank insight
        if gw_rank:
            if gw_rank <= 100000:
                insights.append({
                    "type": "positive",
                    "icon": "rank",
                    "text": f"Top 100k GW rank ({gw_rank:,}) - you're in elite company!"
                })
            elif gw_rank <= 500000:
                insights.append({
                    "type": "neutral",
                    "icon": "rank",
                    "text": f"Top 500k GW rank ({gw_rank:,}) - above average performance."
                })
            elif gw_rank >= 5000000:
                insights.append({
                    "type": "negative",
                    "icon": "rank",
                    "text": f"GW rank {gw_rank:,} - a tough week, time to regroup."
                })

        # Limit to 5 most important insights
        insights = insights[:5]

        return {
            "gw_points": gw_points,
            "gw_rank": gw_rank,
            "insights": insights,
            "summary": self._generate_summary(gw_points, gw_rank, len([i for i in insights if i["type"] == "positive"]))
        }

    def _generate_summary(self, gw_points: int, gw_rank: Optional[int], positive_count: int) -> str:
        """Generate a one-line summary."""
        if gw_points >= 70:
            return "Outstanding gameweek! Your team fired on all cylinders."
        elif gw_points >= 55:
            return "Solid performance. A few tweaks could push you higher."
        elif gw_points >= 40:
            return "Average week. Time to assess your underperformers."
        else:
            return "Tough gameweek. Let's identify the issues and fix them."

    async def get_transfer_suggestions(
        self,
        team_id: int,
        squad: list[PlayerSummary],
        bank: float,
        free_transfers: int,
    ) -> dict:
        """Generate smart transfer suggestions using Claude AI."""

        all_players = self.fpl.get_all_players()
        players_dict = {p.id: p for p in all_players}
        teams = self.fpl.get_all_teams()
        team_names = {t.id: t.short_name for t in teams}

        # Try to use Claude for analysis
        claude = self._get_claude_service()
        out_candidates = []

        if claude.is_available():
            try:
                # Build comprehensive data for Claude
                squad_data = self._build_squad_data_for_claude(squad, players_dict, team_names)
                ml_scores = self._load_ml_scores()
                market_context = self._get_market_context(players_dict, team_names)

                # Get crowd insights
                crowd_service = self._get_crowd_service()
                squad_ids = [p.id for p in squad]
                crowd_response = await crowd_service.get_crowd_insights(team_id, squad_ids)
                crowd_insights = {
                    'insights': [
                        {
                            'type': c.type,
                            'title': c.title,
                            'tag': c.tag,
                            'description': c.description,
                            'players': [
                                {
                                    'id': p.id,
                                    'name': p.name,
                                    'team': p.team,
                                    'form': p.form,
                                    'in_squad': p.in_squad,
                                }
                                for p in c.players
                            ],
                        }
                        for c in crowd_response.insights
                    ],
                    'template_score': crowd_response.template_score,
                    'avg_ownership': crowd_response.avg_ownership,
                }

                # Call Claude for sell analysis
                sell_response = await claude.analyze_sell_candidates(
                    squad_data=squad_data,
                    smartplay_scores=ml_scores,
                    crowd_insights=crowd_insights,
                    market_context=market_context,
                )

                # Convert Claude's response to out_candidates format
                for candidate in sell_response.candidates:
                    if candidate.verdict == "SELL":
                        # Find the player in squad
                        squad_player = next((p for p in squad if p.id == candidate.id), None)
                        if squad_player:
                            out_candidates.append({
                                "player": squad_player,
                                "score": 5 if candidate.priority == "critical" else 4 if candidate.priority == "high" else 2,
                                "reasons": [candidate.reasoning],
                                "selling_price": squad_player.price,
                                "priority": candidate.priority,
                                "alternative_view": candidate.alternative_view,
                            })

                logger.info(f"Claude identified {len(out_candidates)} sell candidates")

            except Exception as e:
                logger.error(f"Claude analysis failed, falling back to rules: {e}")
                out_candidates = []  # Will trigger fallback below

        # Fallback to rule-based analysis if Claude unavailable or failed
        if not out_candidates:
            logger.info("Using rule-based transfer analysis")
            for p in squad:
                player_full = players_dict.get(p.id)
                if not player_full:
                    continue

                score = 0
                reasons = []

                # Poor form
                if p.form < 3.0:
                    score += 3
                    reasons.append(f"Poor form ({p.form:.1f})")
                elif p.form < 4.5:
                    score += 1
                    reasons.append(f"Below average form ({p.form:.1f})")

                # Injury/doubt
                if p.status != 'a':
                    score += 4
                    if p.status == 'i':
                        reasons.append("Injured")
                    elif p.status == 'd':
                        reasons.append("Doubtful")
                    elif p.status == 's':
                        reasons.append("Suspended")

                # High price, low returns
                if p.price >= 8.0 and p.form < 5.0:
                    score += 2
                    reasons.append("Expensive underperformer")

                # Being mass-sold
                if player_full.transfers_out_event > 100000:
                    score += 1
                    reasons.append(f"{player_full.transfers_out_event // 1000}k selling")

                if score > 0:
                    out_candidates.append({
                        "player": p,
                        "score": score,
                        "reasons": reasons,
                        "selling_price": p.price,
                    })

            # Sort by score (higher = more urgent to sell)
            out_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Generate transfer suggestions
        suggestions = []
        used_positions = set()

        # Load ML scores for SmartPlay ratings
        ml_scores = self._load_ml_scores()

        for out_candidate in out_candidates[:3]:  # Max 3 suggestions
            out_player = out_candidate["player"]

            # Skip if we already suggested a transfer for this position
            if out_player.position in used_positions:
                continue

            # Find best replacement
            budget = bank + out_candidate["selling_price"]
            replacement = self._find_best_replacement(
                out_player,
                budget,
                all_players,
                squad,
            )

            if replacement:
                # Get SmartPlay score for OUT player
                out_ml = ml_scores.get(out_player.id, {})
                out_smartplay = round(out_ml.get('final_score', 0.0), 1)

                suggestions.append({
                    "out": {
                        "id": out_player.id,
                        "name": out_player.name,
                        "team": out_player.team,
                        "position": out_player.position,
                        "price": out_player.price,
                        "form": out_player.form,
                        "reasons": out_candidate["reasons"],
                        "smartplay_score": out_smartplay,
                    },
                    "in": {
                        "id": replacement["player"].id,
                        "name": replacement["player"].web_name,
                        "team": replacement["player"].team_name or "",
                        "position": replacement["player"].position or out_player.position,
                        "price": replacement["player"].price,
                        "form": replacement["player"].form_float,
                        "reasons": replacement["reasons"],
                    },
                    "alternatives": replacement.get("alternatives", []),
                    "cost_change": replacement["player"].price - out_player.price,
                    "priority": "high" if out_candidate["score"] >= 4 else "medium" if out_candidate["score"] >= 2 else "low",
                })
                used_positions.add(out_player.position)

        return {
            "free_transfers": free_transfers,
            "bank": bank,
            "suggestions": suggestions,
            "message": self._get_transfer_message(len(suggestions), free_transfers),
        }

    def _find_best_replacement(
        self,
        out_player: PlayerSummary,
        budget: float,
        all_players: list[Player],
        squad: list[PlayerSummary],
        max_alternatives: int = 3,
    ) -> Optional[dict]:
        """Find the best replacement(s) for a player.

        Returns the top candidate with 'alternatives' list containing 2-3 options.
        """
        # Load ML scores for SmartPlay ratings
        ml_scores = self._load_ml_scores()

        squad_ids = {p.id for p in squad}
        squad_teams = {}
        for p in squad:
            squad_teams[p.team] = squad_teams.get(p.team, 0) + 1

        # Position mapping
        position_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
        target_position = position_map.get(out_player.position, 0)

        candidates = []
        for player in all_players:
            # Must be same position
            if player.element_type != target_position:
                continue

            # Must be within budget
            if player.price > budget:
                continue

            # Can't already own
            if player.id in squad_ids:
                continue

            # Can't exceed 3 from same team (after removing out_player)
            player_team = player.team_name or ""
            current_from_team = squad_teams.get(player_team, 0)
            if out_player.team == player_team:
                current_from_team -= 1
            if current_from_team >= 3:
                continue

            # Must be available
            if player.status not in ('a', 'd'):
                continue

            # Must have played minutes
            if player.minutes < 200:
                continue

            # Score the candidate
            score = 0
            reasons = []

            # Form bonus
            if player.form_float >= 7.0:
                score += 4
                reasons.append(f"Excellent form ({player.form_float:.1f})")
            elif player.form_float >= 5.0:
                score += 2
                reasons.append(f"Good form ({player.form_float:.1f})")

            # Transfer momentum
            if player.transfers_in_event > 100000:
                score += 2
                reasons.append(f"+{player.transfers_in_event // 1000}k transfers in")

            # Low ownership differential
            if player.ownership < 10:
                score += 1
                reasons.append(f"Differential ({player.ownership:.1f}%)")

            # Value for money
            points_per_million = player.total_points / max(player.price, 4.0)
            if points_per_million > 15:
                score += 1
                reasons.append("Good value")

            candidates.append({
                "player": player,
                "score": score,
                "reasons": reasons,
            })

        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        if not candidates:
            return None

        # Return top candidate with alternatives
        top_candidate = candidates[0]

        # Build alternatives list (top 2-3 candidates)
        alternatives = []
        for c in candidates[:max_alternatives]:
            player_ml = ml_scores.get(c["player"].id, {})
            smartplay_score = player_ml.get('final_score', 0.0)
            alternatives.append({
                "id": c["player"].id,
                "name": c["player"].web_name,
                "team": c["player"].team_name or "",
                "position": c["player"].position or out_player.position,
                "price": c["player"].price,
                "form": c["player"].form_float,
                "total_points": c["player"].total_points,
                "ownership": c["player"].ownership,
                "transfers_in": c["player"].transfers_in_event,
                "score": c["score"],
                "reasons": c["reasons"],
                "smartplay_score": round(smartplay_score, 1),
            })

        top_candidate["alternatives"] = alternatives
        return top_candidate

    def _get_transfer_message(self, suggestion_count: int, free_transfers: int) -> str:
        """Generate a message about transfers."""
        if suggestion_count == 0:
            return "Your squad looks solid! No urgent transfers needed."
        elif free_transfers >= suggestion_count:
            return f"You have {free_transfers} free transfer(s) - enough to make these changes without a hit."
        else:
            hits_needed = suggestion_count - free_transfers
            return f"Making all {suggestion_count} transfers would cost -{hits_needed * 4}pts. Consider prioritizing."

    async def get_alerts(
        self,
        team_id: int,
        squad: list[PlayerSummary],
    ) -> dict:
        """Generate alerts for injuries, rotation, price changes, fixtures."""

        all_players = self.fpl.get_all_players()
        players_dict = {p.id: p for p in all_players}
        teams = self.fpl.get_all_teams()
        teams_dict = {t.short_name: t for t in teams}

        alerts = []

        for p in squad:
            player_full = players_dict.get(p.id)
            if not player_full:
                continue

            # INJURED players - absolutely cannot play
            if p.status == 'i':
                alerts.append({
                    "type": "injured",
                    "severity": "high",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} is INJURED",
                    "detail": p.news or "No return date",
                    "icon": "injury",
                })
            # DOUBTFUL players - might not play
            elif p.status == 'd':
                # Parse chance of playing from news if available
                chance = ""
                if p.news:
                    if "75%" in p.news:
                        chance = " (75% chance)"
                    elif "50%" in p.news:
                        chance = " (50% chance)"
                    elif "25%" in p.news:
                        chance = " (25% chance)"
                alerts.append({
                    "type": "doubtful",
                    "severity": "medium",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} is DOUBTFUL{chance}",
                    "detail": p.news or "Check press conference",
                    "icon": "doubtful",
                })
            # SUSPENDED players - banned from playing
            elif p.status == 's':
                alerts.append({
                    "type": "suspended",
                    "severity": "high",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} is SUSPENDED",
                    "detail": p.news or "Banned",
                    "icon": "suspended",
                })
            # UNAVAILABLE players
            elif p.status == 'u':
                alerts.append({
                    "type": "unavailable",
                    "severity": "high",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} UNAVAILABLE",
                    "detail": p.news or "Not available for selection",
                    "icon": "unavailable",
                })

            # Yellow card suspension warnings (About to be disqualified)
            yellow_cards = player_full.yellow_cards
            if yellow_cards >= 4:
                severity = "high" if yellow_cards == 4 else "medium"
                cards_from_ban = 5 - yellow_cards
                alerts.append({
                    "type": "suspension_risk",
                    "severity": severity,
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} on {yellow_cards} yellow cards",
                    "detail": f"One yellow away from suspension" if cards_from_ban == 1 else f"{cards_from_ban} yellows from suspension",
                    "icon": "yellow_card",
                })
            elif yellow_cards == 3:
                alerts.append({
                    "type": "suspension_risk",
                    "severity": "warning",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} on 3 yellow cards",
                    "detail": "Two yellows from suspension",
                    "icon": "yellow_card",
                })

            # Rotation risk (low minutes in recent games)
            if player_full and player_full.minutes > 0:
                # Estimate games played from total minutes
                games_played = max(1, player_full.minutes // 90 + 1)
                avg_minutes = player_full.minutes / games_played
                if avg_minutes < 60 and p.multiplier > 0:  # Started in your team
                    alerts.append({
                        "type": "rotation",
                        "severity": "medium",
                        "player_id": p.id,
                        "player_name": p.name,
                        "team": p.team,
                        "message": f"{p.name} rotation risk",
                        "detail": f"Averaging {avg_minutes:.0f} mins/game",
                        "icon": "rotation",
                    })

            # Selling out alerts - Players being heavily transferred out
            if player_full:
                transfers_out = player_full.transfers_out_event
                net_transfers = player_full.transfers_in_event - player_full.transfers_out_event

                # High transfer-out (selling out)
                if transfers_out > 150000:  # Being heavily sold
                    severity = "high" if transfers_out > 300000 else "warning"
                    alerts.append({
                        "type": "selling_out",
                        "severity": severity,
                        "player_id": p.id,
                        "player_name": p.name,
                        "team": p.team,
                        "message": f"{p.name} being sold by {transfers_out // 1000}k managers",
                        "detail": f"Price falling risk - {abs(net_transfers) // 1000}k net transfers out",
                        "icon": "trending_down",
                    })
                elif net_transfers > 200000:  # Being heavily bought
                    alerts.append({
                        "type": "price_rise",
                        "severity": "info",
                        "player_id": p.id,
                        "player_name": p.name,
                        "team": p.team,
                        "message": f"{p.name} price rising",
                        "detail": f"+{net_transfers // 1000}k net transfers in",
                        "icon": "price_up",
                    })

                # Price drop risk - heavy selling
                if transfers_out > 100000 and net_transfers < -50000:
                    alerts.append({
                        "type": "price_drop",
                        "severity": "warning",
                        "player_id": p.id,
                        "player_name": p.name,
                        "team": p.team,
                        "message": f"{p.name} price drop risk",
                        "detail": f"{abs(net_transfers) // 1000}k net transfers OUT",
                        "icon": "price_down",
                    })

            # Low form warning (form below 3.0)
            if player_full and player_full.form and float(player_full.form) < 3.0:
                form_val = float(player_full.form)
                alerts.append({
                    "type": "low_form",
                    "severity": "warning",
                    "player_id": p.id,
                    "player_name": p.name,
                    "team": p.team,
                    "message": f"{p.name} in poor form",
                    "detail": f"Form: {form_val:.1f} - struggling recently",
                    "icon": "form_low",
                })

            # Blank gameweek check (if player's team has no fixture)
            # This would need fixture data - simplified version
            if player_full and hasattr(player_full, 'chance_of_playing_next_round'):
                chance = player_full.chance_of_playing_next_round
                if chance is not None and chance < 50 and p.status == 'a':
                    alerts.append({
                        "type": "rotation",
                        "severity": "medium",
                        "player_id": p.id,
                        "player_name": p.name,
                        "team": p.team,
                        "message": f"{p.name} may not play",
                        "detail": f"{chance}% chance of playing next GW",
                        "icon": "rotation",
                    })

        # Fixture difficulty alerts
        fixture_alerts = []
        team_fixtures = {}

        for p in squad:
            if p.team not in team_fixtures:
                team_data = teams_dict.get(p.team)
                if team_data:
                    # Get next fixture difficulty (simplified)
                    fdr = getattr(team_data, 'strength_overall_away', 3)  # Default to 3
                    team_fixtures[p.team] = {
                        "team": p.team,
                        "fdr": fdr,
                        "players": [],
                    }
            if p.team in team_fixtures:
                team_fixtures[p.team]["players"].append(p.name)

        # Add fixture alerts for tough matchups
        for team_name, data in team_fixtures.items():
            if data["fdr"] >= 4:
                player_names = ", ".join(data["players"][:2])
                if len(data["players"]) > 2:
                    player_names += f" +{len(data['players']) - 2}"
                fixture_alerts.append({
                    "type": "fixture",
                    "severity": "warning",
                    "player_id": None,
                    "player_name": None,
                    "team": team_name,
                    "message": f"{team_name} has tough fixture",
                    "detail": f"Affects {player_names}",
                    "icon": "fixture_hard",
                })

        alerts.extend(fixture_alerts)

        # Sort: high severity first, then medium, then low/info
        severity_order = {"high": 0, "medium": 1, "warning": 2, "info": 3}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))

        return {
            "alerts": alerts[:20],  # Limit to 20 alerts (more comprehensive)
            "summary": self._get_alerts_summary(alerts),
        }

    def _get_alerts_summary(self, alerts: list) -> str:
        """Generate summary of alerts."""
        high_count = len([a for a in alerts if a["severity"] == "high"])
        medium_count = len([a for a in alerts if a["severity"] == "medium"])

        if high_count > 0:
            return f"{high_count} critical issue(s) need attention before deadline."
        elif medium_count > 0:
            return f"{medium_count} potential concern(s) to monitor."
        elif len(alerts) > 0:
            return "No major issues, but stay informed."
        else:
            return "All clear! Your squad has no alerts."

    async def get_lineup_recommendation(
        self,
        team_id: int,
        squad: list[PlayerSummary],
        db: Optional[Session] = None,
    ) -> dict:
        """Generate optimal lineup recommendation using SmartPlay ML scores."""

        # Try to get SmartPlay scores from database
        smartplay_scores: Dict[int, Dict[str, Any]] = {}

        if db:
            try:
                from database import MLPlayerScore as DBMLPlayerScore

                # Get latest gameweek scores
                latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

                if latest_score:
                    # Get all player scores for squad
                    squad_ids = [p.id for p in squad]
                    scores = db.query(DBMLPlayerScore).filter(
                        DBMLPlayerScore.gameweek == latest_score.gameweek,
                        DBMLPlayerScore.player_id.in_(squad_ids)
                    ).all()

                    for s in scores:
                        # Calculate lineup score (for starting XI decisions)
                        # Lineup decisions are single-GW, so weight fixture_now more heavily
                        fixture_now = getattr(s, 'fixture_now_score', s.fixture_score)
                        fixture_adjustment = (fixture_now - s.fixture_score) / 10  # Scale 0-1
                        lineup_score = s.final_score * (1 + fixture_adjustment * 0.15)

                        smartplay_scores[s.player_id] = {
                            "final_score": s.final_score,
                            "lineup_score": round(lineup_score, 2),  # For starting XI decisions
                            "nailedness_score": s.nailedness_score,
                            "form_xg_score": s.form_xg_score,
                            "form_pts_score": s.form_pts_score,
                            "fixture_score": s.fixture_score,
                            "fixture_now_score": fixture_now,
                            "next_opponent": s.next_opponent,
                            "next_fdr": s.next_fdr,
                        }
                    logger.info(f"Loaded SmartPlay scores for {len(smartplay_scores)} players")
            except Exception as e:
                logger.warning(f"Could not load SmartPlay scores: {e}")

        all_players = self.fpl.get_all_players()
        players_dict = {p.id: p for p in all_players}

        # Score each player using SmartPlay scores if available, fallback to old method
        scored_players = []
        for p in squad:
            player_full = players_dict.get(p.id)

            # Use SmartPlay score if available
            # For lineup decisions, use lineup_score which weighs fixture_now more heavily
            if p.id in smartplay_scores:
                sp_data = smartplay_scores[p.id]
                score = sp_data.get("lineup_score", sp_data["final_score"])
                reasons = self._get_smartplay_reasons(p, sp_data)
            else:
                # Fallback to simple calculation
                score = self._calculate_player_gw_score(p, player_full)
                reasons = self._get_selection_reasons(p, player_full, score)

            scored_players.append({
                "player": p,
                "score": score,
                "reasons": reasons,
                "smartplay_data": smartplay_scores.get(p.id),
            })

        # Separate by position
        gkps = [sp for sp in scored_players if sp["player"].position == "GKP"]
        defs = [sp for sp in scored_players if sp["player"].position == "DEF"]
        mids = [sp for sp in scored_players if sp["player"].position == "MID"]
        fwds = [sp for sp in scored_players if sp["player"].position == "FWD"]

        # Sort each position by score
        gkps.sort(key=lambda x: x["score"], reverse=True)
        defs.sort(key=lambda x: x["score"], reverse=True)
        mids.sort(key=lambda x: x["score"], reverse=True)
        fwds.sort(key=lambda x: x["score"], reverse=True)

        # Find optimal formation
        best_formation = self._find_optimal_formation(defs, mids, fwds)

        # Build starting XI
        starting_xi = []
        bench = []

        # GKP: 1 starter, 1 bench
        starting_xi.append(gkps[0])
        if len(gkps) > 1:
            bench.append(gkps[1])

        # DEF: based on formation
        def_count = int(best_formation.split("-")[0])
        starting_xi.extend(defs[:def_count])
        bench.extend(defs[def_count:])

        # MID: based on formation
        mid_count = int(best_formation.split("-")[1])
        starting_xi.extend(mids[:mid_count])
        bench.extend(mids[mid_count:])

        # FWD: based on formation
        fwd_count = int(best_formation.split("-")[2])
        starting_xi.extend(fwds[:fwd_count])
        bench.extend(fwds[fwd_count:])

        # Sort bench by score for optimal bench order
        bench.sort(key=lambda x: x["score"], reverse=True)

        # Captain recommendation (highest scoring outfield player)
        outfield_starters = [sp for sp in starting_xi if sp["player"].position != "GKP"]
        outfield_starters.sort(key=lambda x: x["score"], reverse=True)

        captain_pick = outfield_starters[0] if outfield_starters else None
        vice_captain_pick = outfield_starters[1] if len(outfield_starters) > 1 else None

        return {
            "formation": best_formation,
            "starting_xi": [
                {
                    "id": sp["player"].id,
                    "name": sp["player"].name,
                    "position": sp["player"].position,
                    "team": sp["player"].team,
                    "price": sp["player"].price,
                    "form": sp["player"].form,
                    "ownership": sp["player"].ownership,
                    "points": sp["player"].points,
                    "gw_points": sp["player"].gw_points,
                    "status": sp["player"].status,
                    "news": sp["player"].news,
                    "is_captain": sp["player"].id == (captain_pick["player"].id if captain_pick else -1),
                    "is_vice_captain": sp["player"].id == (vice_captain_pick["player"].id if vice_captain_pick else -1),
                    "score": round(sp["score"], 2),
                    "reasons": sp["reasons"],
                    "smartplay_data": sp.get("smartplay_data"),
                }
                for sp in starting_xi
            ],
            "bench": [
                {
                    "id": sp["player"].id,
                    "name": sp["player"].name,
                    "position": sp["player"].position,
                    "team": sp["player"].team,
                    "price": sp["player"].price,
                    "form": sp["player"].form,
                    "ownership": sp["player"].ownership,
                    "points": sp["player"].points,
                    "gw_points": sp["player"].gw_points,
                    "status": sp["player"].status,
                    "news": sp["player"].news,
                    "is_captain": False,
                    "is_vice_captain": False,
                    "score": round(sp["score"], 2),
                    "order": idx + 1,
                    "smartplay_data": sp.get("smartplay_data"),
                }
                for idx, sp in enumerate(bench)
            ],
            "captain": {
                "id": captain_pick["player"].id,
                "name": captain_pick["player"].name,
                "score": round(captain_pick["score"], 2),
                "reasons": captain_pick["reasons"],
            } if captain_pick else None,
            "vice_captain": {
                "id": vice_captain_pick["player"].id,
                "name": vice_captain_pick["player"].name,
                "score": round(vice_captain_pick["score"], 2),
            } if vice_captain_pick else None,
            "summary": f"Optimal {best_formation} with {captain_pick['player'].name if captain_pick else 'TBD'} as captain.",
            "using_smartplay": len(smartplay_scores) > 0,
        }

    def _get_smartplay_reasons(self, p: PlayerSummary, sp_data: Dict[str, Any]) -> list[str]:
        """Get selection reasons based on SmartPlay score components."""
        reasons = []

        # Nailedness
        if sp_data["nailedness_score"] >= 9.0:
            reasons.append("Highly nailed")
        elif sp_data["nailedness_score"] >= 7.0:
            reasons.append("Good nailedness")

        # Form (combined xG and pts)
        form_combined = (sp_data["form_xg_score"] + sp_data["form_pts_score"]) / 2
        if form_combined >= 7.0:
            reasons.append("Excellent form")
        elif form_combined >= 5.0:
            reasons.append("In form")

        # Fixtures
        if sp_data["fixture_score"] >= 8.0:
            reasons.append(f"Easy fixture (vs {sp_data['next_opponent']})")
        elif sp_data["fixture_score"] >= 6.0:
            reasons.append(f"Good fixture (vs {sp_data['next_opponent']})")

        # Overall SmartPlay score
        if sp_data["final_score"] >= 7.5:
            reasons.insert(0, f"SmartPlay {sp_data['final_score']:.1f}")

        return reasons[:3]  # Max 3 reasons

    def _calculate_player_gw_score(self, p: PlayerSummary, player_full) -> float:
        """Calculate a player's expected score for selection."""
        score = 0.0

        # Base: form
        score += p.form * 1.5

        # Availability penalty
        if p.status == 'i':
            return 0  # Injured = don't start
        elif p.status == 'd':
            score *= 0.5  # Doubtful = reduce score
        elif p.status == 's':
            return 0  # Suspended = don't start

        # Recent points trend
        score += p.gw_points * 0.3

        # Ownership (slight boost for template players - less risky)
        if p.ownership > 30:
            score += 0.5

        # Price (premium players tend to have higher ceilings)
        if p.price >= 10:
            score += 1.0
        elif p.price >= 7:
            score += 0.5

        return round(score, 1)

    def _get_selection_reasons(self, p: PlayerSummary, player_full, score: float) -> list[str]:
        """Get reasons for selecting this player."""
        reasons = []

        if p.form >= 7:
            reasons.append("Excellent form")
        elif p.form >= 5:
            reasons.append("Good form")

        if p.ownership > 30:
            reasons.append("Template pick")
        elif p.ownership < 5:
            reasons.append("Differential")

        if p.gw_points >= 8:
            reasons.append(f"Scored {p.gw_points}pts last GW")

        return reasons[:2]  # Max 2 reasons

    def _find_optimal_formation(self, defs: list, mids: list, fwds: list) -> str:
        """Find the optimal formation based on player scores."""

        # Available formations
        formations = [
            ("3-4-3", 3, 4, 3),
            ("3-5-2", 3, 5, 2),
            ("4-3-3", 4, 3, 3),
            ("4-4-2", 4, 4, 2),
            ("4-5-1", 4, 5, 1),
            ("5-3-2", 5, 3, 2),
            ("5-4-1", 5, 4, 1),
        ]

        best_formation = "4-4-2"
        best_score = 0

        for name, d, m, f in formations:
            # Check if we have enough players
            if len(defs) < d or len(mids) < m or len(fwds) < f:
                continue

            # Calculate total score for this formation
            total = sum(sp["score"] for sp in defs[:d])
            total += sum(sp["score"] for sp in mids[:m])
            total += sum(sp["score"] for sp in fwds[:f])

            if total > best_score:
                best_score = total
                best_formation = name

        return best_formation

    def _find_formation_for_strategy(
        self,
        strategy: str,
        defs: list,
        mids: list,
        fwds: list
    ) -> str:
        """Find the best formation for a given strategy."""

        # Strategy-specific formations
        strategy_formations = {
            "attacking": [
                ("3-4-3", 3, 4, 3),
                ("4-3-3", 4, 3, 3),
                ("3-5-2", 3, 5, 2),
            ],
            "defensive": [
                ("5-4-1", 5, 4, 1),
                ("5-3-2", 5, 3, 2),
                ("4-5-1", 4, 5, 1),
            ],
            "balanced": [
                ("4-4-2", 4, 4, 2),
                ("4-3-3", 4, 3, 3),
                ("3-5-2", 3, 5, 2),
                ("4-5-1", 4, 5, 1),
            ],
        }

        formations = strategy_formations.get(strategy, strategy_formations["balanced"])

        best_formation = formations[0][0]  # Default to first
        best_score = -1

        for name, d, m, f in formations:
            # Check if we have enough players
            if len(defs) < d or len(mids) < m or len(fwds) < f:
                continue

            # Calculate total score for this formation
            total = sum(sp["score"] for sp in defs[:d])
            total += sum(sp["score"] for sp in mids[:m])
            total += sum(sp["score"] for sp in fwds[:f])

            if total > best_score:
                best_score = total
                best_formation = name

        return best_formation

    def _build_lineup_for_formation(
        self,
        formation: str,
        gkps: list,
        defs: list,
        mids: list,
        fwds: list,
    ) -> tuple[list, list]:
        """Build starting XI and bench for a given formation."""
        starting_xi = []
        bench = []

        # GKP: 1 starter, 1 bench
        starting_xi.append(gkps[0])
        if len(gkps) > 1:
            bench.append(gkps[1])

        # Parse formation
        parts = formation.split("-")
        def_count = int(parts[0])
        mid_count = int(parts[1])
        fwd_count = int(parts[2])

        # DEF
        starting_xi.extend(defs[:def_count])
        bench.extend(defs[def_count:])

        # MID
        starting_xi.extend(mids[:mid_count])
        bench.extend(mids[mid_count:])

        # FWD
        starting_xi.extend(fwds[:fwd_count])
        bench.extend(fwds[fwd_count:])

        # Sort bench by score for optimal bench order
        bench.sort(key=lambda x: x["score"], reverse=True)

        return starting_xi, bench

    async def get_lineup_strategies(
        self,
        team_id: int,
        squad: list[PlayerSummary],
        db: Optional[Session] = None,
    ) -> dict:
        """Generate all three lineup strategies with SmartPlay scores."""

        # Get SmartPlay scores (same as get_lineup_recommendation)
        smartplay_scores: Dict[int, Dict[str, Any]] = {}

        if db:
            try:
                from database import MLPlayerScore as DBMLPlayerScore

                latest_score = db.query(DBMLPlayerScore).order_by(DBMLPlayerScore.calculated_at.desc()).first()

                if latest_score:
                    squad_ids = [p.id for p in squad]
                    scores = db.query(DBMLPlayerScore).filter(
                        DBMLPlayerScore.gameweek == latest_score.gameweek,
                        DBMLPlayerScore.player_id.in_(squad_ids)
                    ).all()

                    for s in scores:
                        # Calculate lineup score (for starting XI decisions)
                        # Lineup decisions are single-GW, so weight fixture_now more heavily
                        fixture_now = getattr(s, 'fixture_now_score', s.fixture_score)
                        fixture_adjustment = (fixture_now - s.fixture_score) / 10  # Scale 0-1
                        lineup_score = s.final_score * (1 + fixture_adjustment * 0.15)

                        smartplay_scores[s.player_id] = {
                            "final_score": s.final_score,
                            "lineup_score": round(lineup_score, 2),  # For starting XI decisions
                            "nailedness_score": s.nailedness_score,
                            "form_xg_score": s.form_xg_score,
                            "form_pts_score": s.form_pts_score,
                            "fixture_score": s.fixture_score,
                            "fixture_now_score": fixture_now,
                            "next_opponent": s.next_opponent,
                            "next_fdr": s.next_fdr,
                        }
                    logger.info(f"Loaded SmartPlay scores for {len(smartplay_scores)} players (strategies)")
            except Exception as e:
                logger.warning(f"Could not load SmartPlay scores for strategies: {e}")

        all_players = self.fpl.get_all_players()
        players_dict = {p.id: p for p in all_players}

        # Score each player
        scored_players = []
        for p in squad:
            player_full = players_dict.get(p.id)

            # Use SmartPlay score if available
            # For lineup decisions, use lineup_score which weighs fixture_now more heavily
            if p.id in smartplay_scores:
                sp_data = smartplay_scores[p.id]
                score = sp_data.get("lineup_score", sp_data["final_score"])
                reasons = self._get_smartplay_reasons(p, sp_data)
            else:
                score = self._calculate_player_gw_score(p, player_full)
                reasons = self._get_selection_reasons(p, player_full, score)

            scored_players.append({
                "player": p,
                "score": score,
                "reasons": reasons,
                "smartplay_data": smartplay_scores.get(p.id),
            })

        # Separate by position
        gkps = [sp for sp in scored_players if sp["player"].position == "GKP"]
        defs = [sp for sp in scored_players if sp["player"].position == "DEF"]
        mids = [sp for sp in scored_players if sp["player"].position == "MID"]
        fwds = [sp for sp in scored_players if sp["player"].position == "FWD"]

        # Sort each position by score
        gkps.sort(key=lambda x: x["score"], reverse=True)
        defs.sort(key=lambda x: x["score"], reverse=True)
        mids.sort(key=lambda x: x["score"], reverse=True)
        fwds.sort(key=lambda x: x["score"], reverse=True)

        # Strategy definitions
        strategies_config = [
            {
                "key": "balanced",
                "name": "Balanced",
                "description": "Optimal balance between defense and attack based on SmartPlay scores"
            },
            {
                "key": "attacking",
                "name": "Attacking",
                "description": "Maximize attacking potential with more forwards and midfielders"
            },
            {
                "key": "defensive",
                "name": "Defensive",
                "description": "Prioritize defensive stability with 5 at the back"
            },
        ]

        strategies = []
        best_strategy_key = "balanced"
        best_avg_score = 0

        for cfg in strategies_config:
            strategy_key = cfg["key"]

            # Find best formation for this strategy
            formation = self._find_formation_for_strategy(strategy_key, defs, mids, fwds)

            # Build lineup
            starting_xi, bench = self._build_lineup_for_formation(
                formation, gkps, defs, mids, fwds
            )

            # Calculate scores
            total_score = sum(sp["score"] for sp in starting_xi)
            avg_score = total_score / len(starting_xi) if starting_xi else 0

            # Track best strategy
            if avg_score > best_avg_score:
                best_avg_score = avg_score
                best_strategy_key = strategy_key

            # Captain and vice captain
            outfield_starters = [sp for sp in starting_xi if sp["player"].position != "GKP"]
            outfield_starters.sort(key=lambda x: x["score"], reverse=True)

            captain_pick = outfield_starters[0] if outfield_starters else None
            vice_captain_pick = outfield_starters[1] if len(outfield_starters) > 1 else None

            strategies.append({
                "strategy": strategy_key,
                "name": cfg["name"],
                "formation": formation,
                "total_smartplay_score": round(total_score, 1),
                "avg_smartplay_score": round(avg_score, 2),
                "starting_xi": [
                    {
                        "id": sp["player"].id,
                        "name": sp["player"].name,
                        "position": sp["player"].position,
                        "team": sp["player"].team,
                        "price": sp["player"].price,
                        "form": sp["player"].form,
                        "ownership": sp["player"].ownership,
                        "points": sp["player"].points,
                        "gw_points": sp["player"].gw_points,
                        "status": sp["player"].status,
                        "news": sp["player"].news,
                        "is_captain": sp["player"].id == (captain_pick["player"].id if captain_pick else -1),
                        "is_vice_captain": sp["player"].id == (vice_captain_pick["player"].id if vice_captain_pick else -1),
                        "score": round(sp["score"], 2),
                        "reasons": sp["reasons"],
                        "smartplay_data": sp.get("smartplay_data"),
                    }
                    for sp in starting_xi
                ],
                "bench": [
                    {
                        "id": sp["player"].id,
                        "name": sp["player"].name,
                        "position": sp["player"].position,
                        "team": sp["player"].team,
                        "price": sp["player"].price,
                        "form": sp["player"].form,
                        "ownership": sp["player"].ownership,
                        "points": sp["player"].points,
                        "gw_points": sp["player"].gw_points,
                        "status": sp["player"].status,
                        "news": sp["player"].news,
                        "is_captain": False,
                        "is_vice_captain": False,
                        "score": round(sp["score"], 2),
                        "order": idx + 1,
                        "smartplay_data": sp.get("smartplay_data"),
                    }
                    for idx, sp in enumerate(bench)
                ],
                "captain": {
                    "id": captain_pick["player"].id,
                    "name": captain_pick["player"].name,
                    "score": round(captain_pick["score"], 2),
                    "reasons": captain_pick["reasons"],
                } if captain_pick else None,
                "vice_captain": {
                    "id": vice_captain_pick["player"].id,
                    "name": vice_captain_pick["player"].name,
                    "score": round(vice_captain_pick["score"], 2),
                } if vice_captain_pick else None,
                "summary": f"{cfg['name']} {formation} lineup",
                "description": cfg["description"],
            })

        return {
            "strategies": strategies,
            "recommended": best_strategy_key,
        }

    async def get_chip_advice(
        self,
        team_id: int,
        squad: list[PlayerSummary],
        chips_used: list[str],
        current_gw: int,
        free_transfers: int,
    ) -> dict:
        """Generate chip usage advice with smarter scoring."""

        available_chips = []
        chip_names = ["wildcard", "freehit", "bboost", "3xc"]  # Triple captain = 3xc

        for chip in chip_names:
            if chip not in chips_used:
                available_chips.append(chip)

        recommendations = []

        # Get full player data for more analysis
        all_players = self.fpl.get_all_players()
        players_dict = {p.id: p for p in all_players}

        # Check squad status
        injured_count = len([p for p in squad if p.status in ('i', 's')])
        doubtful_count = len([p for p in squad if p.status == 'd'])
        poor_form_count = len([p for p in squad if p.form < 3])
        good_form_count = len([p for p in squad if p.form >= 5])
        excellent_form_count = len([p for p in squad if p.form >= 7])

        # Calculate squad quality metrics
        total_form = sum(p.form for p in squad)
        avg_form = total_form / len(squad) if squad else 0

        # Get bench players
        bench = [p for p in squad if p.multiplier == 0]
        bench_form = sum(p.form for p in bench) / max(len(bench), 1)
        bench_available = len([p for p in bench if p.status == 'a'])
        bench_all_playing = bench_available == len(bench)

        # Premium players (price >= 9.0)
        premium_players = [p for p in squad if p.price >= 9.0]
        premium_in_form = [p for p in premium_players if p.form >= 5]

        # ========== WILDCARD LOGIC ==========
        wc_score = 0
        wc_reasons = []

        # Strong reasons to use wildcard
        if injured_count >= 3:
            wc_score += 3
            wc_reasons.append(f"{injured_count} injured/suspended players need replacing")
        elif injured_count >= 2:
            wc_score += 2
            wc_reasons.append(f"{injured_count} injured/suspended players")
        elif injured_count >= 1:
            wc_score += 1
            wc_reasons.append(f"{injured_count} injury concern")

        if poor_form_count >= 5:
            wc_score += 3
            wc_reasons.append(f"{poor_form_count} players badly out of form")
        elif poor_form_count >= 4:
            wc_score += 2
            wc_reasons.append(f"{poor_form_count} players in poor form")
        elif poor_form_count >= 3:
            wc_score += 1
            wc_reasons.append(f"{poor_form_count} players underperforming")

        if free_transfers == 1 and (injured_count >= 1 or poor_form_count >= 2):
            wc_score += 1
            wc_reasons.append("Limited free transfers to fix issues")

        # Low squad average form
        if avg_form < 3.5:
            wc_score += 2
            wc_reasons.append(f"Squad avg form is just {avg_form:.1f}")
        elif avg_form < 4.0:
            wc_score += 1
            wc_reasons.append(f"Squad needs freshening up (avg form {avg_form:.1f})")

        # Many doubtful players
        if doubtful_count >= 3:
            wc_score += 1
            wc_reasons.append(f"{doubtful_count} doubtful players")

        # Recommend if score >= 2 (lowered threshold)
        if wc_score >= 2:
            recommendations.append({
                "chip": "wildcard",
                "name": "Wildcard",
                "recommendation": "consider",
                "score": wc_score,
                "reasons": wc_reasons[:3],  # Top 3 reasons
                "message": "Your squad needs a refresh. Consider activating Wildcard.",
            })
        else:
            recommendations.append({
                "chip": "wildcard",
                "name": "Wildcard",
                "recommendation": "save",
                "score": wc_score,
                "reasons": wc_reasons[:2] if wc_reasons else ["Squad is in reasonable shape"],
                "message": "Save for a better opportunity.",
            })

        # ========== FREE HIT LOGIC ==========
        fh_score = 0
        fh_reasons = []

        # Free hit is best for blank/double GWs or many unavailable players
        if injured_count >= 4:
            fh_score += 3
            fh_reasons.append(f"{injured_count} unavailable players - Free Hit perfect!")
        elif injured_count >= 3:
            fh_score += 2
            fh_reasons.append(f"{injured_count} unavailable players")

        if injured_count + doubtful_count >= 5:
            fh_score += 2
            fh_reasons.append("Squad decimated by availability issues")

        # Check if many players are unavailable (status not 'a')
        unavailable_count = len([p for p in squad if p.status != 'a'])
        if unavailable_count >= 4:
            fh_score += 2
            fh_reasons.append(f"{unavailable_count} players with fitness doubts")

        recommendations.append({
            "chip": "freehit",
            "name": "Free Hit",
            "recommendation": "consider" if fh_score >= 2 else "save",
            "score": fh_score,
            "reasons": fh_reasons[:3] if fh_reasons else ["Save for blank/double gameweek"],
            "message": "Navigate availability crisis with Free Hit!" if fh_score >= 2 else "Best used during blank or double gameweeks.",
        })

        # ========== BENCH BOOST LOGIC ==========
        bb_score = 0
        bb_reasons = []

        # Check bench quality - more generous scoring
        if bench_all_playing and len(bench) == 4:
            bb_score += 1
            bb_reasons.append("All 4 bench players available")

        if bench_form >= 5:
            bb_score += 3
            bb_reasons.append(f"Excellent bench form ({bench_form:.1f})")
        elif bench_form >= 4:
            bb_score += 2
            bb_reasons.append(f"Strong bench form ({bench_form:.1f})")
        elif bench_form >= 3.5:
            bb_score += 1
            bb_reasons.append(f"Decent bench form ({bench_form:.1f})")

        # Check if bench has good fixtures (simplified - check player form as proxy)
        bench_points = sum(p.form for p in bench if p.status == 'a')
        if bench_points >= 16:  # Average 4+ form per bench player
            bb_score += 1
            bb_reasons.append("Bench players are performing well")

        # Double gameweek consideration (would need fixture data)
        # For now, check if we're in typical DGW range (GW 26-35)
        if 26 <= current_gw <= 35:
            bb_score += 1
            bb_reasons.append("Potential double gameweek period")

        recommendations.append({
            "chip": "bboost",
            "name": "Bench Boost",
            "recommendation": "consider" if bb_score >= 2 else "save",
            "score": bb_score,
            "reasons": bb_reasons[:3] if bb_reasons else ["Build a stronger bench first"],
            "message": "Your bench is firing - consider Bench Boost!" if bb_score >= 2 else "Best used during double gameweeks with 15 playing assets.",
        })

        # ========== TRIPLE CAPTAIN LOGIC ==========
        tc_score = 0
        tc_reasons = []

        # Find best captain option
        outfield = [p for p in squad if p.position != "GKP"]
        if outfield:
            best_player = max(outfield, key=lambda p: p.form)
        else:
            best_player = max(squad, key=lambda p: p.form)

        # Score based on best player form
        if best_player.form >= 8:
            tc_score += 3
            tc_reasons.append(f"{best_player.name} is on fire! ({best_player.form:.1f} form)")
        elif best_player.form >= 7:
            tc_score += 2
            tc_reasons.append(f"{best_player.name} in excellent form ({best_player.form:.1f})")
        elif best_player.form >= 6:
            tc_score += 1
            tc_reasons.append(f"{best_player.name} in good form ({best_player.form:.1f})")

        # Premium player bonus
        if best_player.price >= 10:
            tc_score += 1
            tc_reasons.append(f"Premium asset ({best_player.name} @ £{best_player.price}m)")
        elif best_player.price >= 8:
            tc_score += 0.5
            tc_reasons.append(f"Quality option ({best_player.name})")

        # High ownership = safety net
        if best_player.ownership >= 30:
            tc_score += 0.5
            tc_reasons.append(f"Highly owned ({best_player.ownership:.1f}%) - safe pick")

        # Check if best player has good recent points
        player_full = players_dict.get(best_player.id)
        if player_full:
            # High bonus points indicates good underlying stats
            if player_full.bonus >= 15:
                tc_score += 1
                tc_reasons.append(f"{best_player.name} has {player_full.bonus} bonus (underlying stats)")
            # High ICT index
            if player_full.ict_index and float(player_full.ict_index) >= 100:
                tc_score += 0.5
                tc_reasons.append("Strong ICT index")

        # Double gameweek period bonus
        if 26 <= current_gw <= 35:
            tc_score += 0.5
            tc_reasons.append("DGW period - captain could have 2 fixtures")

        # Convert to integer for comparison
        tc_score_int = int(tc_score)

        recommendations.append({
            "chip": "3xc",
            "name": "Triple Captain",
            "recommendation": "consider" if tc_score >= 2 else "save",
            "score": tc_score,
            "reasons": tc_reasons[:3] if tc_reasons else ["Wait for a captain with two fixtures"],
            "message": f"Triple Captain {best_player.name} this week!" if tc_score >= 2 else "Best used when your captain has two fixtures.",
        })

        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x["score"], reverse=True)

        # Determine overall advice based on best recommendation
        top_rec = recommendations[0] if recommendations else None
        if top_rec and top_rec["recommendation"] == "consider":
            overall = f"Consider using {top_rec['name']} this week!"
        elif any(r["recommendation"] == "consider" for r in recommendations):
            consider_chips = [r for r in recommendations if r["recommendation"] == "consider"]
            overall = f"Consider: {', '.join(r['name'] for r in consider_chips)}"
        else:
            overall = "Save your chips for a better opportunity."

        return {
            "available_chips": available_chips,
            "recommendations": recommendations,
            "overall_advice": overall,
        }
