import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { RiskMapView } from "@/components/map/risk-map";

export const metadata: Metadata = {
  title: "Urban risk map",
  description:
    "Explore explainable H3 urban risk cells, trends, and infrastructure exposure.",
};

export default function RiskPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <RiskMapView />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
