import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { IncidentDetailView } from "./incident-detail-view";

// The route id is runtime data; opt out of static prerendering for this page.
export const instant = false;

export const metadata: Metadata = {
  title: "Incident",
  description: "CivicFlow incident detail and response history.",
};

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <IncidentDetailView incidentId={id} />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
