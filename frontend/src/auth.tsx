import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { authApi } from './api/endpoints';
import type { Me } from './api/endpoints';
import { ApiError, clearCsrf } from './api/client';

type AuthContextValue = {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setChatMode: (mode: string) => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await authApi.me());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setMe(null);
      else setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // UI density per chat mode (index.css: [data-chat-mode="zen"] etc.)
  useEffect(() => {
    document.body.dataset.chatMode = me?.chat_mode ?? 'work';
    return () => {
      delete document.body.dataset.chatMode;
    };
  }, [me?.chat_mode]);

  const login = useCallback(async (username: string, password: string) => {
    setMe(await authApi.login(username, password));
    clearCsrf();
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      clearCsrf();
      setMe(null);
    }
  }, []);

  const setChatMode = useCallback(async (mode: string) => {
    setMe(await authApi.setChatMode(mode));
  }, []);

  const value = useMemo(
    () => ({ me, loading, login, logout, setChatMode, refresh }),
    [me, loading, login, logout, setChatMode, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
