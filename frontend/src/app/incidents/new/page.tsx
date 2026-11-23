import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ReportIncidentForm } from "./report-incident-form";

export const metadata: Metadata = {
  title: "Report an incident",
  description: "Submit a civic incident to CivicFlow.",
};

export default function NewIncidentPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <ReportIncidentForm />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
