import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ValidationDashboard } from "@/components/validation/validation-dashboard";

export const metadata: Metadata = {
  title: "Validation",
  description:
    "Persisted real-world validation experiments, baseline comparisons, dataset provenance, and explicit limitations.",
};

export default function ValidationPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <ValidationDashboard />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
