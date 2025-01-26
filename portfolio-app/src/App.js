import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Assets from './pages/Assets';
import Savings from './pages/savings';
import CreditCard from './pages/creditcard';

function App() {
  return (
    <div>
      <header>
        <p>Welcome to My Portfolio.</p>
        
        <Link to="/dashboard" style={{ color: 'black', textDecoration: 'none' }}>
          Dashboard Page
        </Link>
        <p>
          <Link to="/assets" style={{ color: 'black', textDecoration: 'none' }}>
                    Assets Page
                  </Link>
        </p>
        <p>
          <Link to="/savings" style={{ color: 'black', textDecoration: 'none' }}>
                    Savings Page
                  </Link>
        </p>
        <p>
          <Link to="/creditcard" style={{ color: 'black', textDecoration: 'none' }}>
                    Credit Cards Page
                  </Link>
        </p>
      </header>

      <Routes>
        <Route path="/" element={<div>Welcome to my portfolio! Click the button above to go to your Dashboard.</div>} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/savings" element={<Savings />} />
        <Route path="/creditcard" element={<CreditCard />} />
      </Routes>
    </div>
  );
}

export default App;


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