"use client";

import { Calendar, TrendingUp, ArrowUpDown } from "lucide-react";
import type { PlayerPlannerResponse, PlayerPlannerEntry } from "@/lib/api";
import { useState } from "react";

interface PlayerPlannerProps {
  plannerData: PlayerPlannerResponse | null;
  loading?: boolean;
}

const fdrColors: Record<number, { bg: string; text: string }> = {
  1: { bg: "bg-emerald-500", text: "text-white" },
  2: { bg: "bg-emerald-400", text: "text-white" },
  3: { bg: "bg-amber-400", text: "text-slate-800" },
  4: { bg: "bg-orange-500", text: "text-white" },
  5: { bg: "bg-red-500", text: "text-white" },
};

const positionOrder: Record<string, number> = { GKP: 1, DEF: 2, MID: 3, FWD: 4 };

export default function PlayerPlanner({ plannerData, loading }: PlayerPlannerProps) {
  const [sortBy, setSortBy] = useState<"position" | "form" | "points">("position");

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-slate-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!plannerData || plannerData.players.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4">Player Planner</h2>
        <p className="text-slate-500 text-sm">No fixture data available.</p>
      </div>
    );
  }

  // Sort players
  const sortedPlayers = [...plannerData.players].sort((a, b) => {
    if (sortBy === "position") {
      return (positionOrder[a.position] || 99) - (positionOrder[b.position] || 99);
    }
    if (sortBy === "form") return b.form - a.form;
    if (sortBy === "points") return b.points - a.points;
    return 0;
  });

  // Get GW numbers for header
  const gwNumbers = plannerData.players[0]?.fixtures.map((f) => f.gameweek) || [];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5 text-blue-500" />
          <h2 className="text-lg font-bold text-slate-800">Player Planner</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white"
          >
            <option value="position">Position</option>
            <option value="form">Form</option>
            <option value="points">Points</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-4 py-3 font-medium text-slate-600 sticky left-0 bg-slate-50">
                Player
              </th>
              <th className="text-center px-2 py-3 font-medium text-slate-600 w-12">
                <TrendingUp className="w-4 h-4 mx-auto" aria-label="Form" />
              </th>
              {gwNumbers.map((gw) => (
                <th key={gw} className="text-center px-1 py-3 font-medium text-slate-600 w-10">
                  {gw}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedPlayers.map((player) => (
              <tr key={player.id} className="hover:bg-slate-50">
                <td className="px-4 py-2 sticky left-0 bg-white">
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${
                      player.position === "GKP" ? "bg-amber-100 text-amber-700" :
                      player.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
                      player.position === "MID" ? "bg-blue-100 text-blue-700" :
                      "bg-rose-100 text-rose-700"
                    }`}>
                      {player.position}
                    </span>
                    <span className="font-medium text-slate-800 truncate max-w-[100px]">
                      {player.name}
                    </span>
                  </div>
                </td>
                <td className="text-center px-2 py-2">
                  <span className={`font-medium ${
                    player.form >= 6 ? "text-emerald-600" :
                    player.form >= 4 ? "text-amber-600" :
                    "text-slate-500"
                  }`}>
                    {player.form.toFixed(1)}
                  </span>
                </td>
                {player.fixtures.map((fix, idx) => {
                  const colors = fdrColors[fix.difficulty] || { bg: "bg-slate-300", text: "text-slate-800" };
                  return (
                    <td key={idx} className="text-center px-1 py-2">
                      <div
                        className={`w-8 h-8 mx-auto rounded flex items-center justify-center text-xs font-medium ${colors.bg} ${colors.text}`}
                        title={`${fix.opponent} (${fix.is_home ? "H" : "A"}) - FDR ${fix.difficulty}`}
                      >
                        {fix.opponent.slice(0, 3).toUpperCase()}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* FDR Legend */}
      <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-center gap-4">
        <span className="text-xs text-slate-500">FDR:</span>
        {[1, 2, 3, 4, 5].map((fdr) => {
          const colors = fdrColors[fdr];
          return (
            <div key={fdr} className="flex items-center gap-1">
              <div className={`w-4 h-4 rounded ${colors.bg}`} />
              <span className="text-xs text-slate-600">{fdr}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
