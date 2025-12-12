"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, AlertCircle, LogOut, Clock, Calendar, X, ArrowRightLeft, Trash2, Search, LayoutGrid, List } from "lucide-react";
import { SkeletonTeamDashboard } from "@/components/ui/Skeleton";
import { getTeamAnalysis, getAllMLScores, type TeamAnalysisResponse, type PlayerSummary, type MLPlayerScore, type LineupPlayer, type BenchPlayer } from "@/lib/api";
import PitchVisualization from "@/components/PitchVisualization";
import SquadListView from "@/components/SquadListView";
import {
  ManagerHeader,
  KeyInsights,
  WorkflowTabNav,
  WorkflowStepContent,
  CrowdInsights,
  CrowdIntelligence,
  DecisionQuality,
  MiniLeagueRankings,
} from "@/components/my-team";
import {
  TransferWorkflowProvider,
  useTransferWorkflow,
} from "@/contexts/TransferWorkflowContext";
import {
  trackTeamAnalysisComplete,
  trackFunnelStep,
  trackGoalCompletion,
  trackError,
  getUserData,
  recordTeamAnalyzed,
  trackEvent,
} from "@/lib/analytics";

const STORAGE_KEY = "fpl_team_id";

// Type adapter for PitchVisualization
interface PitchPlayer {
  id: number;
  web_name: string;
  full_name: string;
  position: string;
  team_short: string;
  price: number;
  form: number;
  ownership: number;
  total_points?: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
  smart_tags: string[];
  selection_reason: string;
  gw_points?: number;
  status?: string;
  news?: string;
}

// Convert PlayerSummary to PitchPlayer
function toPitchPlayer(p: PlayerSummary, isStarter: boolean): PitchPlayer {
  return {
    id: p.id,
    web_name: p.name,
    full_name: p.name,
    position: p.position,
    team_short: p.team,
    price: p.price,
    form: p.form,
    ownership: p.ownership,
    total_points: p.points,
    is_starter: isStarter,
    is_captain: p.is_captain,
    is_vice_captain: p.is_vice_captain,
    smart_tags: [],
    selection_reason: "",
    gw_points: p.gw_points,
    status: p.status,
    news: p.news,
  };
}

// Countdown hook
function useDeadlineCountdown(deadlineTime: string) {
  const [timeLeft, setTimeLeft] = useState<{ days: number; hours: number; minutes: number; seconds: number; isUrgent: boolean } | null>(null);

  useEffect(() => {
    const deadline = new Date(deadlineTime);

    const calculateTimeLeft = () => {
      const now = new Date();
      const diff = deadline.getTime() - now.getTime();

      if (diff <= 0) {
        return null;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      const isUrgent = diff < 1000 * 60 * 60 * 24; // Less than 24 hours

      return { days, hours, minutes, seconds, isUrgent };
    };

    setTimeLeft(calculateTimeLeft());

    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);

    return () => clearInterval(timer);
  }, [deadlineTime]);

  return timeLeft;
}

// MLScore type for PitchVisualization (subset of MLPlayerScore)
interface MLScore {
  final_score: number;
  rank: number;
  nailedness_score: number;
  form_xg_score: number;
  form_pts_score: number;
  fixture_score: number;
}

