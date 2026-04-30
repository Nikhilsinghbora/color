import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useUIStore } from './ui-store';

function resetStore() {
  useUIStore.setState({
    theme: 'light',
    isChatOpen: false,
    unreadChatCount: 0,
    isOffline: false,
    sessionStartTime: null,
    sessionLimitMinutes: null,
  });
}

describe('UI Store', () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
  });

  it('starts with default state', () => {
    const state = useUIStore.getState();
    expect(state.theme).toBe('light');
    expect(state.isChatOpen).toBe(false);
    expect(state.unreadChatCount).toBe(0);
    expect(state.isOffline).toBe(false);
    expect(state.sessionStartTime).toBeNull();
    expect(state.sessionLimitMinutes).toBeNull();
  });

  describe('setTheme', () => {
    it('sets theme to dark and persists to localStorage', () => {
      useUIStore.getState().setTheme('dark');
      expect(useUIStore.getState().theme).toBe('dark');
      expect(localStorage.getItem('theme')).toBe('dark');
    });

    it('sets theme to light and persists to localStorage', () => {
      useUIStore.getState().setTheme('dark');
      useUIStore.getState().setTheme('light');
      expect(useUIStore.getState().theme).toBe('light');
      expect(localStorage.getItem('theme')).toBe('light');
    });

    it('handles localStorage errors gracefully', () => {
      const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('QuotaExceededError');
      });
      // Should not throw
      useUIStore.getState().setTheme('dark');
      expect(useUIStore.getState().theme).toBe('dark');
      spy.mockRestore();
    });
  });

  describe('toggleChat', () => {
    it('opens chat when closed', () => {
      useUIStore.getState().toggleChat();
      expect(useUIStore.getState().isChatOpen).toBe(true);
    });

    it('closes chat when open', () => {
      useUIStore.getState().toggleChat(); // open
      useUIStore.getState().toggleChat(); // close
      expect(useUIStore.getState().isChatOpen).toBe(false);
    });

    it('resets unread count when opening chat', () => {
      useUIStore.getState().incrementUnreadChat();
      useUIStore.getState().incrementUnreadChat();
      expect(useUIStore.getState().unreadChatCount).toBe(2);

      useUIStore.getState().toggleChat(); // open
      expect(useUIStore.getState().unreadChatCount).toBe(0);
    });

    it('preserves unread count when closing chat', () => {
      useUIStore.getState().toggleChat(); // open
      // Simulate messages arriving while open, then close
      useUIStore.setState({ unreadChatCount: 3 });
      useUIStore.getState().toggleChat(); // close
      expect(useUIStore.getState().unreadChatCount).toBe(3);
    });
  });

  describe('incrementUnreadChat', () => {
    it('increments unread count by 1', () => {
      useUIStore.getState().incrementUnreadChat();
      expect(useUIStore.getState().unreadChatCount).toBe(1);
      useUIStore.getState().incrementUnreadChat();
      expect(useUIStore.getState().unreadChatCount).toBe(2);
    });
  });

  describe('resetUnreadChat', () => {
    it('resets unread count to 0', () => {
      useUIStore.getState().incrementUnreadChat();
      useUIStore.getState().incrementUnreadChat();
      useUIStore.getState().resetUnreadChat();
      expect(useUIStore.getState().unreadChatCount).toBe(0);
    });
  });

  describe('setOffline', () => {
    it('sets offline to true', () => {
      useUIStore.getState().setOffline(true);
      expect(useUIStore.getState().isOffline).toBe(true);
    });

    it('sets offline to false', () => {
      useUIStore.getState().setOffline(true);
      useUIStore.getState().setOffline(false);
      expect(useUIStore.getState().isOffline).toBe(false);
    });
  });

  describe('startSession', () => {
    it('sets sessionStartTime to current time and sessionLimitMinutes', () => {
      const before = Date.now();
      useUIStore.getState().startSession(60);
      const after = Date.now();

      const state = useUIStore.getState();
      expect(state.sessionStartTime).toBeGreaterThanOrEqual(before);
      expect(state.sessionStartTime).toBeLessThanOrEqual(after);
      expect(state.sessionLimitMinutes).toBe(60);
    });

    it('accepts null for no session limit', () => {
      useUIStore.getState().startSession(null);
      const state = useUIStore.getState();
      expect(state.sessionStartTime).not.toBeNull();
      expect(state.sessionLimitMinutes).toBeNull();
    });

    it('overwrites previous session on restart', () => {
      useUIStore.getState().startSession(30);
      const firstStart = useUIStore.getState().sessionStartTime;

      // Small delay to ensure different timestamp
      useUIStore.getState().startSession(120);
      const state = useUIStore.getState();
      expect(state.sessionStartTime).toBeGreaterThanOrEqual(firstStart!);
      expect(state.sessionLimitMinutes).toBe(120);
    });
  });
});
