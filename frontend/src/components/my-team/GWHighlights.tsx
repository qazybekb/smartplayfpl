"use client";

import { TrendingUp, Shield, Users } from "lucide-react";
import type { TeamAnalysisResponse } from "@/lib/api";

interface GWHighlightsProps {
  teamData: TeamAnalysisResponse;
}

export default function GWHighlights({ teamData }: GWHighlightsProps) {
  const allPlayers = [...teamData.squad.starting, ...teamData.squad.bench];

  // Get top scorer
  const topScorer = allPlayers.reduce((top, p) =>
    (p.gw_points || 0) > (top?.gw_points || 0) ? p : top
  );

  // Get captain
  const captain = teamData.squad.starting.find((p) => p.is_captain);

  // Bench points
  const benchPoints = teamData.squad.bench.reduce((acc, p) => acc + (p.gw_points || 0), 0);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-800">GW Highlights</h2>
      </div>
      <div className="p-4 space-y-4">
        {/* Top Scorer */}
        {topScorer && (
          <div className="flex items-center gap-4 p-3 bg-amber-50 rounded-xl border border-amber-200">
            <div className="w-10 h-10 bg-amber-500 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-xs text-amber-600 font-medium">Top Scorer</p>
              <p className="font-bold text-slate-800">{topScorer.name}</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-amber-600">{topScorer.gw_points}</p>
              <p className="text-xs text-slate-500">pts</p>
            </div>
          </div>
        )}

        {/* Captain */}
        {captain && (
          <div className="flex items-center gap-4 p-3 bg-emerald-50 rounded-xl border border-emerald-200">
            <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-xs text-emerald-600 font-medium">Captain</p>
              <p className="font-bold text-slate-800">{captain.name}</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-emerald-600">
                {(captain.gw_points || 0) * 2}
              </p>
              <p className="text-xs text-slate-500">pts (2x)</p>
            </div>
          </div>
        )}

        {/* Bench Points */}
        <div className="flex items-center gap-4 p-3 bg-slate-50 rounded-xl border border-slate-200">
          <div className="w-10 h-10 bg-slate-500 rounded-lg flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <p className="text-xs text-slate-500 font-medium">Bench Points</p>
            <p className="font-bold text-slate-800">Left on bench</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-slate-600">{benchPoints}</p>
            <p className="text-xs text-slate-500">pts</p>
          </div>
        </div>
      </div>
    </div>
  );
}
