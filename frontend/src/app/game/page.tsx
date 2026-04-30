'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useCountdown } from '@/hooks/useCountdown';
import { useGameStore } from '@/stores/game-store';
import { useWalletStore } from '@/stores/wallet-store';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { calculatePotentialPayout } from '@/lib/utils';
import { soundManager } from '@/lib/sound-manager';
import type { BetResponse, GameMode } from '@/types';

import ResultDisplay from '@/components/ResultDisplay';
import CountdownTimer from '@/components/CountdownTimer';
import ColorBetButtons from '@/components/ColorBetButtons';
import NumberGrid from '@/components/NumberGrid';
import BigSmallButtons from '@/components/BigSmallButtons';
import GameModeTabs from '@/components/GameModeTabs';
import BetConfirmationSheet from '@/components/BetConfirmationSheet';
import SoundToggle from '@/components/SoundToggle';
import RulesModal from '@/components/RulesModal';
import WalletCard from '@/components/WalletCard';
import AnnouncementBar from '@/components/AnnouncementBar';
import HistoryTable from '@/components/HistoryTable';
import WinLossDialog from '@/components/WinLossDialog';

const DEFAULT_ROUND_ID = 'current';

/** Default round duration used when the server hasn't sent a value yet. */
const DEFAULT_TOTAL_SECONDS = 30;

