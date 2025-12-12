"use client";

import { createContext, useContext, useState, useCallback, ReactNode, useMemo } from "react";
import type {
  PlayerSummary,
  GWReviewResponse,
  AlertsResponse,
  WorkflowTransferSuggestionsResponse,
  WorkflowTransferSuggestion,
  LineupResponse,
  ChipAdviceResponse,
  LineupPlayer,
  BenchPlayer,
  FormationStrategy,
  LineupStrategiesResponse,
  SellAnalysisResponse,
  BuyAnalysisResponse,
} from "@/lib/api";
import {
  getGWReview,
  getAlerts,
  getWorkflowTransferSuggestions,
  getLineupRecommendation,
  getChipAdvice,
  getLineupStrategies,
} from "@/lib/api";

// 7 workflow steps (in decision-making order) - Chips moved to Lineup, Feedback at end
export type WorkflowStep = "review" | "alerts" | "transfers" | "lineup" | "captain" | "confirm" | "feedback";

// Step order for enforcing sequential progression
export const STEP_ORDER: WorkflowStep[] = ["review", "alerts", "transfers", "lineup", "captain", "confirm", "feedback"];

export interface AppliedTransfer {
  suggestion: WorkflowTransferSuggestion;
  selected: boolean; // User has marked this transfer for consideration
  applied: boolean;  // User has clicked "Apply" to update the pitch
  selectedAlternativeIndex: number; // Index in alternatives array (0 = top recommendation)
}

interface TransferWorkflowState {
  step: WorkflowStep;
  teamId: string;

  // Step completion tracking for sequential workflow
  completedSteps: Set<WorkflowStep>;
  highestReachedStep: WorkflowStep;
  markStepCompleted: (step: WorkflowStep) => void;
  advanceToStep: (currentStep: WorkflowStep, nextStep: WorkflowStep) => void;
  canAccessStep: (step: WorkflowStep) => boolean;
  getStepProgress: () => { completed: number; total: number; percentage: number };

  // Original squad (from parent)
  originalSquad: PlayerSummary[];

  // Step 1: GW Review data
  gwReview: GWReviewResponse | null;
  gwReviewLoading: boolean;

  // Step 2: Alerts data
  alerts: AlertsResponse | null;
  alertsLoading: boolean;

  // Step 3: Transfer suggestions
  transferSuggestions: WorkflowTransferSuggestionsResponse | null;
  transfersLoading: boolean;

  // AI Sell/Buy Analysis (for wizard workflow)
  sellAnalysis: SellAnalysisResponse | null;
  buyAnalysis: BuyAnalysisResponse | null;
  setSellAnalysis: (data: SellAnalysisResponse | null) => void;
  setBuyAnalysis: (data: BuyAnalysisResponse | null) => void;

  // Step 4: Lineup recommendation
  lineup: LineupResponse | null;
  lineupLoading: boolean;

  // Step 5: Chip advice
  chipAdvice: ChipAdviceResponse | null;
  chipAdviceLoading: boolean;

  // Lineup strategies (loaded in lineup step)
  lineupStrategies: LineupStrategiesResponse | null;
  lineupStrategiesLoading: boolean;
  selectedStrategy: FormationStrategy | null;
  selectedPlayerForCard: LineupPlayer | BenchPlayer | null;

  // Player alternatives (for pitch clicks in transfers mode)
  selectedPlayerForAlternatives: { id: number; name: string } | null;

  // User selections (old workflow - deprecated)
  appliedTransfers: AppliedTransfer[];

  // Wizard selections: candidateId -> selectedReplacementId (null = skipped, undefined = not decided)
  wizardSelections: Record<number, number | null | undefined>;
  setWizardSelections: (selections: Record<number, number | null | undefined>) => void;
  updateWizardSelection: (candidateId: number, replacementId: number | null | undefined) => void;
  clearWizardSelections: () => void;

  // Derived preview squad (reflects wizard selections if in transfers step)
  previewSquad: PlayerSummary[];

  // Optimized lineup squad (derived from lineup response)
  optimizedSquad: PlayerSummary[];
  optimizedFormation: string;

