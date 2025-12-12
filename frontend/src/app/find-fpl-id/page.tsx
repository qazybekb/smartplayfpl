"use client";

import Link from "next/link";
import {
  ArrowLeft,
  ExternalLink,
  MousePointer,
  Copy,
  Check,
  HelpCircle,
  Smartphone,
  Monitor,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";

export default function FindFplIdPage() {
  const [copiedStep, setCopiedStep] = useState<number | null>(null);

  const copyToClipboard = (text: string, step: number) => {
    navigator.clipboard.writeText(text);
    setCopiedStep(step);
    setTimeout(() => setCopiedStep(null), 2000);
  };

  return (
    <div className="bg-gradient-to-br from-slate-50 via-white to-emerald-50">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-100/50 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-100/50 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-3xl mx-auto px-4 py-8 sm:py-12">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-800 transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm font-medium">Back to Home</span>
        </Link>

        <div className="text-center mb-10">
          <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-emerald-200">
            <HelpCircle className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-800 mb-3">
            How to Find Your FPL Team ID
          </h1>
          <p className="text-slate-600 max-w-lg mx-auto">
            Your Team ID is a unique number that identifies your Fantasy Premier League team.
          </p>
        </div>

        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 mb-8">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center flex-shrink-0">
              <MousePointer className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <h2 className="font-bold text-emerald-800 mb-2">Quickest Method</h2>
              <p className="text-emerald-700 text-sm mb-3">
                Your Team ID is in the URL when viewing your points:
              </p>
              <div className="bg-white rounded-lg p-3 border border-emerald-200 font-mono text-sm overflow-x-auto">
                <span className="text-slate-500">https://fantasy.premierleague.com/entry/</span>
                <span className="text-emerald-600 font-bold">12520735</span>
                <span className="text-slate-500">/event/16</span>
              </div>
              <p className="text-emerald-600 text-xs mt-2">
                The number after /entry/ is your Team ID
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Monitor className="w-5 h-5 text-slate-600" />
            <h2 className="font-bold text-slate-800">Desktop / Laptop</h2>
          </div>
          <div className="p-6 space-y-6">
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm flex-shrink-0">1</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">Go to FPL Website</h3>
                <a href="https://fantasy.premierleague.com/" target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-sm font-medium text-slate-700 transition-colors">
                  fantasy.premierleague.com <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm flex-shrink-0">2</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">Click Points Tab</h3>
                <p className="text-slate-600 text-sm">Click on <strong>Points</strong> in the navigation menu.</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm flex-shrink-0">3</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">Copy Your Team ID</h3>
                <div className="bg-slate-900 rounded-lg p-4 font-mono text-sm text-slate-300 overflow-x-auto">
                  <span className="text-slate-500">https://fantasy.premierleague.com/entry/</span>
                  <span className="text-emerald-400 font-bold bg-emerald-500/20 px-1 rounded">12520735</span>
                  <span className="text-slate-500">/event/16</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
            <Smartphone className="w-5 h-5 text-slate-600" />
            <h2 className="font-bold text-slate-800">Mobile App</h2>
          </div>
          <div className="p-6 space-y-6">
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-bold text-sm flex-shrink-0">1</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">Open FPL App</h3>
                <p className="text-slate-600 text-sm">Open the Premier League app and go to Fantasy.</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-bold text-sm flex-shrink-0">2</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">View Profile</h3>
                <p className="text-slate-600 text-sm">Go to My Team then Gameweek History or View Profile.</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center font-bold text-sm flex-shrink-0">3</div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800 mb-2">Find Your ID</h3>
                <p className="text-slate-600 text-sm">Your Team ID is displayed or tap Share to get a link containing it.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-50 rounded-2xl border border-slate-200 p-6 mb-8">
          <h3 className="font-bold text-slate-800 mb-4">Example Team IDs</h3>
          <p className="text-slate-600 text-sm mb-4">Team IDs are typically 5-8 digit numbers:</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {["12520735", "1234567", "9876543", "5555555"].map((id, idx) => (
              <button key={id} onClick={() => copyToClipboard(id, idx)}
                className="flex items-center justify-between gap-2 px-3 py-2 bg-white border border-slate-200 rounded-lg hover:border-emerald-300 hover:bg-emerald-50 transition-colors group">
                <span className="font-mono text-slate-700">{id}</span>
                {copiedStep === idx ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4 text-slate-400 group-hover:text-emerald-500" />}
              </button>
            ))}
          </div>
        </div>

        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-600 hover:to-teal-700 transition-all shadow-lg shadow-emerald-500/25">
            Analyse My Team <ChevronRight className="w-5 h-5" />
          </Link>
        </div>
      </div>
    </div>
  );
}
