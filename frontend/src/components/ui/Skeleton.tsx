"use client";

import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-slate-200/70",
        className
      )}
    />
  );
}

// Pre-built skeleton components for common patterns
export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn("bg-white rounded-2xl border border-slate-200 p-6", className)}>
      <div className="flex items-center gap-4 mb-4">
        <Skeleton className="w-12 h-12 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    </div>
  );
}

export function SkeletonPitch({ className }: SkeletonProps) {
  return (
    <div className={cn("bg-white rounded-2xl border border-slate-200 overflow-hidden", className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-5 w-24" />
        </div>
        <div className="flex gap-4 mt-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>
      {/* Pitch area */}
      <div className="p-4">
        <div className="bg-gradient-to-b from-emerald-100 to-emerald-200/50 rounded-xl p-6 min-h-[400px]">
          {/* GK Row */}
          <div className="flex justify-center mb-6">
            <Skeleton className="w-14 h-20 rounded-lg" />
          </div>
          {/* DEF Row */}
          <div className="flex justify-center gap-4 mb-6">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="w-14 h-20 rounded-lg" />
            ))}
          </div>
          {/* MID Row */}
          <div className="flex justify-center gap-4 mb-6">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="w-14 h-20 rounded-lg" />
            ))}
          </div>
          {/* FWD Row */}
          <div className="flex justify-center gap-4">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="w-14 h-20 rounded-lg" />
            ))}
          </div>
        </div>
        {/* Bench */}
        <div className="flex justify-center gap-3 mt-4 pt-4 border-t border-dashed border-slate-200">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="w-14 h-16 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center gap-4">
          <Skeleton className="w-10 h-10 rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
      </div>
      {/* Table Header */}
      <div className="px-6 py-3 bg-slate-50 border-b border-slate-100 flex gap-4">
        <Skeleton className="h-4 w-8" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-16 ml-auto" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-16" />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-6 py-4 border-b border-slate-50 last:border-0 flex gap-4 items-center">
          <Skeleton className="h-4 w-6" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-6 w-12 rounded ml-auto" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonManagerHeader() {
  return (
    <div className="bg-gradient-to-r from-emerald-600 to-green-600 rounded-2xl p-6">
      <div className="flex items-center gap-4">
        <Skeleton className="w-16 h-16 rounded-2xl bg-white/20" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-48 bg-white/20" />
          <Skeleton className="h-4 w-32 bg-white/20" />
        </div>
      </div>
      <div className="flex gap-4 mt-4">
        <Skeleton className="h-16 w-24 rounded-xl bg-white/20" />
        <Skeleton className="h-16 w-24 rounded-xl bg-white/20" />
        <Skeleton className="h-16 w-24 rounded-xl bg-white/20" />
      </div>
    </div>
  );
}

export function SkeletonWorkflowTabs() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-2">
      <div className="flex gap-2 overflow-x-auto">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Skeleton key={i} className="h-10 w-24 rounded-lg flex-shrink-0" />
        ))}
      </div>
    </div>
  );
}

export function SkeletonInsightCard() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-start gap-3">
        <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    </div>
  );
}

// Full page loading skeleton for team dashboard
export function SkeletonTeamDashboard() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Nav */}
        <div className="flex items-center justify-between mb-6">
          <Skeleton className="h-8 w-20" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-24 rounded-full" />
            <Skeleton className="h-8 w-24 rounded-full" />
          </div>
        </div>

        {/* Manager Header */}
        <SkeletonManagerHeader />

        {/* Section Divider */}
        <div className="relative mt-8 mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center">
            <Skeleton className="h-8 w-48 rounded-full" />
          </div>
        </div>

        {/* Workflow Tabs */}
        <SkeletonWorkflowTabs />

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-5 gap-6 mt-6">
          {/* Pitch */}
          <div className="lg:col-span-3">
            <SkeletonPitch />
          </div>
          {/* Step Content */}
          <div className="lg:col-span-2 space-y-4">
            <SkeletonCard />
            <SkeletonInsightCard />
            <SkeletonInsightCard />
          </div>
        </div>

        {/* Analytics Section */}
        <div className="mt-12">
          <div className="relative mb-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center">
              <Skeleton className="h-8 w-40 rounded-full" />
            </div>
          </div>
          <SkeletonCard />
        </div>
      </div>
    </div>
  );
}
