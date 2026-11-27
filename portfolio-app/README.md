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
| `REACT_APP_AI_API_URL` | Base URL of the AI service (`ai_service/`). Set in `.env.development` (`http://localhost:8001`). When it is not set, the assistant panel is hidden, so production builds don't show it until the AI service is deployed. |

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
│   ├── AssistantChat.js   # PPA Assistant chat panel on the Dashboard (help + "My data")
│   ├── dialogs/           # Profile, entity/transaction forms, transaction table
│   └── ui/                # Modal, DataTable, Button, SearchBar
├── services/
│   ├── api.js             # axios instance + all API calls
│   ├── assistantApi.js    # AI service client: /v1/ask, /v1/usage (same login token)
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

## PPA Assistant panel (RAG/AI phase, step 5, local only)

`components/AssistantChat.js` replaces the earlier `DummyChatbot` preview, which had canned replies, and keeps its look (`AssistantChat.css`, renamed from `Dummychatbot.css`).

- **Two modes.**
  - **Help** (default): PPA how-to and finance basics, with sources.
  - **My data**: a switch, off by default. When on, a notice explains that the question and the needed figures go to Groq, and that the assistant can only read data.
- **Every "My data" answer has "Figures used":** the tables it was based on, so the user can check the numbers.
- **Header line:** "47 of 50 left · resets 1:30 PM IST", from `/v1/usage`.
- **Errors:** the service's own message (busy for N seconds, daily limit, not reachable). A 401 logs the user out, like any Flask call.
- **One question at a time;** 500-character limit (matches the service).
- **Model text is never rendered as HTML.** A small formatter turns `**bold**` and `- ` bullets into React elements. Model output, or a transaction description it repeats, cannot inject markup; a test checks this.
- **Calls go straight from the browser to the AI service,** so its CORS allows `http://localhost:3000` (`AI_CORS_ORIGINS`).

*Update, November 26, 2026 (fine-tuning phase):*

- **Follow-ups:** in "My data" mode the last 3 questions and answers of that mode go with each new question (`buildHistory`, answers cut to 600 characters), so "what about all time?" works. The AI service does not store them.
- **Help hint:** when Help mode finds nothing, the answer adds "Asking about your own figures? Turn on My data above."
- **Figures:** "Figures used" also formats the new facts (largest, smallest, matched, groups).

*Update, November 26, 2026 (round 2):* each history answer now ends with the search it used ("Searched: …"), so follow-ups keep the same filters. The "My data" welcome message no longer appears twice (a StrictMode double-run of a state updater).

*Update, November 26, 2026 (round 4):* the id column of transaction tables is hidden (ids are for the assistant's "add up these rows" step). Picked answers show Counted and Not counted tables.

*Update, November 26, 2026 (round 6):* tables written by the model (`| a | b |` lines) are shown as real tables, built from React elements like bold and bullets, so cell text can never become markup.

*Update, November 26, 2026 (panel size and message box):* the panel is now about half the screen wide (up to 920px) and runs from just under the header to just above the chat button; before, it was 400 x 600, and a rule for screens 1800px and wider shrank it to 380 x 520. The message box is a growing text area: up to about 6 lines, then it scrolls. Enter sends and Shift+Enter adds a line. Checked at 1907 x 949: panel 915 x 759.

*Update, November 26, 2026 (usage line):* the header shows questions **and** the percentage of today's tokens left. With the per-user caps switched off for testing, it shows the percentage of Groq's free daily tokens left (shared by all users); the tooltip has the exact numbers.

*Update, November 27, 2026 (assistant on every page):* `AssistantChat` is rendered once in `App.js` for signed-in users, not in `Dashboard.js`, so it is available on every page and keeps the conversation while you move between pages; logging out clears it. `App.test.js` checks that it is shown on a signed-in page and not on the login page.

*Update, November 27, 2026 (assistant links):* help answers can end with "Click here" buttons. `services/assistantLinks.js` maps the AI service's action names to a fixed list of pages and forms. When an account is needed, the chat fetches the user's accounts live and asks which one. `hooks/useAssistantLink.js` lets the Credit Cards, Banks, Savings and Assets pages open the requested form (`?open=add|add-transaction|view-transactions|delete&id=…`) for one of their own loaded accounts, then clears the address. Page tests now render inside a `MemoryRouter`.

## Tests

There are 14 test suites (`*.test.js` next to the code they cover). The last local run (November 23, 2026) gave `201 passed`.

*Update, November 26, 2026 (panel size):* 16 suites, `226 passed`.

*Update, November 26, 2026 (round 6):* 16 suites, `225 passed`.

*Update, November 26, 2026 (round 4):* 16 suites, `224 passed`.

*Update, November 26, 2026 (round 2):* 16 suites, `223 passed`.

*Update, November 26, 2026:* 16 suites, `221 passed` (history, help hint, history builder, API history).

*Update, November 25, 2026:* 16 suites, `217 passed`. New: `AssistantChat.test.js` (11) and `assistantApi.test.js` (5), including a StrictMode regression test.

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
