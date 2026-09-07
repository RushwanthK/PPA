import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  const [checkingSession, setCheckingSession] = useState(
    () => Boolean(localStorage.getItem('token'))
  );

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

        if (!response.ok) {
          throw new Error('Invalid token');
        }

        const data = await response.json();

        if (!cancelled) {
          setUser(data);
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.error('Session expired:', error);
          localStorage.removeItem('token');

          if (!cancelled) {
            setUser(null);
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

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setUser(null);
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