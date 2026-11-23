import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { IncidentsView } from "./incidents-view";

export const metadata: Metadata = {
  title: "Incidents",
  description: "Report and track civic incidents in CivicFlow.",
};

export default function IncidentsPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <IncidentsView />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
