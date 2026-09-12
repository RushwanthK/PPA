import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  notifySessionExpired,
  onSessionExpired,
} from './services/authEvents';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const [checkingSession, setCheckingSession] = useState(
    () => Boolean(localStorage.getItem('token'))
  );

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setUser(null);
  }, []);

  /*
   * Central session-expiry reaction.
   *
   * api.js detects a 401 and emits the session-expired event.
   * AuthContext owns the actual authentication-state change.
   */
  useEffect(() => {
    return onSessionExpired(logout);
  }, [logout]);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');

    if (!storedToken) {
      setCheckingSession(false);
      return;
    }

    let cancelled = false;

    const restoreSession = async () => {
      try {
        const response = await fetch(
          `${process.env.REACT_APP_API_URL}/me`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${storedToken}`,
            },
          }
        );

        /*
         * /me is intentionally kept on native fetch().
         *
         * A 401 means the stored session is no longer valid,
         * so use the same centralized session-expiry action.
         */
        if (response.status === 401) {
          notifySessionExpired();
          return;
        }

        if (!response.ok) {
          throw new Error('Failed to restore session');
        }

        const data = await response.json();

        if (!cancelled) {
          setUser(data);
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Session restoration failed:', error);

          /*
           * Only authentication failure should force logout.
           * Other failures are not automatically treated as
           * "expired session".
           */
          if (!cancelled) {
            setCheckingSession(false);
          }
        }
      } finally {
        if (!cancelled) {
          setCheckingSession(false);
        }
      }
    };

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      user,
      setUser,
      logout,
      checkingSession,
    }),
    [user, logout, checkingSession]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }

  return context;
}

export default AuthContext;