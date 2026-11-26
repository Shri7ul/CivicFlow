import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ApplicationStatusView } from "@/components/workforce/application-status";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const metadata: Metadata = {
  title: "Worker application status",
  description: "Track the review status of your CivicFlow worker application.",
};

export default function WorkforceStatusPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:px-8">
            <ApplicationStatusView />
          </div>
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
