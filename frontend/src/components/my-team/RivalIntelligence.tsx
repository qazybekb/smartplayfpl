"use client";

import { Trophy, Medal, TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { RivalIntelligenceResponse, LeagueStanding } from "@/lib/api";

interface RivalIntelligenceProps {
  rivalData: RivalIntelligenceResponse | null;
  loading?: boolean;
}

export default function RivalIntelligence({ rivalData, loading }: RivalIntelligenceProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!rivalData) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4">Rival Intelligence</h2>
        <p className="text-slate-500 text-sm">No rival data available.</p>
      </div>
    );
  }

  // Calculate percentile display
  const percentile = rivalData.gw_rank_percentile;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-bold text-slate-800">Rival Intelligence</h2>
        </div>
      </div>

      {/* Overall Stats */}
      <div className="px-6 py-4 bg-gradient-to-r from-amber-50 to-orange-50 border-b border-amber-100">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-amber-700 font-medium mb-1">GW Rank</p>
            <p className="text-xl font-bold text-slate-800">
              {rivalData.gw_rank?.toLocaleString() || "N/A"}
            </p>
          </div>
          <div>
            <p className="text-xs text-amber-700 font-medium mb-1">Overall Rank</p>
            <p className="text-xl font-bold text-slate-800">
              {rivalData.overall_rank?.toLocaleString() || "N/A"}
            </p>
          </div>
          <div>
            <p className="text-xs text-amber-700 font-medium mb-1">Percentile</p>
            <p className="text-xl font-bold text-slate-800">
              {percentile !== null ? `Top ${percentile}%` : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* League Standings */}
      {rivalData.leagues.length > 0 && (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">League Standings</h3>
          <div className="space-y-2">
            {rivalData.leagues.slice(0, 5).map((league) => (
              <LeagueRow key={league.league_id} league={league} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LeagueRow({ league }: { league: LeagueStanding }) {
  // Determine rank medal
  const getMedal = (rank: number) => {
    if (rank === 1) return <Medal className="w-4 h-4 text-amber-500" />;
    if (rank === 2) return <Medal className="w-4 h-4 text-slate-400" />;
    if (rank === 3) return <Medal className="w-4 h-4 text-amber-700" />;
    return null;
  };

  return (
    <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {getMedal(league.rank)}
        <div className="truncate">
          <p className="font-medium text-slate-800 text-sm truncate">{league.league_name}</p>
          {league.total_entries && (
            <p className="text-xs text-slate-500">
              {league.total_entries.toLocaleString()} managers
            </p>
          )}
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold text-emerald-600">#{league.rank}</p>
      </div>
    </div>
  );
}
