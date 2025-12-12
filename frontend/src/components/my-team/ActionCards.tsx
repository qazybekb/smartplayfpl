"use client";

import { Zap, Crown, Armchair, Play, Pause, ArrowRightLeft } from "lucide-react";
import type { ActionsResponse, ActionCard } from "@/lib/api";

interface ActionCardsProps {
  actionsData: ActionsResponse | null;
  loading?: boolean;
}

const actionIcons: Record<string, React.ReactNode> = {
  captain: <Crown className="w-4 h-4" />,
  bench: <Armchair className="w-4 h-4" />,
  start: <Play className="w-4 h-4" />,
  hold: <Pause className="w-4 h-4" />,
  transfer: <ArrowRightLeft className="w-4 h-4" />,
};

const actionColors: Record<string, { bg: string; border: string; icon: string }> = {
  captain: { bg: "bg-amber-50", border: "border-amber-200", icon: "bg-amber-500" },
  bench: { bg: "bg-slate-50", border: "border-slate-200", icon: "bg-slate-500" },
  start: { bg: "bg-emerald-50", border: "border-emerald-200", icon: "bg-emerald-500" },
  hold: { bg: "bg-blue-50", border: "border-blue-200", icon: "bg-blue-500" },
  transfer: { bg: "bg-violet-50", border: "border-violet-200", icon: "bg-violet-500" },
};

const fdrColors: Record<number, string> = {
  1: "bg-emerald-500",
  2: "bg-emerald-400",
  3: "bg-amber-400",
  4: "bg-orange-500",
  5: "bg-red-500",
};

export default function ActionCards({ actionsData, loading }: ActionCardsProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!actionsData || actionsData.actions.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4">This Week's Actions</h2>
        <p className="text-slate-500 text-sm">No action recommendations available.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-violet-500" />
          <h2 className="text-lg font-bold text-slate-800">This Week's Actions</h2>
        </div>
        <span className="text-xs text-slate-500">GW {actionsData.gameweek}</span>
      </div>

      <div className="p-4 space-y-3">
        {actionsData.actions.slice(0, 5).map((action, idx) => {
          const colors = actionColors[action.action_type] || actionColors.hold;
          return (
            <div
              key={idx}
              className={`p-4 rounded-xl border ${colors.bg} ${colors.border}`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-8 h-8 ${colors.icon} rounded-lg flex items-center justify-center text-white`}>
                  {actionIcons[action.action_type] || <Zap className="w-4 h-4" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-slate-800">{action.player_name}</p>
                    <span className="text-xs text-slate-500">{action.team}</span>
                  </div>
                  <p className="text-sm text-slate-600 mt-1">{action.reasoning}</p>

                  {/* Fixture */}
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-slate-500">Next:</span>
                    <span className={`px-2 py-0.5 text-xs font-medium text-white rounded ${fdrColors[action.fixture_difficulty] || "bg-slate-400"}`}>
                      {action.fixture}
                    </span>
                  </div>

                  {/* Future fixtures */}
                  {action.future_fixtures && action.future_fixtures.length > 0 && (
                    <div className="flex items-center gap-1 mt-2">
                      {action.future_fixtures.slice(0, 4).map((fix, i) => (
                        <span
                          key={i}
                          className={`w-6 h-6 flex items-center justify-center text-xs font-medium text-white rounded ${fdrColors[fix.fdr] || "bg-slate-400"}`}
                          title={`GW${fix.gw}: ${fix.opponent}`}
                        >
                          {fix.opponent.slice(0, 3).toUpperCase()}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
