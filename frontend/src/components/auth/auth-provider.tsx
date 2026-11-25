"use client";

import type { Session } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  apiFetch,
  uploadFormData,
  type ApiRequestOptions,
  type UploadProgress,
} from "@/lib/api/client";
import {
  fetchCurrentProfile,
  loadOrProvisionProfile,
} from "@/lib/api/auth";
import { profileLoadMessage } from "@/lib/api/errors";
import { getEmailRedirectTo } from "@/lib/auth/redirect";
import { authorizationHeader, requireAccessToken } from "@/lib/auth/session";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import type { AuthStatus, AuthUser, Profile } from "@/types/auth";

type AuthActionResult = {
  error?: string;
  needsEmailConfirmation?: boolean;
};

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  profile: Profile | null;
  error: string | null;
  isConfigured: boolean;
  signIn: (email: string, password: string) => Promise<AuthActionResult>;
  signUp: (
    email: string,
    password: string,
    fullName?: string,
  ) => Promise<AuthActionResult>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  apiRequest: <T>(path: string, options?: ApiRequestOptions) => Promise<T>;
  uploadRequest: <T>(
    path: string,
    formData: FormData,
    onProgress?: UploadProgress,
  ) => Promise<T>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function userFromSession(session: Session | null): AuthUser | null {
  if (!session?.user) {
    return null;
  }
  return {
    id: session.user.id,
    email: session.user.email ?? null,
  };
}

function loginError(error: unknown): string {
  return profileLoadMessage(error);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isSupabaseConfigured();
  const [status, setStatus] = useState<AuthStatus>(
    configured ? "loading" : "unconfigured",
  );
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const requestIdRef = useRef(0);

  const clearSessionState = useCallback(() => {
    sessionRef.current = null;
    setUser(null);
    setProfile(null);
    setError(null);
    setStatus(configured ? "unauthenticated" : "unconfigured");
  }, [configured]);

  const syncSession = useCallback(async (session: Session) => {
    const requestId = ++requestIdRef.current;
    sessionRef.current = session;
    setUser(userFromSession(session));
    setProfile(null);
    setError(null);
    setStatus("loading");

    try {
      const nextProfile: Profile = await loadOrProvisionProfile(
        session.access_token,
      );

      if (requestId !== requestIdRef.current) {
        return;
      }
      setProfile(nextProfile);
      setStatus("authenticated");
    } catch (loadError) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      if (loadError instanceof ApiError && loadError.status === 401) {
        clearSessionState();
        await getSupabaseBrowserClient()?.auth.signOut();
        return;
      }
      setError(loginError(loadError));
      setStatus("error");
    }
  }, [clearSessionState]);

  useEffect(() => {
    if (!configured) {
      return;
    }
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    let active = true;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (!active) {
        return;
      }
      if (event === "SIGNED_OUT" || !session) {
        clearSessionState();
        return;
      }
      if (event === "TOKEN_REFRESHED") {
        sessionRef.current = session;
        setUser(userFromSession(session));
        return;
      }
      // Supabase warns against awaiting Supabase calls inside this callback.
      void Promise.resolve().then(() => {
        if (active) {
          void syncSession(session);
        }
      });
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [clearSessionState, configured, syncSession]);

  const signIn = useCallback(
    async (email: string, password: string): Promise<AuthActionResult> => {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        return { error: "Supabase authentication is not configured." };
      }
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      return signInError ? { error: signInError.message } : {};
    },
    [],
  );

  const signUp = useCallback(
    async (
      email: string,
      password: string,
      fullName?: string,
    ): Promise<AuthActionResult> => {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        return { error: "Supabase authentication is not configured." };
      }
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: fullName?.trim() ? { full_name: fullName.trim() } : undefined,
          emailRedirectTo: getEmailRedirectTo(),
        },
      });
      if (signUpError) {
        return { error: signUpError.message };
      }
      return { needsEmailConfirmation: data.session === null };
    },
    [],
  );

  const signOut = useCallback(async () => {
    ++requestIdRef.current;
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    clearSessionState();
  }, [clearSessionState]);

  const apiRequest = useCallback(
    async <T,>(path: string, options: ApiRequestOptions = {}): Promise<T> => {
      const token = requireAccessToken(sessionRef.current?.access_token);
      const headers = new Headers(options.headers);
      Object.entries(authorizationHeader(token)).forEach(([name, value]) => {
        headers.set(name, value);
      });
      return apiFetch<T>(path, { ...options, headers });
    },
    [],
  );

  const uploadRequest = useCallback(
    async <T,>(
      path: string,
      formData: FormData,
      onProgress?: UploadProgress,
    ): Promise<T> => {
      const token = requireAccessToken(sessionRef.current?.access_token);
      return uploadFormData<T>(path, formData, token, { onProgress });
    },
    [],
  );

  const refreshProfile = useCallback(async () => {
    try {
      const token = requireAccessToken(sessionRef.current?.access_token);
      setError(null);
      const nextProfile = await fetchCurrentProfile(token);
      setProfile(nextProfile);
      setStatus("authenticated");
    } catch (refreshError) {
      if (refreshError instanceof ApiError && refreshError.status === 401) {
        await getSupabaseBrowserClient()?.auth.signOut();
        clearSessionState();
        return;
      }
      setError(loginError(refreshError));
      setStatus("error");
    }
  }, [clearSessionState]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      profile,
      error,
      isConfigured: configured,
      signIn,
      signUp,
      signOut,
      refreshProfile,
      apiRequest,
      uploadRequest,
    }),
    [
      configured,
      error,
      profile,
      refreshProfile,
      apiRequest,
      uploadRequest,
      signIn,
      signOut,
      signUp,
      status,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
