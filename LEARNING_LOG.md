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

---

## Step 7: Video Analysis API — Submission & Processing Lifecycle

### 1. HTTP POST Method
- Unlike `GET` (which retrieves data without side effects), `POST` transmits payload data in the HTTP request body (`application/json`) to create or process server-side resources.
- `POST /api/videos/process` receives the client's URL payload securely in the request body rather than exposing it as URL query parameters.

### 2. Pydantic Validation & Data Integrity
- FastAPI leverages Pydantic models (`BaseModel`) for strict schema declaration, runtime type casting, and validation.
- `@field_validator` validates the URL scheme (HTTP/HTTPS) and structure before route handler execution, returning structured HTTP `422 Unprocessable Entity` responses automatically if invalid.

### 3. API Request and Response Models
- **Request Model (`VideoProcessRequest`)**: Defines the contract for incoming JSON payloads (`{ "url": string }`).
- **Response Model (`VideoProcessResponse`)**: Guarantees the output structure (`{ "status", "message", "video_url", "received_at", "video_id" }`), strips unexposed internal data, and auto-generates accurate OpenAPI/Swagger documentation.

### 4. Async / Await Lifecycle
- In React, asynchronous operations (`await fetch(...)`, `await response.json()`) allow network requests to resolve in the background without freezing the UI or browser thread.
- React components update UI state sequentially: `isSubmitting: true` $\rightarrow$ network await $\rightarrow$ `processedVideo: data` $\rightarrow$ `isSubmitting: false`.

### 5. Frontend-to-Backend Data Flow (POST)
1. **User Action**: User enters URL in `VideoInput` and submits the form.
2. **Client Validation**: Quick syntax/empty checks occur instantly in the browser.
3. **HTTP Dispatch**: `fetch('http://127.0.0.1:8000/api/videos/process', { method: 'POST', body: JSON.stringify({ url }) })`.
4. **Backend Processing**: FastAPI parses JSON body into `VideoProcessRequest`, validates URL, extracts `video_id`, and returns `VideoProcessResponse`.
5. **Client Response**: React receives JSON payload, clears loading spinner, and renders the success card with video details and timestamp.

### 6. Error Handling Strategy (Defense-in-Depth)
- **Client-Side**: Instant feedback for empty strings or invalid URL formats before sending network packets.
- **Server-Side**: Authoritative validation via Pydantic; catches malformed payloads or invalid protocols with descriptive 422 errors.
- **Network / Transport**: `try...catch` in React catches server downtime or offline states and displays user-friendly recovery instructions.

### 7. Interactive API Testing via Swagger UI (`/docs`)
- FastAPI auto-generates interactive OpenAPI documentation at `http://127.0.0.1:8000/docs`.
- Enables developers to test endpoints, inspect schemas, and verify response payloads directly in the browser without writing manual test scripts.

---

## Step 8: Video Metadata and Processing Foundation

### 1. Video Metadata
- **Definition**: Data about data. In VIDYORA AI, video metadata encapsulates identity, source, origin platform, status, and lifecycle timestamps for educational video resources.
- **Why it matters**: Before audio transcription or AI generation can begin, the system must establish an unambiguous entity contract representing the video.

### 2. Data Modeling & Separation of Concerns
- **Domain Decoupling**: Extracted data models out of route handler scripts (`main.py`) into a dedicated module (`models.py`). This keeps route definitions focused exclusively on HTTP transport logic, status codes, and error serialization.
- **Enums for Type Safety**:
  - `VideoPlatform`: Distinguishes `youtube`, `direct` (e.g. `.mp4`, `.webm`), and `unknown` educational sources.
  - `VideoProcessingStatus`: Constrains lifecycle values to verified string enumerations, preventing silent bugs caused by typos or ad-hoc strings.
- **Structured Models vs. Scattered Variables**: Grouping related video attributes into a unified `VideoMetadata` model guarantees consistent data shapes, automatic type conversion, and self-documenting API schemas.

### 3. Processing Lifecycle & State Machine
- **Lifecycle States**:
  - `SUBMITTED`: Initial URL intake from client.
  - `VALIDATING`: Syntactic, scheme, and accessibility checks actively executing.
  - `ACCEPTED`: Video URL validated, platform identified, and entity registered; queued for downstream processing.
  - `PROCESSING`: Downstream transcript extraction or AI analysis actively executing.
  - `COMPLETED`: Transcripts, structured study notes, and assessments successfully generated.
  - `FAILED`: Validation or processing error encountered.
- **Valid State Transitions**:
  ```text
  SUBMITTED ──> VALIDATING ──> ACCEPTED ──> PROCESSING ──> COMPLETED
                     │               │            │
                     └───> FAILED <──┴────────────┘
  ```
- **Truthful Status Reporting**: Because Step 8 implements metadata registration without background workers or LLM summarization yet, the endpoint truthfully reports `status = "accepted"`. It never claims "processing" or "completed" prematurely.

### 4. API Response Consistency & Backwards Compatibility
- **Consistent Envelope Pattern**: Standardized API response format (`{ status, message, video: VideoMetadata }`), allowing frontend clients to safely inspect entity metadata.
- **Computed Fields (`@computed_field`)**: Added backward-compatible properties (`video_url`, `video_id`, `received_at`) to `VideoProcessResponse` in Pydantic v2. This ensures legacy clients continue working seamlessly while newer clients leverage the nested metadata structure.

### 5. Architectural Decisions & Deferrals
- **No Premature Database**: State is kept in-memory/returned directly to the caller during these foundational phases. Persisting to a database before the schema stabilizes causes unnecessary migration overhead.
- **No Fake Processing Progress**: Simulating false progress bars or fake background delays creates deceptive behavior and fragile tests; progress states must reflect real server-side pipeline tasks.
- **Deterministic ID Generation**: YouTube URLs preserve their native 11-character identifiers (`v=...`, `youtu.be/...`). Direct video streams and generic links receive deterministic SHA-256 content hashes, avoiding collisions.

### 6. Future Database Considerations
- When persisting videos in later steps (e.g., PostgreSQL / SQLite), `VideoMetadata` maps directly to a relational table:
  - `id`: Primary key (`VARCHAR(64)`).
  - `url`: Indexed unique or non-unique source URL (`TEXT`).
  - `platform`: Enum column (`VARCHAR(20)`).
  - `status`: Enum column (`VARCHAR(20)`).
  - `created_at` / `updated_at`: `TIMESTAMP WITH TIME ZONE`.
  - `error_message`: Nullable text for post-mortem debugging.
