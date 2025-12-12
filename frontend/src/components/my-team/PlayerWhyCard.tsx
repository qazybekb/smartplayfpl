"use client";

import { useState } from "react";
import { X, Lightbulb, TrendingUp, Shield, Zap, Target, Check, AlertTriangle, Users, Award } from "lucide-react";
import type { LineupPlayer, BenchPlayer, SmartPlayData } from "@/lib/api";

interface PlayerWhyCardProps {
  player: LineupPlayer | BenchPlayer;
  isOpen: boolean;
  onClose: () => void;
  isBench?: boolean;
  benchOrder?: number;
  isPanel?: boolean; // When true, render as inline panel instead of modal
}

// Score threshold labels
const getScoreLabel = (score: number): { label: string; color: string } => {
  if (score >= 8.0) return { label: "Elite Pick", color: "text-emerald-600 bg-emerald-50 border-emerald-200" };
  if (score >= 7.0) return { label: "Strong Pick", color: "text-blue-600 bg-blue-50 border-blue-200" };
  if (score >= 5.5) return { label: "Solid Pick", color: "text-cyan-600 bg-cyan-50 border-cyan-200" };
  if (score >= 4.0) return { label: "Moderate Pick", color: "text-amber-600 bg-amber-50 border-amber-200" };
  return { label: "Weak Pick", color: "text-red-600 bg-red-50 border-red-200" };
};

