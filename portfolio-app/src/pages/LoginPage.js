import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';

const API_URL = process.env.REACT_APP_API_URL;

function LoginPage({ setUser }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [form, setForm] = useState({ name: '', password: '', dob: '', place: '' });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');

    try {
      const endpoint = isRegistering ? '/register' : '/login';
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'Something went wrong');
        return;
      }

      localStorage.setItem('token', data.token);
      setUser(data.user); // set current user
      navigate('/dashboard');
    } catch (err) {
      setError('Network error');
    }
  };

  return (
    <div className="login-container">
      <h2>{isRegistering ? 'Register' : 'Login'}</h2>
      <form onSubmit={handleSubmit}>
        <input name="name" value={form.name} onChange={handleChange} placeholder="Name" required />
        <input name="password" type="password" value={form.password} onChange={handleChange} placeholder="Password" required />

        {isRegistering && (
          <>
            <input 
              name="dob" 
              type="date" 
              value={form.dob} 
              onChange={handleChange} 
              required
              className={!form.dob ? "empty-date" : ""}  // Add this line
            />
            <input name="place" value={form.place} onChange={handleChange} placeholder="Place" required />
          </>
        )}

        <button type="submit" className={isRegistering ? 'green' : 'blue'}>
          {isRegistering ? 'Create Account' : 'Login'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      <p onClick={() => setIsRegistering(!isRegistering)} className="toggle-auth">
        {isRegistering ? 'Already have an account? Login' : 'New user? Register'}
      </p>
    </div>
  );
}

export default LoginPage;