  // Captain selection (user override of AI recommendations)
  selectedCaptainId: number | null;
  selectedViceCaptainId: number | null;
  setSelectedCaptainId: (id: number | null) => void;
  setSelectedViceCaptainId: (id: number | null) => void;

  // Actions
  setStep: (step: WorkflowStep) => void;
  loadGWReview: () => Promise<void>;
  loadAlerts: () => Promise<void>;
  loadTransferSuggestions: () => Promise<void>;
  loadLineup: () => Promise<void>;
  loadChipAdvice: () => Promise<void>;
  loadLineupStrategies: () => Promise<void>;
  selectStrategy: (strategyKey: string) => void;
  setSelectedPlayerForCard: (player: LineupPlayer | BenchPlayer | null) => void;
  setSelectedPlayerForAlternatives: (player: { id: number; name: string } | null) => void;
  toggleTransfer: (index: number) => void;
  selectAlternative: (transferIndex: number, alternativeIndex: number) => void;
  applySelectedTransfers: () => void;
  resetTransfers: () => void;
  resetWorkflow: () => void;

  // Visual mode for pitch
  pitchMode: "normal" | "review" | "alerts" | "transfers" | "lineup" | "captain" | "confirm" | "feedback";
  highlightedPlayerIds: Set<number>;
  transferOutIds: Set<number>;
  transferInIds: Set<number>;
}

const TransferWorkflowContext = createContext<TransferWorkflowState | null>(null);

export function useTransferWorkflow() {
  const context = useContext(TransferWorkflowContext);
  if (!context) {
    throw new Error("useTransferWorkflow must be used within TransferWorkflowProvider");
  }
  return context;
}

interface ProviderProps {
  children: ReactNode;
  teamId: string;
  originalSquad: PlayerSummary[];
}

