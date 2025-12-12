"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  trackEvent,
  trackSquadBuilder,
  trackGoalCompletion,
  trackFunnelStep,
  trackApiPerformance,
  trackError,
  trackFeatureDiscovery,
} from "@/lib/analytics";
import {
  ArrowLeft,
  Check,
  X,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Loader2,
  Wrench,
  Sparkles,
  Shield,
  Code,
  Play,
  Plus,
  Minus,
  Database,
  Zap,
  CheckCircle,
  Copy,
  RefreshCw,
} from "lucide-react";
import Footer from "@/components/Footer";

// Types
interface TagInfo {
  name: string;
  description: string;
  count: number;
  icon: string;
  color: string;
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
}

interface BuiltSquad {
  players: Player[];
  formation: string;
  total_cost: number;
  in_the_bank: number;
  validation: any;
  strategy_id: string;
  strategy_name: string;
  strategy_analysis: any;
  sparql_queries: string[];
}

// Position colors
const POSITION_COLORS: Record<string, { bg: string; text: string }> = {
  GKP: { bg: "bg-amber-100", text: "text-amber-700" },
  DEF: { bg: "bg-emerald-100", text: "text-emerald-700" },
  MID: { bg: "bg-blue-100", text: "text-blue-700" },
  FWD: { bg: "bg-rose-100", text: "text-rose-700" },
};

