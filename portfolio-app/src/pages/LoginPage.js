import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';

const API_URL = process.env.REACT_APP_API_URL;
const EMPTY_FORM = { name: '', password: '', dob: '', place: '' };

function LoginPage({ setUser }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const abortRef = useRef(null);
  const nameInputRef = useRef(null);

  // Autofocus the first field on mount so keyboard users / desktop visitors
  // can start typing immediately without an extra click.
  useEffect(() => {
    nameInputRef.current?.focus();
  }, []);

  // Cancel any in-flight login/register request if the component unmounts
  // mid-request (e.g. user navigates away quickly), so we never try to
  // setState on an unmounted component.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // useCallback keeps these handler references stable across renders,
  // which avoids handing every <input> a brand-new onChange function on
  // each keystroke (cheap here, but it's the correct pattern and matches
  // what the rest of the app is being moved to).
  const handleChange = useCallback(e => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  }, []);

  const handleToggleMode = useCallback(() => {
    setError('');
    setIsRegistering(prev => !prev);
  }, []);

  const handleSubmit = useCallback(async e => {
    e.preventDefault();
    if (submitting) return; // guards against double-submit on slow taps/connections
    setError('');
    setSubmitting(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const endpoint = isRegistering ? '/register' : '/login';
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
        signal: controller.signal,
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
      if (err.name !== 'AbortError') {
        setError('Network error');
      }
    } finally {
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }, [form, isRegistering, navigate, setUser, submitting]);

  return (
    <div className="login-container">
      <h2>{isRegistering ? 'Register' : 'Login'}</h2>
      <form onSubmit={handleSubmit}>
        <input
          ref={nameInputRef}
          name="name"
          value={form.name}
          onChange={handleChange}
          placeholder="Name"
          autoComplete="username"
          required
        />
        <input
          name="password"
          type="password"
          value={form.password}
          onChange={handleChange}
          placeholder="Password"
          autoComplete={isRegistering ? 'new-password' : 'current-password'}
          required
        />

        {isRegistering && (
          <>
            <input
              name="dob"
              type="date"
              value={form.dob}
              onChange={handleChange}
              required
              className={!form.dob ? 'empty-date' : ''}
            />
            <input
              name="place"
              value={form.place}
              onChange={handleChange}
              placeholder="Place"
              autoComplete="address-level2"
              required
            />
          </>
        )}

        <button type="submit" className={isRegistering ? 'green' : 'blue'} disabled={submitting}>
          {submitting ? 'Please wait…' : (isRegistering ? 'Create Account' : 'Login')}
        </button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}

      <p onClick={handleToggleMode} className="toggle-auth">
        {isRegistering ? 'Already have an account? Login' : 'New user? Register'}
      </p>
    </div>
  );
}

export default LoginPage;