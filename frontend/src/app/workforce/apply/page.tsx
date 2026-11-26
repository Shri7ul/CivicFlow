import type { Metadata } from "next";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ApplicationForm } from "@/components/workforce/application-form";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

export const metadata: Metadata = {
  title: "Apply as a worker",
  description: "Apply for an authorized field worker role.",
};

export default function ApplyPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-slate-950">
      <SiteHeader />
      <div className="flex-1">
        <AuthGuard>
          <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:px-8">
            <ApplicationForm />
          </div>
        </AuthGuard>
      </div>
      <SiteFooter />
    </div>
  );
}
