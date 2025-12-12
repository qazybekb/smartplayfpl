"use client";

import { useState } from "react";
import { Crown, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";

// Types
interface Player {
  id: number;
  web_name: string;
  full_name: string;
  position: string;
  team_id?: number;
  team_short: string;
  price: number;
  form: number;
  ownership: number;
  total_points?: number;
  points_per_million?: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
  smart_tags: string[];
  selection_reason: string;
  bench_order?: number;
  gw_points?: number; // Gameweek points
  status?: string; // 'a' = available, 'd' = doubtful, 'i' = injured, 's' = suspended
  news?: string;
}

interface MLScore {
  final_score: number;
  rank: number;
  nailedness_score: number;
  form_xg_score: number;
  form_pts_score: number;
  fixture_score: number;
}

type PitchMode = "normal" | "review" | "alerts" | "squad" | "transfers" | "lineup" | "captain" | "confirm" | "preview" | "feedback";

interface PitchVisualizationProps {
  players: Player[];
  formation: string;
  onPlayerClick?: (player: Player) => void;
  strategyColor?: string;
  mlScores?: Record<number, MLScore>; // player_id -> ML score
  // Visual mode props for transfer workflow
  pitchMode?: PitchMode;
  highlightedPlayerIds?: Set<number>;  // Players to highlight (e.g., underperformers)
  transferOutIds?: Set<number>;        // Players being transferred out (red glow)
  transferInIds?: Set<number>;         // Players transferred in (green glow)
}

// Formation position mappings (percentages on pitch)
const FORMATION_POSITIONS: Record<string, Record<string, { top: number; left: number }[]>> = {
  "4-4-2": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 15 },
      { top: 72, left: 38 },
      { top: 72, left: 62 },
      { top: 72, left: 85 },
    ],
    MID: [
      { top: 48, left: 15 },
      { top: 48, left: 38 },
      { top: 48, left: 62 },
      { top: 48, left: 85 },
    ],
    FWD: [
      { top: 22, left: 35 },
      { top: 22, left: 65 },
    ],
  },
  "4-3-3": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 15 },
      { top: 72, left: 38 },
      { top: 72, left: 62 },
      { top: 72, left: 85 },
    ],
    MID: [
      { top: 48, left: 25 },
      { top: 48, left: 50 },
      { top: 48, left: 75 },
    ],
    FWD: [
      { top: 22, left: 20 },
      { top: 22, left: 50 },
      { top: 22, left: 80 },
    ],
  },
  "3-4-3": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 25 },
      { top: 72, left: 50 },
      { top: 72, left: 75 },
    ],
    MID: [
      { top: 48, left: 15 },
      { top: 48, left: 38 },
      { top: 48, left: 62 },
      { top: 48, left: 85 },
    ],
    FWD: [
      { top: 22, left: 20 },
      { top: 22, left: 50 },
      { top: 22, left: 80 },
    ],
  },
  "3-5-2": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 25 },
      { top: 72, left: 50 },
      { top: 72, left: 75 },
    ],
    MID: [
      { top: 48, left: 10 },
      { top: 48, left: 30 },
      { top: 48, left: 50 },
      { top: 48, left: 70 },
      { top: 48, left: 90 },
    ],
    FWD: [
      { top: 22, left: 35 },
      { top: 22, left: 65 },
    ],
  },
  "5-4-1": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 10 },
      { top: 72, left: 28 },
      { top: 72, left: 50 },
      { top: 72, left: 72 },
      { top: 72, left: 90 },
    ],
    MID: [
      { top: 48, left: 15 },
      { top: 48, left: 38 },
      { top: 48, left: 62 },
      { top: 48, left: 85 },
    ],
    FWD: [{ top: 22, left: 50 }],
  },
  "5-3-2": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 10 },
      { top: 72, left: 28 },
      { top: 72, left: 50 },
      { top: 72, left: 72 },
      { top: 72, left: 90 },
    ],
    MID: [
      { top: 48, left: 25 },
      { top: 48, left: 50 },
      { top: 48, left: 75 },
    ],
    FWD: [
      { top: 22, left: 35 },
      { top: 22, left: 65 },
    ],
  },
  "4-5-1": {
    GKP: [{ top: 90, left: 50 }],
    DEF: [
      { top: 72, left: 15 },
      { top: 72, left: 38 },
      { top: 72, left: 62 },
      { top: 72, left: 85 },
    ],
    MID: [
      { top: 48, left: 10 },
      { top: 48, left: 30 },
      { top: 48, left: 50 },
      { top: 48, left: 70 },
      { top: 48, left: 90 },
    ],
    FWD: [{ top: 22, left: 50 }],
  },
};

