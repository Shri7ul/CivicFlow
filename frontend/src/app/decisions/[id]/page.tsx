import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { DecisionWorkspace } from "@/components/decisions/decision-workspace";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const instant = false;

export const metadata: Metadata = {
  title: "Decision workspace",
  description:
    "Plan response actions, run bounded simulations, and compare strategies.",
};

export default async function DecisionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <DecisionWorkspace scenarioId={id} />
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
