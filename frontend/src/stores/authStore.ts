import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getCurrentUser, loginUser, registerUser } from "@/api/auth";
import type { User, UserCreate, UserLogin } from "@/types/auth";

interface AuthState {
  token: string | null;
  user: User | null;
  isHydrated: boolean;
  setHydrated: () => void;
  setSession: (token: string, user: User) => void;
  clearSession: () => void;
  login: (payload: UserLogin) => Promise<void>;
  register: (payload: UserCreate) => Promise<void>;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isHydrated: false,
      setHydrated: () => set({ isHydrated: true }),
      setSession: (token, user) => set({ token, user }),
      clearSession: () => set({ token: null, user: null }),
      login: async (payload) => {
        const tokenResponse = await loginUser(payload);
        const user = await getCurrentUser(tokenResponse.access_token);
        set({ token: tokenResponse.access_token, user });
      },
      register: async (payload) => {
        await registerUser(payload);
        await get().login({ email: payload.email, password: payload.password });
      },
      loadUser: async () => {
        const { token } = get();
        if (!token) {
          return;
        }

        try {
          const user = await getCurrentUser(token);
          set({ user });
        } catch {
          set({ token: null, user: null });
        }
      },
    }),
    {
      name: "codethera-auth",
      partialize: (state) => ({ token: state.token }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    },
  ),
);
