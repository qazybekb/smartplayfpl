"use client";

import { Trophy } from "lucide-react";
import type { TeamAnalysisResponse } from "@/lib/api";

interface ManagerHeaderProps {
  teamData: TeamAnalysisResponse;
  embedded?: boolean;
}

// Total FPL players (approximately 11 million active)
const TOTAL_FPL_PLAYERS = 11_000_000;

export default function ManagerHeader({ teamData, embedded = false }: ManagerHeaderProps) {
  // Calculate GW rank percentile
  const gwRankPercentile = teamData.manager.summary_event_rank
    ? ((teamData.manager.summary_event_rank / TOTAL_FPL_PLAYERS) * 100).toFixed(1)
    : null;

  const content = (
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
      {/* Left: Manager Info */}
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 bg-white/20 backdrop-blur rounded-2xl flex items-center justify-center">
          <Trophy className="w-8 h-8 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">
            {teamData.manager.name}
          </h1>
          <p className="text-violet-100">
            {teamData.manager.player_first_name}{" "}
            {teamData.manager.player_last_name}
          </p>
        </div>
      </div>

      {/* Right: Stats */}
      <div className="flex flex-wrap items-start gap-6">
        <div className="text-center min-w-[80px]">
          <p className="text-violet-100 text-xs font-medium uppercase mb-1">
            GW Points
          </p>
          <p className="text-3xl font-bold text-white">
            {teamData.manager.summary_event_points}
          </p>
          <p className="text-violet-200 text-xs mt-1">
            avg {teamData.gameweek.average_entry_score}
          </p>
        </div>
        <div className="hidden sm:block w-px h-16 bg-white/20 mt-1" />
        <div className="text-center min-w-[80px]">
          <p className="text-violet-100 text-xs font-medium uppercase mb-1">
            GW Rank
          </p>
          <p className="text-2xl font-bold text-white">
            {teamData.manager.summary_event_rank?.toLocaleString() || "N/A"}
          </p>
          {gwRankPercentile && (
            <p className="text-violet-200 text-xs mt-1">
              top {gwRankPercentile}%
            </p>
          )}
        </div>
        <div className="hidden sm:block w-px h-16 bg-white/20 mt-1" />
        <div className="text-center min-w-[80px]">
          <p className="text-violet-100 text-xs font-medium uppercase mb-1">
            Overall Rank
          </p>
          <p className="text-2xl font-bold text-white">
            {teamData.manager.summary_overall_rank?.toLocaleString() || "N/A"}
          </p>
          <p className="text-violet-200 text-xs mt-1 invisible">-</p>
        </div>
        <div className="hidden sm:block w-px h-16 bg-white/20 mt-1" />
        <div className="text-center min-w-[80px]">
          <p className="text-violet-100 text-xs font-medium uppercase mb-1">
            Total Points
          </p>
          <p className="text-2xl font-bold text-white">
            {teamData.manager.summary_overall_points}
          </p>
          <p className="text-violet-200 text-xs mt-1 invisible">-</p>
        </div>
      </div>
    </div>
  );

  if (embedded) {
    return <div className="p-6">{content}</div>;
  }

  return (
    <div className="bg-gradient-to-r from-emerald-600 to-green-600 rounded-2xl p-6 shadow-lg shadow-emerald-200">
      {content}
    </div>
  );
}
