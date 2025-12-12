/**
 * Utility functions for SmartPlayFPL
 */

import { type ClassValue, clsx } from "clsx";

/**
 * Merge class names with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

/**
 * Format price (e.g., 10.5 -> £10.5m)
 */
export function formatPrice(price: number): string {
  return `£${price.toFixed(1)}m`;
}

/**
 * Format large numbers with commas
 */
export function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Format rank with # prefix
 */
export function formatRank(rank: number | null): string {
  if (rank === null) return "-";
  return `#${formatNumber(rank)}`;
}

/**
 * Format ownership percentage
 */
export function formatOwnership(ownership: number): string {
  return `${ownership.toFixed(1)}%`;
}

/**
 * Get position badge class
 */
export function getPositionClass(position: string): string {
  const classes: Record<string, string> = {
    GKP: "badge-gkp",
    DEF: "badge-def",
    MID: "badge-mid",
    FWD: "badge-fwd",
  };
  return classes[position] || "bg-gray-500 text-white";
}

/**
 * Get FDR class for fixture difficulty
 */
export function getFdrClass(fdr: number): string {
  return `fdr-${Math.min(Math.max(fdr, 1), 5)}`;
}

/**
 * Get status indicator
 */
export function getStatusInfo(status: string): { label: string; color: string } {
  const statusMap: Record<string, { label: string; color: string }> = {
    a: { label: "Available", color: "text-green-500" },
    d: { label: "Doubtful", color: "text-yellow-500" },
    i: { label: "Injured", color: "text-red-500" },
    s: { label: "Suspended", color: "text-red-500" },
    u: { label: "Unavailable", color: "text-red-500" },
    n: { label: "Not in squad", color: "text-gray-500" },
  };
  return statusMap[status] || { label: "Unknown", color: "text-gray-500" };
}

/**
 * Calculate time until deadline
 */
export function getTimeUntilDeadline(deadline: string): string {
  const now = new Date();
  const deadlineDate = new Date(deadline);
  const diff = deadlineDate.getTime() - now.getTime();
  
  if (diff <= 0) return "Deadline passed";
  
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

/**
 * Get rank percentile label
 */
export function getRankPercentile(rank: number, totalPlayers: number = 11000000): string {
  const percentile = (rank / totalPlayers) * 100;
  if (percentile <= 1) return "Top 1%";
  if (percentile <= 5) return "Top 5%";
  if (percentile <= 10) return "Top 10%";
  if (percentile <= 25) return "Top 25%";
  if (percentile <= 50) return "Top 50%";
  if (percentile <= 100) return `Top ${Math.ceil(percentile)}%`;
  return ""; // Rank higher than total players (shouldn't happen)
}

