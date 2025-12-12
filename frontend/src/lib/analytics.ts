/**
 * SmartPlay FPL Analytics Library
 *
 * Comprehensive analytics tracking for user behavior analysis.
 * Supports Google Analytics 4, custom events, and performance monitoring.
 */

// Types for analytics events
export interface AnalyticsEvent {
  name: string;
  properties?: Record<string, string | number | boolean | undefined>;
}

export interface UserProperties {
  user_id?: string;
  returning_user?: boolean;
  preferred_view?: string;
  total_teams_analyzed?: number;
}

// =============================================================================
// ENVIRONMENT DETECTION
// =============================================================================
// Analytics tracking is DISABLED in development to avoid polluting production data.
// Set NEXT_PUBLIC_GA_MEASUREMENT_ID in Vercel for production tracking.

// Check if we're in browser
const isClient = typeof window !== 'undefined';

// Check environment - uses NEXT_PUBLIC_ENVIRONMENT first, falls back to NODE_ENV
const isDevelopment = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development' ||
  process.env.NODE_ENV === 'development';
const isProduction = !isDevelopment;

// GA4 Measurement ID - only set from environment variable in production
// In development, this will be empty (from .env.local) and GA will be disabled
const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '';

// Check if GA tracking is enabled (only in production with a valid measurement ID)
const isGAEnabled = isProduction && !!GA_MEASUREMENT_ID;

// Initialize gtag
declare global {
  interface Window {
    gtag: (...args: unknown[]) => void;
    dataLayer: unknown[];
  }
}

/**
 * Initialize Google Analytics
 * Only initializes in production with a valid measurement ID
 */
export function initGA(): void {
  if (!isClient) return;

  // Skip GA initialization in development
  if (!isGAEnabled) {
    console.log('[Analytics] GA disabled (development mode or no measurement ID)');
    return;
  }

  // Create gtag function
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag(...args: unknown[]) {
    window.dataLayer.push(args);
  };

  window.gtag('js', new Date());
  window.gtag('config', GA_MEASUREMENT_ID, {
    page_path: window.location.pathname,
    send_page_view: true,
    // Enhanced measurement settings
    anonymize_ip: true,
    cookie_flags: 'SameSite=None;Secure',
  });

  console.log('[Analytics] GA initialized with ID:', GA_MEASUREMENT_ID);
}

/**
 * Track page views
 * Only sends to GA in production; logs to console in development
 */
export function trackPageView(url: string, title?: string): void {
  if (!isClient) return;

  // Console logging in development (always log for debugging)
  if (isDevelopment) {
    console.log('[Analytics] Page View (dev mode - not sent to GA):', { url, title });
    return;
  }

  // GA4 tracking - only in production with valid measurement ID
  if (isGAEnabled && window.gtag) {
    window.gtag('config', GA_MEASUREMENT_ID, {
      page_path: url,
      page_title: title,
    });
  }
}

/**
 * Track custom events
 * Only sends to GA in production; logs to console in development
 */
export function trackEvent(event: AnalyticsEvent): void {
  if (!isClient) return;

  const { name, properties = {} } = event;

  // Console logging in development (always log for debugging)
  if (isDevelopment) {
    console.log('[Analytics] Event (dev mode - not sent to GA):', name, properties);
    return;
  }

  // GA4 tracking - only in production with valid measurement ID
  if (isGAEnabled && window.gtag) {
    window.gtag('event', name, properties);
  }
}

/**
 * Set user properties
 * Only sends to GA in production; logs to console in development
 */
export function setUserProperties(properties: UserProperties): void {
  if (!isClient) return;

  // Console logging in development (always log for debugging)
  if (isDevelopment) {
    console.log('[Analytics] User Properties (dev mode - not sent to GA):', properties);
    return;
  }

  // GA4 tracking - only in production with valid measurement ID
  if (isGAEnabled && window.gtag) {
    window.gtag('config', GA_MEASUREMENT_ID, {
      user_properties: properties,
    });
  }
}

