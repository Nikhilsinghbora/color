import { create } from 'zustand';
import type {
  RoundPhase,
  ColorOption,
  PlacedBet,
  RoundResult,
  RoundState,
} from '@/types';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface GameStoreState {
  currentRound: RoundState | null;
  phase: RoundPhase;
  timerRemaining: number;
  colorOptions: ColorOption[];
  selectedBets: Record<string, string>; // color -> amount string
  placedBets: PlacedBet[];
  result: RoundResult | null;
  connectionStatus: ConnectionStatus;

  setRoundState: (state: RoundState) => void;
  setPhase: (phase: RoundPhase) => void;
  updateTimer: (remaining: number) => void;
  setBetSelection: (color: string, amount: string) => void;
  removeBetSelection: (color: string) => void;
  addPlacedBet: (bet: PlacedBet) => void;
  setResult: (result: RoundResult) => void;
  resetRound: (roundId: string, timer: number) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
}

export const useGameStore = create<GameStoreState>((set) => ({
  currentRound: null,
  phase: 'betting',
  timerRemaining: 0,
  colorOptions: [],
  selectedBets: {},
  placedBets: [],
  result: null,
  connectionStatus: 'disconnected',

  setRoundState: (roundState: RoundState) => {
    // Extract color options from the round's gameMode info isn't available here,
    // so we set the core round fields. Color options are typically set separately
    // or derived from the game mode config.
    set({
      currentRound: roundState,
      phase: roundState.phase,
      timerRemaining: roundState.timer,
    });
  },

  setPhase: (phase: RoundPhase) => {
    set({ phase });
  },

  updateTimer: (remaining: number) => {
    set({ timerRemaining: remaining });
  },

  setBetSelection: (color: string, amount: string) => {
    set((state) => ({
      selectedBets: { ...state.selectedBets, [color]: amount },
    }));
  },

  removeBetSelection: (color: string) => {
    set((state) => {
      const { [color]: _, ...rest } = state.selectedBets;
      return { selectedBets: rest };
    });
  },

  addPlacedBet: (bet: PlacedBet) => {
    set((state) => ({
      placedBets: [...state.placedBets, bet],
    }));
  },

  setResult: (result: RoundResult) => {
    set({ result });
  },

  resetRound: (roundId: string, timer: number) => {
    set({
      currentRound: {
        roundId,
        phase: 'betting',
        timer,
        totalPlayers: 0,
        totalPool: '0',
        gameMode: '',
      },
      phase: 'betting',
      timerRemaining: timer,
      selectedBets: {},
      placedBets: [],
      result: null,
    });
  },

  setConnectionStatus: (status: ConnectionStatus) => {
    set({ connectionStatus: status });
  },
}));
