import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { IncidentMapView } from "@/components/map/incident-map";

export const metadata: Metadata = {
  title: "Incident map",
  description:
    "Explore CivicFlow incidents spatially with live viewport filtering.",
};

export default function IncidentMapPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <IncidentMapView />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
