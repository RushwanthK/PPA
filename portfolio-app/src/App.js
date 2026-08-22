import { Routes, Route, Link, Navigate } from 'react-router-dom';
import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Assets from './pages/Assets';
import Savings from './pages/savings';
import CreditCard from './pages/creditcard';
import Users from './pages/users';
import Bank from './pages/bank';
import LoginPage from './pages/LoginPage';
import AuthContext from './AuthContext';
import './App.css';

function App() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (!storedToken) return;

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
        setUser(data); // ✅ Restore user on refresh
      })
      .catch(err => {
        console.error('Session expired:', err);
        localStorage.removeItem('token');
        setUser(null);
      });
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  const PrivateRoute = ({ element }) => {
    return user ? element : <Navigate to="/" />;
  };

  if (localStorage.getItem('token') && user === null) {
    return <div className="loading">Restoring session...</div>;
  }

  return (
    <AuthContext.Provider value={{ user, setUser }}>
      <div>
        <header className="app-header">
          <div className="logo">My Portfolio</div>
          {user && (
            <nav className="nav-tabs">
              <Link to="/dashboard" className="nav-link">Dashboard</Link>
              <Link to="/assets" className="nav-link">Assets</Link>
              <Link to="/savings" className="nav-link">Savings</Link>
              <Link to="/creditcard" className="nav-link">Credit Cards</Link>
              <Link to="/bank" className="nav-link">Banks</Link>
              <Link to="/users" className="nav-link">Profile</Link>
              <button onClick={logout} className="button logout-button">Logout</button>
            </nav>
          )}
        </header>

        <Routes>
          <Route path="/" element={<LoginPage setUser={setUser} />} />
          <Route path="/dashboard" element={<PrivateRoute element={<Dashboard />} />} />
          <Route path="/assets" element={<PrivateRoute element={<Assets />} />} />
          <Route path="/savings" element={<PrivateRoute element={<Savings />} />} />
          <Route path="/creditcard" element={<PrivateRoute element={<CreditCard />} />} />
          <Route path="/bank" element={<PrivateRoute element={<Bank />} />} />
          <Route path="/users" element={<PrivateRoute element={<Users />} />} />
        </Routes>
      </div>
    </AuthContext.Provider>
  );
}

export default App;
