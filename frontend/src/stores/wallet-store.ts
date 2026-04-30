import { create } from 'zustand';
import type { WalletState, Transaction, PaginatedTransactions, WalletBalance } from '@/types';
import { apiClient } from '@/lib/api-client';

const TRANSACTIONS_PAGE_SIZE = 20;

export const useWalletStore = create<WalletState>((set, get) => ({
  balance: null,
  transactions: [],
  transactionPage: 1,
  hasMoreTransactions: false,
  isLoading: false,

  fetchBalance: async () => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.get<WalletBalance>('/wallet/balance');
      set({ balance: data.balance });
    } finally {
      set({ isLoading: false });
    }
  },

  updateBalance: (newBalance: string) => {
    set({ balance: newBalance });
  },

  fetchTransactions: async (page?: number) => {
    const targetPage = page ?? get().transactionPage;
    set({ isLoading: true });
    try {
      const { data } = await apiClient.get<PaginatedTransactions>(
        `/wallet/transactions?page=${targetPage}&size=${TRANSACTIONS_PAGE_SIZE}`,
      );

      const mapped: Transaction[] = data.items.map((item) => ({
        id: item.id,
        type: item.type,
        amount: item.amount,
        balance_after: item.balance_after,
        description: item.description,
        created_at: item.created_at,
      }));

      set((state) => ({
        transactions: targetPage === 1 ? mapped : [...state.transactions, ...mapped],
        transactionPage: targetPage,
        hasMoreTransactions: data.has_more,
      }));
    } finally {
      set({ isLoading: false });
    }
  },

  deposit: async (amount: string, stripeToken: string) => {
    set({ isLoading: true });
    try {
      const { data } = await apiClient.post<{ balance: string }>('/wallet/deposit', {
        amount,
        stripe_token: stripeToken,
      });
      set({ balance: data.balance });
    } finally {
      set({ isLoading: false });
    }
  },

  withdraw: async (amount: string) => {
    set({ isLoading: true });
    try {
      await apiClient.post('/wallet/withdraw', { amount });
    } finally {
      set({ isLoading: false });
    }
  },
}));
