import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { AuthShell } from "@/components/auth/auth-shell";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a Citizen account for CivicFlow.",
};

export default function SignupPage() {
  return (
    <AuthShell
      eyebrow="Join the response"
      title="Create your CivicFlow account"
      subtitle="New accounts start with the Citizen role. Administrators can grant worker or admin access later."
    >
      <AuthForm mode="signup" />
    </AuthShell>
  );
}
