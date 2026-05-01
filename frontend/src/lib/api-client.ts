import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import type { ApiError, TokenPair } from '@/types';

// ---------------------------------------------------------------------------
// Error‑code → human‑readable message map
// ---------------------------------------------------------------------------

const ERROR_MESSAGES: Record<string, string> = {
  INSUFFICIENT_BALANCE: 'Insufficient balance',
  BET_BELOW_MIN: 'Bet amount is below the minimum',
  BET_ABOVE_MAX: 'Bet amount exceeds the maximum',
  BETTING_CLOSED: 'Betting is closed for this round',
  RATE_LIMIT_EXCEEDED: 'Too many requests. Please try again later.',
  INVALID_CREDENTIALS: 'Invalid email or password',
  TOKEN_EXPIRED: 'Session expired. Please log in again.',
  ACCOUNT_LOCKED: 'Account is locked',
  ACCOUNT_SUSPENDED: 'Account has been suspended',
  SELF_EXCLUDED: 'Account is self-excluded',
  DEPOSIT_LIMIT_EXCEEDED: 'Deposit limit exceeded',
  INTERNAL_ERROR: 'Something went wrong. Please try again.',
};

// ---------------------------------------------------------------------------
// Error parsing helpers
// ---------------------------------------------------------------------------

/**
 * Extract the structured error payload from an Axios error response.
 * Returns `null` when the response doesn't match the expected shape.
 */
export function parseApiError(
  error: unknown,
): ApiError['error'] | null {
  if (!isAxiosError(error)) return null;

  const data = error.response?.data as ApiError | undefined;
  if (
    data &&
    typeof data === 'object' &&
    'error' in data &&
    data.error &&
    typeof data.error.code === 'string' &&
    typeof data.error.message === 'string'
  ) {
    return data.error;
  }
  return null;
}

/**
 * Map an error code to a user‑friendly message.
 * Falls back to the raw `serverMessage` (if provided) or a generic string.
 */
export function getErrorMessage(
  code: string,
  serverMessage?: string,
): string {
  return ERROR_MESSAGES[code] ?? serverMessage ?? 'An unexpected error occurred';
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Log the API base URL on initialization (client-side only)
if (typeof window !== 'undefined') {
  console.log('[api-client] Using BASE_URL:', BASE_URL);
  console.log('[api-client] NEXT_PUBLIC_API_URL from env:', process.env.NEXT_PUBLIC_API_URL || 'NOT SET');
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// ---------------------------------------------------------------------------
// Lazy auth‑store accessor (avoids circular‑dependency issues)
// ---------------------------------------------------------------------------

type AuthStoreAccessor = () => {
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (access: string, refresh: string) => void;
  clearTokens: () => void;
};

let _getAuthStore: AuthStoreAccessor | null = null;

/**
 * Register the auth‑store accessor. Called once from the Auth Store module
 * after it has been created, so the API client never imports the store
 * directly.
 */
export function registerAuthStore(accessor: AuthStoreAccessor): void {
  _getAuthStore = accessor;
}

function getAuth() {
  if (!_getAuthStore) {
    throw new Error(
      'Auth store not registered. Call registerAuthStore() before making authenticated requests.',
    );
  }
  return _getAuthStore();
}

// ---------------------------------------------------------------------------
// Request interceptor — attach Bearer token
// ---------------------------------------------------------------------------

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  try {
    const { accessToken } = getAuth();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
  } catch {
    // Auth store not registered yet — skip token attachment
  }
  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor — 401 TOKEN_EXPIRED → refresh & retry
// ---------------------------------------------------------------------------

let isRefreshing = false;
let failedQueue: {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}[] = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((p) => {
    if (token) {
      p.resolve(token);
    } else {
      p.reject(error);
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Only handle 401 TOKEN_EXPIRED
    const errorCode = (error.response?.data as ApiError | undefined)?.error
      ?.code;
    if (
      error.response?.status !== 401 ||
      errorCode !== 'TOKEN_EXPIRED' ||
      originalRequest._retry
    ) {
      return Promise.reject(error);
    }

    // If a refresh is already in progress, queue this request
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      }).then((newToken) => {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const auth = getAuth();
      const { data } = await axios.post<TokenPair>(
        `${BASE_URL}/auth/refresh`,
        { refresh_token: auth.refreshToken },
        { headers: { 'Content-Type': 'application/json' } },
      );

      auth.setTokens(data.access_token, data.refresh_token);
      processQueue(null, data.access_token);

      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      try {
        const auth = getAuth();
        auth.clearTokens();
      } catch {
        // ignore
      }
      // Redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

// ---------------------------------------------------------------------------
// Type guard
// ---------------------------------------------------------------------------

function isAxiosError(error: unknown): error is AxiosError {
  return axios.isAxiosError(error);
}

// Re‑export for convenience
export { ERROR_MESSAGES };
export default apiClient;
