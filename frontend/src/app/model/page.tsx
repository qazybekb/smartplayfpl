"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Brain,
  Database,
  PlayCircle,
  CheckCircle,
  AlertCircle,
  TrendingUp,
  BarChart3,
  Target,
  Home,
  ArrowLeft,
  RefreshCw,
  Info,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap,
} from "lucide-react";
import Footer from "@/components/Footer";
import {
  trackEvent,
  trackApiPerformance,
  trackError,
  trackFeatureDiscovery,
} from "@/lib/analytics";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface ModelStatus {
  is_trained: boolean;
  training_samples: number;
  model_type: string;
  last_trained: string | null;
  r_squared: number | null;
  mae: number | null;
  rmse: number | null;
}

interface FeatureData {
  name: string;
  coefficient: number;
  importance: number;
  direction: string;
  description: string;
}

interface Prediction {
  player_id: number;
  player_name: string;
  position: string;
  team: string;
  expected_points: number;
  confidence_low: number;
  confidence_high: number;
  form: number;
  next_opponent: string;
  fdr: number;
  is_home: boolean;
  contributions: {
    form: number;
    fdr: number;
    home: number;
    position: number;
    base: number;
  };
}

export default function ModelPage() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [features, setFeatures] = useState<FeatureData[]>([]);
  const [interpretation, setInterpretation] = useState<Record<string, string>>({});
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [trainingProgress, setTrainingProgress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showFormula, setShowFormula] = useState(false);
  const [filterPosition, setFilterPosition] = useState<string>("ALL");
  
  // Admin mode - only show training controls with ?admin=true
  const [isAdmin, setIsAdmin] = useState(false);
  
  useEffect(() => {
    // Check for admin mode in URL
    const params = new URLSearchParams(window.location.search);
    setIsAdmin(params.get("admin") === "true");
  }, []);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    const startTime = Date.now();
    try {
      const response = await fetch(`${API_BASE_URL}/api/ml/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);

        const loadTimeMs = Date.now() - startTime;
        trackApiPerformance('/api/ml/status', loadTimeMs, true);
        trackEvent({
          name: 'ml_model_page_loaded',
          properties: {
            is_trained: data.is_trained,
            model_type: data.model_type,
            r_squared: data.r_squared,
            mae: data.mae,
            training_samples: data.training_samples,
            load_time_ms: loadTimeMs,
          },
        });
        trackFeatureDiscovery('ml_prediction_model', 'navigation');

        if (data.is_trained) {
          await Promise.all([fetchFeatureImportance(), fetchPredictions()]);
        }
      } else {
        trackApiPerformance('/api/ml/status', Date.now() - startTime, false);
        trackError('ml_status_failed', 'Failed to fetch model status', 'model');
      }
    } catch (e: any) {
      console.error("Failed to fetch model status:", e);
      setError("Failed to connect to backend");
      trackError('ml_status_error', e.message || 'Failed to connect to backend', 'model');
    } finally {
      setLoading(false);
    }
  };

  const fetchFeatureImportance = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/ml/feature-importance`);
      if (response.ok) {
        const data = await response.json();
        setFeatures(data.features);
        setInterpretation(data.interpretation);
      }
    } catch (e) {
      console.error("Failed to fetch feature importance:", e);
    }
  };

  const fetchPredictions = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/ml/predictions`);
      if (response.ok) {
        const data = await response.json();
        setPredictions(data.predictions);
      }
    } catch (e) {
      console.error("Failed to fetch predictions:", e);
    }
  };

  const trainModel = async () => {
    setTraining(true);
    setTrainingProgress("Collecting data from FPL API...");
    setError(null);
    const startTime = Date.now();

    trackEvent({
      name: 'ml_model_training_started',
      properties: {
        is_retrain: status?.is_trained || false,
        max_players: 150,
      },
    });

    try {
      const response = await fetch(`${API_BASE_URL}/api/ml/train-full?max_players=150`, {
        method: "POST",
      });

      const loadTimeMs = Date.now() - startTime;

      if (!response.ok) {
        const errorData = await response.json();
        trackApiPerformance('/api/ml/train-full', loadTimeMs, false);
        trackError('ml_training_failed', errorData.detail || 'Training failed', 'model');
        throw new Error(errorData.detail || "Training failed");
      }

      setTrainingProgress("Model trained successfully!");
      trackApiPerformance('/api/ml/train-full', loadTimeMs, true);
      trackEvent({
        name: 'ml_model_training_completed',
        properties: {
          training_time_ms: loadTimeMs,
          is_retrain: status?.is_trained || false,
        },
      });

      // Refresh all data
      await fetchStatus();

    } catch (e: any) {
      setError(e.message || "Training failed");
      setTrainingProgress("");
      trackError('ml_training_error', e.message || 'Training failed', 'model');
    } finally {
      setTraining(false);
    }
  };

  const filteredPredictions = filterPosition === "ALL" 
    ? predictions 
    : predictions.filter(p => p.position === filterPosition);

  const positionColor = (pos: string) => {
    switch (pos) {
      case "GKP": return "bg-amber-100 text-amber-700";
      case "DEF": return "bg-emerald-100 text-emerald-700";
      case "MID": return "bg-blue-100 text-blue-700";
      case "FWD": return "bg-rose-100 text-rose-700";
      default: return "bg-slate-100 text-slate-700";
    }
  };

  if (loading) {
    return (
      <div className="bg-gradient-to-br from-violet-50 via-white to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <Brain className="w-16 h-16 text-violet-500 mx-auto mb-4 animate-pulse" />
          <p className="text-slate-600">Loading ML Model...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-violet-50 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
                  <Brain className="w-7 h-7" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">ML Prediction Model</h1>
                  <p className="text-sm text-white/80">Transparent, data-driven expected points</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Model Status Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                status?.is_trained ? "bg-emerald-100" : "bg-amber-100"
              }`}>
                {status?.is_trained ? (
                  <CheckCircle className="w-6 h-6 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-6 h-6 text-amber-600" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  {status?.is_trained ? "Model Ready" : "Model Not Trained"}
                </h2>
                <p className="text-sm text-slate-500">
                  {status?.model_type || "Ridge Regression"}
                </p>
              </div>
            </div>
            
            {isAdmin && (
              <button
                onClick={trainModel}
                disabled={training}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium transition-all ${
                  training
                    ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                    : "bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:shadow-lg"
                }`}
              >
                {training ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Training...
                  </>
                ) : (
                  <>
                    <PlayCircle className="w-4 h-4" />
                    {status?.is_trained ? "Retrain Model" : "Train Model"}
                  </>
                )}
              </button>
            )}
          </div>
          
          {trainingProgress && (
            <div className="mb-4 p-3 bg-violet-50 rounded-lg text-sm text-violet-700">
              {trainingProgress}
            </div>
          )}
          
          {error && (
            <div className="mb-4 p-3 bg-red-50 rounded-lg text-sm text-red-700">
              Error: {error}
            </div>
          )}
          
          {/* Model Metrics */}
          {status?.is_trained && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-violet-600">
                  {((status.r_squared || 0) * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-slate-500">R² (Variance Explained)</p>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-emerald-600">
                  ±{(status.mae || 0).toFixed(2)}
                </p>
                <p className="text-xs text-slate-500">MAE (Avg Error)</p>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-blue-600">
                  ±{(status.rmse || 0).toFixed(2)}
                </p>
                <p className="text-xs text-slate-500">RMSE (Typical Error)</p>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-slate-700">
                  {(status.training_samples || 0).toLocaleString()}
                </p>
                <p className="text-xs text-slate-500">Training Samples</p>
              </div>
            </div>
          )}
        </div>

        {/* How It Works */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <button
            onClick={() => {
              const newState = !showFormula;
              setShowFormula(newState);
              trackEvent({
                name: 'ml_formula_toggle',
                properties: {
                  action: newState ? 'expand' : 'collapse',
                },
              });
              if (newState) {
                trackFeatureDiscovery('ml_model_explanation', 'click');
              }
            }}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
                <Info className="w-5 h-5 text-indigo-600" />
              </div>
              <div className="text-left">
                <h2 className="text-lg font-bold text-slate-900">How It Works</h2>
                <p className="text-sm text-slate-500">Transparent formula explanation</p>
              </div>
            </div>
            {showFormula ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
          
          {showFormula && (
            <div className="mt-6 space-y-4">
              <div className="p-4 bg-slate-900 rounded-xl text-white font-mono text-sm overflow-x-auto">
                <p className="text-violet-400 mb-2"># Linear Regression Model</p>
                <p>expected_points = β₀ + β₁×form + β₂×FDR + β₃×is_home + β₄×minutes + ...</p>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div className="p-4 bg-emerald-50 rounded-xl">
                  <h4 className="font-bold text-emerald-800 mb-2">✅ What We Use</h4>
                  <ul className="text-sm text-emerald-700 space-y-1">
                    <li>• Recent form (last 5 GW average)</li>
                    <li>• Fixture difficulty (FDR 1-5)</li>
                    <li>• Home vs Away</li>
                    <li>• Minutes played %</li>
                    <li>• Expected goals (xG) & assists (xA)</li>
                    <li>• ICT Index</li>
                    <li>• Position (GKP/DEF/MID/FWD)</li>
                  </ul>
                </div>
                <div className="p-4 bg-violet-50 rounded-xl">
                  <h4 className="font-bold text-violet-800 mb-2">🎯 Why Ridge Regression?</h4>
                  <ul className="text-sm text-violet-700 space-y-1">
                    <li>• <strong>Interpretable:</strong> See exact coefficient weights</li>
                    <li>• <strong>Stable:</strong> L2 regularization prevents overfitting</li>
                    <li>• <strong>Fast:</strong> Trains in milliseconds</li>
                    <li>• <strong>Transparent:</strong> No black-box magic</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Feature Importance */}
        {features.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Feature Importance</h2>
                <p className="text-sm text-slate-500">What drives predictions most</p>
              </div>
            </div>
            
            <div className="space-y-3">
              {features.slice(0, 8).map((feature, idx) => (
                <div key={idx} className="flex items-center gap-4">
                  <div className="w-32 text-sm font-medium text-slate-700 truncate">
                    {feature.name}
                  </div>
                  <div className="flex-1">
                    <div className="h-6 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          feature.direction === "positive" ? "bg-emerald-500" : "bg-red-400"
                        }`}
                        style={{ width: `${Math.min(feature.importance * 20, 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-20 text-right">
                    <span className={`text-sm font-mono font-bold ${
                      feature.coefficient > 0 ? "text-emerald-600" : "text-red-500"
                    }`}>
                      {feature.coefficient > 0 ? "+" : ""}{feature.coefficient.toFixed(3)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-4 p-3 bg-slate-50 rounded-lg text-xs text-slate-600">
              <strong>How to read:</strong> Positive coefficients increase expected points. 
              For example, if Form coefficient is +0.85, each point of form adds ~0.85 expected points.
            </div>
          </div>
        )}

        {/* Predictions Table */}
        {predictions.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                    <Target className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Predictions</h2>
                    <p className="text-sm text-slate-500">Expected points for next GW</p>
                  </div>
                </div>
                
                {/* Position Filter */}
                <div className="flex items-center gap-2">
                  {["ALL", "GKP", "DEF", "MID", "FWD"].map((pos) => (
                    <button
                      key={pos}
                      onClick={() => {
                        setFilterPosition(pos);
                        trackEvent({
                          name: 'ml_predictions_filter',
                          properties: {
                            position: pos,
                            previous_position: filterPosition,
                            total_predictions: predictions.length,
                          },
                        });
                      }}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                        filterPosition === pos
                          ? "bg-violet-500 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {pos}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">#</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">Player</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">Pos</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">Team</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">vs</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600">Form</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600">FDR</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600">Expected</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600">Range</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredPredictions.slice(0, 50).map((p, idx) => (
                    <tr key={p.player_id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-sm text-slate-500">{idx + 1}</td>
                      <td className="px-4 py-3">
                        <span className="font-medium text-slate-900">{p.player_name}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${positionColor(p.position)}`}>
                          {p.position}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">{p.team}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          {p.is_home && <Home className="w-3 h-3 text-emerald-500" />}
                          <span className="text-sm text-slate-600">{p.next_opponent}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`text-sm font-mono font-medium ${
                          p.form >= 6 ? "text-emerald-600" : p.form >= 4 ? "text-amber-600" : "text-slate-500"
                        }`}>
                          {p.form.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                          p.fdr <= 2 ? "bg-emerald-100 text-emerald-700" :
                          p.fdr >= 4 ? "bg-red-100 text-red-700" :
                          "bg-slate-100 text-slate-700"
                        }`}>
                          {p.fdr}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-lg font-bold text-violet-600">
                          {p.expected_points.toFixed(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs text-slate-500">
                          {p.confidence_low.toFixed(1)} - {p.confidence_high.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {filteredPredictions.length > 50 && (
              <div className="px-6 py-3 bg-slate-50 text-center text-sm text-slate-500">
                Showing top 50 of {filteredPredictions.length} players
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!status?.is_trained && !training && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 text-center">
            <Brain className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-slate-900 mb-2">Model Loading...</h3>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              {isAdmin 
                ? "Click \"Train Model\" above to collect historical data and train the regression model."
                : "The prediction model is being initialized. Please refresh in a moment."}
            </p>
            {isAdmin && (
              <button
                onClick={trainModel}
                className="px-6 py-3 bg-gradient-to-r from-violet-500 to-purple-600 text-white font-medium rounded-xl hover:shadow-lg transition-all"
              >
                <PlayCircle className="w-5 h-5 inline mr-2" />
                Train Model Now
              </button>
            )}
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

