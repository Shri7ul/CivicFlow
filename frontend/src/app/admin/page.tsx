import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { AdminWorkspace } from "@/components/workforce/admin-workspace";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const metadata: Metadata = {
  title: "Admin control plane",
  description:
    "Municipal operations control plane for worker approval, assignments, and audit.",
};

export default function AdminPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <AdminWorkspace />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
