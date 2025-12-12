"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  ArrowLeft,
  RefreshCw,
  Check,
  X,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  ArrowLeftRight,
  Crown,
  Shield,
  Code,
  Loader2,
  Users,
  Gem,
  Coins,
  Flame,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Zap,
  Database,
  Copy,
  CheckCircle,
  Repeat,
  GitBranch,
  ExternalLink,
  Award,
  HelpCircle,
  BarChart3,
  Brain,
} from "lucide-react";
import { MLPlayerScore, getPlayerMLScore, getPredictorStatus, calculatePredictorScores, getAllMLScores } from "@/lib/api";
import PitchVisualization from "@/components/PitchVisualization";
import Footer from "@/components/Footer";
import {
  trackEvent,
  trackSquadBuilder,
  trackGoalCompletion,
  trackFunnelStep,
  trackApiPerformance,
  trackError,
} from "@/lib/analytics";

// Dynamic import for force graph
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500"></div>
    </div>
  ),
});

// Team short code to full name mapping
const TEAM_FULL_NAMES: Record<string, string> = {
  ARS: "Arsenal",
  AVL: "Aston Villa",
  BOU: "Bournemouth",
  BRE: "Brentford",
  BHA: "Brighton & Hove Albion",
  CHE: "Chelsea",
  CRY: "Crystal Palace",
  EVE: "Everton",
  FUL: "Fulham",
  IPS: "Ipswich Town",
  LEI: "Leicester City",
  LIV: "Liverpool",
  MCI: "Manchester City",
  MUN: "Manchester United",
  NEW: "Newcastle United",
  NFO: "Nottingham Forest",
  SOU: "Southampton",
  TOT: "Tottenham Hotspur",
  WHU: "West Ham United",
  WOL: "Wolverhampton Wanderers",
};

// Types
interface SelectionTrace {
  strategy_score: number;
  rank_in_position: number;
  total_in_position: number;
  score_breakdown: Record<string, number | string>;
  tag_bonuses: Record<string, number>;
  tag_penalties: Record<string, number>;
  alternatives: { name: string; score: number; reason: string; price: number }[];
}

interface InferenceStep {
  data_field: string;
  data_value: string;
  inferred_class: string;
  rule: string;
  contributed_to: string;
}

interface Player {
  id: number;
  web_name: string;
  full_name: string;
  position: string;
  team_id: number;
  team_short: string;
  price: number;
  form: number;
  ownership: number;
  total_points: number;
  points_per_million: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
  smart_tags: string[];
  selection_reason: string;
  bench_order: number;
  smartplay_score?: number;
  fixture_score?: number;
  nailedness_score?: number;
  selection_trace?: SelectionTrace;
  inference_chain?: InferenceStep[];
}

interface Constraint {
  name: string;
  passed: boolean;
  message: string;
  severity: string;
  value?: string;
}

interface Validation {
  passed: boolean;
  hard_constraints: Constraint[];
  soft_constraints: Constraint[];
  error_count: number;
  warning_count: number;
}

interface StrategyAnalysis {
  description: string;
  metrics: Record<string, any>;
  strengths: string[];
  weaknesses: string[];
}

interface FormationOption {
  formation: string;
  expected_points: number;
  total_form: number;
  is_selected: boolean;
  starters: string[];
  benched: string[];
  reasoning: string;
  points_breakdown: Record<string, number>;
}

interface FormationAnalysis {
  selected_formation: string;
  options: FormationOption[];
  selection_reason: string;
  expected_points_formula: string;
}

interface BuiltSquad {
  players: Player[];
  formation: string;
  total_cost: number;
  in_the_bank: number;
  validation: Validation;
  strategy_id: string;
  strategy_name: string;
  strategy_analysis: StrategyAnalysis;
  formation_analysis: FormationAnalysis;
  sparql_queries: string[];
}

interface StrategyInfo {
  id: string;
  name: string;
  icon: string;
  tagline: string;
  description: string;
  risk_level: string;
}

interface SwapCandidate {
  id: number;
  web_name: string;
  full_name: string;
  position: string;
  team_short: string;
  price: number;
  form: number;
  ownership: number;
  total_points: number;
  smart_tags: string[];
  price_diff: number;
  why_recommended: string;
  smartplay_score?: number;
}

// Strategy themes
const STRATEGY_THEMES: Record<string, {
  gradient: string;
  bgGradient: string;
  accentColor: string;
  lightBg: string;
  icon: string;
  headerBg: string;
}> = {
  template: {
    gradient: "from-emerald-500 to-teal-600",
    bgGradient: "from-emerald-50 via-white to-teal-50",
    accentColor: "emerald",
    lightBg: "bg-emerald-50",
    icon: "👥",
    headerBg: "from-emerald-600 via-emerald-700 to-teal-700",
  },
  premium: {
    gradient: "from-violet-500 to-purple-600",
    bgGradient: "from-violet-50 via-white to-purple-50",
    accentColor: "violet",
    lightBg: "bg-violet-50",
    icon: "💎",
    headerBg: "from-violet-600 via-violet-700 to-purple-700",
  },
  value: {
    gradient: "from-amber-500 to-orange-600",
    bgGradient: "from-amber-50 via-white to-orange-50",
    accentColor: "amber",
    lightBg: "bg-amber-50",
    icon: "💰",
    headerBg: "from-amber-600 via-amber-700 to-orange-700",
  },
  form: {
    gradient: "from-orange-500 to-red-500",
    bgGradient: "from-orange-50 via-white to-red-50",
    accentColor: "orange",
    lightBg: "bg-orange-50",
    icon: "🔥",
    headerBg: "from-orange-600 via-red-600 to-red-700",
  },
  balanced: {
    gradient: "from-indigo-500 to-blue-600",
    bgGradient: "from-indigo-50 via-white to-blue-50",
    accentColor: "indigo",
    lightBg: "bg-indigo-50",
    icon: "⚖️",
    headerBg: "from-indigo-600 via-indigo-700 to-blue-700",
  },
  smartplay: {
    gradient: "from-cyan-500 to-blue-600",
    bgGradient: "from-cyan-50 via-white to-blue-50",
    accentColor: "cyan",
    lightBg: "bg-cyan-50",
    icon: "🤖",
    headerBg: "from-cyan-600 via-cyan-700 to-blue-700",
  },
};

// Position colors
const POSITION_COLORS: Record<string, { bg: string; text: string; gradient: string }> = {
  GKP: { bg: "bg-amber-100", text: "text-amber-700", gradient: "from-amber-400 to-yellow-500" },
  DEF: { bg: "bg-emerald-100", text: "text-emerald-700", gradient: "from-emerald-400 to-green-500" },
  MID: { bg: "bg-blue-100", text: "text-blue-700", gradient: "from-blue-400 to-indigo-500" },
  FWD: { bg: "bg-rose-100", text: "text-rose-700", gradient: "from-rose-400 to-red-500" },
};

// Smart Tag colors (aligned with SmartPlay scoring system)
const TAG_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  CaptainCandidate: { bg: "bg-amber-100", text: "text-amber-800", icon: "👑" },
  TopPlayer: { bg: "bg-emerald-100", text: "text-emerald-800", icon: "⭐" },
  DifferentialPick: { bg: "bg-violet-100", text: "text-violet-800", icon: "💎" },
  ValuePick: { bg: "bg-green-100", text: "text-green-800", icon: "💰" },
  Premium: { bg: "bg-purple-100", text: "text-purple-800", icon: "💸" },
  FormPlayer: { bg: "bg-orange-100", text: "text-orange-800", icon: "🔥" },
  FixtureFriendly: { bg: "bg-cyan-100", text: "text-cyan-800", icon: "📅" },
  NailedOn: { bg: "bg-blue-100", text: "text-blue-800", icon: "🔒" },
  RotationRisk: { bg: "bg-amber-100", text: "text-amber-800", icon: "⚠️" },
  InjuryConcern: { bg: "bg-red-100", text: "text-red-800", icon: "🏥" },
};

// Available formations
const FORMATIONS = ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"];

