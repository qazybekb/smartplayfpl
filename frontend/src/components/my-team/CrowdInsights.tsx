"use client";

import { useEffect, useState } from "react";
import { Users, TrendingUp, TrendingDown, Target, Zap, Gem, Rocket, ChevronDown, ChevronUp, Sparkles, Loader2 } from "lucide-react";
import { getCrowdInsights, getAICrowdInsights, type CrowdInsightsResponse, type CrowdInsightCard } from "@/lib/api";

interface CrowdInsightsProps {
  teamId: string;
}

const typeIcons: Record<string, React.ReactNode> = {
  smart_money: <TrendingUp className="w-4 h-4" />,
  under_radar: <Gem className="w-4 h-4" />,
  bandwagon: <Rocket className="w-4 h-4" />,
  panic_sell: <TrendingDown className="w-4 h-4" />,
  value_pick: <Zap className="w-4 h-4" />,
  template_score: <Target className="w-4 h-4" />,
  squad_alert: <TrendingDown className="w-4 h-4" />,
};

const tagColors: Record<string, { bg: string; text: string }> = {
  green: { bg: "bg-emerald-100", text: "text-emerald-700" },
  red: { bg: "bg-red-100", text: "text-red-700" },
  amber: { bg: "bg-amber-100", text: "text-amber-700" },
  blue: { bg: "bg-blue-100", text: "text-blue-700" },
  gray: { bg: "bg-slate-100", text: "text-slate-600" },
};

const cardColors: Record<string, { bg: string; border: string; iconBg: string }> = {
  smart_money: { bg: "bg-emerald-50/50", border: "border-emerald-200", iconBg: "bg-emerald-500" },
  under_radar: { bg: "bg-violet-50/50", border: "border-violet-200", iconBg: "bg-violet-500" },
  bandwagon: { bg: "bg-blue-50/50", border: "border-blue-200", iconBg: "bg-blue-500" },
  panic_sell: { bg: "bg-red-50/50", border: "border-red-200", iconBg: "bg-red-500" },
  value_pick: { bg: "bg-amber-50/50", border: "border-amber-200", iconBg: "bg-amber-500" },
  template_score: { bg: "bg-slate-50/50", border: "border-slate-200", iconBg: "bg-slate-600" },
  squad_alert: { bg: "bg-orange-50/50", border: "border-orange-200", iconBg: "bg-orange-500" },
};

