"use client";

import { useEffect } from "react";
import {
  Crown, Award, AlertTriangle, TrendingDown, BarChart3,
  ArrowRight, ArrowLeft, Check, X, RefreshCw, Sparkles,
  ArrowRightLeft, ChevronRight, Bell, Users, Zap, ExternalLink,
  Shield, Target, Lightbulb
} from "lucide-react";
import { useTransferWorkflow, type WorkflowStep } from "@/contexts/TransferWorkflowContext";

const STEPS: { key: WorkflowStep; label: string; shortLabel: string }[] = [
  { key: "review", label: "Review", shortLabel: "1" },
  { key: "alerts", label: "Alerts", shortLabel: "2" },
  { key: "transfers", label: "Transfers", shortLabel: "3" },
  { key: "lineup", label: "Lineup", shortLabel: "4" },
  { key: "captain", label: "Captain", shortLabel: "5" },
  { key: "confirm", label: "Confirm", shortLabel: "6" },
];

const iconMap: Record<string, React.ReactNode> = {
  crown: <Crown className="w-4 h-4" />,
  bench: <Award className="w-4 h-4" />,
  star: <Sparkles className="w-4 h-4" />,
  alert: <AlertTriangle className="w-4 h-4" />,
  trending_down: <TrendingDown className="w-4 h-4" />,
  rank: <BarChart3 className="w-4 h-4" />,
  injury: <X className="w-4 h-4" />,
  doubtful: <AlertTriangle className="w-4 h-4" />,
  suspended: <Shield className="w-4 h-4" />,
  rotation: <RefreshCw className="w-4 h-4" />,
  price_up: <TrendingDown className="w-4 h-4 rotate-180" />,
  price_down: <TrendingDown className="w-4 h-4" />,
  fixture_hard: <Target className="w-4 h-4" />,
};

const insightColors: Record<string, { bg: string; border: string; icon: string }> = {
  positive: { bg: "bg-emerald-50", border: "border-emerald-200", icon: "text-emerald-600" },
  negative: { bg: "bg-red-50", border: "border-red-200", icon: "text-red-600" },
  neutral: { bg: "bg-blue-50", border: "border-blue-200", icon: "text-blue-600" },
  warning: { bg: "bg-amber-50", border: "border-amber-200", icon: "text-amber-600" },
};

const severityColors: Record<string, { bg: string; border: string; icon: string }> = {
  high: { bg: "bg-red-50", border: "border-red-200", icon: "text-red-600" },
  medium: { bg: "bg-amber-50", border: "border-amber-200", icon: "text-amber-600" },
  warning: { bg: "bg-orange-50", border: "border-orange-200", icon: "text-orange-600" },
  info: { bg: "bg-blue-50", border: "border-blue-200", icon: "text-blue-600" },
};

