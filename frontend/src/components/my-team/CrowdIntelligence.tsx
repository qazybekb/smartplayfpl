"use client";

import { useEffect, useState } from "react";
import { Users, CheckCircle2, XCircle, Flame, HelpCircle } from "lucide-react";
import { getCrowdIntelligence, type CrowdIntelligenceResponse, type CrowdIntelligenceCard, type CrowdPlayer } from "@/lib/api";

interface CrowdIntelligenceProps {
  teamId: string;
}

// Card color schemes based on card type
const cardStyles: Record<string, { bg: string; border: string }> = {
  shared_picks: { bg: "bg-amber-50", border: "border-amber-200" },
  your_edge: { bg: "bg-emerald-50", border: "border-emerald-200" },
  rising: { bg: "bg-green-50", border: "border-green-200" },
  being_sold: { bg: "bg-orange-50", border: "border-orange-200" },
  template_misses: { bg: "bg-amber-50", border: "border-amber-200" },
  hidden_gems: { bg: "bg-violet-50", border: "border-violet-200" },
  bandwagons: { bg: "bg-blue-50", border: "border-blue-200" },
  form_leaders: { bg: "bg-orange-50", border: "border-orange-200" },
};

// Card icons
const cardIcons: Record<string, string> = {
  shared_picks: "🤝",
  your_edge: "🎯",
  rising: "📈",
  being_sold: "📉",
  template_misses: "⚠️",
  hidden_gems: "💎",
  bandwagons: "🚀",
  form_leaders: "🔥",
};

function formatTransfers(value: number): string {
  if (value >= 1000000) return `+${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `+${Math.round(value / 1000)}k`;
  return `+${value}`;
}

function formatTransfersOut(value: number): string {
  if (value >= 1000000) return `-${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `-${Math.round(value / 1000)}k`;
  return `-${value}`;
}

interface IntelligenceCardProps {
  card: CrowdIntelligenceCard;
  cardKey: string;
  showTransfersIn?: boolean;
  showTransfersOut?: boolean;
}

function IntelligenceCard({ card, cardKey, showTransfersIn, showTransfersOut }: IntelligenceCardProps) {
  const style = cardStyles[cardKey] || cardStyles.shared_picks;
  const icon = cardIcons[cardKey] || "📊";

  return (
    <div className={`rounded-xl ${style.bg} ${style.border} border overflow-hidden`}>
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="font-semibold text-slate-800">{card.title}</span>
        </div>
        <HelpCircle className="w-4 h-4 text-slate-400" />
      </div>

      {/* Subtitle */}
      <div className="px-4 pb-2">
        <p className="text-xs text-slate-500">{card.subtitle}</p>
      </div>

      {/* Players List */}
      <div className="px-4 pb-4 space-y-2">
        {card.players.length === 0 ? (
          <p className="text-sm text-slate-400 italic">No players match criteria</p>
        ) : (
          card.players.map((player) => (
            <div
              key={player.id}
              className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-slate-100"
            >
              <span className="font-medium text-slate-800 text-sm">{player.name}</span>
              <div className="flex items-center gap-3 text-sm">
                {/* Ownership or Transfers */}
                {showTransfersIn ? (
                  <span className="text-emerald-600 font-medium">
                    {formatTransfers(player.transfers_in)}
                  </span>
                ) : showTransfersOut ? (
                  <span className="text-red-500 font-medium">
                    {formatTransfersOut(player.transfers_out)}
                  </span>
                ) : (
                  <span className="text-slate-500">{player.ownership.toFixed(0)}%</span>
                )}
                {/* Form with fire icon */}
                <span className={`flex items-center gap-0.5 font-medium ${
                  player.form >= 7 ? "text-orange-500" :
                  player.form >= 5 ? "text-emerald-600" :
                  player.form >= 3 ? "text-amber-500" : "text-slate-400"
                }`}>
                  <Flame className="w-3 h-3" />
                  {player.form.toFixed(1)}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function CrowdIntelligence({ teamId }: CrowdIntelligenceProps) {
  const [data, setData] = useState<CrowdIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCrowdIntelligence(teamId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [teamId]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <div key={i} className="h-48 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-2">
          <Users className="w-5 h-5 text-violet-500" />
          <h2 className="text-lg font-bold text-slate-800">Crowd Intelligence</h2>
        </div>
        <p className="text-slate-500 text-sm">
          {error || "Unable to load crowd intelligence."}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-violet-50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Users className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">Crowd Intelligence</h2>
              <p className="text-xs text-slate-500">Your squad vs the global FPL crowd</p>
            </div>
          </div>
          {/* Differential Badge */}
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-emerald-600">{data.differential_percentage}%</span>
            <span className="px-2 py-1 text-xs font-medium bg-rose-100 text-rose-600 rounded-full flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-rose-500 rounded-full" />
              Differential
            </span>
          </div>
        </div>
      </div>

      {/* You Have Section */}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          <span className="text-sm font-medium text-emerald-600">You have</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <IntelligenceCard card={data.shared_picks} cardKey="shared_picks" />
          <IntelligenceCard card={data.your_edge} cardKey="your_edge" />
          <IntelligenceCard card={data.rising} cardKey="rising" showTransfersIn />
          <IntelligenceCard card={data.being_sold} cardKey="being_sold" showTransfersOut />
        </div>
      </div>

      {/* You Don't Have Section */}
      <div className="p-4 pt-0">
        <div className="flex items-center gap-2 mb-3">
          <XCircle className="w-4 h-4 text-red-400" />
          <span className="text-sm font-medium text-red-500">You don&apos;t have</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <IntelligenceCard card={data.template_misses} cardKey="template_misses" />
          <IntelligenceCard card={data.hidden_gems} cardKey="hidden_gems" />
          <IntelligenceCard card={data.bandwagons} cardKey="bandwagons" showTransfersIn />
          <IntelligenceCard card={data.form_leaders} cardKey="form_leaders" />
        </div>
      </div>
    </div>
  );
}
