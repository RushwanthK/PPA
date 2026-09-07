import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  lazy,
  Suspense,
} from 'react';

import { Routes, Route, NavLink, Navigate } from 'react-router-dom';

import { AuthProvider, useAuth } from './AuthContext';
import './App.css';

// Route-level code splitting:
// pages are loaded only when the user navigates to them.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Assets = lazy(() => import('./pages/Assets'));
const Savings = lazy(() => import('./pages/savings'));
const CreditCard = lazy(() => import('./pages/creditcard'));
const Users = lazy(() => import('./pages/users'));
const Bank = lazy(() => import('./pages/bank'));
const LoginPage = lazy(() => import('./pages/LoginPage'));

const NAV_LINKS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/assets', label: 'Assets' },
  { to: '/savings', label: 'Savings' },
  { to: '/creditcard', label: 'Credit Cards' },
  { to: '/bank', label: 'Banks' },
  { to: '/users', label: 'Profile' },
];

function PrivateRoute({ user, element }) {
  return user ? element : <Navigate to="/" replace />;
}

function PublicRoute({ user, element }) {
  return user ? <Navigate to="/dashboard" replace /> : element;
}

function PageFallback() {
  return (
    <div className="page-loading" role="status" aria-live="polite">
      <div className="spinner" />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

function AppContent() {
  const {
    user,
    setUser,
    logout: authLogout,
    checkingSession,
  } = useAuth();

  const [menuOpen, setMenuOpen] = useState(false);
  const navRef = useRef(null);

  const logout = useCallback(() => {
    authLogout();
    setMenuOpen(false);
  }, [authLogout]);

  // Close the mobile nav on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return;

    const handleClick = e => {
      if (navRef.current && !navRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };

    const handleKey = e => {
      if (e.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);

    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  if (checkingSession && user === null) {
    return (
      <div className="app-boot-loading">
        <div className="spinner" />
        <p>Restoring session…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="logo">My Portfolio</div>

        {user && (
          <>
            <button
              type="button"
              className={`nav-toggle ${menuOpen ? 'open' : ''}`}
              aria-label="Toggle navigation menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(open => !open)}
            >
              <span />
              <span />
              <span />
            </button>

            <nav
              ref={navRef}
              className={`nav-tabs ${menuOpen ? 'open' : ''}`}
            >
              {NAV_LINKS.map(link => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    `nav-link ${isActive ? 'active' : ''}`
                  }
                  onClick={() => setMenuOpen(false)}
                >
                  {link.label}
                </NavLink>
              ))}

              <button
                onClick={logout}
                className="button logout-button"
              >
                Logout
              </button>
            </nav>
          </>
        )}
      </header>

      <main className="app-main">
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route
              path="/"
              element={
                <PublicRoute
                  user={user}
                  element={<LoginPage setUser={setUser} />}
                />
              }
            />

            <Route
              path="/dashboard"
              element={
                <PrivateRoute
                  user={user}
                  element={<Dashboard />}
                />
              }
            />

            <Route
              path="/assets"
              element={
                <PrivateRoute
                  user={user}
                  element={<Assets />}
                />
              }
            />

            <Route
              path="/savings"
              element={
                <PrivateRoute
                  user={user}
                  element={<Savings />}
                />
              }
            />

            <Route
              path="/creditcard"
              element={
                <PrivateRoute
                  user={user}
                  element={<CreditCard />}
                />
              }
            />

            <Route
              path="/bank"
              element={
                <PrivateRoute
                  user={user}
                  element={<Bank />}
                />
              }
            />

            <Route
              path="/users"
              element={
                <PrivateRoute
                  user={user}
                  element={<Users />}
                />
              }
            />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export default App;