export function TransferWorkflowProvider({ children, teamId, originalSquad }: ProviderProps) {
  const [step, setStepInternal] = useState<WorkflowStep>("review");

  // Step completion tracking - tracks which steps the user has completed
  const [completedSteps, setCompletedSteps] = useState<Set<WorkflowStep>>(new Set());
  const [highestReachedStep, setHighestReachedStep] = useState<WorkflowStep>("review");

  // Captain selection (user override of AI recommendations)
  const [selectedCaptainId, setSelectedCaptainId] = useState<number | null>(null);
  const [selectedViceCaptainId, setSelectedViceCaptainId] = useState<number | null>(null);

  // Mark a step as completed and update highest reached
  const markStepCompleted = useCallback((stepToMark: WorkflowStep) => {
    setCompletedSteps(prev => new Set([...prev, stepToMark]));

    // Update highest reached step if this is further in the workflow
    const currentIndex = STEP_ORDER.indexOf(stepToMark);
    const highestIndex = STEP_ORDER.indexOf(highestReachedStep);
    if (currentIndex >= highestIndex) {
      const nextIndex = Math.min(currentIndex + 1, STEP_ORDER.length - 1);
      setHighestReachedStep(STEP_ORDER[nextIndex]);
    }
  }, [highestReachedStep]);

  // Atomically mark current step complete AND navigate to next step (bypasses access check)
  const advanceToStep = useCallback((currentStep: WorkflowStep, nextStep: WorkflowStep) => {
    // Mark current step as completed
    setCompletedSteps(prev => new Set([...prev, currentStep]));

    // Update highest reached step to the next step
    const nextIndex = STEP_ORDER.indexOf(nextStep);
    setHighestReachedStep(prev => {
      const prevIndex = STEP_ORDER.indexOf(prev);
      return nextIndex > prevIndex ? nextStep : prev;
    });

    // Navigate directly (no access check needed since we're advancing forward)
    setStepInternal(nextStep);
  }, []);

  // Check if a step can be accessed (must be completed step or the next available)
  const canAccessStep = useCallback((targetStep: WorkflowStep): boolean => {
    const targetIndex = STEP_ORDER.indexOf(targetStep);
    const highestIndex = STEP_ORDER.indexOf(highestReachedStep);

    // Can access if it's at or before the highest reached step
    return targetIndex <= highestIndex;
  }, [highestReachedStep]);

  // Get progress percentage
  const getStepProgress = useCallback(() => {
    const completed = completedSteps.size;
    const total = STEP_ORDER.length;
    const percentage = Math.round((completed / total) * 100);
    return { completed, total, percentage };
  }, [completedSteps]);

  // Wrapper for setStep that respects sequential order
  const setStep = useCallback((newStep: WorkflowStep) => {
    if (canAccessStep(newStep)) {
      setStepInternal(newStep);
    }
  }, [canAccessStep]);

  // Step 1: GW Review
  const [gwReview, setGwReview] = useState<GWReviewResponse | null>(null);
  const [gwReviewLoading, setGwReviewLoading] = useState(false);

  // Step 2: Alerts
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(false);

  // Step 3: Transfers
  const [transferSuggestions, setTransferSuggestions] = useState<WorkflowTransferSuggestionsResponse | null>(null);
  const [transfersLoading, setTransfersLoading] = useState(false);
  const [appliedTransfers, setAppliedTransfers] = useState<AppliedTransfer[]>([]);

  // Wizard selections for new workflow
  const [wizardSelections, setWizardSelections] = useState<Record<number, number | null | undefined>>({});

  // AI Sell/Buy Analysis for wizard workflow
  const [sellAnalysis, setSellAnalysis] = useState<SellAnalysisResponse | null>(null);
  const [buyAnalysis, setBuyAnalysis] = useState<BuyAnalysisResponse | null>(null);

  // Step 4: Lineup
  const [lineup, setLineup] = useState<LineupResponse | null>(null);
  const [lineupLoading, setLineupLoading] = useState(false);

  // Step 5: Chips
  const [chipAdvice, setChipAdvice] = useState<ChipAdviceResponse | null>(null);
  const [chipAdviceLoading, setChipAdviceLoading] = useState(false);

  // Lineup Strategies
  const [lineupStrategies, setLineupStrategies] = useState<LineupStrategiesResponse | null>(null);
  const [lineupStrategiesLoading, setLineupStrategiesLoading] = useState(false);
  const [selectedStrategyKey, setSelectedStrategyKey] = useState<string>("balanced");
  const [selectedPlayerForCard, setSelectedPlayerForCard] = useState<LineupPlayer | BenchPlayer | null>(null);

  // Player alternatives (for pitch clicks in transfers mode)
  const [selectedPlayerForAlternatives, setSelectedPlayerForAlternatives] = useState<{ id: number; name: string } | null>(null);

  // Step 1: Load GW Review
  const loadGWReview = useCallback(async () => {
    if (gwReview) return;
    setGwReviewLoading(true);
    try {
      const data = await getGWReview(teamId);
      setGwReview(data);
    } catch (err) {
      console.error("Failed to load GW review:", err);
    } finally {
      setGwReviewLoading(false);
    }
  }, [teamId, gwReview]);

  // Step 2: Load Alerts
  const loadAlerts = useCallback(async () => {
    if (alerts) return;
    setAlertsLoading(true);
    try {
      const data = await getAlerts(teamId);
      setAlerts(data);
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setAlertsLoading(false);
    }
  }, [teamId, alerts]);

  // Step 3: Load Transfer Suggestions
  const loadTransferSuggestions = useCallback(async () => {
    if (transferSuggestions) return;
    setTransfersLoading(true);
    try {
      const data = await getWorkflowTransferSuggestions(teamId);
      setTransferSuggestions(data);
      setAppliedTransfers(data.suggestions.map(s => ({ suggestion: s, selected: false, applied: false, selectedAlternativeIndex: 0 })));
    } catch (err) {
      console.error("Failed to load transfer suggestions:", err);
    } finally {
      setTransfersLoading(false);
    }
  }, [teamId, transferSuggestions]);

  // Step 4: Load Lineup
  const loadLineup = useCallback(async () => {
    if (lineup) return;
    setLineupLoading(true);
    try {
      const data = await getLineupRecommendation(teamId);
      setLineup(data);
    } catch (err) {
      console.error("Failed to load lineup:", err);
    } finally {
      setLineupLoading(false);
    }
  }, [teamId, lineup]);

  // Step 5: Load Chip Advice
  const loadChipAdvice = useCallback(async () => {
    if (chipAdvice) return;
    setChipAdviceLoading(true);
    try {
      const data = await getChipAdvice(teamId);
      setChipAdvice(data);
    } catch (err) {
      console.error("Failed to load chip advice:", err);
    } finally {
      setChipAdviceLoading(false);
    }
  }, [teamId, chipAdvice]);

  // Load Lineup Strategies - needs to be a function that can be called fresh with current transfers
  const loadLineupStrategies = useCallback(async () => {
    // Skip if we already have strategies (reset lineupStrategies to null to force reload)
    if (lineupStrategies) return;

    setLineupStrategiesLoading(true);
    try {
      let outIds: number[] = [];
      let inIds: number[] = [];

      // Priority 1: Use wizard selections (new workflow)
      if (sellAnalysis && buyAnalysis && Object.keys(wizardSelections).length > 0) {
        Object.entries(wizardSelections).forEach(([candIdStr, repId]) => {
          if (repId === null || repId === undefined) return; // Skipped or not decided
          const candId = parseInt(candIdStr);
          outIds.push(candId);
          inIds.push(repId);
        });
      }
      // Fallback: Use old applied transfers workflow
      else {
        outIds = appliedTransfers
          .filter(t => t.applied)
          .map(t => t.suggestion.out.id);
        inIds = appliedTransfers
          .filter(t => t.applied)
          .map(t => {
            const selectedAlt = t.suggestion.alternatives?.[t.selectedAlternativeIndex];
            return selectedAlt?.id || t.suggestion.in_player.id;
          });
      }

      // Pass transfers if any are applied
      const transfers = (outIds.length > 0 || inIds.length > 0)
        ? { outIds, inIds }
        : undefined;

      const data = await getLineupStrategies(teamId, transfers);
      setLineupStrategies(data);
      setSelectedStrategyKey(data.recommended);
    } catch (err) {
      console.error("Failed to load lineup strategies:", err);
      throw err; // Re-throw so UI can handle it
    } finally {
      setLineupStrategiesLoading(false);
    }
  }, [teamId, appliedTransfers, wizardSelections, sellAnalysis, buyAnalysis, lineupStrategies]);

  // Select a strategy
  const selectStrategy = useCallback((strategyKey: string) => {
    setSelectedStrategyKey(strategyKey);
    setSelectedPlayerForCard(null); // Clear selected player when changing strategy
  }, []);

  const toggleTransfer = useCallback((index: number) => {
    setAppliedTransfers(prev =>
      prev.map((t, i) => i === index ? { ...t, selected: !t.selected } : t)
    );
  }, []);

  const selectAlternative = useCallback((transferIndex: number, alternativeIndex: number) => {
    setAppliedTransfers(prev =>
      prev.map((t, i) => i === transferIndex ? { ...t, selectedAlternativeIndex: alternativeIndex } : t)
    );
  }, []);

  // Apply all selected transfers - this updates the pitch visualization
  const applySelectedTransfers = useCallback(() => {
    setAppliedTransfers(prev =>
      prev.map(t => t.selected ? { ...t, applied: true } : t)
    );
    // Reset lineup strategies so fresh data is fetched when navigating to lineup tab
    setLineupStrategies(null);
  }, []);

  // Wizard selection management
  const updateWizardSelection = useCallback((candidateId: number, replacementId: number | null | undefined) => {
    setWizardSelections(prev => ({
      ...prev,
      [candidateId]: replacementId,
    }));
    // Reset lineup strategies when any transfer changes so fresh data is fetched
    setLineupStrategies(null);
  }, []);

  const clearWizardSelections = useCallback(() => {
    setWizardSelections({});
    // Reset lineup strategies so fresh data is fetched when navigating to lineup tab
    setLineupStrategies(null);
  }, []);

  // Reset all transfers (undo applied transfers, stay on transfers tab)
  const resetTransfers = useCallback(() => {
    setAppliedTransfers(prev => prev.map(t => ({ ...t, selected: false, applied: false, selectedAlternativeIndex: 0 })));
    clearWizardSelections();
    // Reset lineup strategies so fresh data is fetched when navigating to lineup tab
    setLineupStrategies(null);
  }, [clearWizardSelections]);

  const resetWorkflow = useCallback(() => {
    setStep("review");
    setAppliedTransfers(prev => prev.map(t => ({ ...t, selected: false, applied: false, selectedAlternativeIndex: 0 })));
  }, []);

  // Calculate preview squad based on wizard selections (new workflow) or applied transfers (old workflow)
  const previewSquad = [...originalSquad];
  const transferOutIds = new Set<number>();
  const transferInIds = new Set<number>();

  // Priority 1: Use wizard selections (new transfer workflow)
  if (sellAnalysis && buyAnalysis && Object.keys(wizardSelections).length > 0) {
    Object.entries(wizardSelections).forEach(([candIdStr, repId]) => {
      if (repId === null || repId === undefined) return; // Skipped or not decided

      const candId = parseInt(candIdStr);
      const candidate = sellAnalysis.candidates.find(c => c.id === candId);
      const replacement = buyAnalysis.recommendations.find(r => r.id === repId);

      if (candidate && replacement) {
        transferOutIds.add(candidate.id);
        transferInIds.add(replacement.id);

        // Replace player in preview squad
        const idx = previewSquad.findIndex(p => p.id === candidate.id);
        if (idx !== -1) {
          previewSquad[idx] = {
            ...previewSquad[idx],
            id: replacement.id,
            name: replacement.name,
            team: replacement.team,
            position: replacement.position,
            price: replacement.price,
            form: replacement.form,
            points: replacement.total_points,
            ownership: replacement.ownership,
          };
        }
      }
    });
  }
  // Fallback: Use old applied transfers workflow
  else {
    appliedTransfers.forEach(({ suggestion, applied, selectedAlternativeIndex }) => {
      if (applied) {
        transferOutIds.add(suggestion.out.id);

        // Get the selected alternative (use alternatives array if available)
        const selectedAlt = suggestion.alternatives?.[selectedAlternativeIndex];
        const inPlayer = selectedAlt || suggestion.in_player;

        transferInIds.add(inPlayer.id);

        // Replace player in preview squad
        const idx = previewSquad.findIndex(p => p.id === suggestion.out.id);
        if (idx !== -1) {
          previewSquad[idx] = {
            ...previewSquad[idx],
            id: inPlayer.id,
            name: inPlayer.name,
            team: inPlayer.team,
            position: inPlayer.position,
            price: inPlayer.price,
            form: inPlayer.form,
          };
        }
      }
    });
  }

  // Get the current selected strategy
  const selectedStrategy = useMemo(() => {
    if (!lineupStrategies) return null;
    return lineupStrategies.strategies.find(s => s.strategy === selectedStrategyKey) || lineupStrategies.strategies[0];
  }, [lineupStrategies, selectedStrategyKey]);

  // Build optimized squad from selected strategy (or fallback to lineup response)
  // Uses selectedCaptainId to apply user's captain override
  const optimizedSquad: PlayerSummary[] = useMemo(() => {
    // Effective captain ID: user selection or AI recommendation
    const effectiveCaptainId = selectedCaptainId ?? lineup?.captain?.id;
    const effectiveViceCaptainId = selectedViceCaptainId ?? lineup?.vice_captain?.id;

    // Convert lineup players to PlayerSummary format with captain override
    const lineupToPlayerSummary = (player: LineupPlayer | BenchPlayer, isStarter: boolean): PlayerSummary => ({
      id: player.id,
      name: player.name,
      team: player.team,
      position: player.position,
      price: player.price,
      form: player.form,
      points: player.points,
      gw_points: player.gw_points,
      ownership: player.ownership,
      status: player.status,
      news: player.news,
      is_captain: player.id === effectiveCaptainId,
      is_vice_captain: player.id === effectiveViceCaptainId,
      multiplier: isStarter ? (player.id === effectiveCaptainId ? 2 : 1) : 0,
    });

    // First priority: use selected strategy from lineup strategies
    if (selectedStrategy) {
      const starting = selectedStrategy.starting_xi.map(p => lineupToPlayerSummary(p, true));
      const bench = selectedStrategy.bench
        .sort((a, b) => a.order - b.order)
        .map(p => lineupToPlayerSummary(p, false));
      return [...starting, ...bench];
    }

    // Fallback to lineup response (for captain step)
    if (!lineup) return [];
    const starting = lineup.starting_xi.map(p => lineupToPlayerSummary(p, true));
    const bench = lineup.bench
      .sort((a, b) => a.order - b.order)
      .map(p => lineupToPlayerSummary(p, false));
    return [...starting, ...bench];
  }, [selectedStrategy, lineup, selectedCaptainId, selectedViceCaptainId]);

  // Get optimized formation from selected strategy or lineup response
  const optimizedFormation = selectedStrategy?.formation || lineup?.formation || "";

  // Determine pitch mode and highlighted players
  let pitchMode: TransferWorkflowState["pitchMode"] = "normal";
  let highlightedPlayerIds = new Set<number>();

  if (step === "review") {
    pitchMode = "review";
    // Highlight underperformers (gw_points <= 2)
    highlightedPlayerIds = new Set(
      originalSquad.filter(p => p.gw_points <= 2 && p.multiplier > 0).map(p => p.id)
    );
  } else if (step === "alerts") {
    pitchMode = "alerts";
    // Highlight players with alerts
    if (alerts) {
      highlightedPlayerIds = new Set(
        alerts.alerts.filter(a => a.player_id).map(a => a.player_id!)
      );
    }
  } else if (step === "transfers") {
    pitchMode = "transfers";
    // Highlight players suggested to transfer out
    highlightedPlayerIds = new Set(
      appliedTransfers.map(t => t.suggestion.out.id)
    );
  } else if (step === "lineup") {
    pitchMode = "lineup";
  } else if (step === "captain") {
    pitchMode = "captain";
    // Highlight captain and vice-captain recommendations
    if (lineup) {
      highlightedPlayerIds = new Set([
        lineup.captain?.id,
        lineup.vice_captain?.id,
      ].filter(Boolean) as number[]);
    }
  } else if (step === "confirm") {
    pitchMode = "confirm";
  } else if (step === "feedback") {
    pitchMode = "feedback";
  }

  const value: TransferWorkflowState = {
    step,
    teamId,
    completedSteps,
    highestReachedStep,
    markStepCompleted,
    advanceToStep,
    canAccessStep,
    getStepProgress,
    originalSquad,
    gwReview,
    gwReviewLoading,
    alerts,
    alertsLoading,
    transferSuggestions,
    transfersLoading,
    sellAnalysis,
    buyAnalysis,
    setSellAnalysis,
    setBuyAnalysis,
    lineup,
    lineupLoading,
    chipAdvice,
    chipAdviceLoading,
    lineupStrategies,
    lineupStrategiesLoading,
    selectedStrategy,
    selectedPlayerForCard,
    selectedPlayerForAlternatives,
    appliedTransfers,
    wizardSelections,
    setWizardSelections,
    updateWizardSelection,
    clearWizardSelections,
    previewSquad,
    optimizedSquad,
    optimizedFormation,
    selectedCaptainId,
    selectedViceCaptainId,
    setSelectedCaptainId,
    setSelectedViceCaptainId,
    setStep,
    loadGWReview,
    loadAlerts,
    loadTransferSuggestions,
    loadLineup,
    loadChipAdvice,
    loadLineupStrategies,
    selectStrategy,
    setSelectedPlayerForCard,
    setSelectedPlayerForAlternatives,
    toggleTransfer,
    selectAlternative,
    applySelectedTransfers,
    resetTransfers,
    resetWorkflow,
    pitchMode,
    highlightedPlayerIds,
    transferOutIds,
    transferInIds,
  };

  return (
    <TransferWorkflowContext.Provider value={value}>
      {children}
    </TransferWorkflowContext.Provider>
  );
}