// Component score indicator
const ScoreIndicator = ({ label, score, max = 10, icon: Icon, color }: {
  label: string;
  score: number;
  max?: number;
  icon: typeof TrendingUp;
  color: string;
}) => {
  const percentage = (score / max) * 100;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon className={`w-3.5 h-3.5 ${color}`} />
          <span className="text-xs text-slate-600 font-medium">{label}</span>
        </div>
        <span className={`text-sm font-bold ${color}`}>{score.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            percentage >= 70 ? "bg-emerald-500" :
            percentage >= 50 ? "bg-blue-500" :
            percentage >= 30 ? "bg-amber-500" : "bg-red-400"
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

export default function PlayerWhyCard({ player, isOpen, onClose, isBench, benchOrder, isPanel }: PlayerWhyCardProps) {
  if (!isOpen) return null;

  const scoreInfo = getScoreLabel(player.score);
  const smartplay = player.smartplay_data;

  // Generate reasons if none provided (reasons only exist on LineupPlayer, not BenchPlayer)
  const playerReasons = 'reasons' in player ? player.reasons : [];
  const reasons = playerReasons && playerReasons.length > 0
    ? playerReasons
    : generateReasons(player, smartplay);

  // Panel mode - render inline
  if (isPanel) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {/* Compact Header */}
        <div className={`px-4 py-3 ${
          player.position === "GKP" ? "bg-gradient-to-r from-amber-400 to-yellow-500" :
          player.position === "DEF" ? "bg-gradient-to-r from-emerald-400 to-green-500" :
          player.position === "MID" ? "bg-gradient-to-r from-blue-400 to-indigo-500" :
          "bg-gradient-to-r from-rose-400 to-red-500"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                <span className="text-white text-sm font-bold">
                  {player.name.substring(0, 2).toUpperCase()}
                </span>
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{player.name}</h3>
                <p className="text-white/80 text-xs">{player.team} • {player.position}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="w-4 h-4 text-white" />
            </button>
          </div>
        </div>

        {/* Compact Content */}
        <div className="p-4 space-y-4">
          {/* Status Badge */}
          {isBench && (
            <div className="flex items-center gap-2 p-2.5 bg-slate-100 rounded-lg">
              <Users className="w-4 h-4 text-slate-500" />
              <span className="text-sm text-slate-600">
                <span className="font-semibold">Bench #{benchOrder}</span> - Ready if needed
              </span>
            </div>
          )}

          {/* Injury/Status Alert */}
          {player.status !== "a" && player.news && (
            <div className={`flex items-start gap-2 p-2.5 rounded-lg ${
              player.status === "i" || player.status === "s"
                ? "bg-red-50 border border-red-200"
                : "bg-amber-50 border border-amber-200"
            }`}>
              <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                player.status === "i" || player.status === "s" ? "text-red-500" : "text-amber-500"
              }`} />
              <span className={`text-xs ${
                player.status === "i" || player.status === "s" ? "text-red-700" : "text-amber-700"
              }`}>
                {player.news}
              </span>
            </div>
          )}

          {/* SmartPlay Score - Compact */}
          <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-lg p-3 border border-purple-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-600 text-xs font-semibold mb-1">SmartPlay Score</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-purple-700">{player.score.toFixed(1)}</span>
                  <span className="text-sm text-purple-400">/10</span>
                </div>
              </div>
              <div className={`px-2.5 py-1 rounded-full border text-xs font-semibold ${scoreInfo.color}`}>
                {scoreInfo.label}
              </div>
            </div>
          </div>

          {/* Score Breakdown - Compact */}
          {smartplay && (
            <div className="space-y-2.5 bg-slate-50 rounded-lg p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Score Breakdown</p>
              <ScoreIndicator label="Nailedness" score={smartplay.nailedness_score} icon={Shield} color="text-violet-600" />
              <ScoreIndicator label="Form (xG)" score={smartplay.form_xg_score} icon={TrendingUp} color="text-orange-600" />
              <ScoreIndicator label="Form (Pts)" score={smartplay.form_pts_score} icon={Zap} color="text-emerald-600" />
              <ScoreIndicator label="Fixture" score={smartplay.fixture_score} icon={Target} color="text-blue-600" />

              {smartplay.next_opponent && (
                <div className="mt-2 pt-2 border-t border-slate-200 flex items-center justify-between">
                  <span className="text-xs text-slate-500">Next</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-slate-700 text-sm">{smartplay.next_opponent}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      smartplay.next_fdr <= 2 ? "bg-emerald-100 text-emerald-700" :
                      smartplay.next_fdr === 3 ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {smartplay.next_fdr}
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Selection Reasons - Compact */}
          <div>
            <h4 className="font-semibold text-slate-700 mb-2 flex items-center gap-1.5 text-sm">
              <Check className="w-3.5 h-3.5 text-emerald-500" />
              Why Selected
            </h4>
            <div className="space-y-1.5">
              {reasons.slice(0, 3).map((reason: string, idx: number) => (
                <div key={idx} className="flex items-start gap-1.5 py-1.5 px-2.5 bg-emerald-50 rounded-lg border border-emerald-100">
                  <Check className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-emerald-800">{reason}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Stats - Compact */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-slate-50 rounded-lg p-2 text-center">
              <p className="text-[9px] text-slate-500 uppercase">Price</p>
              <p className="text-sm font-bold text-slate-800">£{player.price.toFixed(1)}m</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-2 text-center">
              <p className="text-[9px] text-slate-500 uppercase">Form</p>
              <p className={`text-sm font-bold ${
                player.form >= 6 ? "text-emerald-600" :
                player.form >= 4 ? "text-amber-600" : "text-slate-600"
              }`}>{player.form.toFixed(1)}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-2 text-center">
              <p className="text-[9px] text-slate-500 uppercase">Owned</p>
              <p className="text-sm font-bold text-slate-800">{player.ownership.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Modal mode (original)
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-x-4 top-1/2 -translate-y-1/2 max-w-md mx-auto bg-white rounded-2xl shadow-2xl z-50 overflow-hidden animate-in zoom-in-95 slide-in-from-bottom-4 duration-300">
        {/* Header */}
        <div className={`px-5 py-4 border-b ${
          player.position === "GKP" ? "bg-gradient-to-r from-amber-400 to-yellow-500" :
          player.position === "DEF" ? "bg-gradient-to-r from-emerald-400 to-green-500" :
          player.position === "MID" ? "bg-gradient-to-r from-blue-400 to-indigo-500" :
          "bg-gradient-to-r from-rose-400 to-red-500"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
                <span className="text-white text-lg font-bold">
                  {player.name.substring(0, 2).toUpperCase()}
                </span>
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">{player.name}</h3>
                <p className="text-white/80 text-sm">{player.team} • {player.position}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-full transition-colors"
            >
              <X className="w-5 h-5 text-white" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 max-h-[60vh] overflow-y-auto">
          {/* Status Badge */}
          {isBench && (
            <div className="mb-4 flex items-center gap-2 p-3 bg-slate-100 rounded-lg">
              <Users className="w-4 h-4 text-slate-500" />
              <span className="text-sm text-slate-600">
                <span className="font-semibold">Bench #{benchOrder}</span> - Ready if needed
              </span>
            </div>
          )}

          {/* Injury/Status Alert */}
          {player.status !== "a" && player.news && (
            <div className={`mb-4 flex items-start gap-2 p-3 rounded-lg ${
              player.status === "i" || player.status === "s"
                ? "bg-red-50 border border-red-200"
                : "bg-amber-50 border border-amber-200"
            }`}>
              <AlertTriangle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
                player.status === "i" || player.status === "s" ? "text-red-500" : "text-amber-500"
              }`} />
              <span className={`text-sm ${
                player.status === "i" || player.status === "s" ? "text-red-700" : "text-amber-700"
              }`}>
                {player.news}
              </span>
            </div>
          )}

          {/* SmartPlay Score Summary */}
          <div className="mb-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-purple-500" />
                <h4 className="font-bold text-slate-800">Why Selected?</h4>
              </div>
              <div className={`px-3 py-1 rounded-full border text-sm font-semibold ${scoreInfo.color}`}>
                {scoreInfo.label}
              </div>
            </div>

            {/* Main SmartPlay Score */}
            <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-xl p-4 border border-purple-200 mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-purple-600 text-sm font-semibold">SmartPlay Score</span>
                <Award className="w-5 h-5 text-purple-400" />
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-bold text-purple-700">{player.score.toFixed(1)}</span>
                <span className="text-lg text-purple-400">/10</span>
              </div>
              <p className="text-xs text-purple-500 mt-1">
                Combines nailedness, form, and fixture difficulty
              </p>
            </div>

            {/* Score Breakdown */}
            {smartplay && (
              <div className="space-y-3 bg-slate-50 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Score Breakdown</p>
                <ScoreIndicator
                  label="Nailedness"
                  score={smartplay.nailedness_score}
                  icon={Shield}
                  color="text-violet-600"
                />
                <ScoreIndicator
                  label="Form (xG)"
                  score={smartplay.form_xg_score}
                  icon={TrendingUp}
                  color="text-orange-600"
                />
                <ScoreIndicator
                  label="Form (Points)"
                  score={smartplay.form_pts_score}
                  icon={Zap}
                  color="text-emerald-600"
                />
                <ScoreIndicator
                  label="Fixture"
                  score={smartplay.fixture_score}
                  icon={Target}
                  color="text-blue-600"
                />

                {/* Next Fixture */}
                {smartplay.next_opponent && (
                  <div className="mt-3 pt-3 border-t border-slate-200">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-500">Next Opponent</span>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-700">{smartplay.next_opponent}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          smartplay.next_fdr <= 2 ? "bg-emerald-100 text-emerald-700" :
                          smartplay.next_fdr === 3 ? "bg-amber-100 text-amber-700" :
                          "bg-red-100 text-red-700"
                        }`}>
                          FDR {smartplay.next_fdr}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Selection Reasons */}
          <div>
            <h4 className="font-semibold text-slate-700 mb-3 flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-500" />
              Selection Reasons
            </h4>
            <div className="space-y-2">
              {reasons.map((reason: string, idx: number) => (
                <div key={idx} className="flex items-start gap-2 py-2 px-3 bg-emerald-50 rounded-lg border border-emerald-100">
                  <Check className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <span className="text-sm text-emerald-800">{reason}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="mt-4 grid grid-cols-3 gap-2">
            <div className="bg-slate-50 rounded-lg p-3 text-center">
              <p className="text-[10px] text-slate-500 uppercase">Price</p>
              <p className="text-lg font-bold text-slate-800">£{player.price.toFixed(1)}m</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 text-center">
              <p className="text-[10px] text-slate-500 uppercase">Form</p>
              <p className={`text-lg font-bold ${
                player.form >= 6 ? "text-emerald-600" :
                player.form >= 4 ? "text-amber-600" : "text-slate-600"
              }`}>{player.form.toFixed(1)}</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 text-center">
              <p className="text-[10px] text-slate-500 uppercase">Owned</p>
              <p className="text-lg font-bold text-slate-800">{player.ownership.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// Generate reasons based on SmartPlay data if none provided
function generateReasons(player: LineupPlayer | BenchPlayer, smartplay?: SmartPlayData | null): string[] {
  const reasons: string[] = [];

  if (smartplay) {
    if (smartplay.nailedness_score >= 8) {
      reasons.push("High nailedness - guaranteed starter");
    } else if (smartplay.nailedness_score >= 6) {
      reasons.push("Good nailedness - expected to start");
    }

    if (smartplay.form_xg_score >= 7) {
      reasons.push("Excellent underlying stats (xG/xA)");
    }

    if (smartplay.form_pts_score >= 7) {
      reasons.push("Strong recent points returns");
    }

    if (smartplay.fixture_score >= 7) {
      reasons.push("Favorable fixture difficulty");
    } else if (smartplay.fixture_score <= 4) {
      reasons.push("Tough fixture but strong enough overall");
    }

    if (smartplay.next_fdr <= 2) {
      reasons.push(`Easy fixture vs ${smartplay.next_opponent} (FDR ${smartplay.next_fdr})`);
    }
  }

  // Fallback based on basic stats
  if (player.form >= 6) {
    reasons.push(`In excellent form (${player.form.toFixed(1)})`);
  }

  if (player.ownership <= 10) {
    reasons.push(`Differential pick (${player.ownership.toFixed(1)}% owned)`);
  }

  if (reasons.length === 0) {
    reasons.push("Best available option at this position based on SmartPlay Score");
  }

  return reasons.slice(0, 4); // Max 4 reasons
}
