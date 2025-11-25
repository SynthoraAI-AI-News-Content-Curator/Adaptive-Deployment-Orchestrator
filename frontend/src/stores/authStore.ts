/**
 * Authentication Store
 * Global state management for user authentication
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, User } from '../services/api';

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        try {
          const response = await api.auth.login({ username, password });
          const token = response.access_token;

          // Store token
          localStorage.setItem('auth_token', token);
          set({ token, isAuthenticated: true });

          // Load user info
          await get().loadUser();
        } catch (error) {
          set({ token: null, user: null, isAuthenticated: false });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('auth_token');
        set({ token: null, user: null, isAuthenticated: false });
        api.auth.logout().catch(() => {});
      },

      loadUser: async () => {
        try {
          const user = await api.auth.getCurrentUser();
          set({ user });
        } catch (error) {
          console.error('Failed to load user:', error);
          set({ user: null });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