export default function CustomBuildPage() {
  const router = useRouter();
  
  const [includeOptions, setIncludeOptions] = useState<TagInfo[]>([]);
  const [excludeOptions, setExcludeOptions] = useState<TagInfo[]>([]);
  const [selectedInclude, setSelectedInclude] = useState<string[]>([]);
  const [selectedExclude, setSelectedExclude] = useState<string[]>(["InjuryConcern", "SellUrgent"]);
  const [sparqlPreview, setSparqlPreview] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [squad, setSquad] = useState<BuiltSquad | null>(null);
  const [copiedSparql, setCopiedSparql] = useState(false);

  useEffect(() => {
    fetchTags();
  }, []);

  useEffect(() => {
    previewSparql();
  }, [selectedInclude, selectedExclude]);

  const fetchTags = async () => {
    const startTime = Date.now();
    try {
      const res = await fetch("/api/build/tags");
      if (res.ok) {
        const data = await res.json();
        setIncludeOptions(data.include_options || []);
        setExcludeOptions(data.exclude_options || []);

        const loadTimeMs = Date.now() - startTime;
        trackApiPerformance('/api/build/tags', loadTimeMs, true);
        trackEvent({
          name: 'custom_builder_loaded',
          properties: {
            include_tags_count: data.include_options?.length || 0,
            exclude_tags_count: data.exclude_options?.length || 0,
            load_time_ms: loadTimeMs,
          },
        });
        trackSquadBuilder('start', { page: 'custom_builder' });
        trackFunnelStep('squad_builder', 2, 'custom_builder_opened', true);
        trackFeatureDiscovery('custom_squad_builder', 'navigation');
      } else {
        trackError('custom_builder_tags_failed', 'Failed to fetch tags', 'custom');
        trackApiPerformance('/api/build/tags', Date.now() - startTime, false);
      }
    } catch (err: any) {
      console.error("Error fetching tags:", err);
      trackError('custom_builder_tags_error', err.message || 'Unknown error', 'custom');
    } finally {
      setLoading(false);
    }
  };

  const previewSparql = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedInclude.length > 0) {
        params.set("include_tags", selectedInclude.join(","));
      }
      if (selectedExclude.length > 0) {
        params.set("exclude_tags", selectedExclude.join(","));
      }
      
      const res = await fetch(`/api/build/preview-sparql?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setSparqlPreview(data.sparql);
      }
    } catch (err) {
      console.error("Error previewing SPARQL:", err);
    }
  };

  const toggleInclude = (tag: string) => {
    const isRemoving = selectedInclude.includes(tag);
    setSelectedInclude(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
    trackEvent({
      name: 'custom_builder_tag_toggle',
      properties: {
        tag_name: tag,
        tag_type: 'include',
        action: isRemoving ? 'remove' : 'add',
        total_include_tags: isRemoving ? selectedInclude.length - 1 : selectedInclude.length + 1,
      },
    });
  };

  const toggleExclude = (tag: string) => {
    const isRemoving = selectedExclude.includes(tag);
    setSelectedExclude(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
    trackEvent({
      name: 'custom_builder_tag_toggle',
      properties: {
        tag_name: tag,
        tag_type: 'exclude',
        action: isRemoving ? 'remove' : 'add',
        total_exclude_tags: isRemoving ? selectedExclude.length - 1 : selectedExclude.length + 1,
      },
    });
  };

  const buildSquad = async () => {
    setBuilding(true);
    const startTime = Date.now();
    trackSquadBuilder('generate', {
      strategy_id: 'custom',
      include_tags_count: selectedInclude.length,
      exclude_tags_count: selectedExclude.length,
    });

    try {
      const res = await fetch("/api/build/custom/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          include_tags: selectedInclude,
          exclude_tags: selectedExclude,
        }),
      });

      const loadTimeMs = Date.now() - startTime;

      if (res.ok) {
        const data = await res.json();
        setSquad(data);
        trackApiPerformance('/api/build/custom/build', loadTimeMs, true);
        trackSquadBuilder('complete', {
          strategy_id: 'custom',
          strategy_name: 'Custom Build',
          formation: data.formation,
          total_cost: data.total_cost,
          in_the_bank: data.in_the_bank,
          validation_passed: data.validation?.passed,
          include_tags_count: selectedInclude.length,
          exclude_tags_count: selectedExclude.length,
          load_time_ms: loadTimeMs,
        });
        trackGoalCompletion('squad_built', {
          strategy_id: 'custom',
          formation: data.formation,
          total_cost: data.total_cost,
        });
        trackFunnelStep('squad_builder', 3, 'custom_squad_generated', true);
      } else {
        const errorText = await res.text();
        trackError('custom_squad_build_failed', errorText, 'custom');
        trackApiPerformance('/api/build/custom/build', loadTimeMs, false);
      }
    } catch (err: any) {
      console.error("Error building squad:", err);
      trackError('custom_squad_build_error', err.message || 'Unknown error', 'custom');
    } finally {
      setBuilding(false);
    }
  };

  const copySparql = () => {
    navigator.clipboard.writeText(sparqlPreview);
    setCopiedSparql(true);
    setTimeout(() => setCopiedSparql(false), 2000);
    trackEvent({
      name: 'custom_builder_sparql_copy',
      properties: {
        include_tags_count: selectedInclude.length,
        exclude_tags_count: selectedExclude.length,
        sparql_length: sparqlPreview.length,
      },
    });
    trackFeatureDiscovery('sparql_query_copy', 'click');
  };

  const resetSelection = () => {
    trackEvent({
      name: 'custom_builder_reset',
      properties: {
        previous_include_tags_count: selectedInclude.length,
        previous_exclude_tags_count: selectedExclude.length,
        had_squad: !!squad,
      },
    });
    setSelectedInclude([]);
    setSelectedExclude(["InjuryConcern", "SellUrgent"]);
    setSquad(null);
  };

  if (loading) {
    return (
      <div className="bg-gradient-to-br from-slate-100 via-white to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center mx-auto mb-4 animate-pulse">
            <Wrench className="w-10 h-10 text-white" />
          </div>
          <p className="text-slate-600 font-medium">Loading Smart Tags...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-slate-100 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-slate-700 via-slate-800 to-slate-900 text-white">
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
                  <Wrench className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="text-xl font-bold">Build Your Own Strategy</h1>
                  <p className="text-sm text-white/80">Custom KG-Powered Squad Builder</p>
                </div>
              </div>
            </div>
            
            <button
              onClick={resetSelection}
              className="flex items-center gap-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg font-medium transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Reset
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left - Tag Selection */}
          <div className="space-y-6">
            {/* Include Tags */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 bg-emerald-50 border-b border-emerald-100">
                <div className="flex items-center gap-2">
                  <Plus className="w-5 h-5 text-emerald-600" />
                  <h2 className="font-bold text-emerald-900">Include Players With</h2>
                </div>
                <p className="text-xs text-emerald-700 mt-1">
                  Players must have at least one of these tags
                </p>
              </div>
              
              <div className="p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {includeOptions.map((tag) => {
                    const isSelected = selectedInclude.includes(tag.name);
                    return (
                      <button
                        key={tag.name}
                        onClick={() => toggleInclude(tag.name)}
                        className={`p-3 rounded-xl border-2 text-left transition-all ${
                          isSelected
                            ? "border-emerald-400 bg-emerald-50"
                            : "border-slate-200 hover:border-slate-300 bg-white"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{tag.icon}</span>
                            <span className="font-semibold text-slate-900 text-sm">{tag.name}</span>
                          </div>
                          {isSelected && <Check className="w-4 h-4 text-emerald-600" />}
                        </div>
                        <p className="text-[10px] text-slate-500 leading-relaxed">{tag.description}</p>
                        <p className="text-[10px] text-slate-400 mt-1">{tag.count} players</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Exclude Tags */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 bg-rose-50 border-b border-rose-100">
                <div className="flex items-center gap-2">
                  <Minus className="w-5 h-5 text-rose-600" />
                  <h2 className="font-bold text-rose-900">Exclude Players With</h2>
                </div>
                <p className="text-xs text-rose-700 mt-1">
                  Players with any of these tags will be filtered out
                </p>
              </div>
              
              <div className="p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {excludeOptions.map((tag) => {
                    const isSelected = selectedExclude.includes(tag.name);
                    return (
                      <button
                        key={tag.name}
                        onClick={() => toggleExclude(tag.name)}
                        className={`p-3 rounded-xl border-2 text-left transition-all ${
                          isSelected
                            ? "border-rose-400 bg-rose-50"
                            : "border-slate-200 hover:border-slate-300 bg-white"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{tag.icon}</span>
                            <span className="font-semibold text-slate-900 text-sm">{tag.name}</span>
                          </div>
                          {isSelected && <X className="w-4 h-4 text-rose-600" />}
                        </div>
                        <p className="text-[10px] text-slate-500 leading-relaxed">{tag.description}</p>
                        <p className="text-[10px] text-slate-400 mt-1">{tag.count} players</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Right - SPARQL Preview & Results */}
          <div className="space-y-6">
            {/* SPARQL Preview */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-5 py-4 bg-violet-50 border-b border-violet-100">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Code className="w-5 h-5 text-violet-600" />
                    <h2 className="font-bold text-violet-900">Generated SPARQL Query</h2>
                  </div>
                  <button
                    onClick={copySparql}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-violet-700 hover:bg-violet-100 rounded transition-colors"
                  >
                    {copiedSparql ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copiedSparql ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
              
              <div className="p-4">
                <pre className="bg-slate-900 text-slate-300 p-4 rounded-lg text-xs overflow-x-auto max-h-64">
                  {sparqlPreview || "SELECT ?player WHERE { ... }"}
                </pre>
              </div>
            </div>

            {/* Build Button */}
            <button
              onClick={buildSquad}
              disabled={building}
              className="w-full py-4 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-bold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {building ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Building Squad...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Build Squad with Custom Strategy
                </>
              )}
            </button>

            {/* Results */}
            {squad && (
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="px-5 py-4 bg-gradient-to-r from-indigo-500 to-violet-600 text-white">
                  <div className="flex items-center justify-between">
                    <h2 className="font-bold flex items-center gap-2">
                      <CheckCircle className="w-5 h-5" />
                      Your Custom Squad
                    </h2>
                    <span className="text-sm bg-white/20 px-3 py-1 rounded-full">
                      {squad.formation}
                    </span>
                  </div>
                </div>
                
                <div className="p-5">
                  {/* Quick Stats */}
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <p className="text-lg font-bold text-slate-900">£{squad.total_cost}m</p>
                      <p className="text-[10px] text-slate-500">Total Cost</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <p className={`text-lg font-bold ${squad.in_the_bank >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        £{squad.in_the_bank}m
                      </p>
                      <p className="text-[10px] text-slate-500">In Bank</p>
                    </div>
                    <div className={`rounded-lg p-3 text-center ${squad.validation.passed ? "bg-emerald-50" : "bg-amber-50"}`}>
                      <p className={`text-lg font-bold ${squad.validation.passed ? "text-emerald-600" : "text-amber-600"}`}>
                        {squad.validation.passed ? "✓ Passed" : squad.validation.error_count + " Errors"}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        SHACL Validation
                      </p>
                    </div>
                  </div>

                  {/* Starting XI */}
                  <div className="mb-4">
                    <p className="text-xs font-bold text-slate-700 mb-2">Starting XI</p>
                    <div className="grid grid-cols-2 gap-2">
                      {squad.players.filter(p => p.is_starter).map((player) => (
                        <div 
                          key={player.id}
                          className="flex items-center gap-2 p-2 rounded-lg bg-slate-50"
                        >
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${POSITION_COLORS[player.position].bg} ${POSITION_COLORS[player.position].text}`}>
                            {player.position}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-slate-900 truncate">
                              {player.web_name}
                              {player.is_captain && " (C)"}
                              {player.is_vice_captain && " (V)"}
                            </p>
                            <p className="text-[10px] text-slate-500">{player.team_short} · £{player.price}m</p>
                          </div>
                          <span className={`text-xs font-bold ${
                            player.form >= 6 ? "text-emerald-600" : 
                            player.form >= 4 ? "text-amber-600" : "text-slate-500"
                          }`}>
                            {player.form.toFixed(1)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Bench */}
                  <div>
                    <p className="text-xs font-bold text-slate-700 mb-2">Bench</p>
                    <div className="flex gap-2">
                      {squad.players.filter(p => !p.is_starter).map((player) => (
                        <div 
                          key={player.id}
                          className="flex-1 p-2 rounded-lg bg-slate-50 text-center"
                        >
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${POSITION_COLORS[player.position].bg} ${POSITION_COLORS[player.position].text}`}>
                            {player.position}
                          </span>
                          <p className="text-[10px] font-semibold text-slate-900 mt-1 truncate">{player.web_name}</p>
                          <p className="text-[9px] text-slate-500">£{player.price}m</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Help Text */}
            <div className="bg-indigo-50 rounded-xl p-4 border border-indigo-100">
              <div className="flex items-start gap-3">
                <Info className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-indigo-900">How it works</p>
                  <ul className="text-xs text-indigo-700 mt-1 space-y-1">
                    <li>• Select tags to <strong>include</strong> (players must match at least one)</li>
                    <li>• Select tags to <strong>exclude</strong> (players with these are filtered out)</li>
                    <li>• Watch the SPARQL query update in real-time</li>
                    <li>• Click "Build Squad" to generate your custom 15-player squad</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

