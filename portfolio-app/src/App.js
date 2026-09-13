import React, {
  useState,
  useEffect,
  lazy,
  Suspense,
} from 'react';

import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
} from 'react-router-dom';

import { AuthProvider, useAuth } from './AuthContext';
import './App.css';
import ProfileDialog from './components/dialogs/ProfileDialog';
import { useBackendStatus } from './services/backendStatus';

// Route-level code splitting:
// pages are loaded only when the user navigates to them.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Assets = lazy(() => import('./pages/Assets'));
const Savings = lazy(() => import('./pages/savings'));
const CreditCard = lazy(() => import('./pages/creditcard'));
const Bank = lazy(() => import('./pages/bank'));
const LoginPage = lazy(() => import('./pages/LoginPage'));

const NAV_LINKS = [
  { to: '/dashboard', label: 'Overview' },
  { to: '/assets', label: 'Assets' },
  { to: '/savings', label: 'Savings' },
  { to: '/creditcard', label: 'Credit Cards' },
  { to: '/bank', label: 'Banks' },
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
    checkingSession,
  } = useAuth();

  const backendStatus = useBackendStatus();
  const location = useLocation();

  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  // Close the navigation menu when the Escape key is pressed.
  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const handleKey = event => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
      }
    };

    document.addEventListener('keydown', handleKey);

    return () => {
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  // On mobile, close the overlay after navigation.
  // On desktop, keep the sidebar open until the user explicitly closes it.
  useEffect(() => {
    const isMobile = window.matchMedia('(max-width: 860px)').matches;

    if (isMobile) {
      setMenuOpen(false);
    }
  }, [location.pathname]);

  if (checkingSession && user === null) {
    const bootMessage = backendStatus.phase === 'waking'
      ? 'The server is starting up. This may take a little while.'
      : backendStatus.phase === 'connecting'
        ? 'Connecting to server…'
        : 'Restoring session…';

    return (
      <div className="app-boot-loading">
        <div className="spinner" />
        <p>{bootMessage}</p>
      </div>
    );
  }

  const backendStatusMessage = backendStatus.phase === 'waking'
    ? 'The server is starting up. This may take a little while.'
    : 'Connecting to server…';

  return (
    <div className={`app-shell ${menuOpen ? 'menu-is-open' : ''}`}>
      <header className="app-header">
        <div className="header-left">
          {user && (
            <button
              type="button"
              className={`nav-toggle ${menuOpen ? 'open' : ''}`}
              aria-label={
                menuOpen ? 'Close navigation menu' : 'Open navigation menu'
              }
              aria-expanded={menuOpen}
              aria-controls="app-sidebar"
              onClick={() => setMenuOpen(open => !open)}
            >
              <span />
              <span />
              <span />
            </button>
          )}

          {user ? (
            <NavLink
              to="/dashboard"
              className="logo-link"
              onClick={() => {
                const isMobile = window.matchMedia('(max-width: 860px)').matches;

                if (isMobile) {
                  setMenuOpen(false);
                }
              }}
              aria-label="Go to financial overview"
            >
              My Finances
            </NavLink>
          ) : (
            <span className="logo-link">My Finances</span>
          )}
        </div>

        {user && (
          <button
            type="button"
            className="profile-trigger"
            aria-label="Open profile"
            aria-expanded={profileOpen}
            aria-haspopup="dialog"
            title="Profile"
            onClick={() => {
              setMenuOpen(false);
              setProfileOpen(true);
            }}
          >
            <span className="profile-trigger-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <circle cx="12" cy="8" r="4" />
                <path d="M4.5 20c.8-3.4 3.3-5 7.5-5s6.7 1.6 7.5 5" />
              </svg>
            </span>
          </button>
        )}
      </header>

      {backendStatus.phase !== 'idle' && (
        <div className="backend-status" role="status" aria-live="polite">
          <div className="backend-status-spinner" aria-hidden="true" />
          <span>{backendStatusMessage}</span>
        </div>
      )}

      <div
        className={`app-body ${menuOpen ? 'menu-is-open' : ''} ${
          location.pathname === '/' ? 'auth-body' : ''
        }`}
      >
        {user && (
          <>
            <aside
              id="app-sidebar"
              className={`app-sidebar ${menuOpen ? 'open' : ''}`}
              aria-hidden={!menuOpen}
            >

              <nav className="sidebar-nav" aria-label="Main navigation">
                {NAV_LINKS.map(link => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    className={({ isActive }) =>
                      `sidebar-link ${isActive ? 'active' : ''}`
                    }
                    onClick={() => {
                      const isMobile = window.matchMedia('(max-width: 860px)').matches;

                      if (isMobile) {
                        setMenuOpen(false);
                      }
                    }}
                    tabIndex={menuOpen ? 0 : -1}
                  >
                    {link.label}
                  </NavLink>
                ))}
              </nav>
            </aside>

            <button
              type="button"
              className="sidebar-backdrop"
              aria-label="Close navigation menu"
              tabIndex={menuOpen ? 0 : -1}
              onClick={() => setMenuOpen(false)}
            />
          </>
        )}

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
                element={<Navigate to="/dashboard" replace />}
              />
            </Routes>
          </Suspense>
        </main>
      </div>

      <ProfileDialog
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
      />
    </div>
  );
}

export default App;
