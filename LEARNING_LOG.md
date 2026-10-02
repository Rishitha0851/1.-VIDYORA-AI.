# VIDYORA AI — Learning Log

A concise record of core architectural concepts and mechanisms learned throughout the development phases.

---

## Phase 3: Frontend–Backend Integration & Health Check

### 1. Fetch API
- The browser-native `fetch()` function sends asynchronous HTTP requests over the network and returns a `Promise` that resolves to a `Response` object.
- Unlike third-party libraries, `fetch()` requires no external dependencies and handles network operations natively.

### 2. `useEffect()` Hook
- Synchronizes React components with external systems (such as network requests, subscriptions, or DOM events).
- In this phase, `useEffect` triggers the initial backend health check as soon as the `BackendStatus` component mounts onto the screen.

### 3. Cross-Origin Resource Sharing (CORS)
- Browsers enforce the Same-Origin Policy, preventing JavaScript on `http://127.0.0.1:5173` from accessing resources on `http://127.0.0.1:8000` unless permitted.
- Adding `CORSMiddleware` in FastAPI explicitly allows requests originating from the frontend dev server, preventing `CORS header missing` browser errors.

### 4. HTTP Request & Response Cycle
- **Client (Frontend)**: Initiates an HTTP `GET` request to `http://127.0.0.1:8000/health`.
- **Server (Backend)**: Receives the request, processes it, and returns an HTTP `200 OK` status with JSON payload `{ "status": "healthy", "service": "VIDYORA AI Backend", "version": "0.1.0" }`.

### 5. Managing Loading, Success, and Error States
- **Loading**: Indicates network activity is in progress (`status: 'loading'`), keeping the user informed with an animated indicator and disabling repetitive clicks.
- **Success**: Confirms server availability (`status: 'success'`) and displays returned metadata (`version`, `service`).
- **Error**: Catches server downtime or network disconnects (`status: 'error'`), presenting a user-friendly error message alongside a manual **Retry** action.

### 6. End-to-End Data Flow
1. **Trigger**: Component mounts $\rightarrow$ `useEffect` invokes `checkConnection()`.
2. **Request**: `fetch('http://127.0.0.1:8000/health')` sends asynchronous GET request.
3. **Validation**: `response.ok` checks whether HTTP status is in the 200–299 range.
4. **Parsing**: `response.json()` parses the JSON body into a TypeScript-typed object.
5. **Re-render**: `setStatus('success')` and `setData(result)` update React state, prompting an automatic and safe UI re-render.
