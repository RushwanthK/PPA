import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import LoginPage from './LoginPage';

const renderLogin = (setUser = jest.fn()) => {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<LoginPage setUser={setUser} />} />
        <Route path="/dashboard" element={<h1>Dashboard page</h1>} />
      </Routes>
    </MemoryRouter>
  );

  return { setUser, user: userEvent.setup() };
};

const jsonResponse = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

describe('LoginPage', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test('renders the login form by default', () => {
    renderLogin();

    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Name')).toBeRequired();
    expect(screen.getByPlaceholderText('Password')).toBeRequired();
    expect(screen.queryByPlaceholderText('Place')).not.toBeInTheDocument();
  });

  test('logs in, stores the token, sets the user and goes to the dashboard', async () => {
    const apiUser = { id: 1, name: 'tester' };
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(200, { token: 'jwt-token', user: apiUser }));

    const { setUser, user } = renderLogin();

    await user.type(screen.getByPlaceholderText('Name'), 'tester');
    await user.type(screen.getByPlaceholderText('Password'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(
      await screen.findByRole('heading', { name: 'Dashboard page' })
    ).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/login$/),
      expect.objectContaining({ method: 'POST' })
    );
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body).toMatchObject({ name: 'tester', password: 'secret' });

    expect(localStorage.getItem('token')).toBe('jwt-token');
    expect(setUser).toHaveBeenCalledWith(apiUser);
  });

  test('shows the backend error for invalid credentials and stays on login', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(401, { error: 'Invalid credentials' }));

    const { setUser, user } = renderLogin();

    await user.type(screen.getByPlaceholderText('Name'), 'tester');
    await user.type(screen.getByPlaceholderText('Password'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
    expect(setUser).not.toHaveBeenCalled();
    expect(localStorage.getItem('token')).toBeNull();
    expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled();
  });

  test('shows a network error message when the request fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const { user } = renderLogin();

    await user.type(screen.getByPlaceholderText('Name'), 'tester');
    await user.type(screen.getByPlaceholderText('Password'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Network error. Please try again.'
    );
  });

  test('disables the submit button while the request is in flight', async () => {
    let resolveFetch;
    global.fetch = jest.fn(
      () => new Promise(resolve => {
        resolveFetch = resolve;
      })
    );

    const { user } = renderLogin();

    await user.type(screen.getByPlaceholderText('Name'), 'tester');
    await user.type(screen.getByPlaceholderText('Password'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Login' }));

    expect(screen.getByRole('button', { name: 'Please wait…' })).toBeDisabled();

    resolveFetch(jsonResponse(401, { error: 'Invalid credentials' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  test('registers a new account and returns to login with the name kept', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(201, { message: 'User registered successfully' }));

    const { user } = renderLogin();

    await user.click(screen.getByRole('button', { name: 'New user? Register' }));
    expect(screen.getByRole('heading', { name: 'Register' })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('Name'), 'newbie');
    await user.type(screen.getByPlaceholderText('Password'), 'pw');
    // The date input has no placeholder; find it by type.
    const dobInput = document.querySelector('input[name="dob"]');
    await user.type(dobInput, '1995-05-20');
    await user.type(screen.getByPlaceholderText('Place'), 'Chennai');

    await user.click(screen.getByRole('button', { name: 'Create Account' }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Account created successfully. Please log in.'
    );
    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Name')).toHaveValue('newbie');
    expect(screen.getByPlaceholderText('Password')).toHaveValue('');

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/register$/),
      expect.anything()
    );
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
      name: 'newbie',
      password: 'pw',
      dob: '1995-05-20',
      place: 'Chennai',
    });
  });

  test('shows the backend error when registration fails', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(400, { error: 'Username already taken' }));

    const { user } = renderLogin();

    await user.click(screen.getByRole('button', { name: 'New user? Register' }));
    await user.type(screen.getByPlaceholderText('Name'), 'taken');
    await user.type(screen.getByPlaceholderText('Password'), 'pw');
    await user.type(document.querySelector('input[name="dob"]'), '1995-05-20');
    await user.type(screen.getByPlaceholderText('Place'), 'Chennai');
    await user.click(screen.getByRole('button', { name: 'Create Account' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Username already taken');
    expect(screen.getByRole('heading', { name: 'Register' })).toBeInTheDocument();
  });

  test('switching between login and register clears the form and messages', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(401, { error: 'Invalid credentials' }));

    const { user } = renderLogin();

    await user.type(screen.getByPlaceholderText('Name'), 'tester');
    await user.type(screen.getByPlaceholderText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Login' }));
    await screen.findByRole('alert');

    await user.click(screen.getByRole('button', { name: 'New user? Register' }));

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText('Name')).toHaveValue('');
  });
});
