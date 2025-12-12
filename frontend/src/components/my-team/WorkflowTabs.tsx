"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart3, Bell, ArrowRightLeft, ArrowRight, Users, Lightbulb, CheckCircle2,
  ChevronRight, ChevronDown, ChevronUp, Crown, Award, AlertTriangle, TrendingUp, TrendingDown,
  RefreshCw, Zap, Shield, Target, ExternalLink, Check, X, Sparkles,
  Star, PartyPopper, Trophy, Flame, HelpCircle, Search, Loader2, RotateCcw, ThumbsUp, ThumbsDown,
  MessageSquare, Send
} from "lucide-react";
import { useTransferWorkflow, type WorkflowStep, STEP_ORDER } from "@/contexts/TransferWorkflowContext";
import PlayerWhyCard from "./PlayerWhyCard";
import type { LineupPlayer, BenchPlayer, PlayerAlternativesResponse, PlayerAlternative, SellAnalysisResponse, BuyAnalysisResponse, SquadAnalysisResponse, AIGWReviewResponse } from "@/lib/api";
import { getPlayerAlternatives, getSellAnalysis, getBuyAnalysis, getSquadAnalysis, getAIGWReview } from "@/lib/api";
import { trackWorkflowTab, trackFunnelStep, trackGoalCompletion, trackEvent, trackFeedbackSubmission } from "@/lib/analytics";

// Tab configuration - 7 steps in decision-making order (Chips moved to Lineup, Feedback at end)
const TABS: { key: WorkflowStep; label: string; icon: React.ReactNode; color: string }[] = [
  { key: "review", label: "Review", icon: <BarChart3 className="w-4 h-4" />, color: "emerald" },
  { key: "alerts", label: "Alerts", icon: <Bell className="w-4 h-4" />, color: "amber" },
  { key: "transfers", label: "Transfers", icon: <ArrowRightLeft className="w-4 h-4" />, color: "violet" },
  { key: "lineup", label: "Lineup", icon: <Users className="w-4 h-4" />, color: "blue" },
  { key: "captain", label: "Captain", icon: <Crown className="w-4 h-4" />, color: "amber" },
  { key: "confirm", label: "Confirm", icon: <CheckCircle2 className="w-4 h-4" />, color: "emerald" },
  { key: "feedback", label: "Feedback", icon: <MessageSquare className="w-4 h-4" />, color: "purple" },
];

// Color utilities
const getTabColors = (color: string, isActive: boolean) => {
  const colors: Record<string, { active: string; inactive: string; border: string }> = {
    emerald: {
      active: "bg-emerald-600 text-white shadow-lg shadow-emerald-200",
      inactive: "text-slate-600 hover:text-emerald-600 hover:bg-emerald-50",
      border: "border-emerald-600"
    },
    amber: {
      active: "bg-amber-500 text-white shadow-lg shadow-amber-200",
      inactive: "text-slate-600 hover:text-amber-600 hover:bg-amber-50",
      border: "border-amber-500"
    },
    violet: {
      active: "bg-violet-600 text-white shadow-lg shadow-violet-200",
      inactive: "text-slate-600 hover:text-violet-600 hover:bg-violet-50",
      border: "border-violet-600"
    },
    blue: {
      active: "bg-blue-600 text-white shadow-lg shadow-blue-200",
      inactive: "text-slate-600 hover:text-blue-600 hover:bg-blue-50",
      border: "border-blue-600"
    },
    purple: {
      active: "bg-purple-600 text-white shadow-lg shadow-purple-200",
      inactive: "text-slate-600 hover:text-purple-600 hover:bg-purple-50",
      border: "border-purple-600"
    },
    teal: {
      active: "bg-teal-600 text-white shadow-lg shadow-teal-200",
      inactive: "text-slate-600 hover:text-teal-600 hover:bg-teal-50",
      border: "border-teal-600"
    },
  };
  return colors[color] || colors.emerald;
};

// ============================================================================
// Tab Navigation Component
// ============================================================================

interface WorkflowTabNavProps {
  gameweekName?: string;
  deadline?: {
    days: number;
    hours: number;
    minutes: number;
    seconds: number;
    isUrgent: boolean;
  } | null;
}

