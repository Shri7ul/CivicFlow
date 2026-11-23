import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { DashboardView } from "./dashboard-view";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Your protected CivicFlow role foundation.",
};

export default function DashboardPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <DashboardView />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
