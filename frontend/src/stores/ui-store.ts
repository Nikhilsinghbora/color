import { create } from 'zustand';
import type { UIState } from '@/types';

function getInitialTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  try {
    const stored = localStorage.getItem('theme');
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage may be unavailable (SSR, privacy mode)
  }
  return 'light';
}

export const useUIStore = create<UIState>((set) => ({
  theme: getInitialTheme(),
  isChatOpen: false,
  unreadChatCount: 0,
  isOffline: false,
  sessionStartTime: null,
  sessionLimitMinutes: null,

  setTheme: (theme: 'light' | 'dark') => {
    try {
      localStorage.setItem('theme', theme);
    } catch {
      // localStorage may be unavailable
    }
    set({ theme });
  },

  toggleChat: () => {
    set((state) => {
      const opening = !state.isChatOpen;
      return {
        isChatOpen: opening,
        unreadChatCount: opening ? 0 : state.unreadChatCount,
      };
    });
  },

  incrementUnreadChat: () => {
    set((state) => ({ unreadChatCount: state.unreadChatCount + 1 }));
  },

  resetUnreadChat: () => {
    set({ unreadChatCount: 0 });
  },

  setOffline: (offline: boolean) => {
    set({ isOffline: offline });
  },

  startSession: (limitMinutes: number | null) => {
    set({ sessionStartTime: Date.now(), sessionLimitMinutes: limitMinutes });
  },
}));
