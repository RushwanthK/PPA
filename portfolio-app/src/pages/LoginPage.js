import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';

const API_URL = process.env.REACT_APP_API_URL;

const EMPTY_FORM = {
  name: '',
  password: '',
  dob: '',
  place: '',
};

function LoginPage({ setUser }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const navigate = useNavigate();
  const abortRef = useRef(null);
  const nameInputRef = useRef(null);

  useEffect(() => {
    nameInputRef.current?.focus();
  }, [isRegistering]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleChange = useCallback(e => {
    const { name, value } = e.target;

    setForm(prev => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  const handleToggleMode = useCallback(() => {
    setError('');
    setMessage('');
    setForm(EMPTY_FORM);

    setIsRegistering(prev => !prev);
  }, []);

  const handleSubmit = useCallback(
    async e => {
      e.preventDefault();

      if (submitting) {
        return;
      }

      setError('');
      setMessage('');
      setSubmitting(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const endpoint = isRegistering ? '/register' : '/login';

        const response = await fetch(`${API_URL}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(form),
          signal: controller.signal,
        });

        const data = await response.json();

        if (!response.ok) {
          setError(data.error || 'Something went wrong');
          return;
        }

        // Registration and login have different backend responses.
        if (isRegistering) {
          setForm(prev => ({
            ...EMPTY_FORM,
            name: prev.name,
          }));

          setIsRegistering(false);
          setMessage('Account created successfully. Please log in.');

          return;
        }

        // Login response contains the token and authenticated user.
        localStorage.setItem('token', data.token);
        setUser(data.user);

        // Replace login route so browser Back does not return to it.
        navigate('/dashboard', { replace: true });
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError('Network error. Please try again.');
        }
      } finally {
        if (!controller.signal.aborted) {
          setSubmitting(false);
        }
      }
    },
    [form, isRegistering, navigate, setUser, submitting]
  );

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
          autoComplete={
            isRegistering ? 'new-password' : 'current-password'
          }
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

        <button
          type="submit"
          className={isRegistering ? 'green' : 'blue'}
          disabled={submitting}
        >
          {submitting
            ? 'Please wait…'
            : isRegistering
              ? 'Create Account'
              : 'Login'}
        </button>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}

      <button
        type="button"
        onClick={handleToggleMode}
        className="toggle-auth"
      >
        {isRegistering
          ? 'Already have an account? Login'
          : 'New user? Register'}
      </button>
    </div>
  );
}

export default LoginPage;