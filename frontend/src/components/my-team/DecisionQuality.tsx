"use client";

import { useEffect, useState } from "react";
import { Activity, ArrowRightLeft, Crown, Armchair, TrendingUp, TrendingDown, Lightbulb } from "lucide-react";
import { getDecisionQuality, type DecisionQualityResponse } from "@/lib/api";

interface DecisionQualityProps {
  teamId: string;
}

// Circular progress component for overall score
function CircularProgress({ score, size = 120 }: { score: number; size?: number }) {
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  const getScoreColor = (score: number) => {
    if (score >= 80) return { stroke: "#10b981", text: "text-emerald-500" }; // emerald-500
    if (score >= 65) return { stroke: "#22c55e", text: "text-green-500" }; // green-500
    if (score >= 50) return { stroke: "#eab308", text: "text-yellow-500" }; // yellow-500
    if (score >= 35) return { stroke: "#f97316", text: "text-orange-500" }; // orange-500
    return { stroke: "#ef4444", text: "text-red-500" }; // red-500
  };

  const colors = getScoreColor(score);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={colors.stroke}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      {/* Score text in center */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-3xl font-bold ${colors.text}`}>{score}</span>
        <span className="text-xs text-slate-400 font-medium">/ 100</span>
      </div>
    </div>
  );
}

// Metric card component
function MetricCard({
  icon: Icon,
  iconBg,
  title,
  subtitle,
  mainValue,
  mainLabel,
  secondaryValue,
  secondaryLabel,
  tertiaryValue,
  tertiaryLabel,
  isPositive,
}: {
  icon: React.ElementType;
  iconBg: string;
  title: string;
  subtitle: string;
  mainValue: string | number;
  mainLabel: string;
  secondaryValue?: string | number;
  secondaryLabel?: string;
  tertiaryValue?: string | number;
  tertiaryLabel?: string;
  isPositive?: boolean;
}) {
  return (
    <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 ${iconBg} rounded-xl flex items-center justify-center`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="font-semibold text-slate-800">{title}</h3>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>

      {/* Main stat */}
      <div className="mb-3">
        <div className="flex items-baseline gap-1">
          <span className={`text-2xl font-bold ${
            isPositive === undefined ? "text-slate-800" :
            isPositive ? "text-emerald-600" : "text-red-500"
          }`}>
            {mainValue}
          </span>
          {isPositive !== undefined && (
            isPositive ? (
              <TrendingUp className="w-4 h-4 text-emerald-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-500" />
            )
          )}
        </div>
        <p className="text-xs text-slate-500">{mainLabel}</p>
      </div>

      {/* Secondary stats */}
      <div className="flex gap-4 text-sm">
        {secondaryValue !== undefined && (
          <div>
            <span className="font-medium text-slate-700">{secondaryValue}</span>
            <span className="text-slate-400 ml-1">{secondaryLabel}</span>
          </div>
        )}
        {tertiaryValue !== undefined && (
          <div>
            <span className="font-medium text-slate-700">{tertiaryValue}</span>
            <span className="text-slate-400 ml-1">{tertiaryLabel}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DecisionQuality({ teamId }: DecisionQualityProps) {
  const [data, setData] = useState<DecisionQualityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDecisionQuality(teamId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [teamId]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-slate-200 rounded w-1/3 mb-4" />
          <div className="flex gap-6">
            <div className="w-32 h-32 bg-slate-100 rounded-full" />
            <div className="flex-1 grid grid-cols-3 gap-4">
              <div className="h-36 bg-slate-100 rounded-xl" />
              <div className="h-36 bg-slate-100 rounded-xl" />
              <div className="h-36 bg-slate-100 rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-5 h-5 text-cyan-500" />
          <h2 className="text-lg font-bold text-slate-800">Decision Quality</h2>
        </div>
        <p className="text-slate-500 text-sm">
          {error || "Unable to load decision quality."}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-cyan-50 to-white">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-800">Decision Quality</h2>
            <p className="text-xs text-slate-500">
              Analysis of your last {data.gameweeks_analyzed} gameweeks
            </p>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Overall Score */}
          <div className="flex flex-col items-center lg:items-start">
            <CircularProgress score={data.overall_score} />
            <p className="mt-2 text-sm font-medium text-slate-600 text-center lg:text-left">
              Overall Score
            </p>
          </div>

          {/* Metrics Grid */}
          <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Transfer Quality */}
            <MetricCard
              icon={ArrowRightLeft}
              iconBg="bg-gradient-to-br from-violet-500 to-purple-600"
              title="Transfer Quality"
              subtitle="Transfer decisions"
              mainValue={`${data.transfer_quality.success_rate.toFixed(0)}%`}
              mainLabel="Success Rate"
              secondaryValue={data.transfer_quality.net_points_gained > 0 ? `+${data.transfer_quality.net_points_gained}` : data.transfer_quality.net_points_gained}
              secondaryLabel="net pts"
              tertiaryValue={data.transfer_quality.hits_taken}
              tertiaryLabel="hits"
              isPositive={data.transfer_quality.net_points_gained >= 0}
            />

            {/* Captain Quality */}
            <MetricCard
              icon={Crown}
              iconBg="bg-gradient-to-br from-amber-500 to-orange-600"
              title="Captain Quality"
              subtitle="Captain picks"
              mainValue={`${data.captain_quality.success_rate.toFixed(0)}%`}
              mainLabel="Success Rate (6+ pts)"
              secondaryValue={data.captain_quality.captain_points}
              secondaryLabel="total pts"
              tertiaryValue={data.captain_quality.most_captained}
              tertiaryLabel=""
            />

            {/* Bench Management */}
            <MetricCard
              icon={Armchair}
              iconBg="bg-gradient-to-br from-slate-500 to-slate-700"
              title="Bench Management"
              subtitle="Points wasted"
              mainValue={data.bench_management.points_on_bench}
              mainLabel="Points on Bench"
              secondaryValue={data.bench_management.per_gameweek.toFixed(1)}
              secondaryLabel="per GW"
              isPositive={data.bench_management.per_gameweek <= 5}
            />
          </div>
        </div>

        {/* Insights Section */}
        <div className="mt-6 space-y-3">
          {/* Overall Insight */}
          <div className="bg-gradient-to-r from-slate-50 to-slate-100 rounded-xl p-4 border border-slate-200">
            <p className="text-sm text-slate-700">{data.overall_insight}</p>
          </div>

          {/* Key Insight */}
          <div className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-xl p-4 border border-amber-200">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center flex-shrink-0">
                <Lightbulb className="w-4 h-4 text-amber-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-amber-700 mb-1">Key Insight</p>
                <p className="text-sm text-amber-900">{data.key_insight}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
