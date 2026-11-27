import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { AdminWorkspace } from "@/components/workforce/admin-workspace";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

// The deep-link tab is read from searchParams at request time. Next 16 must
// render this route on demand rather than prerendering it at build time.
export const instant = false;

export const metadata: Metadata = {
  title: "Admin control plane",
  description:
    "Municipal operations control plane for worker approval, assignments, and audit.",
};

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <AdminWorkspace initialTab={tab} />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