// Step 1: GW Review
function GWReviewStep() {
  const { gwReview, gwReviewLoading, loadGWReview, setStep, loadAlerts } = useTransferWorkflow();

  useEffect(() => {
    loadGWReview();
  }, [loadGWReview]);

  const handleContinue = () => {
    loadAlerts();
    setStep("alerts");
  };

  if (gwReviewLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-2/3" />
          <div className="h-4 bg-slate-200 rounded w-full" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!gwReview) {
    return (
      <div className="p-6 text-center text-slate-500">
        Failed to load GW review
      </div>
    );
  }

  return (
    <div className="p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-emerald-600" />
        </div>
        <div>
          <h3 className="font-bold text-slate-800">GW Performance Review</h3>
          <p className="text-xs text-slate-500">{gwReview.gw_points}pts • Rank {gwReview.gw_rank?.toLocaleString()}</p>
        </div>
      </div>

      <div className="bg-slate-50 rounded-lg p-3 mb-4 border border-slate-200">
        <p className="text-sm text-slate-700">{gwReview.summary}</p>
      </div>

      <div className="space-y-2 mb-5 max-h-[300px] overflow-y-auto">
        {gwReview.insights.map((insight, idx) => {
          const colors = insightColors[insight.type] || insightColors.neutral;
          return (
            <div
              key={idx}
              className={`flex items-start gap-3 p-3 rounded-lg border ${colors.bg} ${colors.border}`}
            >
              <div className={`mt-0.5 ${colors.icon}`}>
                {iconMap[insight.icon] || <AlertTriangle className="w-4 h-4" />}
              </div>
              <p className="text-sm text-slate-700 flex-1">{insight.text}</p>
            </div>
          );
        })}
      </div>

      <button
        onClick={handleContinue}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
      >
        Continue to Alerts
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// Step 2: Alerts
function AlertsStep() {
  const { alerts, alertsLoading, loadAlerts, setStep, loadTransferSuggestions } = useTransferWorkflow();

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleContinue = () => {
    loadTransferSuggestions();
    setStep("transfers");
  };

  if (alertsLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-2/3" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!alerts) {
    return (
      <div className="p-6 text-center text-slate-500">
        Failed to load alerts
      </div>
    );
  }

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center">
            <Bell className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Squad Alerts</h3>
            <p className="text-xs text-slate-500">{alerts.alerts.length} alert(s)</p>
          </div>
        </div>
        <button
          onClick={() => setStep("review")}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Back
        </button>
      </div>

      <div className="bg-amber-50 rounded-lg p-3 mb-4 border border-amber-200">
        <p className="text-sm text-amber-700">{alerts.summary}</p>
      </div>

      {alerts.alerts.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <Check className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
          <p className="text-sm">All clear! No alerts for your squad.</p>
        </div>
      ) : (
        <div className="space-y-2 mb-5 max-h-[280px] overflow-y-auto">
          {alerts.alerts.map((alert, idx) => {
            const colors = severityColors[alert.severity] || severityColors.info;
            return (
              <div
                key={idx}
                className={`flex items-start gap-3 p-3 rounded-lg border ${colors.bg} ${colors.border}`}
              >
                <div className={`mt-0.5 ${colors.icon}`}>
                  {iconMap[alert.icon] || <AlertTriangle className="w-4 h-4" />}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-800">{alert.message}</p>
                  <p className="text-xs text-slate-500">{alert.detail}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <button
        onClick={handleContinue}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
      >
        Continue to Transfers
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// Step 3: Transfers
function TransfersStep() {
  const {
    transferSuggestions, transfersLoading, appliedTransfers,
    toggleTransfer, setStep, loadLineup
  } = useTransferWorkflow();

  if (transfersLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-2/3" />
          <div className="space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="h-28 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!transferSuggestions) {
    return (
      <div className="p-6 text-center text-slate-500">
        Failed to load transfer suggestions
      </div>
    );
  }

  const selectedCount = appliedTransfers.filter(t => t.applied).length;

  const handleContinue = () => {
    loadLineup();
    setStep("lineup");
  };

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
            <ArrowRightLeft className="w-4 h-4 text-violet-600" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Transfer Suggestions</h3>
            <p className="text-xs text-slate-500">
              {transferSuggestions.free_transfers} FT • £{transferSuggestions.bank.toFixed(1)}m ITB
            </p>
          </div>
        </div>
        <button
          onClick={() => setStep("alerts")}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Back
        </button>
      </div>

      <div className="bg-violet-50 rounded-lg p-3 mb-4 border border-violet-200">
        <p className="text-sm text-violet-700">{transferSuggestions.message}</p>
      </div>

      {transferSuggestions.suggestions.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <Check className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
          <p className="text-sm">Your squad looks solid! No urgent transfers needed.</p>
        </div>
      ) : (
        <div className="space-y-3 mb-5 max-h-[280px] overflow-y-auto">
          {appliedTransfers.map((item, idx) => {
            const { suggestion, applied } = item;
            const priorityColors = {
              high: "border-red-300 bg-red-50/50",
              medium: "border-amber-300 bg-amber-50/50",
              low: "border-slate-300 bg-slate-50/50",
            };
            const borderColor = priorityColors[suggestion.priority as keyof typeof priorityColors] || priorityColors.low;

            return (
              <div
                key={idx}
                className={`rounded-xl border-2 p-4 transition-all cursor-pointer ${
                  applied ? "border-emerald-400 bg-emerald-50/50" : borderColor
                }`}
                onClick={() => toggleTransfer(idx)}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    suggestion.priority === "high" ? "bg-red-100 text-red-700" :
                    suggestion.priority === "medium" ? "bg-amber-100 text-amber-700" :
                    "bg-slate-100 text-slate-600"
                  }`}>
                    {suggestion.priority.toUpperCase()} PRIORITY
                  </span>
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                    applied ? "bg-emerald-500 border-emerald-500" : "border-slate-300"
                  }`}>
                    {applied && <Check className="w-3 h-3 text-white" />}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-red-50 rounded-lg p-2 border border-red-100">
                    <p className="text-xs text-red-500 font-medium mb-0.5">OUT</p>
                    <p className="font-semibold text-slate-800 text-sm">{suggestion.out.name}</p>
                    <p className="text-xs text-slate-500">{suggestion.out.team} • £{suggestion.out.price}m</p>
                  </div>

                  <ArrowRight className="w-4 h-4 text-slate-400 shrink-0" />

                  <div className="flex-1 bg-emerald-50 rounded-lg p-2 border border-emerald-100">
                    <p className="text-xs text-emerald-500 font-medium mb-0.5">IN</p>
                    <p className="font-semibold text-slate-800 text-sm">{suggestion.in_player.name}</p>
                    <p className="text-xs text-slate-500">{suggestion.in_player.team} • £{suggestion.in_player.price}m</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <button
        onClick={handleContinue}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
      >
        Continue to Lineup {selectedCount > 0 && `(${selectedCount} selected)`}
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// Step 4: Lineup
function LineupStep() {
  const { lineup, lineupLoading, loadLineup, setStep, loadChipAdvice } = useTransferWorkflow();

  useEffect(() => {
    loadLineup();
  }, [loadLineup]);

  const handleContinue = () => {
    setStep("captain");
  };

  if (lineupLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-2/3" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!lineup) {
    return (
      <div className="p-6 text-center text-slate-500">
        Failed to load lineup recommendation
      </div>
    );
  }

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
            <Users className="w-4 h-4 text-blue-600" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Optimal Lineup</h3>
            <p className="text-xs text-slate-500">Formation: {lineup.formation}</p>
          </div>
        </div>
        <button
          onClick={() => setStep("transfers")}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Back
        </button>
      </div>

      <div className="bg-blue-50 rounded-lg p-3 mb-4 border border-blue-200">
        <p className="text-sm text-blue-700">{lineup.summary}</p>
      </div>

      {/* Captain Recommendation */}
      {lineup.captain && (
        <div className="bg-amber-50 rounded-lg p-3 mb-4 border border-amber-200">
          <div className="flex items-center gap-2 mb-1">
            <Crown className="w-4 h-4 text-amber-600" />
            <span className="text-sm font-medium text-amber-800">Captain: {lineup.captain.name}</span>
          </div>
          {lineup.captain.reasons.length > 0 && (
            <p className="text-xs text-amber-600">{lineup.captain.reasons.join(" • ")}</p>
          )}
        </div>
      )}

      {/* Vice Captain */}
      {lineup.vice_captain && (
        <div className="bg-slate-100 rounded-lg p-2 mb-4 border border-slate-200">
          <div className="flex items-center gap-2">
            <Award className="w-3 h-3 text-slate-500" />
            <span className="text-xs text-slate-600">Vice Captain: {lineup.vice_captain.name}</span>
          </div>
        </div>
      )}

      {/* Bench Order */}
      <div className="mb-5">
        <h4 className="text-xs font-medium text-slate-500 mb-2">BENCH ORDER</h4>
        <div className="space-y-1">
          {lineup.bench.map((player, idx) => (
            <div key={player.id} className="flex items-center gap-2 text-sm">
              <span className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center text-xs font-medium text-slate-600">
                {player.order}
              </span>
              <span className="text-slate-700">{player.name}</span>
              <span className="text-xs text-slate-400">{player.position}</span>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={handleContinue}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
      >
        Continue to Chips
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// Step 5: Chips
function ChipsStep() {
  const { chipAdvice, chipAdviceLoading, loadChipAdvice, setStep } = useTransferWorkflow();

  useEffect(() => {
    loadChipAdvice();
  }, [loadChipAdvice]);

  if (chipAdviceLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-200 rounded w-2/3" />
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!chipAdvice) {
    return (
      <div className="p-6 text-center text-slate-500">
        Failed to load chip advice
      </div>
    );
  }

  const chipIcons: Record<string, React.ReactNode> = {
    wildcard: <RefreshCw className="w-4 h-4" />,
    freehit: <Zap className="w-4 h-4" />,
    bboost: <Users className="w-4 h-4" />,
    "3xc": <Crown className="w-4 h-4" />,
  };

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
            <Lightbulb className="w-4 h-4 text-purple-600" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Chip Strategy</h3>
            <p className="text-xs text-slate-500">{chipAdvice.available_chips.length} chips available</p>
          </div>
        </div>
        <button
          onClick={() => setStep("lineup")}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Back
        </button>
      </div>

      <div className="bg-purple-50 rounded-lg p-3 mb-4 border border-purple-200">
        <p className="text-sm text-purple-700">{chipAdvice.overall_advice}</p>
      </div>

      <div className="space-y-3 mb-5 max-h-[280px] overflow-y-auto">
        {chipAdvice.recommendations.map((rec, idx) => (
          <div
            key={idx}
            className={`rounded-lg border p-3 ${
              rec.recommendation === "consider"
                ? "bg-emerald-50 border-emerald-200"
                : "bg-slate-50 border-slate-200"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-6 h-6 rounded flex items-center justify-center ${
                rec.recommendation === "consider" ? "bg-emerald-200 text-emerald-700" : "bg-slate-200 text-slate-600"
              }`}>
                {chipIcons[rec.chip]}
              </div>
              <span className="font-medium text-slate-800">{rec.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                rec.recommendation === "consider"
                  ? "bg-emerald-200 text-emerald-700"
                  : "bg-slate-200 text-slate-600"
              }`}>
                {rec.recommendation === "consider" ? "CONSIDER" : "SAVE"}
              </span>
            </div>
            <p className="text-xs text-slate-600 mb-1">{rec.message}</p>
            {rec.reasons.length > 0 && (
              <p className="text-xs text-slate-500">{rec.reasons.join(" • ")}</p>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={() => setStep("confirm")}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
      >
        Review & Confirm
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// Step 6: Confirm
function ConfirmStep() {
  const {
    appliedTransfers, lineup, chipAdvice, transferSuggestions, resetWorkflow, setStep
  } = useTransferWorkflow();

  const appliedCount = appliedTransfers.filter(t => t.applied).length;

  // Calculate new bank
  const totalCostChange = appliedTransfers
    .filter(t => t.applied)
    .reduce((sum, t) => sum + t.suggestion.cost_change, 0);
  const newBank = (transferSuggestions?.bank || 0) - totalCostChange;

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-emerald-100 rounded-lg flex items-center justify-center">
            <Check className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">Your Game Plan</h3>
            <p className="text-xs text-slate-500">Ready for the deadline</p>
          </div>
        </div>
        <button
          onClick={() => setStep("captain")}
          className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Back
        </button>
      </div>

      {/* Transfers Summary */}
      <div className="bg-violet-50 rounded-lg p-3 mb-3 border border-violet-200">
        <div className="flex items-center gap-2 mb-2">
          <ArrowRightLeft className="w-4 h-4 text-violet-600" />
          <span className="font-medium text-violet-800">Transfers ({appliedCount})</span>
        </div>
        {appliedCount > 0 ? (
          <div className="space-y-1">
            {appliedTransfers.filter(t => t.applied).map((item, idx) => (
              <div key={idx} className="flex items-center gap-2 text-sm">
                <span className="text-red-600">{item.suggestion.out.name}</span>
                <ArrowRight className="w-3 h-3 text-slate-400" />
                <span className="text-emerald-600">{item.suggestion.in_player.name}</span>
              </div>
            ))}
            <div className="text-xs text-violet-600 mt-2">
              New bank: £{newBank.toFixed(1)}m
            </div>
          </div>
        ) : (
          <p className="text-sm text-violet-600">No transfers planned</p>
        )}
      </div>

      {/* Lineup Summary */}
      {lineup && (
        <div className="bg-blue-50 rounded-lg p-3 mb-3 border border-blue-200">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-blue-600" />
            <span className="font-medium text-blue-800">Lineup</span>
          </div>
          <p className="text-sm text-blue-700">
            {lineup.formation} • {lineup.captain?.name} (C) • {lineup.vice_captain?.name} (VC)
          </p>
        </div>
      )}

      {/* Chip Summary */}
      {chipAdvice && (
        <div className="bg-purple-50 rounded-lg p-3 mb-5 border border-purple-200">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb className="w-4 h-4 text-purple-600" />
            <span className="font-medium text-purple-800">Chip</span>
          </div>
          <p className="text-sm text-purple-700">
            {chipAdvice.recommendations.find(r => r.recommendation === "consider")
              ? `Consider: ${chipAdvice.recommendations.find(r => r.recommendation === "consider")?.name}`
              : "No chip recommended"
            }
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="space-y-2">
        <a
          href="https://fantasy.premierleague.com/transfers"
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors"
        >
          Go to FPL
          <ExternalLink className="w-4 h-4" />
        </a>
        <button
          onClick={resetWorkflow}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Start Over
        </button>
      </div>
    </div>
  );
}

export default function WorkflowPanel() {
  const { step } = useTransferWorkflow();

  const currentStepIndex = STEPS.findIndex(s => s.key === step);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden h-full flex flex-col">
      {/* Step indicator */}
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 shrink-0">
        <div className="flex items-center gap-1">
          {STEPS.map((s, idx) => (
            <div key={s.key} className="flex items-center gap-1">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                step === s.key ? "bg-violet-600 text-white" :
                currentStepIndex > idx ? "bg-emerald-100 text-emerald-600" :
                "bg-slate-200 text-slate-500"
              }`}>
                {idx + 1}
              </div>
              {idx < STEPS.length - 1 && (
                <div className={`w-3 h-0.5 ${
                  currentStepIndex > idx ? "bg-emerald-300" : "bg-slate-200"
                }`} />
              )}
            </div>
          ))}
        </div>
        <div className="mt-1 text-xs text-slate-500">
          Step {currentStepIndex + 1}: {STEPS[currentStepIndex].label}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {step === "review" && <GWReviewStep />}
        {step === "alerts" && <AlertsStep />}
        {step === "transfers" && <TransfersStep />}
        {step === "lineup" && <LineupStep />}
        {step === "captain" && <div className="p-6 text-center text-slate-500">Captain step - use WorkflowTabs</div>}
        {step === "confirm" && <ConfirmStep />}
      </div>
    </div>
  );
}