// Highlight player names and numbers in description text
function HighlightedDescription({ text, playerNames }: { text: string; playerNames: string[] }) {
  // Pattern for numbers: percentages, prices, transfer counts (k suffix), form scores
  const numberPatternStr = '\\d+\\.?\\d*%|£\\d+\\.?\\d*m?|[+-]?\\d+k|\\d+\\.\\d+\\s*form|\\d{2,}(?:,\\d{3})*';

  // Build pattern for player names (escape special chars)
  const escapedNames = playerNames
    .filter(name => name && name.length > 2)
    .map(name => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));

  // Combine patterns with capturing group
  let patternStr: string;
  if (escapedNames.length > 0) {
    const namePattern = escapedNames.join('|');
    patternStr = `(${namePattern}|${numberPatternStr})`;
  } else {
    patternStr = `(${numberPatternStr})`;
  }

  const pattern = new RegExp(patternStr, 'gi');
  const parts = text.split(pattern).filter(part => part !== '');

  // Create a fresh regex for testing (since .test() advances lastIndex)
  const numberTestPattern = new RegExp(`^(${numberPatternStr})$`, 'i');

  return (
    <>
      {parts.map((part, i) => {
        if (!part) return null;

        // Check if it's a player name
        const isPlayerName = playerNames.some(
          name => name && part.toLowerCase() === name.toLowerCase()
        );

        // Check if it's a number/stat
        const isNumber = numberTestPattern.test(part);

        if (isPlayerName) {
          return (
            <span key={i} className="font-semibold text-slate-800">
              {part}
            </span>
          );
        }

        if (isNumber) {
          return (
            <span key={i} className="font-semibold text-violet-600">
              {part}
            </span>
          );
        }

        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

function InsightCard({ insight }: { insight: CrowdInsightCard }) {
  const [expanded, setExpanded] = useState(false);
  const colors = cardColors[insight.type] || cardColors.template_score;
  const icon = typeIcons[insight.type] || <Zap className="w-4 h-4" />;
  const tag = tagColors[insight.tag_color] || tagColors.gray;

  const hasPlayers = insight.players && insight.players.length > 0;
  const playerNames = insight.players?.map(p => p.name) || [];

  return (
    <div className={`rounded-xl border ${colors.bg} ${colors.border} overflow-hidden`}>
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <div className={`w-7 h-7 ${colors.iconBg} rounded-lg flex items-center justify-center text-white shrink-0`}>
              {icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg">{insight.icon}</span>
                <h3 className="font-semibold text-slate-800 text-sm leading-tight">
                  {insight.title}
                </h3>
              </div>
            </div>
          </div>
          <span className={`px-2 py-0.5 text-xs font-bold rounded ${tag.bg} ${tag.text} shrink-0`}>
            {insight.tag}
          </span>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">
          <HighlightedDescription text={insight.description} playerNames={playerNames} />
        </p>

        {/* Template Score special display */}
        {insight.type === "template_score" && insight.value && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-slate-500">Category:</span>
            <span className="px-2 py-0.5 text-xs font-semibold bg-slate-200 text-slate-700 rounded">
              {insight.value}
            </span>
          </div>
        )}
      </div>

      {/* Players section (expandable) */}
      {hasPlayers && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 hover:bg-slate-50/50 transition-colors"
          >
            <span>{insight.players.length} player{insight.players.length > 1 ? 's' : ''}</span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {expanded && (
            <div className="px-4 pb-3 space-y-2 border-t border-slate-100 pt-2">
              {insight.players.map((player) => (
                <div
                  key={player.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-800">{player.name}</span>
                    <span className="text-xs text-slate-400">{player.team}</span>
                    {player.in_squad && (
                      <span className="px-1.5 py-0.5 text-[10px] font-medium bg-emerald-100 text-emerald-600 rounded">
                        IN SQUAD
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-slate-500">£{player.price.toFixed(1)}m</span>
                    <span className="text-slate-500">{player.ownership.toFixed(1)}%</span>
                    <span className={`font-medium ${player.form >= 6 ? 'text-emerald-600' : player.form >= 4 ? 'text-amber-600' : 'text-slate-500'}`}>
                      {player.form.toFixed(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function CrowdInsights({ teamId }: CrowdInsightsProps) {
  const [data, setData] = useState<CrowdInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [isAiGenerated, setIsAiGenerated] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    getCrowdInsights(teamId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [teamId]);

  const handleRegenerateWithAI = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const aiData = await getAICrowdInsights(teamId);
      setData(aiData);
      setIsAiGenerated(true);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "Failed to generate AI insights");
    } finally {
      setAiLoading(false);
    }
  };

  const handleResetToBasic = async () => {
    setLoading(true);
    setAiError(null);
    try {
      const basicData = await getCrowdInsights(teamId);
      setData(basicData);
      setIsAiGenerated(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-40 bg-slate-100 rounded-xl" />
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
          <h2 className="text-lg font-bold text-slate-800">Crowd Insights</h2>
        </div>
        <p className="text-slate-500 text-sm">
          {error || "Unable to load crowd insights."}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-violet-500" />
            <h2 className="text-lg font-bold text-slate-800">Crowd Insights</h2>
            {isAiGenerated && (
              <span className="px-2 py-0.5 text-xs font-medium bg-violet-100 text-violet-700 rounded-full flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                AI
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500">Avg ownership:</span>
              <span className="font-semibold text-slate-700">{data.avg_ownership.toFixed(1)}%</span>
            </div>
            {isAiGenerated ? (
              <button
                onClick={handleResetToBasic}
                disabled={loading}
                className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
              >
                Reset
              </button>
            ) : (
              <button
                onClick={handleRegenerateWithAI}
                disabled={aiLoading}
                className="px-3 py-1.5 text-xs font-medium text-white bg-violet-500 hover:bg-violet-600 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {aiLoading ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3" />
                    Get new insights with AI
                  </>
                )}
              </button>
            )}
          </div>
        </div>
        {aiError && (
          <p className="mt-2 text-xs text-red-500">{aiError}</p>
        )}
      </div>

      {/* Insight Cards Grid */}
      <div className={`p-4 grid grid-cols-1 sm:grid-cols-2 gap-3 ${aiLoading ? 'opacity-50' : ''}`}>
        {data.insights.map((insight, idx) => (
          <InsightCard key={idx} insight={insight} />
        ))}
      </div>

    </div>
  );
}
