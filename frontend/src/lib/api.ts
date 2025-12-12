/**
 * API client for SmartPlayFPL backend
 *
 * Environment configuration:
 * - Development: Uses NEXT_PUBLIC_API_URL from .env.local (defaults to localhost:8000)
 * - Production: Uses NEXT_PUBLIC_API_URL from Vercel env vars (Railway backend)
 */

// Production backend URL (fallback if env var not set)
const PRODUCTION_API_URL = 'https://smartplayfpl-backend-production.up.railway.app';

// Get API URL from environment variable, with smart fallbacks
function getApiBaseUrl(): string {
  // Check environment variable first (works in both server and client)
  const envApiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (envApiUrl) {
    // If env var is set, use it directly (add /api if not included)
    return envApiUrl.endsWith('/api') ? envApiUrl : `${envApiUrl}/api`;
  }

  // Fallback: Check if we're in development mode
  const isDevelopment = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development' ||
    process.env.NODE_ENV === 'development';

  if (isDevelopment) {
    // Development: use local proxy (Next.js rewrites to localhost:8000)
    return '/api';
  }

  // Production fallback
  return `${PRODUCTION_API_URL}/api`;
}

const API_BASE = getApiBaseUrl();

export interface PlayerSummary {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  points: number;      // Total season points
  gw_points: number;   // Points in this gameweek
  ownership: number;
  status: string;
  news: string;
  is_captain: boolean;
  is_vice_captain: boolean;
  multiplier: number;
}

export interface SquadData {
  starting: PlayerSummary[];
  bench: PlayerSummary[];
  captain_id: number;
  vice_captain_id: number;
}

export interface ManagerInfo {
  id: number;
  player_first_name: string;
  player_last_name: string;
  name: string;
  summary_overall_points: number;
  summary_overall_rank: number | null;
  summary_event_points: number | null;
  summary_event_rank: number | null;
}

export interface Gameweek {
  id: number;
  name: string;
  deadline_time: string;
  is_current: boolean;
  is_next: boolean;
  finished: boolean;
  average_entry_score: number | null;  // Average points for this GW
  highest_score: number | null;        // Highest score for this GW
}

export interface League {
  id: number;
  name: string;
  entry_rank: number | null;
  entry_last_rank: number | null;
}

export interface TeamAnalysisResponse {
  manager: ManagerInfo;
  gameweek: Gameweek;
  squad: SquadData;
  team_value: number;
  bank: number;
  free_transfers: number;
  gw_rank: number | null;
  overall_rank: number | null;
  leagues: League[];
}

