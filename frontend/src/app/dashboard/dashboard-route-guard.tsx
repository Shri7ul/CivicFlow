"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { homePathForRole } from "@/lib/auth/routing";

/**
 * `/dashboard` is the Citizen home. Staff must never see the Citizen workspace
 * while they are being redirected, even briefly, so this guard renders nothing
 * until the authoritative profile says the visitor is a Citizen.
 */
export function DashboardRouteGuard({ children }: { children: ReactNode }) {
  const { status, profile } = useAuth();
  const router = useRouter();
  const staffHome =
    status === "authenticated" && profile && profile.role !== "CITIZEN"
      ? homePathForRole(profile.role)
      : null;

  useEffect(() => {
    if (staffHome) {
      router.replace(staffHome);
    }
  }, [router, staffHome]);

  if (status === "loading" || !profile || staffHome) {
    return null;
  }
  return <>{children}</>;
}