// =============================================================================
// FPL-SPECIFIC EVENT TRACKING
// =============================================================================

/**
 * Track when a user analyzes their team
 */
export function trackTeamAnalysis(teamId: string, isReturning: boolean = false): void {
  trackEvent({
    name: 'team_analysis_started',
    properties: {
      team_id: teamId,
      is_returning_user: isReturning,
      timestamp: new Date().toISOString(),
    },
  });
}

/**
 * Track team analysis completion
 */
export function trackTeamAnalysisComplete(teamId: string, loadTimeMs: number): void {
  trackEvent({
    name: 'team_analysis_complete',
    properties: {
      team_id: teamId,
      load_time_ms: loadTimeMs,
    },
  });
}

/**
 * Track workflow tab navigation
 */
export function trackWorkflowTab(tabName: string, fromTab?: string): void {
  trackEvent({
    name: 'workflow_tab_click',
    properties: {
      tab_name: tabName,
      from_tab: fromTab,
    },
  });
}

/**
 * Track transfer workflow actions
 */
export function trackTransferAction(
  action: 'start' | 'select_out' | 'select_in' | 'complete' | 'cancel',
  details?: Record<string, string | number>
): void {
  trackEvent({
    name: 'transfer_action',
    properties: {
      action,
      ...details,
    },
  });
}

/**
 * Track captain selection
 */
export function trackCaptainSelection(
  playerId: number,
  playerName: string,
  pickType: 'safe' | 'balanced' | 'differential'
): void {
  trackEvent({
    name: 'captain_selection',
    properties: {
      player_id: playerId,
      player_name: playerName,
      pick_type: pickType,
    },
  });
}

/**
 * Track squad builder usage
 */
export function trackSquadBuilder(
  action: 'start' | 'strategy_select' | 'budget_change' | 'generate' | 'complete',
  details?: Record<string, string | number>
): void {
  trackEvent({
    name: 'squad_builder',
    properties: {
      action,
      ...details,
    },
  });
}

/**
 * Track player search/filter
 */
export function trackPlayerSearch(filters: Record<string, string | number | boolean>): void {
  trackEvent({
    name: 'player_search',
    properties: {
      ...filters,
      filter_count: Object.keys(filters).length,
    },
  });
}

/**
 * Track player comparison
 */
export function trackPlayerComparison(playerIds: number[], playerNames: string[]): void {
  trackEvent({
    name: 'player_comparison',
    properties: {
      player_count: playerIds.length,
      player_ids: playerIds.join(','),
      player_names: playerNames.join(','),
    },
  });
}

/**
 * Track FPL ID lookup help
 */
export function trackFplIdHelp(action: 'view' | 'expand_step' | 'success'): void {
  trackEvent({
    name: 'fpl_id_help',
    properties: { action },
  });
}

/**
 * Track view mode toggle (pitch vs list)
 */
export function trackViewModeToggle(mode: 'pitch' | 'list'): void {
  trackEvent({
    name: 'view_mode_toggle',
    properties: { mode },
  });
}

/**
 * Track chip strategy views
 */
export function trackChipStrategy(chipType: string, action: 'view' | 'activate'): void {
  trackEvent({
    name: 'chip_strategy',
    properties: {
      chip_type: chipType,
      action,
    },
  });
}

/**
 * Track crowd insights engagement
 */
export function trackCrowdInsights(section: string, action: 'view' | 'expand' | 'click'): void {
  trackEvent({
    name: 'crowd_insights',
    properties: {
      section,
      action,
    },
  });
}

/**
 * Track external link clicks
 */
export function trackExternalLink(url: string, context: string): void {
  trackEvent({
    name: 'external_link_click',
    properties: {
      url,
      context,
    },
  });
}

/**
 * Track error occurrences
 */
