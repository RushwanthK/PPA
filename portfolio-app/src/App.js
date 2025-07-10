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
    // Optional: implement token validation with backend later
    const storedToken = localStorage.getItem('token');
    if (!storedToken) return;
    // You can add a `/me` route later to validate
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  const PrivateRoute = ({ element }) => {
    return user ? element : <Navigate to="/" />;
  };

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
              <button onClick={logout} className="nav-link">Logout</button>
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


//Version 2
/*import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Assets from './pages/Assets';
import Savings from './pages/savings';
import CreditCard from './pages/creditcard';
import Users from './pages/users';
import Bank from './pages/bank';
import './App.css';

function App() {
  return (
    <div>
      <header className="app-header">
        <div className="logo">My Portfolio</div>
        <nav className="nav-tabs">
          <Link to="/dashboard" className="nav-link">Dashboard</Link>
          <Link to="/assets" className="nav-link">Assets</Link>
          <Link to="/savings" className="nav-link">Savings</Link>
          <Link to="/creditcard" className="nav-link">Credit Cards</Link>
          <Link to="/bank" className="nav-link">Banks</Link>
          <Link to="/users" className="nav-link">Users</Link>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<div>Welcome to my portfolio! Click the button above to go to your Dashboard.</div>} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/savings" element={<Savings />} />
        <Route path="/creditcard" element={<CreditCard />} />
        <Route path="/bank" element={<Bank />} />
        <Route path="/users" element={<Users />} />
      </Routes>
    </div>
  );
}

export default App;
*/

//version 1
/*import './App.css';
import { BrowserRouter as Router, Routes, Route, Link, BrowserRouter } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Assets from './pages/Assets';

function App() {
  return (
   
    <BrowserRouter>
      <div className="App">
        <header className="App-header">
          <p>Welcome to My Portfolio.</p>
          
          <Link to="/dashboard" className="dashboard-button" style={{ color: 'white', textDecoration: 'none' }}>
            <button style={{ padding: '10px 20px', fontSize: '16px', cursor: 'pointer' }}>
              Click here to go to Dashboard
            </button>
          </Link>
          <Link to="/assets" >
              Click here to go to Assets
          </Link>
        </header>

        
        <Routes>
          
          <Route path="/" element={<div>Welcome to my portfolio! Click the button above to go to your Dashboard.</div>} />
          
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/assets" element={<Assets />} />
        </Routes>
      </div>
    </BrowserRouter>
    
  );
}

export default App;*/