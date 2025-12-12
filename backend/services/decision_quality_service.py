"""Decision Quality Service - Analyzes FPL decision-making patterns."""

import logging
from collections import Counter
from typing import Optional

from models import (
    DecisionQualityResponse,
    TransferQuality,
    CaptainQuality,
    BenchManagement,
)
from services.fpl_service import fpl_service

logger = logging.getLogger(__name__)


class DecisionQualityService:
    """
    Analyzes a manager's historical FPL decisions to calculate quality scores.

    Metrics:
    - Transfer Quality: Did your transfers pay off?
    - Captain Quality: Did you pick the right captains?
    - Bench Management: How many points did you leave on the bench?
    """

    # Thresholds for scoring
    GOOD_CAPTAIN_THRESHOLD = 6  # Points (before multiplier) considered "good"
    MAX_GAMEWEEKS_TO_ANALYZE = 10  # Look at last N gameweeks

    async def get_decision_quality(self, team_id: int) -> DecisionQualityResponse:
        """
        Calculate decision quality metrics for a manager.

        Args:
            team_id: FPL team ID

        Returns:
            DecisionQualityResponse with all metrics
        """
        await fpl_service.initialize()

        # Get manager history
        history = await fpl_service.get_manager_history(team_id)
        current_gw = fpl_service.get_current_gameweek()

        if not current_gw or not history:
            raise ValueError("Could not fetch manager history")

        # Analyze last N gameweeks
        recent_history = history[-self.MAX_GAMEWEEKS_TO_ANALYZE:]
        gameweeks_analyzed = len(recent_history)

        # Calculate each metric
        transfer_quality = await self._calculate_transfer_quality(team_id, recent_history)
        captain_quality = await self._calculate_captain_quality(team_id, recent_history, current_gw.id)
        bench_management = self._calculate_bench_management(recent_history)

        # Calculate overall score (weighted average)
        overall_score = self._calculate_overall_score(
            transfer_quality, captain_quality, bench_management
        )

        # Generate insights
        overall_insight = self._get_overall_insight(overall_score)
        key_insight = self._get_key_insight(transfer_quality, captain_quality, bench_management)

        return DecisionQualityResponse(
            overall_score=overall_score,
            overall_insight=overall_insight,
            key_insight=key_insight,
            transfer_quality=transfer_quality,
            captain_quality=captain_quality,
            bench_management=bench_management,
            gameweeks_analyzed=gameweeks_analyzed,
        )

    async def _calculate_transfer_quality(
        self,
        team_id: int,
        history: list,
    ) -> TransferQuality:
        """
        Calculate transfer decision quality.

        We analyze:
        - Total transfers made
        - Total hits taken (points spent on extra transfers)
        - Net points impact (simplified: based on hits vs average gain)
        """
        total_transfers = sum(h.event_transfers for h in history)
        total_hits = sum(h.event_transfers_cost for h in history)

        # Calculate success rate based on transfer cost
        # A "successful" gameweek is one where you either:
        # - Made free transfers only (no hits)
        # - Made transfers that cost less than 8 points (2 hits max)
        successful_gws = sum(1 for h in history if h.event_transfers_cost <= 4)
        gws_with_transfers = sum(1 for h in history if h.event_transfers > 0)

        if gws_with_transfers > 0:
            # Success rate is percentage of transfer-making GWs without excessive hits
            success_rate = (successful_gws / len(history)) * 100
        else:
            success_rate = 100.0  # No transfers = no mistakes

        # Estimate net points gained
        # Each hit costs 4 points, but transfers on average gain ~2 points per transfer
        # This is a simplified estimate
        estimated_gain = total_transfers * 2  # Average gain per transfer
        net_points = estimated_gain - total_hits

        return TransferQuality(
            success_rate=round(success_rate, 0),
            net_points_gained=net_points,
            hits_taken=total_hits,
            total_transfers=total_transfers,
        )

    async def _calculate_captain_quality(
        self,
        team_id: int,
        history: list,
        current_gw: int,
    ) -> CaptainQuality:
        """
        Calculate captain decision quality.

        We analyze:
        - How often did your captain score 6+ points?
        - Total points from captain picks
        - Most frequently captained player
        """
        captain_points_list = []
        captain_names = []
        successful_picks = 0
        total_picks = 0

        for h in history:
            gw = h.event

            try:
                # Get picks for this gameweek
                picks = await fpl_service.get_manager_picks(team_id, gw)

                # Find captain
                captain_pick = next((p for p in picks if p.is_captain), None)
                if not captain_pick:
                    continue

                # Get captain's points for that gameweek
                try:
                    live_points = await fpl_service.get_live_gameweek_points(gw)
                    captain_gw_points = live_points.get(captain_pick.element, 0)
                except Exception:
                    # If we can't get live points, estimate from player stats
                    captain_gw_points = 5  # Default estimate

                # Track captain stats
                captain_points = captain_gw_points * 2  # Captain doubles points
                captain_points_list.append(captain_points)

                # Get captain name
                player = fpl_service.get_player(captain_pick.element)
                if player:
                    captain_names.append(player.web_name)

                # Check if this was a "good" pick (6+ points before multiplier)
                if captain_gw_points >= self.GOOD_CAPTAIN_THRESHOLD:
                    successful_picks += 1
                total_picks += 1

            except Exception as e:
                logger.warning(f"Error analyzing captain for GW{gw}: {e}")
                continue

        # Calculate metrics
        success_rate = (successful_picks / total_picks * 100) if total_picks > 0 else 0
        total_captain_points = sum(captain_points_list)

        # Find most captained player
        if captain_names:
            name_counts = Counter(captain_names)
            most_captained, most_count = name_counts.most_common(1)[0]
        else:
            most_captained = "N/A"
            most_count = 0

        return CaptainQuality(
            success_rate=round(success_rate, 0),
            captain_points=total_captain_points,
            most_captained=f"{most_captained} ({most_count}x)",
            most_captained_count=most_count,
        )

    def _calculate_bench_management(self, history: list) -> BenchManagement:
        """
        Calculate bench management quality.

        We analyze:
        - Total points left on bench
        - Average points per gameweek wasted
        """
        total_bench_points = sum(h.points_on_bench for h in history)
        avg_per_gw = total_bench_points / len(history) if history else 0

        # Generate insight based on bench points
        if avg_per_gw <= 2:
            insight = "Great bench management! Minimal points wasted."
        elif avg_per_gw <= 5:
            insight = "Good bench management. Some optimization possible."
        elif avg_per_gw <= 10:
            insight = "Room for improvement in bench selection."
        else:
            insight = "Consider reviewing your starting XI decisions."

        return BenchManagement(
            points_on_bench=total_bench_points,
            per_gameweek=round(avg_per_gw, 1),
            insight=insight,
        )

    def _calculate_overall_score(
        self,
        transfer: TransferQuality,
        captain: CaptainQuality,
        bench: BenchManagement,
    ) -> int:
        """
        Calculate overall decision score (0-100).

        Weights:
        - Transfer Quality: 30%
        - Captain Quality: 40% (most impactful)
        - Bench Management: 30%
        """
        # Transfer score (0-100)
        transfer_score = min(100, transfer.success_rate)

        # Captain score (0-100)
        captain_score = min(100, captain.success_rate)

        # Bench score (0-100) - lower bench points = better
        # Assume 10 points per GW on bench is "average" (50/100)
        # 0 points = 100, 20+ points = 0
        bench_avg = bench.per_gameweek
        if bench_avg <= 1:
            bench_score = 100
        elif bench_avg >= 15:
            bench_score = 20
        else:
            bench_score = max(20, 100 - (bench_avg * 6))

        # Weighted average
        overall = (
            transfer_score * 0.30 +
            captain_score * 0.40 +
            bench_score * 0.30
        )

        return int(round(overall))

    def _get_overall_insight(self, score: int) -> str:
        """Generate insight message based on overall score."""
        if score >= 80:
            return "Excellent! Your decisions are consistently strong. Keep trusting your process."
        elif score >= 65:
            return "Good decision-making! Small tweaks could push you higher."
        elif score >= 50:
            return "Solid foundation. Focus on captain picks for biggest gains."
        elif score >= 35:
            return "Room for improvement. Consider being more patient with transfers."
        else:
            return "Building experience. Focus on one decision area at a time."

    def _get_key_insight(
        self,
        transfer: TransferQuality,
        captain: CaptainQuality,
        bench: BenchManagement,
    ) -> str:
        """Generate the most actionable key insight."""
        insights = []

        # Check transfer quality
        if transfer.hits_taken > 12:
            insights.append("Reduce transfer hits - they're costing you significant points.")
        elif transfer.success_rate < 50:
            insights.append("Be more patient with transfers - wait for clear value.")

        # Check captain quality
        if captain.success_rate < 50:
            insights.append("Focus on captain picks - they have the highest point swing.")
        elif captain.success_rate >= 80:
            insights.append("Your captain picks are excellent! Keep trusting the data.")

        # Check bench management
        if bench.per_gameweek > 8:
            insights.append("Review your starting XI choices - too many points on bench.")
        elif bench.per_gameweek <= 2:
            insights.append("Great bench management! Minimal points wasted.")

        # Return the most important insight
        if insights:
            return insights[0]
        else:
            return "Your decision-making is solid! Keep trusting your process and avoid emotional transfers."


# Create singleton instance
decision_quality_service = DecisionQualityService()