// Position colors
const POSITION_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  GKP: { bg: "from-amber-400 to-yellow-500", border: "border-amber-300", text: "text-amber-900" },
  DEF: { bg: "from-emerald-400 to-green-500", border: "border-emerald-300", text: "text-emerald-900" },
  MID: { bg: "from-blue-400 to-indigo-500", border: "border-blue-300", text: "text-blue-900" },
  FWD: { bg: "from-rose-400 to-red-500", border: "border-rose-300", text: "text-rose-900" },
};

export default function PitchVisualization({
  players,
  formation,
  onPlayerClick,
  strategyColor = "emerald",
  mlScores,
  pitchMode = "normal",
  highlightedPlayerIds = new Set(),
  transferOutIds = new Set(),
  transferInIds = new Set(),
}: PitchVisualizationProps) {
  const [hoveredPlayer, setHoveredPlayer] = useState<number | null>(null);

  // Helper to get visual state for a player
  const getPlayerVisualState = (playerId: number) => {
    if (transferInIds.has(playerId)) return "transfer-in";
    if (transferOutIds.has(playerId)) return "transfer-out";
    if (highlightedPlayerIds.has(playerId)) return "highlighted";
    return "normal";
  };
  
  // Get starters and bench
  const starters = players.filter(p => p.is_starter);
  const bench = players.filter(p => !p.is_starter).sort((a, b) => {
    // GKP first, then by position
    if (a.position === "GKP") return -1;
    if (b.position === "GKP") return 1;
    return 0;
  });

  // Group starters by position
  const startersByPosition: Record<string, Player[]> = {
    GKP: starters.filter(p => p.position === "GKP"),
    DEF: starters.filter(p => p.position === "DEF"),
    MID: starters.filter(p => p.position === "MID"),
    FWD: starters.filter(p => p.position === "FWD"),
  };

  // Calculate actual formation from players
  const actualFormation = `${startersByPosition.DEF.length}-${startersByPosition.MID.length}-${startersByPosition.FWD.length}`;

  // Get formation positions - prefer actual formation, then passed formation, then default
  const positions = FORMATION_POSITIONS[actualFormation] || FORMATION_POSITIONS[formation] || FORMATION_POSITIONS["4-4-2"];

  // Generate dynamic positions for a given count at a row
  const generateDynamicPositions = (count: number, topPercent: number): { top: number; left: number }[] => {
    if (count === 1) return [{ top: topPercent, left: 50 }];
    if (count === 2) return [{ top: topPercent, left: 35 }, { top: topPercent, left: 65 }];
    if (count === 3) return [{ top: topPercent, left: 25 }, { top: topPercent, left: 50 }, { top: topPercent, left: 75 }];
    if (count === 4) return [{ top: topPercent, left: 15 }, { top: topPercent, left: 38 }, { top: topPercent, left: 62 }, { top: topPercent, left: 85 }];
    if (count === 5) return [{ top: topPercent, left: 10 }, { top: topPercent, left: 28 }, { top: topPercent, left: 50 }, { top: topPercent, left: 72 }, { top: topPercent, left: 90 }];
    // For 6+, distribute evenly
    const spacing = 80 / (count - 1);
    return Array.from({ length: count }, (_, i) => ({ top: topPercent, left: 10 + i * spacing }));
  };

  // Position rows (top percentages)
  const POSITION_ROWS: Record<string, number> = {
    GKP: 90,
    DEF: 72,
    MID: 48,
    FWD: 22,
  };

  // Assign positions to players - dynamically calculate if needed
  const getPlayerPosition = (player: Player, index: number): { top: number; left: number } => {
    const positionSlots = positions[player.position] || [];

    // If we have a predefined slot, use it
    if (positionSlots[index]) {
      return positionSlots[index];
    }

    // Otherwise, dynamically generate positions based on actual player count
    const playersInPosition = startersByPosition[player.position]?.length || 1;
    const dynamicSlots = generateDynamicPositions(playersInPosition, POSITION_ROWS[player.position] || 50);
    return dynamicSlots[index] || { top: 50, left: 50 };
  };

  // Get form color
  const getFormColor = (form: number) => {
    if (form >= 7) return "text-emerald-400";
    if (form >= 5) return "text-amber-400";
    return "text-red-400";
  };

  // Render player on pitch
  const renderPlayer = (player: Player, index: number) => {
    const pos = getPlayerPosition(player, index);
    const isHovered = hoveredPlayer === player.id;
    const posColors = POSITION_COLORS[player.position];
    const visualState = getPlayerVisualState(player.id);

    // Visual effect classes based on mode
    const glowEffect =
      visualState === "transfer-out" ? "ring-4 ring-red-500/60 ring-offset-2 ring-offset-transparent" :
      visualState === "transfer-in" ? "ring-4 ring-emerald-500/60 ring-offset-2 ring-offset-transparent" :
      visualState === "highlighted" && pitchMode === "review" ? "ring-4 ring-amber-500/60 ring-offset-2 ring-offset-transparent" :
      visualState === "highlighted" && pitchMode === "transfers" ? "ring-4 ring-red-400/50 ring-offset-2 ring-offset-transparent" :
      "";

    return (
      <div
        key={player.id}
        className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300 ease-out cursor-pointer group"
        style={{
          top: `${pos.top}%`,
          left: `${pos.left}%`,
          zIndex: isHovered ? 50 : 10,
        }}
        onMouseEnter={() => setHoveredPlayer(player.id)}
        onMouseLeave={() => setHoveredPlayer(null)}
        onClick={() => onPlayerClick?.(player)}
      >
        {/* Player Card */}
        <div
          className={`relative transition-all duration-300 ${
            isHovered ? "scale-125" : "scale-100"
          } ${glowEffect} rounded-full`}
        >
          {/* Captain/VC Badge */}
          {(player.is_captain || player.is_vice_captain) && (
            <div
              className={`absolute -top-2 -right-2 z-20 w-6 h-6 rounded-full flex items-center justify-center shadow-lg ${
                player.is_captain
                  ? "bg-gradient-to-br from-amber-400 to-yellow-500"
                  : "bg-gradient-to-br from-slate-400 to-slate-500"
              }`}
            >
              {player.is_captain ? (
                <Crown className="w-3.5 h-3.5 text-amber-900" />
              ) : (
                <span className="text-[10px] font-bold text-white">V</span>
              )}
            </div>
          )}

          {/* Injury/Status Badge */}
          {player.status && player.status !== 'a' && (
            <div
              className={`absolute -top-2 -left-2 z-20 w-6 h-6 rounded-full flex items-center justify-center shadow-lg ${
                player.status === 'i' ? "bg-gradient-to-br from-red-500 to-red-600" :
                player.status === 's' ? "bg-gradient-to-br from-red-500 to-red-600" :
                "bg-gradient-to-br from-amber-400 to-amber-500"
              }`}
              title={player.news || (player.status === 'i' ? 'Injured' : player.status === 's' ? 'Suspended' : 'Doubtful')}
            >
              <AlertTriangle className={`w-3.5 h-3.5 ${
                player.status === 'i' || player.status === 's' ? "text-white" : "text-amber-900"
              }`} />
            </div>
          )}

          {/* NEW Transfer Badge - shows "IN" for newly transferred-in players */}
          {visualState === "transfer-in" && (
            <div
              className="absolute -bottom-1 -right-1 z-20 px-1.5 py-0.5 rounded-full flex items-center justify-center shadow-lg bg-gradient-to-br from-emerald-400 to-emerald-600 border-2 border-white"
              title="Planned Transfer In"
            >
              <span className="text-[9px] font-bold text-white tracking-wide">IN</span>
            </div>
          )}

          {/* Main Player Circle - larger on mobile for better touch targets */}
          <div
            className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-gradient-to-br ${posColors.bg} shadow-xl border-2 ${posColors.border} flex items-center justify-center relative overflow-hidden touch-manipulation`}
          >
            {/* Jersey Number / Initials */}
            <span className={`text-base sm:text-lg font-bold ${posColors.text} drop-shadow-sm`}>
              {player.web_name.substring(0, 2).toUpperCase()}
            </span>
            
            {/* Shine effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-white/30 to-transparent rounded-full" />
          </div>

          {/* Player Name Tag with Score - Mode-aware display, improved mobile readability */}
          <div className="absolute -bottom-7 sm:-bottom-6 left-1/2 transform -translate-x-1/2 whitespace-nowrap">
            <div className="bg-slate-900/90 backdrop-blur-sm px-1.5 sm:px-2 py-0.5 sm:py-1 rounded-md shadow-lg border border-slate-700/50">
              <p className="text-[9px] sm:text-[10px] font-bold text-white text-center truncate max-w-[60px] sm:max-w-[70px]">
                {player.web_name}
              </p>
              {/* Review mode: Show GW points with label, SmartPlay on hover */}
              {pitchMode === "review" ? (
                player.gw_points !== undefined ? (() => {
                  const effectivePoints = player.is_captain ? player.gw_points * 2 : player.gw_points;
                  return (
                    <p className={`text-[9px] font-bold text-center ${
                      effectivePoints >= 10 ? "text-emerald-400" :
                      effectivePoints >= 5 ? "text-cyan-400" :
                      effectivePoints > 0 ? "text-slate-400" : "text-red-400"
                    }`}>
                      <span className="text-[7px] text-slate-500">GW</span> {effectivePoints}
                    </p>
                  );
                })() : null
              ) : (
                /* All other modes: Show SmartPlay score with label */
                mlScores && mlScores[player.id] ? (
                  <p className={`text-[9px] font-bold text-center ${
                    mlScores[player.id].final_score >= 7.5 ? "text-emerald-400" :
                    mlScores[player.id].final_score >= 6.0 ? "text-cyan-400" :
                    mlScores[player.id].final_score >= 4.5 ? "text-amber-400" : "text-slate-400"
                  }`}>
                    <span className="text-[7px] text-slate-500">SP</span> {mlScores[player.id].final_score.toFixed(1)}
                  </p>
                ) : player.gw_points !== undefined ? (() => {
                  const effectivePoints = player.is_captain ? player.gw_points * 2 : player.gw_points;
                  return (
                    <p className={`text-[9px] font-bold text-center ${
                      effectivePoints >= 10 ? "text-emerald-400" :
                      effectivePoints >= 5 ? "text-cyan-400" :
                      effectivePoints > 0 ? "text-slate-400" : "text-red-400"
                    }`}>
                      <span className="text-[7px] text-slate-500">GW</span> {effectivePoints}
                    </p>
                  );
                })() : null
              )}
            </div>
          </div>

          {/* Expanded Info on Hover */}
          {isHovered && (
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-8 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="bg-slate-900/95 backdrop-blur-md rounded-xl p-3 shadow-2xl border border-slate-700/50 min-w-[180px]">
                {/* Player Info */}
                <div className="text-center mb-2">
                  <p className="text-sm font-bold text-white">{player.web_name}</p>
                  <p className="text-[10px] text-slate-400">{player.team_short} • {player.position}</p>
                </div>

                {/* Status/News Alert */}
                {player.news && (
                  <div className={`mb-2 rounded-lg p-2 text-[10px] ${
                    player.status === 'i' || player.status === 's'
                      ? "bg-red-500/20 border border-red-500/30 text-red-300"
                      : "bg-amber-500/20 border border-amber-500/30 text-amber-300"
                  }`}>
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                      <span className="line-clamp-2">{player.news}</span>
                    </div>
                  </div>
                )}

                {/* SmartPlay Score - Prominent Display */}
                {mlScores && mlScores[player.id] && (
                  <div className="mb-2 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-lg p-2 border border-cyan-500/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] text-cyan-400 font-semibold uppercase">SmartPlay Score</span>
                      <span className="text-[8px] text-cyan-300/70">#{mlScores[player.id].rank}</span>
                    </div>
                    <div className="flex items-baseline gap-1 justify-center">
                      <span className={`text-xl font-bold ${
                        mlScores[player.id].final_score >= 7 ? "text-emerald-400" :
                        mlScores[player.id].final_score >= 5 ? "text-cyan-400" :
                        mlScores[player.id].final_score >= 3 ? "text-amber-400" : "text-slate-400"
                      }`}>
                        {mlScores[player.id].final_score.toFixed(1)}
                      </span>
                      <span className="text-[10px] text-slate-400">/10</span>
                    </div>
                    {/* Mini breakdown */}
                    <div className="grid grid-cols-4 gap-1 mt-1.5">
                      <div className="text-center">
                        <p className="text-[7px] text-slate-400">Nail</p>
                        <p className="text-[9px] font-bold text-violet-400">
                          {mlScores[player.id].nailedness_score.toFixed(0)}
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-[7px] text-slate-400">xG</p>
                        <p className="text-[9px] font-bold text-orange-400">
                          {mlScores[player.id].form_xg_score.toFixed(0)}
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-[7px] text-slate-400">Pts</p>
                        <p className="text-[9px] font-bold text-emerald-400">
                          {mlScores[player.id].form_pts_score.toFixed(0)}
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-[7px] text-slate-400">Fix</p>
                        <p className="text-[9px] font-bold text-blue-400">
                          {mlScores[player.id].fixture_score.toFixed(0)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* GW Points Highlight (when no mlScores) */}
                {!mlScores && player.gw_points !== undefined && (() => {
                  const effectivePoints = player.is_captain ? player.gw_points * 2 : player.gw_points;
                  return (
                    <div className={`mb-2 rounded-lg p-2 text-center ${
                      effectivePoints >= 10 ? "bg-emerald-500/20 border border-emerald-500/30" :
                      effectivePoints >= 5 ? "bg-cyan-500/20 border border-cyan-500/30" :
                      effectivePoints > 0 ? "bg-slate-700/50 border border-slate-600/30" :
                      "bg-red-500/20 border border-red-500/30"
                    }`}>
                      <p className="text-[9px] text-slate-400 uppercase mb-0.5">
                        This GW {player.is_captain && <span className="text-amber-400">(C)</span>}
                      </p>
                      <p className={`text-xl font-bold ${
                        effectivePoints >= 10 ? "text-emerald-400" :
                        effectivePoints >= 5 ? "text-cyan-400" :
                        effectivePoints > 0 ? "text-white" : "text-red-400"
                      }`}>
                        {effectivePoints} <span className="text-xs text-slate-400">pts</span>
                      </p>
                      {player.is_captain && (
                        <p className="text-[8px] text-amber-400/70 mt-0.5">({player.gw_points} × 2)</p>
                      )}
                    </div>
                  );
                })()}

                
                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="bg-slate-800/50 rounded-lg px-2 py-1.5">
                    <p className="text-[9px] text-slate-500 uppercase">Price</p>
                    <p className="text-xs font-bold text-white">£{player.price}m</p>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg px-2 py-1.5">
                    <p className="text-[9px] text-slate-500 uppercase">Form</p>
                    <p className={`text-xs font-bold flex items-center justify-center gap-0.5 ${getFormColor(player.form)}`}>
                      {player.form >= 5 ? <TrendingUp className="w-3 h-3" /> : player.form < 3 ? <TrendingDown className="w-3 h-3" /> : null}
                      {player.form.toFixed(1)}
                    </p>
                  </div>
                </div>

                {/* Additional Stats */}
                <div className="grid grid-cols-2 gap-2 text-center mt-2">
                  {player.total_points !== undefined && (
                    <div className="bg-slate-800/50 rounded-lg px-2 py-1.5">
                      <p className="text-[9px] text-slate-500 uppercase">Total Pts</p>
                      <p className="text-xs font-bold text-white">{player.total_points}</p>
                    </div>
                  )}
                  {player.ownership !== undefined && (
                    <div className="bg-slate-800/50 rounded-lg px-2 py-1.5">
                      <p className="text-[9px] text-slate-500 uppercase">Owned</p>
                      <p className={`text-xs font-bold ${
                        player.ownership >= 30 ? "text-violet-400" :
                        player.ownership >= 10 ? "text-white" : "text-emerald-400"
                      }`}>
                        {player.ownership.toFixed(1)}%
                      </p>
                    </div>
                  )}
                </div>

                {/* Tags */}
                {player.smart_tags.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1 justify-center">
                    {player.smart_tags.slice(0, 2).map((tag) => (
                      <span
                        key={tag}
                        className="text-[8px] px-1.5 py-0.5 rounded-full bg-slate-700 text-slate-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Selection Reason */}
                {player.selection_reason && (
                  <p className="text-[9px] text-slate-500 text-center mt-2 italic line-clamp-2">
                    {player.selection_reason}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="w-full">
      {/* Pitch Container */}
      <div className="relative w-full aspect-[3/4] max-w-lg mx-auto">
        {/* Pitch Background */}
        <div className="absolute inset-0 rounded-2xl overflow-hidden shadow-2xl">
          {/* Grass Base */}
          <div className="absolute inset-0 bg-gradient-to-b from-emerald-600 via-emerald-500 to-emerald-600" />
          
          {/* Grass Stripes */}
          <div className="absolute inset-0">
            {[...Array(12)].map((_, i) => (
              <div
                key={i}
                className={`absolute w-full h-[8.33%] ${
                  i % 2 === 0 ? "bg-emerald-500/30" : "bg-emerald-600/30"
                }`}
                style={{ top: `${i * 8.33}%` }}
              />
            ))}
          </div>

          {/* Pitch Markings */}
          <svg
            className="absolute inset-0 w-full h-full"
            viewBox="0 0 100 133"
            preserveAspectRatio="none"
          >
            {/* Outer Border */}
            <rect
              x="5"
              y="5"
              width="90"
              height="123"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Center Line */}
            <line
              x1="5"
              y1="66.5"
              x2="95"
              y2="66.5"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Center Circle */}
            <circle
              cx="50"
              cy="66.5"
              r="12"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Center Spot */}
            <circle cx="50" cy="66.5" r="0.8" fill="rgba(255,255,255,0.6)" />

            {/* Top Penalty Area */}
            <rect
              x="22"
              y="5"
              width="56"
              height="22"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Top Goal Area */}
            <rect
              x="34"
              y="5"
              width="32"
              height="8"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Top Penalty Spot */}
            <circle cx="50" cy="18" r="0.6" fill="rgba(255,255,255,0.6)" />

            {/* Top Penalty Arc */}
            <path
              d="M 34 27 Q 50 35 66 27"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Bottom Penalty Area */}
            <rect
              x="22"
              y="106"
              width="56"
              height="22"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Bottom Goal Area */}
            <rect
              x="34"
              y="120"
              width="32"
              height="8"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Bottom Penalty Spot */}
            <circle cx="50" cy="115" r="0.6" fill="rgba(255,255,255,0.6)" />

            {/* Bottom Penalty Arc */}
            <path
              d="M 34 106 Q 50 98 66 106"
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth="0.5"
            />

            {/* Corner Arcs */}
            <path d="M 5 8 Q 8 5 11 5" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.5" />
            <path d="M 89 5 Q 92 5 95 8" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.5" />
            <path d="M 5 125 Q 8 128 11 128" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.5" />
            <path d="M 89 128 Q 92 128 95 125" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="0.5" />
          </svg>

          {/* Ambient Light Effect */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-black/10" />
        </div>

        {/* Players */}
        <div className="absolute inset-0">
          {Object.entries(startersByPosition).map(([position, positionPlayers]) =>
            positionPlayers.map((player, idx) => renderPlayer(player, idx))
          )}
        </div>

        {/* Formation Badge - shows actual formation from players */}
        <div className="absolute top-3 right-3 z-20">
          <div className="bg-slate-900/80 backdrop-blur-sm px-3 py-1.5 rounded-full border border-slate-700/50">
            <span className="text-sm font-bold text-white">{actualFormation}</span>
          </div>
        </div>
      </div>

      {/* Bench Section - Responsive grid for mobile */}
      <div className="mt-4 sm:mt-6 px-2 sm:px-4">
        <div className="flex items-center gap-2 mb-2 sm:mb-3">
          <div className="w-1 h-4 bg-emerald-500 rounded-full" />
          <h3 className="text-xs sm:text-sm font-bold text-slate-700 uppercase tracking-wider">Substitutes</h3>
        </div>

        <div className="grid grid-cols-4 gap-2 sm:gap-3">
          {bench.map((player, idx) => {
            const posColors = POSITION_COLORS[player.position];
            const benchVisualState = getPlayerVisualState(player.id);
            const isTransferIn = benchVisualState === "transfer-in";
            return (
              <div
                key={player.id}
                className={`group relative bg-white rounded-lg sm:rounded-xl p-2 sm:p-3 border hover:border-slate-300 hover:shadow-md transition-all cursor-pointer touch-manipulation ${
                  isTransferIn
                    ? "border-emerald-400 ring-2 ring-emerald-200 bg-emerald-50/50"
                    : "border-slate-200"
                }`}
                onClick={() => onPlayerClick?.(player)}
              >
                {/* Bench Order */}
                <div className="absolute -top-2 -left-2 w-5 h-5 rounded-full bg-slate-700 border-2 border-white flex items-center justify-center shadow-sm">
                  <span className="text-[10px] font-bold text-white">{idx + 1}</span>
                </div>

                {/* Injury/Status Badge */}
                {player.status && player.status !== 'a' && (
                  <div
                    className={`absolute -top-2 -right-2 w-5 h-5 rounded-full flex items-center justify-center shadow-sm ${
                      player.status === 'i' || player.status === 's'
                        ? "bg-red-500"
                        : "bg-amber-400"
                    }`}
                    title={player.news || (player.status === 'i' ? 'Injured' : player.status === 's' ? 'Suspended' : 'Doubtful')}
                  >
                    <AlertTriangle className={`w-3 h-3 ${
                      player.status === 'i' || player.status === 's' ? "text-white" : "text-amber-900"
                    }`} />
                  </div>
                )}

                {/* NEW Transfer Badge for bench */}
                {isTransferIn && (
                  <div
                    className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full flex items-center justify-center shadow-sm bg-gradient-to-br from-emerald-400 to-emerald-600 border-2 border-white"
                    title="Planned Transfer In"
                  >
                    <span className="text-[8px] font-bold text-white tracking-wide">NEW</span>
                  </div>
                )}

                {/* Position Badge */}
                <div
                  className={`w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br ${posColors.bg} mx-auto mb-1 sm:mb-2 flex items-center justify-center shadow-md`}
                >
                  <span className={`text-[10px] sm:text-xs font-bold ${posColors.text}`}>
                    {player.position}
                  </span>
                </div>

                {/* Player Name */}
                <p className="text-[10px] sm:text-xs font-bold text-slate-900 text-center truncate">
                  {player.web_name}
                </p>

                {/* Team */}
                <p className="text-[10px] text-slate-500 text-center">
                  {player.team_short}
                </p>

                {/* Score display - Mode-aware with data labels */}
                <div className="mt-1 flex justify-center">
                  {pitchMode === "review" ? (
                    /* Review mode: Show GW points with label */
                    player.gw_points !== undefined ? (
                      <span className={`text-xs font-bold ${
                        player.gw_points >= 10 ? "text-emerald-600" :
                        player.gw_points >= 5 ? "text-cyan-600" :
                        player.gw_points > 0 ? "text-slate-600" : "text-red-500"
                      }`}>
                        <span className="text-[9px] text-slate-400 font-normal">GW</span> {player.gw_points}
                      </span>
                    ) : null
                  ) : (
                    /* All other modes: Show SmartPlay score with label */
                    mlScores && mlScores[player.id] ? (
                      <span className={`text-xs font-bold ${
                        mlScores[player.id].final_score >= 7.5 ? "text-emerald-600" :
                        mlScores[player.id].final_score >= 6.0 ? "text-cyan-600" :
                        mlScores[player.id].final_score >= 4.5 ? "text-amber-600" : "text-slate-600"
                      }`}>
                        <span className="text-[9px] text-slate-400 font-normal">SP</span> {mlScores[player.id].final_score.toFixed(1)}
                      </span>
                    ) : player.gw_points !== undefined ? (
                      <span className={`text-xs font-bold ${
                        player.gw_points >= 10 ? "text-emerald-600" :
                        player.gw_points >= 5 ? "text-cyan-600" :
                        player.gw_points > 0 ? "text-slate-600" : "text-red-500"
                      }`}>
                        <span className="text-[9px] text-slate-400 font-normal">GW</span> {player.gw_points}
                      </span>
                    ) : null
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

