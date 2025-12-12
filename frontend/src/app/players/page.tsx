"use client";

import { Suspense, useState, useMemo, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";

// Dynamic import for force graph (client-side only)
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500"></div>
    </div>
  ),
});
import {
  Brain,
  Search,
  X,
  Users,
  Shield,
  Shirt,
  Target,
  Loader2,
  SlidersHorizontal,
  ChevronDown,
  ChevronUp,
  Filter,
  RotateCcw,
  TrendingUp,
  TrendingDown,
  Calendar,
  Activity,
  Zap,
  Award,
  Clock,
  ArrowLeft,
  Database,
  GitBranch,
  Bookmark,
  Scale,
  Plus,
  Minus,
  Sparkles,
  Home,
  Plane,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  BookOpen,
  Linkedin,
  GraduationCap,
  FileText,
} from "lucide-react";
import { getCurrentGameweek, type Gameweek } from "@/lib/api";
import ChatWidget from "@/components/ChatWidget";
import DeadlineCountdown from "@/components/DeadlineCountdown";
import {
  trackEvent,
  trackPlayerSearch,
  trackPlayerComparison,
  trackFeatureDiscovery,
  trackFunnelStep,
  trackApiPerformance,
  trackError,
} from "@/lib/analytics";

// Types
interface Player {
  id: number;
  name: string;
  webName: string;
  team: {
    id: number;
    name: string;
    shortName: string;
  };
  teamId: number;
  position: "GKP" | "DEF" | "MID" | "FWD";
  price: number;
  form: number;
  totalPoints: number;
  pointsPerGame?: number;
  ownership: number;
  status?: string;
  chanceOfPlaying?: number;
  news?: string;
  xG?: number;
  xA?: number;
  goals?: number;
  assists?: number;
  cleanSheets?: number;
  minutes?: number;
  bonus?: number;
  ictIndex?: number;
  netTransfersGW?: number;
  // OWL Inferred Classes
  inferredClasses?: string[];
}

interface NormalizedPlayer {
  id: number;
  name: string;
  webName: string;
  team: string;
  teamShort: string;
  teamId: number;
  position: "GKP" | "DEF" | "MID" | "FWD";
  price: number;
  form: number;
  totalPoints: number;
  pointsPerGame: number;
  ownership: number;
  status: string;
  chanceOfPlaying: number;
  news: string;
  xG: number;
  xA: number;
  goals: number;
  assists: number;
  cleanSheets: number;
  minutes: number;
  bonus: number;
  ictIndex: number;
  netTransfersGW: number;
  // FDR data
  avgFDR?: number;
  nextFixtures?: { opponent: string; isHome: boolean; difficulty: number }[];
  // SmartPlay ML Scores (0-10 scale)
  smartplayScore: number;
  nailednessScore: number;
  formXgScore: number;
  formPtsScore: number;
  fixtureScore: number;
  // OWL Inferred Classes (now generated from SmartPlay scores)
  inferredClasses?: string[];
}

interface PlayerFDR {
  playerId: number;
  playerName: string;
  teamShort: string;
  fixtures: {
    gameweek: number;
    opponent: string;
    isHome: boolean;
    difficulty: number;
  }[];
  avgDifficulty: number;
}

interface KGStats {
  total_triples: number;
  base_triples: number;
  inferred_triples: number;
  entities: {
    players: number;
    teams: number;
    fixtures: number;
  };
  inference: {
    rules_count: number;
    inferred_by_class: Record<string, number>;
  };
}

// Faceted Filter State
interface Filters {
  search: string;
  positions: ("GKP" | "DEF" | "MID" | "FWD")[];
  teams: string[];
  priceRange: [number, number];
  formRange: [number, number];
  ownershipRange: [number, number];
  pointsRange: [number, number];
  minutesRange: [number, number];
  xGRange: [number, number];
  ppgRange: [number, number];
  goalsAssistsRange: [number, number];
  transferTrend: "all" | "rising" | "falling" | "stable";
  status: ("available" | "doubtful" | "injured")[];
  // Fixture-based filters
  fdrRange: [number, number];
  homeAwayFilter: "all" | "home" | "away";
  // OWL Class filters
  inferredClasses: string[];
  sortBy: "form" | "price" | "points" | "ownership" | "priceAsc" | "xG" | "ppg" | "ppm" | "minutes" | "goalsAssists" | "transfers" | "fdr" | "value";
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  positions: [],
  teams: [],
  priceRange: [3.5, 15],
  formRange: [0, 10],
  ownershipRange: [0, 100],
  pointsRange: [0, 150],
  minutesRange: [0, 1500],
  xGRange: [0, 15],
  ppgRange: [0, 10],
  goalsAssistsRange: [0, 20],
  transferTrend: "all",
  status: ["available", "doubtful"],
  fdrRange: [1, 5],
  homeAwayFilter: "all",
  inferredClasses: [],
  sortBy: "form",
};

// Smart Presets
interface SmartPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  filters: Partial<Filters>;
}

const SMART_PRESETS: SmartPreset[] = [
  {
    id: "budget-enablers",
    name: "Budget Enablers",
    description: "Cheap players who play regularly",
    icon: "💰",
    filters: {
      priceRange: [3.5, 5.5],
      minutesRange: [600, 1500],
      status: ["available"],
    },
  },
  {
    id: "differentials",
    name: "Differential Picks",
    description: "Low ownership + high form",
    icon: "🎯",
    filters: {
      ownershipRange: [0, 5],
      formRange: [4, 10],
      status: ["available"],
    },
  },
  {
    id: "captain-options",
    name: "Captain Options",
    description: "Premium players with easy fixtures",
    icon: "👑",
    filters: {
      priceRange: [9, 15],
      formRange: [5, 10],
      fdrRange: [1, 2.5],
      status: ["available"],
    },
  },
  {
    id: "bench-fodder",
    name: "Bench Fodder",
    description: "Cheapest playing players",
    icon: "🪑",
    filters: {
      priceRange: [3.5, 4.5],
      minutesRange: [400, 1500],
      status: ["available"],
      sortBy: "priceAsc",
    },
  },
  {
    id: "form-picks",
    name: "In-Form Players",
    description: "Hottest players right now",
    icon: "🔥",
    filters: {
      formRange: [6, 10],
      minutesRange: [500, 1500],
      status: ["available"],
      sortBy: "form",
    },
  },
  {
    id: "value-picks",
    name: "Best Value",
    description: "Highest points per million",
    icon: "📈",
    filters: {
      minutesRange: [500, 1500],
      status: ["available"],
      sortBy: "ppm",
    },
  },
  {
    id: "fixture-proof",
    name: "Fixture-Proof",
    description: "Easy fixtures coming up",
    icon: "🟢",
    filters: {
      fdrRange: [1, 2.5],
      formRange: [3, 10],
      status: ["available"],
      sortBy: "fdr",
    },
  },
  {
    id: "xg-merchants",
    name: "xG Merchants",
    description: "High expected output",
    icon: "⚽",
    filters: {
      xGRange: [3, 15],
      status: ["available"],
      sortBy: "xG",
    },
  },
];

// SmartPlay-Based Tag Presets - Tags generated from ML SmartPlay scores
const OWL_CLASS_PRESETS = [
  {
    id: "CaptainCandidate",
    name: "Captain Pick",
    icon: "👑",
    color: "bg-amber-100 text-amber-700 border-amber-200",
    description: "Elite SmartPlay score AND highly nailed - ideal captains",
    rule: "SmartPlay ≥ 7.5 AND Nailedness ≥ 8.0",
    whyTag: (p: NormalizedPlayer) => `SmartPlay ${p.smartplayScore.toFixed(1)} ≥ 7.5 ✓ • Nailedness ${p.nailednessScore.toFixed(1)} ≥ 8.0 ✓`,
    match: (p: NormalizedPlayer) => p.smartplayScore >= 7.5 && p.nailednessScore >= 8.0
  },
  {
    id: "TopPlayer",
    name: "Top Player",
    icon: "⭐",
    color: "bg-yellow-100 text-yellow-700 border-yellow-200",
    description: "High overall SmartPlay score - quality pick",
    rule: "SmartPlay ≥ 7.0",
    whyTag: (p: NormalizedPlayer) => `SmartPlay ${p.smartplayScore.toFixed(1)} ≥ 7.0 ✓ • Top tier player`,
    match: (p: NormalizedPlayer) => p.smartplayScore >= 7.0
  },
  {
    id: "FormPlayer",
    name: "In Form",
    icon: "🔥",
    color: "bg-orange-100 text-orange-700 border-orange-200",
    description: "Currently in hot form based on xG/points",
    rule: "Form_xG ≥ 7.0 OR Form_Pts ≥ 7.0",
    whyTag: (p: NormalizedPlayer) => `Form xG ${p.formXgScore.toFixed(1)} • Form Pts ${p.formPtsScore.toFixed(1)} ✓`,
    match: (p: NormalizedPlayer) => p.formPtsScore >= 7.0 || p.formXgScore >= 7.0
  },
  {
    id: "FixtureFriendly",
    name: "Great Fixtures",
    icon: "📅",
    color: "bg-emerald-100 text-emerald-700 border-emerald-200",
    description: "Favorable upcoming fixtures",
    rule: "Fixture Score ≥ 7.0",
    whyTag: (p: NormalizedPlayer) => `Fixture Score ${p.fixtureScore.toFixed(1)} ≥ 7.0 ✓ • Easy run ahead`,
    match: (p: NormalizedPlayer) => p.fixtureScore >= 7.0
  },
  {
    id: "DifferentialPick",
    name: "Differential",
    icon: "💎",
    color: "bg-purple-100 text-purple-700 border-purple-200",
    description: "Low ownership but quality SmartPlay score",
    rule: "Ownership < 10% AND SmartPlay ≥ 6.0",
    whyTag: (p: NormalizedPlayer) => `Only ${p.ownership.toFixed(1)}% owned • SmartPlay ${p.smartplayScore.toFixed(1)} ✓`,
    match: (p: NormalizedPlayer) => p.ownership < 10 && p.smartplayScore >= 6.0
  },
  {
    id: "ValuePick",
    name: "Budget Gem",
    icon: "💰",
    color: "bg-blue-100 text-blue-700 border-blue-200",
    description: "Great points per million with decent SmartPlay",
    rule: "Pts/£m ≥ 20 AND SmartPlay ≥ 5.5",
    whyTag: (p: NormalizedPlayer) => `${(p.totalPoints/p.price).toFixed(1)} pts/£m ≥ 20 ✓ • SmartPlay ${p.smartplayScore.toFixed(1)} ✓`,
    match: (p: NormalizedPlayer) => (p.totalPoints / Math.max(p.price, 0.1)) >= 20 && p.smartplayScore >= 5.5
  },
  {
    id: "Premium",
    name: "Premium Star",
    icon: "💫",
    color: "bg-indigo-100 text-indigo-700 border-indigo-200",
    description: "Expensive player worth the price tag",
    rule: "Price ≥ £10m AND SmartPlay ≥ 6.5",
    whyTag: (p: NormalizedPlayer) => `Price £${p.price.toFixed(1)}m • SmartPlay ${p.smartplayScore.toFixed(1)} ≥ 6.5 ✓`,
    match: (p: NormalizedPlayer) => p.price >= 10.0 && p.smartplayScore >= 6.5
  },
  {
    id: "NailedOn",
    name: "Nailed On",
    icon: "🔒",
    color: "bg-teal-100 text-teal-700 border-teal-200",
    description: "Guaranteed starter - very secure",
    rule: "Nailedness ≥ 9.0",
    whyTag: (p: NormalizedPlayer) => `Nailedness ${p.nailednessScore.toFixed(1)} ≥ 9.0 ✓ • Guaranteed starter`,
    match: (p: NormalizedPlayer) => p.nailednessScore >= 9.0
  },
  {
    id: "RotationRisk",
    name: "Rotation Risk",
    icon: "🔄",
    color: "bg-rose-100 text-rose-700 border-rose-200",
    description: "Not nailed - may not start regularly",
    rule: "Nailedness < 5.0",
    whyTag: (p: NormalizedPlayer) => `Nailedness ${p.nailednessScore.toFixed(1)} < 5.0 ✗ • Rotation concerns`,
    match: (p: NormalizedPlayer) => p.nailednessScore < 5.0 && p.nailednessScore > 0
  },
  {
    id: "InjuryConcern",
    name: "Injury Doubt",
    icon: "🏥",
    color: "bg-red-100 text-red-700 border-red-200",
    description: "Not fully available - monitor news",
    rule: "Status ≠ available",
    whyTag: (p: NormalizedPlayer) => `Status: ${p.status !== 'a' ? 'Not fully fit' : 'Concern'} • ${p.chanceOfPlaying < 100 ? `${p.chanceOfPlaying}% chance` : 'Monitor'}`,
    match: (p: NormalizedPlayer) => p.status !== 'a'
  },
];

// Activity-Based Presets - Goal-oriented quick filters
const ACTIVITY_PRESETS = [
  {
    id: "wildcard",
    name: "Building Wildcard",
    icon: "🃏",
    description: "Best overall squad options",
    filters: { formRange: [5, 10] as [number, number], status: ["available"] as ("available" | "doubtful" | "injured")[] }
  },
  {
    id: "captain",
    name: "Need a Captain",
    icon: "👑",
    description: "Top captain choices this GW",
    inferredClass: "CaptainCandidate"
  },
  {
    id: "differential",
    name: "Chasing Rank",
    icon: "🎯",
    description: "Low-owned differentials",
    inferredClass: "DifferentialPick"
  },
  {
    id: "budget",
    name: "Saving Money",
    icon: "💰",
    description: "Budget enablers under £5.5m",
    filters: { priceRange: [3.5, 5.5] as [number, number], formRange: [3, 10] as [number, number] }
  },
  {
    id: "fixtures",
    name: "Easy Fixtures",
    icon: "📅",
    description: "Players with green fixtures",
    inferredClass: "FixtureFriendly"
  },
  {
    id: "nailed",
    name: "Nailed Starters",
    icon: "🔒",
    description: "Guaranteed to start",
    inferredClass: "NailedOn"
  },
  {
    id: "form",
    name: "In Hot Form",
    icon: "🔥",
    description: "Players on fire",
    inferredClass: "FormPlayer"
  },
];

