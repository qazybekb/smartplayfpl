"use client";

import { Crown, TrendingUp, Calendar, Users } from "lucide-react";
import type { CaptainResponse, CaptainPick } from "@/lib/api";

interface CaptainPicksProps {
  captainData: CaptainResponse | null;
  loading?: boolean;
}

const categoryColors: Record<string, { bg: string; border: string; text: string }> = {
  safe: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700" },
  balanced: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700" },
  differential: { bg: "bg-violet-50", border: "border-violet-200", text: "text-violet-700" },
};

export default function CaptainPicks({ captainData, loading }: CaptainPicksProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!captainData || captainData.picks.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4">Captain Picks</h2>
        <p className="text-slate-500 text-sm">No captain recommendations available.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Crown className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-bold text-slate-800">Captain Picks</h2>
        </div>
        <span className="text-xs text-slate-500">GW {captainData.gameweek}</span>
      </div>

      {/* One-liner */}
      {captainData.one_liner && (
        <div className="px-6 py-3 bg-amber-50 border-b border-amber-100">
          <p className="text-sm text-amber-800">{captainData.one_liner}</p>
        </div>
      )}

      <div className="p-4 space-y-3">
        {captainData.picks.slice(0, 3).map((pick, idx) => {
          const colors = categoryColors[pick.category] || categoryColors.balanced;
          return (
            <div
              key={pick.player_id}
              className={`p-4 rounded-xl border ${colors.bg} ${colors.border}`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center font-bold text-slate-700 shadow-sm">
                    {idx + 1}
                  </div>
                  <div>
                    <p className="font-bold text-slate-800">{pick.name}</p>
                    <p className="text-xs text-slate-500">{pick.team} • {pick.position}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-lg font-bold ${colors.text}`}>
                    {(pick.total_score * 10).toFixed(1)}
                  </p>
                  <p className="text-xs text-slate-500">score</p>
                </div>
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-4 text-xs text-slate-600 mt-3">
                <div className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  <span>Form {pick.form}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  <span>{pick.fixture}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  <span>{pick.ownership.toFixed(1)}%</span>
                </div>
              </div>

              {/* Reasoning */}
              <p className="text-xs text-slate-600 mt-2 line-clamp-2">{pick.reasoning}</p>

              {/* Category badge */}
              <div className="mt-2">
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${colors.bg} ${colors.text} border ${colors.border}`}>
                  {pick.category}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
