'use client';

import { useEffect, useRef, useCallback } from 'react';
import { createWSClient, type WSClient, type WSStatus } from '@/lib/ws-client';
import { useAuthStore } from '@/stores/auth-store';
import { useGameStore } from '@/stores/game-store';
import { useUIStore } from '@/stores/ui-store';
import type { WSIncomingMessage, WSOutgoingMessage } from '@/types';

export function useWebSocket(roundId: string) {
  const clientRef = useRef<WSClient | null>(null);
  const statusRef = useRef<WSStatus>('disconnected');

  // Message handler - doesn't need dependencies as it always reads latest state via getState()
  const handleMessage = useCallback((msg: WSIncomingMessage) => {
    const gameStore = useGameStore.getState();
    const uiStore = useUIStore.getState();

    switch (msg.type) {
      case 'round_state':
        gameStore.setRoundState({
          roundId: msg.round_id,
          phase: msg.phase,
          timer: msg.timer,
          totalPlayers: msg.total_players,
          totalPool: msg.total_pool,
          gameMode: '',
        });
        if (msg.period_number) {
          gameStore.setPeriodNumber(msg.period_number);
        }
        // Also update the timer immediately so countdown starts
        gameStore.updateTimer(msg.timer);
        break;

      case 'timer_tick':
        gameStore.updateTimer(msg.remaining);
        break;

      case 'phase_change':
        gameStore.setPhase(msg.phase);
        break;

      case 'result':
        gameStore.setResult({
          winningColor: msg.winning_color,
          winningNumber: msg.winning_number,
          playerPayouts: msg.payouts.map((p) => ({
            betId: p.bet_id,
            amount: p.amount,
            isWinner: true,
          })),
        });
        if (gameStore.placedBets.length > 0) {
          gameStore.openWinLossDialog();
        }
        break;

      case 'new_round':
        gameStore.resetRound(msg.round_id, msg.timer);
        if (msg.period_number) {
          gameStore.setPeriodNumber(msg.period_number);
        }
        // Also update the timer immediately so countdown starts
        gameStore.updateTimer(msg.timer);
        // Update the active round ID on the game mode so the WebSocket
        // hook reconnects to the new round's channel.
        {
          const activeModeId = gameStore.activeGameModeId;
          if (activeModeId) {
            gameStore.updateActiveRoundId(activeModeId, msg.round_id);
          }
        }
        break;

      case 'bet_update': {
        const current = useGameStore.getState().currentRound;
        if (current) {
          gameStore.setRoundState({
            ...current,
            totalPlayers: msg.total_players,
            totalPool: msg.total_pool,
          });
        }
        break;
      }

      case 'chat_message':
        if (!uiStore.isChatOpen) {
          uiStore.incrementUnreadChat();
        }
        break;

      case 'error':
        // Errors are handled by the WS client itself for TOKEN_EXPIRED;
        // other errors can be logged or displayed via toast
        break;
    }
  }, []);

  useEffect(() => {
    console.log('[useWebSocket] Effect triggered with roundId:', roundId);

    if (!roundId) {
      console.log('[useWebSocket] No roundId, skipping connection');
      return;
    }

    const token = useAuthStore.getState().accessToken;
    const isAuthenticated = useAuthStore.getState().isAuthenticated;
    console.log('[useWebSocket] Auth state - isAuthenticated:', isAuthenticated, 'hasToken:', !!token);

    if (!token) {
      console.log('[useWebSocket] No token available, skipping connection');
      return;
    }

    console.log('[useWebSocket] Connecting with roundId:', roundId, 'token:', token.substring(0, 20) + '...');

    const client = createWSClient({
      onTokenExpired: async () => {
        // Return current token — the API client interceptor handles refresh
        return useAuthStore.getState().accessToken;
      },
    });

    clientRef.current = client;

    const unsubscribe = client.onMessage(handleMessage);

    // Update connection status in game store
    const statusInterval = setInterval(() => {
      const currentStatus = client.getStatus();
      if (currentStatus !== statusRef.current) {
        statusRef.current = currentStatus;
        useGameStore.getState().setConnectionStatus(currentStatus);
      }
    }, 500);

    client.connect(roundId, token);
    useGameStore.getState().setConnectionStatus('connecting');

    return () => {
      clearInterval(statusInterval);
      unsubscribe();
      client.disconnect();
      clientRef.current = null;
    };
  }, [roundId, handleMessage]); // Only depend on roundId and handleMessage (which is stable)

  const sendMessage = useCallback((message: WSOutgoingMessage) => {
    clientRef.current?.send(message);
  }, []);

  return {
    status: statusRef.current,
    sendMessage,
  };
}