export default function GameViewPage() {
  useAuthGuard();

  const searchParams = useSearchParams();
  const fallbackRoundId = searchParams.get('roundId') ?? DEFAULT_ROUND_ID;

  // ── Game mode state ──
  const gameModes = useGameStore((s) => s.gameModes);
  const activeGameModeId = useGameStore((s) => s.activeGameModeId);
  const setGameModes = useGameStore((s) => s.setGameModes);
  const setActiveGameMode = useGameStore((s) => s.setActiveGameMode);

  // Derive the active round ID from the selected game mode
  const activeMode = (gameModes ?? []).find((m) => m.id === activeGameModeId);
  const roundId = activeMode?.active_round_id ?? fallbackRoundId;

  // ── Fetch game modes on mount ──
  useEffect(() => {
    let cancelled = false;

    async function fetchModes() {
      try {
        const { data } = await apiClient.get<GameMode[]>('/game/modes');
        if (cancelled) return;

        const activeModes = data.filter((m) => m.is_active);
        setGameModes(activeModes);

        // Set the first mode as active if none is currently set
        const currentActiveId = useGameStore.getState().activeGameModeId;
        if (!currentActiveId && activeModes.length > 0) {
          setActiveGameMode(activeModes[0].id);
        }
      } catch {
        // Silently fail — the page will use the fallback round ID
      }
    }

    fetchModes();
    return () => { cancelled = true; };
  }, [setGameModes, setActiveGameMode]);

  // ── Handle game mode switching ──
  const handleModeChange = useCallback(
    (modeId: string) => {
      setActiveGameMode(modeId);
    },
    [setActiveGameMode],
  );

  useWebSocket(roundId);

  // ── Store selectors ──
  const phase = useGameStore((s) => s.phase);
  const timerRemaining = useGameStore((s) => s.timerRemaining);
  const currentRound = useGameStore((s) => s.currentRound);
  const placedBets = useGameStore((s) => s.placedBets);
  const connectionStatus = useGameStore((s) => s.connectionStatus);
  const betAmount = useGameStore((s) => s.betAmount);
  const addPlacedBet = useGameStore((s) => s.addPlacedBet);
  const periodNumber = useGameStore((s) => s.periodNumber);

  const balance = useWalletStore((s) => s.balance);
  const updateBalance = useWalletStore((s) => s.updateBalance);
  const fetchBalance = useWalletStore((s) => s.fetchBalance);

  // ── Fetch wallet balance on mount ──
  useEffect(() => {
    fetchBalance();
  }, [fetchBalance]);

  // ── Bet sheet state ──
  const showBetSheet = useGameStore((s) => s.showBetSheet);
  const betSheetType = useGameStore((s) => s.betSheetType);
  const openBetSheet = useGameStore((s) => s.openBetSheet);
  const closeBetSheet = useGameStore((s) => s.closeBetSheet);

  // ── Win/Loss dialog state ──
  const showWinLossDialog = useGameStore((s) => s.showWinLossDialog);
  const closeWinLossDialog = useGameStore((s) => s.closeWinLossDialog);
  const result = useGameStore((s) => s.result);

  const { remaining } = useCountdown(timerRemaining);

  // ── Local UI state ──
  const [toast, setToast] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);

  const isBetting = phase === 'betting';
  const isResolving = phase === 'resolution';
  const showReconnecting =
    connectionStatus === 'reconnecting' || connectionStatus === 'disconnected';

  // Derive the total seconds for the countdown ring from the round state.
  const totalSeconds = currentRound?.timer
    ? Math.max(currentRound.timer, remaining)
    : DEFAULT_TOTAL_SECONDS;

  // ── Sound: initialize on first user interaction (requirement 8.7) ──
  const soundInitRef = useRef(false);
  useEffect(() => {
    if (soundInitRef.current) return;
    const handler = () => {
      soundManager.initialize();
      soundInitRef.current = true;
      document.removeEventListener('click', handler);
      document.removeEventListener('keydown', handler);
      document.removeEventListener('touchstart', handler);
    };
    document.addEventListener('click', handler);
    document.addEventListener('keydown', handler);
    document.addEventListener('touchstart', handler);
    return () => {
      document.removeEventListener('click', handler);
      document.removeEventListener('keydown', handler);
      document.removeEventListener('touchstart', handler);
    };
  }, []);

  // ── Sound: countdown tick during last 5 seconds (requirements 8.1, 8.2) ──
  const prevRemainingRef = useRef(remaining);
  useEffect(() => {
    const prev = prevRemainingRef.current;
    prevRemainingRef.current = remaining;

    // Only play when the value actually decremented (avoid replaying on re-renders)
    if (remaining >= prev) return;
    if (!isBetting) return;

    if (remaining === 1) {
      soundManager.playLastSecond();
    } else if (remaining > 0 && remaining <= 5) {
      soundManager.playTick();
    }
  }, [remaining, isBetting]);

  // ── Sound: win celebration when WinLossDialog shows a win (requirement 8.4) ──
  useEffect(() => {
    if (showWinLossDialog && result) {
      const hasWin = result.playerPayouts.some((p) => p.isWinner);
      if (hasWin) {
        soundManager.playWinCelebration();
      }
    }
  }, [showWinLossDialog, result]);

  // ── Bet placement ──
  const placeBet = useCallback(
    async (color: string, amountOverride?: string) => {
      if (!isBetting || submitting) return;

      const amount = amountOverride ?? betAmount;
      const effectiveRoundId = currentRound?.roundId ?? roundId;

      // Basic client-side validation
      if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
        setError('Enter a valid bet amount');
        return;
      }
      if (balance !== null && Number(amount) > Number(balance)) {
        setError('Insufficient balance');
        return;
      }

      setSubmitting(true);
      setError(null);

      try {
        const { data } = await apiClient.post<BetResponse>('/game/bet', {
          round_id: effectiveRoundId,
          color,
          amount,
        });

        addPlacedBet({
          id: data.id,
          color: data.color,
          amount: data.amount,
          oddsAtPlacement: data.odds_at_placement,
          potentialPayout: calculatePotentialPayout(data.amount, data.odds_at_placement),
        });

        updateBalance(data.balance_after);

        // Play bet confirmation sound (requirement 8.3)
        soundManager.playBetConfirm();

        setToast(`Bet placed: $${data.amount} on ${data.color}`);
        setTimeout(() => setToast(null), 3000);
      } catch (err: unknown) {
        const parsed = parseApiError(err);
        if (parsed) {
          setError(getErrorMessage(parsed.code, parsed.message));
        } else {
          setError('An unexpected error occurred');
        }
      } finally {
        setSubmitting(false);
      }
    },
    [isBetting, submitting, betAmount, currentRound, roundId, balance, addPlacedBet, updateBalance],
  );

  const handleSelectColor = useCallback(
    (color: string) => openBetSheet(color),
    [openBetSheet],
  );

  const handleSelectNumber = useCallback(
    (num: number) => openBetSheet(String(num)),
    [openBetSheet],
  );

  const handleSelectBigSmall = useCallback(
    (type: 'big' | 'small') => openBetSheet(type),
    [openBetSheet],
  );

  const handleBetConfirm = useCallback(
    (amount: number, quantity: number) => {
      if (!betSheetType) return;
      const totalAmount = String(amount * quantity);
      closeBetSheet();
      placeBet(betSheetType, totalAmount);
    },
    [betSheetType, placeBet, closeBetSheet],
  );

  // Derive placed color/number/big-small sets for badge indicators
  const placedColors = new Set(
    placedBets.filter((b) => !/^\d$/.test(b.color) && b.color !== 'big' && b.color !== 'small').map((b) => b.color),
  );
  const placedNumbers = new Set(
    placedBets.filter((b) => /^\d$/.test(b.color)).map((b) => b.color),
  );
  const placedBigSmall = new Set(
    placedBets.filter((b) => b.color === 'big' || b.color === 'small').map((b) => b.color),
  );

  // ── Derive WinLossDialog props from result ──
  const hasWin = result?.playerPayouts.some((p) => p.isWinner) ?? false;
  const totalBonus = result
    ? result.playerPayouts
        .reduce((sum, p) => sum + Number(p.amount), 0)
        .toFixed(2)
    : '0.00';
  const winningIsBig = (result?.winningNumber ?? 0) >= 5;

  return (
    <main className="casino-bg flex flex-col pb-6">
      {/* ── Connection status banner ── */}
      {showReconnecting && (
        <div
          role="alert"
          aria-live="assertive"
          className="mx-4 mt-4 rounded-lg bg-yellow-900/60 px-4 py-2 text-center text-sm font-medium text-yellow-200"
        >
          {connectionStatus === 'reconnecting'
            ? 'Reconnecting to game server…'
            : 'Disconnected from game server. Attempting to reconnect…'}
        </div>
      )}

      {/* ── Toast notification ── */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="mx-4 mt-3 rounded-lg bg-casino-green/20 px-4 py-2 text-center text-sm font-medium text-casino-green"
        >
          {toast}
        </div>
      )}

      {/* ── Error banner ── */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mx-4 mt-3 rounded-lg bg-casino-red/20 px-4 py-2 text-center text-sm font-medium text-casino-red"
        >
          {error}
        </div>
      )}

      {/* 1. WalletCard */}
      <WalletCard />

      {/* 2. AnnouncementBar */}
      <AnnouncementBar />

      {/* 3. GameModeTabs */}
      {gameModes && gameModes.length > 0 && (
        <GameModeTabs
          modes={gameModes}
          activeMode={activeGameModeId ?? ''}
          onModeChange={handleModeChange}
        />
      )}

      {/* 4. Timer area (PeriodNumber + CountdownTimer + HowToPlay + SoundToggle) */}
      <header className="relative px-4 pt-5 pb-2 text-center">
        {/* Sound toggle in header area (requirement 8.5) */}
        <div className="absolute right-4 top-5" data-testid="sound-toggle-wrapper">
          <SoundToggle />
        </div>
        <div className="flex items-center justify-center gap-2">
          <h1 className="text-lg font-bold text-casino-text-primary" data-testid="period-number-display">
            {periodNumber ?? currentRound?.roundId ?? '—'}
          </h1>
          <button
            type="button"
            onClick={() => setRulesModalOpen(true)}
            className="inline-flex items-center justify-center rounded-full text-casino-text-muted hover:text-casino-text-primary casino-transition"
            aria-label="How to Play"
            data-testid="how-to-play-btn"
          >
            ❓
          </button>
        </div>
        <div className="mt-1 flex items-center justify-center gap-4 text-xs text-casino-text-muted">
          <span data-testid="total-players">
            Players: <strong className="text-casino-text-secondary">{currentRound?.totalPlayers ?? 0}</strong>
          </span>
          <span data-testid="total-pool">
            Pool: <strong className="text-casino-text-secondary">${currentRound?.totalPool ?? '0'}</strong>
          </span>
        </div>
      </header>

      {/* Countdown Timer */}
      <div className="mt-2">
        <CountdownTimer
          totalSeconds={totalSeconds}
          remainingSeconds={remaining}
          isResolving={isResolving}
        />
      </div>

      {/* 5. ResultDisplay */}
      <div className="mt-2 px-4">
        <ResultDisplay />
      </div>

      {/* 6. ColorBetButtons */}
      <div className="mt-4">
        <ColorBetButtons
          onSelectColor={handleSelectColor}
          disabled={!isBetting || submitting}
          placedColors={placedColors}
        />
      </div>

      {/* 7. NumberGrid */}
      <div className="mt-4">
        <NumberGrid
          onSelectNumber={handleSelectNumber}
          disabled={!isBetting || submitting}
          placedNumbers={placedNumbers}
        />
      </div>

      {/* 8. BigSmallButtons */}
      <div className="mt-4">
        <BigSmallButtons
          onSelectBigSmall={handleSelectBigSmall}
          disabled={!isBetting || submitting}
          placedBigSmall={placedBigSmall}
        />
      </div>

      {/* 9. HistoryTable */}
      <div className="mt-6 mb-4">
        <HistoryTable gameModeId={activeGameModeId ?? ''} />
      </div>

      {/* 10. BetConfirmationSheet (overlay) */}
      <BetConfirmationSheet
        isOpen={showBetSheet}
        betType={betSheetType ?? ''}
        gameModeName={activeMode?.name ?? 'Win Go'}
        balance={balance ?? '0'}
        onConfirm={handleBetConfirm}
        onCancel={closeBetSheet}
      />

      {/* 11. WinLossDialog (overlay) */}
      <WinLossDialog
        isOpen={showWinLossDialog}
        isWin={hasWin}
        winningNumber={result?.winningNumber ?? 0}
        winningColor={result?.winningColor ?? 'green'}
        isBig={winningIsBig}
        totalBonus={totalBonus}
        periodNumber={periodNumber ?? ''}
        onClose={closeWinLossDialog}
      />

      {/* ── Rules Modal (overlay) ── */}
      <RulesModal
        isOpen={rulesModalOpen}
        onClose={() => setRulesModalOpen(false)}
      />
    </main>
  );
}
