"use client";

import type { TeamAnalysisResponse } from "@/lib/api";

interface LeaguesPreviewProps {
  teamData: TeamAnalysisResponse;
}

export default function LeaguesPreview({ teamData }: LeaguesPreviewProps) {
  if (teamData.leagues.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-800">Mini-Leagues</h2>
      </div>
      <div className="divide-y divide-slate-100">
        {teamData.leagues.slice(0, 5).map((league) => (
          <div
            key={league.id}
            className="px-6 py-3 flex items-center justify-between"
          >
            <span className="text-sm text-slate-700 truncate max-w-[180px]">
              {league.name}
            </span>
            <span className="font-bold text-emerald-600">#{league.entry_rank}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