// Inner component that uses the workflow context
function TeamDashboardInner({
  teamData,
  teamId,
  onLogout,
  mlScores,
}: {
  teamData: TeamAnalysisResponse;
  teamId: string;
  onLogout: () => void;
  mlScores: Record<number, MLScore>;
}) {
  const {
    step,
    pitchMode,
    highlightedPlayerIds,
    transferOutIds,
    transferInIds,
    previewSquad,
    originalSquad,
    optimizedSquad,
    optimizedFormation,
    lineup,
    selectedStrategy,
    setSelectedPlayerForCard,
    setSelectedPlayerForAlternatives,
    wizardSelections,
    sellAnalysis,
    buyAnalysis,
    updateWizardSelection,
    clearWizardSelections,
  } = useTransferWorkflow();

  // Pitch always shows projected lineup when there are planned transfers
  const hasPlannedTransfers = transferOutIds.size > 0;

  const timeLeft = useDeadlineCountdown(teamData.gameweek.deadline_time);

  // View mode state for mobile-friendly list toggle
  // Default to list view on mobile (< 768px) for better usability
  const [viewMode, setViewMode] = useState<"pitch" | "list">(() => {
    // Check if window exists (client-side) and if it's mobile
    if (typeof window !== "undefined") {
      return window.innerWidth < 768 ? "list" : "pitch";
    }
    return "pitch"; // Default for SSR
  });

  // Update view mode when window resizes (only set default, don't force)
  useEffect(() => {
    const handleResize = () => {
      // Only auto-switch on initial mount based on screen size
      // Don't force switch if user has manually changed it
    };

    // Set initial view mode based on screen size
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setViewMode("list");
    }
  }, []);

  // Compute planned transfers with player names for the summary card
  const plannedTransfers = useMemo(() => {
    if (!hasPlannedTransfers || !sellAnalysis || !buyAnalysis) return [];

    const transfers: Array<{
      outId: number;
      outName: string;
      outPrice: number;
      inId: number;
      inName: string;
      inPrice: number;
    }> = [];

    Object.entries(wizardSelections).forEach(([candIdStr, repId]) => {
      if (repId === null || repId === undefined) return;
      const candId = parseInt(candIdStr);

      // Find the candidate (player being sold)
      const candidate = sellAnalysis.candidates.find(c => c.id === candId);
      if (!candidate) return;

      // Find the replacement (player being bought) - from recommendations array
      const replacement = buyAnalysis.recommendations.find(r => r.id === repId);
      if (!replacement) return;

      transfers.push({
        outId: candId,
        outName: candidate.name,
        outPrice: candidate.price,
        inId: repId,
        inName: replacement.name,
        inPrice: replacement.price,
      });
    });

    return transfers;
  }, [hasPlannedTransfers, wizardSelections, sellAnalysis, buyAnalysis]);

  // Handle undo single transfer
  const handleUndoTransfer = useCallback((candId: number) => {
    updateWizardSelection(candId, undefined);
  }, [updateWizardSelection]);

  // Handle player click on pitch - different behavior based on step
  const handlePitchPlayerClick = useCallback((pitchPlayer: PitchPlayer) => {
    // In transfers step - do nothing (user should use the transfer cards instead)
    if (step === "transfers") {
      return;
    }

    // In lineup step - show player details card
    if (step === "lineup" && selectedStrategy) {
      // Find player in starting XI
      const startingPlayer = selectedStrategy.starting_xi.find(p => p.id === pitchPlayer.id);
      if (startingPlayer) {
        setSelectedPlayerForCard(startingPlayer);
        return;
      }

      // Find player in bench
      const benchPlayer = selectedStrategy.bench.find(p => p.id === pitchPlayer.id);
      if (benchPlayer) {
        setSelectedPlayerForCard(benchPlayer);
      }
    }
  }, [step, selectedStrategy, setSelectedPlayerForCard, setSelectedPlayerForAlternatives]);

  // Detect formation from starting XI - use optimized formation when on lineup step
  const detectFormation = (): string => {
    // Use optimized formation for lineup/captain/confirm steps when available
    if ((step === "lineup" || step === "captain" || step === "confirm") && optimizedFormation) {
      return optimizedFormation;
    }

    const starting = teamData.squad.starting;
    const def = starting.filter((p) => p.position === "DEF").length;
    const mid = starting.filter((p) => p.position === "MID").length;
    const fwd = starting.filter((p) => p.position === "FWD").length;
    return `${def}-${mid}-${fwd}`;
  };

  // Convert squad to pitch players based on step
  // Priority: optimizedSquad (strategy) > previewSquad (transfers) > originalSquad
  const getPitchPlayers = (): PitchPlayer[] => {
    // On lineup/captain/confirm steps, use optimized squad when available
    // This takes priority even when there are planned transfers, since the
    // lineup strategies API already incorporates transfers
    if ((step === "lineup" || step === "captain" || step === "confirm") && optimizedSquad.length > 0) {
      const startingCount = lineup?.starting_xi.length || 11;
      const starting = optimizedSquad.slice(0, startingCount).map((p) => toPitchPlayer(p, true));
      const bench = optimizedSquad.slice(startingCount).map((p) => toPitchPlayer(p, false));
      return [...starting, ...bench];
    }

    // Show projected lineup when there are planned transfers (on other steps)
    if (hasPlannedTransfers) {
      const startingCount = teamData.squad.starting.length;
      const starting = previewSquad.slice(0, startingCount).map((p) => toPitchPlayer(p, true));
      const bench = previewSquad.slice(startingCount).map((p) => toPitchPlayer(p, false));
      return [...starting, ...bench];
    }

    // Default: show original squad
    const startingCount = teamData.squad.starting.length;
    const starting = originalSquad.slice(0, startingCount).map((p) => toPitchPlayer(p, true));
    const bench = originalSquad.slice(startingCount).map((p) => toPitchPlayer(p, false));

    return [...starting, ...bench];
  };

  // Dynamic title based on workflow step
  const getSquadTitle = () => {
    switch (step) {
      case "review": return `GW${teamData.gameweek.id} Performance`;
      case "alerts": return "Squad Health Check";
      case "transfers": return "Transfer Planning";
      case "lineup": return "Lineup Optimization";
      case "captain": return "Captain Selection";
      case "confirm": return "Final Review";
      default: return `${teamData.gameweek.name} Squad`;
    }
  };

  return (
    <div className="bg-gradient-to-br from-slate-50 via-white to-emerald-50">
      {/* Background pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-100/40 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-green-100/40 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Navigation Header */}
        <div className="flex items-center justify-between mb-6">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm font-medium">Back</span>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              href="/players"
              className="flex items-center gap-2 px-3 py-1.5 bg-violet-100 hover:bg-violet-200 text-violet-700 rounded-full text-sm font-medium transition-colors"
              title="Find Players"
            >
              <Search className="w-4 h-4" />
              <span className="hidden sm:inline">Find Players</span>
              <span className="sm:hidden">Search</span>
            </Link>
            <button
              onClick={onLogout}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-full text-sm font-medium transition-colors"
              title="Switch Team"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Switch Team</span>
              <span className="sm:hidden">Switch</span>
            </button>
          </div>
        </div>

        {/* Unified Manager Info Block */}
        <div className="bg-gradient-to-r from-emerald-600 to-green-600 rounded-2xl shadow-lg shadow-emerald-200 overflow-hidden">
          {/* Manager Header */}
          <ManagerHeader teamData={teamData} embedded />

          {/* Divider */}
          <div className="h-px bg-white/20 mx-6" />

          {/* Mini-League Rankings */}
          <MiniLeagueRankings teamId={teamId} embedded />

          {/* Divider */}
          <div className="h-px bg-white/20 mx-6" />

          {/* Deadline Banner */}
          <div className="px-6 py-3">
            {timeLeft ? (
              <div className={`rounded-lg px-4 py-3 flex items-center justify-between ${
                timeLeft.isUrgent
                  ? "bg-red-500/30"
                  : "bg-amber-500/30"
              }`}>
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-full ${timeLeft.isUrgent ? "bg-red-400/30" : "bg-amber-400/30"}`}>
                    <Clock className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-white/80 text-xs font-medium uppercase tracking-wide">
                      {teamData.gameweek.name} Deadline
                    </p>
                    <p className="text-white text-sm">
                      {new Date(teamData.gameweek.deadline_time).toLocaleDateString('en-GB', {
                        weekday: 'short',
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-white/80 text-xs font-medium uppercase tracking-wide">Time Left</p>
                  {timeLeft.days > 0 ? (
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {timeLeft.days}<span className="text-lg">d</span>{" "}
                      {timeLeft.hours}<span className="text-lg">h</span>{" "}
                      {timeLeft.minutes}<span className="text-lg">m</span>
                    </p>
                  ) : (
                    <p className={`text-white text-2xl font-bold tabular-nums ${timeLeft.isUrgent ? "animate-pulse" : ""}`}>
                      {String(timeLeft.hours).padStart(2, '0')}:
                      {String(timeLeft.minutes).padStart(2, '0')}:
                      {String(timeLeft.seconds).padStart(2, '0')}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-lg px-4 py-3 bg-white/10 flex items-center gap-3">
                <div className="p-2 rounded-full bg-white/20">
                  <Calendar className="w-5 h-5 text-white" />
                </div>
                <p className="text-white font-medium">{teamData.gameweek.name} - Deadline Passed</p>
              </div>
            )}
          </div>
        </div>

        {/* Section Divider - Gameweek Planner */}
        <div className="relative mt-8 mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center">
            <div className="px-4 py-1.5 bg-white text-sm font-semibold text-slate-500 rounded-full border border-slate-200 shadow-sm">
              Prepare for the next Gameweek!
            </div>
          </div>
        </div>

        {/* Workflow Tabs - Full Width */}
        <div className="mt-4">
          <WorkflowTabNav
            gameweekName={`Gameweek ${teamData.gameweek.id + 1}`}
            deadline={null}
          />
        </div>

        {/* Planned Changes Summary Card - Shows when transfers are planned */}
        {plannedTransfers.length > 0 && (
          <div className="mt-3 bg-gradient-to-r from-violet-50 to-purple-50 rounded-xl border border-violet-200 shadow-sm overflow-hidden">
            <div className="px-4 py-2.5 border-b border-violet-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-violet-100">
                  <ArrowRightLeft className="w-4 h-4 text-violet-600" />
                </div>
                <span className="text-sm font-semibold text-violet-800">
                  Planned Transfers ({plannedTransfers.length})
                </span>
              </div>
              <button
                onClick={clearWizardSelections}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear All
              </button>
            </div>
            <div className="p-3 space-y-2">
              {plannedTransfers.map((transfer) => {
                const costDiff = transfer.inPrice - transfer.outPrice;
                return (
                  <div
                    key={transfer.outId}
                    className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-slate-200 group"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      {/* OUT Player */}
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-[10px] font-bold text-red-500 bg-red-50 px-1.5 py-0.5 rounded uppercase">OUT</span>
                        <span className="text-sm font-medium text-slate-700 truncate">{transfer.outName}</span>
                        <span className="text-xs text-slate-400">£{transfer.outPrice}m</span>
                      </div>
                      {/* Arrow */}
                      <span className="text-slate-300 flex-shrink-0">→</span>
                      {/* IN Player */}
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded uppercase">IN</span>
                        <span className="text-sm font-medium text-slate-700 truncate">{transfer.inName}</span>
                        <span className="text-xs text-slate-400">£{transfer.inPrice}m</span>
                      </div>
                    </div>
                    {/* Cost Diff & Undo */}
                    <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                      <span className={`text-xs font-medium ${costDiff > 0 ? "text-red-500" : costDiff < 0 ? "text-blue-500" : "text-slate-400"}`}>
                        {costDiff > 0 ? `+£${costDiff.toFixed(1)}m` : costDiff < 0 ? `-£${Math.abs(costDiff).toFixed(1)}m` : "±£0"}
                      </span>
                      <button
                        onClick={() => handleUndoTransfer(transfer.outId)}
                        className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors opacity-0 group-hover:opacity-100"
                        title="Undo this transfer"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
              {/* Cost Summary */}
              {plannedTransfers.length > 0 && (
                <div className="flex items-center justify-end gap-2 pt-1 border-t border-slate-100 mt-2">
                  <span className="text-xs text-slate-500">Net Cost:</span>
                  {(() => {
                    const totalCostDiff = plannedTransfers.reduce((sum, t) => sum + (t.inPrice - t.outPrice), 0);
                    return (
                      <span className={`text-sm font-semibold ${totalCostDiff > 0 ? "text-red-500" : totalCostDiff < 0 ? "text-blue-500" : "text-slate-600"}`}>
                        {totalCostDiff > 0 ? `+£${totalCostDiff.toFixed(1)}m` : totalCostDiff < 0 ? `-£${Math.abs(totalCostDiff).toFixed(1)}m` : "±£0"}
                      </span>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Main Content Grid - Pitch + Step Content Side by Side */}
        {/* Highlighted Main Section */}
        <div className="relative mt-6">
          {/* Glow Effect Background - Subtle violet/slate */}
          <div className="absolute -inset-1 bg-gradient-to-r from-violet-500/10 via-slate-400/10 to-cyan-500/10 rounded-3xl blur-xl opacity-50" />

          <div className="relative grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 md:gap-6 p-3 sm:p-4 bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-200 shadow-lg">
          {/* Pitch/List - Takes 3 columns on lg, full on mobile, half on md */}
          <div className="md:col-span-1 lg:col-span-3 order-2 md:order-1">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              {/* Squad Header with Stats */}
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center justify-between mb-3">
                  <h2 className={`text-lg font-bold ${
                    step === "transfers" ? "text-violet-700" :
                    step === "lineup" ? "text-blue-700" :
                    step === "captain" ? "text-amber-700" :
                    "text-slate-800"
                  }`}>
                    {getSquadTitle()}
                    {/* Show "Projected" badge when transfers are planned */}
                    {hasPlannedTransfers && (
                      <span className="ml-2 text-xs font-medium text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">
                        Projected
                      </span>
                    )}
                  </h2>
                  <div className="flex items-center gap-3">
                    {/* View Mode Toggle */}
                    <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
                      <button
                        onClick={() => setViewMode("pitch")}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                          viewMode === "pitch"
                            ? "bg-white text-emerald-600 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                        }`}
                        aria-label="Pitch view"
                      >
                        <LayoutGrid className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Pitch</span>
                      </button>
                      <button
                        onClick={() => setViewMode("list")}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all ${
                          viewMode === "list"
                            ? "bg-white text-emerald-600 shadow-sm"
                            : "text-slate-500 hover:text-slate-700"
                        }`}
                        aria-label="List view"
                      >
                        <List className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">List</span>
                      </button>
                    </div>
                    <span className="text-sm text-slate-500 hidden sm:inline">
                      {detectFormation()}
                    </span>
                  </div>
                </div>
                {/* Squad Stats Row */}
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-500">Squad:</span>
                    <span className="font-semibold text-slate-800">
                      £{teamData.team_value.toFixed(1)}m
                    </span>
                  </div>
                  <div className="w-px h-4 bg-slate-200" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-500">Bank:</span>
                    <span className="font-semibold text-blue-600">
                      £{teamData.bank.toFixed(1)}m
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-4">
                {viewMode === "pitch" ? (
                  <PitchVisualization
                    players={getPitchPlayers() as any}
                    formation={detectFormation()}
                    pitchMode={pitchMode}
                    highlightedPlayerIds={highlightedPlayerIds}
                    transferOutIds={transferOutIds}
                    transferInIds={transferInIds}
                    mlScores={mlScores}
                    onPlayerClick={(step === "lineup" || step === "transfers") ? handlePitchPlayerClick as any : undefined}
                  />
                ) : (
                  <SquadListView
                    players={getPitchPlayers().map(p => ({
                      id: p.id,
                      web_name: p.web_name,
                      position: p.position,
                      team_short: p.team_short,
                      price: p.price,
                      form: p.form,
                      ownership: p.ownership,
                      total_points: p.total_points,
                      is_starter: p.is_starter,
                      is_captain: p.is_captain,
                      is_vice_captain: p.is_vice_captain,
                      gw_points: p.gw_points,
                      status: p.status,
                      news: p.news,
                    }))}
                    mlScores={mlScores}
                    highlightedPlayerIds={highlightedPlayerIds}
                    transferOutIds={transferOutIds}
                    transferInIds={transferInIds}
                  />
                )}
              </div>
            </div>
          </div>

          {/* Step Content - Takes 2 columns on lg, full on mobile, half on md */}
          <div className="md:col-span-1 lg:col-span-2 order-1 md:order-2">
            <WorkflowStepContent />
          </div>
          </div>
        </div>

        {/* Section Divider - Analytics */}
        <div className="relative mt-12 mb-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center">
            <div className="px-4 py-1.5 bg-white text-sm font-semibold text-slate-500 rounded-full border border-slate-200 shadow-sm">
              Community Analytics
            </div>
          </div>
        </div>

        {/* Crowd Insights - Full Width Below Grid */}
        <div>
          <CrowdInsights teamId={teamId} />
        </div>

        {/* Crowd Intelligence - Full Width */}
        <div className="mt-6">
          <CrowdIntelligence teamId={teamId} />
        </div>

        {/* Section Divider - Performance */}
        <div className="relative mt-12 mb-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center">
            <div className="px-4 py-1.5 bg-white text-sm font-semibold text-slate-500 rounded-full border border-slate-200 shadow-sm">
              Performance Insights
            </div>
          </div>
        </div>

        {/* Decision Quality - Full Width */}
        <div>
          <DecisionQuality teamId={teamId} />
        </div>
      </div>
    </div>
  );
}

export default function MyTeamDashboard() {
  const params = useParams();
  const router = useRouter();
  const teamId = params.id as string;

  const [teamData, setTeamData] = useState<TeamAnalysisResponse | null>(null);
  const [mlScores, setMlScores] = useState<Record<number, MLScore>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const startTime = Date.now();

    // Fetch team data and ML scores in parallel
    Promise.all([
      getTeamAnalysis(teamId),
      getAllMLScores(759).catch(() => []) // Fetch all players, silent fail if predictor not ready
    ])
      .then(([team, scores]) => {
        setTeamData(team);
        // Convert array to Record<number, MLScore> for O(1) lookup
        const scoresMap: Record<number, MLScore> = {};
        for (const s of scores) {
          scoresMap[s.player_id] = {
            final_score: s.final_score,
            rank: s.rank,
            nailedness_score: s.nailedness_score,
            form_xg_score: s.form_xg_score,
            form_pts_score: s.form_pts_score,
            fixture_score: s.fixture_score,
          };
        }
        setMlScores(scoresMap);

        // Track successful team analysis completion
        const loadTimeMs = Date.now() - startTime;
        trackTeamAnalysisComplete(teamId, loadTimeMs);
        recordTeamAnalyzed(teamId);
        trackFunnelStep('team_analysis', 2, 'team_data_loaded', true);
        trackGoalCompletion('team_analyzed', {
          team_id: teamId,
          load_time_ms: loadTimeMs,
          gameweek: team.gameweek.id,
          overall_rank: team.overall_rank ?? 0,
        });

        // Track team metadata for insights
        trackEvent({
          name: 'team_profile',
          properties: {
            team_id: teamId,
            overall_rank: team.overall_rank ?? 0,
            squad_size: team.squad.starting.length + team.squad.bench.length,
          },
        });
      })
      .catch((err) => {
        setError(err.message);
        trackError('team_analysis_failed', err.message, `team_id: ${teamId}`);
        trackFunnelStep('team_analysis', 2, 'team_data_failed', false);
      })
      .finally(() => setLoading(false));
  }, [teamId]);

  // Logout handler
  const handleLogout = () => {
    localStorage.removeItem(STORAGE_KEY);
    router.push("/my-team");
  };

  if (loading) {
    return <SkeletonTeamDashboard />;
  }

  if (error || !teamData) {
    return (
      <div className="bg-gradient-to-br from-slate-50 via-white to-emerald-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-slate-800 font-semibold mb-2">Failed to load team</p>
          <p className="text-slate-500 text-sm mb-4">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Home
            </Link>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
            >
              Try Another Team
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Convert squad to PlayerSummary array for context
  const allSquadPlayers: PlayerSummary[] = [
    ...teamData.squad.starting,
    ...teamData.squad.bench,
  ];

  return (
    <TransferWorkflowProvider
      teamId={teamId}
      originalSquad={allSquadPlayers}
    >
      <TeamDashboardInner
        teamData={teamData}
        teamId={teamId}
        onLogout={handleLogout}
        mlScores={mlScores}
      />
    </TransferWorkflowProvider>
  );
}
