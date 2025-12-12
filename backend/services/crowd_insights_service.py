"""Crowd Insights Service - Market movements & transfer trends analysis."""

import logging
from typing import Optional

from models import (
    Player,
    CrowdInsightPlayer,
    CrowdInsightCard,
    CrowdInsightsResponse,
)

logger = logging.getLogger(__name__)


class CrowdInsightsService:
    """Service for analyzing crowd behavior and transfer trends."""

    def __init__(self, fpl_service):
        self.fpl = fpl_service

    async def get_crowd_insights(
        self, team_id: int, squad_player_ids: list[int]
    ) -> CrowdInsightsResponse:
        """Generate crowd insights for a manager's team."""

        # Get all players (sync method returns list)
        all_players_list = self.fpl.get_all_players()
        teams_list = self.fpl.get_all_teams()

        # Convert to dict for easier lookup
        all_players = {p.id: p for p in all_players_list}

        # Build team name lookup
        team_names = {t.id: t.short_name for t in teams_list}

        # Convert squad IDs to set for quick lookup
        squad_set = set(squad_player_ids)

        insights: list[CrowdInsightCard] = []

        # 1. Smart Money Alert - Low ownership but gaining transfers
        smart_money = self._find_smart_money(all_players, team_names, squad_set)
        if smart_money:
            insights.append(smart_money)

        # 2. Under-the-Radar Gems - Low ownership, high form
        under_radar = self._find_under_radar_gems(all_players, team_names, squad_set)
        if under_radar:
            insights.append(under_radar)

        # 3. Bandwagon Watch - Massive transfer activity
        bandwagon = self._find_bandwagon(all_players, team_names, squad_set)
        if bandwagon:
            insights.append(bandwagon)

        # 4. Panic Sell Analysis - Players being dumped
        panic_sell = self._find_panic_sells(all_players, team_names, squad_set)
        if panic_sell:
            insights.append(panic_sell)

        # 5. Value Pick - Best value players (form per price)
        value_pick = self._find_value_pick(all_players, team_names, squad_set)
        if value_pick:
            insights.append(value_pick)

        # 6. Squad Alert - Your players being sold massively
        squad_alert = self._find_squad_alert(all_players, team_names, squad_set)
        if squad_alert:
            insights.append(squad_alert)

        # Calculate template metrics
        _, template_score, avg_ownership = self._calculate_template_score(
            all_players, squad_set
        )

        return CrowdInsightsResponse(
            insights=insights,
            template_score=template_score,
            avg_ownership=avg_ownership,
        )

    def _player_to_insight(
        self, player: Player, team_names: dict, squad_set: set
    ) -> CrowdInsightPlayer:
        """Convert Player to CrowdInsightPlayer."""
        return CrowdInsightPlayer(
            id=player.id,
            name=player.web_name,
            team=team_names.get(player.team, "???"),
            price=player.price,
            form=player.form_float,
            ownership=player.ownership,
            transfers_in=player.transfers_in_event,
            transfers_out=player.transfers_out_event,
            in_squad=player.id in squad_set,
        )

    def _find_smart_money(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find players with low ownership but significant transfer gains."""

        # Criteria: ownership < 10%, transfers_in > 100k, form >= 5, NOT in squad
        candidates = [
            p for p in players.values()
            if p.ownership < 10
            and p.transfers_in_event > 100000
            and p.form_float >= 5.0
            and p.minutes > 200  # Has played reasonable minutes
            and p.id not in squad_set  # Exclude players already in squad
        ]

        # Sort by transfer ratio (transfers_in / ownership)
        candidates.sort(
            key=lambda p: p.transfers_in_event / max(p.ownership, 0.1),
            reverse=True
        )

        if not candidates:
            return None

        top = candidates[0]
        return CrowdInsightCard(
            type="smart_money",
            title=f"Smart Money Alert: {top.web_name}",
            icon="📈",
            tag="BUY",
            tag_color="green",
            description=f"{top.web_name} (£{top.price}m) is quietly gaining {top.transfers_in_event // 1000}k transfers while sitting at just {top.ownership:.1f}% ownership. His {top.form_float:.1f} form suggests he's finding his rhythm. This is the week's sneaky differential play.",
            players=[self._player_to_insight(top, team_names, squad_set)],
        )

    def _find_under_radar_gems(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find budget players with low ownership but excellent form."""

        # Criteria: ownership < 10%, form >= 5, price < 7m, NOT in squad
        candidates = [
            p for p in players.values()
            if p.ownership < 10
            and p.form_float >= 5.0
            and p.price < 7.0
            and p.minutes > 200
            and p.id not in squad_set  # Exclude players already in squad
        ]

        # Sort by form
        candidates.sort(key=lambda p: p.form_float, reverse=True)

        if not candidates:
            return None

        # Take top 2
        top_players = candidates[:2]
        top = top_players[0]

        desc = f"While everyone sleeps, {top.web_name} (£{top.price}m) at {top.ownership:.1f}% ownership"
        if len(top_players) > 1:
            p2 = top_players[1]
            desc += f" and {p2.web_name} (£{p2.price}m) at {p2.ownership:.1f}% ownership"
        desc += f" are posting strong form scores. These budget enablers could separate you from the pack."

        return CrowdInsightCard(
            type="under_radar",
            title=f"Under-the-Radar Gems: {top.web_name}",
            icon="💎",
            tag="BUY",
            tag_color="green",
            description=desc,
            players=[self._player_to_insight(p, team_names, squad_set) for p in top_players],
        )

    def _find_bandwagon(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find players with massive transfer movement - NOT in squad."""

        # Criteria: transfers_in > 200k, NOT in squad
        candidates = [
            p for p in players.values()
            if p.transfers_in_event > 200000
            and p.id not in squad_set  # Exclude players already in squad
        ]

        # Sort by transfers in
        candidates.sort(key=lambda p: p.transfers_in_event, reverse=True)

        if not candidates:
            return None

        top = candidates[0]

        return CrowdInsightCard(
            type="bandwagon",
            title=f"Bandwagon Watch: {top.web_name}",
            icon="🚀",
            tag="TRENDING",
            tag_color="blue",
            description=f"Massive movement toward {top.web_name} with +{top.transfers_in_event // 1000}k transfers. Template is shifting - decide if you want to join or stay contrarian.",
            players=[self._player_to_insight(top, team_names, squad_set)],
        )

    def _find_panic_sells(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find players being mass-sold despite decent form."""

        # Criteria: transfers_out > 300k, form is still OK (not terrible)
        candidates = [
            p for p in players.values()
            if p.transfers_out_event > 300000
        ]

        # Sort by transfers out
        candidates.sort(key=lambda p: p.transfers_out_event, reverse=True)

        if not candidates:
            return None

        top = candidates[0]
        action = "AVOID" if top.form_float < 3 else "HOLD"
        tag_color = "red" if top.form_float < 3 else "amber"

        justifies = "justifies the exodus" if top.form_float < 3 else "doesn't fully justify the panic"
        recommendation = "Time to move on rather than hope for a turnaround." if top.form_float < 3 else "Consider holding if you have bigger fires to put out."

        return CrowdInsightCard(
            type="panic_sell",
            title=f"Panic Sell Analysis: {top.web_name}",
            icon="📉",
            tag=action,
            tag_color=tag_color,
            description=f"{top.web_name} (£{top.price}m) is being sold by {top.transfers_out_event // 1000}k managers but his {top.form_float:.1f} form over recent weeks {justifies}. {recommendation}",
            players=[self._player_to_insight(top, team_names, squad_set)],
        )

    def _find_value_pick(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find best value picks - high points per million."""

        # Criteria: price <= 6.5m, form >= 5, decent minutes
        candidates = [
            p for p in players.values()
            if p.price <= 6.5
            and p.form_float >= 5.0
            and p.minutes > 200
            and p.id not in squad_set
        ]

        # Calculate value score (form per price)
        for p in candidates:
            p._value_score = p.form_float / p.price

        # Sort by value score
        candidates.sort(key=lambda p: p._value_score, reverse=True)

        if not candidates:
            return None

        # Take top 2
        top_players = candidates[:2]
        top = top_players[0]

        desc = f"{top.web_name} at just £{top.price}m is delivering {top.form_float:.1f} form - elite value."
        if len(top_players) > 1:
            p2 = top_players[1]
            desc += f" Also consider {p2.web_name} (£{p2.price}m, {p2.form_float:.1f} form)."

        return CrowdInsightCard(
            type="value_pick",
            title=f"Value Pick: {top.web_name}",
            icon="💰",
            tag="VALUE",
            tag_color="green",
            description=desc,
            players=[self._player_to_insight(p, team_names, squad_set) for p in top_players],
        )

    def _find_squad_alert(
        self, players: dict[int, Player], team_names: dict, squad_set: set
    ) -> Optional[CrowdInsightCard]:
        """Find YOUR players being sold massively - alert about potential issues."""

        # Only look at squad players
        squad_players = [p for p in players.values() if p.id in squad_set]

        # Criteria: high transfers out (>50k) - players you own being sold
        being_sold = [
            p for p in squad_players
            if p.transfers_out_event > 50000
        ]

        # Sort by transfers out (most sold first)
        being_sold.sort(key=lambda p: p.transfers_out_event, reverse=True)

        if not being_sold:
            # No alerts - your squad is stable
            return CrowdInsightCard(
                type="squad_alert",
                title="Squad Alert: All Clear",
                icon="✅",
                tag="STABLE",
                tag_color="green",
                description="None of your players are being mass-sold. Your squad looks stable for now.",
                players=[],
            )

        # Take top 3 most sold
        top_players = being_sold[:3]
        top = top_players[0]

        # Build description based on severity
        total_sold = sum(p.transfers_out_event for p in top_players)

        if len(top_players) == 1:
            desc = f"Warning: {top.web_name} is being sold by {top.transfers_out_event // 1000}k managers with {top.form_float:.1f} form. "
            if top.form_float < 3:
                desc += "The poor form justifies concern - consider replacing."
            else:
                desc += "Check if it's panic or genuine concern."
        else:
            names = ", ".join([p.web_name for p in top_players[:2]])
            desc = f"Alert: {names} are being dumped ({total_sold // 1000}k+ transfers out combined). "
            avg_form = sum(p.form_float for p in top_players) / len(top_players)
            if avg_form < 3:
                desc += "Poor form across the board - prioritize transfers."
            else:
                desc += "Review if you should hold or sell."

        # Determine severity based on form and transfers
        avg_form = sum(p.form_float for p in top_players) / len(top_players)
        if avg_form < 2 or top.transfers_out_event > 150000:
            tag = "URGENT"
            tag_color = "red"
        elif avg_form < 4 or top.transfers_out_event > 80000:
            tag = "WARNING"
            tag_color = "amber"
        else:
            tag = "MONITOR"
            tag_color = "blue"

        return CrowdInsightCard(
            type="squad_alert",
            title=f"Squad Alert: {len(top_players)} Player{'s' if len(top_players) > 1 else ''} Being Sold",
            icon="⚠️",
            tag=tag,
            tag_color=tag_color,
            description=desc,
            players=[self._player_to_insight(p, team_names, squad_set) for p in top_players],
        )

    def _calculate_template_score(
        self, players: dict[int, Player], squad_set: set
    ) -> tuple[CrowdInsightCard, float, float]:
        """Calculate how template vs differential the squad is."""

        squad_players = [p for p in players.values() if p.id in squad_set]

        if not squad_players:
            return CrowdInsightCard(
                type="template_score",
                title="Template Score: Unknown",
                icon="🎲",
                tag="N/A",
                tag_color="gray",
                description="Unable to calculate template score.",
                value="Unknown",
            ), 0, 0

        # Calculate average ownership
        total_ownership = sum(p.ownership for p in squad_players)
        avg_ownership = total_ownership / len(squad_players)

        # Count template picks (ownership > 20%)
        template_count = sum(1 for p in squad_players if p.ownership > 20)
        template_percentage = (template_count / len(squad_players)) * 100

        # Determine category
        if avg_ownership >= 25:
            category = "Template"
            tag = "SAFE"
            tag_color = "blue"
            desc = f"Most of your {len(squad_players)} players ({template_count}) are template picks. At {avg_ownership:.0f}% average ownership, you'll move with the crowd — safe but limited upside."
        elif avg_ownership >= 15:
            category = "Balanced"
            tag = "BALANCED"
            tag_color = "green"
            desc = f"A healthy mix of template and differential picks. At {avg_ownership:.0f}% average ownership, you have room to both protect rank and make gains."
        else:
            category = "Punty"
            tag = "RISK"
            tag_color = "amber"
            desc = f"Only {template_count}/{len(squad_players)} players ({template_percentage:.0f}%) are template picks. At {avg_ownership:.0f}% average ownership, you're taking big swings — high risk, high reward."

        return CrowdInsightCard(
            type="template_score",
            title=f"Template Score: {category}",
            icon="🎯",
            tag=tag,
            tag_color=tag_color,
            description=desc,
            value=category,
        ), template_percentage, avg_ownership
