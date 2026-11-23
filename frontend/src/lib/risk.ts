import type { RiskCategory, RiskFactor, RiskTrend } from "@/types/risk";

export const riskCategoryLabels: Record<RiskCategory, string> = {
  MINIMAL: "Minimal",
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const riskCategoryColors: Record<RiskCategory, string> = {
  MINIMAL: "#64748b",
  LOW: "#38bdf8",
  MODERATE: "#fbbf24",
  HIGH: "#fb923c",
  CRITICAL: "#fb7185",
};

export const riskCategoryOrder: RiskCategory[] = [
  "MINIMAL",
  "LOW",
  "MODERATE",
  "HIGH",
  "CRITICAL",
];

export const riskWindowLabels: Record<string, string> = {
  current: "Current window",
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
};

export function formatRiskScore(value: number): string {
  return `${value.toFixed(1)} / 100`;
}

export function formatRiskConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatRiskDistance(value: number): string {
  return value < 1000
    ? `${Math.round(value)} m`
    : `${(value / 1000).toFixed(1)} km`;
}

export function trendTone(trend: RiskTrend): string {
  if (!trend.available) return "border-white/10 bg-white/5 text-slate-400";
  if (trend.direction === "INCREASING") {
    return "border-rose-300/25 bg-rose-300/10 text-rose-200";
  }
  if (trend.direction === "DECREASING") {
    return "border-emerald-300/25 bg-emerald-300/10 text-emerald-200";
  }
  return "border-white/10 bg-white/5 text-slate-300";
}

export function factorTone(factor: RiskFactor): string {
  if (!factor.available) return "text-slate-500";
  if (factor.contribution >= 0.15) return "text-rose-200";
  if (factor.contribution >= 0.08) return "text-amber-200";
  return "text-slate-300";
}

export function formatFactorValue(factor: RiskFactor): string {
  if (!factor.available) return "Unavailable";
  if (factor.normalized === null) return "—";
  return `${Math.round(factor.normalized * 100)}%`;
}
