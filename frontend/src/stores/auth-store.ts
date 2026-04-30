import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { AuthState, PlayerProfile } from '@/types';
import { registerAuthStore } from '@/lib/api-client';

/**
 * Decode the payload section of a JWT access token.
 * Uses base64 decoding (atob) — no external library needed.
 */
function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid JWT: expected 3 parts');
  }
  // Handle base64url encoding: replace URL-safe chars and pad
  let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4;
  if (pad) {
    base64 += '='.repeat(4 - pad);
  }
  const json = atob(base64);
  return JSON.parse(json);
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      player: null,
      isAuthenticated: false,
      isAdmin: false,

      setTokens: (access: string, refresh: string) => {
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true });
        // Decode player info from the access token
        useAuthStore.getState().decodeAndSetPlayer(access);
      },

      clearTokens: () => {
        set({
          accessToken: null,
          refreshToken: null,
          player: null,
          isAuthenticated: false,
          isAdmin: false,
        });
      },

      setPlayer: (player: PlayerProfile) => {
        set({ player, isAdmin: player.isAdmin });
      },

      decodeAndSetPlayer: (accessToken: string) => {
        try {
          const payload = decodeJwtPayload(accessToken);
          const player: PlayerProfile = {
            id: String(payload.sub ?? payload.id ?? ''),
            email: String(payload.email ?? ''),
            username: String(payload.username ?? ''),
            isAdmin: Boolean(payload.is_admin ?? payload.isAdmin ?? false),
          };
          set({ player, isAdmin: player.isAdmin });
        } catch {
          // If decoding fails, don't crash — just leave player as null
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      // Only persist tokens and auth state, player info is derived
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
      // Restore player info from token after rehydration
      onRehydrateStorage: () => (state) => {
        if (state?.accessToken) {
          state.decodeAndSetPlayer(state.accessToken);
        }
      },
    }
  )
);

// Register the auth store accessor with the API client so it can
// read tokens and trigger refresh without a circular import.
registerAuthStore(() => useAuthStore.getState());
