import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { PilotWorkspace } from "@/components/pilot/pilot-workspace";

export const metadata: Metadata = {
  title: "Pilot readiness",
  description:
    "Phase 10 controlled pilot governance: human risk review, assessment traceability, reviewer-verified correlation evaluation, infrastructure metadata, simulation constraints and readiness gates.",
};

export default function PilotPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <PilotWorkspace />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
