// === Auth Types ===

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordReset {
  token: string;
  new_password: string;
}

// === Wallet Types ===

export interface WalletBalance {
  balance: string; // e.g. "150.00"
}

export interface DepositRequest {
  amount: string;
  stripe_token: string;
}

export interface WithdrawRequest {
  amount: string;
}

export interface Transaction {
  id: string;
  type: 'deposit' | 'withdrawal' | 'bet_debit' | 'payout_credit';
  amount: string;
  balance_after: string;
  description: string | null;
  created_at: string; // ISO 8601
}

export interface PaginatedTransactions {
  items: Transaction[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

// === Game Types ===

export interface GameMode {
  id: string;
  name: string;
  mode_type: 'classic' | 'timed_challenge' | 'tournament';
  color_options: string[];
  odds: Record<string, string>; // color -> odds decimal string
  min_bet: string;
  max_bet: string;
  round_duration_seconds: number;
  is_active: boolean;
  mode_prefix: string;          // e.g. "100", "101", etc.
  active_round_id?: string;     // current active round for this mode
}

export interface BetRequest {
  round_id: string;
  color: string;
  amount: string;
}

export interface BetResponse {
  id: string;
  color: string;
  amount: string;
  odds_at_placement: string;
  balance_after: string;
}

export type RoundPhase = 'betting' | 'resolution' | 'result';

export interface ColorOption {
  color: string;
  odds: string; // Decimal string
}

export interface PlacedBet {
  id: string;
  color: string;
  amount: string;
  oddsAtPlacement: string;
  potentialPayout: string;
}

export interface RoundResult {
  winningColor: string;
  winningNumber: number;
  playerPayouts: { betId: string; amount: string; isWinner: boolean }[];
}

export interface RoundState {
  roundId: string;
  phase: RoundPhase;
  timer: number;
  totalPlayers: number;
  totalPool: string;
  gameMode: string;
  periodNumber?: string;       // formatted period number for display
}

// === Leaderboard Types ===

export type LeaderboardMetric = 'total_winnings' | 'win_rate' | 'win_streak';
export type LeaderboardPeriod = 'daily' | 'weekly' | 'monthly' | 'all_time';

export interface LeaderboardEntry {
  rank: number;
  player_id: string;
  username: string;
  metric_value: string;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  player_rank: LeaderboardEntry | null; // Viewing player's own rank
  metric: LeaderboardMetric;
  period: LeaderboardPeriod;
}

// === Social Types ===

export interface InviteCode {
  code: string;
  round_id: string;
}

export interface PlayerPublicProfile {
  id: string;
  username: string;
  total_games: number;
  win_rate: string;
  leaderboard_rank: number | null;
}

export interface FriendRequest {
  username: string;
}

// === Responsible Gambling Types ===

export type LimitPeriod = 'daily' | 'weekly' | 'monthly';

export interface DepositLimit {
  period: LimitPeriod;
  amount: string;
  current_usage: string;
  resets_at: string; // ISO 8601
}

export interface SessionLimitRequest {
  duration_minutes: number;
}

export interface SelfExclusionRequest {
  duration: '24h' | '7d' | '30d' | 'permanent';
}

// === Admin Types ===

export interface AdminDashboardMetrics {
  active_players: number;
  total_bets: string;
  total_payouts: string;
  revenue: string;
  period: string;
}

export interface GameConfigUpdate {
  game_mode_id: string;
  min_bet?: string;
  max_bet?: string;
  odds?: Record<string, string>;
  color_options?: string[];
  round_duration_seconds?: number;
}

export interface AdminPlayerEntry {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  event_type: string;
  actor_id: string;
  target_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface RNGAuditEntry {
  id: string;
  round_id: string;
  algorithm: string;
  raw_value: number;
  num_options: number;
  selected_color: string;
  created_at: string;
}

// === API Error Types ===

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// === WebSocket Types ===

export interface PayoutInfo {
  player_id: string;
  bet_id: string;
  amount: string;
}

export type WSIncomingMessage =
  | { type: 'round_state'; phase: RoundPhase; timer: number; round_id: string; total_players: number; total_pool: string; period_number?: string }
  | { type: 'timer_tick'; remaining: number }
  | { type: 'phase_change'; phase: RoundPhase }
  | { type: 'result'; winning_color: string; winning_number: number; payouts: PayoutInfo[]; period_number?: string }
  | { type: 'new_round'; round_id: string; timer: number; period_number?: string }
  | { type: 'chat_message'; sender: string; message: string; timestamp: string }
  | { type: 'bet_update'; total_players: number; total_pool: string }
  | { type: 'error'; code: string; message: string };

export type WSOutgoingMessage =
  | { type: 'chat'; message: string }
  | { type: 'ping' };

// === Store State Interfaces ===

export interface PlayerProfile {
  id: string;
  email: string;
  username: string;
  isAdmin: boolean;
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  player: PlayerProfile | null;
  isAuthenticated: boolean;
  isAdmin: boolean;

  setTokens: (access: string, refresh: string) => void;
  clearTokens: () => void;
  setPlayer: (player: PlayerProfile) => void;
  decodeAndSetPlayer: (accessToken: string) => void;
}

export interface WalletState {
  balance: string | null; // Decimal string, e.g. "150.00"
  transactions: Transaction[];
  transactionPage: number;
  hasMoreTransactions: boolean;
  isLoading: boolean;

  fetchBalance: () => Promise<void>;
  updateBalance: (newBalance: string) => void;
  fetchTransactions: (page?: number) => Promise<void>;
  deposit: (amount: string, stripeToken: string) => Promise<void>;
  withdraw: (amount: string) => Promise<void>;
}

export interface GameState {
  currentRound: RoundState | null;
  phase: RoundPhase;
  timerRemaining: number;
  colorOptions: ColorOption[];
  selectedBets: Map<string, string>; // color -> amount string
  placedBets: PlacedBet[];
  result: RoundResult | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

  setRoundState: (state: RoundState) => void;
  setPhase: (phase: RoundPhase) => void;
  updateTimer: (remaining: number) => void;
  setBetSelection: (color: string, amount: string) => void;
  removeBetSelection: (color: string) => void;
  addPlacedBet: (bet: PlacedBet) => void;
  setResult: (result: RoundResult) => void;
  resetRound: (roundId: string, timer: number) => void;
  setConnectionStatus: (status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting') => void;
}

export interface UIState {
  theme: 'light' | 'dark';
  isChatOpen: boolean;
  unreadChatCount: number;
  isOffline: boolean;
  sessionStartTime: number | null;
  sessionLimitMinutes: number | null;

  setTheme: (theme: 'light' | 'dark') => void;
  toggleChat: () => void;
  incrementUnreadChat: () => void;
  resetUnreadChat: () => void;
  setOffline: (offline: boolean) => void;
  startSession: (limitMinutes: number | null) => void;
}
