import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { WorkerWorkspace } from "@/components/workforce/worker-workspace";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const metadata: Metadata = {
  title: "Field worker workspace",
  description: "Assigned incidents and field workflow for authorized workers.",
};

export default function WorkerPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <WorkerWorkspace />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
