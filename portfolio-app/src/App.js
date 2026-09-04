import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import React, { useState, useEffect, useMemo, useCallback, useRef, lazy, Suspense } from 'react';
import AuthContext from './AuthContext';
import './App.css';

// Route-level code splitting: each page becomes its own chunk that is only
// downloaded when the user actually navigates to it, instead of every page
// (Dashboard, Assets, Savings, CreditCard, Bank, Users) being bundled into
// the initial load before the user even logs in.
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

// Declared once, outside App, so it is a stable component reference across
// renders (previously this was recreated on every App render, which forced
// React to unmount/remount the whole routed page tree on every state change).
function PrivateRoute({ user, element }) {
  return user ? element : <Navigate to="/" replace />;
}

function PageFallback() {
  return (
    <div className="page-loading" role="status" aria-live="polite">
      <div className="spinner" />
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(!!localStorage.getItem('token'));
  const [menuOpen, setMenuOpen] = useState(false);
  const navRef = useRef(null);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (!storedToken) return;

    let cancelled = false;

    fetch(`${process.env.REACT_APP_API_URL}/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${storedToken}`
      }
    })
      .then(res => {
        if (!res.ok) throw new Error('Invalid token');
        return res.json();
      })
      .then(data => {
        if (!cancelled) setUser(data); // Restore user on refresh
      })
      .catch(err => {
        console.error('Session expired:', err);
        localStorage.removeItem('token');
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setCheckingSession(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setUser(null);
    setMenuOpen(false);
  }, []);

  // Close the mobile nav on outside click / Escape, and whenever a link is
  // tapped, so it never lingers open over page content.
  useEffect(() => {
    if (!menuOpen) return;

    const handleClick = e => {
      if (navRef.current && !navRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleKey = e => {
      if (e.key === 'Escape') setMenuOpen(false);
    };

    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [menuOpen]);

  // Memoized so consumers of AuthContext don't re-render just because App
  // re-rendered for an unrelated reason (e.g. menuOpen toggling).
  const authValue = useMemo(() => ({ user, setUser }), [user]);

  if (checkingSession && user === null) {
    return (
      <div className="app-boot-loading">
        <div className="spinner" />
        <p>Restoring session…</p>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={authValue}>
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

              <nav ref={navRef} className={`nav-tabs ${menuOpen ? 'open' : ''}`}>
                {NAV_LINKS.map(link => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    onClick={() => setMenuOpen(false)}
                  >
                    {link.label}
                  </NavLink>
                ))}
                <button onClick={logout} className="button logout-button">Logout</button>
              </nav>
            </>
          )}
        </header>

        <main className="app-main">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<LoginPage setUser={setUser} />} />
              <Route path="/dashboard" element={<PrivateRoute user={user} element={<Dashboard />} />} />
              <Route path="/assets" element={<PrivateRoute user={user} element={<Assets />} />} />
              <Route path="/savings" element={<PrivateRoute user={user} element={<Savings />} />} />
              <Route path="/creditcard" element={<PrivateRoute user={user} element={<CreditCard />} />} />
              <Route path="/bank" element={<PrivateRoute user={user} element={<Bank />} />} />
              <Route path="/users" element={<PrivateRoute user={user} element={<Users />} />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </AuthContext.Provider>
  );
}

export default App;