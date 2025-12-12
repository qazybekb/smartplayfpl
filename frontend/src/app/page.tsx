"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Brain,
  Zap,
  ChevronRight,
  ArrowRight,
  Sparkles,
  Trophy,
  Users,
  Calendar,
  Lightbulb,
  Search,
  RefreshCw,
  Activity,
  Wand2,
  Check,
  BarChart3,
  Eye,
  GraduationCap,
  Clock,
  Star,
  Shield,
  Menu,
  X,
  Target,
  TrendingUp,
  Github,
  Linkedin,
  Network,
  GitBranch,
  Layers,
  Cpu,
} from "lucide-react";
import DeadlineCountdown from "@/components/DeadlineCountdown";
import {
  trackTeamAnalysis,
  trackFunnelStep,
  trackGoalCompletion,
  trackEvent,
  getUserData,
  recordTeamAnalyzed,
} from "@/lib/analytics";

const RECENT_TEAMS_KEY = "fpl_recent_teams";
const MAX_RECENT_TEAMS = 3;

interface RecentTeam {
  id: string;
  name?: string;
  lastAccessed: number;
}

interface GameweekInfo {
  id: number;
  name: string;
  deadline_time: string;
  is_current: boolean;
  is_next: boolean;
  finished: boolean;
}

// What SmartPlay actually does - based on real implementation
const FEATURES = [
  { name: "AI Predictions", icon: "🎯", desc: "Points & playing time forecasts", color: "from-purple-500 to-indigo-600" },
  { name: "SmartPlay Scores", icon: "📊", desc: "Position-weighted player rankings", color: "from-emerald-500 to-teal-600" },
  { name: "Transfer Engine", icon: "🔄", desc: "Who to sell, who to buy", color: "from-blue-500 to-cyan-600" },
  { name: "Captain Picks", icon: "👑", desc: "Safe, balanced & differential", color: "from-amber-500 to-yellow-500" },
  { name: "Crowd Insights", icon: "👁️", desc: "What top managers are doing", color: "from-pink-500 to-rose-500" },
  { name: "Fixture Analysis", icon: "📅", desc: "Easy/hard runs ahead", color: "from-green-500 to-emerald-600" },
];