export async function getTeamAnalysis(teamId: string): Promise<TeamAnalysisResponse> {
  const response = await fetch(`${API_BASE}/team/${teamId}`);
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Team ${teamId} not found`);
    }
    throw new Error(`Failed to fetch team analysis: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getCurrentGameweek(): Promise<Gameweek> {
  const response = await fetch(`${API_BASE}/gameweek/current`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch current gameweek");
  }
  
  return response.json();
}

export interface PlayerBasic {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  points: number;
  ownership: number;
  status: string;
}

export async function getAllPlayers(): Promise<PlayerBasic[]> {
  const response = await fetch(`${API_BASE}/players`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch players");
  }
  
  return response.json();
}

// =============================================================================
// Rival Intelligence Types
// =============================================================================

export interface PlayerInsight {
  id: number;
  name: string;
  team: string;
  ownership: number;
  form: number;
  transfers_in: number;
  transfers_out: number;
}

export interface RivalInsightCard {
  title: string;
  icon: string;
  you_have: boolean;
  description: string;
  players: PlayerInsight[];
}

export interface LeagueStanding {
  league_id: number;
  league_name: string;
  rank: number;
  total_entries: number | null;
}

export interface RivalIntelligenceResponse {
  gw_rank: number | null;
  overall_rank: number | null;
  gw_rank_percentile: number | null;
  leagues: LeagueStanding[];
  total_rivals: number;
  insights: RivalInsightCard[];
  strategy: string;
}

export async function getRivalIntelligence(teamId: string): Promise<RivalIntelligenceResponse> {
  const response = await fetch(`${API_BASE}/rivals/${teamId}`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch rival intelligence");
  }
  
  return response.json();
}

// =============================================================================
// Player Planner Types
// =============================================================================

export interface FixtureInfo {
  gameweek: number;
  opponent: string;
  is_home: boolean;
  difficulty: number; // 1-5 FDR
}

export interface PlayerPlannerEntry {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  points: number;
  ownership: number;
  transfers_in: number;
  transfers_out: number;
  fixtures: FixtureInfo[];
}

export interface PlayerPlannerResponse {
  current_gameweek: number;
  players: PlayerPlannerEntry[];
}

export async function getPlayerPlanner(teamId: string): Promise<PlayerPlannerResponse> {
  const response = await fetch(`${API_BASE}/planner/${teamId}`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch player planner data");
  }
  
  return response.json();
}

// =============================================================================
// Captain Recommendation Types
// =============================================================================

export interface CaptainPick {
  player_id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  
  // Scores (0-1)
  total_score: number;
  form_score: number;
  fixture_score: number;
  crowd_score: number;
  risk_score: number;
  
  // Context
  ownership: number;
  form: number;
  gw_points: number;
  fixture: string;
  fixture_difficulty: number;
  
  // Reasoning
  category: string; // "safe", "balanced", "differential"
  reasoning: string;
  risks: string[];
}

export interface CaptainResponse {
  gameweek: number;
  picks: CaptainPick[];
  one_liner: string;
  powered_by: string;
}

export async function getCaptainRecommendation(teamId: string): Promise<CaptainResponse> {
  const response = await fetch(`${API_BASE}/captain/${teamId}`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch captain recommendation");
  }
  
  return response.json();
}

// =============================================================================
// This Week's Actions Types
// =============================================================================

export interface FutureFixture {
  gw: number;
  opponent: string;
  fdr: number;
}

export interface ActionCard {
  action_type: string; // "captain", "bench", "start", "hold"
  icon: string;
  player_name: string;
  player_id: number;
  team: string;
  fixture: string;
  fixture_difficulty: number;
  reasoning: string;
  form: number;
  future_fixtures: FutureFixture[];
}

export interface ActionsResponse {
  gameweek: number;
  actions: ActionCard[];
  powered_by: string;
}

export async function getWeeklyActions(teamId: string): Promise<ActionsResponse> {
  const response = await fetch(`${API_BASE}/actions/${teamId}`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch weekly actions");
  }
  
  return response.json();
}

// =============================================================================
// Chip Planner Types
// =============================================================================

export interface ChipStatus {
  name: string;
  display_name: string;
  icon: string;
  description: string;
  available: boolean;
  used_gw: number | null;
}

export interface ChipRecommendation {
  chip_name: string;
  display_name: string;
  icon: string;
  title: string;
  description: string;
  readiness: number | null;
  best_player: string | null;
  recommended_gw: number | null;
}

export interface ChipPlannerResponse {
  gameweek: number;
  chips: ChipStatus[];
  recommendations: ChipRecommendation[];
  reminder: string | null;
}

export async function getChipPlanner(teamId: string): Promise<ChipPlannerResponse> {
  const response = await fetch(`${API_BASE}/chips/${teamId}`);
  
  if (!response.ok) {
    throw new Error("Failed to fetch chip planner");
  }
  
  return response.json();
}

// =============================================================================
// Transfer Suggestions Types
// =============================================================================

export interface TransferTarget {
  player_id: number;
  player_name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  ownership: number;
  fixture: string;
  fixture_difficulty: number;
  reasons: string[];
  priority: string; // "urgent", "recommended", "consider"
}

export interface TransferPair {
  out_player: TransferTarget;
  in_player: TransferTarget;
  net_cost: number;
  expected_gain: string;
}

export interface TransferSuggestionsResponse {
  gameweek: number;
  free_transfers: number;
  bank: number;
  out_suggestions: TransferTarget[];
  in_suggestions: TransferTarget[];
  transfer_pairs: TransferPair[];
}

export async function getTransferSuggestions(teamId: string): Promise<TransferSuggestionsResponse> {
  const response = await fetch(`${API_BASE}/transfers/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch transfer suggestions");
  }

  return response.json();
}

// =============================================================================
// ML Predictor Types
// =============================================================================

export interface MLPlayerScore {
  player_id: number;
  name: string;
  full_name: string;
  team: string;
  team_id: number;
  position: string;
  price: number;
  ownership: number;
  status: string;
  news: string;
  // Component scores (0-10 scale)
  nailedness_score: number;
  form_xg_score: number;
  form_pts_score: number;
  fixture_score: number;
  // Final combined score (0-10 scale)
  final_score: number;
  // Additional context
  avg_minutes: number;
  avg_points: number;
  total_points: number;
  form: number;
  next_opponent: string;
  next_fdr: number;
  next_home: boolean;
  rank: number;
}

export interface PredictorStatusResponse {
  is_initialized: boolean;
  player_count: number;
  last_update: string | null;
  gameweek: number | null;
}

export async function getPredictorStatus(): Promise<PredictorStatusResponse> {
  const response = await fetch(`${API_BASE}/predictor/status`);

  if (!response.ok) {
    throw new Error("Failed to fetch predictor status");
  }

  return response.json();
}

export async function calculatePredictorScores(): Promise<{
  success: boolean;
  players_scored: number;
  gameweek: number;
  elapsed_seconds: number;
  last_update: string;
}> {
  const response = await fetch(`${API_BASE}/predictor/calculate`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to calculate predictor scores");
  }

  return response.json();
}

export async function getPlayerMLScore(playerId: number): Promise<MLPlayerScore> {
  const response = await fetch(`${API_BASE}/predictor/player/${playerId}`);

  if (!response.ok) {
    if (response.status === 400) {
      throw new Error("Predictor not initialized. Please calculate scores first.");
    }
    if (response.status === 404) {
      throw new Error(`Player ${playerId} not found`);
    }
    throw new Error("Failed to fetch player ML score");
  }

  return response.json();
}

export async function getAllMLScores(
  limit: number = 100,
  position?: string,
  minScore?: number
): Promise<MLPlayerScore[]> {
  const params = new URLSearchParams();
  params.set("limit", limit.toString());
  if (position) params.set("position", position);
  if (minScore !== undefined) params.set("min_score", minScore.toString());

  const response = await fetch(`${API_BASE}/predictor/scores?${params}`);

  if (!response.ok) {
    throw new Error("Failed to fetch ML scores");
  }

  return response.json();
}

export async function getTopByPosition(
  position: string,
  limit: number = 10
): Promise<{ position: string; players: MLPlayerScore[] }> {
  const response = await fetch(`${API_BASE}/predictor/top/${position}?limit=${limit}`);

  if (!response.ok) {
    throw new Error("Failed to fetch top players");
  }

  return response.json();
}

export async function getCaptainPicks(limit: number = 10): Promise<MLPlayerScore[]> {
  const response = await fetch(`${API_BASE}/predictor/captain-picks?limit=${limit}`);

  if (!response.ok) {
    throw new Error("Failed to fetch captain picks");
  }

  return response.json();
}

export async function getDifferentialPicks(
  maxOwnership: number = 10,
  limit: number = 10
): Promise<MLPlayerScore[]> {
  const response = await fetch(
    `${API_BASE}/predictor/differential-picks?max_ownership=${maxOwnership}&limit=${limit}`
  );

  if (!response.ok) {
    throw new Error("Failed to fetch differential picks");
  }

  return response.json();
}

export async function getValuePicks(
  maxPrice: number = 7.0,
  limit: number = 10
): Promise<MLPlayerScore[]> {
  const response = await fetch(
    `${API_BASE}/predictor/value-picks?max_price=${maxPrice}&limit=${limit}`
  );

  if (!response.ok) {
    throw new Error("Failed to fetch value picks");
  }

  return response.json();
}

// =============================================================================
// Crowd Insights Types
// =============================================================================

export interface CrowdInsightPlayer {
  id: number;
  name: string;
  team: string;
  price: number;
  form: number;
  ownership: number;
  transfers_in: number;
  transfers_out: number;
  in_squad: boolean;
}

export interface CrowdInsightCard {
  type: string; // smart_money, under_radar, bandwagon, panic_sell, quick_hit, template_score
  title: string;
  icon: string;
  tag: string; // BUY, AVOID, CAPTAIN, etc.
  tag_color: string; // green, red, amber, blue
  description: string;
  players: CrowdInsightPlayer[];
  value?: string; // For template score: "Punty", "Balanced", "Template"
}

export interface CrowdInsightsResponse {
  insights: CrowdInsightCard[];
  template_score: number; // 0-100, higher = more template
  avg_ownership: number;
}

export async function getCrowdInsights(teamId: string): Promise<CrowdInsightsResponse> {
  const response = await fetch(`${API_BASE}/crowd-insights/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch crowd insights");
  }

  return response.json();
}

export async function getAICrowdInsights(teamId: string): Promise<CrowdInsightsResponse> {
  const response = await fetch(`${API_BASE}/crowd-insights-ai/${teamId}`);

  if (!response.ok) {
    if (response.status === 503) {
      throw new Error("AI service not available. Please configure API key.");
    }
    throw new Error("Failed to fetch AI crowd insights");
  }

  return response.json();
}

// =============================================================================
// Transfer Workflow Types
// =============================================================================

export interface GWInsight {
  type: string; // positive, negative, neutral, warning
  icon: string; // crown, bench, star, alert, trending_down, rank
  text: string;
}

export interface GWReviewResponse {
  gw_points: number;
  gw_rank: number | null;
  gw_average: number | null;
  gw_highest: number | null;
  rank_percentile: number | null; // e.g., 7.2 means top 7.2%
  insights: GWInsight[];
  summary: string;
  current_gameweek?: number;
}

export interface WorkflowTransferPlayerOut {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  reasons: string[];
  smartplay_score: number;
}

export interface WorkflowTransferPlayerIn {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  reasons: string[];
}

export interface TransferAlternative {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  total_points: number;
  ownership: number;
  transfers_in: number;
  score: number;
  reasons: string[];
  smartplay_score: number;
}

export interface WorkflowTransferSuggestion {
  out: WorkflowTransferPlayerOut;
  in_player: WorkflowTransferPlayerIn;
  alternatives: TransferAlternative[];
  cost_change: number;
  priority: string; // high, medium, low
}

export interface WorkflowTransferSuggestionsResponse {
  free_transfers: number;
  bank: number;
  suggestions: WorkflowTransferSuggestion[];
  message: string;
}

export async function getGWReview(teamId: string): Promise<GWReviewResponse> {
  const response = await fetch(`${API_BASE}/gw-review/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch GW review");
  }

  return response.json();
}

// AI-powered GW Review analysis
export interface SquadScore {
  overall: number;
  attack: number;
  midfield: number;
  defense: number;
  bench: number;
}

export interface AIGWReviewResponse {
  what_went_well: string[];
  areas_to_address: string[];
  strengths: string[];
  weaknesses: string[];
  squad_score: SquadScore;
  summary: string;
  ai_model: string;
  gw_points: number;
  gw_rank: number | null;
  gw_average: number | null;
}

export async function getAIGWReview(teamId: string): Promise<AIGWReviewResponse> {
  const response = await fetch(`${API_BASE}/gw-review-ai/${teamId}`);

  if (!response.ok) {
    if (response.status === 503) {
      throw new Error("AI service not available. Please configure API key.");
    }
    throw new Error("Failed to fetch AI GW review");
  }

  return response.json();
}

export async function getWorkflowTransferSuggestions(teamId: string): Promise<WorkflowTransferSuggestionsResponse> {
  // Add retry logic for transient failures
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const response = await fetch(`${API_BASE}/transfer-suggestions/${teamId}`);

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        if (response.status === 500) {
          throw new Error(`Server error: ${errorText}`);
        }
        throw new Error(`Failed to fetch transfer suggestions (${response.status})`);
      }

      return response.json();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Unknown error");
      // Only retry on network errors, not HTTP errors
      if (error instanceof TypeError && error.message.includes("fetch")) {
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
        continue;
      }
      throw lastError;
    }
  }

  throw lastError || new Error("Failed to fetch transfer suggestions after retries");
}

// =============================================================================
// Alerts Types (Step 2)
// =============================================================================

export interface Alert {
  type: string; // injury, rotation, price, fixture
  severity: string; // high, medium, warning, info
  player_id: number | null;
  player_name: string | null;
  team: string;
  message: string;
  detail: string;
  icon: string;
}

export interface AlertsResponse {
  alerts: Alert[];
  summary: string;
}

export async function getAlerts(teamId: string): Promise<AlertsResponse> {
  const response = await fetch(`${API_BASE}/alerts/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch alerts");
  }

  return response.json();
}

// =============================================================================
// Lineup Types (Step 4)
// =============================================================================

export interface SmartPlayData {
  final_score: number;
  nailedness_score: number;
  form_xg_score: number;
  form_pts_score: number;
  fixture_score: number;
  next_opponent: string;
  next_fdr: number;
}

export interface LineupPlayer {
  id: number;
  name: string;
  position: string;
  team: string;
  price: number;
  form: number;
  ownership: number;
  points: number;
  gw_points: number;
  status: string;
  news: string;
  is_captain: boolean;
  is_vice_captain: boolean;
  score: number;
  reasons: string[];
  smartplay_data?: SmartPlayData | null;
}

export interface BenchPlayer {
  id: number;
  name: string;
  position: string;
  team: string;
  price: number;
  form: number;
  ownership: number;
  points: number;
  gw_points: number;
  status: string;
  news: string;
  is_captain: boolean;
  is_vice_captain: boolean;
  score: number;
  order: number;
  smartplay_data?: SmartPlayData | null;
}

export interface CaptainPick {
  id: number;
  name: string;
  score: number;
  reasons: string[];
}

export interface ViceCaptainPick {
  id: number;
  name: string;
  score: number;
}

export interface LineupResponse {
  formation: string;
  starting_xi: LineupPlayer[];
  bench: BenchPlayer[];
  captain: CaptainPick | null;
  vice_captain: ViceCaptainPick | null;
  summary: string;
  using_smartplay?: boolean;
}

export async function getLineupRecommendation(teamId: string): Promise<LineupResponse> {
  const response = await fetch(`${API_BASE}/lineup/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch lineup recommendation");
  }

  return response.json();
}

// =============================================================================
// Lineup Strategies Types (Formation Options)
// =============================================================================

export interface FormationStrategy {
  strategy: string; // balanced, attacking, defensive
  name: string;
  formation: string;
  total_smartplay_score: number;
  avg_smartplay_score: number;
  starting_xi: LineupPlayer[];
  bench: BenchPlayer[];
  captain: CaptainPick | null;
  vice_captain: ViceCaptainPick | null;
  summary: string;
  description: string;
}

export interface LineupStrategiesResponse {
  strategies: FormationStrategy[];
  recommended: string;
}

export async function getLineupStrategies(
  teamId: string,
  transfers?: { outIds: number[]; inIds: number[] }
): Promise<LineupStrategiesResponse> {
  let url = `${API_BASE}/lineup-strategies/${teamId}`;

  // Add transfer parameters if provided
  if (transfers && (transfers.outIds.length > 0 || transfers.inIds.length > 0)) {
    const params = new URLSearchParams();
    if (transfers.outIds.length > 0) {
      params.append("transfers_out", transfers.outIds.join(","));
    }
    if (transfers.inIds.length > 0) {
      params.append("transfers_in", transfers.inIds.join(","));
    }
    url += `?${params.toString()}`;
  }

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error("Failed to fetch lineup strategies");
  }

  return response.json();
}

// =============================================================================
// Chip Advice Types (Step 5)
// =============================================================================

export interface ChipRecommendation {
  chip: string; // wildcard, freehit, bboost, 3xc
  name: string;
  recommendation: string; // consider, save
  score: number;
  reasons: string[];
  message: string;
}

export interface ChipAdviceResponse {
  available_chips: string[];
  recommendations: ChipRecommendation[];
  overall_advice: string;
}

export async function getChipAdvice(teamId: string): Promise<ChipAdviceResponse> {
  const response = await fetch(`${API_BASE}/chip-advice/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch chip advice");
  }

  return response.json();
}

// =============================================================================
// Crowd Intelligence Types
// =============================================================================

export interface CrowdPlayer {
  id: number;
  name: string;
  team: string;
  position: string;
  ownership: number;
  form: number;
  transfers_in: number;
  transfers_out: number;
}

export interface CrowdIntelligenceCard {
  title: string;
  subtitle: string;
  players: CrowdPlayer[];
}

export interface CrowdIntelligenceResponse {
  differential_percentage: number;
  // You Have
  shared_picks: CrowdIntelligenceCard;
  your_edge: CrowdIntelligenceCard;
  rising: CrowdIntelligenceCard;
  being_sold: CrowdIntelligenceCard;
  // You Don't Have
  template_misses: CrowdIntelligenceCard;
  hidden_gems: CrowdIntelligenceCard;
  bandwagons: CrowdIntelligenceCard;
  form_leaders: CrowdIntelligenceCard;
}

export async function getCrowdIntelligence(teamId: string): Promise<CrowdIntelligenceResponse> {
  const response = await fetch(`${API_BASE}/crowd-intelligence/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch crowd intelligence");
  }

  return response.json();
}

// =============================================================================
// Decision Quality Types
// =============================================================================

export interface TransferQuality {
  success_rate: number; // 0-100
  net_points_gained: number;
  hits_taken: number;
  total_transfers: number;
}

export interface CaptainQuality {
  success_rate: number; // 0-100
  captain_points: number;
  most_captained: string;
  most_captained_count: number;
}

export interface BenchManagement {
  points_on_bench: number;
  per_gameweek: number;
  insight: string;
}

export interface DecisionQualityResponse {
  overall_score: number; // 0-100
  overall_insight: string;
  key_insight: string;
  transfer_quality: TransferQuality;
  captain_quality: CaptainQuality;
  bench_management: BenchManagement;
  gameweeks_analyzed: number;
}

export async function getDecisionQuality(teamId: string): Promise<DecisionQualityResponse> {
  const response = await fetch(`${API_BASE}/decision-quality/${teamId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch decision quality");
  }

  return response.json();
}

// =============================================================================
// Player Alternatives Types
// =============================================================================

export interface PlayerAlternative {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  total_points: number;
  ownership: number;
  smartplay_score: number;
  reasons: string[];
  price_diff: number;
  rank: number;
}

export interface PlayerAlternativesResponse {
  player_id: number;
  player_name: string;
  player_team: string;
  player_position: string;
  player_price: number;
  player_form: number;
  budget: number;
  bank: number;
  alternatives: PlayerAlternative[];
}

export async function getPlayerAlternatives(
  playerId: number,
  teamId: string,
  limit: number = 3
): Promise<PlayerAlternativesResponse> {
  const response = await fetch(
    `${API_BASE}/player-alternatives/${playerId}?team_id=${teamId}&limit=${limit}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Player ${playerId} not found`);
    }
    throw new Error("Failed to fetch player alternatives");
  }

  return response.json();
}

