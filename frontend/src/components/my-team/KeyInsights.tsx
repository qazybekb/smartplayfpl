"use client";

import { Flame, Users, Coins, Target } from "lucide-react";
import type { TeamAnalysisResponse } from "@/lib/api";

interface KeyInsightsProps {
  teamData: TeamAnalysisResponse;
}

interface Insight {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: "emerald" | "amber" | "red" | "blue" | "violet";
}

const colorClasses = {
  emerald: { border: "border-emerald-200", icon: "text-emerald-500", value: "text-emerald-700" },
  amber: { border: "border-amber-200", icon: "text-amber-500", value: "text-amber-700" },
  red: { border: "border-red-200", icon: "text-red-500", value: "text-red-700" },
  blue: { border: "border-blue-200", icon: "text-blue-500", value: "text-blue-700" },
  violet: { border: "border-violet-200", icon: "text-violet-500", value: "text-violet-700" },
};

export default function KeyInsights({ teamData }: KeyInsightsProps) {
  const allPlayers = [...teamData.squad.starting, ...teamData.squad.bench];

  // Form insight
  const hotPlayers = allPlayers.filter((p) => p.form >= 6).length;
  const formInsight: Insight = {
    icon: <Flame className="w-4 h-4" />,
    label: "Form",
    value: hotPlayers > 0 ? `${hotPlayers} in form` : "Mixed form",
    color: hotPlayers >= 4 ? "emerald" : hotPlayers >= 2 ? "amber" : "red",
  };

  // Ownership insight
  const avgOwnership = allPlayers.reduce((acc, p) => acc + p.ownership, 0) / allPlayers.length;
  const styleInsight: Insight = {
    icon: <Users className="w-4 h-4" />,
    label: "Style",
    value: avgOwnership > 20 ? "Template" : avgOwnership > 10 ? "Balanced" : "Differential",
    color: avgOwnership > 20 ? "blue" : avgOwnership > 10 ? "violet" : "amber",
  };

  // Budget insight
  const budgetInsight: Insight = {
    icon: <Coins className="w-4 h-4" />,
    label: "Bank",
    value: `£${teamData.bank.toFixed(1)}m`,
    color: teamData.bank >= 1 ? "emerald" : teamData.bank >= 0.5 ? "amber" : "red",
  };

  // Transfers insight
  const transferInsight: Insight = {
    icon: <Target className="w-4 h-4" />,
    label: "Transfers",
    value: `${teamData.free_transfers} FT`,
    color: teamData.free_transfers >= 2 ? "emerald" : "amber",
  };

  const insights = [formInsight, styleInsight, budgetInsight, transferInsight];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {insights.map((insight, idx) => {
        const classes = colorClasses[insight.color];
        return (
          <div
            key={idx}
            className={`bg-white rounded-xl border p-4 shadow-sm ${classes.border}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className={classes.icon}>{insight.icon}</span>
              <span className="text-xs text-slate-500 font-medium">{insight.label}</span>
            </div>
            <p className={`text-lg font-bold ${classes.value}`}>{insight.value}</p>
          </div>
        );
      })}
    </div>
  );
}