export default function LandingPage() {
  const router = useRouter();
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [gameweek, setGameweek] = useState<GameweekInfo | null>(null);
  const [countdown, setCountdown] = useState<{ days: number; hours: number; minutes: number; seconds: number } | null>(null);
  const [fplId, setFplId] = useState("");
  const [fplIdError, setFplIdError] = useState("");
  const [recentTeams, setRecentTeams] = useState<RecentTeam[]>([]);

  // Load recent teams from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(RECENT_TEAMS_KEY);
      if (stored) {
        const teams = JSON.parse(stored) as RecentTeam[];
        // Sort by last accessed (most recent first)
        teams.sort((a, b) => b.lastAccessed - a.lastAccessed);
        setRecentTeams(teams.slice(0, MAX_RECENT_TEAMS));
      }
    } catch (e) {
      console.error("Failed to load recent teams", e);
    }
  }, []);

  // Save team to recent teams
  const saveRecentTeam = (teamId: string) => {
    try {
      const stored = localStorage.getItem(RECENT_TEAMS_KEY);
      let teams: RecentTeam[] = stored ? JSON.parse(stored) : [];

      // Remove existing entry for this team
      teams = teams.filter(t => t.id !== teamId);

      // Add new entry at the beginning
      teams.unshift({ id: teamId, lastAccessed: Date.now() });

      // Keep only the most recent teams
      teams = teams.slice(0, MAX_RECENT_TEAMS);

      localStorage.setItem(RECENT_TEAMS_KEY, JSON.stringify(teams));
    } catch (e) {
      console.error("Failed to save recent team", e);
    }
  };

  const handleGetInsights = () => {
    const trimmedId = fplId.trim();

    if (!trimmedId) {
      setFplIdError("Please enter your FPL Team ID");
      trackEvent({ name: 'form_error', properties: { field: 'fpl_id', error: 'empty' } });
      return;
    }

    const numericId = parseInt(trimmedId);
    if (isNaN(numericId) || numericId <= 0) {
      setFplIdError("Please enter a valid Team ID (numbers only)");
      trackEvent({ name: 'form_error', properties: { field: 'fpl_id', error: 'invalid_format' } });
      return;
    }

    if (trimmedId.length > 10) {
      setFplIdError("Team ID seems too long. Check and try again.");
      trackEvent({ name: 'form_error', properties: { field: 'fpl_id', error: 'too_long' } });
      return;
    }

    setFplIdError("");
    saveRecentTeam(trimmedId);

    // Track analytics
    const userData = getUserData();
    const isReturning = userData.teamsAnalyzed.includes(trimmedId);
    trackTeamAnalysis(trimmedId, isReturning);
    trackFunnelStep('team_analysis', 1, 'fpl_id_submitted');
    recordTeamAnalyzed(trimmedId);

    router.push(`/my-team/${numericId}`);
  };

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const fetchGameweek = async () => {
      try {
        // Use the proxy route which goes through Next.js rewrites
        const response = await fetch("/api/gameweek/current");
        if (response.ok) {
          const data = await response.json();
          setGameweek(data);
        }
      } catch (e) {
        console.error("Failed to fetch gameweek", e);
        // Silent fail - DeadlineCountdown component will handle display
      }
    };
    fetchGameweek();
  }, []);

  useEffect(() => {
    if (!gameweek?.deadline_time) return;
    const updateCountdown = () => {
      const deadline = new Date(gameweek.deadline_time);
      const now = new Date();
      const diff = deadline.getTime() - now.getTime();
      if (diff <= 0) { setCountdown(null); return; }
      setCountdown({
        days: Math.floor(diff / (1000 * 60 * 60 * 24)),
        hours: Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)),
        minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
        seconds: Math.floor((diff % (1000 * 60)) / 1000),
      });
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [gameweek]);

  return (
    <div className="bg-slate-50">
      {/* Navigation */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled || mobileMenuOpen ? "bg-white/95 backdrop-blur-xl shadow-sm border-b border-slate-200/60" : "bg-transparent"
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/25">
                <Brain className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
              </div>
              <span className="text-lg sm:text-xl font-bold text-slate-900">
                Smart<span className="text-emerald-600">Play</span>
              </span>
              <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-emerald-100 rounded-full">
                <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                <span className="text-[10px] font-semibold text-emerald-700">AI-POWERED</span>
              </div>
            </div>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-5">
              <Link href="/players" className="text-slate-600 hover:text-emerald-600 font-medium transition-colors">
                Players
              </Link>
              <Link href="/model" className="text-slate-600 hover:text-emerald-600 font-medium transition-colors">
                AI Model
              </Link>
              <Link href="/build" className="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-700 transition-all shadow-lg shadow-emerald-500/25">
                Build Squad
              </Link>
            </div>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-slate-100 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <X className="w-6 h-6 text-slate-700" />
              ) : (
                <Menu className="w-6 h-6 text-slate-700" />
              )}
            </button>
          </div>

          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden mt-4 pb-4 border-t border-slate-100 pt-4 space-y-3">
              <Link
                href="/players"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-2.5 text-slate-700 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg font-medium transition-colors"
              >
                Players
              </Link>
              <Link
                href="/model"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-2.5 text-slate-700 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg font-medium transition-colors"
              >
                AI Model
              </Link>
              <Link
                href="/my-team"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-2.5 text-slate-700 hover:bg-emerald-50 hover:text-emerald-600 rounded-lg font-medium transition-colors"
              >
                My Team
              </Link>
              <Link
                href="/build"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-4 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl text-center shadow-lg shadow-emerald-500/25"
              >
                Build Squad
              </Link>
            </div>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 sm:pt-28 pb-8 sm:pb-12 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-white via-slate-50 to-slate-100" />
        <div className="absolute top-0 left-0 right-0 h-[600px] bg-gradient-to-br from-emerald-50/80 via-transparent to-teal-50/50" />

        {/* Animated background orbs - hidden on mobile for performance */}
        <div className="hidden sm:block absolute top-20 left-1/4 w-96 h-96 bg-emerald-200/30 rounded-full blur-3xl animate-pulse" />
        <div className="hidden sm:block absolute bottom-0 right-1/4 w-96 h-96 bg-teal-200/30 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6">
          {/* Deadline Countdown */}
          <div className="flex justify-center mb-4 sm:mb-8">
            <div className="w-full max-w-5xl">
              <DeadlineCountdown />
            </div>
          </div>

          {/* Hero Content */}
          <div className="text-center max-w-4xl mx-auto mb-6 sm:mb-8">
            {/* Pain Point Hook */}
            <p className="text-slate-500 text-sm sm:text-lg mb-2 sm:mb-3 px-2">
              What if AI could analyse your entire team and tell you exactly what to do?
            </p>

            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-extrabold text-slate-900 leading-[1.1] mb-3 sm:mb-5 tracking-tight px-2">
              Your{" "}
              <span className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-600 bg-clip-text text-transparent">
                FPL AI Assistant
              </span>
            </h1>

            <p className="text-base sm:text-xl text-slate-600 max-w-2xl mx-auto mb-3 sm:mb-4 leading-relaxed px-2">
              Get a complete analysis of your squad: optimal lineup, who to transfer, captain picks,
              chip strategy — with <strong>reasoning</strong> for every recommendation.
            </p>

            {/* UC Berkeley Badge */}
            <div className="flex justify-center mb-4 sm:mb-6">
              <div className="inline-flex flex-wrap items-center justify-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-gradient-to-r from-[#003262] to-[#004785] rounded-full shadow-lg">
                <GraduationCap className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#FDB515]" />
                <span className="text-white text-xs sm:text-sm font-medium">UC Berkeley</span>
                <span className="text-white/60 hidden sm:inline">•</span>
                <Brain className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#FDB515]" />
                <span className="text-white/80 text-xs sm:text-sm">AI-Powered</span>
              </div>
            </div>
          </div>

          {/* Main CTA - FPL ID Input */}
          <div className="max-w-3xl mx-auto mb-6 sm:mb-8">
            <div className="bg-white rounded-2xl sm:rounded-3xl shadow-2xl border border-slate-200/60 p-4 sm:p-8">
              <div className="flex items-center gap-3 sm:gap-4 mb-4 sm:mb-6">
                <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/30 flex-shrink-0">
                  <Zap className="w-5 h-5 sm:w-7 sm:h-7 text-white" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base sm:text-xl font-bold text-slate-900">Get Your Personalized Analysis</h3>
                  <p className="text-slate-500 text-xs sm:text-base">Enter your FPL ID — AI analyses your entire squad</p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 mb-3">
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="Your FPL Team ID"
                  value={fplId}
                  onChange={(e) => {
                    setFplId(e.target.value);
                    setFplIdError("");
                  }}
                  onKeyDown={(e) => e.key === "Enter" && handleGetInsights()}
                  className={`flex-1 px-4 sm:px-5 py-3.5 sm:py-4 rounded-xl border-2 text-base sm:text-lg ${fplIdError ? "border-red-300 focus:border-red-400 focus:ring-red-100" : "border-slate-200 focus:border-emerald-400 focus:ring-emerald-100"} focus:ring-4 outline-none text-slate-800 placeholder:text-slate-400 font-medium`}
                />
                <button
                  onClick={handleGetInsights}
                  className="w-full sm:w-auto px-6 sm:px-8 py-3.5 sm:py-4 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold rounded-xl hover:from-emerald-600 hover:to-teal-700 transition-all shadow-lg shadow-emerald-500/25 flex items-center justify-center gap-2 text-base sm:text-lg"
                >
                  <Brain className="w-5 h-5 sm:w-6 sm:h-6" />
                  Analyse
                </button>
              </div>

              {fplIdError && (
                <p className="text-red-500 text-sm mb-3 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />
                  {fplIdError}
                </p>
              )}

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                <Link
                  href="/find-fpl-id"
                  className="inline-flex items-center gap-1.5 text-xs sm:text-sm text-emerald-600 hover:text-emerald-700 hover:underline font-medium"
                >
                  <Lightbulb className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  Where do I find my FPL ID?
                  <ChevronRight className="w-3 h-3" />
                </Link>
                <span className="text-xs sm:text-sm text-slate-400">Free • No signup • Instant</span>
              </div>

            </div>
          </div>

          {/* Alternative Options */}
          <div className="flex items-center justify-center gap-3 sm:gap-4 mb-4 sm:mb-6">
            <div className="h-px bg-slate-200 w-12 sm:w-16" />
            <span className="text-xs sm:text-sm text-slate-400">or</span>
            <div className="h-px bg-slate-200 w-12 sm:w-16" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 max-w-3xl mx-auto">
            {/* Build Squad */}
            <Link href="/build" className="group flex flex-col p-4 sm:p-5 bg-white rounded-xl sm:rounded-2xl border border-slate-200 hover:border-indigo-300 hover:shadow-lg transition-all">
              <div className="flex items-center gap-3 mb-2 sm:mb-3">
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md flex-shrink-0">
                  <Wand2 className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] sm:text-xs text-indigo-600 font-semibold uppercase tracking-wide">New to FPL?</p>
                  <p className="font-bold text-slate-900 text-base sm:text-lg">AI Builds Your Squad</p>
                </div>
                <ChevronRight className="w-4 h-4 sm:w-5 sm:h-5 text-slate-300 group-hover:text-indigo-500 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </div>
              <p className="text-xs sm:text-sm text-slate-600 mb-2 sm:mb-3">
                Pick a strategy and AI assembles an optimised 15-player squad.
              </p>
              <div className="flex flex-wrap gap-1 sm:gap-1.5">
                <span className="px-1.5 sm:px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] sm:text-xs font-medium rounded-full">Balanced</span>
                <span className="px-1.5 sm:px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] sm:text-xs font-medium rounded-full">Template</span>
                <span className="px-1.5 sm:px-2 py-0.5 bg-indigo-50 text-indigo-700 text-[10px] sm:text-xs font-medium rounded-full">Differential</span>
                <span className="hidden sm:inline-block px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full">Form-Based</span>
              </div>
            </Link>

            {/* Player Search - Faceted Search */}
            <Link href="/players" className="group flex flex-col p-4 sm:p-5 bg-white rounded-xl sm:rounded-2xl border border-slate-200 hover:border-emerald-300 hover:shadow-lg transition-all">
              <div className="flex items-center gap-3 mb-2 sm:mb-3">
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md flex-shrink-0">
                  <Search className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] sm:text-xs text-emerald-600 font-semibold uppercase tracking-wide">Faceted Search</p>
                  <p className="font-bold text-slate-900 text-base sm:text-lg">Search 750+ Players</p>
                </div>
                <ChevronRight className="w-4 h-4 sm:w-5 sm:h-5 text-slate-300 group-hover:text-emerald-500 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </div>
              <p className="text-xs sm:text-sm text-slate-600 mb-2 sm:mb-3">
                Filter by position, team, price, form, and SmartPlay Scores.
              </p>
              <div className="flex flex-wrap gap-1 sm:gap-1.5">
                <span className="px-1.5 sm:px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] sm:text-xs font-medium rounded-full">Position</span>
                <span className="px-1.5 sm:px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] sm:text-xs font-medium rounded-full">Team</span>
                <span className="px-1.5 sm:px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] sm:text-xs font-medium rounded-full">Price</span>
                <span className="px-1.5 sm:px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] sm:text-xs font-medium rounded-full">Form</span>
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* Pain Points → Solutions */}
      <section className="py-10 sm:py-16 bg-white border-y border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-8 sm:mb-12">
            <p className="text-emerald-600 font-semibold text-xs sm:text-sm uppercase tracking-wide mb-2">The FPL Struggle is Real</p>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 mb-3 sm:mb-4">
              Sound Familiar?
            </h2>
            <p className="text-slate-600 text-sm sm:text-base max-w-2xl mx-auto px-2">Based on research from r/FantasyPL and FPL community surveys</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-6 mb-8 sm:mb-12">
            {[
              { pain: '"I spend 5+ hours researching each week"', solution: "AI analyses everything in seconds", icon: Clock, stat: "65% cite time as major pain" },
              { pain: '"Pep roulette destroyed my rank again"', solution: "Rotation risk analysis before deadline", icon: RefreshCw, stat: "80% frustration rate" },
              { pain: '"Too many tabs — FPL, Understat, Twitter..."', solution: "Everything in one unified dashboard", icon: Activity, stat: "70% face info overload" },
              { pain: '"Is this injury news even reliable?"', solution: "Knowledge Graph validates all sources", icon: Shield, stat: "80% injury chaos" },
              { pain: '"Which differential will actually haul?"', solution: "AI finds hidden gems with SmartPlay scores", icon: TrendingUp, stat: "60% struggle with picks" },
              { pain: '"Should I wildcard now or wait?"', solution: "Chip strategy with fixture planning", icon: Sparkles, stat: "Timing is everything" },
            ].map((item, i) => (
              <div key={i} className="bg-slate-50 rounded-xl sm:rounded-2xl p-3.5 sm:p-5 border border-slate-100 hover:shadow-md transition-all">
                <div className="flex items-center justify-between mb-2 sm:mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-red-100 flex items-center justify-center">
                      <item.icon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-red-500" />
                    </div>
                    <span className="text-[10px] sm:text-xs font-medium text-red-500 uppercase">Pain</span>
                  </div>
                  <span className="text-[10px] sm:text-xs text-slate-400 hidden sm:block">{item.stat}</span>
                </div>
                <p className="text-slate-700 font-medium italic mb-2 sm:mb-3 text-sm sm:text-base">{item.pain}</p>
                <div className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-500 flex-shrink-0" />
                  <p className="text-xs sm:text-sm text-emerald-700 font-medium">{item.solution}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center justify-center gap-4 sm:gap-8 py-4 sm:py-6 px-4 sm:px-8 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 rounded-xl sm:rounded-2xl">
            {[
              { value: "12M+", label: "FPL players" },
              { value: "750+", label: "Players analysed" },
              { value: "Real-time", label: "Recommendations" },
              { value: "Free", label: "No signup" },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <p className="text-lg sm:text-2xl font-bold text-emerald-400 font-mono">{stat.value}</p>
                <p className="text-[10px] sm:text-sm text-slate-400">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What SmartPlay Does */}
      <section className="py-10 sm:py-16 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-6 sm:mb-10">
            <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-emerald-100 rounded-full mb-3 sm:mb-4">
              <Brain className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-600" />
              <span className="text-xs sm:text-sm font-semibold text-emerald-700">AI-Powered Analysis</span>
            </div>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 mb-3 sm:mb-4">
              What SmartPlay Does For You
            </h2>
            <p className="text-sm sm:text-lg text-slate-600 max-w-2xl mx-auto px-2">
              AI predictions combined with real-time FPL data to give you actionable insights.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-4">
            {FEATURES.map((feature, i) => (
              <div key={i} className="bg-white rounded-lg sm:rounded-xl p-3 sm:p-5 border border-slate-100 hover:shadow-lg hover:border-slate-200 transition-all">
                <div className="flex items-start gap-2 sm:gap-3">
                  <span className="text-xl sm:text-2xl">{feature.icon}</span>
                  <div className="min-w-0">
                    <h4 className="font-bold text-slate-900 text-sm sm:text-base">{feature.name}</h4>
                    <p className="text-[10px] sm:text-sm text-slate-500 leading-tight">{feature.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <p className="text-center text-slate-500 mt-4 sm:mt-6 text-xs sm:text-base px-2">
            → Powered by <strong className="text-slate-700">custom AI</strong> + <strong className="text-slate-700">real-time analysis</strong>
          </p>
        </div>
      </section>

      {/* What You Get - Analysis Modules */}
      <section className="py-10 sm:py-16 bg-white border-y border-slate-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-6 sm:mb-12">
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 mb-2 sm:mb-4">
              Complete Team Analysis
            </h2>
            <p className="text-sm sm:text-lg text-slate-600">Enter your FPL ID and get these modules:</p>
          </div>

          {/* Priority Actions Highlight */}
          <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl sm:rounded-2xl p-4 sm:p-6 mb-4 sm:mb-8 text-white">
            <div className="flex items-start gap-3 sm:gap-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0">
                <Zap className="w-5 h-5 sm:w-6 sm:h-6" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base sm:text-xl font-bold mb-1.5 sm:mb-2">Priority Actions for This Gameweek</h3>
                <p className="text-emerald-100 mb-2 sm:mb-3 text-xs sm:text-base">
                  AI identifies what matters most RIGHT NOW:
                </p>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                  <span className="px-2 sm:px-3 py-0.5 sm:py-1 bg-white/20 rounded-full text-[10px] sm:text-sm">🔴 Replace injured</span>
                  <span className="px-2 sm:px-3 py-0.5 sm:py-1 bg-white/20 rounded-full text-[10px] sm:text-sm">👑 Captain pick</span>
                  <span className="px-2 sm:px-3 py-0.5 sm:py-1 bg-white/20 rounded-full text-[10px] sm:text-sm">🔥 Form alert</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-4">
            {[
              { icon: BarChart3, title: "GW Review", desc: "What went right, what went wrong", num: "1", color: "emerald" },
              { icon: Activity, title: "Risk Alerts", desc: "Injuries, rotation, price changes", num: "2", color: "amber" },
              { icon: RefreshCw, title: "Transfer Engine", desc: "Who to sell, who to buy", num: "3", color: "violet" },
              { icon: Shield, title: "Lineup Optimiser", desc: "Optimal formation & bench order", num: "4", color: "blue" },
              { icon: Trophy, title: "Captain Picks", desc: "Safe, balanced & differential", num: "5", color: "amber" },
              { icon: Eye, title: "Crowd Insights", desc: "What top managers are doing", num: "6", color: "pink" },
            ].map((feature, i) => (
              <div key={i} className="bg-slate-50 rounded-lg sm:rounded-xl p-3 sm:p-5 border border-slate-100 hover:shadow-lg transition-all group">
                <div className="flex items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                  <span className={`w-6 h-6 sm:w-8 sm:h-8 rounded-full ${feature.color === 'emerald' ? 'bg-emerald-100 text-emerald-700' : feature.color === 'amber' ? 'bg-amber-100 text-amber-700' : feature.color === 'violet' ? 'bg-violet-100 text-violet-700' : feature.color === 'blue' ? 'bg-blue-100 text-blue-700' : 'bg-pink-100 text-pink-700'} text-xs sm:text-sm font-bold flex items-center justify-center`}>{feature.num}</span>
                  <feature.icon className={`w-4 h-4 sm:w-5 sm:h-5 ${feature.color === 'emerald' ? 'text-emerald-600' : feature.color === 'amber' ? 'text-amber-600' : feature.color === 'violet' ? 'text-violet-600' : feature.color === 'blue' ? 'text-blue-600' : 'text-pink-600'}`} />
                </div>
                <h4 className="font-bold text-slate-900 mb-0.5 sm:mb-1 text-sm sm:text-lg">{feature.title}</h4>
                <p className="text-[10px] sm:text-sm text-slate-500 leading-tight sm:leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-10 sm:py-16 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-6 sm:mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 mb-2 sm:mb-4">What Managers Are Saying</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-6">
            {[
              {
                quote: "Lineup builder suggested 3-4-3 with Salah captain. Got 12 extra points that week.",
                name: "James Thompson",
                location: "Manchester, UK",
                avatar: "JT",
                color: "from-blue-500 to-indigo-600",
              },
              {
                quote: "Priority Actions told me my defender was flagged. Swapped him out, got a green arrow.",
                name: "Aisha Okonkwo",
                location: "Lagos, Nigeria",
                avatar: "AO",
                color: "from-purple-500 to-pink-600",
              },
              {
                quote: "Template comparison showed I was missing 3 essential players. Climbed 200k places!",
                name: "Arman Yessenbayev",
                location: "Almaty, KZ",
                avatar: "AY",
                color: "from-emerald-500 to-teal-600",
              },
            ].map((testimonial, i) => (
              <div key={i} className="bg-white rounded-lg sm:rounded-xl p-4 sm:p-6 border border-slate-100 shadow-sm flex flex-col h-full">
                <div className="flex items-center gap-0.5 sm:gap-1 mb-2 sm:mb-3">
                  {[1, 2, 3, 4, 5].map(s => <Star key={s} className="w-3 h-3 sm:w-4 sm:h-4 text-amber-400 fill-amber-400" />)}
                </div>
                <p className="text-slate-700 mb-3 sm:mb-4 italic flex-1 text-sm sm:text-base leading-snug">&ldquo;{testimonial.quote}&rdquo;</p>
                <div className="flex items-center gap-2 sm:gap-3 mt-auto pt-2 border-t border-slate-100">
                  <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gradient-to-br ${testimonial.color} flex items-center justify-center text-white font-bold text-xs sm:text-sm flex-shrink-0`}>
                    {testimonial.avatar}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-800 text-sm sm:text-base truncate">{testimonial.name}</p>
                    <p className="text-[10px] sm:text-xs text-slate-500">{testimonial.location}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-10 sm:py-16 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-6 sm:mb-12">
            <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-emerald-500/20 rounded-full border border-emerald-500/30 mb-3 sm:mb-4">
              <TrendingUp className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-400" />
              <span className="text-xs sm:text-sm font-medium text-emerald-400">How It Works</span>
            </div>
            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-3 sm:mb-4 text-white">
              AI + Real-Time Data
            </h2>
            <p className="text-sm sm:text-lg text-slate-400 max-w-3xl mx-auto px-2">
              <strong className="text-white">AI prediction models</strong> + <strong className="text-white">live FPL API data</strong> = insights no spreadsheet can give.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-6">
            <div className="bg-slate-800/50 rounded-xl sm:rounded-2xl p-4 sm:p-6 border border-slate-700">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-cyan-500/20 flex items-center justify-center mb-3 sm:mb-4">
                <Target className="w-5 h-5 sm:w-6 sm:h-6 text-cyan-400" />
              </div>
              <h4 className="font-semibold text-white mb-1.5 sm:mb-2 text-base sm:text-lg">AI Predictions</h4>
              <p className="text-slate-400 text-xs sm:text-sm">
                Models predict points and playing time for every player, every gameweek.
              </p>
            </div>

            <div className="bg-slate-800/50 rounded-xl sm:rounded-2xl p-4 sm:p-6 border border-slate-700">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-emerald-500/20 flex items-center justify-center mb-3 sm:mb-4">
                <Brain className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-400" />
              </div>
              <h4 className="font-semibold text-white mb-1.5 sm:mb-2 text-base sm:text-lg">SmartPlay Scores</h4>
              <p className="text-slate-400 text-xs sm:text-sm">
                Position-weighted rankings combining form, fixtures, xG, and ownership.
              </p>
            </div>

            <div className="bg-slate-800/50 rounded-xl sm:rounded-2xl p-4 sm:p-6 border border-slate-700">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-amber-500/20 flex items-center justify-center mb-3 sm:mb-4">
                <Eye className="w-5 h-5 sm:w-6 sm:h-6 text-amber-400" />
              </div>
              <h4 className="font-semibold text-white mb-1.5 sm:mb-2 text-base sm:text-lg">Real-Time Analysis</h4>
              <p className="text-slate-400 text-xs sm:text-sm">
                Live FPL API powers crowd insights, transfer trends, and ownership alerts.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Knowledge Graph Section */}
      <section className="py-12 sm:py-20 bg-gradient-to-br from-violet-950 via-purple-900 to-indigo-950 relative overflow-hidden">
        {/* Animated graph lines background - hidden on mobile */}
        <div className="hidden sm:block absolute inset-0 opacity-10">
          <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="graph-pattern" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
                <circle cx="50" cy="50" r="2" fill="white" />
                <line x1="50" y1="50" x2="100" y2="0" stroke="white" strokeWidth="0.5" />
                <line x1="50" y1="50" x2="100" y2="100" stroke="white" strokeWidth="0.5" />
                <line x1="50" y1="50" x2="0" y2="50" stroke="white" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#graph-pattern)" />
          </svg>
        </div>

        {/* Glowing orbs - hidden on mobile */}
        <div className="hidden sm:block absolute top-20 left-1/4 w-64 h-64 bg-violet-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="hidden sm:block absolute bottom-20 right-1/4 w-64 h-64 bg-fuchsia-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
        <div className="hidden sm:block absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-6 sm:mb-12">
            <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-violet-500/20 rounded-full border border-violet-400/30 mb-3 sm:mb-4">
              <Network className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-violet-300" />
              <span className="text-xs sm:text-sm font-semibold text-violet-300">Advanced Architecture</span>
            </div>
            <h2 className="text-2xl sm:text-3xl md:text-5xl font-bold text-white mb-3 sm:mb-4">
              Powered by{" "}
              <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-pink-400 bg-clip-text text-transparent">
                Knowledge Graphs
              </span>
            </h2>
            <p className="text-sm sm:text-lg text-violet-200/80 max-w-3xl mx-auto px-2">
              The same tech that powers Google Search and Amazon — now applied to FPL.
            </p>
          </div>

          {/* Interactive Graph Visualization */}
          <div className="relative mb-6 sm:mb-12">
            <div className="bg-gradient-to-br from-slate-900/80 to-slate-800/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl border border-violet-500/20 p-4 sm:p-8 shadow-2xl shadow-violet-500/10">
              {/* Central visual */}
              <div className="flex flex-col lg:flex-row items-center gap-4 sm:gap-8">
                {/* Graph visualization - hidden on very small screens */}
                <div className="flex-1 relative h-48 sm:h-64 lg:h-80 hidden sm:block">
                  {/* Nodes */}
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/50 z-10">
                    <span className="text-white font-bold text-sm">Salah</span>
                  </div>

                  {/* Connected nodes */}
                  <div className="absolute top-4 left-1/2 -translate-x-1/2 w-14 h-14 rounded-full bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center shadow-md animate-pulse">
                    <span className="text-white text-xs font-semibold">LIV</span>
                  </div>
                  <div className="absolute bottom-4 left-1/4 w-14 h-14 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md">
                    <span className="text-white text-xs font-semibold">FWD</span>
                  </div>
                  <div className="absolute bottom-4 right-1/4 w-14 h-14 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-md">
                    <span className="text-white text-xs font-semibold">8.2pts</span>
                  </div>
                  <div className="absolute top-1/3 left-8 w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md">
                    <span className="text-white text-[10px] font-semibold">vs EVE</span>
                  </div>
                  <div className="absolute top-1/3 right-8 w-12 h-12 rounded-full bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center shadow-md">
                    <span className="text-white text-[10px] font-semibold">30%</span>
                  </div>
                  <div className="absolute bottom-1/4 left-1/2 translate-x-8 w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-md">
                    <span className="text-white text-[10px] font-semibold">xG 0.8</span>
                  </div>

                  {/* Connection lines */}
                  <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 5 }}>
                    <line x1="50%" y1="50%" x2="50%" y2="15%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <line x1="50%" y1="50%" x2="25%" y2="85%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <line x1="50%" y1="50%" x2="75%" y2="85%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <line x1="50%" y1="50%" x2="12%" y2="35%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <line x1="50%" y1="50%" x2="88%" y2="35%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <line x1="50%" y1="50%" x2="65%" y2="75%" stroke="url(#line-gradient)" strokeWidth="2" strokeDasharray="4,4">
                      <animate attributeName="stroke-dashoffset" from="0" to="8" dur="1s" repeatCount="indefinite" />
                    </line>
                    <defs>
                      <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.3" />
                        <stop offset="50%" stopColor="#f472b6" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.3" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>

                {/* Description */}
                <div className="flex-1 text-center lg:text-left">
                  <h3 className="text-xl sm:text-2xl font-bold text-white mb-2 sm:mb-4">
                    Every Entity. Every Relationship. Connected.
                  </h3>
                  <p className="text-violet-200/70 mb-4 sm:mb-6 leading-relaxed text-sm sm:text-base">
                    Our Knowledge Graph represents FPL as a <strong className="text-white">web of interconnected entities</strong> — players, teams, fixtures, stats — all linked through meaningful relationships.
                  </p>
                  <div className="flex flex-wrap gap-2 sm:gap-3 justify-center lg:justify-start">
                    <span className="px-2 sm:px-3 py-1 sm:py-1.5 bg-violet-500/20 border border-violet-400/30 rounded-full text-xs sm:text-sm text-violet-300">
                      750+ Players
                    </span>
                    <span className="px-2 sm:px-3 py-1 sm:py-1.5 bg-fuchsia-500/20 border border-fuchsia-400/30 rounded-full text-xs sm:text-sm text-fuchsia-300">
                      10,000+ Links
                    </span>
                    <span className="px-2 sm:px-3 py-1 sm:py-1.5 bg-pink-500/20 border border-pink-400/30 rounded-full text-xs sm:text-sm text-pink-300">
                      Real-Time
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Why Knowledge Graphs */}
          <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
            {[
              {
                icon: GitBranch,
                title: "Semantic Reasoning",
                desc: "Infer hidden patterns from multiple signals",
                gradient: "from-violet-500 to-purple-600",
              },
              {
                icon: Shield,
                title: "Data Validation",
                desc: "Automated quality checks on all data",
                gradient: "from-fuchsia-500 to-pink-600",
              },
              {
                icon: Layers,
                title: "Ontology-Driven",
                desc: "Player archetypes and classifications",
                gradient: "from-indigo-500 to-violet-600",
              },
              {
                icon: Cpu,
                title: "ML Integration",
                desc: "Graph embeddings for richer predictions",
                gradient: "from-cyan-500 to-blue-600",
              },
            ].map((item, i) => (
              <div key={i} className="bg-slate-800/50 backdrop-blur rounded-xl sm:rounded-2xl p-3 sm:p-5 border border-slate-700/50 hover:border-violet-500/50 transition-all group">
                <div className={`w-9 h-9 sm:w-12 sm:h-12 rounded-lg sm:rounded-xl bg-gradient-to-br ${item.gradient} flex items-center justify-center mb-2 sm:mb-4 shadow-lg group-hover:scale-110 transition-transform`}>
                  <item.icon className="w-4 h-4 sm:w-6 sm:h-6 text-white" />
                </div>
                <h4 className="font-bold text-white mb-1 sm:mb-2 text-sm sm:text-base">{item.title}</h4>
                <p className="text-[10px] sm:text-sm text-slate-400 leading-tight sm:leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>

          {/* Bottom note */}
          <p className="text-center text-violet-300/60 mt-6 sm:mt-10 text-xs sm:text-sm px-2">
            Built with <strong className="text-violet-300">RDFLib</strong> and <strong className="text-violet-300">OWL</strong> — same tech used by Google, NASA, BBC.
          </p>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-10 sm:py-16 bg-gradient-to-br from-emerald-600 via-teal-600 to-emerald-700">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
          <Trophy className="w-10 h-10 sm:w-12 sm:h-12 text-white/80 mx-auto mb-3 sm:mb-4" />
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white mb-2 sm:mb-3">
            Ready to Stop Guessing?
          </h2>
          <p className="text-emerald-100/80 mb-6 sm:mb-8 text-sm sm:text-lg">
            Join FPL managers who make better decisions with less research.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4">
            <Link href="/my-team" className="w-full sm:w-auto px-5 sm:px-6 py-3 bg-white text-emerald-700 font-bold rounded-xl hover:bg-emerald-50 transition-all shadow-lg flex items-center justify-center gap-2 text-sm sm:text-base">
              <Zap className="w-4 h-4 sm:w-5 sm:h-5" />
              Analyse My Team
            </Link>
            <Link href="/build" className="w-full sm:w-auto px-5 sm:px-6 py-3 bg-white/10 text-white font-semibold rounded-xl hover:bg-white/20 transition-all border border-white/20 flex items-center justify-center gap-2 text-sm sm:text-base">
              <Wand2 className="w-4 h-4 sm:w-5 sm:h-5" />
              Build a Squad
            </Link>
          </div>

          <div className="flex items-center justify-center gap-3 sm:gap-4 mt-4 sm:mt-6 text-xs sm:text-sm text-emerald-100/60">
            <span className="flex items-center gap-1"><Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> Free</span>
            <span className="flex items-center gap-1"><Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> No signup</span>
            <span className="flex items-center gap-1"><Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> Instant</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-white py-8 sm:py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8 mb-6 sm:mb-8">
            {/* Brand */}
            <div className="col-span-2 sm:col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                  <Brain className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <span className="text-lg sm:text-xl font-bold">Smart<span className="text-emerald-400">Play</span></span>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <GraduationCap className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#FDB515]" />
                <span className="text-xs sm:text-sm font-medium">UC Berkeley</span>
              </div>
              <p className="text-slate-500 text-[10px] sm:text-xs">AI-powered FPL analysis.</p>
            </div>

            {/* Get Started */}
            <div>
              <h4 className="font-semibold text-white mb-3 sm:mb-4 text-sm sm:text-base">Get Started</h4>
              <div className="space-y-1.5 sm:space-y-2 text-xs sm:text-sm text-slate-400">
                <Link href="/my-team" className="block hover:text-emerald-400 transition-colors">Analyse Team</Link>
                <Link href="/build" className="block hover:text-emerald-400 transition-colors">Build Squad</Link>
                <Link href="/players" className="block hover:text-emerald-400 transition-colors">Players</Link>
              </div>
            </div>

            {/* Learn More */}
            <div>
              <h4 className="font-semibold text-white mb-3 sm:mb-4 text-sm sm:text-base">Learn More</h4>
              <div className="space-y-1.5 sm:space-y-2 text-xs sm:text-sm text-slate-400">
                <Link href="/model" className="block hover:text-emerald-400 transition-colors">AI Model</Link>
                <span className="block text-slate-500">SmartPlay Scores</span>
              </div>
            </div>

            {/* Connect */}
            <div className="hidden sm:block">
              <h4 className="font-semibold text-white mb-3 sm:mb-4 text-sm sm:text-base">Connect</h4>
              <div className="space-y-1.5 sm:space-y-2 text-xs sm:text-sm text-slate-400">
                <a
                  href="https://github.com/qazybekb/SmartPlayFPLProject"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 hover:text-emerald-400 transition-colors"
                >
                  <Github className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  GitHub
                </a>
                <a
                  href="https://www.linkedin.com/in/qazybek-beken/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 hover:text-emerald-400 transition-colors"
                >
                  <Linkedin className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  LinkedIn
                </a>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="pt-4 sm:pt-6 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4 text-[10px] sm:text-sm text-slate-500">
            <p className="text-center sm:text-left">© 2025 SmartPlay. Not affiliated with FPL.</p>
            <div className="flex items-center gap-3 sm:gap-4">
              <span>Made with 🧠 in Berkeley, CA</span>
              {/* Mobile social links */}
              <div className="flex sm:hidden items-center gap-3">
                <a href="https://github.com/qazybekb/SmartPlayFPLProject" target="_blank" rel="noopener noreferrer">
                  <Github className="w-4 h-4 text-slate-400 hover:text-emerald-400" />
                </a>
                <a href="https://www.linkedin.com/in/qazybek-beken/" target="_blank" rel="noopener noreferrer">
                  <Linkedin className="w-4 h-4 text-slate-400 hover:text-emerald-400" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
