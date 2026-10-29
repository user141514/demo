"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
} from "react";
import { loginUser, registerUser, getCurrentUser, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { RegisterRequest, UserResponse } from "@/lib/types";

type AuthContextType = {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInstructor: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const store = useAuthStore();

  useEffect(() => {
    store.hydrate();
    const token = localStorage.getItem("auth_token");
    if (token) {
      getCurrentUser()
        .then((user) => store.setAuth(user, token))
        .catch((err) => {
          // Only clear auth on 401 (token invalid/expired).
          // Network errors should not force logout.
          if (err instanceof ApiError && err.status === 401) {
            store.clearAuth();
          } else {
            // Token is still valid but server unreachable — keep session
            const raw = localStorage.getItem("auth_user");
            if (raw) {
              try {
                const user = JSON.parse(raw) as UserResponse;
                store.setAuth(user, token);
              } catch { store.clearAuth(); }
            } else {
              store.clearAuth();
            }
          }
        });
    } else {
      store.setInitialized(true);
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      store.setLoading(true);
      try {
        const result = await loginUser({ email, password });
        store.setAuth(result.user, result.access_token);
      } catch (error) {
        store.setLoading(false);
        throw error;
      }
    },
    [store]
  );

  const register = useCallback(
    async (payload: RegisterRequest) => {
      store.setLoading(true);
      try {
        const result = await registerUser(payload);
        store.setAuth(result.user, result.access_token);
      } catch (error) {
        store.setLoading(false);
        throw error;
      }
    },
    [store]
  );

  const logout = useCallback(() => {
    store.clearAuth();
    window.location.replace("/login");
  }, [store]);

  const value = useMemo<AuthContextType>(
    () => ({
      user: store.user,
      token: store.token,
      isAuthenticated: Boolean(store.token && store.user),
      isLoading: store.isLoading,
      isInstructor: store.user?.role === "instructor",
      login,
      register,
      logout,
    }),
    [store.user, store.token, store.isLoading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
