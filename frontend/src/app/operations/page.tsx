import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { OperationsDashboard } from "@/components/operations/operations-dashboard";

export const metadata: Metadata = {
  title: "Operations",
  description:
    "Staff operational dashboard for risk, data quality, alerts, models, and plan approvals.",
};

export default function OperationsPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <OperationsDashboard />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
