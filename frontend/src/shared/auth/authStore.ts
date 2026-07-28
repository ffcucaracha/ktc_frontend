import { create } from "zustand";

interface AuthState {
  accessToken: string | null;
  setAccessToken: (accessToken: string) => void;
  clearAccessToken: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  setAccessToken: (accessToken) => {
    set({ accessToken });
  },
  clearAccessToken: () => {
    set({ accessToken: null });
  },
}));

export function getAccessToken(): string | null {
  return useAuthStore.getState().accessToken;
}

export function setAccessToken(accessToken: string): void {
  useAuthStore.getState().setAccessToken(accessToken);
}

export function clearAccessToken(): void {
  useAuthStore.getState().clearAccessToken();
}
