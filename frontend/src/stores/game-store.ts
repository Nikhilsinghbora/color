import { create } from 'zustand';
import type {
  RoundPhase,
  ColorOption,
  PlacedBet,
  RoundResult,
  RoundState,
  GameMode,
} from '@/types';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface LastResult {
  winningNumber: number;
  winningColor: string;
}

export interface RoundHistoryEntry {
  roundId: string;
  winningNumber: number;
  winningColor: string;
}

export interface GameStoreState {
  currentRound: RoundState | null;
  phase: RoundPhase;
  timerRemaining: number;
  colorOptions: ColorOption[];
  selectedBets: Record<string, string>; // color or number string -> amount string
  placedBets: PlacedBet[];
  result: RoundResult | null;
  lastResult: LastResult | null;
  betAmount: string;
  roundHistory: RoundHistoryEntry[];
  connectionStatus: ConnectionStatus;
  activeGameModeId: string | null;
  gameModes: GameMode[];
  periodNumber: string | null;
  showBetSheet: boolean;
  betSheetType: string | null;
  showWinLossDialog: boolean;

  setRoundState: (state: RoundState) => void;
  setPhase: (phase: RoundPhase) => void;
  updateTimer: (remaining: number) => void;
  setBetSelection: (color: string, amount: string) => void;
  removeBetSelection: (color: string) => void;
  addPlacedBet: (bet: PlacedBet) => void;
  setResult: (result: RoundResult) => void;
  resetRound: (roundId: string, timer: number) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setBetAmount: (amount: string) => void;
  setActiveGameMode: (modeId: string) => void;
  setGameModes: (modes: GameMode[]) => void;
  setPeriodNumber: (pn: string) => void;
  openBetSheet: (betType: string) => void;
  closeBetSheet: () => void;
  openWinLossDialog: () => void;
  closeWinLossDialog: () => void;
}

export const useGameStore = create<GameStoreState>((set) => ({
  currentRound: null,
  phase: 'betting',
  timerRemaining: 0,
  colorOptions: [],
  selectedBets: {},
  placedBets: [],
  result: null,
  lastResult: null,
  betAmount: '10',
  roundHistory: [],
  connectionStatus: 'disconnected',
  activeGameModeId: null,
  gameModes: [],
  periodNumber: null,
  showBetSheet: false,
  betSheetType: null,
  showWinLossDialog: false,

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
    set((state) => ({
      result,
      lastResult: {
        winningNumber: result.winningNumber,
        winningColor: result.winningColor,
      },
      roundHistory: [
        ...state.roundHistory,
        ...(state.currentRound
          ? [{
              roundId: state.currentRound.roundId,
              winningNumber: result.winningNumber,
              winningColor: result.winningColor,
            }]
          : []),
      ],
    }));
  },

  resetRound: (roundId: string, timer: number) => {
    set((state) => ({
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
      periodNumber: null,
      // Preserve lastResult so ResultDisplay continues showing previous round's result
      lastResult: state.lastResult,
    }));
  },

  setConnectionStatus: (status: ConnectionStatus) => {
    set({ connectionStatus: status });
  },

  setBetAmount: (amount: string) => {
    set({ betAmount: amount });
  },

  setActiveGameMode: (modeId: string) => {
    set({ activeGameModeId: modeId });
  },

  setGameModes: (modes: GameMode[]) => {
    set({ gameModes: modes });
  },

  setPeriodNumber: (pn: string) => {
    set({ periodNumber: pn });
  },

  openBetSheet: (betType: string) => {
    set({ showBetSheet: true, betSheetType: betType });
  },

  closeBetSheet: () => {
    set({ showBetSheet: false, betSheetType: null });
  },

  openWinLossDialog: () => {
    set({ showWinLossDialog: true });
  },

  closeWinLossDialog: () => {
    set({ showWinLossDialog: false });
  },
}));
