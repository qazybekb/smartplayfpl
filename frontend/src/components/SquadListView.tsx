"use client";

import { cn } from "@/lib/utils";
import { AlertCircle, Star, Shield, TrendingUp } from "lucide-react";

interface Player {
  id: number;
  web_name: string;
  position: string;
  team_short: string;
  price: number;
  form: number;
  ownership: number;
  total_points?: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
  gw_points?: number;
  status?: string;
  news?: string;
}

interface MLScore {
  final_score: number;
  rank: number;
}

interface SquadListViewProps {
  players: Player[];
  mlScores?: Record<number, MLScore>;
  highlightedPlayerIds?: Set<number>;
  transferOutIds?: Set<number>;
  transferInIds?: Set<number>;
  onPlayerClick?: (player: Player) => void;
  className?: string;
}

const positionOrder = { GKP: 1, DEF: 2, MID: 3, FWD: 4 };
const positionColors = {
  GKP: "bg-amber-500",
  DEF: "bg-emerald-500",
  MID: "bg-blue-500",
  FWD: "bg-red-500",
};

export default function SquadListView({
  players,
  mlScores,
  highlightedPlayerIds = new Set(),
  transferOutIds = new Set(),
  transferInIds = new Set(),
  onPlayerClick,
  className,
}: SquadListViewProps) {
  // Separate starters and bench
  const starters = players.filter((p) => p.is_starter);
  const bench = players.filter((p) => !p.is_starter);

  // Sort by position
  const sortedStarters = [...starters].sort(
    (a, b) => (positionOrder[a.position as keyof typeof positionOrder] || 5) - (positionOrder[b.position as keyof typeof positionOrder] || 5)
  );
  const sortedBench = [...bench].sort(
    (a, b) => (positionOrder[a.position as keyof typeof positionOrder] || 5) - (positionOrder[b.position as keyof typeof positionOrder] || 5)
  );

  const renderPlayer = (player: Player, index: number) => {
    const isHighlighted = highlightedPlayerIds.has(player.id);
    const isTransferOut = transferOutIds.has(player.id);
    const isTransferIn = transferInIds.has(player.id);
    const mlScore = mlScores?.[player.id];
    const hasIssue = player.status && player.status !== "a";

    return (
      <button
        key={player.id}
        onClick={() => onPlayerClick?.(player)}
        className={cn(
          "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left",
          "hover:bg-slate-50 active:bg-slate-100",
          isHighlighted && "bg-violet-50 ring-2 ring-violet-300",
          isTransferOut && "bg-red-50 ring-2 ring-red-300 opacity-75",
          isTransferIn && "bg-emerald-50 ring-2 ring-emerald-300",
          !isHighlighted && !isTransferOut && !isTransferIn && "bg-white"
        )}
        aria-label={`${player.web_name}, ${player.position}, ${player.team_short}`}
      >
        {/* Position Badge */}
        <div
          className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0",
            positionColors[player.position as keyof typeof positionColors] || "bg-slate-500"
          )}
        >
          {player.position}
        </div>

        {/* Player Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-slate-800 truncate">
              {player.web_name}
            </span>
            {player.is_captain && (
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] font-bold flex items-center justify-center" title="Captain">
                C
              </span>
            )}
            {player.is_vice_captain && (
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-slate-400 text-white text-[10px] font-bold flex items-center justify-center" title="Vice Captain">
                V
              </span>
            )}
            {hasIssue && (
              <AlertCircle className="flex-shrink-0 w-4 h-4 text-amber-500" />
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>{player.team_short}</span>
            <span className="text-slate-300">|</span>
            <span>{player.price.toFixed(1)}m</span>
            {player.form > 0 && (
              <>
                <span className="text-slate-300">|</span>
                <span className="flex items-center gap-0.5">
                  <TrendingUp className="w-3 h-3" />
                  {player.form.toFixed(1)}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {mlScore && (
            <div className="text-center">
              <div className="text-xs text-slate-400">SP</div>
              <div className={cn(
                "text-sm font-bold",
                mlScore.final_score >= 70 ? "text-emerald-600" :
                mlScore.final_score >= 50 ? "text-blue-600" :
                "text-slate-600"
              )}>
                {mlScore.final_score.toFixed(0)}
              </div>
            </div>
          )}
          {player.gw_points !== undefined && (
            <div className="text-center">
              <div className="text-xs text-slate-400">GW</div>
              <div className={cn(
                "text-sm font-bold",
                player.gw_points >= 10 ? "text-emerald-600" :
                player.gw_points >= 5 ? "text-blue-600" :
                player.gw_points > 0 ? "text-slate-600" :
                "text-red-500"
              )}>
                {player.gw_points}
              </div>
            </div>
          )}
          {player.total_points !== undefined && (
            <div className="text-center">
              <div className="text-xs text-slate-400">Tot</div>
              <div className="text-sm font-semibold text-slate-700">
                {player.total_points}
              </div>
            </div>
          )}
        </div>
      </button>
    );
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Starting XI */}
      <div>
        <div className="flex items-center gap-2 mb-2 px-1">
          <Star className="w-4 h-4 text-emerald-500" />
          <h3 className="text-sm font-semibold text-slate-700">Starting XI</h3>
          <span className="text-xs text-slate-400">({sortedStarters.length})</span>
        </div>
        <div className="space-y-1 bg-slate-50/50 rounded-xl p-2 border border-slate-100">
          {sortedStarters.map((player, index) => renderPlayer(player, index))}
        </div>
      </div>

      {/* Bench */}
      {sortedBench.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2 px-1">
            <Shield className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-500">Bench</h3>
            <span className="text-xs text-slate-400">({sortedBench.length})</span>
          </div>
          <div className="space-y-1 bg-slate-50/50 rounded-xl p-2 border border-slate-100 opacity-75">
            {sortedBench.map((player, index) => renderPlayer(player, index))}
          </div>
        </div>
      )}
    </div>
  );
}
