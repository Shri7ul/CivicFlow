import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { UpdatePasswordForm } from "@/components/auth/update-password-form";

export const metadata: Metadata = {
  title: "Choose a new password",
  description: "Complete a CivicFlow password reset.",
};

export default function UpdatePasswordPage() {
  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Choose a new password"
      subtitle="Use at least eight characters. You will be signed in to your dashboard after the change."
    >
      <UpdatePasswordForm />
    </AuthShell>
  );
}
