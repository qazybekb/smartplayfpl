"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Users,
  Gem,
  Coins,
  Flame,
  ChevronRight,
  Sparkles,
  Shield,
  TrendingUp,
  Zap,
  ArrowLeft,
  Database,
  Calendar,
  Clock,
  X,
  Target,
} from "lucide-react";
import { getCurrentGameweek, type Gameweek } from "@/lib/api";
import DeadlineCountdown from "@/components/DeadlineCountdown";
import {
  trackEvent,
  trackSquadBuilder,
  trackFeatureDiscovery,
  trackFunnelStep,
} from "@/lib/analytics";

// Strategy type definition
interface Strategy {
  id: string;
  name: string;
  icon: string;
  tagline: string;
  description: string;
  risk_level: string;
  risk_color: string;
  benefits: string[];
  theme: {
    primary: string;
    gradient_from: string;
    gradient_to: string;
    bg_pattern: string;
    accent: string;
  };
}

// Icon mapping
const STRATEGY_ICONS: Record<string, any> = {
  "🤖": Sparkles,
  "👥": Users,
  "💎": Gem,
  "💰": Coins,
  "🔥": Flame,
  "⚖️": Shield,
};

// Risk level colors
const RISK_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Low: { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" },
  Medium: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-200" },
  "Medium-High": { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200" },
};

// Gradient classes for each strategy
const GRADIENT_CLASSES: Record<string, string> = {
  smartplay: "from-cyan-500 to-blue-600",
  template: "from-emerald-500 to-teal-600",
  premium: "from-violet-500 to-purple-600",
  value: "from-amber-500 to-orange-600",
  form: "from-orange-500 to-red-500",
  balanced: "from-indigo-500 to-blue-600",
};

// Background patterns for each strategy
const BG_PATTERNS: Record<string, string> = {
  smartplay: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-50 via-white to-blue-50",
  template: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-emerald-50 via-white to-teal-50",
  premium: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-violet-50 via-white to-purple-50",
  value: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-50 via-white to-orange-50",
  form: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-orange-50 via-white to-red-50",
  balanced: "bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-50 via-white to-blue-50",
};

interface ShortlistPlayer {
  id: number;
  name: string;
  position: string;
  team: string;
  price: number;
}

export default function BuildPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredStrategy, setHoveredStrategy] = useState<string | null>(null);
  const [gameweek, setGameweek] = useState<Gameweek | null>(null);
  const [shortlist, setShortlist] = useState<ShortlistPlayer[]>([]);

  useEffect(() => {
    fetchStrategies();
    getCurrentGameweek().then(setGameweek).catch(console.error);
    // Load shortlist from localStorage
    const saved = localStorage.getItem("fpl-shortlist");
    if (saved) {
      setShortlist(JSON.parse(saved));
    }
    // Track page view
    trackSquadBuilder('start', { page: 'build_landing' });
    trackFunnelStep('squad_builder', 1, 'strategy_selection_page', true);
  }, []);

  const removeFromShortlist = (playerId: number) => {
    const removedPlayer = shortlist.find(p => p.id === playerId);
    const newShortlist = shortlist.filter(p => p.id !== playerId);
    setShortlist(newShortlist);
    localStorage.setItem("fpl-shortlist", JSON.stringify(newShortlist));
    if (removedPlayer) {
      trackEvent({
        name: 'shortlist_remove',
        properties: {
          player_id: playerId,
          player_name: removedPlayer.name,
          context: 'build_page',
        },
      });
    }
  };

  const clearShortlist = () => {
    const clearedCount = shortlist.length;
    setShortlist([]);
    localStorage.removeItem("fpl-shortlist");
    trackEvent({
      name: 'shortlist_clear',
      properties: {
        cleared_count: clearedCount,
        context: 'build_page',
      },
    });
  };

  // Format deadline compactly
  const formatDeadlineCompact = (deadline: string) => {
    const date = new Date(deadline);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    
    if (diffMs < 0) return "Passed";
    if (diffDays === 0) return `${diffHours}h`;
    return `${diffDays}d ${diffHours}h`;
  };

  const fetchStrategies = async () => {
    try {
      const res = await fetch("/api/build/strategies");
      if (res.ok) {
        const data = await res.json();
        setStrategies(data);
      }
    } catch (err) {
      console.error("Error fetching strategies:", err);
      // Fallback to hardcoded strategies
      setStrategies([
        {
          id: "smartplay",
          name: "SmartPlay Choice",
          icon: "🤖",
          tagline: "AI recommends",
          description: "Pure AI optimization. Picks the highest SmartPlay scores.",
          risk_level: "Medium",
          risk_color: "cyan",
          benefits: ["Highest SmartPlay scores", "No strategy bias", "AI's best picks"],
          theme: { primary: "cyan", gradient_from: "cyan-500", gradient_to: "blue-600", bg_pattern: "circuit", accent: "cyan-400" }
        },
        {
          id: "template",
          name: "Template Squad",
          icon: "👥",
          tagline: "Follow the winners",
          description: "Build like the elite. Pick what the top managers own.",
          risk_level: "Low",
          risk_color: "emerald",
          benefits: ["High ownership picks", "Protected when template hauls", "Low risk"],
          theme: { primary: "emerald", gradient_from: "emerald-500", gradient_to: "teal-600", bg_pattern: "dots", accent: "emerald-400" }
        },
        {
          id: "premium",
          name: "Premium & Punts",
          icon: "💎",
          tagline: "Stars + enablers",
          description: "2-3 premium superstars + budget enablers.",
          risk_level: "Medium",
          risk_color: "violet",
          benefits: ["2-3 premium stars", "Budget enablers", "High ceiling"],
          theme: { primary: "violet", gradient_from: "violet-500", gradient_to: "purple-600", bg_pattern: "stars", accent: "violet-400" }
        },
        {
          id: "value",
          name: "Value Hunters",
          icon: "💰",
          tagline: "Maximum bang for buck",
          description: "Find players who punch above their price tag.",
          risk_level: "Medium",
          risk_color: "amber",
          benefits: ["Best pts/£m ratio", "Room to upgrade", "Efficient squad"],
          theme: { primary: "amber", gradient_from: "amber-500", gradient_to: "orange-600", bg_pattern: "coins", accent: "amber-400" }
        },
        {
          id: "form",
          name: "Form Riders",
          icon: "🔥",
          tagline: "Chase the hot streaks",
          description: "Ride the momentum of in-form players.",
          risk_level: "Medium-High",
          risk_color: "orange",
          benefits: ["Current hot form", "Momentum picks", "Capture points"],
          theme: { primary: "orange", gradient_from: "orange-500", gradient_to: "red-500", bg_pattern: "flames", accent: "orange-400" }
        },
        {
          id: "balanced",
          name: "Balanced Squad",
          icon: "⚖️",
          tagline: "Best of all worlds",
          description: "A well-rounded squad combining form, value, and reliability.",
          risk_level: "Medium",
          risk_color: "indigo",
          benefits: ["Mix of approaches", "Balanced risk-reward", "Consistent returns"],
          theme: { primary: "indigo", gradient_from: "indigo-500", gradient_to: "blue-600", bg_pattern: "balance", accent: "indigo-400" }
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Loading strategies...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-50">
      {/* Background Pattern */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-50/50 via-transparent to-transparent pointer-events-none" />
      
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16">
            <div className="flex items-center gap-2 sm:gap-4">
              <Link 
                href="/" 
                className="p-1.5 sm:p-2 -ml-1 sm:-ml-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <ArrowLeft className="w-4 h-4 sm:w-5 sm:h-5" />
              </Link>
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                  <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <div>
                  <h1 className="text-base sm:text-lg font-bold text-slate-900">Squad Builder</h1>
                  <p className="hidden sm:block text-xs text-slate-500">Powered by SmartPlay</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-2 sm:gap-4">
              {/* Gameweek Badge - Compact on mobile */}
              {gameweek && (
                <div className="flex items-center gap-1.5 sm:gap-3 px-2 sm:px-4 py-1.5 sm:py-2 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg sm:rounded-xl">
                  <div className="flex items-center gap-1 sm:gap-1.5">
                    <Calendar className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-600" />
                    <span className="text-xs sm:text-sm font-bold text-emerald-700">GW {gameweek.id}</span>
                  </div>
                  <div className="hidden sm:block w-px h-4 bg-emerald-200" />
                  <div className="hidden sm:flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="text-xs font-medium text-emerald-600">{formatDeadlineCompact(gameweek.deadline_time)}</span>
                  </div>
                </div>
              )}

              <Link 
                href="/players" 
                className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <Database className="w-4 h-4" />
                <span className="hidden sm:inline">Player Explorer</span>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {/* Hero Section */}
        <div className="text-center mb-8 sm:mb-12">
          <h1 className="text-2xl sm:text-4xl font-bold text-slate-900 mb-3 sm:mb-4">
            Build Your FPL Squad
          </h1>
          <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto px-4">
            Choose a strategy and let SmartPlay build your optimal £100m squad.
            Each strategy uses ML-powered scores for nailedness, form, and fixture difficulty.
          </p>
        </div>

        {/* Deadline Countdown */}
        <div className="mb-8">
          <DeadlineCountdown />
        </div>

        {/* SmartPlay Badges */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mb-8 sm:mb-10 px-4">
          <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-white rounded-full border border-slate-200 shadow-sm">
            <TrendingUp className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-cyan-600" />
            <span className="text-xs sm:text-sm font-medium text-slate-700">SmartPlay Scores</span>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-white rounded-full border border-slate-200 shadow-sm">
            <Shield className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-blue-600" />
            <span className="text-xs sm:text-sm font-medium text-slate-700">FPL Validation</span>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-white rounded-full border border-slate-200 shadow-sm">
            <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-violet-600" />
            <span className="text-xs sm:text-sm font-medium text-slate-700">Smart Tags</span>
          </div>
        </div>

        {/* Shortlist Banner */}
        {shortlist.length > 0 && (
          <div className="mb-8 p-4 bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 rounded-2xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center">
                  <Target className="w-4 h-4 text-violet-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-800">Saved Players</h3>
                  <p className="text-xs text-slate-500">Players you saved from Player Explorer</p>
                </div>
              </div>
              <button
                onClick={clearShortlist}
                className="text-xs text-red-500 hover:text-red-600 font-medium"
              >
                Clear all
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {shortlist.map(player => (
                <div
                  key={player.id}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-slate-200 shadow-sm"
                >
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    player.position === "GKP" ? "bg-amber-100 text-amber-700" :
                    player.position === "DEF" ? "bg-emerald-100 text-emerald-700" :
                    player.position === "MID" ? "bg-blue-100 text-blue-700" :
                    "bg-rose-100 text-rose-700"
                  }`}>{player.position}</span>
                  <span className="text-sm font-medium text-slate-800">{player.name}</span>
                  <span className="text-xs text-slate-400">{player.team}</span>
                  <span className="text-xs font-mono text-slate-500">£{player.price.toFixed(1)}m</span>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      removeFromShortlist(player.id);
                    }}
                    className="p-0.5 text-slate-400 hover:text-red-500 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strategy Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {strategies.map((strategy) => {
            const IconComponent = STRATEGY_ICONS[strategy.icon] || Users;
            const riskColors = RISK_COLORS[strategy.risk_level] || RISK_COLORS["Medium"];
            const gradientClass = GRADIENT_CLASSES[strategy.id] || GRADIENT_CLASSES["template"];
            const bgPattern = BG_PATTERNS[strategy.id] || BG_PATTERNS["template"];
            const isHovered = hoveredStrategy === strategy.id;
            
            return (
              <Link
                key={strategy.id}
                href={`/build/${strategy.id}`}
                className={`group relative overflow-hidden rounded-2xl border-2 transition-all duration-300 ${
                  isHovered
                    ? "border-slate-300 shadow-2xl scale-[1.02]"
                    : "border-slate-200 shadow-lg hover:shadow-xl"
                }`}
                onMouseEnter={() => setHoveredStrategy(strategy.id)}
                onMouseLeave={() => setHoveredStrategy(null)}
                onClick={() => {
                  trackSquadBuilder('strategy_select', {
                    strategy_id: strategy.id,
                    strategy_name: strategy.name,
                    risk_level: strategy.risk_level,
                  });
                  trackFunnelStep('squad_builder', 2, 'strategy_selected', true);
                }}
              >
                {/* Background */}
                <div className={`absolute inset-0 ${bgPattern} opacity-60`} />
                
                {/* Content */}
                <div className="relative p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${gradientClass} flex items-center justify-center shadow-lg transition-transform duration-300 ${isHovered ? "scale-110" : ""}`}>
                      <span className="text-3xl">{strategy.icon}</span>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${riskColors.bg} ${riskColors.text} ${riskColors.border} border`}>
                      {strategy.risk_level} Risk
                    </span>
                  </div>

                  {/* Title & Tagline */}
                  <h3 className="text-xl font-bold text-slate-900 mb-1 group-hover:text-emerald-700 transition-colors">
                    {strategy.name}
                  </h3>
                  <p className="text-sm font-medium text-slate-500 mb-3">
                    {strategy.tagline}
                  </p>

                  {/* Description */}
                  <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                    {strategy.description}
                  </p>

                  {/* Benefits */}
                  <ul className="space-y-2 mb-5">
                    {strategy.benefits.map((benefit, idx) => (
                      <li key={idx} className="flex items-center gap-2 text-sm text-slate-700">
                        <div className={`w-5 h-5 rounded-full bg-gradient-to-br ${gradientClass} flex items-center justify-center flex-shrink-0`}>
                          <Zap className="w-3 h-3 text-white" />
                        </div>
                        {benefit}
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <div className={`flex items-center justify-between pt-4 border-t border-slate-200`}>
                    <span className="text-sm font-medium text-slate-500">
                      Build Squad →
                    </span>
                    <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${gradientClass} flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0`}>
                      <ChevronRight className="w-5 h-5 text-white" />
                    </div>
                  </div>
                </div>

                {/* Hover Glow Effect */}
                <div className={`absolute inset-0 bg-gradient-to-br ${gradientClass} opacity-0 group-hover:opacity-5 transition-opacity duration-300`} />
              </Link>
            );
          })}
        </div>

        {/* Bottom Info */}
        <div className="mt-12 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full text-sm text-slate-600">
            <TrendingUp className="w-4 h-4" />
            All squads validated against FPL rules and ranked by SmartPlay scores
          </div>
        </div>
      </main>
    </div>
  );
}