export function WorkflowTabNav({ gameweekName }: WorkflowTabNavProps) {
  const { step, setStep, transferOutIds, transferInIds, completedSteps, canAccessStep, getStepProgress } = useTransferWorkflow();
  const hasPlannedTransfers = transferOutIds.size > 0;
  const progress = getStepProgress();

  // Calculate current step number (1-based)
  const currentStepIndex = STEP_ORDER.indexOf(step);
  const currentStepNumber = currentStepIndex + 1;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header with Progress Bar */}
      <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-700">
            Gameweek Planner
          </span>
          <div className="flex items-center gap-2">
            {/* Step counter */}
            <span className="text-xs font-medium text-slate-500">
              Step {currentStepNumber} of {STEP_ORDER.length}
            </span>
            {/* Show planned transfers count if any */}
            {hasPlannedTransfers && (
              <span className="text-xs font-medium text-violet-600 bg-violet-50 px-2 py-1 rounded-full">
                {transferOutIds.size} transfer{transferOutIds.size > 1 ? 's' : ''} planned
              </span>
            )}
          </div>
        </div>
        {/* Progress Bar */}
        <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-violet-600 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${((currentStepIndex + 1) / STEP_ORDER.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Desktop Tabs - Sequential navigation with disabled states */}
      <div className="hidden sm:flex items-center gap-1 p-2">
        {TABS.map((tab, idx) => {
          const isActive = step === tab.key;
          const colors = getTabColors(tab.color, isActive);
          const isAccessible = canAccessStep(tab.key);
          const isCompleted = completedSteps.has(tab.key);
          // Show badge on Transfers tab if transfers are planned
          const showBadge = tab.key === "transfers" && hasPlannedTransfers && !isActive;

          return (
            <button
              key={tab.key}
              onClick={() => {
                if (isAccessible) {
                  trackWorkflowTab(tab.key, step);
                  trackFunnelStep('team_analysis', idx + 2, tab.label);
                  setStep(tab.key);
                }
              }}
              disabled={!isAccessible}
              className={`
                flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl
                font-medium text-sm transition-all duration-200 relative
                ${isActive ? colors.active : isAccessible ? colors.inactive : "text-slate-300 cursor-not-allowed"}
                ${!isAccessible && "opacity-50"}
              `}
              title={!isAccessible ? `Complete previous steps first` : undefined}
            >
              {/* Step number or check mark for completed */}
              {isCompleted && !isActive ? (
                <Check className="w-4 h-4 text-emerald-500" />
              ) : (
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold
                  ${isActive ? "bg-white/30" : isAccessible ? "bg-slate-200" : "bg-slate-100"}
                `}>
                  {idx + 1}
                </span>
              )}
              {tab.icon}
              <span>{tab.label}</span>
              {showBadge && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-violet-500 text-white text-xs rounded-full flex items-center justify-center">
                  {transferOutIds.size}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Mobile Tab Selector - Sequential with disabled states */}
      <div className="sm:hidden p-2">
        <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-hide">
          {TABS.map((tab, idx) => {
            const isActive = step === tab.key;
            const colors = getTabColors(tab.color, isActive);
            const isAccessible = canAccessStep(tab.key);
            const isCompleted = completedSteps.has(tab.key);
            const showBadge = tab.key === "transfers" && hasPlannedTransfers && !isActive;

            return (
              <button
                key={tab.key}
                onClick={() => {
                if (isAccessible) {
                  trackWorkflowTab(tab.key, step);
                  trackFunnelStep('team_analysis', idx + 2, tab.label);
                  setStep(tab.key);
                }
              }}
                disabled={!isAccessible}
                className={`
                  flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap
                  font-medium text-xs transition-all duration-200 flex-shrink-0 relative
                  ${isActive ? colors.active : isAccessible ? colors.inactive : "text-slate-300 cursor-not-allowed"}
                  ${!isAccessible && "opacity-50"}
                `}
              >
                {/* Step number or check mark for completed */}
                {isCompleted && !isActive ? (
                  <Check className="w-3 h-3 text-emerald-500" />
                ) : (
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold
                    ${isActive ? "bg-white/30" : isAccessible ? "bg-slate-200" : "bg-slate-100"}
                  `}>
                    {idx + 1}
                  </span>
                )}
                {tab.icon}
                <span>{tab.label}</span>
                {showBadge && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-violet-500 text-white text-[10px] rounded-full flex items-center justify-center">
                    {transferOutIds.size}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Step Content Components
// ============================================================================

// Review Step Content - Enhanced with celebrations
function ReviewContent() {
  const { gwReview, gwReviewLoading, loadGWReview, loadAlerts, teamId, advanceToStep } = useTransferWorkflow();

  // AI Analysis state
  const [aiAnalysis, setAiAnalysis] = useState<AIGWReviewResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Collapsible section states
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    what_went_well: true,
    areas_to_address: true,
    strengths: true,
    weaknesses: true,
    squad_score: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  useEffect(() => {
    loadGWReview();
  }, [loadGWReview]);

  // Load AI analysis when button is clicked
  const handleLoadAIAnalysis = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const data = await getAIGWReview(teamId);
      setAiAnalysis(data);
    } catch (err) {
      console.error("Failed to load AI analysis:", err);
      setAiError(err instanceof Error ? err.message : "Failed to load AI analysis");
    } finally {
      setAiLoading(false);
    }
  };

  if (gwReviewLoading) {
    return <LoadingState message="Analyzing your gameweek..." />;
  }

  if (!gwReview) {
    return <ErrorState message="Failed to load GW review" />;
  }

  const handleContinue = () => {
    loadAlerts();
    advanceToStep("review", "alerts");
  };

  // Determine performance level for styling
  const isGreatWeek = gwReview.gw_points >= 60;
  const isGoodWeek = gwReview.gw_points >= 50;
  const isPoorWeek = gwReview.gw_points < 40;

  // Find star performer from insights
  const starInsight = gwReview.insights.find(i => i.type === "positive" && i.icon === "star");
  const captainInsight = gwReview.insights.find(i => i.icon === "crown");

  return (
    <div className="space-y-4">
      {/* Summary Card - Dynamic styling based on performance */}
      <div className={`rounded-xl p-5 text-white relative overflow-hidden ${
        isGreatWeek
          ? "bg-gradient-to-br from-amber-500 via-amber-400 to-yellow-500"
          : isGoodWeek
            ? "bg-gradient-to-br from-emerald-500 to-emerald-600"
            : isPoorWeek
              ? "bg-gradient-to-br from-slate-500 to-slate-600"
              : "bg-gradient-to-br from-blue-500 to-blue-600"
      }`}>
        {/* Celebration decoration for great weeks */}
        {isGreatWeek && (
          <div className="absolute top-2 right-2 flex gap-1">
            <Sparkles className="w-5 h-5 text-yellow-200 animate-pulse" />
            <Trophy className="w-5 h-5 text-yellow-200" />
          </div>
        )}

        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-white/80 text-sm flex items-center gap-1">
              {isGreatWeek && <Flame className="w-4 h-4" />}
              Gameweek Points
            </p>
            <p className="text-5xl font-bold tracking-tight">{gwReview.gw_points}</p>
            {gwReview.gw_average && (
              <p className="text-white/70 text-xs mt-1">
                vs avg {gwReview.gw_average} ({gwReview.gw_points >= gwReview.gw_average ? "+" : ""}{gwReview.gw_points - gwReview.gw_average})
              </p>
            )}
          </div>
          {gwReview.gw_rank && (
            <div className="text-right">
              <p className="text-white/80 text-sm">GW Rank</p>
              <p className="text-2xl font-bold">{gwReview.gw_rank.toLocaleString()}</p>
              {gwReview.rank_percentile && gwReview.rank_percentile <= 10 && (
                <p className="text-xs font-semibold text-yellow-200 flex items-center justify-end gap-1">
                  <Trophy className="w-3 h-3" /> Top {gwReview.rank_percentile}%
                </p>
              )}
              {gwReview.rank_percentile && gwReview.rank_percentile > 10 && gwReview.rank_percentile <= 25 && (
                <p className="text-xs text-white/80">Top {gwReview.rank_percentile}%</p>
              )}
            </div>
          )}
        </div>
        <p className="text-white/90 text-sm">{gwReview.summary}</p>
      </div>

      {/* Star Performer Card - if there's a standout player */}
      {starInsight && (
        <div className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-xl p-4 border border-amber-200 relative">
          <div className="absolute -top-2 -right-2">
            <div className="bg-amber-500 text-white text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1">
              <Star className="w-3 h-3" /> MVP
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center">
              <Trophy className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-xs text-amber-600 font-medium">Star Performer</p>
              <p className="text-sm text-slate-700">{starInsight.text}</p>
            </div>
          </div>
        </div>
      )}

      {/* AI Analysis Button - Show when AI hasn't been loaded */}
      {!aiAnalysis && !aiLoading && (
        <button
          onClick={handleLoadAIAnalysis}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-violet-600 text-white rounded-xl hover:from-purple-600 hover:to-violet-700 transition-all shadow-md hover:shadow-lg"
        >
          <Sparkles className="w-4 h-4" />
          <span className="font-medium">Get AI-Powered Analysis</span>
        </button>
      )}

      {/* AI Loading State */}
      {aiLoading && (
        <div className="flex items-center justify-center gap-3 px-4 py-4 bg-purple-50 rounded-xl border border-purple-200">
          <Loader2 className="w-5 h-5 text-purple-600 animate-spin" />
          <span className="text-sm text-purple-700">AI is analyzing your gameweek...</span>
        </div>
      )}

      {/* AI Error State */}
      {aiError && (
        <div className="flex items-center gap-3 px-4 py-3 bg-red-50 rounded-xl border border-red-200">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <span className="text-sm text-red-700">{aiError}</span>
          <button
            onClick={handleLoadAIAnalysis}
            className="ml-auto text-xs text-red-600 hover:text-red-800 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Insights Grid - AI-generated with collapsible sections */}
      {aiAnalysis && (
        <div className="space-y-3">
          {/* AI Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-50 rounded-lg border border-purple-200 w-fit">
            <Sparkles className="w-3 h-3 text-purple-600" />
            <span className="text-xs text-purple-700 font-medium">AI-Powered Analysis</span>
          </div>

          {/* Squad Score Section */}
          {aiAnalysis.squad_score && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <button
                onClick={() => toggleSection("squad_score")}
                className="w-full px-4 py-3 flex items-center justify-between bg-gradient-to-r from-violet-50 to-purple-50 hover:from-violet-100 hover:to-purple-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-violet-600" />
                  <span className="text-sm font-semibold text-violet-700">Squad Score</span>
                  <span className="text-lg font-bold text-violet-600">{aiAnalysis.squad_score.overall}/100</span>
                </div>
                {expandedSections.squad_score ? (
                  <ChevronUp className="w-4 h-4 text-violet-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-violet-500" />
                )}
              </button>
              {expandedSections.squad_score && (
                <div className="px-4 py-3 grid grid-cols-2 gap-3">
                  {[
                    { label: "Attack", value: aiAnalysis.squad_score.attack, color: "red" },
                    { label: "Midfield", value: aiAnalysis.squad_score.midfield, color: "blue" },
                    { label: "Defense", value: aiAnalysis.squad_score.defense, color: "emerald" },
                    { label: "Bench", value: aiAnalysis.squad_score.bench, color: "slate" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                      <span className="text-xs text-slate-600">{label}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              color === "red" ? "bg-red-500" :
                              color === "blue" ? "bg-blue-500" :
                              color === "emerald" ? "bg-emerald-500" : "bg-slate-500"
                            }`}
                            style={{ width: `${value}%` }}
                          />
                        </div>
                        <span className="text-xs font-semibold text-slate-700 w-6">{value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* What went well - Collapsible */}
          {aiAnalysis.what_went_well && aiAnalysis.what_went_well.length > 0 && (
            <div className="bg-white rounded-xl border border-emerald-200 overflow-hidden">
              <button
                onClick={() => toggleSection("what_went_well")}
                className="w-full px-4 py-3 flex items-center justify-between bg-emerald-50 hover:bg-emerald-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-semibold text-emerald-700">What Went Well</span>
                  <span className="text-xs text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full">{aiAnalysis.what_went_well.length}</span>
                </div>
                {expandedSections.what_went_well ? (
                  <ChevronUp className="w-4 h-4 text-emerald-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-emerald-500" />
                )}
              </button>
              {expandedSections.what_went_well && (
                <div className="px-4 py-3 space-y-2">
                  {aiAnalysis.what_went_well.map((text, idx) => (
                    <div key={`pos-${idx}`} className="flex items-start gap-2">
                      <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-slate-700">{text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Areas to address - Collapsible */}
          {aiAnalysis.areas_to_address && aiAnalysis.areas_to_address.length > 0 && (
            <div className="bg-white rounded-xl border border-amber-200 overflow-hidden">
              <button
                onClick={() => toggleSection("areas_to_address")}
                className="w-full px-4 py-3 flex items-center justify-between bg-amber-50 hover:bg-amber-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span className="text-sm font-semibold text-amber-700">Areas to Address</span>
                  <span className="text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded-full">{aiAnalysis.areas_to_address.length}</span>
                </div>
                {expandedSections.areas_to_address ? (
                  <ChevronUp className="w-4 h-4 text-amber-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-amber-500" />
                )}
              </button>
              {expandedSections.areas_to_address && (
                <div className="px-4 py-3 space-y-2">
                  {aiAnalysis.areas_to_address.map((text, idx) => (
                    <div key={`neg-${idx}`} className="flex items-start gap-2">
                      <TrendingDown className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-slate-700">{text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Strengths - Collapsible */}
          {aiAnalysis.strengths && aiAnalysis.strengths.length > 0 && (
            <div className="bg-white rounded-xl border border-blue-200 overflow-hidden">
              <button
                onClick={() => toggleSection("strengths")}
                className="w-full px-4 py-3 flex items-center justify-between bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <ThumbsUp className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-semibold text-blue-700">Squad Strengths</span>
                  <span className="text-xs text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">{aiAnalysis.strengths.length}</span>
                </div>
                {expandedSections.strengths ? (
                  <ChevronUp className="w-4 h-4 text-blue-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-blue-500" />
                )}
              </button>
              {expandedSections.strengths && (
                <div className="px-4 py-3 space-y-2">
                  {aiAnalysis.strengths.map((text, idx) => (
                    <div key={`str-${idx}`} className="flex items-start gap-2">
                      <Zap className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-slate-700">{text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Weaknesses - Collapsible */}
          {aiAnalysis.weaknesses && aiAnalysis.weaknesses.length > 0 && (
            <div className="bg-white rounded-xl border border-red-200 overflow-hidden">
              <button
                onClick={() => toggleSection("weaknesses")}
                className="w-full px-4 py-3 flex items-center justify-between bg-red-50 hover:bg-red-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <ThumbsDown className="w-4 h-4 text-red-600" />
                  <span className="text-sm font-semibold text-red-700">Squad Weaknesses</span>
                  <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded-full">{aiAnalysis.weaknesses.length}</span>
                </div>
                {expandedSections.weaknesses ? (
                  <ChevronUp className="w-4 h-4 text-red-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-red-500" />
                )}
              </button>
              {expandedSections.weaknesses && (
                <div className="px-4 py-3 space-y-2">
                  {aiAnalysis.weaknesses.map((text, idx) => (
                    <div key={`weak-${idx}`} className="flex items-start gap-2">
                      <X className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-slate-700">{text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}


      {/* Continue Button */}
      <ContinueButton onClick={handleContinue} label="Check Alerts" color="amber" />
    </div>
  );
}

// Alerts Step Content - Enhanced with grouped alerts and better visual design
function AlertsContent() {
  const { alerts, alertsLoading, loadAlerts, advanceToStep } = useTransferWorkflow();

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  if (alertsLoading) {
    return <LoadingState message="Scanning for alerts..." />;
  }

  if (!alerts) {
    return <ErrorState message="Failed to load alerts" />;
  }

  const handleContinue = () => {
    advanceToStep("alerts", "transfers");
  };

  // Group alerts by type - prioritize critical sections
  const groupedAlerts = {
    // CRITICAL - Can't Play
    injured: alerts.alerts.filter(a => a.type === "injured"),
    suspended: alerts.alerts.filter(a => a.type === "suspended"),
    unavailable: alerts.alerts.filter(a => a.type === "unavailable"),
    doubtful: alerts.alerts.filter(a => a.type === "doubtful"),
    // YELLOW CARD RISK
    suspension_risk: alerts.alerts.filter(a => a.type === "suspension_risk"),
    // TRANSFER/PRICE
    selling_out: alerts.alerts.filter(a => a.type === "selling_out"),
    price_drop: alerts.alerts.filter(a => a.type === "price_drop"),
    price_rise: alerts.alerts.filter(a => a.type === "price_rise"),
    // FORM & ROTATION
    low_form: alerts.alerts.filter(a => a.type === "low_form"),
    rotation: alerts.alerts.filter(a => a.type === "rotation"),
    // FIXTURES
    fixture: alerts.alerts.filter(a => a.type === "fixture"),
    // Legacy types
    disqualified: alerts.alerts.filter(a => a.type === "disqualified"),
    price: alerts.alerts.filter(a => a.type === "price"),
  };

  const highCount = alerts.alerts.filter(a => a.severity === "high").length;
  const mediumCount = alerts.alerts.filter(a => a.severity === "medium").length;
  const warningCount = alerts.alerts.filter(a => a.severity === "warning").length;

  // Get status text based on alerts
  const getStatusText = () => {
    if (highCount > 0) return "Action Required";
    if (mediumCount > 0) return "Review Recommended";
    if (warningCount > 0) return "Minor Concerns";
    return "All Clear";
  };

  const getStatusIcon = () => {
    if (highCount > 0) return <AlertTriangle className="w-6 h-6" />;
    if (mediumCount > 0) return <Bell className="w-6 h-6" />;
    return <Shield className="w-6 h-6" />;
  };

  return (
    <div className="space-y-4">
      {/* Alert Summary Header - More detailed with severity breakdown */}
      <div className={`rounded-xl overflow-hidden ${
        highCount > 0 ? "bg-gradient-to-br from-red-500 via-red-500 to-rose-600" :
        mediumCount > 0 ? "bg-gradient-to-br from-amber-500 via-amber-500 to-orange-500" :
        "bg-gradient-to-br from-emerald-500 to-emerald-600"
      } text-white shadow-lg`}>
        <div className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${
                highCount > 0 ? "bg-red-400/30" :
                mediumCount > 0 ? "bg-amber-400/30" : "bg-emerald-400/30"
              }`}>
                {getStatusIcon()}
              </div>
              <div>
                <h3 className="text-lg font-bold">{getStatusText()}</h3>
                <p className="text-sm opacity-80">{alerts.alerts.length} alert{alerts.alerts.length !== 1 ? "s" : ""} found</p>
              </div>
            </div>
          </div>
          <p className="text-sm opacity-90">{alerts.summary}</p>
        </div>

        {/* Severity breakdown bar */}
        {alerts.alerts.length > 0 && (
          <div className="px-5 pb-4">
            <div className="flex gap-3">
              {highCount > 0 && (
                <div className="flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1">
                  <div className="w-2 h-2 rounded-full bg-red-200" />
                  <span className="text-xs font-semibold">{highCount} Critical</span>
                </div>
              )}
              {mediumCount > 0 && (
                <div className="flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1">
                  <div className="w-2 h-2 rounded-full bg-amber-200" />
                  <span className="text-xs font-semibold">{mediumCount} Important</span>
                </div>
              )}
              {warningCount > 0 && (
                <div className="flex items-center gap-1.5 bg-white/20 rounded-full px-3 py-1">
                  <div className="w-2 h-2 rounded-full bg-orange-200" />
                  <span className="text-xs font-semibold">{warningCount} Watch</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* No Alerts State */}
      {alerts.alerts.length === 0 ? (
        <div className="text-center py-10 bg-gradient-to-br from-blue-50 to-violet-50 rounded-xl border border-blue-200">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-8 h-8 text-blue-600" />
          </div>
          <p className="font-bold text-blue-800 text-lg">Squad Looking Healthy!</p>
          <p className="text-sm text-blue-600 mt-1">No issues detected - you're all set</p>
        </div>
      ) : (
        /* Grouped Alert Sections - Priority order */
        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
          {/* ===== CRITICAL: CAN'T PLAY ===== */}

          {/* Injured Players */}
          {groupedAlerts.injured.length > 0 && (
            <AlertGroup
              title="Injured Players"
              icon={<AlertTriangle className="w-4 h-4" />}
              color="red"
              alerts={groupedAlerts.injured}
            />
          )}

          {/* Suspended Players */}
          {groupedAlerts.suspended.length > 0 && (
            <AlertGroup
              title="Suspended Players"
              icon={<AlertTriangle className="w-4 h-4" />}
              color="red"
              alerts={groupedAlerts.suspended}
            />
          )}

          {/* Unavailable Players */}
          {groupedAlerts.unavailable.length > 0 && (
            <AlertGroup
              title="Unavailable Players"
              icon={<AlertTriangle className="w-4 h-4" />}
              color="red"
              alerts={groupedAlerts.unavailable}
            />
          )}

          {/* Doubtful Players */}
          {groupedAlerts.doubtful.length > 0 && (
            <AlertGroup
              title="Doubtful Players"
              icon={<Bell className="w-4 h-4" />}
              color="amber"
              alerts={groupedAlerts.doubtful}
            />
          )}

          {/* Legacy disqualified type (backwards compatibility) */}
          {groupedAlerts.disqualified.length > 0 && (
            <AlertGroup
              title="Cannot Play"
              icon={<AlertTriangle className="w-4 h-4" />}
              color="red"
              alerts={groupedAlerts.disqualified}
            />
          )}

          {/* ===== YELLOW CARD WARNINGS ===== */}
          {groupedAlerts.suspension_risk.length > 0 && (
            <AlertGroup
              title="Yellow Card Danger"
              icon={<AlertTriangle className="w-4 h-4" />}
              color="amber"
              alerts={groupedAlerts.suspension_risk}
            />
          )}

          {/* ===== TRANSFER/PRICE ALERTS ===== */}

          {/* Players Being Sold */}
          {groupedAlerts.selling_out.length > 0 && (
            <AlertGroup
              title="Your Players Being Sold"
              icon={<TrendingDown className="w-4 h-4" />}
              color="purple"
              alerts={groupedAlerts.selling_out}
            />
          )}

          {/* Price Drop Risk */}
          {groupedAlerts.price_drop.length > 0 && (
            <AlertGroup
              title="Price Drop Risk"
              icon={<TrendingDown className="w-4 h-4" />}
              color="red"
              alerts={groupedAlerts.price_drop}
            />
          )}

          {/* Price Rising (positive) */}
          {groupedAlerts.price_rise.length > 0 && (
            <AlertGroup
              title="Price Rising"
              icon={<TrendingUp className="w-4 h-4" />}
              color="green"
              alerts={groupedAlerts.price_rise}
            />
          )}

          {/* ===== FORM & ROTATION ===== */}

          {/* Low Form Warning */}
          {groupedAlerts.low_form.length > 0 && (
            <AlertGroup
              title="Poor Form"
              icon={<TrendingDown className="w-4 h-4" />}
              color="amber"
              alerts={groupedAlerts.low_form}
            />
          )}

          {/* Rotation Risk */}
          {groupedAlerts.rotation.length > 0 && (
            <AlertGroup
              title="Rotation Risk"
              icon={<RefreshCw className="w-4 h-4" />}
              color="amber"
              alerts={groupedAlerts.rotation}
            />
          )}

          {/* ===== FIXTURES ===== */}
          {groupedAlerts.fixture.length > 0 && (
            <AlertGroup
              title="Tough Fixtures"
              icon={<Target className="w-4 h-4" />}
              color="blue"
              alerts={groupedAlerts.fixture}
            />
          )}

          {/* Legacy price type */}
          {groupedAlerts.price.length > 0 && (
            <AlertGroup
              title="Price Changes"
              icon={<TrendingDown className="w-4 h-4" />}
              color="blue"
              alerts={groupedAlerts.price}
            />
          )}
        </div>
      )}


      <ContinueButton onClick={handleContinue} label="Make Transfers" color="emerald" />
    </div>
  );
}

// Alert Group Component - Groups alerts by type
function AlertGroup({
  title,
  icon,
  color,
  alerts,
}: {
  title: string;
  icon: React.ReactNode;
  color: "red" | "amber" | "purple" | "blue" | "green";
  alerts: { type: string; severity: string; player_name: string | null; team: string; message: string; detail: string; icon: string }[];
}) {
  const colorStyles = {
    red: {
      header: "bg-red-50 border-red-200 text-red-700",
      icon: "text-red-500",
    },
    amber: {
      header: "bg-amber-50 border-amber-200 text-amber-700",
      icon: "text-amber-500",
    },
    purple: {
      header: "bg-purple-50 border-purple-200 text-purple-700",
      icon: "text-purple-500",
    },
    green: {
      header: "bg-blue-50 border-blue-200 text-blue-700",
      icon: "text-blue-500",
    },
    blue: {
      header: "bg-blue-50 border-blue-200 text-blue-700",
      icon: "text-blue-500",
    },
  };

  const styles = colorStyles[color];

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
      {/* Group Header */}
      <div className={`px-4 py-2.5 flex items-center gap-2 border-b ${styles.header}`}>
        <span className={styles.icon}>{icon}</span>
        <span className="font-semibold text-sm">{title}</span>
        <span className="ml-auto text-xs bg-white/80 px-2 py-0.5 rounded-full font-medium">
          {alerts.length}
        </span>
      </div>

      {/* Alert Items */}
      <div className="divide-y divide-slate-100">
        {alerts.map((alert, idx) => (
          <AlertCardEnhanced key={idx} alert={alert} />
        ))}
      </div>
    </div>
  );
}

// Enhanced Alert Card - Cleaner, more compact design
function AlertCardEnhanced({ alert }: { alert: { type: string; severity: string; player_name: string | null; team: string; message: string; detail: string; icon: string } }) {
  const severityStyles: Record<string, { dot: string; badge: string; badgeText: string }> = {
    high: { dot: "bg-red-500", badge: "bg-red-100 text-red-700", badgeText: "CRITICAL" },
    medium: { dot: "bg-amber-500", badge: "bg-amber-100 text-amber-700", badgeText: "IMPORTANT" },
    warning: { dot: "bg-orange-400", badge: "bg-orange-100 text-orange-700", badgeText: "WATCH" },
    info: { dot: "bg-blue-400", badge: "bg-blue-100 text-blue-700", badgeText: "INFO" },
  };

  const styles = severityStyles[alert.severity] || severityStyles.info;

  return (
    <div className="px-4 py-3 hover:bg-slate-50 transition-colors">
      <div className="flex items-start gap-3">
        {/* Severity indicator */}
        <div className="pt-1.5">
          <div className={`w-2.5 h-2.5 rounded-full ${styles.dot} animate-pulse`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {alert.player_name && (
              <span className="font-bold text-slate-800">{alert.player_name}</span>
            )}
            <span className="text-xs text-slate-400">{alert.team}</span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${styles.badge}`}>
              {styles.badgeText}
            </span>
          </div>
          <p className="text-sm text-slate-700">{alert.message}</p>
          {alert.detail && (
            <p className="text-xs text-slate-500 mt-1">{alert.detail}</p>
          )}
        </div>
      </div>
    </div>
  );
}

// PlayerAlternativesPanel - Shows alternatives for a clicked player on the pitch
function PlayerAlternativesPanel({
  playerId,
  playerName,
  teamId,
  onClose,
  onSelectAlternative,
}: {
  playerId: number;
  playerName: string;
  teamId: string;
  onClose: () => void;
  onSelectAlternative?: (playerId: number, alternativeId: number) => void;
}) {
  const [data, setData] = useState<PlayerAlternativesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAlternatives = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getPlayerAlternatives(playerId, teamId, 3);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch alternatives");
      } finally {
        setLoading(false);
      }
    };

    fetchAlternatives();
  }, [playerId, teamId]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-lg">
        <div className="flex items-center justify-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-violet-500" />
          <span className="text-slate-600">Finding alternatives...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <span className="text-red-600">{error || "No alternatives found"}</span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-violet-200 shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-500 to-purple-600 px-4 py-3 text-white">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-violet-200 uppercase tracking-wide">Upgrades for</p>
            <p className="font-bold text-lg">{data.player_name}</p>
            <p className="text-xs text-violet-200">{data.player_team} • £{data.player_price}m • Form {data.player_form.toFixed(1)}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Budget Info */}
      <div className="px-4 py-2 bg-violet-50 border-b border-violet-100 flex items-center justify-between text-sm">
        <span className="text-slate-600">Budget Available:</span>
        <span className="font-bold text-violet-700">£{data.budget.toFixed(1)}m</span>
        <span className="text-slate-400 text-xs">(£{data.bank.toFixed(1)}m in bank)</span>
      </div>

      {/* Alternatives List */}
      {data.alternatives.length === 0 ? (
        <div className="p-6 text-center">
          <p className="text-slate-500">No suitable alternatives found within budget</p>
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {data.alternatives.map((alt, idx) => (
            <div
              key={alt.id}
              className="p-4 hover:bg-slate-50 cursor-pointer transition-colors"
              onClick={() => onSelectAlternative?.(playerId, alt.id)}
            >
              <div className="flex items-start gap-3">
                {/* Rank Badge */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  idx === 0 ? "bg-amber-100 text-amber-700" :
                  idx === 1 ? "bg-slate-200 text-slate-600" :
                  "bg-orange-100 text-orange-700"
                }`}>
                  <span className="font-bold text-sm">#{alt.rank}</span>
                </div>

                {/* Player Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-slate-800">{alt.name}</span>
                    {idx === 0 && (
                      <span className="text-[9px] font-bold bg-amber-400 text-amber-900 px-1.5 py-0.5 rounded-full">
                        BEST PICK
                      </span>
                    )}
                  </div>

                  {/* Stats Row */}
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                    <span className="font-medium text-slate-600">{alt.team}</span>
                    <span>£{alt.price}m</span>
                    <span>Form: <span className={`font-semibold ${
                      alt.form >= 5 ? "text-emerald-600" :
                      alt.form >= 3 ? "text-amber-600" : "text-red-600"
                    }`}>{alt.form.toFixed(1)}</span></span>
                    <span>{alt.total_points}pts</span>
                  </div>

                  {/* Reasoning */}
                  {alt.reasons.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {alt.reasons.map((reason, rIdx) => (
                        <span
                          key={rIdx}
                          className="text-[10px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full"
                        >
                          {reason}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Price Diff Badge */}
                <div className={`text-xs font-bold px-2 py-1 rounded-lg flex-shrink-0 ${
                  alt.price_diff > 0
                    ? "bg-red-100 text-red-600"
                    : alt.price_diff < 0
                      ? "bg-blue-100 text-blue-600"
                      : "bg-slate-100 text-slate-600"
                }`}>
                  {alt.price_diff > 0
                    ? `+£${alt.price_diff.toFixed(1)}m`
                    : alt.price_diff < 0
                      ? `-£${Math.abs(alt.price_diff).toFixed(1)}m`
                      : "Same"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Browse More Link */}
      <div className="px-4 py-3 bg-slate-50 border-t border-slate-100">
        <a
          href={`/players?pos=${data.player_position}&priceMax=${data.budget.toFixed(1)}&formMin=4&sort=form`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-1.5 text-xs text-violet-600 hover:text-violet-700 font-medium"
        >
          <Search className="w-3.5 h-3.5" />
          Browse all {data.player_position} options
        </a>
      </div>
    </div>
  );
}

// ============================================================================
// Wizard-Style Transfer Flow
// ============================================================================

type WizardMode = "wizard" | "summary";

// Transfers Step Content - Wizard-Style One-at-a-Time Flow
function TransfersContent() {
  const {
    transferSuggestions, transfersLoading, setStep, loadLineup, teamId,
    selectedPlayerForAlternatives, setSelectedPlayerForAlternatives,
    originalSquad,
    sellAnalysis, setSellAnalysis,
    buyAnalysis, setBuyAnalysis,
    wizardSelections, updateWizardSelection, clearWizardSelections,
    loadTransferSuggestions,
    advanceToStep
  } = useTransferWorkflow();

  // AI Analysis loading state - lazy load to save API costs
  const [analysisRequested, setAnalysisRequested] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Wizard state
  const [wizardMode, setWizardMode] = useState<WizardMode>("wizard");
  const [currentStep, setCurrentStep] = useState(0);

  // FPL Rule: Max 3 players from same team
  const MAX_PLAYERS_PER_TEAM = 3;

  // Pending selection - local state for preview before applying
  const [pendingSelection, setPendingSelection] = useState<number | null>(null);

  // Reset pending selection when step changes
  useEffect(() => {
    setPendingSelection(null);
  }, [currentStep]);

  // Load transfer suggestions to get free_transfers count
  useEffect(() => {
    loadTransferSuggestions();
  }, [loadTransferSuggestions]);

  // Load analysis function (extracted for retry capability)
  const loadAnalysis = useCallback(async () => {
    if (!teamId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      console.log("[TransfersContent] Loading sell analysis for team:", teamId);
      const sellData = await getSellAnalysis(teamId);
      console.log("[TransfersContent] Sell analysis loaded:", sellData?.candidates?.length, "candidates");

      // Validate response structure
      if (!sellData || !Array.isArray(sellData.candidates)) {
        throw new Error("Invalid response from sell analysis API");
      }

      setSellAnalysis(sellData);

      const sellIds = sellData.candidates
        .filter(c => c.verdict === "SELL")
        .map(c => c.id);

      console.log("[TransfersContent] SELL candidates:", sellIds.length);
      if (sellIds.length > 0) {
        const buyData = await getBuyAnalysis(teamId, sellIds);
        console.log("[TransfersContent] Buy analysis loaded:", buyData?.recommendations?.length, "recommendations");

        // Validate response structure
        if (!buyData || !Array.isArray(buyData.recommendations)) {
          throw new Error("Invalid response from buy analysis API");
        }

        setBuyAnalysis(buyData);
      }
    } catch (err) {
      console.error("[TransfersContent] Error loading analysis:", err);
      setError(err instanceof Error ? err.message : "Failed to load transfer analysis");
    } finally {
      setLoading(false);
    }
  }, [teamId, setSellAnalysis, setBuyAnalysis]);

  // Trigger analysis when user requests it (lazy load)
  const handleRequestAnalysis = useCallback(() => {
    setAnalysisRequested(true);
    loadAnalysis();
  }, [loadAnalysis]);

  // Get sell candidates (only SELL verdicts)
  const sellCandidates = sellAnalysis?.candidates.filter(c => c.verdict === "SELL") || [];
  const totalSteps = sellCandidates.length;
  const currentCandidate = sellCandidates[currentStep];

  // Calculate current team counts considering applied transfers
  const getTeamCounts = useCallback(() => {
    const counts: Record<string, number> = {};

    // Start with original squad
    originalSquad.forEach(player => {
      counts[player.team] = (counts[player.team] || 0) + 1;
    });

    // Apply confirmed transfers (excluding current step's candidate if being sold)
    Object.entries(wizardSelections).forEach(([candIdStr, repId]) => {
      if (repId === null || repId === undefined) return; // skipped or not decided

      const candId = parseInt(candIdStr);
      const candidate = sellCandidates.find(c => c.id === candId);
      const replacement = buyAnalysis?.recommendations.find(r => r.id === repId);

      if (candidate && replacement) {
        // Subtract the sold player's team
        counts[candidate.team] = Math.max(0, (counts[candidate.team] || 0) - 1);
        // Add the bought player's team
        counts[replacement.team] = (counts[replacement.team] || 0) + 1;
      }
    });

    // If current candidate is being sold, subtract their team count temporarily
    if (currentCandidate) {
      counts[currentCandidate.team] = Math.max(0, (counts[currentCandidate.team] || 0) - 1);
    }

    return counts;
  }, [originalSquad, wizardSelections, sellCandidates, buyAnalysis, currentCandidate]);

  // Get replacements for a specific position with team limit validation
  const getReplacementsForCandidate = useCallback((candidate: SellAnalysisResponse["candidates"][0]) => {
    if (!buyAnalysis) return [];

    const teamCounts = getTeamCounts();

    // Filter out already-selected players
    const selectedReplacementIds = new Set(
      Object.values(wizardSelections).filter((id): id is number => typeof id === "number")
    );

    const positionMatches = buyAnalysis.recommendations.filter(r => r.position === candidate.position && !selectedReplacementIds.has(r.id));

    // Add blocked status to each replacement
    return positionMatches.map(r => {
      const currentTeamCount = teamCounts[r.team] || 0;
      const isBlocked = currentTeamCount >= MAX_PLAYERS_PER_TEAM;
      const blockReason = isBlocked ? `Already have ${currentTeamCount} players from ${r.team}` : null;

      return {
        ...r,
        isBlocked,
        blockReason,
      };
    });
  }, [buyAnalysis, getTeamCounts, MAX_PLAYERS_PER_TEAM, wizardSelections]);

  // Handle replacement selection - just updates preview, doesn't commit
  const handleSelectReplacement = useCallback((replacementId: number | null) => {
    setPendingSelection(replacementId);
  }, []);

  // Apply the transfer - commits pending selection and moves to next step
  const handleApplyTransfer = useCallback(() => {
    if (!currentCandidate || pendingSelection === null) return;
    updateWizardSelection(currentCandidate.id, pendingSelection);
    setPendingSelection(null);
    // Move to next step
    if (currentStep < totalSteps - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      setWizardMode("summary");
    }
  }, [currentCandidate, pendingSelection, updateWizardSelection, currentStep, totalSteps]);

  // Navigate to next step
  const handleNext = useCallback(() => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      // Finished all steps, go to summary
      setWizardMode("summary");
    }
  }, [currentStep, totalSteps]);

  // Skip current transfer
  const handleSkip = useCallback(() => {
    if (!currentCandidate) return;
    updateWizardSelection(currentCandidate.id, null);
    handleNext();
  }, [currentCandidate, handleNext, updateWizardSelection]);

  // Go back to specific step from summary
  const handleEditStep = useCallback((stepIndex: number) => {
    setCurrentStep(stepIndex);
    setWizardMode("wizard");
  }, []);

  // Calculate selected transfers count and budget
  const bank = transferSuggestions?.bank || 0;

  const completedTransfers = Object.entries(wizardSelections)
    .filter(([, repId]) => repId !== null && repId !== undefined)
    .map(([candIdStr, repId]) => {
      const candId = parseInt(candIdStr);
      const candidate = sellCandidates.find(c => c.id === candId);
      const replacement = buyAnalysis?.recommendations.find(r => r.id === repId);
      return { candidate, replacement, repId };
    })
    .filter(t => t.candidate && t.replacement);

  const selectedCount = completedTransfers.length;

  // Calculate budget impact
  const budgetImpact = completedTransfers.reduce((total, { candidate, replacement }) => {
    if (candidate && replacement) {
      return total + (replacement.price - candidate.price);
    }
    return total;
  }, 0);
  const newBank = bank - budgetImpact;
  const canAfford = newBank >= 0;

  // Continue to lineup
  const handleContinue = () => {
    advanceToStep("transfers", "lineup");
  };

  // Initial state - show button to request AI analysis (lazy load)
  if (!analysisRequested && !sellAnalysis) {
    return (
      <div className="space-y-4">
        {/* Info about free transfers */}
        {transferSuggestions && (
          <div className="bg-white rounded-xl p-4 border border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-violet-100">
                  <ArrowRightLeft className="w-5 h-5 text-violet-600" />
                </div>
                <div>
                  <p className="font-semibold text-slate-800">Free Transfers</p>
                  <p className="text-sm text-slate-500">Available this gameweek</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-violet-600">{transferSuggestions.free_transfers}</p>
                <p className="text-xs text-slate-500">£{bank.toFixed(1)}m in bank</p>
              </div>
            </div>
          </div>
        )}

        {/* Main CTA to get AI analysis */}
        <div className="bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl p-6 text-white">
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="p-3 rounded-full bg-white/20">
                <Sparkles className="w-8 h-8" />
              </div>
            </div>
            <div>
              <h3 className="text-xl font-bold">Get AI Transfer Suggestions</h3>
              <p className="text-sm text-violet-200 mt-1">
                Claude AI will analyse your squad and recommend the best transfers
              </p>
            </div>
            <button
              onClick={handleRequestAnalysis}
              className="w-full py-3 bg-white text-violet-600 rounded-xl font-bold text-lg hover:bg-violet-50 transition-colors flex items-center justify-center gap-2"
            >
              <Zap className="w-5 h-5" />
              Analyse My Squad
            </button>
          </div>
        </div>

        {/* Skip transfers option */}
        <div className="text-center">
          <button
            onClick={handleContinue}
            className="text-sm text-slate-500 hover:text-slate-700 underline"
          >
            Skip transfers and set lineup
          </button>
        </div>

        {/* Browse All Players Link */}
        <div className="bg-white rounded-xl p-4 border border-slate-200">
          <a
            href="/players"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-violet-100 group-hover:bg-violet-200 transition-colors">
                <Search className="w-5 h-5 text-violet-600" />
              </div>
              <div>
                <p className="font-semibold text-slate-800 group-hover:text-violet-600 transition-colors">Browse All Players</p>
                <p className="text-sm text-slate-500">Use faceted search to find players</p>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-violet-600 transition-colors" />
          </a>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading || transfersLoading) {
    return (
      <div className="space-y-4">
        <div className="bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl p-6 text-white">
          <div className="flex items-center gap-3">
            <Loader2 className="w-6 h-6 animate-spin" />
            <div>
              <p className="font-bold">Analyzing Your Squad...</p>
              <p className="text-sm text-violet-200">SmartPlay AI is finding the best transfers for you</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-4">
        <div className="bg-red-50 rounded-xl p-6 border border-red-200">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0" />
            <div>
              <p className="font-bold text-red-800">Analysis Failed</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={loadAnalysis}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700"
                >
                  Retry
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-300"
                >
                  Reload Page
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // No sell candidates - squad is healthy
  if (sellCandidates.length === 0) {
    return (
      <div className="space-y-4">
        <div className="bg-gradient-to-br from-violet-600 to-blue-600 rounded-xl p-6 text-white">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-white/20">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Squad Looking Strong!</h3>
              <p className="text-sm text-blue-100">No urgent transfers needed this week</p>
            </div>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold">£{bank.toFixed(1)}m</p>
            <p className="text-xs text-blue-200">In The Bank</p>
          </div>
        </div>

        {sellAnalysis?.summary && (
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-violet-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-slate-700">{sellAnalysis.summary}</p>
            </div>
          </div>
        )}

        <div className="text-center py-4">
          <p className="text-sm text-slate-500">Consider saving your transfers for upcoming fixture swings</p>
        </div>

        <ContinueButton onClick={handleContinue} label="Set Lineup" color="blue" />
      </div>
    );
  }

  // ============================================================================
  // SUMMARY MODE - Show all completed transfers
  // ============================================================================
  if (wizardMode === "summary") {
    const skippedCount = Object.entries(wizardSelections).filter(([, v]) => v === null).length;

    return (
      <div className="space-y-4">
        {/* Summary Header */}
        <div className="bg-gradient-to-br from-violet-600 to-blue-600 rounded-xl p-5 text-white">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2.5 rounded-xl bg-white/20">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold">Your Transfer Plan</h3>
              <p className="text-sm text-blue-100">
                {selectedCount} transfer{selectedCount !== 1 ? "s" : ""} selected
                {skippedCount > 0 && `, ${skippedCount} skipped`}
              </p>
            </div>
          </div>

          {/* Budget Summary */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/10 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold">{selectedCount}</p>
              <p className="text-xs text-blue-200">Transfers</p>
            </div>
            <div className="bg-white/10 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold">£{newBank.toFixed(1)}m</p>
              <p className="text-xs text-blue-200">New Bank</p>
            </div>
          </div>
        </div>

        {/* Transfer List */}
        <div className="space-y-2">
          {sellCandidates.map((candidate, idx) => {
            const selection = wizardSelections[candidate.id];
            const isSkipped = selection === null;
            const replacement = !isSkipped && selection ? buyAnalysis?.recommendations.find(r => r.id === selection) : null;
            const priceDiff = replacement ? replacement.price - candidate.price : 0;

            return (
              <div
                key={candidate.id}
                className={`rounded-xl border-2 p-4 transition-all ${
                  isSkipped
                    ? "border-slate-200 bg-slate-50"
                    : replacement
                      ? "border-violet-300 bg-violet-50"
                      : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex items-center gap-3">
                  {/* Status indicator */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    isSkipped ? "bg-slate-200" : "bg-violet-500"
                  }`}>
                    {isSkipped ? (
                      <X className="w-4 h-4 text-slate-500" />
                    ) : (
                      <Check className="w-4 h-4 text-white" />
                    )}
                  </div>

                  {/* Transfer details */}
                  <div className="flex-1 min-w-0">
                    {isSkipped ? (
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-500 line-through">{candidate.name}</span>
                        <span className="text-xs text-slate-400">Skipped</span>
                      </div>
                    ) : replacement ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-800">{candidate.name}</span>
                        <ArrowRight className="w-4 h-4 text-violet-500" />
                        <span className="font-bold text-violet-700">{replacement.name}</span>
                        <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                          priceDiff > 0 ? "bg-red-100 text-red-600" : priceDiff < 0 ? "bg-blue-100 text-blue-600" : "bg-slate-100 text-slate-600"
                        }`}>
                          {priceDiff > 0 ? `+£${priceDiff.toFixed(1)}m` : priceDiff < 0 ? `-£${Math.abs(priceDiff).toFixed(1)}m` : "Same"}
                        </span>
                      </div>
                    ) : (
                      <span className="font-semibold text-slate-600">{candidate.name}</span>
                    )}
                  </div>

                  {/* Edit button */}
                  <button
                    onClick={() => handleEditStep(idx)}
                    className="text-xs font-medium text-violet-600 hover:text-violet-700 px-3 py-1.5 rounded-lg hover:bg-violet-50 transition-colors"
                  >
                    Edit
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Budget Warning */}
        {!canAfford && (
          <div className="bg-red-50 rounded-xl p-4 border border-red-200 flex items-start gap-3">
            <X className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-800">Over Budget</p>
              <p className="text-sm text-red-700 mt-1">
                You&apos;re £{Math.abs(newBank).toFixed(1)}m over. Edit your transfers.
              </p>
            </div>
          </div>
        )}

        {/* Continue Button */}
        <ContinueButton
          onClick={handleContinue}
          label={selectedCount > 0 ? `Confirm ${selectedCount} Transfer${selectedCount !== 1 ? "s" : ""}` : "Confirm Squad"}
          color="teal"
          disabled={!canAfford}
        />
      </div>
    );
  }

  // ============================================================================
  // WIZARD MODE - One transfer at a time
  // ============================================================================
  const replacements = currentCandidate ? getReplacementsForCandidate(currentCandidate) : [];
  // Use pendingSelection for current preview, fall back to committed selection
  const currentSelection = pendingSelection !== null ? pendingSelection : (currentCandidate ? wizardSelections[currentCandidate.id] : undefined);
  const hasSelection = pendingSelection !== null;  // Only show Apply button when there's a pending selection

  return (
    <div className="space-y-4">
      {/* Progress Header */}
      <div className="bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-white/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-violet-200">Transfer {currentStep + 1} of {totalSteps}</p>
              <p className="text-xs text-violet-300">Powered by Claude</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="bg-white/20 rounded-lg px-3 py-1.5 text-center">
              <p className="text-lg font-bold">£{bank.toFixed(1)}m</p>
              <p className="text-[10px] text-violet-200">In Bank</p>
            </div>
            <button
              onClick={() => {
                clearWizardSelections();
                setCurrentStep(0);
              }}
              className="text-sm font-medium text-violet-200 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/10 transition-colors flex items-center gap-1"
            >
              <RotateCcw className="w-4 h-4" /> Reset All
            </button>
            <button
              onClick={handleSkip}
              className="text-sm font-medium text-violet-200 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/10 transition-colors flex items-center gap-1"
            >
              Skip <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="h-2 bg-white/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-white rounded-full transition-all duration-300"
            style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
          />
        </div>
        <div className="flex justify-between mt-2">
          {sellCandidates.map((_, idx) => (
            <div
              key={idx}
              className={`w-2 h-2 rounded-full ${
                idx < currentStep
                  ? "bg-emerald-400"
                  : idx === currentStep
                    ? "bg-white"
                    : "bg-white/30"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Sell Candidate Card */}
      {currentCandidate && (
        <div className="bg-red-50 rounded-xl border-2 border-red-200 overflow-hidden">
          <div className="px-4 py-2 bg-red-100 border-b border-red-200">
            <p className="text-xs font-bold text-red-700 uppercase tracking-wide flex items-center gap-2">
              <ArrowRightLeft className="w-3.5 h-3.5" />
              Selling
            </p>
          </div>
          <div className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-full bg-red-200 flex items-center justify-center flex-shrink-0">
                <span className="text-lg font-bold text-red-700">{currentCandidate.name.charAt(0)}</span>
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-slate-800">{currentCandidate.name}</h3>
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <span>{currentCandidate.team}</span>
                  <span>•</span>
                  <span>£{currentCandidate.price}m</span>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg p-3 border border-red-100">
              <p className="text-sm text-slate-700 leading-relaxed">{currentCandidate.reasoning}</p>
            </div>
          </div>
        </div>
      )}

      {/* Replacements Section */}
      <div className="bg-white rounded-xl border-2 border-slate-200 overflow-hidden">
        <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200">
          <p className="text-xs font-bold text-emerald-700 uppercase tracking-wide flex items-center gap-2">
            <Target className="w-3.5 h-3.5" />
            Pick Replacement
          </p>
        </div>

        {replacements.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-slate-500">No suitable replacements found within budget</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {/* Sort: available players first, then blocked */}
            {[...replacements]
              .sort((a, b) => (a.isBlocked ? 1 : 0) - (b.isBlocked ? 1 : 0))
              .slice(0, 5) // Show up to 5 including blocked ones
              .map((replacement, idx) => {
              const priceDiff = replacement.price - (currentCandidate?.price || 0);
              const isSelected = currentSelection === replacement.id;
              const availableReplacements = replacements.filter(r => !r.isBlocked);
              const isBest = !replacement.isBlocked && availableReplacements[0]?.id === replacement.id;

              // Blocked player - show but cannot select
              if (replacement.isBlocked) {
                return (
                  <div
                    key={replacement.id}
                    className="flex items-start gap-4 p-4 bg-slate-50 opacity-70"
                  >
                    {/* Blocked indicator */}
                    <div className="w-5 h-5 mt-1 flex items-center justify-center">
                      <X className="w-4 h-4 text-slate-400" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-bold text-lg text-slate-500 line-through">
                          {replacement.name}
                        </span>
                        <span className="text-[10px] font-bold bg-red-100 text-red-600 px-2 py-0.5 rounded-full">
                          BLOCKED
                        </span>
                      </div>

                      <div className="flex items-center gap-3 text-sm text-slate-400 mb-2">
                        <span className="font-medium">{replacement.team}</span>
                        <span>£{replacement.price}m</span>
                        <span>Form: {replacement.form.toFixed(1)}</span>
                      </div>

                      {/* Block reason message */}
                      <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                        <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-amber-800">Good pick, but unavailable</p>
                          <p className="text-xs text-amber-700">{replacement.blockReason} (FPL max 3 per team)</p>
                        </div>
                      </div>
                    </div>

                    {/* Price diff badge - muted */}
                    <div className="text-sm font-bold px-3 py-1.5 rounded-lg flex-shrink-0 bg-slate-200 text-slate-500">
                      {priceDiff > 0 ? `+£${priceDiff.toFixed(1)}m` : priceDiff < 0 ? `-£${Math.abs(priceDiff).toFixed(1)}m` : "Same"}
                    </div>
                  </div>
                );
              }

              // Available player - can select
              return (
                <label
                  key={replacement.id}
                  className={`flex items-start gap-4 p-4 cursor-pointer transition-all ${
                    isSelected ? "bg-emerald-50" : "hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="replacement"
                    checked={isSelected}
                    onChange={() => handleSelectReplacement(replacement.id)}
                    className="w-5 h-5 text-emerald-600 mt-1"
                  />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`font-bold text-lg ${isSelected ? "text-emerald-700" : "text-slate-800"}`}>
                        {replacement.name}
                      </span>
                      {isBest && (
                        <span className="text-[10px] font-bold bg-amber-400 text-amber-900 px-2 py-0.5 rounded-full">
                          BEST PICK
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-sm text-slate-600 mb-2">
                      <span className="font-medium">{replacement.team}</span>
                      <span>£{replacement.price}m</span>
                      <span>Form: <span className={`font-bold ${
                        replacement.form >= 6 ? "text-emerald-600" :
                        replacement.form >= 4 ? "text-amber-600" : "text-slate-600"
                      }`}>{replacement.form.toFixed(1)}</span></span>
                      <span>{replacement.ownership}% owned</span>
                    </div>

                    {replacement.reasoning && (
                      <p className="text-sm text-slate-600 bg-slate-50 rounded-lg p-2.5 leading-relaxed">
                        {replacement.reasoning}
                      </p>
                    )}
                  </div>

                  {/* Price diff badge */}
                  <div className={`text-sm font-bold px-3 py-1.5 rounded-lg flex-shrink-0 ${
                    priceDiff > 0
                      ? "bg-red-100 text-red-600"
                      : priceDiff < 0
                        ? "bg-emerald-100 text-emerald-600"
                        : "bg-slate-100 text-slate-600"
                  }`}>
                    {priceDiff > 0 ? `+£${priceDiff.toFixed(1)}m` : priceDiff < 0 ? `-£${Math.abs(priceDiff).toFixed(1)}m` : "Same"}
                  </div>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* Player Alternatives Panel - Shows when a player is clicked on the pitch */}
      {selectedPlayerForAlternatives && teamId && (
        <PlayerAlternativesPanel
          playerId={selectedPlayerForAlternatives.id}
          playerName={selectedPlayerForAlternatives.name}
          teamId={teamId}
          onClose={() => setSelectedPlayerForAlternatives(null)}
        />
      )}

      {/* Action Buttons */}
      <div className="space-y-2">
        {/* Apply Transfer Button - Only commits and moves forward when clicked */}
        {hasSelection && (
          <button
            onClick={handleApplyTransfer}
            className="w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2 bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg"
          >
            <Check className="w-5 h-5" />
            Apply Transfer
          </button>
        )}

        {/* Skip Button - Keep player, move to next */}
        {!hasSelection && (
          <button
            onClick={() => {
              // Skip this player (mark as null = intentionally kept)
              if (currentCandidate) {
                updateWizardSelection(currentCandidate.id, null);
              }
              handleNext();
            }}
            className="w-full py-3.5 rounded-xl font-bold text-base transition-all flex items-center justify-center gap-2 border-2 border-slate-300 text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
            Keep Player & Skip
          </button>
        )}
      </div>

      {/* Hint text */}
      {!hasSelection && (
        <p className="text-center text-xs text-slate-400">
          Select a replacement above to see Apply Transfer button
        </p>
      )}
    </div>
  );
}

// Lineup Step Content - Formation strategies with SmartPlay scores, Chip Strategy & AI Squad Analysis
function LineupContent() {
  const {
    setStep,
    teamId,
    lineupStrategies,
    lineupStrategiesLoading,
    selectedStrategy,
    selectedPlayerForCard,
    loadLineupStrategies,
    selectStrategy,
    setSelectedPlayerForCard,
    chipAdvice,
    chipAdviceLoading,
    loadChipAdvice,
    wizardSelections,
    sellAnalysis,
    buyAnalysis,
    advanceToStep,
  } = useTransferWorkflow();

  // Local state for toggleable sections
  const [showChipStrategy, setShowChipStrategy] = useState(false);
  const [lineupError, setLineupError] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLineupError(false);
      try {
        await loadLineupStrategies();
      } catch {
        setLineupError(true);
      }
    };
    load();
    loadChipAdvice();
  }, [loadLineupStrategies, loadChipAdvice]);

  // Retry loading lineup strategies
  const handleRetryLineup = async () => {
    setLineupError(false);
    try {
      await loadLineupStrategies();
    } catch {
      setLineupError(true);
    }
  };

  if (lineupStrategiesLoading) {
    return <LoadingState message="Analyzing formation options..." />;
  }

  if (lineupError || !lineupStrategies || !selectedStrategy) {
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto mb-3" />
          <h3 className="font-semibold text-slate-700 mb-2">Unable to load lineup strategies</h3>
          <p className="text-sm text-slate-500 mb-4">This may be a temporary issue. Please try again.</p>
          <button
            onClick={handleRetryLineup}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Strategy colors and icons
  const strategyStyles: Record<string, { bg: string; border: string; icon: string }> = {
    balanced: { bg: "bg-blue-500", border: "border-blue-500", icon: "⚖️" },
    attacking: { bg: "bg-rose-500", border: "border-rose-500", icon: "⚔️" },
    defensive: { bg: "bg-emerald-500", border: "border-emerald-500", icon: "🛡️" },
  };

  // Chip icons and colors
  const chipIcons: Record<string, React.ReactNode> = {
    wildcard: <RefreshCw className="w-4 h-4" />,
    freehit: <Zap className="w-4 h-4" />,
    bboost: <Users className="w-4 h-4" />,
    "3xc": <Crown className="w-4 h-4" />,
  };

  const chipColors: Record<string, string> = {
    wildcard: "from-rose-500 to-rose-600",
    freehit: "from-cyan-500 to-cyan-600",
    bboost: "from-green-500 to-green-600",
    "3xc": "from-amber-500 to-amber-600",
  };

  return (
    <div className="space-y-4">
      {/* Strategy Selector - 3 Options */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-blue-500" />
          Choose Your Strategy
        </h3>
        <div className="grid grid-cols-3 gap-2">
          {lineupStrategies.strategies.map((strategy) => {
            const style = strategyStyles[strategy.strategy] || strategyStyles.balanced;
            const isSelected = selectedStrategy.strategy === strategy.strategy;
            const isRecommended = strategy.strategy === lineupStrategies.recommended;

            return (
              <button
                key={strategy.strategy}
                onClick={() => selectStrategy(strategy.strategy)}
                className={`relative p-3 rounded-xl border-2 transition-all ${
                  isSelected
                    ? `${style.border} bg-opacity-10 shadow-md`
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                {/* Recommended badge */}
                {isRecommended && (
                  <div className="absolute -top-2 left-1/2 -translate-x-1/2">
                    <span className="px-2 py-0.5 text-[9px] font-bold bg-amber-400 text-amber-900 rounded-full whitespace-nowrap">
                      RECOMMENDED
                    </span>
                  </div>
                )}

                {/* Strategy icon and name */}
                <div className="text-center mb-2 mt-1">
                  <span className="text-2xl">{style.icon}</span>
                  <p className={`font-bold text-sm ${isSelected ? "text-slate-800" : "text-slate-600"}`}>
                    {strategy.name}
                  </p>
                </div>

                {/* Formation and score */}
                <div className={`rounded-lg p-2 ${isSelected ? style.bg + " bg-opacity-10" : "bg-slate-50"}`}>
                  <p className={`text-lg font-bold ${isSelected ? "text-slate-800" : "text-slate-600"}`}>
                    {strategy.formation}
                  </p>
                  <div className="flex items-center justify-center gap-1 mt-1">
                    <span className="text-[10px] text-slate-500">SP</span>
                    <span className={`text-sm font-bold ${
                      strategy.avg_smartplay_score >= 7 ? "text-emerald-600" :
                      strategy.avg_smartplay_score >= 5.5 ? "text-blue-600" : "text-slate-600"
                    }`}>
                      {strategy.avg_smartplay_score.toFixed(1)}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Strategy description */}
        <p className="text-xs text-slate-500 mt-3 text-center">
          {selectedStrategy.description}
        </p>
      </div>

      {/* Chip Strategy Section - Collapsible */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <button
          onClick={() => setShowChipStrategy(!showChipStrategy)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-purple-500" />
            <span className="font-semibold text-slate-700">Chip Strategy</span>
            {chipAdvice && chipAdvice.recommendations.some(r => r.recommendation === "consider") && (
              <span className="text-[10px] px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full font-medium">
                CHIP WEEK
              </span>
            )}
          </div>
          <ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${showChipStrategy ? "rotate-90" : ""}`} />
        </button>

        {showChipStrategy && (
          <div className="px-4 pb-4 border-t border-slate-100">
            {chipAdviceLoading ? (
              <div className="py-4 text-center text-sm text-slate-500">Loading chip advice...</div>
            ) : chipAdvice ? (
              <div className="space-y-3 mt-3">
                {/* Overall advice */}
                <p className="text-sm text-slate-600 bg-purple-50 rounded-lg p-3">{chipAdvice.overall_advice}</p>

                {/* Chip grid */}
                <div className="grid grid-cols-2 gap-2">
                  {chipAdvice.recommendations.map((rec) => {
                    const isUsed = !chipAdvice.available_chips?.includes(rec.chip);
                    return (
                      <div
                        key={rec.chip}
                        className={`rounded-lg p-3 border relative ${
                          isUsed
                            ? "bg-slate-100 border-slate-200 opacity-60"
                            : rec.recommendation === "consider"
                              ? "bg-gradient-to-br " + (chipColors[rec.chip] || "from-slate-500 to-slate-600") + " text-white border-transparent"
                              : "bg-slate-50 border-slate-200"
                        }`}
                      >
                        {/* Status badge */}
                        <div className={`absolute top-1 right-1 text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          isUsed ? "bg-slate-400 text-white" : "bg-emerald-500 text-white"
                        }`}>
                          {isUsed ? "USED" : "AVAILABLE"}
                        </div>
                        <div className={`flex items-center gap-1.5 mb-1 ${isUsed ? "text-slate-400" : ""}`}>
                          {chipIcons[rec.chip]}
                          <span className={`font-semibold text-sm ${isUsed ? "line-through" : ""}`}>{rec.name}</span>
                        </div>
                        <p className={`text-[10px] ${isUsed ? "text-slate-400" : rec.recommendation === "consider" ? "opacity-90" : "text-slate-500"}`}>
                          {isUsed ? "Already used this season" : rec.message}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="py-4 text-center text-sm text-slate-500">Unable to load chip advice</div>
            )}
          </div>
        )}
      </div>

      {/* Explainability hint - Click on pitch */}
      <div className="flex items-center gap-2 px-3 py-2 bg-purple-50 rounded-lg border border-purple-200">
        <HelpCircle className="w-4 h-4 text-purple-500" />
        <p className="text-xs text-purple-700">
          <span className="font-semibold">Click any player on the pitch</span> to see why they were selected
        </p>
      </div>

      {/* Player Why Card Panel - Shown when a player is selected */}
      {selectedPlayerForCard ? (
        <PlayerWhyCard
          player={selectedPlayerForCard}
          isOpen={true}
          onClose={() => setSelectedPlayerForCard(null)}
          isBench={'order' in selectedPlayerForCard}
          benchOrder={'order' in selectedPlayerForCard ? selectedPlayerForCard.order : undefined}
          isPanel={true}
        />
      ) : (
        /* Empty state prompting to click on pitch */
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
          <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <Users className="w-6 h-6 text-slate-400" />
          </div>
          <p className="font-semibold text-slate-700 mb-1">Select a Player</p>
          <p className="text-sm text-slate-500">
            Click on any player on the pitch to see their selection reasoning and SmartPlay score breakdown
          </p>
        </div>
      )}


      <ContinueButton onClick={() => advanceToStep("lineup", "captain")} label="Pick Captain" color="amber" />
    </div>
  );
}

// Captain Step Content - Dedicated captain selection with SmartPlay scores
function CaptainContent() {
  const {
    lineup, lineupLoading, loadLineup, advanceToStep,
    selectedCaptainId, selectedViceCaptainId, setSelectedCaptainId, setSelectedViceCaptainId
  } = useTransferWorkflow();

  // Local state for picker visibility only
  const [showCaptainPicker, setShowCaptainPicker] = useState(false);
  const [showViceCaptainPicker, setShowViceCaptainPicker] = useState(false);

  useEffect(() => {
    loadLineup();
  }, [loadLineup]);

  // Initialize selections from AI recommendations when lineup loads (only if not already set)
  useEffect(() => {
    if (lineup && selectedCaptainId === null) {
      setSelectedCaptainId(lineup.captain?.id || null);
      setSelectedViceCaptainId(lineup.vice_captain?.id || null);
    }
  }, [lineup, selectedCaptainId, setSelectedCaptainId, setSelectedViceCaptainId]);

  if (lineupLoading) {
    return <LoadingState message="Analyzing captain options..." />;
  }

  if (!lineup) {
    return <ErrorState message="Failed to load captain picks" />;
  }

  // Get all eligible players (non-goalkeepers from starting XI)
  const eligiblePlayers = lineup.starting_xi
    .filter(p => p.position !== "GKP")
    .sort((a, b) => b.score - a.score);

  // Use selected IDs or fall back to AI recommendations
  const captainId = selectedCaptainId || lineup.captain?.id;
  const viceCaptainId = selectedViceCaptainId || lineup.vice_captain?.id;

  // Find the captain and vice captain from the starting XI
  const captainPlayer = lineup.starting_xi.find(p => p.id === captainId);
  const viceCaptainPlayer = lineup.starting_xi.find(p => p.id === viceCaptainId);

  // Check if using AI recommendation
  const isUsingAICaptain = captainId === lineup.captain?.id;
  const isUsingAIViceCaptain = viceCaptainId === lineup.vice_captain?.id;

  // Get score color based on value
  const getScoreColor = (score: number) => {
    if (score >= 7.5) return "text-emerald-600 bg-emerald-50 border-emerald-200";
    if (score >= 6.0) return "text-blue-600 bg-blue-50 border-blue-200";
    if (score >= 4.5) return "text-amber-600 bg-amber-50 border-amber-200";
    return "text-slate-600 bg-slate-50 border-slate-200";
  };

  // Handle captain selection
  const handleSelectCaptain = (playerId: number) => {
    if (playerId === viceCaptainId) {
      // Swap: make current captain the vice captain
      setSelectedViceCaptainId(captainId || null);
    }
    setSelectedCaptainId(playerId);
    setShowCaptainPicker(false);
  };

  // Handle vice captain selection
  const handleSelectViceCaptain = (playerId: number) => {
    if (playerId === captainId) {
      // Swap: make current vice captain the captain
      setSelectedCaptainId(viceCaptainId || null);
    }
    setSelectedViceCaptainId(playerId);
    setShowViceCaptainPicker(false);
  };

  // Reset to AI recommendations
  const handleResetToAI = () => {
    setSelectedCaptainId(lineup.captain?.id || null);
    setSelectedViceCaptainId(lineup.vice_captain?.id || null);
  };

  return (
    <div className="space-y-4">
      {/* Captain Header */}
      <div className="bg-gradient-to-br from-amber-500 to-amber-600 rounded-xl p-5 text-white">
        <div className="flex items-center gap-3 mb-2">
          <Crown className="w-8 h-8" />
          <div>
            <h3 className="text-xl font-bold">Captain Selection</h3>
            <p className="text-amber-100 text-sm">Choose wisely - double points await!</p>
          </div>
        </div>
      </div>

      {/* Your Captain */}
      {captainPlayer && (
        <div className={`rounded-xl p-4 border-2 ${isUsingAICaptain ? "bg-amber-50 border-amber-300" : "bg-violet-50 border-violet-300"}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Crown className={`w-6 h-6 ${isUsingAICaptain ? "text-amber-600" : "text-violet-600"}`} />
              <span className={`font-bold ${isUsingAICaptain ? "text-amber-800" : "text-violet-800"}`}>
                {isUsingAICaptain ? "AI Recommended Captain" : "Your Captain"}
              </span>
              {!isUsingAICaptain && (
                <span className="text-xs bg-violet-200 text-violet-700 px-2 py-0.5 rounded-full">Custom</span>
              )}
            </div>
            <div className={`px-3 py-1.5 rounded-lg border ${getScoreColor(captainPlayer.score)}`}>
              <p className="text-xl font-bold leading-none">{captainPlayer.score.toFixed(1)}</p>
              <p className="text-[10px] text-center opacity-70">SmartPlay</p>
            </div>
          </div>
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
              captainPlayer.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
              captainPlayer.position === "MID" ? "bg-blue-100 text-blue-700" : "bg-rose-100 text-rose-700"
            }`}>
              {captainPlayer.position}
            </div>
            <div className="flex-1">
              <p className="text-2xl font-bold text-slate-800">{captainPlayer.name}</p>
              <p className="text-sm text-slate-500">
                {captainPlayer.team}
                {captainPlayer.smartplay_data && ` • vs ${captainPlayer.smartplay_data.next_opponent}`}
              </p>
            </div>
          </div>
          {isUsingAICaptain && lineup.captain?.reasons && lineup.captain.reasons.length > 0 && (
            <div className="space-y-1 bg-white/50 rounded-lg p-3 mb-3">
              {lineup.captain.reasons.map((reason, idx) => (
                <p key={idx} className="text-sm text-amber-700 flex items-center gap-2">
                  <Check className="w-4 h-4 flex-shrink-0" /> {reason}
                </p>
              ))}
            </div>
          )}
          <button
            onClick={() => setShowCaptainPicker(!showCaptainPicker)}
            className="w-full py-2 px-3 bg-white/80 hover:bg-white rounded-lg text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Change Captain
          </button>
        </div>
      )}

      {/* Captain Picker */}
      {showCaptainPicker && (
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-lg">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-slate-700">Select Captain</h4>
            <button onClick={() => setShowCaptainPicker(false)} className="text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {eligiblePlayers.map((player) => (
              <button
                key={player.id}
                onClick={() => handleSelectCaptain(player.id)}
                disabled={player.id === captainId}
                className={`w-full flex items-center gap-3 p-2 rounded-lg transition-colors ${
                  player.id === captainId
                    ? "bg-amber-100 border border-amber-300 cursor-default"
                    : "hover:bg-slate-50 border border-transparent"
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                  player.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
                  player.position === "MID" ? "bg-blue-100 text-blue-700" : "bg-rose-100 text-rose-700"
                }`}>
                  {player.position.slice(0, 3)}
                </div>
                <div className="flex-1 text-left">
                  <span className="font-medium text-slate-700">{player.name}</span>
                  <span className="text-xs text-slate-400 ml-2">{player.team}</span>
                </div>
                <div className={`px-2 py-1 rounded-lg ${getScoreColor(player.score)}`}>
                  <p className="text-sm font-bold">{player.score.toFixed(1)}</p>
                </div>
                {player.id === lineup.captain?.id && (
                  <span className="text-[10px] bg-amber-200 text-amber-700 px-1.5 py-0.5 rounded">AI Pick</span>
                )}
                {player.id === captainId && (
                  <Check className="w-4 h-4 text-amber-600" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Vice Captain */}
      {viceCaptainPlayer && (
        <div className={`rounded-xl p-4 border ${isUsingAIViceCaptain ? "bg-slate-100 border-slate-200" : "bg-violet-50 border-violet-200"}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Award className={`w-5 h-5 ${isUsingAIViceCaptain ? "text-slate-500" : "text-violet-500"}`} />
              <span className={`font-semibold ${isUsingAIViceCaptain ? "text-slate-600" : "text-violet-700"}`}>
                {isUsingAIViceCaptain ? "Vice Captain" : "Your Vice Captain"}
              </span>
              {!isUsingAIViceCaptain && (
                <span className="text-xs bg-violet-200 text-violet-700 px-2 py-0.5 rounded-full">Custom</span>
              )}
            </div>
            <div className={`px-2.5 py-1 rounded-lg border ${getScoreColor(viceCaptainPlayer.score)}`}>
              <p className="text-lg font-bold leading-none">{viceCaptainPlayer.score.toFixed(1)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
              viceCaptainPlayer.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
              viceCaptainPlayer.position === "MID" ? "bg-blue-100 text-blue-700" : "bg-rose-100 text-rose-700"
            }`}>
              {viceCaptainPlayer.position.slice(0, 3)}
            </div>
            <div className="flex-1">
              <p className="text-lg font-bold text-slate-800">{viceCaptainPlayer.name}</p>
              <p className="text-xs text-slate-500">Steps in if captain doesn't play</p>
            </div>
          </div>
          <button
            onClick={() => setShowViceCaptainPicker(!showViceCaptainPicker)}
            className="w-full py-2 px-3 bg-white/80 hover:bg-white rounded-lg text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Change Vice Captain
          </button>
        </div>
      )}

      {/* Vice Captain Picker */}
      {showViceCaptainPicker && (
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-lg">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-slate-700">Select Vice Captain</h4>
            <button onClick={() => setShowViceCaptainPicker(false)} className="text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {eligiblePlayers.map((player) => (
              <button
                key={player.id}
                onClick={() => handleSelectViceCaptain(player.id)}
                disabled={player.id === viceCaptainId}
                className={`w-full flex items-center gap-3 p-2 rounded-lg transition-colors ${
                  player.id === viceCaptainId
                    ? "bg-slate-200 border border-slate-300 cursor-default"
                    : "hover:bg-slate-50 border border-transparent"
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                  player.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
                  player.position === "MID" ? "bg-blue-100 text-blue-700" : "bg-rose-100 text-rose-700"
                }`}>
                  {player.position.slice(0, 3)}
                </div>
                <div className="flex-1 text-left">
                  <span className="font-medium text-slate-700">{player.name}</span>
                  <span className="text-xs text-slate-400 ml-2">{player.team}</span>
                </div>
                <div className={`px-2 py-1 rounded-lg ${getScoreColor(player.score)}`}>
                  <p className="text-sm font-bold">{player.score.toFixed(1)}</p>
                </div>
                {player.id === lineup.vice_captain?.id && (
                  <span className="text-[10px] bg-slate-300 text-slate-600 px-1.5 py-0.5 rounded">AI Pick</span>
                )}
                {player.id === viceCaptainId && (
                  <Check className="w-4 h-4 text-slate-600" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Reset to AI button */}
      {(!isUsingAICaptain || !isUsingAIViceCaptain) && (
        <button
          onClick={handleResetToAI}
          className="w-full py-2 px-3 bg-amber-50 hover:bg-amber-100 rounded-lg text-sm font-medium text-amber-700 transition-colors flex items-center justify-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          Reset to AI Recommendations
        </button>
      )}

      <ContinueButton onClick={() => advanceToStep("captain", "confirm")} label="Final Review" color="emerald" />
    </div>
  );
}

// Chips Step Content
function ChipsContent() {
  const { chipAdvice, chipAdviceLoading, loadChipAdvice, setStep, loadTransferSuggestions, teamId } = useTransferWorkflow();

  useEffect(() => {
    loadChipAdvice();
  }, [loadChipAdvice]);

  if (chipAdviceLoading) {
    return <LoadingState message="Analyzing chip options..." />;
  }

  if (!chipAdvice) {
    return <ErrorState message="Failed to load chip advice" />;
  }

  const chipIcons: Record<string, React.ReactNode> = {
    wildcard: <RefreshCw className="w-5 h-5" />,
    freehit: <Zap className="w-5 h-5" />,
    bboost: <Users className="w-5 h-5" />,
    "3xc": <Crown className="w-5 h-5" />,
  };

  const chipColors: Record<string, string> = {
    wildcard: "from-rose-500 to-rose-600",
    freehit: "from-cyan-500 to-cyan-600",
    bboost: "from-green-500 to-green-600",
    "3xc": "from-amber-500 to-amber-600",
  };

  return (
    <div className="space-y-4">
      {/* Chip Strategy Summary */}
      <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-5 text-white">
        <div className="flex items-center gap-2 mb-2">
          <Lightbulb className="w-5 h-5" />
          <span className="font-semibold">Chip Strategy</span>
        </div>
        <p className="text-purple-50 text-sm">{chipAdvice.overall_advice}</p>
      </div>

      {/* Chip Recommendations */}
      <div className="grid grid-cols-2 gap-3">
        {chipAdvice.recommendations.map((rec) => {
          const isUsed = !chipAdvice.available_chips?.includes(rec.chip);
          return (
            <div
              key={rec.chip}
              className={`rounded-xl p-4 border relative ${
                isUsed
                  ? "bg-slate-100 border-slate-200 opacity-50"
                  : rec.recommendation === "consider"
                    ? "bg-gradient-to-br " + (chipColors[rec.chip] || "from-slate-500 to-slate-600") + " text-white"
                    : "bg-slate-50 border-slate-200"
              }`}
            >
              {/* Status badge - always shown */}
              <div className={`absolute top-2 right-2 text-[10px] font-bold px-2 py-1 rounded ${
                isUsed ? "bg-slate-400 text-white" : "bg-emerald-500 text-white"
              }`}>
                {isUsed ? "USED" : "AVAILABLE"}
              </div>
              <div className={`flex items-center gap-2 mb-2 ${isUsed ? "text-slate-400" : ""}`}>
                {chipIcons[rec.chip]}
                <span className={`font-semibold ${isUsed ? "line-through" : ""}`}>{rec.name}</span>
              </div>
              <p className={`text-xs mb-2 ${isUsed ? "text-slate-400" : rec.recommendation === "consider" ? "opacity-90" : "text-slate-500"}`}>
                {isUsed ? "Already used this season" : rec.message}
              </p>
              {!isUsed && (
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                  rec.recommendation === "consider"
                    ? "bg-white/20 text-white"
                    : "bg-slate-200 text-slate-600"
                }`}>
                  {rec.recommendation === "consider" ? "CONSIDER" : "SAVE"}
                </span>
              )}
            </div>
          );
        })}
      </div>


      <ContinueButton
        onClick={() => {
          loadTransferSuggestions();
          setStep("transfers");
        }}
        label="Plan Transfers"
        color="violet"
        onSkip={chipAdvice.recommendations.every(r => r.recommendation === "save") ? () => {
          loadTransferSuggestions();
          setStep("transfers");
        } : undefined}
        skipLabel="No chip needed → Skip to Transfers"
      />
    </div>
  );
}

// ============================================================================
// Feedback Step Content
// ============================================================================

const FEATURE_OPTIONS = [
  { value: "overall", label: "Overall Experience" },
  { value: "transfers", label: "Transfer Suggestions" },
  { value: "lineup", label: "Lineup Optimizer" },
  { value: "captain", label: "Captain Picks" },
  { value: "crowd_insights", label: "Crowd Insights" },
  { value: "ai_review", label: "AI Review" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Reusable Star Rating Component for individual features
function FeatureStarRating({
  label,
  rating,
  onRatingChange,
  hoverRating,
  onHoverChange
}: {
  label: string;
  rating: number;
  onRatingChange: (r: number) => void;
  hoverRating: number;
  onHoverChange: (r: number) => void;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => onRatingChange(rating === star ? 0 : star)}
            onMouseEnter={() => onHoverChange(star)}
            onMouseLeave={() => onHoverChange(0)}
            className="p-0.5 transition-transform hover:scale-110"
          >
            <Star
              className={`w-6 h-6 transition-colors ${
                star <= (hoverRating || rating)
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-slate-300"
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

function FeedbackContent() {
  const { teamId, gwReview, markStepCompleted } = useTransferWorkflow();
  const gameweek = gwReview?.current_gameweek || 1;

  // Individual ratings for each feature
  const [aiSquadRating, setAiSquadRating] = useState(0);
  const [transferRating, setTransferRating] = useState(0);
  const [lineupRating, setLineupRating] = useState(0);
  const [captainRating, setCaptainRating] = useState(0);
  const [overallRating, setOverallRating] = useState(0);

  // Hover states for each rating
  const [aiSquadHover, setAiSquadHover] = useState(0);
  const [transferHover, setTransferHover] = useState(0);
  const [lineupHover, setLineupHover] = useState(0);
  const [captainHover, setCaptainHover] = useState(0);
  const [overallHover, setOverallHover] = useState(0);

  // Other feedback fields
  const [followedAdvice, setFollowedAdvice] = useState<string | null>(null);
  const [nps, setNps] = useState<number | null>(null);
  const [comment, setComment] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const hasAnyRating = aiSquadRating > 0 || transferRating > 0 || lineupRating > 0 || captainRating > 0 || overallRating > 0;

  const handleSubmit = async () => {
    if (!hasAnyRating && !comment.trim() && nps === null && !followedAdvice) {
      setError("Please provide at least one rating or comment");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      const apiBase = API_BASE.endsWith("/api") ? API_BASE : `${API_BASE}/api`;
      const res = await fetch(`${apiBase}/feedback/submit-comprehensive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_id: parseInt(teamId),
          gameweek,
          ai_squad_analysis_rating: aiSquadRating > 0 ? aiSquadRating : null,
          transfer_suggestions_rating: transferRating > 0 ? transferRating : null,
          lineup_recommendation_rating: lineupRating > 0 ? lineupRating : null,
          captain_selection_rating: captainRating > 0 ? captainRating : null,
          overall_experience_rating: overallRating > 0 ? overallRating : null,
          followed_advice: followedAdvice,
          would_recommend: nps,
          comment: comment.trim() || null,
        }),
      });

      if (res.ok) {
        setSubmitted(true);
        markStepCompleted("feedback");

        // Track each feature rating to Google Analytics in detail
        const teamIdNum = parseInt(teamId);
        // Convert string followedAdvice to boolean: "yes" -> true, "partially" -> true, "no" -> false
        const followedAdviceBool = followedAdvice === "yes" || followedAdvice === "partially" ? true :
                                   followedAdvice === "no" ? false : undefined;
        if (aiSquadRating > 0) {
          trackFeedbackSubmission("AI Squad Analysis", aiSquadRating, teamIdNum, gameweek, {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: followedAdviceBool
          });
        }
        if (transferRating > 0) {
          trackFeedbackSubmission("Transfer Suggestions", transferRating, teamIdNum, gameweek, {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: followedAdviceBool
          });
        }
        if (lineupRating > 0) {
          trackFeedbackSubmission("Lineup Recommendation", lineupRating, teamIdNum, gameweek, {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: followedAdviceBool
          });
        }
        if (captainRating > 0) {
          trackFeedbackSubmission("Captain Selection", captainRating, teamIdNum, gameweek, {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: followedAdviceBool
          });
        }
        if (overallRating > 0) {
          trackFeedbackSubmission("Overall Experience", overallRating, teamIdNum, gameweek, {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: followedAdviceBool
          });
        }

        // Also track comprehensive submission event
        trackEvent({
          name: "comprehensive_feedback_submitted",
          properties: {
            team_id: teamIdNum,
            gameweek,
            ai_squad_rating: aiSquadRating,
            transfer_rating: transferRating,
            lineup_rating: lineupRating,
            captain_rating: captainRating,
            overall_rating: overallRating,
            followed_advice: followedAdvice ?? undefined,
            nps_score: nps ?? undefined,
            has_comment: !!comment.trim(),
            ratings_provided: [
              aiSquadRating > 0 ? "ai_squad" : null,
              transferRating > 0 ? "transfers" : null,
              lineupRating > 0 ? "lineup" : null,
              captainRating > 0 ? "captain" : null,
              overallRating > 0 ? "overall" : null
            ].filter(Boolean).join(",")
          }
        });
      } else {
        setError("Failed to submit feedback. Please try again.");
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setAiSquadRating(0);
    setTransferRating(0);
    setLineupRating(0);
    setCaptainRating(0);
    setOverallRating(0);
    setFollowedAdvice(null);
    setNps(null);
    setComment("");
    setSubmitted(false);
    setError("");
  };

  if (submitted) {
    return (
      <div className="space-y-6">
        {/* Success Message */}
        <div className="text-center py-8">
          <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-green-100 to-emerald-100 rounded-full flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-3">Thank You!</h2>
          <p className="text-slate-500 max-w-md mx-auto">
            Your feedback helps us improve SmartPlayFPL and make better predictions for everyone.
          </p>
        </div>

        {/* Submit Another */}
        <div className="text-center">
          <button
            onClick={resetForm}
            className="inline-flex items-center gap-2 px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-xl transition-colors"
          >
            <MessageSquare className="w-5 h-5" />
            Submit Another Response
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center pb-4 border-b border-slate-100">
        <div className="w-14 h-14 mx-auto mb-3 bg-gradient-to-br from-purple-100 to-violet-100 rounded-xl flex items-center justify-center">
          <MessageSquare className="w-7 h-7 text-purple-600" />
        </div>
        <h2 className="text-xl font-bold text-slate-800 mb-1">Share Your Feedback</h2>
        <p className="text-sm text-slate-500">
          Help us improve SmartPlayFPL by rating each feature
        </p>
      </div>

      {/* Feature Ratings */}
      <div className="bg-slate-50 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-slate-800 mb-3">Rate Our Features</h3>
        <FeatureStarRating
          label="1. AI Squad Analysis"
          rating={aiSquadRating}
          onRatingChange={setAiSquadRating}
          hoverRating={aiSquadHover}
          onHoverChange={setAiSquadHover}
        />
        <FeatureStarRating
          label="2. Transfer Suggestions"
          rating={transferRating}
          onRatingChange={setTransferRating}
          hoverRating={transferHover}
          onHoverChange={setTransferHover}
        />
        <FeatureStarRating
          label="3. Lineup Recommendation"
          rating={lineupRating}
          onRatingChange={setLineupRating}
          hoverRating={lineupHover}
          onHoverChange={setLineupHover}
        />
        <FeatureStarRating
          label="4. Captain Selection"
          rating={captainRating}
          onRatingChange={setCaptainRating}
          hoverRating={captainHover}
          onHoverChange={setCaptainHover}
        />
        <FeatureStarRating
          label="5. Overall Experience"
          rating={overallRating}
          onRatingChange={setOverallRating}
          hoverRating={overallHover}
          onHoverChange={setOverallHover}
        />
      </div>

      {/* Followed Advice */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-3">
          6. Did you follow our recommendations this gameweek?
        </label>
        <div className="flex gap-2">
          {[
            { value: "yes", label: "Yes, I did" },
            { value: "partially", label: "Partially" },
            { value: "no", label: "No, I didn't" },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => setFollowedAdvice(followedAdvice === option.value ? null : option.value)}
              className={`flex-1 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                followedAdvice === option.value
                  ? "bg-purple-600 text-white shadow-lg shadow-purple-200"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {/* NPS Score */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          7. How likely are you to recommend SmartPlayFPL to a friend?
        </label>
        <div className="flex items-center justify-between gap-1">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((score) => (
            <button
              key={score}
              onClick={() => setNps(nps === score ? null : score)}
              className={`flex-1 aspect-square max-w-[36px] text-sm font-medium rounded-lg transition-all ${
                nps === score
                  ? score >= 9
                    ? "bg-green-500 text-white scale-110"
                    : score >= 7
                    ? "bg-yellow-500 text-white scale-110"
                    : "bg-red-500 text-white scale-110"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {score}
            </button>
          ))}
        </div>
        <div className="flex justify-between text-xs text-slate-400 mt-1.5 px-1">
          <span>Not likely</span>
          <span>Very likely</span>
        </div>
      </div>

      {/* Comment */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          8. Any additional comments or suggestions?
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Tell us what you liked, what could be improved, or any suggestions..."
          rows={4}
          className="w-full px-4 py-3 border border-slate-200 rounded-xl text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
          maxLength={500}
        />
        <div className="text-right text-xs text-slate-400 mt-1">
          {comment.length}/500
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={isSubmitting}
        className="w-full flex items-center justify-center gap-2 px-6 py-4 bg-gradient-to-r from-purple-600 to-violet-600 text-white font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-purple-200"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Submitting...
          </>
        ) : (
          <>
            <Send className="w-5 h-5" />
            Submit Feedback
          </>
        )}
      </button>
    </div>
  );
}

// Confirm Step Content
function ConfirmContent() {
  const {
    appliedTransfers, lineup, chipAdvice, transferSuggestions, resetWorkflow, teamId, completedSteps,
    optimizedSquad, optimizedFormation, wizardSelections, sellAnalysis, buyAnalysis, advanceToStep
  } = useTransferWorkflow();

  const appliedCount = appliedTransfers.filter(t => t.applied).length;
  const totalCostChange = appliedTransfers
    .filter(t => t.applied)
    .reduce((sum, t) => {
      const selectedAlt = t.suggestion.alternatives?.[t.selectedAlternativeIndex];
      const inPrice = selectedAlt?.price || t.suggestion.in_player.price;
      return sum + (inPrice - t.suggestion.out.price);
    }, 0);
  const newBank = (transferSuggestions?.bank || 0) - totalCostChange;

  // Calculate expected points from lineup with confidence interval
  const expectedPoints = lineup?.starting_xi?.reduce((sum: number, p: LineupPlayer) => {
    const pts = p.score || p.form || 0;
    const multiplier = p.is_captain ? 2 : 1;
    return sum + (pts * multiplier);
  }, 0) || 0;

  // 90% confidence interval (approximately +/- 1.645 standard deviations)
  // Using ~25% variance for FPL point predictions
  const variance = 0.25;
  const lowerBound = Math.max(0, expectedPoints * (1 - variance * 1.645));
  const upperBound = expectedPoints * (1 + variance * 1.645);

  // Get starting XI from optimizedSquad (reflects transfers) split by position
  const startingXI = optimizedSquad.filter(p => p.multiplier && p.multiplier > 0);
  const bench = optimizedSquad.filter(p => !p.multiplier || p.multiplier === 0);

  // Split starting XI by position
  const goalkeepers = startingXI.filter(p => p.position === "GKP");
  const defenders = startingXI.filter(p => p.position === "DEF");
  const midfielders = startingXI.filter(p => p.position === "MID");
  const forwards = startingXI.filter(p => p.position === "FWD");

  // Get wizard transfer count
  const wizardTransferCount = Object.entries(wizardSelections)
    .filter(([, repId]) => repId !== null && repId !== undefined).length;

  // Steps checklist
  const steps = [
    { key: "review", label: "Review Performance", icon: <BarChart3 className="w-4 h-4" /> },
    { key: "alerts", label: "Check Alerts", icon: <Bell className="w-4 h-4" /> },
    { key: "transfers", label: "Plan Transfers", icon: <ArrowRightLeft className="w-4 h-4" /> },
    { key: "lineup", label: "Set Lineup", icon: <Users className="w-4 h-4" /> },
    { key: "captain", label: "Pick Captain", icon: <Crown className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-4">
      {/* Success Header with Celebration */}
      <div className="bg-gradient-to-br from-emerald-500 via-emerald-500 to-teal-500 rounded-xl p-6 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2" />
        <div className="relative text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/20 mb-4">
            <Trophy className="w-8 h-8" />
          </div>
          <h3 className="text-2xl font-bold mb-1">You're All Set!</h3>
          <p className="text-emerald-100 text-sm">Your game plan is ready for the deadline</p>

          {/* Expected Points Badge with 90% Interval */}
          {expectedPoints > 0 && (
            <div className="mt-4 space-y-1">
              <div className="inline-flex items-center gap-2 bg-white/20 rounded-full px-4 py-2">
                <Zap className="w-4 h-4" />
                <span className="text-lg font-bold">~{expectedPoints.toFixed(0)} pts</span>
              </div>
              <p className="text-xs text-emerald-200">
                90% CI: {lowerBound.toFixed(0)} - {upperBound.toFixed(0)} pts
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Steps Completion Checklist */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
        <h4 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          Workflow Complete
        </h4>
        <div className="space-y-2">
          {steps.map((step) => (
            <div key={step.key} className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                completedSteps.has(step.key as WorkflowStep)
                  ? "bg-emerald-100 text-emerald-600"
                  : "bg-slate-200 text-slate-400"
              }`}>
                {completedSteps.has(step.key as WorkflowStep) ? (
                  <Check className="w-3.5 h-3.5" />
                ) : (
                  step.icon
                )}
              </div>
              <span className={`text-sm ${
                completedSteps.has(step.key as WorkflowStep) ? "text-slate-700" : "text-slate-400"
              }`}>
                {step.label}
              </span>
              {completedSteps.has(step.key as WorkflowStep) && (
                <Check className="w-4 h-4 text-emerald-500 ml-auto" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Transfers Summary - Enhanced */}
      {appliedCount > 0 && (
        <div className="bg-gradient-to-br from-violet-50 to-purple-50 rounded-xl p-4 border border-violet-200">
          <div className="flex items-center gap-2 mb-3">
            <div className="p-1.5 rounded-lg bg-violet-100">
              <ArrowRightLeft className="w-4 h-4 text-violet-600" />
            </div>
            <span className="font-semibold text-slate-700">Planned Transfers ({appliedCount})</span>
          </div>
          <div className="space-y-2">
            {appliedTransfers.filter(t => t.applied).map((item, idx) => {
              const selectedAlt = item.suggestion.alternatives?.[item.selectedAlternativeIndex];
              const inPlayerName = selectedAlt?.name || item.suggestion.in_player.name;
              const inPrice = selectedAlt?.price || item.suggestion.in_player.price;
              const outPrice = item.suggestion.out.price;
              return (
                <div key={idx} className="flex items-center justify-between bg-white rounded-lg p-3 border border-violet-100">
                  <div className="flex items-center gap-3">
                    <div className="text-center">
                      <p className="text-sm font-medium text-red-600">{item.suggestion.out.name}</p>
                      <p className="text-xs text-slate-400">£{outPrice.toFixed(1)}m</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-300" />
                    <div className="text-center">
                      <p className="text-sm font-medium text-emerald-600">{inPlayerName}</p>
                      <p className="text-xs text-slate-400">£{inPrice.toFixed(1)}m</p>
                    </div>
                  </div>
                  <div className={`text-xs font-medium px-2 py-1 rounded ${
                    inPrice > outPrice
                      ? "bg-red-100 text-red-600"
                      : "bg-emerald-100 text-emerald-600"
                  }`}>
                    {inPrice > outPrice ? "+" : ""}{(inPrice - outPrice).toFixed(1)}m
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-violet-200 flex items-center justify-between">
            <span className="text-sm text-slate-600">Remaining Budget</span>
            <span className="font-semibold text-violet-700">£{newBank.toFixed(1)}m</span>
          </div>
        </div>
      )}

      {/* Lineup Summary - Uses optimizedSquad which reflects transfers */}
      {startingXI.length > 0 && (
        <div className="bg-gradient-to-br from-blue-50 to-sky-50 rounded-xl p-4 border border-blue-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-blue-100">
                <Users className="w-4 h-4 text-blue-600" />
              </div>
              <span className="font-semibold text-slate-700">Starting XI</span>
            </div>
            <span className="text-sm font-medium text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
              {optimizedFormation || lineup?.formation || "4-4-2"}
            </span>
          </div>

          {/* Captain & Vice */}
          <div className="flex gap-3 mb-3">
            <div className="flex-1 bg-amber-50 rounded-lg p-3 border border-amber-200">
              <div className="flex items-center gap-2 mb-1">
                <Crown className="w-4 h-4 text-amber-500" />
                <span className="text-xs text-amber-600 font-medium">CAPTAIN</span>
              </div>
              <p className="font-semibold text-slate-700">
                {startingXI.find(p => p.multiplier === 2)?.name || lineup?.captain?.name || "Not set"}
              </p>
            </div>
            <div className="flex-1 bg-slate-100 rounded-lg p-3 border border-slate-200">
              <div className="flex items-center gap-2 mb-1">
                <Award className="w-4 h-4 text-slate-500" />
                <span className="text-xs text-slate-500 font-medium">VICE</span>
              </div>
              <p className="font-semibold text-slate-700">{lineup?.vice_captain?.name || "Not set"}</p>
            </div>
          </div>

          {/* Starting XI by Position */}
          <div className="bg-white rounded-lg p-3 border border-blue-100 space-y-3">
            {/* Goalkeeper */}
            {goalkeepers.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-400 font-medium mb-1">GK</p>
                <div className="flex flex-wrap gap-1">
                  {goalkeepers.map((player) => (
                    <span key={player.id} className={`text-xs px-2 py-1 rounded ${
                      player.multiplier === 2 ? "bg-amber-100 text-amber-700 font-medium" :
                      "bg-yellow-50 text-yellow-700"
                    }`}>
                      {player.name?.split(" ").pop()}
                      {player.multiplier === 2 && " (C)"}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Defenders */}
            {defenders.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-400 font-medium mb-1">DEF ({defenders.length})</p>
                <div className="flex flex-wrap gap-1">
                  {defenders.map((player) => (
                    <span key={player.id} className={`text-xs px-2 py-1 rounded ${
                      player.multiplier === 2 ? "bg-amber-100 text-amber-700 font-medium" :
                      "bg-emerald-50 text-emerald-700"
                    }`}>
                      {player.name?.split(" ").pop()}
                      {player.multiplier === 2 && " (C)"}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Midfielders */}
            {midfielders.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-400 font-medium mb-1">MID ({midfielders.length})</p>
                <div className="flex flex-wrap gap-1">
                  {midfielders.map((player) => (
                    <span key={player.id} className={`text-xs px-2 py-1 rounded ${
                      player.multiplier === 2 ? "bg-amber-100 text-amber-700 font-medium" :
                      "bg-blue-50 text-blue-700"
                    }`}>
                      {player.name?.split(" ").pop()}
                      {player.multiplier === 2 && " (C)"}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Forwards */}
            {forwards.length > 0 && (
              <div>
                <p className="text-[10px] text-slate-400 font-medium mb-1">FWD ({forwards.length})</p>
                <div className="flex flex-wrap gap-1">
                  {forwards.map((player) => (
                    <span key={player.id} className={`text-xs px-2 py-1 rounded ${
                      player.multiplier === 2 ? "bg-amber-100 text-amber-700 font-medium" :
                      "bg-rose-50 text-rose-700"
                    }`}>
                      {player.name?.split(" ").pop()}
                      {player.multiplier === 2 && " (C)"}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Bench */}
          {bench.length > 0 && (
            <div className="mt-2 bg-slate-50 rounded-lg p-3 border border-slate-200">
              <p className="text-xs text-slate-500 mb-2">Bench ({bench.length})</p>
              <div className="flex flex-wrap gap-1">
                {bench.map((player) => (
                  <span key={player.id} className={`text-xs px-2 py-1 rounded ${
                    player.position === "GKP" ? "bg-yellow-50 text-yellow-600" :
                    player.position === "DEF" ? "bg-emerald-50 text-emerald-600" :
                    player.position === "MID" ? "bg-blue-50 text-blue-600" :
                    "bg-rose-50 text-rose-600"
                  }`}>
                    {player.name?.split(" ").pop()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Chip Summary */}
      {chipAdvice && (
        <div className="bg-gradient-to-br from-purple-50 to-fuchsia-50 rounded-xl p-4 border border-purple-200">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-purple-100">
              <Zap className="w-4 h-4 text-purple-600" />
            </div>
            <span className="font-semibold text-slate-700">Chip Strategy</span>
          </div>
          <p className="text-sm text-slate-700">
            {chipAdvice.recommendations.find(r => r.recommendation === "consider")
              ? (
                <span className="flex items-center gap-2">
                  <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-xs font-medium">
                    CONSIDER
                  </span>
                  {chipAdvice.recommendations.find(r => r.recommendation === "consider")?.name}
                </span>
              )
              : (
                <span className="text-slate-500">No chip recommended this week - save for better opportunities</span>
              )
            }
          </p>
        </div>
      )}

      {/* Give Feedback Section - Most Important */}
      <div className="space-y-3 pt-2">
        <button
          onClick={() => advanceToStep("confirm", "feedback")}
          className="w-full flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white font-semibold rounded-xl shadow-lg shadow-red-200 transition-all animate-pulse"
        >
          <MessageSquare className="w-5 h-5" />
          Give Feedback
        </button>
        <p className="text-center text-sm text-slate-500 px-4">
          Your feedback helps us improve SmartPlayFPL. Tell us what worked well and what we can do better.
        </p>
      </div>

      {/* Action Buttons */}
      <div className="space-y-2 pt-4 mt-4 border-t border-slate-200">
        <a
          href="https://fantasy.premierleague.com/transfers"
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 px-5 py-4 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-700 hover:to-teal-600 text-white font-semibold rounded-xl shadow-lg shadow-emerald-200 transition-all"
        >
          <span>Go to Official FPL</span>
          <ExternalLink className="w-4 h-4" />
        </a>
        <button
          onClick={resetWorkflow}
          className="w-full flex items-center justify-center gap-2 px-5 py-3 bg-slate-100 hover:bg-slate-200 text-slate-600 font-medium rounded-xl transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          Start New Planning
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Helper Components
// ============================================================================

function LoadingState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="w-12 h-12 border-4 border-slate-200 border-t-emerald-600 rounded-full animate-spin mb-4" />
      <p className="text-slate-600 font-medium">{message}</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
      <p className="text-slate-800 font-medium">{message}</p>
    </div>
  );
}

function ContinueButton({
  onClick,
  label,
  color,
  onSkip,
  skipLabel,
  disabled,
}: {
  onClick: () => void;
  label: string;
  color: string;
  onSkip?: () => void;
  skipLabel?: string;
  disabled?: boolean;
}) {
  const colorClasses: Record<string, string> = {
    emerald: "from-emerald-600 to-emerald-500 hover:from-emerald-700 hover:to-emerald-600 shadow-emerald-200",
    amber: "from-amber-500 to-amber-400 hover:from-amber-600 hover:to-amber-500 shadow-amber-200",
    violet: "from-violet-600 to-violet-500 hover:from-violet-700 hover:to-violet-600 shadow-violet-200",
    blue: "from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 shadow-blue-200",
    purple: "from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 shadow-purple-200",
    teal: "from-teal-600 to-teal-500 hover:from-teal-700 hover:to-teal-600 shadow-teal-200",
  };

  return (
    <div className="space-y-2">
      <button
        onClick={disabled ? undefined : onClick}
        disabled={disabled}
        className={`w-full flex items-center justify-center gap-2 px-5 py-3.5 bg-gradient-to-r ${
          disabled
            ? "from-slate-300 to-slate-400 cursor-not-allowed opacity-60"
            : colorClasses[color]
        } text-white font-semibold rounded-xl shadow-lg transition-all`}
      >
        {label}
        <ChevronRight className="w-5 h-5" />
      </button>
      {onSkip && (
        <button
          onClick={onSkip}
          className="w-full flex items-center justify-center gap-1 px-4 py-2 text-slate-500 hover:text-slate-700 text-sm font-medium transition-colors"
        >
          {skipLabel || "Skip this step"}
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

function InsightCard({ insight }: { insight: { type: string; icon: string; text: string } }) {
  const colors: Record<string, { bg: string; border: string; icon: string }> = {
    positive: { bg: "bg-emerald-50", border: "border-emerald-200", icon: "text-emerald-600" },
    negative: { bg: "bg-red-50", border: "border-red-200", icon: "text-red-600" },
    neutral: { bg: "bg-blue-50", border: "border-blue-200", icon: "text-blue-600" },
    warning: { bg: "bg-amber-50", border: "border-amber-200", icon: "text-amber-600" },
  };
  const c = colors[insight.type] || colors.neutral;

  const iconMap: Record<string, React.ReactNode> = {
    crown: <Crown className="w-4 h-4" />,
    star: <TrendingUp className="w-4 h-4" />,
    trending_down: <TrendingDown className="w-4 h-4" />,
    alert: <AlertTriangle className="w-4 h-4" />,
    bench: <Award className="w-4 h-4" />,
    rank: <BarChart3 className="w-4 h-4" />,
  };

  return (
    <div className={`${c.bg} ${c.border} border rounded-xl p-3 flex items-start gap-3`}>
      <div className={`${c.icon} mt-0.5`}>
        {iconMap[insight.icon] || <Target className="w-4 h-4" />}
      </div>
      <p className="text-sm text-slate-700 flex-1">{insight.text}</p>
    </div>
  );
}



function SummaryCard({
  icon,
  title,
  color,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  const colorClasses: Record<string, string> = {
    violet: "bg-violet-50 border-violet-200",
    blue: "bg-blue-50 border-blue-200",
    purple: "bg-purple-50 border-purple-200",
  };

  return (
    <div className={`rounded-xl p-4 border ${colorClasses[color] || "bg-slate-50 border-slate-200"}`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-semibold text-slate-700">{title}</span>
      </div>
      {children}
    </div>
  );
}

// ============================================================================
// Squad Confirmation Step Content
// ============================================================================

function SquadContent() {
  const {
    previewSquad,
    appliedTransfers,
    transferSuggestions,
    setStep,
    loadLineupStrategies,
    applySelectedTransfers,
    transferOutIds,
    transferInIds,
    teamId,
  } = useTransferWorkflow();

  const bank = transferSuggestions?.bank || 0;

  // AI Analysis state
  const [squadAnalysis, setSquadAnalysis] = useState<SquadAnalysisResponse | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Get applied transfers details
  const appliedDetails = appliedTransfers
    .filter(t => t.applied)
    .map(t => {
      const selectedAlt = t.suggestion.alternatives?.[t.selectedAlternativeIndex];
      const inPlayer = selectedAlt || t.suggestion.in_player;
      const priceDiff = inPlayer.price - t.suggestion.out.price;
      return {
        out: t.suggestion.out,
        in: inPlayer,
        priceDiff,
      };
    });

  const totalTransfers = appliedDetails.length;
  const totalPriceChange = appliedDetails.reduce((sum, t) => sum + t.priceDiff, 0);
  const newBank = bank - totalPriceChange;

  // Load AI analysis on mount
  useEffect(() => {
    const loadAnalysis = async () => {
      if (!teamId) return;
      setAnalysisLoading(true);
      try {
        // Build transfers for API
        const transfers = appliedDetails.map(t => ({
          out_id: t.out.id,
          out_name: t.out.name,
          out_team: t.out.team,
          in_id: t.in.id,
          in_name: t.in.name,
          in_team: t.in.team,
          price_diff: t.priceDiff,
        }));
        const data = await getSquadAnalysis(teamId, transfers);
        setSquadAnalysis(data);
      } catch (err) {
        console.error("Failed to load squad analysis:", err);
      } finally {
        setAnalysisLoading(false);
      }
    };
    loadAnalysis();
  }, [teamId, appliedDetails.length]);

  // Proceed to Lineup
  const handleContinue = () => {
    // Apply all selected transfers to context
    applySelectedTransfers();
    // Load lineup strategies with the applied transfers
    loadLineupStrategies();
    setStep("lineup");
  };

  // Go back to transfers
  const handleBack = () => {
    setStep("transfers");
  };

  // Priority colors
  const getPriorityColors = (priority: string) => {
    switch (priority) {
      case "high": return "bg-red-50 border-red-200 text-red-700";
      case "medium": return "bg-amber-50 border-amber-200 text-amber-700";
      default: return "bg-slate-50 border-slate-200 text-slate-700";
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-gradient-to-br from-teal-500 to-teal-600 rounded-xl p-5 text-white">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2.5 rounded-xl bg-white/20">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold">Confirm Your Squad</h3>
            <p className="text-sm text-teal-100">Review your transfers before setting your lineup</p>
          </div>
        </div>

        {/* Budget Overview */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold">{totalTransfers}</p>
            <p className="text-xs text-teal-200">Transfers</p>
          </div>
          <div className="bg-white/10 rounded-lg p-3 text-center">
            <p className="text-2xl font-bold">£{newBank.toFixed(1)}m</p>
            <p className="text-xs text-teal-200">Bank</p>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Transfers + AI Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Transfer Summary */}
        <div className="space-y-4">
          {appliedDetails.length > 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-4 py-2 bg-slate-50 border-b border-slate-200">
                <p className="text-xs font-bold text-slate-600 uppercase tracking-wide">Applied Transfers</p>
              </div>
              <div className="divide-y divide-slate-100">
                {appliedDetails.map((transfer, idx) => (
                  <div key={idx} className="p-3 flex items-center gap-3">
                    {/* Out Player */}
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-bold text-red-600">{transfer.out.name.charAt(0)}</span>
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-slate-700 truncate text-sm">{transfer.out.name}</p>
                        <p className="text-[10px] text-slate-500">{transfer.out.team}</p>
                      </div>
                    </div>

                    <ArrowRight className="w-4 h-4 text-slate-400 flex-shrink-0" />

                    {/* In Player */}
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-bold text-emerald-600">{transfer.in.name.charAt(0)}</span>
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-slate-700 truncate text-sm">{transfer.in.name}</p>
                        <p className="text-[10px] text-slate-500">{transfer.in.team}</p>
                      </div>
                    </div>

                    {/* Price Diff */}
                    <div className={`text-xs font-bold px-2 py-1 rounded flex-shrink-0 ${
                      transfer.priceDiff > 0 ? "bg-red-100 text-red-600"
                        : transfer.priceDiff < 0 ? "bg-emerald-100 text-emerald-600"
                        : "bg-slate-100 text-slate-600"
                    }`}>
                      {transfer.priceDiff > 0 ? `+£${transfer.priceDiff.toFixed(1)}m`
                        : transfer.priceDiff < 0 ? `-£${Math.abs(transfer.priceDiff).toFixed(1)}m`
                        : "£0"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 rounded-xl p-5 text-center border border-slate-200">
              <CheckCircle2 className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="font-semibold text-slate-700">No Transfers Made</p>
              <p className="text-xs text-slate-500 mt-1">Keeping your current squad</p>
            </div>
          )}
        </div>

        {/* Right: AI Squad Analysis */}
        <div className="bg-gradient-to-br from-violet-50 to-purple-50 rounded-xl border border-violet-200 overflow-hidden">
          <div className="px-4 py-2 bg-violet-100 border-b border-violet-200 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-600" />
            <p className="text-xs font-bold text-violet-700 uppercase tracking-wide">AI Squad Analysis</p>
          </div>

          {analysisLoading ? (
            <div className="p-6 text-center">
              <Loader2 className="w-6 h-6 text-violet-500 animate-spin mx-auto mb-2" />
              <p className="text-sm text-violet-600">Analyzing your squad...</p>
            </div>
          ) : squadAnalysis ? (
            <div className="p-4 space-y-4">
              {/* Score */}
              <div className="flex items-center gap-3">
                <div className={`w-14 h-14 rounded-xl flex items-center justify-center font-bold text-xl ${
                  squadAnalysis.score >= 80 ? "bg-emerald-100 text-emerald-700" :
                  squadAnalysis.score >= 60 ? "bg-amber-100 text-amber-700" :
                  "bg-red-100 text-red-700"
                }`}>
                  {squadAnalysis.score}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-700">Squad Rating</p>
                  <p className="text-xs text-slate-500">{squadAnalysis.summary}</p>
                </div>
              </div>

              {/* Strengths & Weaknesses */}
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-emerald-50 rounded-lg p-2.5 border border-emerald-200">
                  <p className="text-[10px] font-bold text-emerald-700 uppercase mb-1">Strengths</p>
                  {squadAnalysis.strengths.slice(0, 2).map((s, i) => (
                    <p key={i} className="text-xs text-emerald-700 flex items-start gap-1">
                      <Check className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      {s}
                    </p>
                  ))}
                </div>
                <div className="bg-red-50 rounded-lg p-2.5 border border-red-200">
                  <p className="text-[10px] font-bold text-red-700 uppercase mb-1">Weaknesses</p>
                  {squadAnalysis.weaknesses.slice(0, 2).map((w, i) => (
                    <p key={i} className="text-xs text-red-700 flex items-start gap-1">
                      <X className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      {w}
                    </p>
                  ))}
                </div>
              </div>

              {/* Optimization Tips */}
              <div>
                <p className="text-[10px] font-bold text-slate-600 uppercase mb-2">Optimization Tips</p>
                <div className="space-y-2">
                  {squadAnalysis.optimization_tips.slice(0, 3).map((tip, i) => (
                    <div key={i} className={`rounded-lg p-2.5 border ${getPriorityColors(tip.priority)}`}>
                      <div className="flex items-start gap-2">
                        <span className="text-base">{tip.icon}</span>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-sm">{tip.title}</p>
                          <p className="text-xs opacity-80">{tip.description}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Chip Strategy */}
              <div>
                <p className="text-[10px] font-bold text-slate-600 uppercase mb-2">Chip Strategy</p>
                {squadAnalysis.chip_strategy ? (
                  <div className={`rounded-lg p-3 border ${
                    squadAnalysis.chip_strategy.should_use
                      ? "bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-300"
                      : "bg-slate-50 border-slate-200"
                  }`}>
                    <div className="flex items-start gap-2">
                      <span className="text-xl">
                        {squadAnalysis.chip_strategy.should_use ? "🎯" : "💾"}
                      </span>
                      <div className="flex-1 min-w-0">
                        {squadAnalysis.chip_strategy.should_use ? (
                          <>
                            <p className="font-bold text-amber-800 text-sm">
                              Use {squadAnalysis.chip_strategy.chip_name} This Week!
                            </p>
                            <p className="text-xs text-amber-700 mt-0.5">
                              {squadAnalysis.chip_strategy.reasoning}
                            </p>
                            <div className="flex items-center gap-1 mt-1.5">
                              <div className="text-[10px] font-medium text-amber-600">
                                Confidence: {squadAnalysis.chip_strategy.confidence}%
                              </div>
                            </div>
                          </>
                        ) : (
                          <>
                            <p className="font-semibold text-slate-700 text-sm">
                              No Need to Use Chips Today
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">
                              {squadAnalysis.chip_strategy.reasoning}
                            </p>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                    <p className="text-sm text-slate-500">Chip strategy not available</p>
                  </div>
                )}
              </div>

              {/* AI Model */}
              <p className="text-[10px] text-slate-400 text-right">
                Powered by {squadAnalysis.ai_model}
              </p>
            </div>
          ) : (
            <div className="p-6 text-center">
              <p className="text-sm text-slate-500">Unable to load analysis</p>
            </div>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="space-y-2">
        <ContinueButton onClick={handleContinue} label="Set Lineup" color="blue" />
        <button
          onClick={handleBack}
          className="w-full flex items-center justify-center gap-1 px-4 py-2 text-slate-500 hover:text-slate-700 text-sm font-medium transition-colors"
        >
          Back to Transfers
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Main Step Content Component
// ============================================================================
export function WorkflowStepContent() {
  const { step } = useTransferWorkflow();

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
      {step === "review" && <ReviewContent />}
      {step === "alerts" && <AlertsContent />}
      {step === "transfers" && <TransfersContent />}
      {step === "lineup" && <LineupContent />}
      {step === "captain" && <CaptainContent />}
      {step === "confirm" && <ConfirmContent />}
      {step === "feedback" && <FeedbackContent />}
    </div>
  );
}
