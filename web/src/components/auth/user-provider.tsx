"use client";

import { createContext, useCallback, useContext } from "react";
import { apiFetch, useApi, type User } from "@/lib/api";

type UserState = { user: User | null; loading: boolean; signOut: () => Promise<void> };

const UserContext = createContext<UserState>({ user: null, loading: true, signOut: async () => {} });

/** Loads the signed-in user once for the whole portal. A 401 redirects to /login (see apiFetch). */
export function UserProvider({ children }: { children: React.ReactNode }) {
  const { data, loading } = useApi<{ user: User }>("/api/auth/me");

  const signOut = useCallback(async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } finally {
      // Full navigation so no signed-in client state survives the logout.
      window.location.href = "/login";
    }
  }, []);

  return (
    <UserContext.Provider value={{ user: data?.user ?? null, loading, signOut }}>{children}</UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
