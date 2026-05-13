"use client";

import { create } from "zustand";
import { api, ApiHttpError } from "./api";
import { tokenStorage } from "./token-storage";
import type { UserDTO } from "./api-types";

interface AuthState {
  user: UserDTO | null;
  initialized: boolean;
  loading: boolean;

  // actions
  bootstrap: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  setUser: (u: UserDTO | null) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  initialized: false,
  loading: false,

  bootstrap: async () => {
    if (get().initialized) return;
    set({ loading: true });
    try {
      if (!tokenStorage.access) {
        set({ user: null, initialized: true, loading: false });
        return;
      }
      const me = await api.auth.me();
      set({ user: me, initialized: true, loading: false });
    } catch {
      tokenStorage.clear();
      set({ user: null, initialized: true, loading: false });
    }
  },

  login: async (email, password) => {
    set({ loading: true });
    try {
      const pair = await api.auth.login(email, password);
      tokenStorage.set(pair);
      const me = await api.auth.me();
      set({ user: me, initialized: true, loading: false });
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  logout: async () => {
    try {
      await api.auth.logout();
    } catch {
      /* ignore */
    } finally {
      tokenStorage.clear();
      set({ user: null });
    }
  },

  refreshMe: async () => {
    try {
      const me = await api.auth.me();
      set({ user: me });
    } catch (err) {
      if (err instanceof ApiHttpError && err.status === 401) {
        tokenStorage.clear();
        set({ user: null });
      }
    }
  },

  setUser: (u) => set({ user: u }),
}));