// All Premier League teams with colors
const ALL_TEAMS = [
  { short: "ARS", name: "Arsenal", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "AVL", name: "Aston Villa", bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-200" },
  { short: "BOU", name: "Bournemouth", bg: "bg-red-100", text: "text-red-800", border: "border-red-200" },
  { short: "BRE", name: "Brentford", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "BHA", name: "Brighton", bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200" },
  { short: "CHE", name: "Chelsea", bg: "bg-blue-100", text: "text-blue-800", border: "border-blue-200" },
  { short: "CRY", name: "Crystal Palace", bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200" },
  { short: "EVE", name: "Everton", bg: "bg-blue-100", text: "text-blue-800", border: "border-blue-200" },
  { short: "FUL", name: "Fulham", bg: "bg-slate-100", text: "text-slate-800", border: "border-slate-200" },
  { short: "IPS", name: "Ipswich", bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200" },
  { short: "LEI", name: "Leicester", bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200" },
  { short: "LIV", name: "Liverpool", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "MCI", name: "Man City", bg: "bg-sky-100", text: "text-sky-700", border: "border-sky-200" },
  { short: "MUN", name: "Man Utd", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "NEW", name: "Newcastle", bg: "bg-slate-200", text: "text-slate-800", border: "border-slate-300" },
  { short: "NFO", name: "Nott'm Forest", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "SOU", name: "Southampton", bg: "bg-red-100", text: "text-red-700", border: "border-red-200" },
  { short: "TOT", name: "Spurs", bg: "bg-slate-100", text: "text-slate-800", border: "border-slate-200" },
  { short: "WHU", name: "West Ham", bg: "bg-purple-100", text: "text-purple-800", border: "border-purple-200" },
  { short: "WOL", name: "Wolves", bg: "bg-amber-100", text: "text-amber-800", border: "border-amber-200" },
];

// Position colors
const POSITION_COLORS: Record<string, { bg: string; text: string; badge: string }> = {
  GKP: { bg: "bg-amber-50", text: "text-amber-700", badge: "bg-amber-500" },
  DEF: { bg: "bg-green-50", text: "text-green-700", badge: "bg-green-500" },
  MID: { bg: "bg-blue-50", text: "text-blue-700", badge: "bg-blue-500" },
  FWD: { bg: "bg-red-50", text: "text-red-700", badge: "bg-red-500" },
};

// API Configuration - Use relative path to leverage Next.js rewrites
const API_BASE_URL = "";

// ============== Graph Visualization Component ==============

interface GraphNode {
  id: string;
  label: string;
  type: string;
  color: string;
  size: number;
  isCenter?: boolean;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
  color: string;
  dashed?: boolean;
}

interface PlayerNeighborhoodGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
}

function PlayerNeighborhoodGraph({ nodes, links }: PlayerNeighborhoodGraphProps) {
  const graphRef = useRef<any>(null);
  
  // Transform data for react-force-graph
  const graphData = useMemo(() => ({
    nodes: nodes.map((node) => ({
      ...node,
      val: node.size,
    })),
    links: links.map((link) => ({
      ...link,
    })),
  }), [nodes, links]);

  // Custom node rendering
  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.label || "";
    const fontSize = node.isCenter ? 12 / globalScale : 9 / globalScale;
    const nodeSize = node.isCenter ? 8 : 5;
    
    // Draw node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeSize, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || "#6366f1";
    ctx.fill();
    
    // Draw border for center node
    if (node.isCenter) {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }
    
    // Draw label
    ctx.font = `${node.isCenter ? "bold " : ""}${fontSize}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    
    // Label background
    const textWidth = ctx.measureText(label).width;
    const bgPadding = 2 / globalScale;
    ctx.fillStyle = "rgba(15, 23, 42, 0.8)";
    ctx.fillRect(
      node.x - textWidth / 2 - bgPadding,
      node.y + nodeSize + 3 / globalScale,
      textWidth + bgPadding * 2,
      fontSize + bgPadding * 2
    );
    
    // Label text
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, node.x, node.y + nodeSize + 3 / globalScale + fontSize / 2 + bgPadding);
  }, []);

  // Custom link rendering
  const linkCanvasObject = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const start = link.source;
    const end = link.target;
    
    if (typeof start !== "object" || typeof end !== "object") return;
    
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = link.color || "#4b5563";
    ctx.lineWidth = 1 / globalScale;
    
    if (link.dashed) {
      ctx.setLineDash([5 / globalScale, 5 / globalScale]);
    } else {
      ctx.setLineDash([]);
    }
    
    ctx.stroke();
    ctx.setLineDash([]);
  }, []);

  // Center on load
  useEffect(() => {
    if (graphRef.current) {
      setTimeout(() => {
        graphRef.current.zoomToFit(400, 40);
      }, 500);
    }
  }, [graphData]);

  return (
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      nodeCanvasObject={nodeCanvasObject}
      linkCanvasObject={linkCanvasObject}
      nodePointerAreaPaint={(node: any, color, ctx) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
        ctx.fill();
      }}
      linkDirectionalArrowLength={3}
      linkDirectionalArrowRelPos={1}
      backgroundColor="#0f172a"
      width={320}
      height={280}
      cooldownTicks={100}
      d3AlphaDecay={0.02}
      d3VelocityDecay={0.3}
      enableNodeDrag={true}
      enableZoomInteraction={true}
      enablePanInteraction={true}
    />
  );
}

// ============== Filter Components ==============

function FilterSection({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-3 px-1 text-left hover:bg-slate-50 transition-colors"
      >
        <span className="text-sm font-semibold text-slate-800">{title}</span>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      {isOpen && <div className="pb-4 px-1">{children}</div>}
    </div>
  );
}

// ============== Main Component ==============

function PlayersPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [allPlayers, setAllPlayers] = useState<NormalizedPlayer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gameweek, setGameweek] = useState<Gameweek | null>(null);
  const [selectedPlayer, setSelectedPlayer] = useState<NormalizedPlayer | null>(null);
  const [playerFDR, setPlayerFDR] = useState<PlayerFDR | null>(null);
  const [fdrLoading, setFdrLoading] = useState(false);
  // Enhanced player card data
  const [playerExplanation, setPlayerExplanation] = useState<any>(null);
  const [similarPlayers, setSimilarPlayers] = useState<any>(null);
  const [playerProvenance, setPlayerProvenance] = useState<any>(null);
  const [playerWikidata, setPlayerWikidata] = useState<any>(null);
  const [playerInjuryAnalysis, setPlayerInjuryAnalysis] = useState<any>(null);
  const [playerNeighborhood, setPlayerNeighborhood] = useState<any>(null);
  const [showSparqlQuery, setShowSparqlQuery] = useState(false);
  const [showUnmatchedTags, setShowUnmatchedTags] = useState(false);
  const [activeCardTab, setActiveCardTab] = useState<"overview" | "inference" | "similar" | "provenance" | "wikidata" | "injury" | "graph">("overview");
  const [showFilters, setShowFilters] = useState(true);
  const [allPlayersFDR, setAllPlayersFDR] = useState<Map<number, PlayerFDR>>(new Map());
  const [fdrDataLoaded, setFdrDataLoaded] = useState(false);
  // Comparison mode
  const [compareMode, setCompareMode] = useState(false);
  const [comparePlayers, setComparePlayers] = useState<NormalizedPlayer[]>([]);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  // Saved players (shortlist)
  const [savedPlayers, setSavedPlayers] = useState<{
    id: number;
    name: string;
    position: string;
    team: string;
    price: number;
    form: number;
    totalPoints: number;
    ownership: number;
    status: string;
  }[]>([]);
  const [showSavedPanel, setShowSavedPanel] = useState(false);
  // KG Stats
  const [kgStats, setKgStats] = useState<KGStats | null>(null);
  const [kgLoading, setKgLoading] = useState(false);
  // Player inferred classes cache
  const [playerClassesCache, setPlayerClassesCache] = useState<Map<number, string[]>>(new Map());
  const [urlInitialized, setUrlInitialized] = useState(false);

  // Load saved players from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("fpl-shortlist");
    if (saved) {
      setSavedPlayers(JSON.parse(saved));
    }
  }, []);

  // Initialize filters from URL on mount
  useEffect(() => {
    const pos = searchParams.get("pos");
    const teams = searchParams.get("teams");
    const tags = searchParams.get("tags");
    const sort = searchParams.get("sort");
    const search = searchParams.get("q");
    const priceMin = searchParams.get("priceMin");
    const priceMax = searchParams.get("priceMax");
    const formMin = searchParams.get("formMin");
    
    const newFilters: Partial<Filters> = {};
    
    if (pos) newFilters.positions = pos.split(",") as ("GKP" | "DEF" | "MID" | "FWD")[];
    if (teams) newFilters.teams = teams.split(",");
    if (tags) newFilters.inferredClasses = tags.split(",");
    if (sort) newFilters.sortBy = sort as Filters["sortBy"];
    if (search) newFilters.search = search;
    if (priceMin || priceMax) {
      const min = priceMin ? parseFloat(priceMin) : 3.5;  // default min price
      const max = priceMax ? parseFloat(priceMax) : 15;   // default max price
      newFilters.priceRange = [min, max];
    }
    if (formMin) newFilters.formRange = [parseFloat(formMin), 10];
    
    if (Object.keys(newFilters).length > 0) {
      setFilters(prev => ({ ...prev, ...newFilters }));
    }
    setUrlInitialized(true);
  }, []);

  // Sync filters to URL (debounced)
  useEffect(() => {
    if (!urlInitialized) return;
    
    const params = new URLSearchParams();
    
    if (filters.positions.length > 0) params.set("pos", filters.positions.join(","));
    if (filters.teams.length > 0) params.set("teams", filters.teams.join(","));
    if (filters.inferredClasses.length > 0) params.set("tags", filters.inferredClasses.join(","));
    if (filters.sortBy !== "form") params.set("sort", filters.sortBy);
    if (filters.search) params.set("q", filters.search);
    if (filters.priceRange[0] !== 3.5 || filters.priceRange[1] !== 15) {
      params.set("priceMin", filters.priceRange[0].toString());
      params.set("priceMax", filters.priceRange[1].toString());
    }
    if (filters.formRange[0] !== 0) params.set("formMin", filters.formRange[0].toString());
    
    const queryString = params.toString();
    const newUrl = queryString ? `?${queryString}` : "/players";
    
    // Only update if different from current URL
    if (window.location.search !== `?${queryString}` && window.location.search !== "" || queryString !== "") {
      router.replace(newUrl, { scroll: false });
    }
  }, [filters, urlInitialized, router]);

  // Helper to update filters
  const updateFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Reset all filters and clear URL
  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setActivePreset(null);
    router.replace("/players", { scroll: false });
    trackEvent({ name: 'player_search_reset', properties: { page: 'players' } });
  };

  // Apply a smart preset
  const applyPreset = (preset: SmartPreset) => {
    setFilters({ ...DEFAULT_FILTERS, ...preset.filters });
    setActivePreset(preset.id);
    trackEvent({
      name: 'player_preset_applied',
      properties: {
        preset_id: preset.id,
        preset_name: preset.name,
      },
    });
    trackFeatureDiscovery('smart_preset', 'click');
  };

  // Toggle OWL class filter
  const toggleOwlClass = (classId: string) => {
    const isRemoving = filters.inferredClasses.includes(classId);
    setFilters(prev => ({
      ...prev,
      inferredClasses: prev.inferredClasses.includes(classId)
        ? prev.inferredClasses.filter(c => c !== classId)
        : [...prev.inferredClasses, classId],
    }));
    trackEvent({
      name: 'player_tag_filter',
      properties: {
        tag: classId,
        action: isRemoving ? 'remove' : 'add',
      },
    });
  };

  // Toggle player in comparison
  const toggleComparePlayer = (player: NormalizedPlayer) => {
    if (comparePlayers.some(p => p.id === player.id)) {
      setComparePlayers(comparePlayers.filter(p => p.id !== player.id));
      trackEvent({
        name: 'player_comparison_remove',
        properties: {
          player_id: player.id,
          player_name: player.webName,
        },
      });
    } else if (comparePlayers.length < 3) {
      setComparePlayers([...comparePlayers, player]);
      trackEvent({
        name: 'player_comparison_add',
        properties: {
          player_id: player.id,
          player_name: player.webName,
          position: player.position,
          price: player.price,
          comparison_count: comparePlayers.length + 1,
        },
      });
    }
  };

  // Clear comparison
  const clearComparison = () => {
    if (comparePlayers.length > 0) {
      trackPlayerComparison(
        comparePlayers.map(p => p.id),
        comparePlayers.map(p => p.webName)
      );
    }
    setComparePlayers([]);
    setCompareMode(false);
  };

  // Check if player is saved
  const isPlayerSaved = (playerId: number) => {
    return savedPlayers.some(p => p.id === playerId);
  };

  // Add player to saved list
  const addToSaved = (player: NormalizedPlayer) => {
    if (isPlayerSaved(player.id)) return;

    const newPlayer = {
      id: player.id,
      name: player.webName,
      position: player.position,
      team: player.teamShort,
      price: player.price,
      form: player.form,
      totalPoints: player.totalPoints,
      ownership: player.ownership,
      status: player.status || "a",
    };
    const newSavedPlayers = [...savedPlayers, newPlayer];
    setSavedPlayers(newSavedPlayers);
    localStorage.setItem("fpl-shortlist", JSON.stringify(newSavedPlayers));
    trackEvent({
      name: 'player_shortlist_add',
      properties: {
        player_id: player.id,
        player_name: player.webName,
        position: player.position,
        team: player.teamShort,
        price: player.price,
        shortlist_size: newSavedPlayers.length,
      },
    });
  };

  // Remove player from saved list
  const removeFromSaved = (playerId: number) => {
    const removedPlayer = savedPlayers.find(p => p.id === playerId);
    const newSavedPlayers = savedPlayers.filter(p => p.id !== playerId);
    setSavedPlayers(newSavedPlayers);
    localStorage.setItem("fpl-shortlist", JSON.stringify(newSavedPlayers));
    if (removedPlayer) {
      trackEvent({
        name: 'player_shortlist_remove',
        properties: {
          player_id: playerId,
          player_name: removedPlayer.name,
          shortlist_size: newSavedPlayers.length,
        },
      });
    }
  };

  // Clear all saved players
  const clearSaved = () => {
    const clearedCount = savedPlayers.length;
    setSavedPlayers([]);
    localStorage.removeItem("fpl-shortlist");
    trackEvent({
      name: 'player_shortlist_clear',
      properties: {
        cleared_count: clearedCount,
      },
    });
  };

  // Toggle position filter
  const togglePosition = (pos: "GKP" | "DEF" | "MID" | "FWD") => {
    const isRemoving = filters.positions.includes(pos);
    setFilters(prev => ({
      ...prev,
      positions: prev.positions.includes(pos)
        ? prev.positions.filter(p => p !== pos)
        : [...prev.positions, pos],
    }));
    trackEvent({
      name: 'player_filter_position',
      properties: {
        position: pos,
        action: isRemoving ? 'remove' : 'add',
      },
    });
  };

  // Toggle team filter
  const toggleTeam = (teamShort: string) => {
    const isRemoving = filters.teams.includes(teamShort);
    setFilters(prev => ({
      ...prev,
      teams: prev.teams.includes(teamShort)
        ? prev.teams.filter(t => t !== teamShort)
        : [...prev.teams, teamShort],
    }));
    trackEvent({
      name: 'player_filter_team',
      properties: {
        team: teamShort,
        action: isRemoving ? 'remove' : 'add',
      },
    });
  };

  // Toggle status filter
  const toggleStatus = (status: "available" | "doubtful" | "injured") => {
    const isRemoving = filters.status.includes(status);
    setFilters(prev => ({
      ...prev,
      status: prev.status.includes(status)
        ? prev.status.filter(s => s !== status)
        : [...prev.status, status],
    }));
    trackEvent({
      name: 'player_filter_status',
      properties: {
        status,
        action: isRemoving ? 'remove' : 'add',
      },
    });
  };

  // Fetch KG status
  const fetchKGStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/kg/status`);
      if (response.ok) {
        const data = await response.json();
        if (data.status === "ready") {
          setKgStats(data.statistics);
        }
      }
    } catch (e) {
      console.warn("Could not fetch KG status:", e);
    }
  };

  // Rebuild KG
  const rebuildKG = async () => {
    setKgLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/kg/rebuild`, { method: "POST" });
      if (response.ok) {
        const data = await response.json();
        setKgStats(data.statistics);
        // Regenerate player tags based on current players
        generateSmartPlayTags(allPlayers);
      }
    } catch (e) {
      console.error("Failed to rebuild KG:", e);
    } finally {
      setKgLoading(false);
    }
  };

  // Generate SmartPlay-based tags for all players (client-side)
  const generateSmartPlayTags = (players: NormalizedPlayer[]) => {
    const cache = new Map<number, string[]>();

    for (const player of players) {
      const tags: string[] = [];

      // Apply each tag preset's match function
      for (const preset of OWL_CLASS_PRESETS) {
        if (preset.match && preset.match(player)) {
          tags.push(preset.id);
        }
      }

      if (tags.length > 0) {
        cache.set(player.id, tags);
      }
    }

    setPlayerClassesCache(cache);
  };

  // Fetch players
  useEffect(() => {
    const fetchPlayers = async () => {
      setIsLoading(true);
      setError(null);
      const startTime = Date.now();

      try {
        // Fetch players and SmartPlay scores in parallel
        const [playersResponse, scoresResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/players?limit=0`),
          fetch(`${API_BASE_URL}/api/predictor/scores?limit=1000`)
        ]);

        if (!playersResponse.ok) {
          throw new Error(`Failed to fetch players: ${playersResponse.status}`);
        }

        const data = await playersResponse.json();

        // Build SmartPlay scores map
        const scoresMap = new Map<number, {
          smartplayScore: number;
          nailednessScore: number;
          formXgScore: number;
          formPtsScore: number;
          fixtureScore: number;
        }>();

        if (scoresResponse.ok) {
          const scoresData = await scoresResponse.json();
          for (const score of scoresData) {
            scoresMap.set(score.player_id, {
              smartplayScore: score.final_score || 0,
              nailednessScore: score.nailedness_score || 0,
              formXgScore: score.form_xg_score || 0,
              formPtsScore: score.form_pts_score || 0,
              fixtureScore: score.fixture_score || 0,
            });
          }
        }

        // Normalize player data with SmartPlay scores
        const normalized: NormalizedPlayer[] = data.players.map((p: Player) => {
          const scores = scoresMap.get(p.id) || {
            smartplayScore: 0,
            nailednessScore: 0,
            formXgScore: 0,
            formPtsScore: 0,
            fixtureScore: 0,
          };

          return {
            id: p.id,
            name: p.name,
            webName: p.webName,
            team: p.team?.name || "Unknown",
            teamShort: p.team?.shortName || "UNK",
            teamId: p.teamId,
            position: p.position as "GKP" | "DEF" | "MID" | "FWD",
            price: p.price,
            form: typeof p.form === 'number' ? p.form : parseFloat(String(p.form)) || 0,
            totalPoints: p.totalPoints,
            pointsPerGame: typeof p.pointsPerGame === 'number' ? p.pointsPerGame : parseFloat(String(p.pointsPerGame)) || 0,
            ownership: typeof p.ownership === 'number' ? p.ownership : parseFloat(String(p.ownership)) || 0,
            status: p.status || "a",
            chanceOfPlaying: p.chanceOfPlaying ?? 100,
            news: p.news || "",
            xG: p.xG || 0,
            xA: p.xA || 0,
            goals: p.goals || 0,
            assists: p.assists || 0,
            cleanSheets: p.cleanSheets || 0,
            minutes: p.minutes || 0,
            bonus: p.bonus || 0,
            ictIndex: p.ictIndex || 0,
            netTransfersGW: p.netTransfersGW || 0,
            // SmartPlay scores
            ...scores,
          };
        });

        setAllPlayers(normalized);

        // Generate SmartPlay-based tags client-side
        generateSmartPlayTags(normalized);

        // Fetch KG status (for display purposes)
        await fetchKGStatus();

        // Track successful page load
        const loadTimeMs = Date.now() - startTime;
        trackApiPerformance('/api/players', loadTimeMs, true);
        trackEvent({
          name: 'player_explorer_loaded',
          properties: {
            player_count: normalized.length,
            load_time_ms: loadTimeMs,
            has_scores: scoresResponse.ok,
          },
        });
        trackFunnelStep('squad_builder', 1, 'player_explorer_opened', true);

      } catch (err) {
        console.error("Error fetching players:", err);
        const errorMessage = err instanceof Error ? err.message : "Failed to load players";
        setError(errorMessage);
        trackError('player_explorer_load_failed', errorMessage, 'players_page');
        trackApiPerformance('/api/players', Date.now() - startTime, false);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPlayers();
    getCurrentGameweek().then(setGameweek).catch(console.error);
  }, []);

  // Format deadline compactly with urgency indicator
  const formatDeadlineCompact = (deadline: string): { text: string; urgent: boolean; veryUrgent: boolean } => {
    const date = new Date(deadline);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    
    if (diffMs < 0) return { text: "Passed", urgent: false, veryUrgent: false };
    if (diffHours < 2 && diffDays === 0) return { text: `${diffMinutes}m`, urgent: true, veryUrgent: true };
    if (diffDays === 0) return { text: `${diffHours}h ${diffMinutes}m`, urgent: true, veryUrgent: diffHours < 6 };
    if (diffDays === 1) return { text: `${diffDays}d ${diffHours}h`, urgent: true, veryUrgent: false };
    return { text: `${diffDays}d ${diffHours}h`, urgent: false, veryUrgent: false };
  };

  // Fetch FDR data for players
  useEffect(() => {
    if (allPlayers.length === 0 || fdrDataLoaded) return;

    const fetchAllFDR = async () => {
      try {
        const activePlayers = allPlayers.filter(p => p.minutes > 100);
        const playerIds = activePlayers.map(p => p.id);
        const batchSize = 50;
        const fdrMap = new Map<number, PlayerFDR>();

        for (let i = 0; i < playerIds.length; i += batchSize) {
          const batch = playerIds.slice(i, i + batchSize);
          try {
            const response = await fetch(
              `${API_BASE_URL}/api/fixtures/players-fdr?player_ids=${batch.join(",")}&gameweeks=5`
            );
            if (response.ok) {
              const data = await response.json();
              const fdrData = data.playersFDR || [];
              fdrData.forEach((fdr: PlayerFDR) => {
                fdrMap.set(fdr.playerId, fdr);
              });
            }
          } catch (batchErr) {
            console.warn(`FDR batch ${i} failed:`, batchErr);
          }
          if (i + batchSize < playerIds.length) {
            await new Promise(r => setTimeout(r, 100));
          }
        }

        setAllPlayersFDR(fdrMap);
        
        setAllPlayers(prev => prev.map(p => {
          const fdr = fdrMap.get(p.id);
          return {
            ...p,
            avgFDR: fdr?.avgDifficulty,
            nextFixtures: fdr?.fixtures?.slice(0, 3),
          };
        }));
        
        setFdrDataLoaded(true);
      } catch (e) {
        console.error("Failed to fetch FDR data:", e);
        setFdrDataLoaded(true);
      }
    };

    const timer = setTimeout(fetchAllFDR, 300);
    return () => clearTimeout(timer);
  }, [allPlayers.length, fdrDataLoaded]);

  // Fetch fixture data and enhanced card data when player is selected
  useEffect(() => {
    if (!selectedPlayer) {
      setPlayerFDR(null);
      setPlayerExplanation(null);
      setSimilarPlayers(null);
      setPlayerProvenance(null);
      setPlayerWikidata(null);
      setPlayerInjuryAnalysis(null);
      setPlayerNeighborhood(null);
      setActiveCardTab("overview");
      setShowUnmatchedTags(false);
      return;
    }

    const fetchFDR = async () => {
      setFdrLoading(true);
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/fixtures/players-fdr?player_ids=${selectedPlayer.id}&gameweeks=5`
        );
        if (response.ok) {
          const data = await response.json();
          const fdrData = data.playersFDR || [];
          if (Array.isArray(fdrData) && fdrData.length > 0) {
            setPlayerFDR(fdrData[0]);
          } else {
            setPlayerFDR(null);
          }
        } else {
          setPlayerFDR(null);
        }
      } catch (e) {
        console.error("Failed to fetch FDR:", e);
        setPlayerFDR(null);
      } finally {
        setFdrLoading(false);
      }
    };

    // Fetch inference explanation
    const fetchExplanation = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/explain`);
        if (response.ok) {
          const data = await response.json();
          setPlayerExplanation(data);
        }
      } catch (e) {
        console.error("Failed to fetch explanation:", e);
      }
    };

    // Fetch similar players
    const fetchSimilar = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/similar?limit=5`);
        if (response.ok) {
          const data = await response.json();
          setSimilarPlayers(data);
        }
      } catch (e) {
        console.error("Failed to fetch similar players:", e);
      }
    };

    // Fetch provenance
    const fetchProvenance = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/provenance`);
        if (response.ok) {
          const data = await response.json();
          setPlayerProvenance(data);
        }
      } catch (e) {
        console.error("Failed to fetch provenance:", e);
      }
    };

    // Fetch Wikidata external data
    const fetchWikidata = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/wikidata`);
        if (response.ok) {
          const data = await response.json();
          setPlayerWikidata(data);
        }
      } catch (e) {
        console.error("Failed to fetch Wikidata:", e);
      }
    };

    // Fetch injury analysis (NLP-parsed news)
    const fetchInjuryAnalysis = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/injury-analysis`);
        if (response.ok) {
          const data = await response.json();
          setPlayerInjuryAnalysis(data);
        }
      } catch (e) {
        console.error("Failed to fetch injury analysis:", e);
      }
    };

    // Fetch neighborhood graph data
    const fetchNeighborhood = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/kg/player/${selectedPlayer.id}/neighborhood`);
        if (response.ok) {
          const data = await response.json();
          setPlayerNeighborhood(data);
        }
      } catch (e) {
        console.error("Failed to fetch neighborhood:", e);
      }
    };

    fetchFDR();
    fetchExplanation();
    fetchSimilar();
    fetchProvenance();
    fetchWikidata();
    fetchInjuryAnalysis();
    fetchNeighborhood();
  }, [selectedPlayer]);

  // Get player status category
  const getStatusCategory = (status: string): "available" | "doubtful" | "injured" => {
    if (status === "a") return "available";
    if (status === "d") return "doubtful";
    return "injured";
  };

  // Compute facet counts - how many players would match each filter value
  const facetCounts = useMemo(() => {
    // For counts, we apply all OTHER filters except the one being counted
    const applyFiltersExcept = (players: NormalizedPlayer[], excludeFilter: string) => {
      return players.filter(p => {
        if (excludeFilter !== "positions" && filters.positions.length > 0 && !filters.positions.includes(p.position)) return false;
        if (excludeFilter !== "teams" && filters.teams.length > 0 && !filters.teams.includes(p.teamShort)) return false;
        if (excludeFilter !== "price" && (p.price < filters.priceRange[0] || p.price > filters.priceRange[1])) return false;
        if (excludeFilter !== "form" && (p.form < filters.formRange[0] || p.form > filters.formRange[1])) return false;
        if (excludeFilter !== "ownership" && (p.ownership < filters.ownershipRange[0] || p.ownership > filters.ownershipRange[1])) return false;
        if (excludeFilter !== "status") {
          const statusCat = getStatusCategory(p.status);
          if (!filters.status.includes(statusCat)) return false;
        }
        if (filters.search) {
          const query = filters.search.toLowerCase();
          if (!p.name.toLowerCase().includes(query) && 
              !p.webName.toLowerCase().includes(query) &&
              !p.team.toLowerCase().includes(query)) return false;
        }
        return true;
      });
    };

    // Position counts
    const positionBase = applyFiltersExcept(allPlayers, "positions");
    const positions = {
      GKP: positionBase.filter(p => p.position === "GKP").length,
      DEF: positionBase.filter(p => p.position === "DEF").length,
      MID: positionBase.filter(p => p.position === "MID").length,
      FWD: positionBase.filter(p => p.position === "FWD").length,
    };

    // Team counts
    const teamBase = applyFiltersExcept(allPlayers, "teams");
    const teams: Record<string, number> = {};
    ALL_TEAMS.forEach(team => {
      teams[team.short] = teamBase.filter(p => p.teamShort === team.short).length;
    });

    // Status counts
    const statusBase = applyFiltersExcept(allPlayers, "status");
    const status = {
      available: statusBase.filter(p => getStatusCategory(p.status) === "available").length,
      doubtful: statusBase.filter(p => getStatusCategory(p.status) === "doubtful").length,
      injured: statusBase.filter(p => getStatusCategory(p.status) === "injured").length,
    };

    // Smart Tag counts (based on current filtered set)
    const tagBase = applyFiltersExcept(allPlayers, "inferredClasses");
    const smartTags: Record<string, number> = {};
    OWL_CLASS_PRESETS.forEach(preset => {
      smartTags[preset.id] = tagBase.filter(p => {
        const classes = playerClassesCache.get(p.id) || [];
        return classes.includes(preset.id);
      }).length;
    });

    // Smart Preset counts - how many players match each preset's filter criteria
    const presets: Record<string, number> = {};
    SMART_PRESETS.forEach(preset => {
      presets[preset.id] = allPlayers.filter(p => {
        const f = preset.filters;
        if (f.priceRange && (p.price < f.priceRange[0] || p.price > f.priceRange[1])) return false;
        if (f.formRange && (p.form < f.formRange[0] || p.form > f.formRange[1])) return false;
        if (f.ownershipRange && (p.ownership < f.ownershipRange[0] || p.ownership > f.ownershipRange[1])) return false;
        if (f.minutesRange && (p.minutes < f.minutesRange[0] || p.minutes > f.minutesRange[1])) return false;
        if (f.xGRange && ((p.xG + p.xA) < f.xGRange[0] || (p.xG + p.xA) > f.xGRange[1])) return false;
        if (f.fdrRange && p.avgFDR && (p.avgFDR < f.fdrRange[0] || p.avgFDR > f.fdrRange[1])) return false;
        if (f.status) {
          const statusCat = getStatusCategory(p.status);
          if (!f.status.includes(statusCat)) return false;
        }
        return true;
      }).length;
    });

    return { positions, teams, status, smartTags, presets };
  }, [allPlayers, filters, playerClassesCache]);

  // Filter and sort players
  const filteredPlayers = useMemo(() => {
    let players = allPlayers.filter(p => {
      // Position filter
      if (filters.positions.length > 0 && !filters.positions.includes(p.position)) {
        return false;
      }

      // Search filter
      if (filters.search) {
        const query = filters.search.toLowerCase();
        if (!p.name.toLowerCase().includes(query) && 
            !p.webName.toLowerCase().includes(query) &&
            !p.team.toLowerCase().includes(query) &&
            !p.teamShort.toLowerCase().includes(query)) {
          return false;
        }
      }
      
      // Team filter
      if (filters.teams.length > 0 && !filters.teams.includes(p.teamShort)) {
        return false;
      }
      
      // Price range filter
      if (p.price < filters.priceRange[0] || p.price > filters.priceRange[1]) {
        return false;
      }
      
      // Form range filter
      if (p.form < filters.formRange[0] || p.form > filters.formRange[1]) {
        return false;
      }
      
      // Ownership range filter
      if (p.ownership < filters.ownershipRange[0] || p.ownership > filters.ownershipRange[1]) {
        return false;
      }
      
      // Total Points range filter
      if (p.totalPoints < filters.pointsRange[0] || p.totalPoints > filters.pointsRange[1]) {
        return false;
      }
      
      // Minutes range filter
      if (p.minutes < filters.minutesRange[0] || p.minutes > filters.minutesRange[1]) {
        return false;
      }
      
      // xG + xA range filter
      const xGI = p.xG + p.xA;
      if (xGI < filters.xGRange[0] || xGI > filters.xGRange[1]) {
        return false;
      }
      
      // Points Per Game range filter
      if (p.pointsPerGame < filters.ppgRange[0] || p.pointsPerGame > filters.ppgRange[1]) {
        return false;
      }
      
      // Goals + Assists range filter
      const goalsAssists = p.goals + p.assists;
      if (goalsAssists < filters.goalsAssistsRange[0] || goalsAssists > filters.goalsAssistsRange[1]) {
        return false;
      }
      
      // Transfer Trend filter
      if (filters.transferTrend !== "all") {
        if (filters.transferTrend === "rising" && p.netTransfersGW <= 10000) return false;
        if (filters.transferTrend === "falling" && p.netTransfersGW >= -10000) return false;
        if (filters.transferTrend === "stable" && (p.netTransfersGW > 10000 || p.netTransfersGW < -10000)) return false;
      }
      
      // FDR range filter
      if (p.avgFDR !== undefined) {
        if (p.avgFDR < filters.fdrRange[0] || p.avgFDR > filters.fdrRange[1]) {
          return false;
        }
      }
      
      // Home/Away filter
      if (filters.homeAwayFilter !== "all" && p.nextFixtures && p.nextFixtures.length > 0) {
        const nextIsHome = p.nextFixtures[0].isHome;
        if (filters.homeAwayFilter === "home" && !nextIsHome) return false;
        if (filters.homeAwayFilter === "away" && nextIsHome) return false;
      }
      
      // Status filter
      const statusCategory = getStatusCategory(p.status);
      if (filters.status.length > 0 && !filters.status.includes(statusCategory)) {
        return false;
      }

      // OWL Inferred Class filter
      if (filters.inferredClasses.length > 0) {
        const playerClasses = playerClassesCache.get(p.id) || [];
        const hasMatchingClass = filters.inferredClasses.some(c => playerClasses.includes(c));
        if (!hasMatchingClass) {
          return false;
        }
      }

      return true;
    });

    // Sort
    players.sort((a, b) => {
      switch (filters.sortBy) {
        case "price": return b.price - a.price;
        case "priceAsc": return a.price - b.price;
        case "form": return b.form - a.form;
        case "points": return b.totalPoints - a.totalPoints;
        case "ownership": return b.ownership - a.ownership;
        case "xG": return (b.xG + b.xA) - (a.xG + a.xA);
        case "ppg": return b.pointsPerGame - a.pointsPerGame;
        case "ppm": return (b.totalPoints / b.price) - (a.totalPoints / a.price);
        case "minutes": return b.minutes - a.minutes;
        case "goalsAssists": return (b.goals + b.assists) - (a.goals + a.assists);
        case "transfers": return b.netTransfersGW - a.netTransfersGW;
        case "fdr": return (a.avgFDR || 5) - (b.avgFDR || 5);
        case "value": {
          const valueA = (a.form * a.pointsPerGame) / a.price;
          const valueB = (b.form * b.pointsPerGame) / b.price;
          return valueB - valueA;
        }
        default: return 0;
      }
    });

    return players;
  }, [allPlayers, filters, playerClassesCache]);

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.search) count++;
    if (filters.positions.length > 0) count++;
    if (filters.teams.length > 0) count++;
    if (filters.priceRange[0] > 3.5 || filters.priceRange[1] < 15) count++;
    if (filters.formRange[0] > 0 || filters.formRange[1] < 10) count++;
    if (filters.ownershipRange[0] > 0 || filters.ownershipRange[1] < 100) count++;
    if (filters.pointsRange[0] > 0 || filters.pointsRange[1] < 150) count++;
    if (filters.minutesRange[0] > 0 || filters.minutesRange[1] < 1500) count++;
    if (filters.xGRange[0] > 0 || filters.xGRange[1] < 15) count++;
    if (filters.ppgRange[0] > 0 || filters.ppgRange[1] < 10) count++;
    if (filters.goalsAssistsRange[0] > 0 || filters.goalsAssistsRange[1] < 20) count++;
    if (filters.transferTrend !== "all") count++;
    if (filters.fdrRange[0] > 1 || filters.fdrRange[1] < 5) count++;
    if (filters.homeAwayFilter !== "all") count++;
    if (filters.status.length < 3) count++;
    if (filters.inferredClasses.length > 0) count++;
    return count;
  }, [filters]);

  // Get status icon and color
  const getStatusIndicator = (status: string) => {
    if (status === "a") return { icon: "🟢", color: "text-emerald-600", label: "Available" };
    if (status === "d") return { icon: "🟡", color: "text-amber-600", label: "Doubtful" };
    return { icon: "🔴", color: "text-red-600", label: "Injured/Suspended" };
  };

  // Knowledge Graph facts for loading screen
  const kgFacts = [
    { icon: "🌐", title: "What is a Knowledge Graph?", text: "A network of real-world entities and their relationships, stored as triples (subject → predicate → object)." },
    { icon: "🔗", title: "RDF: The Foundation", text: "Resource Description Framework (RDF) is a W3C standard for representing data as a graph of connected resources." },
    { icon: "🦉", title: "OWL Reasoning", text: "Web Ontology Language (OWL) automatically infers new facts from existing data — like classifying 'Captain Candidates' based on defined rules." },
    { icon: "📊", title: "SPARQL Queries", text: "Like SQL for graphs! SPARQL lets us ask complex questions across interconnected data." },
    { icon: "✅", title: "SHACL Validation", text: "Shapes Constraint Language ensures data quality by validating graph structure against defined rules." },
    { icon: "🔍", title: "What is Faceted Search?", text: "Unlike keyword search, faceted search lets you filter by multiple dimensions (price, form, team) simultaneously — like shopping on Amazon!" },
    { icon: "🎯", title: "Facets + Knowledge Graphs", text: "We combine faceted search with semantic reasoning: filter by position AND Smart Tags like 'Captain Picks' — inferred automatically by OWL." },
    { icon: "🏢", title: "Used by Giants", text: "Google, Amazon, Facebook, and LinkedIn all use Knowledge Graphs to power search and recommendations." },
    { icon: "🧠", title: "Semantic Intelligence", text: "Unlike traditional databases, KGs understand meaning — they know 'Salah plays for Liverpool' implies 'Salah is a footballer'." },
    { icon: "⚡", title: "Why the Wait?", text: "Semantic reasoning is computationally intensive. We're running OWL inference on 756 players to generate Smart Tags!" },
  ];
  
  const [factIndex, setFactIndex] = useState(0);
  
  // Rotate facts every 3 seconds during loading
  useEffect(() => {
    if (!isLoading) return;
    const interval = setInterval(() => {
      setFactIndex((prev) => (prev + 1) % kgFacts.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [isLoading, kgFacts.length]);

  // Loading state - full screen overlay to hide footer
  if (isLoading) {
    const currentFact = kgFacts[factIndex];
    return (
      <div className="fixed inset-0 z-50 bg-gradient-to-br from-slate-900 via-violet-900 to-slate-900 flex items-center justify-center p-4">
        <div className="text-center max-w-xl">
          {/* Dual Animated Icons - KG + Faceted Search */}
          <div className="flex justify-center gap-6 mb-8">
            {/* Knowledge Graph Icon */}
            <div className="relative w-20 h-20 sm:w-24 sm:h-24">
              <div className="absolute inset-0 bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-2xl animate-pulse" />
              <div className="absolute inset-2 bg-slate-800/95 rounded-xl flex items-center justify-center border border-violet-500/30 backdrop-blur">
                <Database className="w-8 h-8 sm:w-10 sm:h-10 text-violet-400 animate-pulse" />
            </div>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-violet-500 rounded-full animate-ping" />
          </div>
            
            {/* Connection */}
            <div className="flex items-center">
              <div className="w-8 h-0.5 bg-gradient-to-r from-violet-500 to-emerald-500 animate-pulse" />
              <span className="text-xl mx-1">+</span>
              <div className="w-8 h-0.5 bg-gradient-to-r from-emerald-500 to-violet-500 animate-pulse" />
          </div>
            
            {/* Faceted Search Icon */}
            <div className="relative w-20 h-20 sm:w-24 sm:h-24">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-2xl animate-pulse" />
              <div className="absolute inset-2 bg-slate-800/95 rounded-xl flex items-center justify-center border border-emerald-500/30 backdrop-blur">
                <Filter className="w-8 h-8 sm:w-10 sm:h-10 text-emerald-400 animate-pulse" />
              </div>
              <div className="absolute -bottom-1 -left-1 w-3 h-3 bg-emerald-500 rounded-full animate-ping" style={{ animationDelay: '0.5s' }} />
            </div>
          </div>
          
          {/* Title - Both Technologies */}
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2">
            Knowledge Graph <span className="text-violet-400">×</span> Faceted Search
          </h2>
          <p className="text-slate-400 mb-6 text-sm">
            Combining <span className="text-violet-400">semantic reasoning</span> with <span className="text-emerald-400">multi-dimensional filtering</span>
          </p>
          
          {/* Progress Steps - Now 4 steps */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            <span className="text-xs text-violet-300 px-3 py-1.5 bg-violet-500/20 rounded-full border border-violet-500/30">
              ✓ Loading ontology
            </span>
            <span className="text-xs text-violet-300 px-3 py-1.5 bg-violet-500/20 rounded-full border border-violet-500/30 animate-pulse">
              ⚡ Running OWL inference
            </span>
            <span className="text-xs text-emerald-300 px-3 py-1.5 bg-emerald-500/20 rounded-full border border-emerald-500/30">
              🔍 Building facet index
            </span>
            <span className="text-xs text-emerald-300 px-3 py-1.5 bg-emerald-500/20 rounded-full border border-emerald-500/30">
              📊 Computing counts
            </span>
          </div>
          
          {/* Rotating Facts Card */}
          <div className="bg-slate-800/50 backdrop-blur border border-violet-500/20 rounded-2xl p-5 mb-6 transition-all duration-500">
            <div className="flex items-start gap-4 text-left">
              <div className="text-3xl flex-shrink-0">{currentFact.icon}</div>
              <div>
                <h3 className="text-sm font-semibold text-violet-300 mb-1">{currentFact.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{currentFact.text}</p>
              </div>
            </div>
          </div>
          
          {/* Fact Indicators */}
          <div className="flex justify-center gap-1.5 mb-6">
            {kgFacts.map((_, idx) => (
              <div
                key={idx}
                className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                  idx === factIndex ? 'bg-violet-400 w-4' : 'bg-slate-600'
                }`}
              />
            ))}
          </div>
          
          {/* Patience Note */}
          <p className="text-[11px] text-slate-500 max-w-md mx-auto leading-relaxed">
            💡 This project combines two powerful technologies: <span className="text-violet-400">Knowledge Graphs</span> for semantic reasoning 
            and <span className="text-emerald-400">Faceted Search</span> for multi-dimensional exploration. First load takes a few seconds!
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-red-100 flex items-center justify-center">
            <X className="w-8 h-8 text-red-500" />
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">Connection Error</h2>
          <p className="text-slate-500 mb-4">{error}</p>
          <p className="text-xs text-slate-400 mb-4">Make sure the backend server is running on port 8000</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-emerald-500 text-white rounded-lg font-medium hover:bg-emerald-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-50">
      {/* Subtle background pattern - z-0 to stay behind content */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-slate-50 to-white pointer-events-none z-0" />
      
      {/* Header */}
      <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            {/* Left side - Logo */}
            <div className="flex items-center gap-2 sm:gap-4">
              <Link href="/" className="group flex items-center gap-2 text-slate-400 hover:text-emerald-600 transition-colors" title="Back to Home">
                <div className="p-1.5 sm:p-2 rounded-lg bg-slate-100 group-hover:bg-emerald-50 transition-colors">
                  <ArrowLeft className="w-4 h-4" />
                </div>
              </Link>
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
                  <Database className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <div>
                  <h1 className="font-bold text-slate-900 text-base sm:text-lg tracking-tight">Player Explorer</h1>
                  <p className="hidden sm:block text-xs text-slate-500 mt-0.5">Powered by Knowledge Graph and Faceted Search</p>
                </div>
              </div>
            </div>
            
            {/* Right side - Actions */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Gameweek Badge with Deadline Countdown */}
              {gameweek && (() => {
                const deadlineInfo = formatDeadlineCompact(gameweek.deadline_time);
                return (
                  <div className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg border transition-all ${
                    deadlineInfo.veryUrgent 
                      ? "bg-red-50 border-red-300 animate-pulse" 
                      : deadlineInfo.urgent 
                        ? "bg-amber-50 border-amber-300" 
                        : "bg-emerald-50 border-emerald-200/60"
                  }`}>
                    <Clock className={`w-3 h-3 ${
                      deadlineInfo.veryUrgent ? "text-red-600" : deadlineInfo.urgent ? "text-amber-600" : "text-emerald-600"
                    }`} />
                    <span className={`text-xs font-bold ${
                      deadlineInfo.veryUrgent ? "text-red-700" : deadlineInfo.urgent ? "text-amber-700" : "text-emerald-700"
                    }`}>GW {gameweek.id}</span>
                    <span className={`text-xs ${
                      deadlineInfo.veryUrgent ? "text-red-500" : deadlineInfo.urgent ? "text-amber-500" : "text-emerald-500"
                    }`}>•</span>
                    <span className={`text-xs font-semibold ${
                      deadlineInfo.veryUrgent ? "text-red-600" : deadlineInfo.urgent ? "text-amber-600" : "text-emerald-600"
                    }`}>
                      {deadlineInfo.veryUrgent && "⚠️ "}{deadlineInfo.text}
                  </span>
                </div>
                );
              })()}

              {/* Datasheet Button */}
              <Link
                href="/datasheet"
                className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-2 rounded-xl text-sm font-medium transition-all bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50"
                title="View Dataset Documentation"
              >
                <FileText className="w-4 h-4" />
                <span className="hidden sm:inline">Datasheet</span>
              </Link>

              {/* Desktop only badges */}

              {/* Comparison Mode Toggle - Icon only on mobile */}
              <button
                onClick={() => {
                  setCompareMode(!compareMode);
                  if (compareMode) clearComparison();
                }}
                className={`flex items-center gap-2 px-2 sm:px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  compareMode 
                    ? "bg-gradient-to-r from-violet-500 to-purple-500 text-white shadow-lg shadow-violet-500/25" 
                    : comparePlayers.length > 0
                    ? "bg-violet-100 text-violet-700 border border-violet-300 hover:bg-violet-200"
                    : "bg-white text-slate-600 border border-slate-200 hover:border-violet-300 hover:text-violet-600"
                }`}
              >
                <Scale className="w-4 h-4" />
                <span className="hidden sm:inline">{compareMode ? "Comparing..." : comparePlayers.length > 0 ? `Compare (${comparePlayers.length})` : "Compare"}</span>
              </button>
              
              {/* Saved Players Button */}
              <button
                onClick={() => setShowSavedPanel(!showSavedPanel)}
                className={`flex items-center gap-2 px-2 sm:px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  showSavedPanel 
                    ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg shadow-amber-500/25" 
                    : savedPlayers.length > 0
                    ? "bg-amber-100 text-amber-700 border border-amber-300 hover:bg-amber-200"
                    : "bg-white text-slate-600 border border-slate-200 hover:border-amber-300 hover:text-amber-600"
                }`}
              >
                <Bookmark className={`w-4 h-4 ${savedPlayers.length > 0 ? "fill-current" : ""}`} />
                <span className="hidden sm:inline">{savedPlayers.length > 0 ? `Saved (${savedPlayers.length})` : "Saved"}</span>
                {savedPlayers.length > 0 && <span className="sm:hidden text-xs">{savedPlayers.length}</span>}
              </button>
              
              {/* Filters Toggle */}
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  showFilters 
                    ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-lg shadow-emerald-500/25" 
                    : "bg-white text-slate-600 border border-slate-200 hover:border-emerald-300 hover:text-emerald-600"
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
                <span className="hidden sm:inline">Filters</span>
                {activeFilterCount > 0 && (
                  <span className={`w-5 h-5 rounded-full text-xs flex items-center justify-center font-bold ${
                    showFilters ? "bg-white/20 text-white" : "bg-emerald-500 text-white"
                  }`}>
                    {activeFilterCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Deadline Countdown */}
      <section className="relative z-10 bg-slate-50 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <DeadlineCountdown />
        </div>
      </section>

      {/* About This Tool - Concise Educational Cards with Tooltips */}
      <section className="relative z-10 bg-slate-50/80 border-b border-slate-200 py-4">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* RDF */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-violet-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-violet-100 group-hover:text-violet-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">Resource Description Framework</div>
                Instead of storing data in tables, RDF stores it as connections: &quot;Salah → playsFor → Liverpool&quot;. This lets us ask questions about relationships.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">🔗</div>
              <div className="text-xs font-bold text-slate-800 mb-1">RDF</div>
              <p className="text-[10px] text-slate-500 leading-tight">Data as connected triples: subject → predicate → object</p>
            </div>
            
            {/* OWL */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-violet-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-violet-100 group-hover:text-violet-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">Web Ontology Language</div>
                We define rules like &quot;if form {'>'} 7 AND available → Captain Candidate&quot;. OWL automatically applies these rules to all 756 players and creates Smart Tags.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">🦉</div>
              <div className="text-xs font-bold text-slate-800 mb-1">OWL Reasoning</div>
              <p className="text-[10px] text-slate-500 leading-tight">Auto-infers new facts. Creates Smart Tags automatically</p>
            </div>
            
            {/* SPARQL */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-violet-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-violet-100 group-hover:text-violet-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">SPARQL Query Language</div>
                Like SQL but for graphs. We can ask: &quot;Find all midfielders who play for teams with easy fixtures AND have form {'>'} 6&quot;. The graph structure makes complex queries easy.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">📊</div>
              <div className="text-xs font-bold text-slate-800 mb-1">SPARQL</div>
              <p className="text-[10px] text-slate-500 leading-tight">SQL for graphs. Query relationships, not just tables</p>
            </div>
            
            {/* Faceted Search */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-emerald-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-emerald-100 group-hover:text-emerald-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">Multi-dimensional Filtering</div>
                Like filtering products on Amazon by price AND brand AND rating at once. Each filter shows how many players match, so you never hit a dead end.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">🔍</div>
              <div className="text-xs font-bold text-slate-800 mb-1">Faceted Search</div>
              <p className="text-[10px] text-slate-500 leading-tight">Filter by multiple dimensions. See counts before clicking</p>
            </div>
            
            {/* Wikidata */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-blue-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-blue-100 group-hover:text-blue-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">Linked Open Data</div>
                Wikidata is Wikipedia&apos;s structured database. We link players to their Wikidata entries to fetch extra info like nationality, birth date, and career history.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">🌐</div>
              <div className="text-xs font-bold text-slate-800 mb-1">Wikidata</div>
              <p className="text-[10px] text-slate-500 leading-tight">Linked to 100M+ entities for enriched player data</p>
            </div>
            
            {/* Smart Tags */}
            <div className="group relative bg-white rounded-xl border border-slate-200 p-3 text-center hover:shadow-md hover:border-amber-300 transition-all">
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-slate-100 text-slate-400 text-[10px] flex items-center justify-center cursor-help group-hover:bg-amber-100 group-hover:text-amber-500 transition-colors">?</div>
              <div className="absolute hidden group-hover:block top-full left-1/2 -translate-x-1/2 mt-2 w-56 p-3 bg-slate-800 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
                <div className="font-semibold mb-1">Auto-classified Labels</div>
                Based on rules we define in our ontology, the system automatically tags players: &quot;Captain Pick&quot;, &quot;Differential&quot;, &quot;Injury Risk&quot;, etc. No manual labeling needed.
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-slate-800 rotate-45" />
              </div>
              <div className="text-2xl mb-1">🏷️</div>
              <div className="text-xs font-bold text-slate-800 mb-1">Smart Tags</div>
              <p className="text-[10px] text-slate-500 leading-tight">Auto-classified labels like &quot;Captain Pick&quot; or &quot;Differential&quot;</p>
            </div>
          </div>
        </div>
      </section>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
        <div className="flex gap-4 sm:gap-6">
          <div className="flex gap-4 sm:gap-6 flex-1 min-w-0">
              {/* Filters Sidebar - Mobile Overlay / Desktop Sidebar */}
              {showFilters && (
                <>
                  {/* Mobile Overlay Backdrop */}
                  <div 
                    className="fixed inset-0 bg-black/50 z-40 lg:hidden"
                    onClick={() => setShowFilters(false)}
                  />
                  {/* Filter Panel */}
                  <div className="fixed inset-y-0 left-0 w-[85%] max-w-sm z-50 lg:relative lg:w-64 lg:z-auto flex-shrink-0 lg:sticky lg:top-24">
                    <div className="h-full lg:h-[calc(100vh-120px)] bg-white lg:rounded-2xl shadow-xl shadow-slate-200/50 border-r lg:border border-slate-200/60 overflow-hidden flex flex-col">
                    {/* Filter Header */}
                    <div className="px-4 sm:px-5 py-4 bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 border-b border-violet-100/80">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 flex items-center justify-center shadow-lg shadow-violet-500/30">
                            <Filter className="w-4 h-4 text-white" />
                          </div>
                          <span className="font-bold text-slate-900">Player Filters</span>
                        </div>
                        <div className="flex items-center gap-2">
                        {activeFilterCount > 0 && (
                          <button
                            onClick={resetFilters}
                            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          >
                            <RotateCcw className="w-3 h-3" />
                            Reset
                          </button>
                        )}
                          {/* Mobile Close Button */}
                          <button
                            onClick={() => setShowFilters(false)}
                            className="lg:hidden p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                          >
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                      {/* Count and Sort Row */}
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">
                          <span className="font-semibold text-slate-800">{filteredPlayers.length}</span>
                          <span className="text-slate-400"> of </span>
                          <span className="text-slate-500">{allPlayers.length}</span>
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-400">Sort:</span>
                          <select
                            value={filters.sortBy}
                            onChange={(e) => updateFilter("sortBy", e.target.value as Filters["sortBy"])}
                            className="text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1 focus:border-violet-400 outline-none cursor-pointer"
                          >
                            <option value="form">🔥 Form</option>
                            <option value="points">📊 Points</option>
                            <option value="ppg">⚡ PPG</option>
                            <option value="xG">⚽ xG+xA</option>
                            <option value="price">💰 Price ↓</option>
                            <option value="priceAsc">💵 Price ↑</option>
                            <option value="ppm">📈 Pts/£m</option>
                            <option value="ownership">👥 Owned</option>
                            <option value="fdr">🟢 Fixtures</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 space-y-1 flex-1 overflow-y-auto bg-gradient-to-b from-white to-slate-50/30 scroll-smooth">
                      {/* OWL Inferred Classes - NEW SECTION */}
                      <div className="mb-4 pb-4 border-b border-slate-100">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Brain className={`w-4 h-4 text-violet-500 ${kgLoading ? 'animate-pulse' : ''}`} />
                            <span className="text-sm font-semibold text-slate-800">Smart Tags</span>
                          </div>
                          {kgLoading ? (
                            <span className="text-[9px] text-violet-600 bg-violet-100 px-1.5 py-0.5 rounded animate-pulse">Building KG...</span>
                          ) : (
                          <span className="text-[9px] text-violet-500 bg-violet-50 px-1.5 py-0.5 rounded">Auto-Inferred</span>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-500 mb-3 leading-relaxed">
                          Players are automatically classified based on their stats. Select multiple tags to combine filters.
                        </p>
                        <div className="space-y-1.5">
                          {OWL_CLASS_PRESETS.map((cls) => {
                            const count = facetCounts.smartTags[cls.id] || 0;
                            return (
                            <button
                              key={cls.id}
                              onClick={() => toggleOwlClass(cls.id)}
                              className={`w-full p-2.5 text-left rounded-lg transition-all border group ${
                                filters.inferredClasses.includes(cls.id)
                                  ? "bg-violet-500 text-white border-violet-500 shadow-md"
                                  : `${cls.color} hover:shadow-sm`
                              } ${count === 0 ? "opacity-40" : ""}`}
                              title={cls.rule}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="text-base">{cls.icon}</span>
                                  <div>
                                    <span className={`text-xs font-semibold block ${
                                      filters.inferredClasses.includes(cls.id) ? "text-white" : ""
                                    }`}>
                                      {cls.name}
                                    </span>
                                    <span className={`text-[9px] block leading-tight ${
                                      filters.inferredClasses.includes(cls.id) ? "text-white/80" : "text-slate-500"
                                    }`}>
                                      {cls.description}
                                    </span>
                                  </div>
                                </div>
                                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                    filters.inferredClasses.includes(cls.id) 
                                      ? "bg-white/20 text-white" 
                                      : "bg-white/80 text-slate-600"
                                  }`}>
                                  {count}
                                  </span>
                              </div>
                            </button>
                          );})}
                        </div>
                      </div>

                      {/* Activity-Based Presets - "What are you doing?" */}
                      <div className="mb-4 pb-4 border-b border-slate-100">
                        <div className="flex items-center gap-2 mb-2">
                          <Target className="w-4 h-4 text-violet-500" />
                          <span className="text-sm font-semibold text-slate-800">What are you doing?</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mb-2">Quick filters based on your goal</p>
                        <div className="flex flex-wrap gap-1.5">
                          {ACTIVITY_PRESETS.map((preset) => (
                            <button
                              key={preset.id}
                              onClick={() => {
                                if (preset.inferredClass) {
                                  setFilters(prev => ({
                                    ...DEFAULT_FILTERS,
                                    inferredClasses: [preset.inferredClass!]
                                  }));
                                } else if (preset.filters) {
                                  setFilters(prev => ({
                                    ...DEFAULT_FILTERS,
                                    ...preset.filters
                                  }));
                                }
                                setActivePreset(preset.id);
                              }}
                              className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
                                activePreset === preset.id
                                  ? "bg-violet-500 text-white shadow-md"
                                  : "bg-violet-50 text-violet-700 hover:bg-violet-100 border border-violet-200"
                              }`}
                              title={preset.description}
                            >
                              <span>{preset.icon}</span>
                              <span>{preset.name}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Smart Presets with Counts */}
                      <div className="mb-4 pb-4 border-b border-slate-100">
                        <div className="flex items-center gap-2 mb-3">
                          <Sparkles className="w-4 h-4 text-amber-500" />
                          <span className="text-sm font-semibold text-slate-800">Smart Presets</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          {SMART_PRESETS.map((preset) => {
                            const count = facetCounts.presets?.[preset.id] || 0;
                            return (
                            <button
                              key={preset.id}
                              onClick={() => applyPreset(preset)}
                              className={`p-2 text-left rounded-lg transition-all ${
                                activePreset === preset.id
                                  ? "bg-emerald-100 border-2 border-emerald-500"
                                  : "bg-slate-50 hover:bg-slate-100 border-2 border-transparent"
                                } ${count === 0 ? "opacity-40" : ""}`}
                              title={preset.description}
                            >
                                <div className="flex items-center justify-between">
                              <span className="text-sm">{preset.icon}</span>
                                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                                    activePreset === preset.id 
                                      ? "bg-emerald-200 text-emerald-700" 
                                      : "bg-slate-200 text-slate-500"
                                  }`}>{count}</span>
                                </div>
                              <span className="text-[10px] font-medium text-slate-700 block truncate">{preset.name}</span>
                            </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Search */}
                      <div className="relative mb-4">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                          type="text"
                          placeholder="Search players..."
                          value={filters.search}
                          onChange={(e) => updateFilter("search", e.target.value)}
                          className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-900 bg-white placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all"
                        />
                      </div>

                      {/* Position Filter with Counts */}
                      <FilterSection title="Position">
                        <div className="grid grid-cols-4 gap-1.5">
                          {([
                            { pos: "GKP" as const, icon: "🧤", label: "GK" },
                            { pos: "DEF" as const, icon: "🛡️", label: "DEF" },
                            { pos: "MID" as const, icon: "⚡", label: "MID" },
                            { pos: "FWD" as const, icon: "⚽", label: "FWD" },
                          ]).map(({ pos, icon, label }) => (
                            <button
                              key={pos}
                              onClick={() => togglePosition(pos)}
                              className={`flex flex-col items-center gap-0.5 py-2 px-1 rounded-xl border transition-all ${
                                filters.positions.includes(pos)
                                  ? `${POSITION_COLORS[pos].badge} text-white border-transparent shadow-sm`
                                  : `${POSITION_COLORS[pos].bg} ${POSITION_COLORS[pos].text} border-slate-200 hover:border-slate-300`
                              } ${facetCounts.positions[pos] === 0 ? "opacity-40" : ""}`}
                            >
                              <span className="text-base">{icon}</span>
                              <span className="text-[10px] font-bold">{label}</span>
                              <span className={`text-[9px] font-mono ${
                                filters.positions.includes(pos) ? "text-white/80" : "text-slate-400"
                              }`}>({facetCounts.positions[pos]})</span>
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* Team Filter with Counts */}
                      <FilterSection title="Team" defaultOpen={false}>
                        <div className="grid grid-cols-4 gap-1 max-h-52 overflow-y-auto pr-1">
                          {ALL_TEAMS.map((team) => (
                            <button
                              key={team.short}
                              onClick={() => toggleTeam(team.short)}
                              title={`${team.name} (${facetCounts.teams[team.short] || 0} players)`}
                              className={`px-1.5 py-1 text-[10px] font-bold rounded-lg text-center border transition-all ${
                                filters.teams.includes(team.short)
                                  ? "bg-emerald-500 text-white border-emerald-500 shadow-sm ring-2 ring-emerald-200"
                                  : `${team.bg} ${team.text} ${team.border} hover:opacity-80`
                              } ${(facetCounts.teams[team.short] || 0) === 0 ? "opacity-40" : ""}`}
                            >
                              <div>{team.short}</div>
                              <div className={`text-[8px] font-mono ${
                                filters.teams.includes(team.short) ? "text-white/70" : "text-slate-400"
                              }`}>{facetCounts.teams[team.short] || 0}</div>
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* Price Filter */}
                      <FilterSection title="Price">
                        <div className="grid grid-cols-2 gap-1.5">
                          {[
                            { label: "All", value: [3.5, 15] as [number, number] },
                            { label: "Budget", value: [3.5, 6] as [number, number] },
                            { label: "Mid", value: [6, 10] as [number, number] },
                            { label: "Premium", value: [10, 15] as [number, number] },
                          ].map((preset) => (
                            <button
                              key={preset.label}
                              onClick={() => updateFilter("priceRange", preset.value)}
                              className={`px-2 py-1.5 text-[11px] rounded-lg border transition-all ${
                                filters.priceRange[0] === preset.value[0] && filters.priceRange[1] === preset.value[1]
                                  ? "bg-emerald-500 text-white font-semibold border-emerald-500"
                                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                              }`}
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* Form Filter */}
                      <FilterSection title="Form">
                        <div className="grid grid-cols-2 gap-1.5">
                          {[
                            { label: "All", value: [0, 10] as [number, number] },
                            { label: "Hot 🔥", value: [5, 10] as [number, number] },
                            { label: "Warm", value: [3, 5] as [number, number] },
                            { label: "Cold ❄️", value: [0, 3] as [number, number] },
                          ].map((preset) => (
                            <button
                              key={preset.label}
                              onClick={() => updateFilter("formRange", preset.value)}
                              className={`px-2 py-1.5 text-[11px] rounded-lg border transition-all ${
                                filters.formRange[0] === preset.value[0] && filters.formRange[1] === preset.value[1]
                                  ? "bg-emerald-500 text-white font-semibold border-emerald-500"
                                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                              }`}
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* Ownership Filter */}
                      <FilterSection title="Ownership">
                        <div className="grid grid-cols-2 gap-1.5">
                          {[
                            { label: "All", value: [0, 100] as [number, number] },
                            { label: "Template", value: [20, 100] as [number, number] },
                            { label: "Mid", value: [5, 20] as [number, number] },
                            { label: "Diff 💎", value: [0, 5] as [number, number] },
                          ].map((preset) => (
                            <button
                              key={preset.label}
                              onClick={() => updateFilter("ownershipRange", preset.value)}
                              className={`px-2 py-1.5 text-[11px] rounded-lg border transition-all ${
                                filters.ownershipRange[0] === preset.value[0] && filters.ownershipRange[1] === preset.value[1]
                                  ? "bg-emerald-500 text-white font-semibold border-emerald-500"
                                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                              }`}
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* FDR Filter */}
                      <FilterSection title="Fixture Difficulty">
                        <div className="grid grid-cols-2 gap-1.5">
                          {[
                            { label: "All", value: [1, 5] as [number, number] },
                            { label: "Easy 🟢", value: [1, 2.5] as [number, number] },
                            { label: "Medium", value: [2, 3.5] as [number, number] },
                            { label: "Hard 🔴", value: [3.5, 5] as [number, number] },
                          ].map((preset) => (
                            <button
                              key={preset.label}
                              onClick={() => updateFilter("fdrRange", preset.value)}
                              className={`px-2 py-1.5 text-[11px] rounded-lg border transition-all ${
                                filters.fdrRange[0] === preset.value[0] && filters.fdrRange[1] === preset.value[1]
                                  ? "bg-emerald-500 text-white font-semibold border-emerald-500"
                                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                              }`}
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                      {/* Availability Filter */}
                      <FilterSection title="Availability">
                        <div className="grid grid-cols-3 gap-1.5">
                          {[
                            { key: "available" as const, label: "Available", dot: "bg-emerald-500" },
                            { key: "doubtful" as const, label: "Doubtful", dot: "bg-amber-500" },
                            { key: "injured" as const, label: "Out", dot: "bg-red-500" },
                          ].map((status) => (
                            <button
                              key={status.key}
                              onClick={() => toggleStatus(status.key)}
                              className={`flex items-center justify-center gap-1.5 px-2 py-2 text-[11px] rounded-lg border transition-all ${
                                filters.status.includes(status.key)
                                  ? "bg-emerald-500 text-white font-semibold border-emerald-500"
                                  : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                              }`}
                            >
                              <span className={`w-2 h-2 rounded-full ${filters.status.includes(status.key) ? "bg-white" : status.dot}`} />
                              {status.label}
                            </button>
                          ))}
                        </div>
                      </FilterSection>

                    </div>
                  </div>
                </div>
                </>
              )}

              {/* Player Grid */}
              <div className="flex-1 min-w-0 lg:sticky lg:top-24">
                <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200/60 overflow-hidden lg:h-[calc(100vh-120px)] flex flex-col">
                  {/* Scrollable container for mobile */}
                  <div className="overflow-x-auto flex-1 flex flex-col">
                    <div className="min-w-[600px] flex flex-col flex-1">
                  {/* Grid Header */}
                      <div className={`sticky top-0 z-10 grid ${compareMode ? "grid-cols-[28px_32px_minmax(140px,1fr)_50px_50px_50px_50px_60px]" : "grid-cols-[28px_minmax(140px,1fr)_50px_50px_50px_50px_60px]"} gap-1 sm:gap-2 px-3 sm:px-5 py-3 sm:py-3.5 bg-gradient-to-r from-slate-50 to-white border-b border-slate-100`}>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-400">#</div>
                    {compareMode && <div></div>}
                        <div className="text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">Player</div>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">Price</div>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">Form</div>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">Pts</div>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">Own%</div>
                        <div className="text-center text-[10px] sm:text-xs font-bold text-slate-600 uppercase tracking-wide">FDR</div>
                  </div>

                  {/* Active Filter Pills */}
                  {activeFilterCount > 0 && (
                    <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-slate-500 font-medium">Active:</span>
                      {filters.positions.length > 0 && filters.positions.map(pos => (
                        <button
                          key={pos}
                          onClick={() => togglePosition(pos)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-full text-xs text-slate-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                        >
                          {pos}
                          <X className="w-3 h-3 text-slate-400 group-hover:text-red-500" />
                        </button>
                      ))}
                      {filters.teams.length > 0 && filters.teams.map(team => (
                        <button
                          key={team}
                          onClick={() => toggleTeam(team)}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-full text-xs text-slate-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                        >
                          {team}
                          <X className="w-3 h-3 text-slate-400 group-hover:text-red-500" />
                        </button>
                      ))}
                      {filters.inferredClasses.length > 0 && filters.inferredClasses.map(cls => {
                        const classInfo = OWL_CLASS_PRESETS.find(c => c.id === cls);
                        return (
                          <button
                            key={cls}
                            onClick={() => toggleOwlClass(cls)}
                            className="inline-flex items-center gap-1 px-2 py-1 bg-violet-100 border border-violet-200 rounded-full text-xs text-violet-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                          >
                            {classInfo?.icon} {classInfo?.name || cls}
                            <X className="w-3 h-3 text-violet-400 group-hover:text-red-500" />
                          </button>
                        );
                      })}
                      {(filters.priceRange[0] > 3.5 || filters.priceRange[1] < 15) && (
                        <button
                          onClick={() => updateFilter("priceRange", [3.5, 15])}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-full text-xs text-slate-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                        >
                          £{filters.priceRange[0]}-{filters.priceRange[1]}m
                          <X className="w-3 h-3 text-slate-400 group-hover:text-red-500" />
                        </button>
                      )}
                      {filters.formRange[0] > 0 && (
                        <button
                          onClick={() => updateFilter("formRange", [0, 10])}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-full text-xs text-slate-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                        >
                          Form {filters.formRange[0]}+
                          <X className="w-3 h-3 text-slate-400 group-hover:text-red-500" />
                        </button>
                      )}
                      {filters.search && (
                        <button
                          onClick={() => updateFilter("search", "")}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-slate-200 rounded-full text-xs text-slate-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors group"
                        >
                          "{filters.search}"
                          <X className="w-3 h-3 text-slate-400 group-hover:text-red-500" />
                        </button>
                      )}
                      <button
                        onClick={resetFilters}
                        className="text-xs text-red-500 hover:text-red-600 font-medium ml-2"
                      >
                        Clear all
                      </button>
                    </div>
                  )}

                  {/* Player Rows */}
                  <div className="overflow-y-auto flex-1">
                    {filteredPlayers.length === 0 ? (
                      <div className="p-8 text-center">
                        <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <p className="text-lg font-semibold text-slate-700 mb-2">No players match your filters</p>
                        <p className="text-sm text-slate-500 mb-4">
                          {filters.positions.length > 0 && `Only ${facetCounts.positions[filters.positions[0]] || 0} ${filters.positions[0]}s match other filters. `}
                          {filters.formRange[0] > 5 && `High form requirement (${filters.formRange[0]}+) may be too restrictive. `}
                          {filters.inferredClasses.length > 2 && "Too many Smart Tags selected. "}
                          Try removing some filters to see more results.
                        </p>
                        <div className="flex justify-center gap-3">
                        <button
                          onClick={resetFilters}
                            className="px-4 py-2 bg-emerald-500 text-white rounded-lg text-sm font-medium hover:bg-emerald-600 transition-colors"
                        >
                            Reset all filters
                        </button>
                          {filters.formRange[0] > 0 && (
                            <button
                              onClick={() => updateFilter("formRange", [0, 10])}
                              className="px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                            >
                              Remove form filter
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      filteredPlayers.map((player, index) => {
                        const statusInfo = getStatusIndicator(player.status);
                        const isSelected = selectedPlayer?.id === player.id;
                        const isInComparison = comparePlayers.some(p => p.id === player.id);
                        const posColors = POSITION_COLORS[player.position];
                        const playerClasses = playerClassesCache.get(player.id) || [];
                        
                        const getFDRColor = (fdr?: number) => {
                          if (!fdr) return "bg-slate-100 text-slate-500";
                          if (fdr <= 2) return "bg-emerald-100 text-emerald-700";
                          if (fdr <= 3) return "bg-amber-100 text-amber-700";
                          if (fdr <= 4) return "bg-orange-100 text-orange-700";
                          return "bg-red-100 text-red-700";
                        };

                        return (
                          <div
                            key={player.id}
                            onClick={() => {
                              if (compareMode) {
                                toggleComparePlayer(player);
                              } else {
                                setSelectedPlayer(player);
                              }
                            }}
                            className={`grid ${compareMode ? "grid-cols-[28px_32px_minmax(140px,1fr)_50px_50px_50px_50px_60px]" : "grid-cols-[28px_minmax(140px,1fr)_50px_50px_50px_50px_60px]"} gap-1 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 border-b border-slate-100/80 hover:bg-gradient-to-r hover:from-slate-50 hover:to-white cursor-pointer transition-all ${
                              isSelected ? "bg-emerald-50/50 border-l-4 border-l-emerald-500" : ""
                            } ${isInComparison ? "bg-violet-50/50 border-l-4 border-l-violet-500" : ""}`}
                          >
                            {/* Row Number */}
                            <div className="flex items-center justify-center">
                              <span className="text-xs text-slate-400 font-medium">{index + 1}</span>
                            </div>
                            
                            {/* Comparison Checkbox */}
                            {compareMode && (
                              <div className="flex items-center justify-center">
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                                  isInComparison 
                                    ? "bg-violet-500 border-violet-500" 
                                    : "border-slate-300 hover:border-violet-400"
                                }`}>
                                  {isInComparison && (
                                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                    </svg>
                                  )}
                                </div>
                              </div>
                            )}
                            
                            {/* Player Info */}
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-sm flex-shrink-0">{statusInfo.icon}</span>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className={`text-[9px] font-bold px-1 py-0.5 rounded flex-shrink-0 ${posColors.badge} text-white`}>
                                    {player.position}
                                  </span>
                                  <span className="font-medium text-slate-800 text-sm">{player.webName}</span>
                                  {/* OWL Class Badges */}
                                  {playerClasses.slice(0, 2).map(cls => {
                                    const classInfo = OWL_CLASS_PRESETS.find(c => c.id === cls);
                                    return classInfo ? (
                                      <span key={cls} className="text-[8px]" title={classInfo.name}>
                                        {classInfo.icon}
                                      </span>
                                    ) : null;
                                  })}
                                </div>
                                <div className="flex items-center gap-1">
                                  <span className="text-[11px] text-slate-500">{player.teamShort}</span>
                                  {player.nextFixtures && player.nextFixtures[0] && (
                                    <span className="text-[10px] text-slate-400">
                                      • {player.nextFixtures[0].isHome ? "H" : "A"} {player.nextFixtures[0].opponent}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Price */}
                            <div className="flex items-center justify-center">
                              <span className="text-xs font-medium text-slate-700">£{player.price.toFixed(1)}</span>
                            </div>

                            {/* Form */}
                            <div className="flex items-center justify-center">
                              <span className={`text-xs font-bold ${
                                player.form >= 6 ? "text-emerald-600" : player.form < 3 ? "text-red-500" : "text-slate-600"
                              }`}>
                                {player.form.toFixed(1)}
                              </span>
                            </div>

                            {/* Points */}
                            <div className="flex items-center justify-center">
                              <span className="text-xs font-medium text-slate-700">{player.totalPoints}</span>
                            </div>

                            {/* Ownership */}
                            <div className="flex items-center justify-center">
                              <span className={`text-xs font-medium ${
                                player.ownership > 25 ? "text-blue-600" : player.ownership < 5 ? "text-purple-600" : "text-slate-600"
                              }`}>
                                {player.ownership.toFixed(0)}%
                              </span>
                            </div>
                            
                            {/* FDR */}
                            <div className="flex items-center justify-center">
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${getFDRColor(player.avgFDR)}`}>
                                {player.avgFDR ? player.avgFDR.toFixed(1) : "..."}
                              </span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                    </div>
                  </div>
                </div>
              </div>

          {/* Right Side: Enhanced Player Detail Card */}
          {selectedPlayer && (
            <div className="hidden lg:block w-[25%] flex-shrink-0 min-w-[320px] max-w-[360px]">
              <div className="bg-gradient-to-b from-white to-slate-50/30 rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200/60 overflow-hidden sticky top-24 h-[calc(100vh-120px)] overflow-y-auto scroll-smooth">
                {/* Player Header */}
                <div className={`p-4 bg-gradient-to-br ${
                  selectedPlayer.position === "GKP" ? "from-amber-50 to-orange-50" :
                  selectedPlayer.position === "DEF" ? "from-emerald-50 to-green-50" :
                  selectedPlayer.position === "MID" ? "from-blue-50 to-indigo-50" :
                  "from-red-50 to-rose-50"
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-bold px-2 py-1 rounded-lg ${POSITION_COLORS[selectedPlayer.position].badge} text-white`}>
                      {selectedPlayer.position}
                    </span>
                    <span className="text-lg">{getStatusIndicator(selectedPlayer.status).icon}</span>
                    <span className="text-xl font-bold text-slate-800 ml-auto font-mono">£{selectedPlayer.price.toFixed(1)}m</span>
                    <button
                      onClick={() => setSelectedPlayer(null)}
                      className="p-1.5 rounded-lg bg-white/80 hover:bg-red-50 hover:text-red-500 transition-all"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <h2 className="text-xl font-bold text-slate-900">{selectedPlayer.webName}</h2>
                  <p className="text-sm text-slate-600 mb-2">{selectedPlayer.team}</p>
                  
                  {/* Save Button */}
                  <button
                    onClick={() => {
                      if (isPlayerSaved(selectedPlayer.id)) {
                        removeFromSaved(selectedPlayer.id);
                      } else {
                        addToSaved(selectedPlayer);
                      }
                    }}
                    className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                      isPlayerSaved(selectedPlayer.id)
                        ? "bg-violet-500 text-white shadow-lg shadow-violet-500/25"
                        : "bg-white text-slate-700 border border-slate-200 hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700"
                    }`}
                  >
                    <Bookmark className={`w-4 h-4 ${isPlayerSaved(selectedPlayer.id) ? "fill-current" : ""}`} />
                    {isPlayerSaved(selectedPlayer.id) ? "Saved" : "Save Player"}
                  </button>
                  
                  {selectedPlayer.news && (
                    <div className="mt-2 p-2 bg-amber-100/80 rounded-lg">
                      <p className="text-[10px] text-amber-800 flex items-start gap-1.5">
                        <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                        {selectedPlayer.news}
                      </p>
                    </div>
                  )}
                </div>

                {/* Tab Navigation */}
                <div className="flex border-b border-slate-200 bg-slate-50/50">
                  {[
                    { id: "overview", label: "Overview", icon: "📊" },
                    { id: "graph", label: "Graph", icon: "🕸️" },
                    { id: "injury", label: "Injury", icon: "🏥" },
                    { id: "inference", label: "Smart Tags", icon: "🧠" },
                    { id: "similar", label: "Similar", icon: "👥" },
                    { id: "provenance", label: "Source", icon: "📜" },
                    { id: "wikidata", label: "Wiki", icon: "🌐" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveCardTab(tab.id as any)}
                      className={`flex-1 px-2 py-2 text-[10px] font-medium transition-all ${
                        activeCardTab === tab.id
                          ? "bg-white text-violet-700 border-b-2 border-violet-500"
                          : "text-slate-500 hover:text-slate-700 hover:bg-white/50"
                      }`}
                    >
                      <span className="block text-sm mb-0.5">{tab.icon}</span>
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="p-3">
                  {/* Overview Tab */}
                  {activeCardTab === "overview" && (
                    <>
                      {/* Stats Grid */}
                      <div className="grid grid-cols-3 gap-2 mb-3">
                        <div className="bg-slate-50 rounded-lg p-2 text-center">
                          <p className="text-[9px] text-slate-400 uppercase">Form</p>
                          <p className={`text-lg font-bold ${selectedPlayer.form >= 6 ? "text-emerald-600" : "text-slate-800"}`}>
                            {selectedPlayer.form.toFixed(1)}
                          </p>
                        </div>
                        <div className="bg-slate-50 rounded-lg p-2 text-center">
                          <p className="text-[9px] text-slate-400 uppercase">Points</p>
                          <p className="text-lg font-bold text-slate-800">{selectedPlayer.totalPoints}</p>
                        </div>
                        <div className="bg-slate-50 rounded-lg p-2 text-center">
                          <p className="text-[9px] text-slate-400 uppercase">Own%</p>
                          <p className="text-lg font-bold text-slate-800">{selectedPlayer.ownership.toFixed(0)}%</p>
                        </div>
                      </div>

                      {/* Smart Tags with "Why This Tag?" */}
                      {playerExplanation && (
                        <div className="mb-3">
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide">🏷️ Smart Tags</p>
                            <span className="text-[9px] text-slate-400">OWL Reasoning</span>
                          </div>
                          <div className="space-y-2">
                            {playerExplanation.explanations
                              .filter((exp: any) => exp.matched)
                              .map((exp: any) => {
                                const classInfo = OWL_CLASS_PRESETS.find(c => c.id === exp.tag_id);
                                return classInfo ? (
                                  <div key={exp.tag_id} className={`rounded-lg overflow-hidden border ${classInfo.color}`}>
                                    <div className="p-2">
                                    <div className="flex items-center justify-between mb-1">
                                      <div className="flex items-center gap-1.5">
                                        <span className="text-sm">{classInfo.icon}</span>
                                        <span className="text-[11px] font-semibold">{classInfo.name}</span>
                                      </div>
                                      <span className="text-[10px] font-bold bg-white/50 px-1.5 py-0.5 rounded">
                                        {exp.strength.toFixed(0)}%
                                      </span>
                                    </div>
                                    {/* Strength Bar */}
                                      <div className="h-1 bg-white/30 rounded-full overflow-hidden mb-1.5">
                                      <div 
                                        className="h-full bg-current opacity-60 rounded-full transition-all"
                                        style={{ width: `${exp.strength}%` }}
                                      />
                                      </div>
                                      {/* Why This Tag? */}
                                      <div className="text-[9px] opacity-80 flex items-start gap-1">
                                        <span className="font-medium">Why?</span>
                                        <span>{classInfo.whyTag ? classInfo.whyTag(selectedPlayer) : classInfo.rule}</span>
                                      </div>
                                    </div>
                                  </div>
                                ) : null;
                              })}
                          </div>
                        </div>
                      )}

                      {/* Fixture Ticker */}
                      <div className="mb-3">
                        <div className="flex items-center gap-1.5 mb-2">
                          <Calendar className="w-3 h-3 text-slate-500" />
                          <span className="text-[10px] font-semibold text-slate-700">Next 5 Fixtures</span>
                        </div>
                        {playerFDR ? (
                          <div className="flex gap-1">
                            {playerFDR.fixtures.slice(0, 5).map((fix, idx) => {
                              const getDiffColor = (diff: number) => {
                                if (diff <= 2) return "bg-emerald-500";
                                if (diff === 3) return "bg-amber-400";
                                if (diff === 4) return "bg-orange-500";
                                return "bg-red-500";
                              };
                              return (
                                <div key={idx} className={`flex-1 ${getDiffColor(fix.difficulty)} rounded py-1 text-center`}>
                                  <span className="text-[8px] font-bold text-white block">{fix.opponent}</span>
                                  <span className="text-[7px] text-white/80">{fix.isHome ? "H" : "A"}</span>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="flex items-center justify-center py-2">
                            <Loader2 className="w-3 h-3 animate-spin text-slate-400" />
                          </div>
                        )}
                      </div>

                      {/* Extended Stats */}
                      <div className="bg-slate-50 rounded-lg p-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                        <div className="flex justify-between"><span className="text-slate-500">Goals</span><span className="font-medium">{selectedPlayer.goals}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">Assists</span><span className="font-medium">{selectedPlayer.assists}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">Minutes</span><span className="font-medium">{selectedPlayer.minutes}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">Bonus</span><span className="font-medium">{selectedPlayer.bonus}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">PPG</span><span className="font-medium">{selectedPlayer.pointsPerGame.toFixed(1)}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">xGI</span><span className="font-medium">{(selectedPlayer.xG + selectedPlayer.xA).toFixed(1)}</span></div>
                      </div>

                      {/* Provenance Display - Data Sources */}
                      <div className="mt-3 pt-3 border-t border-slate-100">
                        <p className="text-[9px] font-semibold text-slate-500 uppercase tracking-wide mb-2">📚 Data Sources</p>
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2 text-[10px]">
                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                            <span className="text-slate-600">Stats & Fixtures</span>
                            <span className="text-slate-400 ml-auto">FPL API</span>
                          </div>
                          {playerExplanation && playerExplanation.explanations.some((e: any) => e.matched) && (
                            <div className="flex items-center gap-2 text-[10px]">
                              <span className="w-2 h-2 rounded-full bg-violet-500"></span>
                              <span className="text-slate-600">Smart Tags</span>
                              <span className="text-slate-400 ml-auto">OWL Reasoning</span>
                            </div>
                          )}
                          {playerWikidata?.found && (
                            <div className="flex items-center gap-2 text-[10px]">
                              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                              <span className="text-slate-600">Bio & Career</span>
                              <span className="text-slate-400 ml-auto">Wikidata</span>
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-[10px]">
                            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                            <span className="text-slate-600">Graph Structure</span>
                            <span className="text-slate-400 ml-auto">RDF/SPARQL</span>
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* Graph Visualization Tab */}
                  {activeCardTab === "graph" && (
                    <div className="space-y-3">
                      {!playerNeighborhood ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="w-5 h-5 animate-spin text-violet-500" />
                          <span className="ml-2 text-sm text-slate-500">Loading graph...</span>
                        </div>
                      ) : (
                        <>
                          {/* Graph Stats */}
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-semibold text-violet-600">Knowledge Graph Neighborhood</span>
                            </div>
                            <span className="text-[9px] text-slate-400">
                              {playerNeighborhood.node_count} nodes • {playerNeighborhood.link_count} links
                            </span>
                          </div>
                          
                          {/* Graph Container */}
                          <div className="bg-slate-900 rounded-lg overflow-hidden" style={{ height: '280px' }}>
                            <PlayerNeighborhoodGraph 
                              nodes={playerNeighborhood.nodes} 
                              links={playerNeighborhood.links}
                            />
                          </div>
                          
                          {/* Legend */}
                          <div className="bg-slate-50 rounded-lg p-2">
                            <p className="text-[9px] font-semibold text-slate-600 mb-2">Node Types</p>
                            <div className="flex flex-wrap gap-2">
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                                <span className="text-[8px] text-slate-600">Player</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                <span className="text-[8px] text-slate-600">Team</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                                <span className="text-[8px] text-slate-600">Position</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-violet-500"></span>
                                <span className="text-[8px] text-slate-600">Similar</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
                                <span className="text-[8px] text-slate-600">Smart Tag</span>
                              </div>
                            </div>
                          </div>
                          
                          {/* RDF Info */}
                          <div className="p-2 bg-violet-50 rounded-lg border border-violet-200">
                            <p className="text-[9px] font-semibold text-violet-700 mb-1">🕸️ About This Graph</p>
                            <p className="text-[9px] text-violet-600 leading-relaxed">
                              This visualization shows the player&apos;s immediate connections in the Knowledge Graph.
                              Each node represents an RDF resource, and edges represent semantic relationships (predicates).
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Injury Analysis Tab (NLP-parsed) */}
                  {activeCardTab === "injury" && (
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
                          <p className="text-[10px] text-emerald-600 mt-1">No injury or availability concerns</p>
                        </div>
                      ) : (
                        <>
                          {/* Current Status Header */}
                          <div className={`p-3 rounded-lg border ${
                            playerInjuryAnalysis.parsed?.severity === "out" ? "bg-red-50 border-red-200" :
                            playerInjuryAnalysis.parsed?.severity === "suspended" ? "bg-slate-100 border-slate-300" :
                            playerInjuryAnalysis.parsed?.severity === "major" ? "bg-orange-50 border-orange-200" :
                            playerInjuryAnalysis.parsed?.severity === "doubtful" ? "bg-amber-50 border-amber-200" :
                            "bg-yellow-50 border-yellow-200"
                          }`}>
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-[10px] font-semibold text-slate-600">Current Status</span>
                              <span className="text-sm font-bold">
                                {playerInjuryAnalysis.parsed?.severity_display}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-700 bg-white/60 p-2 rounded">
                              {playerInjuryAnalysis.fpl_api_data?.news || "No news available"}
                            </p>
                          </div>

                          {/* Parsed Details */}
                          <div className="bg-white rounded-lg border border-slate-200 p-3">
                            <p className="text-[10px] font-semibold text-slate-600 mb-2 flex items-center gap-1">
                              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                              NLP-Extracted Details
                            </p>
                            <div className="space-y-1.5">
                              {playerInjuryAnalysis.parsed?.injury_type && (
                                <div className="flex items-center justify-between text-[10px]">
                                  <span className="text-slate-500">Injury Type</span>
                                  <span className="font-medium text-slate-800">
                                    {playerInjuryAnalysis.parsed.injury_type_display}
                                  </span>
                                </div>
                              )}
                              {playerInjuryAnalysis.parsed?.chance_of_playing !== null && (
                                <div className="flex items-center justify-between text-[10px]">
                                  <span className="text-slate-500">Chance of Playing</span>
                                  <span className={`font-bold ${
                                    playerInjuryAnalysis.parsed.chance_of_playing >= 75 ? "text-emerald-600" :
                                    playerInjuryAnalysis.parsed.chance_of_playing >= 50 ? "text-amber-600" :
                                    "text-red-600"
                                  }`}>
                                    {playerInjuryAnalysis.parsed.chance_of_playing}%
                                  </span>
                                </div>
                              )}
                              {playerInjuryAnalysis.parsed?.expected_return && (
                                <div className="flex items-center justify-between text-[10px]">
                                  <span className="text-slate-500">Expected Return</span>
                                  <span className="font-medium text-slate-800">
                                    {playerInjuryAnalysis.parsed.expected_return}
                                  </span>
                                </div>
                              )}
                              {playerInjuryAnalysis.parsed?.is_suspension && (
                                <div className="flex items-center justify-between text-[10px]">
                                  <span className="text-slate-500">Suspension</span>
                                  <span className="font-medium text-red-600">
                                    {playerInjuryAnalysis.parsed.suspension_matches} match{playerInjuryAnalysis.parsed.suspension_matches !== 1 ? "es" : ""}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Risk Assessment */}
                          {playerInjuryAnalysis.risk_assessment?.recurrence_risk && (
                            <div className={`p-3 rounded-lg border ${
                              playerInjuryAnalysis.risk_assessment.recurrence_risk === "high" 
                                ? "bg-red-50 border-red-200" 
                                : playerInjuryAnalysis.risk_assessment.recurrence_risk === "medium"
                                ? "bg-amber-50 border-amber-200"
                                : "bg-green-50 border-green-200"
                            }`}>
                              <p className="text-[10px] font-semibold mb-2 flex items-center gap-1">
                                <span className="w-2 h-2 bg-current rounded-full"></span>
                                {playerInjuryAnalysis.risk_assessment.recurrence_risk_display}
                              </p>
                              <p className="text-[10px] leading-relaxed">
                                {playerInjuryAnalysis.risk_assessment.risk_reason}
                              </p>
                              {playerInjuryAnalysis.risk_assessment.medical_info && (
                                <div className="mt-2 pt-2 border-t border-current/20 text-[9px] space-y-1">
                                  <div className="flex justify-between">
                                    <span className="opacity-70">Recurrence Rate:</span>
                                    <span className="font-bold">{playerInjuryAnalysis.risk_assessment.medical_info.recurrence_rate}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="opacity-70">Typical Recovery:</span>
                                    <span>{playerInjuryAnalysis.risk_assessment.medical_info.typical_recovery}</span>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Recommendations */}
                          {playerInjuryAnalysis.recommendations?.length > 0 && (
                            <div className="space-y-1.5">
                              <p className="text-[10px] font-semibold text-slate-600 flex items-center gap-1">
                                <span className="w-2 h-2 bg-violet-500 rounded-full"></span>
                                Recommendations
                              </p>
                              {playerInjuryAnalysis.recommendations.map((rec: any, idx: number) => (
                                <div 
                                  key={idx}
                                  className={`p-2 rounded-lg text-[10px] ${
                                    rec.type === "danger" ? "bg-red-50 text-red-700 border border-red-200" :
                                    rec.type === "warning" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                                    rec.type === "positive" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                                    "bg-blue-50 text-blue-700 border border-blue-200"
                                  }`}
                                >
                                  {rec.text}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Knowledge Graph Integration */}
                          {playerInjuryAnalysis.rdf_potential?.can_create_injury_event && (
                            <div className="p-2 bg-violet-50 rounded-lg border border-violet-200">
                              <p className="text-[9px] font-semibold text-violet-700 mb-1">📊 Knowledge Graph</p>
                              <p className="text-[9px] text-violet-600">
                                This injury data can be stored as RDF triples in the Knowledge Graph for tracking injury history and pattern analysis.
                              </p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {/* Inference Explanation Tab */}
                  {activeCardTab === "inference" && playerExplanation && (
                    <div className="space-y-3">
                      <p className="text-[10px] text-slate-500 mb-2">
                        See why this player received each Smart Tag based on OWL inference rules.
                      </p>
                      
                      {/* Matched Tags Section */}
                      {(() => {
                        const matchedTags = playerExplanation.explanations.filter((exp: any) => exp.matched);
                        const unmatchedTags = playerExplanation.explanations.filter((exp: any) => !exp.matched);
                        
                        return (
                          <>
                            {/* Matched Tags */}
                            {matchedTags.length === 0 ? (
                              <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-center">
                                <span className="text-2xl mb-2 block">🏷️</span>
                                <p className="text-sm font-medium text-slate-600">No Matched Tags</p>
                                <p className="text-[10px] text-slate-400 mt-1">This player doesn't meet any Smart Tag criteria</p>
                              </div>
                            ) : (
                              <div className="space-y-2">
                                <p className="text-[10px] font-semibold text-emerald-700 flex items-center gap-1">
                                  <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                                  Matched Tags ({matchedTags.length})
                                </p>
                                {matchedTags.map((exp: any) => {
                                  const classInfo = OWL_CLASS_PRESETS.find(c => c.id === exp.tag_id);
                                  return (
                                    <div 
                                      key={exp.tag_id} 
                                      className="p-2.5 rounded-lg border bg-emerald-50 border-emerald-200"
                                    >
                                      <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-1.5">
                                          <span className="text-sm">{classInfo?.icon}</span>
                                          <span className="text-[11px] font-semibold text-slate-800">{classInfo?.name}</span>
                                        </div>
                                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500 text-white">
                                          ✓ MATCHED
                                        </span>
                                      </div>
                                      <div className="space-y-1">
                                        {exp.conditions.map((cond: any, idx: number) => (
                                          <div key={idx} className="flex items-center gap-2 text-[10px]">
                                            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] ${
                                              cond.passed ? "bg-emerald-500 text-white" : "bg-red-400 text-white"
                                            }`}>
                                              {cond.passed ? "✓" : "✗"}
                                            </span>
                                            <span className="text-slate-600">{cond.label}</span>
                                            <span className="font-mono text-slate-400">{cond.operator}</span>
                                            <span className="font-mono text-slate-500">{typeof cond.threshold === 'object' ? JSON.stringify(cond.threshold) : cond.threshold}</span>
                                            <span className="text-slate-400">→</span>
                                            <span className={`font-mono font-bold ${cond.passed ? "text-emerald-600" : "text-red-500"}`}>
                                              {typeof cond.actual === 'number' ? cond.actual.toFixed(1) : cond.actual}
                                            </span>
                                            {cond.is_or && <span className="text-[8px] text-orange-500 font-bold">OR</span>}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Unmatched Tags Section with Expand/Collapse */}
                            {unmatchedTags.length > 0 && (
                              <div className="space-y-2">
                                <button
                                  onClick={() => setShowUnmatchedTags(!showUnmatchedTags)}
                                  className="w-full flex items-center justify-between p-2 rounded-lg bg-slate-100 hover:bg-slate-200 transition-colors"
                                >
                                  <span className="text-[10px] font-semibold text-slate-600 flex items-center gap-1">
                                    <span className="w-2 h-2 bg-slate-400 rounded-full"></span>
                                    Not Matched ({unmatchedTags.length})
                                  </span>
                                  <span className="text-[10px] text-slate-500 flex items-center gap-1">
                                    {showUnmatchedTags ? "Collapse" : "Expand"}
                                    {showUnmatchedTags ? (
                                      <ChevronUp className="w-3 h-3" />
                                    ) : (
                                      <ChevronDown className="w-3 h-3" />
                                    )}
                                  </span>
                                </button>
                                
                                {showUnmatchedTags && (
                                  <div className="space-y-2">
                                    {unmatchedTags.map((exp: any) => {
                                      const classInfo = OWL_CLASS_PRESETS.find(c => c.id === exp.tag_id);
                                      return (
                                        <div 
                                          key={exp.tag_id} 
                                          className="p-2.5 rounded-lg border bg-slate-50 border-slate-200 opacity-70"
                                        >
                                          <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-1.5">
                                              <span className="text-sm">{classInfo?.icon}</span>
                                              <span className="text-[11px] font-semibold text-slate-800">{classInfo?.name}</span>
                                            </div>
                                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-300 text-slate-600">
                                              ✗ NOT MET
                                            </span>
                                          </div>
                                          <div className="space-y-1">
                                            {exp.conditions.map((cond: any, idx: number) => (
                                              <div key={idx} className="flex items-center gap-2 text-[10px]">
                                                <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[8px] ${
                                                  cond.passed ? "bg-emerald-500 text-white" : "bg-red-400 text-white"
                                                }`}>
                                                  {cond.passed ? "✓" : "✗"}
                                                </span>
                                                <span className="text-slate-600">{cond.label}</span>
                                                <span className="font-mono text-slate-400">{cond.operator}</span>
                                                <span className="font-mono text-slate-500">{typeof cond.threshold === 'object' ? JSON.stringify(cond.threshold) : cond.threshold}</span>
                                                <span className="text-slate-400">→</span>
                                                <span className={`font-mono font-bold ${cond.passed ? "text-emerald-600" : "text-red-500"}`}>
                                                  {typeof cond.actual === 'number' ? cond.actual.toFixed(1) : cond.actual}
                                                </span>
                                                {cond.is_or && <span className="text-[8px] text-orange-500 font-bold">OR</span>}
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}

                  {/* Similar Players Tab */}
                  {activeCardTab === "similar" && similarPlayers && (
                    <div>
                      <p className="text-[10px] text-slate-500 mb-2">
                        Players similar to {selectedPlayer.webName} based on position, price, form, and shared tags.
                      </p>
                      
                      {/* SPARQL Query Toggle */}
                      <button
                        onClick={() => setShowSparqlQuery(!showSparqlQuery)}
                        className="w-full mb-3 p-2 text-[10px] text-violet-600 bg-violet-50 rounded-lg border border-violet-200 hover:bg-violet-100 transition-colors flex items-center justify-center gap-1"
                      >
                        <Database className="w-3 h-3" />
                        {showSparqlQuery ? "Hide" : "Show"} SPARQL Query
                      </button>
                      
                      {showSparqlQuery && similarPlayers.query_used && (
                        <div className="mb-3 p-2 bg-slate-900 rounded-lg overflow-x-auto">
                          <pre className="text-[9px] text-emerald-400 font-mono whitespace-pre-wrap">
                            {similarPlayers.query_used}
                          </pre>
                        </div>
                      )}

                      {/* Similar Players List */}
                      <div className="space-y-2">
                        {similarPlayers.similar_players?.map((p: any, idx: number) => {
                          // Calculate similarity reasons
                          const priceDiff = Math.abs((p.price || 0) - similarPlayers.price);
                          const formDiff = Math.abs((p.form || 0) - selectedPlayer.form);
                          
                          return (
                            <div 
                              key={p.id}
                              className="p-2.5 bg-slate-50 rounded-lg hover:bg-slate-100 cursor-pointer transition-colors border border-slate-100"
                              onClick={() => {
                                const player = allPlayers.find(pl => pl.id === p.id);
                                if (player) setSelectedPlayer(player);
                              }}
                            >
                              {/* Header */}
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-slate-400 font-mono">#{idx + 1}</span>
                                  <span className="text-[11px] font-semibold text-slate-800">{p.name}</span>
                                  <span className="text-[9px] text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">{p.team}</span>
                                </div>
                                <span className="text-[10px] font-bold text-violet-600 bg-violet-100 px-1.5 py-0.5 rounded">
                                  {p.similarity_score}%
                                </span>
                              </div>
                              
                              {/* Why Similar - Reasons */}
                              <div className="bg-white rounded p-2 mb-2 border border-slate-100">
                                <p className="text-[9px] font-semibold text-slate-500 mb-1.5">Why similar:</p>
                                <div className="grid grid-cols-2 gap-1.5 text-[9px]">
                                  <div className="flex items-center gap-1">
                                    <span className="text-emerald-500">✓</span>
                                    <span className="text-slate-600">Same position</span>
                                    <span className="font-mono text-slate-400">({similarPlayers.position})</span>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    {priceDiff <= 1.5 ? (
                                      <span className="text-emerald-500">✓</span>
                                    ) : (
                                      <span className="text-amber-500">~</span>
                                    )}
                                    <span className="text-slate-600">Price</span>
                                    <span className={`font-mono ${priceDiff <= 0.5 ? 'text-emerald-600' : priceDiff <= 1.5 ? 'text-amber-600' : 'text-slate-400'}`}>
                                      {priceDiff <= 0.1 ? '≈' : priceDiff > 0 ? `±£${priceDiff.toFixed(1)}m` : ''}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    {formDiff <= 1 ? (
                                      <span className="text-emerald-500">✓</span>
                                    ) : (
                                      <span className="text-amber-500">~</span>
                                    )}
                                    <span className="text-slate-600">Form</span>
                                    <span className={`font-mono ${formDiff <= 0.5 ? 'text-emerald-600' : formDiff <= 1.5 ? 'text-amber-600' : 'text-slate-400'}`}>
                                      {formDiff <= 0.1 ? '≈' : `±${formDiff.toFixed(1)}`}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    {p.shared_tags?.length > 0 ? (
                                      <span className="text-emerald-500">✓</span>
                                    ) : (
                                      <span className="text-slate-300">○</span>
                                    )}
                                    <span className="text-slate-600">Shared tags</span>
                                    <span className="font-mono text-slate-400">({p.shared_tags?.length || 0})</span>
                                  </div>
                                </div>
                              </div>

                              {/* Shared Tags */}
                              {p.shared_tags?.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {p.shared_tags.map((tag: string) => {
                                    const tagInfo = OWL_CLASS_PRESETS.find(c => c.id === tag);
                                    return tagInfo ? (
                                      <span 
                                        key={tag} 
                                        className="text-[8px] bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded-full flex items-center gap-0.5"
                                      >
                                        {tagInfo.icon} {tagInfo.name}
                                      </span>
                                    ) : null;
                                  })}
                                </div>
                              )}
                              
                              {/* Stats comparison */}
                              <div className="flex items-center gap-3 text-[9px] text-slate-500 mt-2 pt-2 border-t border-slate-100">
                                <span>£{p.price?.toFixed(1)}m</span>
                                <span>Form: {p.form?.toFixed(1)}</span>
                                <span>Pts: {p.points}</span>
                                <span>Own: {p.ownership?.toFixed(0)}%</span>
                              </div>
                            </div>
                          );
                        })}
                        {similarPlayers.similar_players?.length === 0 && (
                          <p className="text-[10px] text-slate-400 text-center py-4">No similar players found</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Provenance Tab */}
                  {activeCardTab === "provenance" && playerProvenance && (
                    <div className="space-y-3">
                      <p className="text-[10px] text-slate-500 mb-2">
                        Track where each piece of data comes from - API, inference, or calculation.
                      </p>

                      {/* RDF URI */}
                      <div className="p-2 bg-violet-50 rounded-lg border border-violet-200">
                        <p className="text-[9px] text-violet-600 font-semibold mb-1">🔗 RDF Entity URI</p>
                        <p className="text-[9px] font-mono text-violet-800 break-all">{playerProvenance.player_uri}</p>
                      </div>

                      {/* API Data */}
                      <div>
                        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-1.5 flex items-center gap-1">
                          <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                          From FPL API
                        </p>
                        <div className="space-y-1">
                          {playerProvenance.data_sources?.slice(0, 6).map((src: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between text-[9px] p-1.5 bg-blue-50 rounded">
                              <span className="text-slate-600">{src.field}</span>
                              <span className="font-mono font-medium text-blue-700">
                                {typeof src.value === 'number' ? src.value.toFixed(2) : src.value}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Inferred Data */}
                      {playerProvenance.inferred_data?.length > 0 && (
                        <div>
                          <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-1.5 flex items-center gap-1">
                            <span className="w-2 h-2 bg-violet-500 rounded-full"></span>
                            OWL Inference
                          </p>
                          <div className="space-y-1">
                            {playerProvenance.inferred_data?.map((inf: any, idx: number) => (
                              <div key={idx} className="flex items-center justify-between text-[9px] p-1.5 bg-violet-50 rounded">
                                <span className="font-mono text-violet-600 text-[8px]">{inf.field}</span>
                                <span className="text-violet-500">🧠 inferred</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Calculated Data */}
                      <div>
                        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wide mb-1.5 flex items-center gap-1">
                          <span className="w-2 h-2 bg-amber-500 rounded-full"></span>
                          Calculated
                        </p>
                        <div className="space-y-1">
                          {playerProvenance.calculated_data?.map((calc: any, idx: number) => (
                            <div key={idx} className="p-1.5 bg-amber-50 rounded">
                              <div className="flex items-center justify-between text-[9px]">
                                <span className="text-slate-600">{calc.field}</span>
                                <span className="font-mono font-medium text-amber-700">{calc.value}</span>
                              </div>
                              <p className="text-[8px] text-amber-600 font-mono mt-0.5">{calc.formula}</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* KG Stats */}
                      <div className="p-2 bg-slate-100 rounded-lg text-center">
                        <p className="text-[9px] text-slate-500">Total triples in Knowledge Graph</p>
                        <p className="text-lg font-bold text-slate-700">{playerProvenance.rdf_triples_count?.toLocaleString()}</p>
                      </div>
                    </div>
                  )}

                  {/* Wikidata Tab */}
                  {activeCardTab === "wikidata" && (
                    <div className="space-y-3">
                      <p className="text-[10px] text-slate-500 mb-2">
                        External data from Wikidata - the free knowledge base with structured data.
                      </p>

                      {!playerWikidata ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="w-5 h-5 animate-spin text-violet-500" />
                          <span className="ml-2 text-sm text-slate-500">Querying Wikidata...</span>
                        </div>
                      ) : !playerWikidata.found ? (
                        <div className="p-4 bg-slate-50 rounded-lg text-center">
                          <span className="text-2xl mb-2 block">🔍</span>
                          <p className="text-sm text-slate-600">{playerWikidata.message || playerWikidata.error || "Player not found in Wikidata"}</p>
                          <p className="text-[10px] text-slate-400 mt-1">Searched: {playerWikidata.full_name}</p>
                        </div>
                      ) : (
                        <>
                          {/* Wikidata Entity Link */}
                          <div className="p-2.5 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-lg border border-blue-200">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-lg">🌐</span>
                                <div>
                                  <p className="text-[10px] text-blue-600 font-semibold">Wikidata Entity</p>
                                  <p className="text-[9px] font-mono text-blue-800">{playerWikidata.wikidata_id}</p>
                                </div>
                              </div>
                              <div className="flex gap-1">
                                {playerWikidata.wikidata_url && (
                                  <a 
                                    href={playerWikidata.wikidata_url} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="p-1.5 bg-blue-100 hover:bg-blue-200 rounded text-blue-700 transition-colors"
                                    title="View on Wikidata"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                )}
                                {playerWikidata.wikipedia_url && (
                                  <a 
                                    href={playerWikidata.wikipedia_url} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="p-1.5 bg-slate-100 hover:bg-slate-200 rounded text-slate-700 transition-colors"
                                    title="View on Wikipedia"
                                  >
                                    <BookOpen className="w-3 h-3" />
                                  </a>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Player Image from Wikidata */}
                          {playerWikidata.image && (
                            <div className="flex justify-center">
                              <img 
                                src={playerWikidata.image} 
                                alt={playerWikidata.full_name}
                                className="max-w-[120px] max-h-[140px] w-auto h-auto object-contain rounded-xl shadow-md border-2 border-slate-100 bg-slate-50"
                                onError={(e) => (e.currentTarget.style.display = 'none')}
                              />
                            </div>
                          )}

                          {/* External Data Grid */}
                          <div className="space-y-2">
                            {playerWikidata.nationality && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">🏳️</span>
                                  <span className="text-[10px] text-slate-600">Nationality</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">{playerWikidata.nationality}</span>
                              </div>
                            )}

                            {playerWikidata.age && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">🎂</span>
                                  <span className="text-[10px] text-slate-600">Age</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">
                                  {playerWikidata.age} years
                                  {playerWikidata.birth_date && (
                                    <span className="text-[9px] text-slate-400 ml-1">
                                      ({playerWikidata.birth_date})
                                    </span>
                                  )}
                                </span>
                              </div>
                            )}

                            {playerWikidata.birth_place && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">📍</span>
                                  <span className="text-[10px] text-slate-600">Birthplace</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">{playerWikidata.birth_place}</span>
                              </div>
                            )}

                            {playerWikidata.height && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">📏</span>
                                  <span className="text-[10px] text-slate-600">Height</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">{playerWikidata.height}</span>
                              </div>
                            )}

                            {playerWikidata.position && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">⚽</span>
                                  <span className="text-[10px] text-slate-600">Position (Wiki)</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">{playerWikidata.position}</span>
                              </div>
                            )}

                            {playerWikidata.national_team && (
                              <div className="flex items-center justify-between p-2 bg-slate-50 rounded-lg">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm">🏆</span>
                                  <span className="text-[10px] text-slate-600">National Team</span>
                                </div>
                                <span className="text-[11px] font-medium text-slate-800">{playerWikidata.national_team}</span>
                              </div>
                            )}
                          </div>

                          {/* Data Source Attribution */}
                          <div className="mt-3 p-2 bg-blue-50/50 rounded-lg border border-blue-100">
                            <p className="text-[9px] text-blue-600 text-center">
                              Data from <a href="https://www.wikidata.org" target="_blank" rel="noopener noreferrer" className="underline">Wikidata</a> • 
                              Licensed under <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener noreferrer" className="underline">CC0</a>
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Empty State - Knowledge Graph Explainer - Hidden on mobile */}
          {!selectedPlayer && !compareMode && (
            <div className="hidden lg:block w-[25%] flex-shrink-0 min-w-[320px] max-w-[360px]">
              <div className="bg-gradient-to-b from-white to-slate-50/30 rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200/60 overflow-hidden sticky top-24 h-[calc(100vh-120px)] overflow-y-auto scroll-smooth">
                {/* Header */}
                <div className="p-5 bg-gradient-to-br from-violet-50 to-purple-50 border-b border-violet-100">
                  <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
                    <Database className="w-7 h-7 text-white" />
                  </div>
                  <h3 className="font-bold text-slate-800 text-center text-lg">What is this?</h3>
                  <p className="text-xs text-slate-500 text-center mt-1">Knowledge Graph Intelligence</p>
                </div>
                
                {/* Explanation */}
                <div className="p-5">
                  <p className="text-sm text-slate-600 leading-relaxed mb-4">
                    Our system analyzes <strong>every player</strong> using semantic web rules (OWL reasoning) and automatically assigns <strong>Smart Tags</strong> based on their stats.
                  </p>
                  
                  <div className="space-y-3 mb-5">
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-sm">🧠</span>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-700">Automatic Classification</p>
                        <p className="text-[10px] text-slate-500">Players tagged based on form, price, ownership & fixtures</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-sm">⚡</span>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-700">Real-Time Updates</p>
                        <p className="text-[10px] text-slate-500">Tags update as FPL data changes</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-sm">🎯</span>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-700">Decision Support</p>
                        <p className="text-[10px] text-slate-500">Find captain picks, differentials & transfer targets</p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-xl p-3 text-center">
                    <p className="text-xs text-slate-500 mb-1">Click any player to see their tags</p>
                    <p className="text-[10px] text-slate-400">or use Smart Tags on the left to filter</p>
                  </div>
                </div>
                
                {/* Stats Footer */}
                {kgStats && (
                  <div className="px-5 pb-5">
                    <div className="p-4 bg-gradient-to-r from-violet-50 to-purple-50 rounded-xl border border-violet-200/60">
                      <p className="text-[10px] font-bold text-violet-700 uppercase tracking-wide mb-3 text-center">Graph Statistics</p>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="text-center p-2 bg-white/60 rounded-lg">
                          <p className="text-lg font-bold text-violet-700">{(kgStats.total_triples / 1000).toFixed(0)}K</p>
                          <p className="text-[9px] text-violet-500">Data Points</p>
                        </div>
                        <div className="text-center p-2 bg-white/60 rounded-lg">
                          <p className="text-lg font-bold text-violet-700">{kgStats.inferred_triples}</p>
                          <p className="text-[9px] text-violet-500">OWL Inferences</p>
                        </div>
                        <div className="text-center p-2 bg-white/60 rounded-lg">
                          <p className="text-lg font-bold text-violet-700">{kgStats.entities.players}</p>
                          <p className="text-[9px] text-violet-500">Players</p>
                        </div>
                        <div className="text-center p-2 bg-white/60 rounded-lg">
                          <p className="text-lg font-bold text-violet-700">{kgStats.inference.rules_count}</p>
                          <p className="text-[9px] text-violet-500">Smart Rules</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Developer Info */}
                <div className="px-5 pb-5">
                  <div className="p-4 bg-gradient-to-r from-slate-50 to-slate-100 rounded-xl border border-slate-200/60">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-md">
                        <GraduationCap className="w-5 h-5 text-white" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-slate-700">Qazybek Beken</p>
                          <a
                            href="https://www.linkedin.com/in/qazybek-beken/"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-700 transition-colors"
                            title="LinkedIn Profile"
                          >
                            <Linkedin className="w-4 h-4" />
                          </a>
                        </div>
                        <p className="text-[10px] text-slate-500">UC Berkeley · School of Information</p>
                      </div>
                    </div>
                    <p className="text-[9px] text-slate-400 mt-3 text-center">
                      Built with RDFLib · PySHACL · OWLRL · Next.js · FastAPI
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Comparison Panel */}
      {compareMode && comparePlayers.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-violet-200 shadow-2xl z-40">
          <div className="max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
                  <Scale className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-800">Comparing {comparePlayers.length} Players</h3>
                  <p className="text-xs text-slate-500">Click more players to add (max 3)</p>
                </div>
              </div>
              <button
                onClick={clearComparison}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-slate-500 hover:text-red-500 hover:bg-red-50 rounded-lg"
              >
                <X className="w-4 h-4" />
                Clear All
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {[0, 1, 2].map((idx) => {
                const player = comparePlayers[idx];
                if (!player) {
                  return (
                    <div key={idx} className="p-3 border-2 border-dashed border-slate-200 rounded-xl text-center bg-slate-50/50">
                      <p className="text-sm text-slate-400">+ Add player</p>
                    </div>
                  );
                }

                const posColors = POSITION_COLORS[player.position];
                const playerClasses = playerClassesCache.get(player.id) || [];

                return (
                  <div key={player.id} className={`p-3 rounded-xl border ${posColors.bg} border-slate-200 relative`}>
                    <button
                      onClick={() => toggleComparePlayer(player)}
                      className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center"
                    >
                      <X className="w-3 h-3" />
                    </button>
                    
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${posColors.badge} text-white`}>
                        {player.position}
                      </span>
                      <span className="font-bold text-slate-800 text-sm truncate">{player.webName}</span>
                      <span className="text-xs text-slate-500 ml-auto">£{player.price.toFixed(1)}m</span>
                    </div>

                    {/* OWL Classes */}
                    {playerClasses.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {playerClasses.slice(0, 3).map(cls => {
                          const classInfo = OWL_CLASS_PRESETS.find(c => c.id === cls);
                          return classInfo ? (
                            <span key={cls} className="text-[8px]" title={classInfo.name}>
                              {classInfo.icon}
                            </span>
                          ) : null;
                        })}
                      </div>
                    )}

                    <div className="grid grid-cols-4 gap-1 text-center">
                      <div className="p-1.5 rounded bg-white/60">
                        <p className="text-[9px] text-slate-500">Form</p>
                        <p className="text-sm font-bold text-slate-700">{player.form.toFixed(1)}</p>
                      </div>
                      <div className="p-1.5 rounded bg-white/60">
                        <p className="text-[9px] text-slate-500">Pts</p>
                        <p className="text-sm font-bold text-slate-700">{player.totalPoints}</p>
                      </div>
                      <div className="p-1.5 rounded bg-white/60">
                        <p className="text-[9px] text-slate-500">PPG</p>
                        <p className="text-sm font-bold text-slate-700">{player.pointsPerGame.toFixed(1)}</p>
                      </div>
                      <div className="p-1.5 rounded bg-white/60">
                        <p className="text-[9px] text-slate-500">Own</p>
                        <p className="text-sm font-bold text-slate-700">{player.ownership.toFixed(0)}%</p>
                      </div>
                    </div>

                    {player.nextFixtures && player.nextFixtures.length > 0 && (
                      <div className="flex gap-1 mt-2">
                        {player.nextFixtures.slice(0, 4).map((fix, fidx) => {
                          const fdrColor = fix.difficulty <= 2 ? "bg-emerald-500" : fix.difficulty === 3 ? "bg-amber-400" : fix.difficulty === 4 ? "bg-orange-500" : "bg-red-500";
                          return (
                            <div key={fidx} className={`flex-1 ${fdrColor} rounded py-1 text-center`}>
                              <span className="text-[8px] font-bold text-white">{fix.opponent}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
        </div>

      {/* Saved Players Panel */}
      {showSavedPanel && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-amber-200 shadow-2xl z-40 max-h-[50vh] overflow-y-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                  <Bookmark className="w-4 h-4 text-white fill-current" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-800">Saved Players ({savedPlayers.length})</h3>
                  <p className="text-xs text-slate-500">Your shortlist for squad building</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {savedPlayers.length > 0 && (
                  <button
                    onClick={clearSaved}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-slate-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Clear All
                  </button>
                )}
                <button
                  onClick={() => setShowSavedPanel(false)}
                  className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>
            </div>

            {savedPlayers.length === 0 ? (
              <div className="text-center py-8 bg-slate-50 rounded-xl">
                <Bookmark className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 font-medium">No saved players yet</p>
                <p className="text-sm text-slate-400 mt-1">Click &quot;Save Player&quot; on any player card to add them here</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {savedPlayers.map((player) => {
                  const posColor = {
                    GKP: "bg-amber-100 text-amber-700",
                    DEF: "bg-emerald-100 text-emerald-700",
                    MID: "bg-blue-100 text-blue-700",
                    FWD: "bg-rose-100 text-rose-700"
                  }[player.position] || "bg-slate-100 text-slate-700";
                  
                  const statusIcon = player.status === "a" ? "🟢" : player.status === "d" ? "🟡" : "🔴";
                  const formColor = player.form >= 6 ? "text-emerald-600" : player.form >= 4 ? "text-amber-600" : "text-slate-500";
                  
                  return (
                    <div
                      key={player.id}
                      className="relative bg-white rounded-xl border border-amber-200 shadow-sm overflow-hidden group hover:shadow-md transition-shadow"
                    >
                      {/* Header with position and status */}
                      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-amber-50 to-orange-50 border-b border-amber-100">
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${posColor}`}>
                            {player.position}
                          </span>
                          <span className="text-sm">{statusIcon}</span>
                        </div>
                        <span className="text-sm font-bold text-slate-700 font-mono">£{player.price.toFixed(1)}m</span>
                      </div>
                      
                      {/* Player info */}
                      <div className="px-3 py-2">
                        <p className="font-semibold text-slate-800 text-sm truncate">{player.name}</p>
                        <p className="text-xs text-slate-500">{player.team}</p>
                      </div>
                      
                      {/* Stats row */}
                      <div className="grid grid-cols-3 gap-1 px-3 pb-3">
                        <div className="text-center p-1.5 bg-slate-50 rounded-lg">
                          <p className="text-[10px] text-slate-400 uppercase">Form</p>
                          <p className={`text-sm font-bold ${formColor}`}>{player.form?.toFixed(1) || "-"}</p>
                        </div>
                        <div className="text-center p-1.5 bg-slate-50 rounded-lg">
                          <p className="text-[10px] text-slate-400 uppercase">Pts</p>
                          <p className="text-sm font-bold text-slate-700">{player.totalPoints || 0}</p>
                        </div>
                        <div className="text-center p-1.5 bg-slate-50 rounded-lg">
                          <p className="text-[10px] text-slate-400 uppercase">Own</p>
                          <p className="text-sm font-bold text-slate-700">{player.ownership?.toFixed(0) || 0}%</p>
                        </div>
                      </div>
                      
                      {/* Remove button */}
                      <button
                        onClick={() => removeFromSaved(player.id)}
                        className="absolute top-2 right-2 p-1 rounded-full bg-white/90 opacity-0 group-hover:opacity-100 transition-all hover:bg-red-50 hover:text-red-500 shadow-sm"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {savedPlayers.length > 0 && (
              <div className="mt-4 pt-4 border-t border-amber-100">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                  <span><span className="font-semibold">{savedPlayers.length}</span> players</span>
                  <span>Cost: <span className="font-mono font-semibold">£{savedPlayers.reduce((sum, p) => sum + p.price, 0).toFixed(1)}m</span></span>
                  <span>Pts: <span className="font-mono font-semibold">{savedPlayers.reduce((sum, p) => sum + (p.totalPoints || 0), 0)}</span></span>
                  <span>Avg Form: <span className="font-mono font-semibold">{(savedPlayers.reduce((sum, p) => sum + (p.form || 0), 0) / savedPlayers.length).toFixed(1)}</span></span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat Widget */}
      <ChatWidget
        allPlayers={allPlayers}
        onApplyFilter={(chatFilters) => {
          setFilters(prev => ({ ...DEFAULT_FILTERS, ...chatFilters }));
          setActivePreset(null);
        }}
        onSelectPlayer={setSelectedPlayer}
      />
    </div>
  );
}

// ============== Page Export with Suspense ==============

function PlayersPageLoading() {
  return (
    <div className="bg-slate-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-violet-500"></div>
        <p className="text-slate-400">Loading players...</p>
      </div>
    </div>
  );
}

export default function PlayersPage() {
  return (
    <Suspense fallback={<PlayersPageLoading />}>
      <PlayersPageContent />
    </Suspense>
  );
}

