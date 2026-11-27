import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import App from './App';
import { notifySessionExpired } from './services/authEvents';

// Replace the heavy, API-driven pages with light stand-ins. These tests are
// about routing and authentication behavior, not the page contents.
jest.mock('./pages/Dashboard', () => () => <h1>Dashboard page</h1>);
jest.mock('./pages/Assets', () => () => <h1>Assets page</h1>);
jest.mock('./pages/savings', () => () => <h1>Savings page</h1>);
jest.mock('./pages/creditcard', () => () => <h1>Credit cards page</h1>);
jest.mock('./pages/bank', () => () => <h1>Banks page</h1>);
jest.mock('./components/dialogs/ProfileDialog', () => () => null);
jest.mock('./components/AssistantChat', () => () => <aside aria-label="PPA Assistant" />);

const TEST_USER = {
  id: 1,
  name: 'tester',
  dob: '1990-01-01',
  place: 'Chennai',
  age: 35,
};

const renderApp = (initialPath = '/') =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>
  );

const mockFetchResponse = (status, body) =>
  jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });

describe('App routing and session handling', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  test('shows the login page at "/" when no one is logged in', async () => {
    renderApp('/');

    expect(
      await screen.findByRole('heading', { name: 'Login' })
    ).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  test.each(['/dashboard', '/assets', '/savings', '/creditcard', '/bank'])(
    'redirects the private route %s to the login page when logged out',
    async path => {
      renderApp(path);

      expect(
        await screen.findByRole('heading', { name: 'Login' })
      ).toBeInTheDocument();
    }
  );

  test('restores a stored session via /me and shows the dashboard', async () => {
    localStorage.setItem('token', 'stored-token');
    global.fetch = mockFetchResponse(200, TEST_USER);

    renderApp('/');

    expect(
      await screen.findByRole('heading', { name: 'Dashboard page' })
    ).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/me$/),
      expect.objectContaining({
        headers: { Authorization: 'Bearer stored-token' },
      })
    );

    // The sidebar is aria-hidden until the menu is opened.
    const nav = screen.getByRole('navigation', {
      name: 'Main navigation',
      hidden: true,
    });
    ['Overview', 'Assets', 'Savings', 'Credit Cards', 'Banks'].forEach(label => {
      expect(nav).toHaveTextContent(label);
    });
  });

  test('the assistant is on every signed-in page and not on the login page', async () => {
    renderApp('/');
    await screen.findByRole('heading', { name: 'Login' });
    expect(screen.queryByRole('complementary', { name: 'PPA Assistant' })).not.toBeInTheDocument();

    localStorage.setItem('token', 'stored-token');
    global.fetch = mockFetchResponse(200, TEST_USER);
    renderApp('/assets');
    expect(await screen.findByRole('heading', { name: 'Assets page' })).toBeInTheDocument();
    expect(await screen.findByRole('complementary', { name: 'PPA Assistant' })).toBeInTheDocument();
  });

  test('clears an expired stored token (401 from /me) and shows login', async () => {
    localStorage.setItem('token', 'expired-token');
    global.fetch = mockFetchResponse(401, { msg: 'Token has expired' });

    renderApp('/dashboard');

    expect(
      await screen.findByRole('heading', { name: 'Login' })
    ).toBeInTheDocument();
    expect(localStorage.getItem('token')).toBeNull();
  });

  test('does not log the user out when /me fails with a server error', async () => {
    localStorage.setItem('token', 'stored-token');
    global.fetch = mockFetchResponse(500, { error: 'boom' });
    jest.spyOn(console, 'error').mockImplementation(() => {});

    renderApp('/');

    expect(
      await screen.findByRole('heading', { name: 'Login' })
    ).toBeInTheDocument();
    // A non-auth failure must not wipe the stored token.
    expect(localStorage.getItem('token')).toBe('stored-token');
  });

  test('navigates between private pages using the sidebar', async () => {
    localStorage.setItem('token', 'stored-token');
    global.fetch = mockFetchResponse(200, TEST_USER);
    const user = userEvent.setup();

    renderApp('/dashboard');
    await screen.findByRole('heading', { name: 'Dashboard page' });

    // The sidebar links are only focusable once the menu is opened.
    await user.click(screen.getByRole('button', { name: 'Open navigation menu' }));
    await user.click(screen.getByRole('link', { name: 'Banks' }));

    expect(
      await screen.findByRole('heading', { name: 'Banks page' })
    ).toBeInTheDocument();
  });

  test('logs the user out when a session-expired event is raised', async () => {
    localStorage.setItem('token', 'stored-token');
    global.fetch = mockFetchResponse(200, TEST_USER);

    renderApp('/dashboard');
    await screen.findByRole('heading', { name: 'Dashboard page' });

    act(() => {
      notifySessionExpired();
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
    });
    expect(localStorage.getItem('token')).toBeNull();
  });
});