export function trackError(errorType: string, errorMessage: string, context?: string): void {
  trackEvent({
    name: 'error_occurred',
    properties: {
      error_type: errorType,
      error_message: errorMessage.substring(0, 100), // Truncate long messages
      context,
    },
  });
}

/**
 * Track API response times
 */
export function trackApiPerformance(endpoint: string, durationMs: number, success: boolean): void {
  trackEvent({
    name: 'api_performance',
    properties: {
      endpoint,
      duration_ms: durationMs,
      success,
    },
  });
}

// =============================================================================
// ENGAGEMENT METRICS
// =============================================================================

/**
 * Track scroll depth
 */
export function trackScrollDepth(depth: 25 | 50 | 75 | 100, pageName: string): void {
  trackEvent({
    name: 'scroll_depth',
    properties: {
      depth_percent: depth,
      page: pageName,
    },
  });
}

/**
 * Track time on page
 */
export function trackTimeOnPage(pageName: string, seconds: number): void {
  trackEvent({
    name: 'time_on_page',
    properties: {
      page: pageName,
      seconds,
      bucket: seconds < 30 ? 'short' : seconds < 120 ? 'medium' : 'long',
    },
  });
}

/**
 * Track feature discovery
 */
export function trackFeatureDiscovery(feature: string, method: 'click' | 'scroll' | 'navigation'): void {
  trackEvent({
    name: 'feature_discovery',
    properties: {
      feature,
      discovery_method: method,
    },
  });
}

// =============================================================================
// WEB VITALS TRACKING
// =============================================================================

interface WebVitalMetric {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  id: string;
}

/**
 * Track Web Vitals
 * Only sends to GA in production; logs to console in development
 */
export function trackWebVitals(metric: WebVitalMetric): void {
  // In development, just log to console
  if (isDevelopment) {
    console.log('[Web Vitals] (dev mode):', metric.name, metric.value, metric.rating);
    return;
  }

  // In production, send to GA via trackEvent
  trackEvent({
    name: 'web_vitals',
    properties: {
      metric_name: metric.name,
      metric_value: Math.round(metric.value),
      metric_rating: metric.rating,
      metric_id: metric.id,
    },
  });
}

// =============================================================================
// SESSION & USER TRACKING
// =============================================================================

const SESSION_KEY = 'smartplay_session';
const USER_KEY = 'smartplay_user';

interface SessionData {
  id: string;
  startTime: number;
  pageViews: number;
  events: number;
}

interface UserData {
  firstVisit: number;
  totalSessions: number;
  teamsAnalyzed: string[];
}

/**
 * Get or create session
 */
export function getSession(): SessionData {
  if (!isClient) {
    return { id: '', startTime: 0, pageViews: 0, events: 0 };
  }

  const stored = sessionStorage.getItem(SESSION_KEY);
  if (stored) {
    return JSON.parse(stored);
  }

  const session: SessionData = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    startTime: Date.now(),
    pageViews: 0,
    events: 0,
  };

  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

/**
 * Update session data
 */
export function updateSession(updates: Partial<SessionData>): void {
  if (!isClient) return;

  const session = getSession();
  const updated = { ...session, ...updates };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(updated));
}

/**
 * Get or create user data
 */
