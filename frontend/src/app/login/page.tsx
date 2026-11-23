import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { AuthShell } from "@/components/auth/auth-shell";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to CivicFlow to access your role-aware dashboard.",
};

export default function LoginPage() {
  return (
    <AuthShell
      eyebrow="Secure access"
      title="Sign in to CivicFlow"
      subtitle="Use your Supabase account to continue to your role-aware civic response workspace."
    >
      <AuthForm mode="login" />
    </AuthShell>
  );
}
