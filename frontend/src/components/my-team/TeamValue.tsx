"use client";

import type { TeamAnalysisResponse } from "@/lib/api";

interface TeamValueProps {
  teamData: TeamAnalysisResponse;
}

export default function TeamValue({ teamData }: TeamValueProps) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <h3 className="text-sm font-medium text-slate-500 mb-4">Team Value</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-slate-600">Squad Value</span>
          <span className="font-bold text-slate-800">
            £{teamData.team_value.toFixed(1)}m
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-600">In the Bank</span>
          <span className="font-bold text-emerald-600">
            £{teamData.bank.toFixed(1)}m
          </span>
        </div>
        <div className="border-t border-slate-100 pt-3 flex items-center justify-between">
          <span className="text-slate-800 font-medium">Total Value</span>
          <span className="font-bold text-lg text-slate-800">
            £{(teamData.team_value + teamData.bank).toFixed(1)}m
          </span>
        </div>
      </div>
    </div>
  );
}