// =============================================================================
// AI Transfer Analysis Types
// =============================================================================

export interface SellCandidate {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  verdict: string; // SELL, HOLD, KEEPER
  priority: string; // critical, high, medium, low
  reasoning: string;
  alternative_view: string;
  smartplay_score: number;
  form: number;
  minutes: number;
  ownership: number;
  transfers_out: number;
  fixture_run_score: number;
  status: string;
  news: string;
}

export interface SellAnalysisResponse {
  candidates: SellCandidate[];
  summary: string;
  ai_model: string;
}

export interface BuyCandidate {
  id: number;
  name: string;
  team: string;
  position: string;
  price: number;
  form: number;
  total_points: number;
  ownership: number;
  reasoning: string;
  smartplay_score: number;
  replaces: string;
  price_diff: number;
}

export interface BuyAnalysisResponse {
  recommendations: BuyCandidate[];
  budget_available: number;
  summary: string;
  ai_model: string;
}

export async function getSellAnalysis(teamId: string): Promise<SellAnalysisResponse> {
  try {
    const response = await fetch(`${API_BASE}/sell-analysis/${teamId}`);

    if (!response.ok) {
      if (response.status === 503) {
        throw new Error("AI service not available. Please configure API key.");
      }
      throw new Error(`Failed to fetch sell analysis (status: ${response.status})`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error("Network error - please check your connection and try again");
    }
    throw err;
  }
}

export async function getBuyAnalysis(
  teamId: string,
  sellIds: number[]
): Promise<BuyAnalysisResponse> {
  try {
    const sellIdsParam = sellIds.join(",");
    const response = await fetch(
      `${API_BASE}/buy-analysis/${teamId}?sell_ids=${sellIdsParam}`
    );

    if (!response.ok) {
      if (response.status === 503) {
        throw new Error("AI service not available. Please configure API key.");
      }
      throw new Error(`Failed to fetch buy analysis (status: ${response.status})`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error("Network error - please check your connection and try again");
    }
    throw err;
  }
}

// =============================================================================
// Squad Analysis Types
// =============================================================================

export interface SquadOptimizationTip {
  type: string; // balance, structure, value, risk, opportunity, transfer_chain
  icon: string;
  title: string;
  description: string;
  priority: string; // high, medium, low
}

export interface ChipStrategy {
  chip: string; // wildcard, freehit, bboost, 3xc, none
  chip_name: string; // Display name
  should_use: boolean; // Whether to use this week
  reasoning: string; // Why to use or not use
  confidence: number; // 0-100 confidence in recommendation
}

export interface SquadAnalysisResponse {
  summary: string;
  score: number;
  strengths: string[];
  weaknesses: string[];
  optimization_tips: SquadOptimizationTip[];
  chip_strategy?: ChipStrategy;
  ai_model: string;
}

export interface TransferForAnalysis {
  out_id: number;
  out_name: string;
  out_team: string;
  in_id: number;
  in_name: string;
  in_team: string;
  price_diff: number;
}

export async function getSquadAnalysis(
  teamId: string,
  transfers: TransferForAnalysis[] = []
): Promise<SquadAnalysisResponse> {
  const response = await fetch(`${API_BASE}/squad-analysis/${teamId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(transfers),
  });

  if (!response.ok) {
    if (response.status === 503) {
      throw new Error("AI service not available. Please configure API key.");
    }
    throw new Error("Failed to fetch squad analysis");
  }

  return response.json();
}
