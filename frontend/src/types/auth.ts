export type ProfileRole = "CITIZEN" | "WORKER" | "ADMIN";

export type Profile = {
  id: string;
  full_name: string;
  phone: string | null;
  role: ProfileRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AuthUser = {
  id: string;
  email: string | null;
};

export type AuthStatus =
  | "loading"
  | "unconfigured"
  | "unauthenticated"
  | "authenticated"
  | "error";