export default function StrategySquadPage() {
  const params = useParams();
  const router = useRouter();
  const strategyId = params.strategy as string;
  
  const [squad, setSquad] = useState<BuiltSquad | null>(null);
  const [strategyInfo, setStrategyInfo] = useState<StrategyInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const [showSparql, setShowSparql] = useState(false);
  const [showKgQuery, setShowKgQuery] = useState(false);
  const [copiedSparql, setCopiedSparql] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  
  // New states for enhanced features
  const [showSwapModal, setShowSwapModal] = useState(false);
  const [swapCandidates, setSwapCandidates] = useState<SwapCandidate[]>([]);
  const [swapLoading, setSwapLoading] = useState(false);
  const [playerToSwap, setPlayerToSwap] = useState<Player | null>(null);
  const [activeCardTab, setActiveCardTab] = useState<"why" | "alternatives" | "health" | "wiki" | "more">("why");
  const [selectedSmartTag, setSelectedSmartTag] = useState<string | null>(null);
  const [playerExplanation, setPlayerExplanation] = useState<any>(null);
  const [similarPlayers, setSimilarPlayers] = useState<any>(null);
  const [playerNeighborhood, setPlayerNeighborhood] = useState<any>(null);
  const [playerWikidata, setPlayerWikidata] = useState<any>(null);
  const [playerInjuryAnalysis, setPlayerInjuryAnalysis] = useState<any>(null);
  const [playerProvenance, setPlayerProvenance] = useState<any>(null);
  const [playerMLScore, setPlayerMLScore] = useState<MLPlayerScore | null>(null);
  const [mlScoreLoading, setMlScoreLoading] = useState(false);
  const [mlScoreError, setMlScoreError] = useState<string | null>(null);
  const [cardDataLoading, setCardDataLoading] = useState(false);
  const [showFormationPicker, setShowFormationPicker] = useState(false);
  const [allMLScores, setAllMLScores] = useState<Record<number, MLPlayerScore>>({});
  const [mlScoresLoaded, setMlScoresLoaded] = useState(false);

  const theme = STRATEGY_THEMES[strategyId] || STRATEGY_THEMES.template;

  useEffect(() => {
    buildSquad();
    fetchStrategyInfo();
    fetchAllMLScores();
  }, [strategyId]);

  // Fetch all ML scores for hover display
  const fetchAllMLScores = async () => {
    try {
      const scores = await getAllMLScores(759); // Get all players
      const scoresMap: Record<number, MLPlayerScore> = {};
      scores.forEach(score => {
        scoresMap[score.player_id] = score;
      });
      setAllMLScores(scoresMap);
      setMlScoresLoaded(true);
    } catch (err) {
      console.error("Error fetching all ML scores:", err);
      // Silently fail - hover will just not show ML scores
    }
  };

  // Fetch player card data when player is selected
  useEffect(() => {
    if (selectedPlayer) {
      fetchPlayerCardData(selectedPlayer.id, selectedPlayer.full_name);
      fetchPlayerMLScore(selectedPlayer.id);
    } else {
      setPlayerExplanation(null);
      setSimilarPlayers(null);
      setPlayerNeighborhood(null);
      setPlayerWikidata(null);
      setPlayerInjuryAnalysis(null);
      setPlayerProvenance(null);
      setPlayerMLScore(null);
      setMlScoreError(null);
    }
  }, [selectedPlayer]);

  // Fetch ML score for a player
  const fetchPlayerMLScore = async (playerId: number) => {
    setMlScoreLoading(true);
    setMlScoreError(null);
    try {
      const mlScore = await getPlayerMLScore(playerId);
      setPlayerMLScore(mlScore);
    } catch (err: any) {
      console.error("Error fetching ML score:", err);
      setMlScoreError(err.message || "Failed to fetch ML score");
      setPlayerMLScore(null);
    } finally {
      setMlScoreLoading(false);
    }
  };

  const fetchPlayerCardData = async (playerId: number, fullName: string) => {
    setCardDataLoading(true);
    try {
      const [explainRes, similarRes, neighborhoodRes, wikiRes, injuryRes, provenanceRes] = await Promise.all([
        fetch(`/api/kg/player/${playerId}/explain`),
        fetch(`/api/kg/player/${playerId}/similar`),
        fetch(`/api/kg/player/${playerId}/neighborhood`),
        fetch(`/api/kg/player/${playerId}/wikidata`),
        fetch(`/api/kg/player/${playerId}/injury-analysis`),
        fetch(`/api/kg/player/${playerId}/provenance`),
      ]);
      
      if (explainRes.ok) setPlayerExplanation(await explainRes.json());
      if (similarRes.ok) setSimilarPlayers(await similarRes.json());
      if (neighborhoodRes.ok) setPlayerNeighborhood(await neighborhoodRes.json());
      if (wikiRes.ok) setPlayerWikidata(await wikiRes.json());
      if (injuryRes.ok) setPlayerInjuryAnalysis(await injuryRes.json());
      if (provenanceRes.ok) setPlayerProvenance(await provenanceRes.json());
    } catch (err) {
      console.error("Error fetching player card data:", err);
    } finally {
      setCardDataLoading(false);
    }
  };

  const fetchStrategyInfo = async () => {
    try {
      const res = await fetch(`/api/build/strategies/${strategyId}`);
      if (res.ok) {
        const data = await res.json();
        setStrategyInfo(data);
      }
    } catch (err) {
      console.error("Error fetching strategy info:", err);
    }
  };

  const buildSquad = async () => {
    setLoading(true);
    const startTime = Date.now();
    trackSquadBuilder('generate', { strategy_id: strategyId });

    try {
      const res = await fetch(`/api/build/${strategyId}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSquad(data);

        const loadTimeMs = Date.now() - startTime;
        trackApiPerformance(`/api/build/${strategyId}`, loadTimeMs, true);
        trackSquadBuilder('complete', {
          strategy_id: strategyId,
          strategy_name: data.strategy_name,
          formation: data.formation,
          total_cost: data.total_cost,
          in_the_bank: data.in_the_bank,
          validation_passed: data.validation?.passed,
          load_time_ms: loadTimeMs,
        });
        trackGoalCompletion('squad_built', {
          strategy_id: strategyId,
          formation: data.formation,
          total_cost: data.total_cost,
        });
        trackFunnelStep('squad_builder', 3, 'squad_generated', true);
      } else {
        const errorText = await res.text();
        console.error("Error building squad:", errorText);
        trackError('squad_build_failed', errorText, strategyId);
        trackApiPerformance(`/api/build/${strategyId}`, Date.now() - startTime, false);
      }
    } catch (err: any) {
      console.error("Error building squad:", err);
      trackError('squad_build_error', err.message || 'Unknown error', strategyId);
    } finally {
      setLoading(false);
    }
  };

  const rebuildSquad = async () => {
    setRebuilding(true);
    trackEvent({
      name: 'squad_rebuild',
      properties: {
        strategy_id: strategyId,
        previous_formation: squad?.formation,
      },
    });
    await buildSquad();
    setRebuilding(false);
  };

  const copySparql = () => {
    if (squad?.sparql_queries?.[0]) {
      navigator.clipboard.writeText(squad.sparql_queries[0]);
      setCopiedSparql(true);
      setTimeout(() => setCopiedSparql(false), 2000);
    }
  };

  // Fetch swap candidates for a player using SmartPlay scores
  const fetchSwapCandidates = async (player: Player) => {
    setSwapLoading(true);
    setPlayerToSwap(player);
    setShowSwapModal(true);
    trackEvent({
      name: 'squad_swap_initiated',
      properties: {
        player_id: player.id,
        player_name: player.web_name,
        position: player.position,
        price: player.price,
        strategy_id: strategyId,
      },
    });

    try {
      // Get IDs of players already in squad to exclude them
      const squadPlayerIds = new Set(squad?.players.map(p => p.id) || []);

      // Use the new predictor alternatives endpoint for SmartPlay-based suggestions
      // Request more than needed since we'll filter out squad players
      const res = await fetch(`/api/predictor/player/${player.id}/alternatives?limit=10`);
      if (res.ok) {
        const data = await res.json();
        // Transform alternatives into swap candidates, excluding players already in squad
        const candidates: SwapCandidate[] = (data.alternatives || [])
          .filter((p: any) => !squadPlayerIds.has(p.player_id))
          .slice(0, 5)  // Take top 5 after filtering
          .map((p: any) => ({
            id: p.player_id,
            web_name: p.name,
            full_name: p.full_name,
            position: p.position,
            team_short: p.team,
            price: p.price,
            form: p.form,
            ownership: p.ownership,
            total_points: p.total_points,
            smart_tags: [],
            price_diff: p.price_diff,
            why_recommended: p.why_recommended,
            smartplay_score: p.final_score,
          }));
        setSwapCandidates(candidates);
      }
    } catch (err) {
      console.error("Error fetching swap candidates:", err);
    } finally {
      setSwapLoading(false);
    }
  };

  // Change formation
  const changeFormation = (newFormation: string) => {
    if (!squad) return;
    
    // Parse formation (e.g., "3-4-3" -> DEF: 3, MID: 4, FWD: 3)
    const [defCount, midCount, fwdCount] = newFormation.split("-").map(Number);
    const formationNeeds: Record<string, number> = {
      GKP: 1,
      DEF: defCount,
      MID: midCount,
      FWD: fwdCount,
    };
    
    // Group all players by position
    const playersByPosition: Record<string, Player[]> = {
      GKP: squad.players.filter(p => p.position === "GKP"),
      DEF: squad.players.filter(p => p.position === "DEF"),
      MID: squad.players.filter(p => p.position === "MID"),
      FWD: squad.players.filter(p => p.position === "FWD"),
    };
    
    // Sort each position by form (best first)
    Object.keys(playersByPosition).forEach(pos => {
      playersByPosition[pos].sort((a, b) => b.form - a.form);
    });
    
    // Reassign starters and bench
    const updatedPlayers: Player[] = [];
    let benchOrder = 1;
    
    // For each position, pick the required starters and bench the rest
    (["GKP", "DEF", "MID", "FWD"] as const).forEach(position => {
      const needed = formationNeeds[position];
      const positionPlayers = playersByPosition[position];
      
      positionPlayers.forEach((player, index) => {
        const isStarter = index < needed;
        updatedPlayers.push({
          ...player,
          is_starter: isStarter,
          bench_order: isStarter ? 0 : benchOrder++,
        });
      });
    });
    
    // Keep captain and vice-captain if they're still starters, otherwise reassign
    const newStarters = updatedPlayers.filter(p => p.is_starter);
    const currentCaptain = updatedPlayers.find(p => p.is_captain);
    const currentVC = updatedPlayers.find(p => p.is_vice_captain);
    
    // If captain is benched, pick new captain from starters
    if (currentCaptain && !currentCaptain.is_starter) {
      // Remove captain from old player
      const oldCaptainIdx = updatedPlayers.findIndex(p => p.id === currentCaptain.id);
      if (oldCaptainIdx >= 0) {
        updatedPlayers[oldCaptainIdx] = { ...updatedPlayers[oldCaptainIdx], is_captain: false };
      }
      // Assign to best form starter (non-GKP)
      const bestStarter = newStarters.filter(p => p.position !== "GKP").sort((a, b) => b.form - a.form)[0];
      if (bestStarter) {
        const idx = updatedPlayers.findIndex(p => p.id === bestStarter.id);
        if (idx >= 0) {
          updatedPlayers[idx] = { ...updatedPlayers[idx], is_captain: true };
        }
      }
    }
    
    // If VC is benched, pick new VC from starters
    if (currentVC && !currentVC.is_starter) {
      const oldVCIdx = updatedPlayers.findIndex(p => p.id === currentVC.id);
      if (oldVCIdx >= 0) {
        updatedPlayers[oldVCIdx] = { ...updatedPlayers[oldVCIdx], is_vice_captain: false };
      }
      const captain = updatedPlayers.find(p => p.is_captain);
      const bestStarter = newStarters
        .filter(p => p.position !== "GKP" && p.id !== captain?.id)
        .sort((a, b) => b.form - a.form)[0];
      if (bestStarter) {
        const idx = updatedPlayers.findIndex(p => p.id === bestStarter.id);
        if (idx >= 0) {
          updatedPlayers[idx] = { ...updatedPlayers[idx], is_vice_captain: true };
        }
      }
    }
    
    setSquad({
      ...squad,
      formation: newFormation,
      players: updatedPlayers,
    });
    setShowFormationPicker(false);
  };

  // Execute player swap
  const executeSwap = (newPlayer: SwapCandidate) => {
    if (!squad || !playerToSwap) return;
    
    // Update squad with swapped player
    const updatedPlayers = squad.players.map(p => {
      if (p.id === playerToSwap.id) {
        return {
          ...p,
          id: newPlayer.id,
          web_name: newPlayer.web_name,
          full_name: newPlayer.full_name,
          team_short: newPlayer.team_short,
          price: newPlayer.price,
          form: newPlayer.form,
          ownership: newPlayer.ownership,
          total_points: newPlayer.total_points,
          smart_tags: newPlayer.smart_tags,
          selection_reason: `Swapped from ${playerToSwap.web_name}`,
        };
      }
      return p;
    });
    
    // Recalculate total cost
    const newTotalCost = updatedPlayers.reduce((sum, p) => sum + p.price, 0);
    
    setSquad({
      ...squad,
      players: updatedPlayers,
      total_cost: Math.round(newTotalCost * 10) / 10,
      in_the_bank: Math.round((100 - newTotalCost) * 10) / 10,
    });
    
    setShowSwapModal(false);
    setPlayerToSwap(null);
  };

  // Calculate tag summary with player names
  const getTagSummary = useCallback(() => {
    if (!squad) return [];
    
    const tagData: Record<string, { count: number; players: string[] }> = {};
    squad.players.forEach(p => {
      p.smart_tags.forEach(tag => {
        if (!tagData[tag]) {
          tagData[tag] = { count: 0, players: [] };
        }
        tagData[tag].count += 1;
        tagData[tag].players.push(p.web_name);
      });
    });
    
    return Object.entries(tagData)
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 6)
      .map(([tag, data]) => ({ tag, count: data.count, players: data.players }));
  }, [squad]);

  if (loading) {
    return (
      <div className={`bg-gradient-to-br ${theme.bgGradient} flex items-center justify-center`}>
        <div className="text-center">
          <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${theme.gradient} flex items-center justify-center mx-auto mb-4 animate-pulse`}>
            <span className="text-4xl">{theme.icon}</span>
          </div>
          <p className="text-slate-600 font-medium">Building your squad...</p>
          <p className="text-sm text-slate-500 mt-1">Analyzing SmartPlay scores</p>
        </div>
      </div>
    );
  }

  if (!squad) {
    return (
      <div className="bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">Failed to build squad</h2>
          <p className="text-slate-600 mb-4">Please try again or choose a different strategy.</p>
          <Link href="/build" className="text-emerald-600 hover:underline">
            ← Back to strategies
          </Link>
        </div>
      </div>
    );
  }

  const starters = squad.players.filter(p => p.is_starter);
  const bench = squad.players.filter(p => !p.is_starter).sort((a, b) => a.bench_order - b.bench_order);
  const tagSummary = getTagSummary();

  return (
    <div className={`bg-gradient-to-br ${theme.bgGradient}`}>
      {/* Strategy-Themed Header */}
      <header className={`bg-gradient-to-r ${theme.headerBg} text-white`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link 
                href="/build" 
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
                  <span className="text-3xl">{theme.icon}</span>
                </div>
                <div>
                  <h1 className="text-xl font-bold">{squad.strategy_name}</h1>
                  <p className="text-sm text-white/80">{strategyInfo?.tagline || "KG-Powered Squad"}</p>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={rebuildSquad}
                disabled={rebuilding}
                className="flex items-center gap-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${rebuilding ? "animate-spin" : ""}`} />
                Rebuild
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-xs font-medium text-slate-500 mb-1">Total Cost</p>
            <p className="text-2xl font-bold text-slate-900">£{squad.total_cost}m</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-xs font-medium text-slate-500 mb-1">In The Bank</p>
            <p className={`text-2xl font-bold ${squad.in_the_bank >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              £{squad.in_the_bank}m
            </p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-xs font-medium text-slate-500 mb-1">Formation</p>
            <p className="text-2xl font-bold text-slate-900">{squad.formation}</p>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200">
            <p className="text-xs font-medium text-slate-500 mb-1">Validation</p>
            <div className="flex items-center gap-2">
              {squad.validation.passed ? (
                <>
                  <CheckCircle className="w-6 h-6 text-emerald-500" />
                  <span className="text-lg font-bold text-emerald-600">Passed</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-6 h-6 text-amber-500" />
                  <span className="text-lg font-bold text-amber-600">{squad.validation.error_count} Errors</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Formation Analysis Panel */}
        {squad.formation_analysis && (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-6 overflow-hidden">
            <div className="px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  <h3 className="font-bold text-sm">Best Formations</h3>
                  <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full">SmartPlay Optimized</span>
                </div>
                <div className="group relative">
                  <div className="flex items-center gap-1 cursor-help opacity-80 hover:opacity-100">
                    <HelpCircle className="w-4 h-4" />
                    <span className="text-[10px]">How is this calculated?</span>
                  </div>
                  <div className="absolute right-0 top-full mt-2 w-80 p-4 bg-slate-900 text-white text-xs rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 shadow-xl">
                    <p className="font-bold text-sm mb-2 text-cyan-400">📊 SmartPlay Formation Model</p>
                    <p className="text-slate-300 whitespace-pre-line text-[10px] leading-relaxed">
                      {squad.formation_analysis.expected_points_formula}
                    </p>
                  </div>
                </div>
              </div>
              <p className="text-xs text-white/80 mt-1">Top 3 formations ranked by SmartPlay score</p>
            </div>
            
            <div className="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {squad.formation_analysis.options.slice(0, 3).map((opt, index) => (
                  <div
                    key={opt.formation}
                    onClick={() => changeFormation(opt.formation)}
                    className={`relative p-3 rounded-xl border-2 transition-all cursor-pointer ${
                      squad.formation === opt.formation
                        ? "border-emerald-500 bg-emerald-50 ring-2 ring-emerald-200"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-slate-100"
                    }`}
                  >
                    {/* Rank badge */}
                    <div className={`absolute -top-2 -left-2 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      index === 0 ? "bg-emerald-500 text-white" :
                      index === 1 ? "bg-slate-400 text-white" :
                      "bg-amber-600 text-white"
                    }`}>
                      {index === 0 ? "1st" : index === 1 ? "2nd" : "3rd"}
                    </div>

                    {/* Selected badge */}
                    {index === 0 && (
                      <div className="absolute -top-2 -right-2 px-2 py-0.5 bg-emerald-500 text-white text-[10px] font-bold rounded-full">
                        BEST
                      </div>
                    )}

                    {/* Formation name and expected points */}
                    <div className="flex items-center justify-between mb-2 mt-1">
                      <span className={`text-lg font-bold ${index === 0 ? "text-emerald-700" : "text-slate-700"}`}>
                        {opt.formation}
                      </span>
                      <div className="text-right">
                        <span className={`text-lg font-bold ${index === 0 ? "text-emerald-600" : "text-slate-600"}`}>
                          {opt.expected_points.toFixed(1)}
                        </span>
                        <span className="text-[10px] text-slate-500 block">SmartPlay</span>
                      </div>
                    </div>
                    
                    {/* Points breakdown by position */}
                    <div className="flex gap-1 mb-2">
                      {Object.entries(opt.points_breakdown).map(([pos, pts]) => (
                        <div
                          key={pos}
                          className={`flex-1 text-center p-1 rounded text-[9px] ${
                            pos === "GKP" ? "bg-amber-100 text-amber-700" :
                            pos === "DEF" ? "bg-emerald-100 text-emerald-700" :
                            pos === "MID" ? "bg-blue-100 text-blue-700" :
                            pos === "FWD" ? "bg-rose-100 text-rose-700" :
                            pos === "👑" ? "bg-purple-100 text-purple-700" :
                            "bg-slate-100 text-slate-700"
                          }`}
                        >
                          <span className="font-bold">{pos}</span>
                          <span className="block font-mono">{pts.toFixed(1)}</span>
                        </div>
                      ))}
                    </div>
                    
                    {/* Reasoning */}
                    <p className="text-[10px] text-slate-500 line-clamp-2">{opt.reasoning}</p>
                    
                    {/* Benched players */}
                    {opt.benched.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-200">
                        <p className="text-[9px] text-slate-400">
                          Bench: <span className="text-slate-500">{opt.benched.join(", ")}</span>
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Chip Analysis Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-6 overflow-hidden">
          <div className="px-4 py-3 bg-gradient-to-r from-purple-500 to-indigo-600 text-white">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4" />
              <h3 className="font-bold text-sm">Chip Analysis</h3>
              <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full">This Gameweek</span>
            </div>
            <p className="text-xs text-white/80 mt-1">When to use your chips with this squad</p>
          </div>

          <div className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Triple Captain Analysis */}
              {(() => {
                const captain = squad.players.find(p => p.is_captain);
                const captainScore = captain ? (captain.smartplay_score || 0) : 0;
                const captainFixture = captain?.fixture_score || 0;
                const tcRating = captainScore >= 8 && captainFixture >= 7 ? "excellent" :
                                 captainScore >= 7 && captainFixture >= 6 ? "good" : "wait";
                return (
                  <div className={`p-3 rounded-xl border-2 ${
                    tcRating === "excellent" ? "border-emerald-300 bg-emerald-50" :
                    tcRating === "good" ? "border-amber-300 bg-amber-50" :
                    "border-slate-200 bg-slate-50"
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">👑</span>
                        <span className="font-bold text-slate-800">Triple Captain</span>
                      </div>
                      <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                        tcRating === "excellent" ? "bg-emerald-500 text-white" :
                        tcRating === "good" ? "bg-amber-500 text-white" :
                        "bg-slate-300 text-slate-700"
                      }`}>
                        {tcRating === "excellent" ? "Use Now!" : tcRating === "good" ? "Consider" : "Wait"}
                      </span>
                    </div>
                    {captain && (
                      <div className="space-y-1">
                        <p className="text-sm text-slate-700">
                          <span className="font-semibold">{captain.web_name}</span>
                          <span className="text-slate-500"> (C)</span>
                        </p>
                        <div className="flex gap-2 text-xs">
                          <span className={`px-2 py-0.5 rounded ${captainScore >= 7 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                            SmartPlay: {captainScore.toFixed(1)}
                          </span>
                          <span className={`px-2 py-0.5 rounded ${captainFixture >= 7 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                            Fixture: {captainFixture.toFixed(1)}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-1">
                          {tcRating === "excellent"
                            ? "Premium captain with great fixture - ideal TC week!"
                            : tcRating === "good"
                            ? "Good option but better weeks may come"
                            : "Save TC for a premium with easier fixtures"}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Bench Boost Analysis */}
              {(() => {
                const starters = squad.players.filter(p => p.is_starter);
                const bench = squad.players.filter(p => !p.is_starter);
                const benchTotalScore = bench.reduce((sum, p) => sum + (p.smartplay_score || 0), 0);
                const benchAvgScore = bench.length > 0 ? benchTotalScore / bench.length : 0;
                const benchAvgFixture = bench.length > 0
                  ? bench.reduce((sum, p) => sum + (p.fixture_score || 0), 0) / bench.length
                  : 0;
                const benchHasNailed = bench.filter(p => (p.nailedness_score || 0) >= 7).length;
                const bbRating = benchAvgScore >= 6 && benchAvgFixture >= 6 && benchHasNailed >= 3 ? "excellent" :
                                 benchAvgScore >= 5 && benchHasNailed >= 2 ? "good" : "wait";
                return (
                  <div className={`p-3 rounded-xl border-2 ${
                    bbRating === "excellent" ? "border-emerald-300 bg-emerald-50" :
                    bbRating === "good" ? "border-amber-300 bg-amber-50" :
                    "border-slate-200 bg-slate-50"
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">🪑</span>
                        <span className="font-bold text-slate-800">Bench Boost</span>
                      </div>
                      <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                        bbRating === "excellent" ? "bg-emerald-500 text-white" :
                        bbRating === "good" ? "bg-amber-500 text-white" :
                        "bg-slate-300 text-slate-700"
                      }`}>
                        {bbRating === "excellent" ? "Use Now!" : bbRating === "good" ? "Consider" : "Wait"}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm text-slate-700">
                        <span className="font-semibold">{bench.length} bench players</span>
                      </p>
                      <div className="flex gap-2 text-xs">
                        <span className={`px-2 py-0.5 rounded ${benchAvgScore >= 5.5 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                          Avg Score: {benchAvgScore.toFixed(1)}
                        </span>
                        <span className={`px-2 py-0.5 rounded ${benchHasNailed >= 3 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                          Nailed: {benchHasNailed}/4
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        {bench.map(p => p.web_name).join(", ")}
                      </div>
                      <p className="text-[10px] text-slate-500">
                        {bbRating === "excellent"
                          ? "Strong bench with good fixtures - great BB week!"
                          : bbRating === "good"
                          ? "Decent bench but could be stronger"
                          : "Build a stronger bench before using BB"}
                      </p>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>

        {/* Tag Summary Bar */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-200 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-violet-500" />
              Squad Smart Tags
            </h3>
            <span className="text-xs text-slate-500">
              {squad.players.reduce((sum, p) => sum + p.smart_tags.length, 0)} total tags
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {tagSummary.map(({ tag, count, players }) => {
              const tagStyle = TAG_COLORS[tag] || { bg: "bg-slate-100", text: "text-slate-800", icon: "🏷️" };
              const isSelected = selectedSmartTag === tag;
              return (
                <button
                  key={tag}
                  onClick={() => setSelectedSmartTag(isSelected ? null : tag)}
                  className={`relative flex items-center gap-2 px-3 py-1.5 rounded-full transition-all ${
                    isSelected
                      ? "ring-2 ring-violet-500 ring-offset-2 shadow-md scale-105 " + tagStyle.bg
                      : tagStyle.bg + " hover:ring-2 hover:ring-offset-1 hover:ring-violet-400"
                  }`}
                >
                  <span className="text-sm">{tagStyle.icon}</span>
                  <span className={`text-xs font-medium ${tagStyle.text}`}>{tag}</span>
                  <span className={`text-xs font-bold ${tagStyle.text} bg-white/50 px-1.5 rounded-full`}>
                    {count}
                  </span>
                </button>
              );
            })}
            {tagSummary.length === 0 && (
              <p className="text-xs text-slate-500">No smart tags in this squad</p>
            )}
          </div>

          {/* Players with selected tag */}
          {selectedSmartTag && (
            <div className="mt-4 pt-4 border-t border-slate-200">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <span>{TAG_COLORS[selectedSmartTag]?.icon || "🏷️"}</span>
                  {selectedSmartTag} Players
                </h4>
                <button
                  onClick={() => setSelectedSmartTag(null)}
                  className="text-xs text-slate-500 hover:text-slate-700"
                >
                  Clear
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
                {squad.players
                  .filter(p => p.smart_tags.includes(selectedSmartTag))
                  .map(player => {
                    const posColor = POSITION_COLORS[player.position];
                    return (
                      <button
                        key={player.id}
                        onClick={() => {
                          setSelectedPlayer(player);
                          setActiveCardTab("why");
                        }}
                        className="flex items-center gap-2 p-2 bg-white rounded-lg border border-slate-200 hover:border-violet-300 hover:shadow-sm transition-all text-left"
                      >
                        <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${posColor.gradient} flex items-center justify-center text-white text-xs font-bold`}>
                          {player.web_name.slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-slate-800 truncate">{player.web_name}</p>
                          <p className="text-[10px] text-slate-500">{player.team_short} · £{player.price}m</p>
                        </div>
                      </button>
                    );
                  })}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Pitch Visualization */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className={`px-5 py-4 bg-gradient-to-r ${theme.gradient} text-white`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="w-5 h-5" />
                    <h2 className="font-bold">Your Squad</h2>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs bg-white/20 px-2 py-1 rounded">
                      Click player to view details
                    </span>
                    <span className="text-sm font-medium bg-white/20 px-2 py-1 rounded">
                      {squad.formation}
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="p-6 bg-gradient-to-b from-slate-50 to-white">
                <PitchVisualization
                  players={squad.players}
                  formation={squad.formation}
                  onPlayerClick={(player) => {
                    const fullPlayer = squad.players.find(p => p.id === player.id);
                    setSelectedPlayer(selectedPlayer?.id === player.id ? null : fullPlayer || null);
                    setActiveCardTab("why");
                  }}
                  strategyColor={theme.accentColor}
                  mlScores={allMLScores}
                />
              </div>
            </div>
          </div>

          {/* Right Column - Player Card or Analysis */}
          <div className="space-y-6">
            {/* Player Detail Card (when selected) */}
            {selectedPlayer ? (
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                {/* Player Header */}
                <div className={`px-5 py-4 bg-gradient-to-r ${POSITION_COLORS[selectedPlayer.position].gradient} text-white`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-bold">{selectedPlayer.web_name}</h2>
                        {selectedPlayer.is_captain && <Crown className="w-5 h-5 text-amber-300" />}
                      </div>
                      <p className="text-sm text-white/80">{selectedPlayer.team_short} · {selectedPlayer.position}</p>
                    </div>
                    <button
                      onClick={() => setSelectedPlayer(null)}
                      className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Tab Navigation - Simplified to 4 tabs */}
                <div className="flex border-b border-slate-200 bg-slate-50/50">
                  {[
                    { id: "why", label: "Why", icon: "🎯" },
                    { id: "alternatives", label: "Swap", icon: "🔄" },
                    { id: "health", label: "Health", icon: "🏥" },
                    { id: "wiki", label: "Wiki", icon: "🌐" },
                    { id: "more", label: "More", icon: "📊" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveCardTab(tab.id as any)}
                      className={`flex-1 px-3 py-2.5 text-xs font-medium transition-all ${
                        activeCardTab === tab.id
                          ? "bg-white text-violet-700 border-b-2 border-violet-500"
                          : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
                      }`}
                    >
                      <span className="block text-base mb-0.5">{tab.icon}</span>
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="p-4 max-h-[60vh] overflow-y-auto">
                  {cardDataLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-violet-500" />
                    </div>
                  ) : (
                    <>
                      {/* WHY SELECTED TAB - Consolidated view answering "why this player?" */}
                      {activeCardTab === "why" && (
                        <div className="space-y-4">
                          {/* SmartPlay Score - The main reason (moved to top) */}
                          {playerMLScore && (
                            <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-xl p-4 border border-cyan-200">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <Brain className="w-5 h-5 text-cyan-600" />
                                  <span className="text-sm font-bold text-cyan-800">SmartPlay Score</span>
                                </div>
                                <span className="text-xs px-2 py-1 bg-cyan-200 text-cyan-800 rounded-full font-bold">
                                  Rank #{playerMLScore.rank}
                                </span>
                              </div>

                              {/* Main score with visual indicator */}
                              <div className="flex items-center gap-4 mb-4">
                                <div className="flex items-baseline gap-1">
                                  <span className={`text-4xl font-bold ${
                                    playerMLScore.final_score >= 7 ? "text-emerald-600" :
                                    playerMLScore.final_score >= 5 ? "text-cyan-600" : "text-amber-600"
                                  }`}>
                                    {playerMLScore.final_score.toFixed(1)}
                                  </span>
                                  <span className="text-lg text-cyan-500">/ 10</span>
                                </div>
                                <div className="flex-1 h-3 bg-slate-200 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      playerMLScore.final_score >= 7 ? "bg-emerald-500" :
                                      playerMLScore.final_score >= 5 ? "bg-cyan-500" : "bg-amber-500"
                                    }`}
                                    style={{ width: `${playerMLScore.final_score * 10}%` }}
                                  />
                                </div>
                              </div>

                              {/* Score breakdown - clearer labels */}
                              <div className="grid grid-cols-4 gap-2">
                                <div className="bg-white/60 rounded-lg p-2 text-center">
                                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden mb-1.5">
                                    <div className="h-full bg-violet-500 rounded-full" style={{ width: `${playerMLScore.nailedness_score * 10}%` }} />
                                  </div>
                                  <p className="text-sm font-bold text-violet-700">{playerMLScore.nailedness_score.toFixed(0)}</p>
                                  <p className="text-[8px] text-slate-500">Nailed</p>
                                </div>
                                <div className="bg-white/60 rounded-lg p-2 text-center">
                                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden mb-1.5">
                                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${playerMLScore.form_pts_score * 10}%` }} />
                                  </div>
                                  <p className="text-sm font-bold text-emerald-700">{playerMLScore.form_pts_score.toFixed(0)}</p>
                                  <p className="text-[8px] text-slate-500">Pts Form</p>
                                </div>
                                <div className="bg-white/60 rounded-lg p-2 text-center">
                                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden mb-1.5">
                                    <div className="h-full bg-orange-500 rounded-full" style={{ width: `${playerMLScore.form_xg_score * 10}%` }} />
                                  </div>
                                  <p className="text-sm font-bold text-orange-700">{playerMLScore.form_xg_score.toFixed(0)}</p>
                                  <p className="text-[8px] text-slate-500">xGI</p>
                                </div>
                                <div className="bg-white/60 rounded-lg p-2 text-center">
                                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden mb-1.5">
                                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${playerMLScore.fixture_score * 10}%` }} />
                                  </div>
                                  <p className="text-sm font-bold text-blue-700">{playerMLScore.fixture_score.toFixed(0)}</p>
                                  <p className="text-[8px] text-slate-500">Fixtures</p>
                                </div>
                              </div>

                              {/* Next fixture */}
                              <div className="mt-3 pt-3 border-t border-cyan-200 flex items-center justify-between">
                                <p className="text-xs text-cyan-700">
                                  Next: <span className="font-bold">{playerMLScore.next_opponent}</span> ({playerMLScore.next_home ? "H" : "A"})
                                </p>
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                  playerMLScore.next_fdr <= 2 ? "bg-emerald-100 text-emerald-700" :
                                  playerMLScore.next_fdr <= 3 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                                }`}>
                                  FDR {playerMLScore.next_fdr}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* Player Stats Row - with clear FPL label */}
                          <div className="grid grid-cols-3 gap-2">
                            <div className="bg-slate-50 rounded-lg p-2.5 text-center border border-slate-200">
                              <p className="text-lg font-bold text-slate-900">£{selectedPlayer.price}m</p>
                              <p className="text-[9px] text-slate-500">Price</p>
                            </div>
                            <div className="bg-slate-50 rounded-lg p-2.5 text-center border border-slate-200">
                              <p className={`text-lg font-bold ${selectedPlayer.form >= 6 ? "text-emerald-600" : selectedPlayer.form >= 4 ? "text-amber-600" : "text-slate-600"}`}>
                                {selectedPlayer.form.toFixed(1)}
                              </p>
                              <p className="text-[9px] text-slate-500">FPL Form</p>
                            </div>
                            <div className="bg-slate-50 rounded-lg p-2.5 text-center border border-slate-200">
                              <p className="text-lg font-bold text-slate-900">{selectedPlayer.ownership.toFixed(1)}%</p>
                              <p className="text-[9px] text-slate-500">Ownership</p>
                            </div>
                          </div>

                          {/* Selection Reason */}
                          <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-200">
                            <p className="text-xs font-bold text-emerald-800 mb-1 flex items-center gap-1">
                              <Award className="w-3 h-3" /> Selection Reason
                            </p>
                            <p className="text-sm text-emerald-700">{selectedPlayer.selection_reason}</p>

                            {/* Strategy rank if available */}
                            {selectedPlayer.selection_trace && (
                              <div className="mt-2 pt-2 border-t border-emerald-200 flex items-center gap-3 text-[10px]">
                                <span className="text-emerald-600">
                                  Strategy Score: <span className="font-bold">{selectedPlayer.selection_trace.strategy_score.toFixed(1)}</span>
                                </span>
                                <span className="text-emerald-600">
                                  Rank: <span className="font-bold">#{selectedPlayer.selection_trace.rank_in_position}</span> of {selectedPlayer.selection_trace.total_in_position} {selectedPlayer.position}s
                                </span>
                              </div>
                            )}
                          </div>

                          {/* Smart Tags with explanations */}
                          {selectedPlayer.smart_tags.length > 0 && (
                            <div>
                              <p className="text-xs font-bold text-slate-700 mb-2">Smart Tags</p>
                              <div className="flex flex-wrap gap-1.5">
                                {selectedPlayer.smart_tags.map((tag) => {
                                  const tagStyle = TAG_COLORS[tag] || { bg: "bg-slate-100", text: "text-slate-800", icon: "🏷️" };
                                  return (
                                    <span
                                      key={tag}
                                      className={`text-[10px] px-2 py-1 rounded-full ${tagStyle.bg} ${tagStyle.text} flex items-center gap-1`}
                                    >
                                      <span>{tagStyle.icon}</span>
                                      {tag}
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Find Alternatives Button */}
                          <button
                            onClick={() => {
                              fetchSwapCandidates(selectedPlayer);
                              setActiveCardTab("alternatives");
                            }}
                            className={`w-full py-2.5 bg-gradient-to-r ${theme.gradient} text-white font-medium rounded-lg flex items-center justify-center gap-2 hover:opacity-90 transition-opacity`}
                          >
                            <Repeat className="w-4 h-4" />
                            Find Alternatives
                          </button>
                        </div>
                      )}

                      {/* Alternatives Tab */}
                      {activeCardTab === "alternatives" && (
                        <div className="space-y-3">
                          <p className="text-xs text-slate-600 mb-3">
                            Players similar to {selectedPlayer.web_name}:
                          </p>
                          {similarPlayers?.similar_players?.slice(0, 5).map((p: any, idx: number) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                              onClick={() => fetchSwapCandidates(selectedPlayer)}
                            >
                              <div className="flex items-center gap-3">
                                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${POSITION_COLORS[similarPlayers.position]?.gradient || "from-slate-400 to-slate-500"} flex items-center justify-center`}>
                                  <span className="text-xs font-bold text-white">{similarPlayers.position}</span>
                                </div>
                                <div>
                                  <p className="text-sm font-medium text-slate-900">{p.name}</p>
                                  <p className="text-[10px] text-slate-500">{p.team} · £{p.price}m</p>
                                </div>
                              </div>
                              <div className="text-right">
                                <p className={`text-sm font-bold ${parseFloat(p.form) >= 6 ? "text-emerald-600" : "text-slate-600"}`}>
                                  {parseFloat(p.form).toFixed(1)}
                                </p>
                                <p className="text-[10px] text-slate-500">form</p>
                              </div>
                            </div>
                          ))}
                          {/* Shared tags info */}
                          {similarPlayers?.similar_players?.length > 0 && similarPlayers.player_tags?.length > 0 && (
                            <div className="mt-3 p-2 bg-violet-50 rounded-lg">
                              <p className="text-[10px] font-medium text-violet-700 mb-1">Matching based on:</p>
                              <div className="flex flex-wrap gap-1">
                                {similarPlayers.player_tags.slice(0, 4).map((tag: string) => (
                                  <span key={tag} className="text-[10px] px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full">
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {(!similarPlayers?.similar_players || similarPlayers.similar_players.length === 0) && (
                            <p className="text-sm text-slate-500 text-center py-4">
                              No similar players found.
                            </p>
                          )}
                        </div>
                      )}

                      {/* Health Tab */}
                      {activeCardTab === "health" && (
                        <div className="space-y-3">
                          {!playerInjuryAnalysis ? (
                            <div className="flex items-center justify-center py-8">
                              <Loader2 className="w-5 h-5 animate-spin text-red-500" />
                              <span className="ml-2 text-sm text-slate-500">Analyzing injury data...</span>
                            </div>
                          ) : playerInjuryAnalysis.parsed?.severity === "fit" ? (
                            <div className="p-4 bg-emerald-50 rounded-lg border border-emerald-200 text-center">
                              <span className="text-3xl mb-2 block">✅</span>
                              <p className="text-sm font-medium text-emerald-700">Player is Fit</p>
                              <p className="text-xs text-emerald-600 mt-1">No injury concerns reported</p>
                            </div>
                          ) : (
                            <>
                              {/* Severity Badge */}
                              <div className={`p-3 rounded-lg border ${
                                playerInjuryAnalysis.parsed?.severity === "minor" 
                                  ? "bg-amber-50 border-amber-200" 
                                  : playerInjuryAnalysis.parsed?.severity === "moderate"
                                  ? "bg-orange-50 border-orange-200"
                                  : "bg-red-50 border-red-200"
                              }`}>
                                <div className="flex items-center gap-2 mb-2">
                                  <span className="text-xl">
                                    {playerInjuryAnalysis.parsed?.severity === "minor" ? "⚠️" : 
                                     playerInjuryAnalysis.parsed?.severity === "moderate" ? "🔶" : "🚨"}
                                  </span>
                                  <span className={`text-sm font-bold capitalize ${
                                    playerInjuryAnalysis.parsed?.severity === "minor" ? "text-amber-800" :
                                    playerInjuryAnalysis.parsed?.severity === "moderate" ? "text-orange-800" : "text-red-800"
                                  }`}>
                                    {playerInjuryAnalysis.parsed?.severity || "Unknown"} Concern
                                  </span>
                                </div>
                                {playerInjuryAnalysis.parsed?.injury_type && (
                                  <p className="text-xs text-slate-600">
                                    Type: <span className="font-medium">{playerInjuryAnalysis.parsed.injury_type}</span>
                                  </p>
                                )}
                                {playerInjuryAnalysis.parsed?.expected_return && (
                                  <p className="text-xs text-slate-600 mt-1">
                                    Expected Return: <span className="font-medium">{playerInjuryAnalysis.parsed.expected_return}</span>
                                  </p>
                                )}
                              </div>

                              {/* Raw News */}
                              {playerInjuryAnalysis.news && (
                                <div className="p-3 bg-slate-50 rounded-lg">
                                  <p className="text-[10px] font-semibold text-slate-500 uppercase mb-1">FPL News</p>
                                  <p className="text-xs text-slate-700">{playerInjuryAnalysis.news}</p>
                                </div>
                              )}

                              {/* Chance of Playing */}
                              {(playerInjuryAnalysis.chance_of_playing_this_round !== null || 
                                playerInjuryAnalysis.chance_of_playing_next_round !== null) && (
                                <div className="grid grid-cols-2 gap-2">
                                  <div className="p-2 bg-slate-50 rounded-lg text-center">
                                    <p className="text-[10px] text-slate-500">This GW</p>
                                    <p className={`text-lg font-bold ${
                                      (playerInjuryAnalysis.chance_of_playing_this_round || 0) >= 75 ? "text-emerald-600" :
                                      (playerInjuryAnalysis.chance_of_playing_this_round || 0) >= 50 ? "text-amber-600" : "text-red-600"
                                    }`}>
                                      {playerInjuryAnalysis.chance_of_playing_this_round ?? "?"}%
                                    </p>
                                  </div>
                                  <div className="p-2 bg-slate-50 rounded-lg text-center">
                                    <p className="text-[10px] text-slate-500">Next GW</p>
                                    <p className={`text-lg font-bold ${
                                      (playerInjuryAnalysis.chance_of_playing_next_round || 0) >= 75 ? "text-emerald-600" :
                                      (playerInjuryAnalysis.chance_of_playing_next_round || 0) >= 50 ? "text-amber-600" : "text-red-600"
                                    }`}>
                                      {playerInjuryAnalysis.chance_of_playing_next_round ?? "?"}%
                                    </p>
                                  </div>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      )}

                      {/* Wikidata Tab - Beautiful & Comprehensive */}
                      {activeCardTab === "wiki" && (
                        <div className="space-y-4">
                          {playerWikidata ? (
                            playerWikidata.found ? (
                              <>
                                {/* Hero Section with Photo */}
                                <div className="bg-gradient-to-br from-blue-50 via-indigo-50 to-violet-50 rounded-xl p-4 border border-blue-100">
                                  <div className="flex items-start gap-4">
                                    {playerWikidata.image ? (
                                      <div className="relative">
                                        <img
                                          src={playerWikidata.image}
                                          alt={selectedPlayer.full_name}
                                          className="w-24 h-28 object-cover rounded-xl shadow-lg border-2 border-white"
                                        />
                                        <div className="absolute -bottom-2 -right-2 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shadow">
                                          <span className="text-white text-xs">W</span>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="w-24 h-28 bg-gradient-to-br from-slate-200 to-slate-300 rounded-xl flex items-center justify-center">
                                        <Users className="w-10 h-10 text-slate-400" />
                                      </div>
                                    )}
                                    <div className="flex-1">
                                      <h3 className="text-lg font-bold text-slate-900">{selectedPlayer.full_name}</h3>
                                      <p className="text-sm text-slate-600">{selectedPlayer.team_short}</p>
                                      {playerWikidata.nationality && (
                                        <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 bg-white/80 rounded-full">
                                          <span className="text-base">🌍</span>
                                          <span className="text-xs font-medium text-slate-700">{playerWikidata.nationality}</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* Current Club */}
                                <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-3 border border-emerald-200">
                                  <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm border border-emerald-100">
                                      <span className="text-xl">⚽</span>
                                    </div>
                                    <div>
                                      <p className="text-[10px] font-medium text-emerald-600 uppercase">Current Club</p>
                                      <p className="text-sm font-bold text-emerald-900">{TEAM_FULL_NAMES[selectedPlayer.team_short] || selectedPlayer.team_short}</p>
                                    </div>
                                  </div>
                                </div>

                                {/* Player Details Grid */}
                                <div className="grid grid-cols-2 gap-3">
                                  {playerWikidata.age && (
                                    <div className="bg-white rounded-xl p-3 border border-slate-200 shadow-sm">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-lg">🎂</span>
                                        <span className="text-[10px] font-medium text-slate-500 uppercase">Age</span>
                                      </div>
                                      <p className="text-xl font-bold text-slate-900">{playerWikidata.age}</p>
                                      <p className="text-[10px] text-slate-400">years old</p>
                                    </div>
                                  )}
                                  {playerWikidata.height && (
                                    <div className="bg-white rounded-xl p-3 border border-slate-200 shadow-sm">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-lg">📏</span>
                                        <span className="text-[10px] font-medium text-slate-500 uppercase">Height</span>
                                      </div>
                                      <p className="text-xl font-bold text-slate-900">{playerWikidata.height}</p>
                                    </div>
                                  )}
                                  {playerWikidata.national_team && (
                                    <div className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-xl p-3 border border-amber-200 col-span-2">
                                      <div className="flex items-center gap-2 mb-1">
                                        <span className="text-lg">🏆</span>
                                        <span className="text-[10px] font-medium text-amber-700 uppercase">National Team</span>
                                      </div>
                                      <p className="text-sm font-bold text-amber-900">{playerWikidata.national_team}</p>
                                    </div>
                                  )}
                                </div>

                                {/* Wikidata Link */}
                                {playerWikidata.wikidata_id && (
                                  <a
                                    href={`https://www.wikidata.org/wiki/${playerWikidata.wikidata_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center justify-center gap-2 w-full py-3 bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-600 transition-all shadow-md"
                                  >
                                    <ExternalLink className="w-4 h-4" />
                                    View Full Profile on Wikidata
                                  </a>
                                )}

                                {/* Powered by Wikidata */}
                                <p className="text-center text-[10px] text-slate-400">
                                  Data sourced from Wikidata - the free knowledge base
                                </p>
                              </>
                            ) : (
                              <div className="text-center py-8">
                                <div className="w-16 h-16 mx-auto mb-4 bg-slate-100 rounded-full flex items-center justify-center">
                                  <Users className="w-8 h-8 text-slate-400" />
                                </div>
                                <p className="text-sm font-medium text-slate-600">No Wikidata Entry Found</p>
                                <p className="text-xs text-slate-400 mt-1">Searched: {playerWikidata.searched_name}</p>
                                <p className="text-[10px] text-slate-400 mt-3">
                                  This player may not have a Wikidata profile yet
                                </p>
                              </div>
                            )
                          ) : (
                            <div className="flex flex-col items-center justify-center py-12">
                              <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-3" />
                              <p className="text-sm text-slate-600">Loading Wikidata...</p>
                              <p className="text-[10px] text-slate-400 mt-1">Fetching player information</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* More Tab - Graph & Data Source */}
                      {activeCardTab === "more" && (
                        <div className="space-y-4">
                          {/* Knowledge Graph Section */}
                          <div>
                            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-2 flex items-center gap-1">
                              <GitBranch className="w-3 h-3 text-cyan-500" />
                              Knowledge Graph
                            </p>
                            <div className="h-48 bg-slate-900 rounded-lg overflow-hidden">
                              {playerNeighborhood?.nodes && playerNeighborhood.nodes.length > 0 ? (
                                <ForceGraph2D
                                  graphData={playerNeighborhood}
                                  nodeLabel={(node: any) => node.label || node.id}
                                  nodeColor={(node: any) => node.color || "#64748b"}
                                  nodeVal={(node: any) => node.size || (node.isCenter ? 4 : 2)}
                                  linkColor={(link: any) => link.color || "#475569"}
                                  linkLabel={(link: any) => link.label}
                                  backgroundColor="#0f172a"
                                  width={300}
                                  height={192}
                                  nodeCanvasObject={(node: any, ctx, globalScale) => {
                                    const label = node.label || "";
                                    const fontSize = node.isCenter ? 10 / globalScale : 7 / globalScale;
                                    ctx.font = `${fontSize}px Sans-Serif`;
                                    ctx.textAlign = "center";
                                    ctx.textBaseline = "middle";
                                    ctx.fillStyle = node.color || "#64748b";
                                    const radius = node.isCenter ? 6 : 4;
                                    ctx.beginPath();
                                    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                                    ctx.fill();
                                    ctx.fillStyle = "#fff";
                                    ctx.fillText(label, node.x, node.y + radius + fontSize);
                                  }}
                                />
                              ) : (
                                <div className="flex items-center justify-center h-full">
                                  <p className="text-xs text-slate-500">
                                    {playerNeighborhood ? "No graph data" : "Loading..."}
                                  </p>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Data Source Section */}
                          {playerProvenance && (
                            <div>
                              <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-2 flex items-center gap-1">
                                <Database className="w-3 h-3 text-violet-500" />
                                Data Source
                              </p>
                              <div className="p-2 bg-violet-50 rounded-lg border border-violet-200 mb-2">
                                <p className="text-[8px] font-mono text-violet-700 break-all">{playerProvenance.player_uri}</p>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <div className="p-2 bg-slate-50 rounded-lg text-center">
                                  <p className="text-sm font-bold text-slate-700">{playerProvenance.data_sources?.length || 0}</p>
                                  <p className="text-[9px] text-slate-500">API Fields</p>
                                </div>
                                <div className="p-2 bg-slate-50 rounded-lg text-center">
                                  <p className="text-sm font-bold text-slate-700">{playerProvenance.rdf_triples_count?.toLocaleString() || 0}</p>
                                  <p className="text-[9px] text-slate-500">RDF Triples</p>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ) : (
              /* Strategy Analysis (when no player selected) */
              <div className={`bg-gradient-to-br ${theme.bgGradient} rounded-2xl shadow-sm border border-slate-200 overflow-hidden`}>
                <div className={`px-5 py-4 bg-gradient-to-r ${theme.gradient} text-white`}>
                  <h2 className="font-bold flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    Strategy Analysis
                  </h2>
                </div>

                <div className="p-5 space-y-4">
                  <p className="text-sm text-slate-600">{squad.strategy_analysis.description}</p>

                  {/* Key Metrics - Strategy-specific display */}
                  <div className="grid grid-cols-2 gap-3">
                    {/* SmartPlay Score - Always shown, most important */}
                    <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-lg p-3 border border-cyan-200">
                      <p className="text-[10px] font-medium text-cyan-600 uppercase tracking-wide">
                        Avg SmartPlay
                      </p>
                      <p className={`text-xl font-bold ${
                        (squad.strategy_analysis.metrics.avg_smartplay_score || 0) >= 7 ? "text-emerald-600" :
                        (squad.strategy_analysis.metrics.avg_smartplay_score || 0) >= 5 ? "text-cyan-600" : "text-amber-600"
                      }`}>
                        {(squad.strategy_analysis.metrics.avg_smartplay_score || 0).toFixed(1)}
                        <span className="text-sm text-cyan-500 font-normal"> /10</span>
                      </p>
                    </div>

                    {/* Strategy-specific metric #2 */}
                    {strategyId === "template" && (
                      <div className="bg-gradient-to-br from-violet-50 to-purple-50 rounded-lg p-3 border border-violet-200">
                        <p className="text-[10px] font-medium text-violet-600 uppercase tracking-wide">
                          Template Players
                        </p>
                        <p className="text-xl font-bold text-violet-700">
                          {squad.strategy_analysis.metrics.high_ownership_count || 0}
                          <span className="text-sm text-violet-400 font-normal"> /15</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "premium" && (
                      <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-lg p-3 border border-amber-200">
                        <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wide">
                          Premium Stars
                        </p>
                        <p className="text-xl font-bold text-amber-700">
                          {squad.strategy_analysis.metrics.premium_count || 0}
                          <span className="text-sm text-amber-400 font-normal"> players</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "value" && (
                      <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-lg p-3 border border-emerald-200">
                        <p className="text-[10px] font-medium text-emerald-600 uppercase tracking-wide">
                          Points/Million
                        </p>
                        <p className="text-xl font-bold text-emerald-700">
                          {(squad.strategy_analysis.metrics.avg_points_per_million || 0).toFixed(1)}
                          <span className="text-sm text-emerald-400 font-normal"> pts/£m</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "form" && (
                      <div className="bg-gradient-to-br from-orange-50 to-red-50 rounded-lg p-3 border border-orange-200">
                        <p className="text-[10px] font-medium text-orange-600 uppercase tracking-wide">
                          Avg FPL Form
                        </p>
                        <p className={`text-xl font-bold ${
                          (squad.strategy_analysis.metrics.avg_form || 0) >= 6 ? "text-emerald-600" :
                          (squad.strategy_analysis.metrics.avg_form || 0) >= 4 ? "text-orange-600" : "text-slate-600"
                        }`}>
                          {(squad.strategy_analysis.metrics.avg_form || 0).toFixed(1)}
                        </p>
                      </div>
                    )}
                    {strategyId === "balanced" && (
                      <div className="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-lg p-3 border border-indigo-200">
                        <p className="text-[10px] font-medium text-indigo-600 uppercase tracking-wide">
                          Balance Score
                        </p>
                        <p className="text-xl font-bold text-indigo-700">
                          {((squad.strategy_analysis.metrics.avg_form || 0) + (squad.strategy_analysis.metrics.avg_smartplay_score || 0)) / 2 > 5 ? "High" : "Good"}
                        </p>
                      </div>
                    )}
                    {strategyId === "smartplay" && (
                      <div className="bg-gradient-to-br from-cyan-50 to-blue-50 rounded-lg p-3 border border-cyan-200">
                        <p className="text-[10px] font-medium text-cyan-600 uppercase tracking-wide">
                          Top Tier (7.0+)
                        </p>
                        <p className="text-xl font-bold text-cyan-700">
                          {squad.strategy_analysis.metrics.top_players_count || 0}
                          <span className="text-sm text-cyan-400 font-normal"> /15</span>
                        </p>
                      </div>
                    )}

                    {/* Strategy-specific metric #3 */}
                    {strategyId === "template" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Avg Ownership
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {(squad.strategy_analysis.metrics.avg_ownership || 0).toFixed(1)}%
                        </p>
                      </div>
                    )}
                    {strategyId === "premium" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Budget Enablers
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {squad.strategy_analysis.metrics.budget_count || 0}
                          <span className="text-sm text-slate-400 font-normal"> players</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "value" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Budget Left
                        </p>
                        <p className="text-xl font-bold text-emerald-600">
                          £{(squad.strategy_analysis.metrics.remaining_budget || 0).toFixed(1)}m
                        </p>
                      </div>
                    )}
                    {strategyId === "form" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Top Tier Players
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {squad.strategy_analysis.metrics.top_players_count || 0}
                          <span className="text-sm text-slate-400 font-normal"> /15</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "balanced" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Avg Ownership
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {(squad.strategy_analysis.metrics.avg_ownership || 0).toFixed(1)}%
                        </p>
                      </div>
                    )}
                    {strategyId === "smartplay" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Avg Ownership
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {(squad.strategy_analysis.metrics.avg_ownership || 0).toFixed(1)}%
                        </p>
                      </div>
                    )}

                    {/* Strategy-specific metric #4 */}
                    {strategyId === "template" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Top Tier Players
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {squad.strategy_analysis.metrics.top_players_count || 0}
                          <span className="text-sm text-slate-400 font-normal"> /15</span>
                        </p>
                      </div>
                    )}
                    {strategyId === "premium" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Squad Value
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          £{(squad.strategy_analysis.metrics.squad_value || 0).toFixed(1)}m
                        </p>
                      </div>
                    )}
                    {strategyId === "value" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Squad Value
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          £{(squad.strategy_analysis.metrics.squad_value || 0).toFixed(1)}m
                        </p>
                      </div>
                    )}
                    {strategyId === "form" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Avg Ownership
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          {(squad.strategy_analysis.metrics.avg_ownership || 0).toFixed(1)}%
                        </p>
                      </div>
                    )}
                    {strategyId === "balanced" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Squad Value
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          £{(squad.strategy_analysis.metrics.squad_value || 0).toFixed(1)}m
                        </p>
                      </div>
                    )}
                    {strategyId === "smartplay" && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
                          Squad Value
                        </p>
                        <p className="text-xl font-bold text-slate-900">
                          £{(squad.strategy_analysis.metrics.squad_value || 0).toFixed(1)}m
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Strengths */}
                  <div>
                    <p className="text-xs font-bold text-emerald-700 mb-2 flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" /> Strengths
                    </p>
                    <ul className="space-y-1">
                      {squad.strategy_analysis.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                          <Check className="w-3 h-3 text-emerald-500 mt-0.5 flex-shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Weaknesses */}
                  <div>
                    <p className="text-xs font-bold text-amber-700 mb-2 flex items-center gap-1">
                      <TrendingDown className="w-3 h-3" /> Considerations
                    </p>
                    <ul className="space-y-1">
                      {squad.strategy_analysis.weaknesses.map((w, i) => (
                        <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                          <AlertTriangle className="w-3 h-3 text-amber-500 mt-0.5 flex-shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* SHACL Validation */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <button
                onClick={() => setShowValidation(!showValidation)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-blue-600" />
                  <h2 className="font-bold text-slate-900">SHACL Validation</h2>
                  {squad.validation.passed ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                      All Passed
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                      {squad.validation.error_count} Issues
                    </span>
                  )}
                </div>
                {showValidation ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              
              {showValidation && (
                <div className="px-5 pb-5 space-y-4">
                  {/* Hard Constraints */}
                  <div>
                    <p className="text-xs font-bold text-slate-700 mb-2">Hard Constraints</p>
                    <div className="space-y-1">
                      {squad.validation.hard_constraints.map((c, i) => (
                        <div key={i} className={`flex items-center justify-between p-2 rounded-lg ${
                          c.passed ? "bg-emerald-50" : "bg-red-50"
                        }`}>
                          <div className="flex items-center gap-2">
                            {c.passed ? (
                              <Check className="w-4 h-4 text-emerald-600" />
                            ) : (
                              <X className="w-4 h-4 text-red-600" />
                            )}
                            <span className="text-xs font-medium text-slate-700">{c.name}</span>
                          </div>
                          <span className="text-xs text-slate-500">{c.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Soft Constraints */}
                  <div>
                    <p className="text-xs font-bold text-slate-700 mb-2">Soft Constraints</p>
                    <div className="space-y-1">
                      {squad.validation.soft_constraints.map((c, i) => (
                        <div key={i} className={`flex items-center justify-between p-2 rounded-lg ${
                          c.passed ? "bg-slate-50" : c.severity === "warning" ? "bg-amber-50" : "bg-blue-50"
                        }`}>
                          <div className="flex items-center gap-2">
                            {c.passed ? (
                              <Check className="w-4 h-4 text-slate-400" />
                            ) : c.severity === "warning" ? (
                              <AlertTriangle className="w-4 h-4 text-amber-500" />
                            ) : (
                              <Info className="w-4 h-4 text-blue-500" />
                            )}
                            <span className="text-xs font-medium text-slate-700">{c.name}</span>
                          </div>
                          <span className="text-xs text-slate-500">{c.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Selection Criteria */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <button
                onClick={() => setShowSparql(!showSparql)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Code className="w-4 h-4 text-cyan-600" />
                  <h2 className="font-bold text-slate-900">Selection Criteria</h2>
                  <span className="text-[10px] bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded-full">SmartPlay</span>
                </div>
                {showSparql ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showSparql && squad.sparql_queries.length > 0 && (
                <div className="px-5 pb-5">
                  <div className="relative">
                    <button
                      onClick={copySparql}
                      className="absolute top-2 right-2 p-1.5 rounded bg-slate-700 hover:bg-slate-600 transition-colors"
                      title="Copy to clipboard"
                    >
                      {copiedSparql ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3 text-slate-300" />
                      )}
                    </button>
                    <pre className="bg-slate-900 text-cyan-300 p-4 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap">
                      {squad.sparql_queries[0]}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            {/* Knowledge Graph SPARQL Query */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <button
                onClick={() => setShowKgQuery(!showKgQuery)}
                className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-violet-600" />
                  <h2 className="font-bold text-slate-900">Knowledge Graph Query</h2>
                  <span className="text-[10px] bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">SPARQL</span>
                </div>
                {showKgQuery ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showKgQuery && (
                <div className="px-5 pb-5">
                  <pre className="bg-slate-900 text-emerald-300 p-4 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap font-mono">
{`PREFIX fpl: <http://smartplay.fpl/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?player ?name ?position ?price ?smartplay_score WHERE {
  ?player a fpl:Player ;
          fpl:webName ?name ;
          fpl:position ?position ;
          fpl:currentPrice ?price ;
          fpl:smartplayScore ?smartplay_score ;
          fpl:status "a" .

  # Strategy-specific filters
  ${strategyId === "smartplay" ? `# No strategy filters - pure SmartPlay optimization
  # Simply select highest SmartPlay scores` :
    strategyId === "template" ? `?player a fpl:TopPlayer .
  FILTER(?ownership > 15)` :
    strategyId === "premium" ? `{ ?player a fpl:Premium } UNION { ?player a fpl:ValuePick }` :
    strategyId === "value" ? `?player a fpl:ValuePick .
  FILTER(?points_per_million > 5)` :
    strategyId === "form" ? `?player a fpl:FormPlayer .` :
    strategyId === "balanced" ? `{ ?player a fpl:NailedOn } UNION { ?player a fpl:FormPlayer }` :
    `# Default strategy`}

  # Exclude injured/unavailable players
  FILTER NOT EXISTS { ?player a fpl:InjuryConcern }
  FILTER NOT EXISTS { ?player a fpl:RotationRisk }
}
ORDER BY DESC(?smartplay_score)
LIMIT 50`}
                  </pre>
                  <div className="mt-3 flex items-center gap-2">
                    <span className="text-[10px] bg-violet-100 text-violet-700 px-2 py-1 rounded-full">
                      RDF Triplestore
                    </span>
                    <span className="text-[10px] bg-emerald-100 text-emerald-700 px-2 py-1 rounded-full">
                      OWL Inference
                    </span>
                    <span className="text-[10px] bg-cyan-100 text-cyan-700 px-2 py-1 rounded-full">
                      SPARQL 1.1
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-3">
              <Link
                href="/build"
                className={`w-full py-3 bg-gradient-to-r ${theme.gradient} text-white font-bold rounded-xl text-center hover:opacity-90 transition-opacity`}
              >
                Try Different Strategy
              </Link>
              <Link
                href="/players"
                className="w-full py-3 bg-white border-2 border-slate-200 text-slate-700 font-bold rounded-xl text-center hover:bg-slate-50 transition-colors"
              >
                Explore Players
              </Link>
            </div>
          </div>
        </div>
      </main>

      {/* Swap Modal */}
      {showSwapModal && playerToSwap && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-hidden">
            {/* Modal Header */}
            <div className={`px-6 py-4 bg-gradient-to-r ${theme.gradient} text-white`}>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-lg">Swap {playerToSwap.web_name}</h3>
                  <p className="text-sm text-white/80">
                    {playerToSwap.team_short} · {playerToSwap.position} · £{playerToSwap.price}m
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowSwapModal(false);
                    setPlayerToSwap(null);
                  }}
                  className="p-2 rounded-lg bg-white/20 hover:bg-white/30"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Swap Candidates */}
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {swapLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
                </div>
              ) : swapCandidates.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-xs text-slate-500 mb-4">
                    Found {swapCandidates.length} quality alternatives based on SmartPlay scores:
                  </p>
                  {swapCandidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className="p-4 border border-slate-200 rounded-xl hover:border-cyan-300 hover:bg-cyan-50/50 transition-all cursor-pointer group"
                      onClick={() => executeSwap(candidate)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${POSITION_COLORS[candidate.position]?.gradient || "from-slate-400 to-slate-500"} flex items-center justify-center`}>
                            <span className="text-sm font-bold text-white">{candidate.position}</span>
                          </div>
                          <div>
                            <p className="font-bold text-slate-900">{candidate.web_name}</p>
                            <p className="text-xs text-slate-500">{candidate.team_short}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-slate-900">£{candidate.price}m</p>
                          <p className={`text-xs font-medium ${
                            candidate.price_diff > 0 ? "text-red-600" : candidate.price_diff < 0 ? "text-emerald-600" : "text-slate-500"
                          }`}>
                            {candidate.price_diff > 0 ? "+" : ""}{candidate.price_diff.toFixed(1)}m
                          </p>
                        </div>
                      </div>

                      {/* SmartPlay Score Badge */}
                      {candidate.smartplay_score && (
                        <div className="mb-2 p-2 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-lg border border-cyan-200/50">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-cyan-700">SmartPlay Score</span>
                            <span className="text-lg font-bold text-cyan-600">{candidate.smartplay_score.toFixed(1)}</span>
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-4">
                          <span className={`font-medium ${candidate.form >= 6 ? "text-emerald-600" : "text-slate-600"}`}>
                            Form: {candidate.form.toFixed(1)}
                          </span>
                          <span className="text-slate-500">
                            {candidate.ownership.toFixed(1)}% owned
                          </span>
                        </div>
                        <span className="text-cyan-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                          Select →
                        </span>
                      </div>

                      {/* Why Recommended */}
                      {candidate.why_recommended && (
                        <p className="text-[10px] text-slate-500 mt-2 italic">
                          {candidate.why_recommended}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Users className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-600 font-medium">No quality alternatives found</p>
                  <p className="text-sm text-slate-500 mt-1">
                    No players with SmartPlay score &ge; 5.0 available at this position
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
