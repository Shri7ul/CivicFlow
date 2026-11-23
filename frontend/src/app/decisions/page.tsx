import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { DecisionDashboard } from "@/components/decisions/decision-dashboard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const metadata: Metadata = {
  title: "Decision scenarios",
  description:
    "Staff-only scenario planning, response constraints, and strategy comparison.",
};

export default function DecisionsPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <DecisionDashboard />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