export function getUserData(): UserData {
  if (!isClient) {
    return { firstVisit: 0, totalSessions: 0, teamsAnalyzed: [] };
  }

  const stored = localStorage.getItem(USER_KEY);
  if (stored) {
    return JSON.parse(stored);
  }

  const user: UserData = {
    firstVisit: Date.now(),
    totalSessions: 1,
    teamsAnalyzed: [],
  };

  localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

/**
 * Record team analyzed
 */
export function recordTeamAnalyzed(teamId: string): void {
  if (!isClient) return;

  const user = getUserData();
  if (!user.teamsAnalyzed.includes(teamId)) {
    user.teamsAnalyzed.push(teamId);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  setUserProperties({
    total_teams_analyzed: user.teamsAnalyzed.length,
    returning_user: user.totalSessions > 1,
  });
}

/**
 * Increment session count on new session
 */
export function startNewSession(): void {
  if (!isClient) return;

  const user = getUserData();
  user.totalSessions += 1;
  localStorage.setItem(USER_KEY, JSON.stringify(user));

  trackEvent({
    name: 'session_start',
    properties: {
      session_number: user.totalSessions,
      is_returning: user.totalSessions > 1,
      days_since_first_visit: Math.floor((Date.now() - user.firstVisit) / (1000 * 60 * 60 * 24)),
    },
  });
}

// =============================================================================
// CONVERSION TRACKING
// =============================================================================

/**
 * Track conversion funnel steps
 */
export function trackFunnelStep(
  funnel: 'team_analysis' | 'squad_builder' | 'transfer_workflow',
  step: number,
  stepName: string,
  completed: boolean = true
): void {
  trackEvent({
    name: 'funnel_step',
    properties: {
      funnel,
      step_number: step,
      step_name: stepName,
      completed,
    },
  });
}

/**
 * Track goal completion
 */
export function trackGoalCompletion(
  goal: 'team_analyzed' | 'squad_built' | 'transfer_planned' | 'captain_selected',
  details?: Record<string, string | number>
): void {
  trackEvent({
    name: 'goal_completion',
    properties: {
      goal,
      ...details,
    },
  });
}

// =============================================================================
// A/B TESTING SUPPORT
// =============================================================================

const EXPERIMENT_KEY = 'smartplay_experiments';

interface Experiment {
  name: string;
  variant: string;
  assignedAt: number;
}

/**
 * Get assigned experiment variant
 */
export function getExperimentVariant(experimentName: string, variants: string[]): string {
  if (!isClient) return variants[0];

  const stored = localStorage.getItem(EXPERIMENT_KEY);
  const experiments: Record<string, Experiment> = stored ? JSON.parse(stored) : {};

  if (experiments[experimentName]) {
    return experiments[experimentName].variant;
  }

  // Randomly assign variant
  const variant = variants[Math.floor(Math.random() * variants.length)];
  experiments[experimentName] = {
    name: experimentName,
    variant,
    assignedAt: Date.now(),
  };

  localStorage.setItem(EXPERIMENT_KEY, JSON.stringify(experiments));

  trackEvent({
    name: 'experiment_assigned',
    properties: {
      experiment_name: experimentName,
      variant,
    },
  });

  return variant;
}

/**
 * Track experiment exposure
 */
export function trackExperimentExposure(experimentName: string, variant: string): void {
  trackEvent({
    name: 'experiment_exposure',
    properties: {
      experiment_name: experimentName,
      variant,
    },
  });
}

// =============================================================================
// FEEDBACK TRACKING
// =============================================================================

/**
 * Track feedback submission to Google Analytics
 */
export function trackFeedbackSubmission(
  featureType: string,
  rating: number,
  teamId: number,
  gameweek: number,
  options?: {
    wouldRecommend?: number;
    hasComment?: boolean;
    followedAdvice?: boolean;
  }
): void {
  trackEvent({
    name: 'feedback_submitted',
    properties: {
      feature_type: featureType,
      rating,
      team_id: teamId,
      gameweek,
      would_recommend: options?.wouldRecommend,
      has_comment: options?.hasComment,
      followed_advice: options?.followedAdvice,
    },
  });

  // Also track as a conversion event if rating is high
  if (rating >= 4) {
    trackEvent({
      name: 'positive_feedback',
      properties: {
        feature_type: featureType,
        rating,
      },
    });
  }

  // Track NPS separately if provided
  if (options?.wouldRecommend !== undefined) {
    trackEvent({
      name: 'nps_response',
      properties: {
        score: options.wouldRecommend,
        category: options.wouldRecommend >= 9 ? 'promoter' : options.wouldRecommend >= 7 ? 'passive' : 'detractor',
        team_id: teamId,
        gameweek,
      },
    });
  }
}
