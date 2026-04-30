'use client';

import { useEffect } from 'react';
import { useGameStore } from '@/stores/game-store';
import { useWalletStore } from '@/stores/wallet-store';
import type { WSIncomingMessage } from '@/types';
import { createWSClient } from '@/lib/ws-client';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Listens for bet_debit and payout_credit transaction messages
 * from the WebSocket and updates the Wallet Store balance.
 *
 * This hook subscribes to the Game Store's result to detect payouts,
 * and relies on the bet placement flow updating balance via API response.
 * For real-time WS-driven balance updates, it watches for balance changes
 * dispatched through the game round lifecycle.
 */
export function useWalletSync(): void {
  useEffect(() => {
    // Subscribe to game store changes for result payouts
    const unsubscribe = useGameStore.subscribe((state, prevState) => {
      // When a new result arrives with payouts, refresh the wallet balance
      if (state.result && state.result !== prevState.result) {
        const hasWinnings = state.result.playerPayouts.some((p) => p.isWinner);
        if (hasWinnings) {
          // Refresh balance from server to get accurate post-payout balance
          useWalletStore.getState().fetchBalance();
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);
}
