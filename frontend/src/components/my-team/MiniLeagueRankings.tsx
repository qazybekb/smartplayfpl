"use client";

import { useEffect, useState } from "react";
import { Trophy } from "lucide-react";
import { getRivalIntelligence, type RivalIntelligenceResponse } from "@/lib/api";

interface MiniLeagueRankingsProps {
  teamId: string;
  embedded?: boolean;
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${Math.round(num / 1000)}k`;
  return num.toLocaleString();
}

export default function MiniLeagueRankings({ teamId, embedded = false }: MiniLeagueRankingsProps) {
  const [data, setData] = useState<RivalIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRivalIntelligence(teamId)
      .then(setData)
      .catch(() => {}) // Silent fail
      .finally(() => setLoading(false));
  }, [teamId]);

  if (loading) {
    const content = (
      <div className="animate-pulse flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 rounded-full" />
        <div className="flex-1">
          <div className="h-3 bg-white/20 rounded w-32 mb-2" />
          <div className="flex gap-4">
            <div className="h-5 bg-white/20 rounded w-16" />
            <div className="h-5 bg-white/20 rounded w-16" />
            <div className="h-5 bg-white/20 rounded w-16" />
          </div>
        </div>
      </div>
    );

    if (embedded) return <div className="px-6 py-3">{content}</div>;

    return (
      <div className="bg-gradient-to-r from-violet-500 to-indigo-500 rounded-xl px-4 py-3 shadow-lg shadow-violet-200">
        {content}
      </div>
    );
  }

  if (!data || data.leagues.length === 0) {
    return null; // Don't show if no leagues
  }

  const content = (
    <div className="flex items-center gap-3">
      <div className="p-2 rounded-full bg-white/20">
        <Trophy className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white/80 text-xs font-medium uppercase tracking-wide mb-1">
          Mini-League Rankings
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {data.leagues.slice(0, 4).map((league) => (
            <div key={league.league_id} className="flex items-baseline gap-1.5">
              <span className="text-white font-bold text-lg">
                #{formatNumber(league.rank)}
              </span>
              <span className="text-white/70 text-xs truncate max-w-[100px]">
                {league.league_name}
              </span>
            </div>
          ))}
          {data.leagues.length > 4 && (
            <span className="text-white/60 text-xs self-center">
              +{data.leagues.length - 4} more
            </span>
          )}
        </div>
      </div>
    </div>
  );

  if (embedded) {
    return <div className="px-6 py-3">{content}</div>;
  }

  return (
    <div className="bg-gradient-to-r from-emerald-500 to-green-500 rounded-xl px-4 py-3 shadow-lg shadow-emerald-200">
      {content}
    </div>
  );
}
