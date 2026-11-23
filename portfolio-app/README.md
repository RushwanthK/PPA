# PPA Frontend (`portfolio-app`)

React single-page app for the Personal Portfolio Application. It talks to the Flask backend over a JSON REST API. See the root `README.md`, `ARCHITECTURE.md` and `PROJECT_STATUS.md` for the whole system.

- **Build tooling:** Create React App (`react-scripts` 5)
- **UI:** React 19, React Router 7, MUI, Recharts
- **HTTP:** axios (`src/services/api.js`)
- **Tests:** Jest + React Testing Library (`react-scripts test`)
- **Hosting:** Vercel, which deploys automatically on every push. Anything pushed goes live, so keep the frontend compatible with the backend version that is currently deployed on Render (Render is deployed manually).

## Configuration

| Variable | Purpose |
|---|---|
| `REACT_APP_API_URL` | Base URL of the Flask backend |

`.env.development` is used by `npm start`, and `.env.production` by `npm run build`. CRA bakes `REACT_APP_*` values into the bundle at build time, so they are public. Never put secrets in them.

## Scripts

Run these from `portfolio-app/`.

```bash
npm ci                          # install exactly what package-lock.json specifies
npm start                       # dev server on http://localhost:3000
npm test                        # Jest in watch mode
npm test -- --watchAll=false    # run every test once (what CI does, with CI=true)
npm run build                   # production build into build/
```

## Structure

```text
src/
├── App.js                 # routes, layout, navigation
├── AuthContext.js         # current user + token, login/logout, /me check
├── pages/                 # Dashboard, Banks, Savings, Assets, Credit Cards, Login
├── components/
│   ├── dialogs/           # Profile, entity/transaction forms, transaction table
│   └── ui/                # Modal, DataTable, Button, SearchBar
├── services/
│   ├── api.js             # axios instance + all API calls
│   ├── authEvents.js      # app-wide "session expired" event (raised on 401)
│   └── backendStatus.js   # tracks slow "backend waking up" requests (Render cold start)
└── setupTests.js          # global Jest setup
```

## Authentication

- The JWT returned by `/login` is stored in `localStorage` and sent as `Authorization: Bearer <token>` by the axios interceptor in `api.js`.
- Any **401** reply logs the user out. The backend returns 401 for every token problem: missing, expired, revoked, bad signature or malformed.
- Requests do **not** send cookies (`withCredentials` was removed). The backend no longer allows cross-site credentials, so do not add it back.
- **Logout** calls `POST /logout` to revoke the token on the server (without waiting for it) and then clears local state.
- **Log out of all devices** (Profile dialog) calls `POST /logout-all` and waits for it, showing an error if it fails.
- **Changing the password** requires the current password. The backend ends all other sessions and returns a new `token`, which the Profile dialog stores so this device stays logged in. A wrong current password returns 403, not 401, so the user is not logged out for a typo.
- Login, registration and password change are rate limited. A 429 reply has an `error` message (with the wait time) that the UI displays as-is.

Planned later: short-lived access tokens with refresh tokens, and possibly moving the token out of `localStorage`.

## Tests

There are 14 test suites (`*.test.js` next to the code they cover). The last local run (November 23, 2026) gave `201 passed`.

- **Pages:** Login, Dashboard, Banks, Savings, Assets, Credit Cards
- **Components:** Modal, DataTable, delete confirmation, transaction table, Profile dialog
- **Services:** `api.js` (token header, 401 logout, session helpers) and `backendStatus.js`
- **App:** login/dashboard routing, session restore via `/me`, logout on 401 or a session-expired event

Conventions:

- Test what the user sees and which API call is made, not component internals.
- Mock `services/api` at the module boundary; don't make real network calls.
- `setupTests.js` loads `@testing-library/jest-dom` and adds the jsdom polyfills (`TextEncoder`/`TextDecoder`, `matchMedia`, `ResizeObserver`). It also clears `localStorage` after each test.
- The `jest.moduleNameMapper` entries in `package.json` point axios and react-router v7 at builds CRA's Jest can load. Check them after upgrading either package.

GitHub Actions (`.github/workflows/ci.yml`) runs `npm ci`, then the tests with `CI=true`, then `npm run build`. A failing test fails the workflow.

## Dependency Audit

`npm audit` still reports advisories in Create React App's build tooling (webpack dev server, svgo, etc.). Those packages run only at build time and are not part of the browser bundle. No runtime dependency is flagged. Fully removing them means migrating off CRA (for example to Vite), which is tracked as separate future work.

## Deploy Notes

- Vercel builds with `npm run build` on every push.
- When a change needs a new backend endpoint or response field, deploy the backend first, or make the frontend tolerate the old backend. When the backend removes something the old frontend relies on, push the frontend first. For the Phase 3 changes the order is: migration, then push (frontend), then backend deploy on Render.
- A Content-Security-Policy for the site (for example via `vercel.json`) has not been added yet.
