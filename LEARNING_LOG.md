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

---

## Step 9: Transcript Extraction Foundation

### 1. The Anatomy of Video Transcripts
- **What is a Transcript?**: Spoken dialogue and lecture content translated into text synchronized with time.
- **Caption Tracks in YouTube**:
  - **Manual Captions**: Uploaded by creators or educators, typically punctuation-accurate and terminology-precise.
  - **Automatic Speech Recognition (ASR)**: Machine-generated captions provided by YouTube's speech models. Often lacks punctuation or proper casing but captures spoken words accurately.
- **Timed Text Streams**: YouTube delivers captions via specialized formats such as `json3` or `vtt`, containing individual events with `tStartMs` (start timestamp in milliseconds) and `dDurationMs` (duration in milliseconds).

### 2. Why Segment-Level Timestamps Matter for Educational AI
- **Source Grounding & Anti-Hallucination**: LLMs can summarize concepts, but hallucinations remain a risk in education. By preserving time-indexed segments (`start`, `duration`), VIDYORA AI can cite exact lecture timestamps in answers:
  > *"Backpropagation is explained at [04:12](https://youtu.be/...&t=252s)."*
- **Interactive Player Seeking**: Clicking a study note, glossary item, or quiz question in the frontend can command the embedded video player to jump directly to the exact second where the concept was taught.
- **Semantic Chunking**: Instead of arbitrarily splitting text at character counts, later AI embedding pipelines can group full sentences by timestamp boundaries (e.g., 2-to-3 minute conceptual sections).

### 3. Architecture: Service Layer Pattern
- **Decoupling Business Logic from Web Transports**:
  - Scraping, parsing, and external API requests must never pollute route handlers in `main.py`.
  - Created `backend/services/transcript_service.py` to isolate external YouTube retrieval, error translation, and data structuring.
  - Route handlers remain thin: they validate input, invoke the service, and serialize standard response envelopes.
- **Resilient Mobile Client Emulation**:
  - Modern YouTube endpoints often enforce aggressive bot-blocking (HTTP 429) against desktop automated scripts.
  - By using `yt-dlp` configured with mobile player clients (`android`, `ios`), the backend accesses official caption tracks reliably without requiring user cookies or API keys.

### 4. Domain Data Modeling
- **`TranscriptSegment`**: Atom of spoken content (`text`, `start`, `duration`).
- **`VideoTranscript`**: Entity holding continuous `full_text`, ordered `segments`, `language`, `is_generated` flag, and `segment_count`.
- **`VideoMetadata` Integration**: Nested within the video metadata contract, populating real video title and transcript data when extraction succeeds.

### 5. Truthful State Machine Transitions
- If captions are found and parsed:
  - `status`: Transitions from `ACCEPTED` to `COMPLETED`.
  - `video.title`: Populated with real video title from YouTube.
  - `video.transcript`: Attached to the metadata response.
- If captions are disabled, absent, or video is private:
  - `status`: Transitions to `FAILED`.
  - `video.error_message`: Explains the exact reason (`"No transcript or captions available for this video."` or `"This video is unavailable, private, or does not exist."`).
  - Server returns HTTP 200 with structured failure status rather than unhandled 500 crashes.

---

## Step 10: Transcript Cleaning, Chunking, and Source Preservation

### 1. The Need for Transcript Cleaning & Normalization
- **Raw Subtitle Artifacts**:
  - Subtitles are peppered with non-verbal sound tags: `[Music]`, `[Applause]`, `[Laughter]`, `(cheering)`, `♪`, etc.
  - Feeding raw noise into LLMs wastes valuable context window tokens and degrades summary/quiz quality.
  - Irregular whitespace (tabs, consecutive newlines, non-breaking spaces) and curly quotes create inconsistent string matching.
- **Normalization Pipeline**:
  - Regular expressions strip noise markers without corrupting actual spoken words.
  - Collapses consecutive whitespace into single spaces and trims edges.
  - Empty or purely non-speech segments are safely pruned while preserving original time codes for real dialogue.

### 2. The Chunking Dilemma in Educational AI
- **Why Not Use Raw Segments Directly?**:
  - Individual caption segments are too brief (often 1–3 seconds, 5–15 words).
  - Embedding a 5-word snippet produces sparse, semantically weak vector embeddings that fail similarity search.
- **Why Not Use the Entire Transcript as One Block?**:
  - Slicing a 40-minute lecture into a single block overflows context windows or prevents precise retrieval.
  - Destroys temporal grounding: students cannot pinpoint *where* in the video a concept was explained.
- **The Contextual Chunking Solution**:
  - Group contiguous segments into cohesive paragraphs (~150–250 words / ~60–120 seconds).
  - Keeps conceptual thoughts intact while preserving exact start and end timestamps.

### 3. Deterministic Chunk Boundary Strategy
- **Sentence-Aware Grouping**:
  - Chunk boundaries prefer natural sentence endings (`.`, `?`, `!`, `."`, etc.) when approaching target word counts (150–250 words).
  - Avoids cutting off an instructor mid-sentence.
- **Guardrails Against Runaway Chunks**:
  - Automatic Speech Recognition (ASR) transcripts frequently omit punctuation.
  - If punctuation is completely missing, strict upper limits (`max_words=350`, `max_duration=180s`) force a boundary, preventing unbounded chunks.
- **Whole-Segment Invariance**:
  - Never cuts through an atomic segment; segments are assigned to chunks as intact units.

### 4. Bidirectional Source Grounding
- Each `TranscriptChunk` stores:
  - `start_time`: Start time in seconds (inherited from first segment).
  - `end_time`: End time in seconds (start + duration of last segment).
  - `duration`: `round(end_time - start_time, 2)`.
  - `segment_start_index` & `segment_end_index`: Zero-based, inclusive indices into `cleaned_segments`.
- This enables **bidirectional navigation**:
  - Chunk $\rightarrow$ Video Player: Jump video to `chunk.start_time`.
  - Chunk $\rightarrow$ Detailed Subtitles: Expand all segments between `segment_start_index` and `segment_end_index`.

### 5. Architectural Compatibility & Non-Breaking Design
- **Dual-Level Representation**:
  - `segments`: Raw source caption track (100% backward compatible for legacy consumers).
  - `cleaned_segments`: Sanitized speech segments.
  - `chunks`: High-level semantic blocks ready for future vector embeddings and LLM prompts.
- **No Premature Infrastructure**:
  - Chunks are generated deterministically in-memory without requiring heavy databases (PostgreSQL/pgvector) or cloud embedding APIs at this stage.

---

## Step 11: AI-Powered Video Summarization and Structured Notes Generation

### 1. What is an LLM and How Does It Differ From Conventional Backend Logic?
- **Conventional Backend Code**:
  - Deterministic and rule-based: given input $X$, code follows explicit logical branches (`if/else`, loops, regex) to produce identical output $Y$ every time.
  - Great for syntax validation, arithmetic, timestamp math, and structured data storage.
- **Large Language Models (LLMs)**:
  - Probabilistic neural networks trained on massive corpora of text code to predict the most statistically probable next token given a preceding context window.
  - They operate through **parametric memory** (weights learned during training) rather than relational database lookups.
  - LLMs excel at synthesis, linguistic simplification ("Explain Like I'm 5"), thematic categorization, and extracting structured hierarchies from unstructured text.
  - **The Risk**: Because they predict plausible text, they can "hallucinate" (confidently generate false facts or fabricate details that sound convincing). Preventing this requires strict **source grounding**.

### 2. How the Gemini API & SDK Work
- **The Official `google-genai` SDK**:
  - Google's unified Python client for the Gemini Developer API (`from google import genai; from google.genai import types`).
  - Replaces legacy libraries with unified client initialization: `client = genai.Client(api_key=...)`.
- **Model Choice (`gemini-2.5-flash`)**:
  - Balances high reasoning quality, massive token context windows, low latency, and cost efficiency for real-time educational synthesis.
  - Configurable via `GEMINI_MODEL` environment variable to support seamless upgrades (e.g. `gemini-2.0-flash`, `gemini-1.5-flash`).

### 3. API Security & Environment Variables
- **Secrets Isolation**:
  - API keys must never appear in frontend code, client-side bundles, or Git repositories.
  - Loaded server-side using `python-dotenv` into `config.py`.
  - `.gitignore` explicitly ignores `.env` and `.env.*` while keeping `.env.example` committed as a documentation contract.
  - Missing credentials trigger a graceful `503 Service Unavailable` with actionable guidance instead of crashing the server.

### 4. Prompt Engineering & Strict Source Grounding
- **The Grounding Dilemma**:
  - An educational assistant must never teach misconceptions or fabricate concepts that an instructor never said.
- **Prompt Architecture**:
  - **System Instructions**: Establishes immutable persona and guardrails:
    - *"Base all explanations EXCLUSIVELY on the provided transcript text."*
    - *"Do NOT invent or extrapolate facts absent from the spoken text."*
    - *"You do not have visual access to the video stream. Only reference what was spoken."*
  - **Contextual Chunk Injection**:
    - Each transcript chunk is injected with its identifier, human-readable start/end time, and exact second offsets (`[chunk_001 | 01:14 - 02:45 | start_seconds: 74.2]`).
  - **Temporal Anchoring**:
    - Prompts instruct the model to cite the exact `start_time` of the chunk where a concept was introduced.
  - **Post-Generation Timestamp Sanitization**:
    - Backend validates that all generated timestamps fall within the video's actual duration bounds ($0.0 \le t \le \text{max\_time} + 2.0$), clamping any drift.

### 5. Structured Output & Double-Layer Pydantic Validation
- **JSON Schema Enforcement via Gemini**:
  - Using `types.GenerateContentConfig(response_mime_type="application/json", response_schema=VideoSummary)`, Gemini constrains its output decoding to valid JSON matching the exact schema definition.
- **Double-Layer Validation**:
  1. **Provider level**: Gemini's decoder forces JSON grammar and schema fields.
  2. **Application level**: `VideoSummary.model_validate_json(response.text)` parses and verifies types, field presence, and executes custom validators (e.g. non-negative timestamps).

### 6. Async API Calls, Timeouts, and Error Handling
- **Domain Exception Hierarchy**:
  - `GeminiConfigurationError` $\rightarrow$ HTTP 503 (missing or invalid API key).
  - `GeminiRateLimitError` $\rightarrow$ HTTP 429 (quota or concurrency limit exceeded).
  - `GeminiTimeoutError` $\rightarrow$ HTTP 504 (upstream network or inference timeout).
  - `GeminiValidationError` $\rightarrow$ HTTP 502 (malformed response or empty payload).
- Dedicated FastAPI exception handler catches `GeminiServiceError` and preserves CORS headers while returning structured diagnostic messages to the frontend.

### 7. End-to-End System Data Flow
```
User clicks "Generate Summary" / "Generate Notes"
         │
         ▼
Frontend (App.tsx): Validates chunks exist in local state
         │
         ▼ (HTTP POST /api/ai/summary or /api/ai/notes)
FastAPI Backend (main.py): Validates GenerateSummaryRequest Pydantic model
         │
         ▼
Gemini Service (gemini_service.py):
  1. Fetches API key from config.py / .env
  2. Formats chunks with time bounds into grounded prompt
  3. Calls google-genai Client with VideoSummary/StructuredNotes response_schema
  4. Validates returned JSON via Pydantic model
  5. Sanitizes source timestamps against video boundaries
         │
         ▼ (HTTP 200 OK with SummaryResponse/NotesResponse)
Frontend (App.tsx):
  1. Updates summaryData / notesData reactive state
  2. Activates tab ('summary' or 'notes')
  3. Renders SummaryView (Overview, ELI5 callout, concepts, takeaways, timestamps)
     or NotesView (Outline sections, terminology glossary, examples, takeaways)
```
---

## Step 13 (Phases 1 & 2): Persistence Foundation & Relational Database Architecture

### 1. Why Persistence is Necessary
- In-memory data structures (like dictionaries) live exclusively in process RAM. When the backend service reboots, crashes, or scales to multiple worker processes, all volatile state vanishes.
- Persistence commits application state to non-volatile secondary storage (disk/SSD), guaranteeing data durability, historical auditability, multi-session learner tracking, and cross-instance data sharing.

### 2. PostgreSQL vs. In-Memory Storage
- **PostgreSQL**: An enterprise-grade, ACID-compliant (Atomicity, Consistency, Isolation, Durability) relational database system. It supports transactional integrity, relational constraints, complex joins, secondary indexes, concurrent queries, and crash recovery.
- **In-Memory Storage (RAM)**: Ultra-fast ($O(1)$ dictionary lookups) but volatile, process-bound, non-relational, and strictly bounded by physical RAM capacity.

### 3. Object-Relational Mapping (ORM) Concept
- ORMs (such as SQLAlchemy) bridge the impedance mismatch between object-oriented programming (Python classes and instances) and relational algebra (tables, rows, and SQL statements).
- Developers manipulate strongly-typed Python objects (`user = User(email=...)`) while the ORM transparently generates dialect-specific SQL (`INSERT INTO users ...`), maps result sets back to objects, and tracks state changes in an active Unit of Work.

### 4. Pydantic Model vs. ORM Model (Separation of Concerns)
- **Pydantic Models (`BaseModel`)**: Focus on **data validation and serialization** at the application boundary (HTTP request parsing, type coercion, field constraints, JSON response generation). They are stateless and database-agnostic.
- **ORM Models (`DeclarativeBase`)**: Focus on **data persistence and relational mapping** (defining tables, primary/foreign keys, cascade behaviors, and database session tracking).
- Conflating the two creates tight coupling, leaks internal database structures to API consumers, and complicates versioning.

### 5. Primary Key
- A unique identifier assigned to every row in a table. It guarantees entity identity, enforces non-nullability, and establishes the clustered or primary B-tree index for rapid point lookups.
- VIDYORA AI uses UUID strings (`String(36)`) for generated entities and canonical video tokens (`String(64)`) for videos.

### 6. Foreign Key
- A referential constraint linking a column in a child table to the primary key of a parent table.
- Enforces referential integrity at the database engine level, rejecting orphaned records or invalid references (e.g. creating a transcript for a non-existent video).

### 7. One-to-Many Relationship
- A relational cardinality where a single record in the parent table associates with zero, one, or multiple records in a child table (e.g. one `Video` has many `KnowledgeChunk`s; one `Quiz` has many `QuizQuestion`s).
- Implemented via a foreign key in the child table pointing to the parent table's primary key.

### 8. Database Session (Unit of Work)
- In SQLAlchemy, a `Session` manages database transactions, tracks modifications to loaded ORM instances, and flushes changes to the database within a coherent transactional boundary.
- In FastAPI, `get_db()` yields a session per HTTP request and closes it in a `finally` block, preventing connection leaks.

### 9. Connection Pooling
- Establishing a fresh TCP connection and SSL handshake with PostgreSQL is computationally expensive (latency overhead).
- A connection pool (configured with `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`) maintains an active pool of warmed connections that requests can borrow and return instantly, drastically increasing throughput.

### 10. Database Migration Concept
- Software evolves incrementally; schemas must evolve alongside it.
- A migration is a version-controlled, reproducible Python script containing structured `upgrade()` and `downgrade()` steps that transition a database schema from revision $N$ to $N+1$ without data loss.

### 11. Alembic
- The standard database migration tool for SQLAlchemy.
- Inspects `Base.metadata`, generates deterministic migration files, tracks applied migrations via the `alembic_version` table in PostgreSQL, and supports offline SQL script generation.

### 12. Why Migrations are Preferable to Blindly Creating Tables (`create_all`)
- `create_all()` only creates tables if they do not exist; it **cannot** alter columns, add foreign keys, rename fields, or apply indexes to existing production databases without dropping tables and destroying data.
- Migrations allow non-destructive, audited, and rollback-capable schema transformations across dev, staging, and production environments.

### 13. Why Database Credentials Belong in Environment Variables
- Database credentials (host, username, password) are sensitive secrets. Hardcoding them risks leaking credentials in public repositories, enables unauthorized access, and prevents deploying the same codebase across different environments (local, testing, cloud).
- Configured via `.env` (ignored by Git) and exposed with masking in diagnostic utilities.

### 14. Why `QUIZ_STORE` is Still Temporarily Retained
- In Step 13 Phases 1 & 2, the goal was building and verifying the persistence foundation without introducing breaking changes or regressions to existing API contracts.
- Keeping `QUIZ_STORE` active in memory guaranteed that existing quiz and flashcard endpoints passed all tests and client interactions without interruption while the database schema and migration pipeline were established.

---

## Step 13 (Phase 3): Full Persistence Integration & Database-Backed Workflows

### 1. Database-Backed Architecture
- Moving from volatile RAM to durable PostgreSQL creates a production-grade 5-layer separation of concerns:
  ```text
  React Client (HTTP/UI)
        ↓
  FastAPI Endpoints (HTTP serialization, Pydantic validation)
        ↓
  Service Layer (Business logic, prompt construction, Gemini AI generation)
        ↓
  Repository Layer (Data access, queries, transactions, rollbacks)
        ↓
  SQLAlchemy ORM Models (PostgreSQL tables, relations, indexes, constraints)
  ```

### 2. Transaction Boundaries, Commit, and Rollback
- A transaction ensures all-or-nothing execution (Atomicity).
- When persisting an educational video, four related entities must be written: `Video`, `VideoTranscript`, `TranscriptSegment`s, and `KnowledgeChunk`s.
- By wrapping these operations within a transaction boundary (`db.commit()`), any failure during chunking or segment writing triggers a complete `db.rollback()`. This guarantees the database is never left in a corrupted state (such as a Video without a transcript or chunks without segments).

### 3. Idempotency & Duplicate Handling
- Idempotency ensures that performing the same operation multiple times produces the exact same state as performing it once.
- Submitting the same YouTube video URL multiple times should not crash with a unique constraint error or create duplicate video records.
- `VideoRepository.save_processed_video` detects existing videos by canonical `video_id`, updates metadata in place, and cleanly flushes old transcripts/chunks before attaching the newly extracted ones.

### 4. Relational Integrity & Foreign Keys
- Foreign keys establish referential constraints enforced by PostgreSQL at the engine level.
- Cascade deletions (`ondelete="CASCADE"`) guarantee that removing a `Video` automatically cleans up its child `VideoTranscript`, `KnowledgeChunk`s, `Quiz`zes, and `FlashcardDeck`s.
- `ondelete="SET NULL"` preserves child assessments (`QuizQuestion`, `Flashcard`) if individual chunks are reorganized or re-indexed.

### 5. Why In-Memory Storage (`QUIZ_STORE`) is Insufficient
- Storing active quizzes in a Python dictionary (`QUIZ_STORE = {}`) means restarting the backend server instantly wipes all active quiz sessions and learner attempts.
- Persisting quizzes, questions, and attempts in PostgreSQL guarantees durability: learners can answer and evaluate quizzes even across backend reboots, deployments, and process restarts.

### 6. Quiz Answer Security & Deterministic Grading
- **Security**: The Gemini-generated answer key (`correct_answer`) and rationale (`explanation`) are written directly to PostgreSQL `quiz_questions` records. The client response (`QuizClientView`) strips both fields, preventing cheat inspection in browser dev tools.
- **Deterministic Grading**: When the learner submits answers, the backend grades them strictly against the database-stored answer key using deterministic Python logic. No additional LLM calls are made, guaranteeing consistent, non-hallucinatory grading with zero token costs and zero latency fluctuations.

### 7. Backend-Only Secret Discipline
- Database passwords and connection URLs remain strictly backend-only within `.env`.
- Frontend code only communicates with FastAPI endpoints over HTTP JSON contracts, guaranteeing that internal database credentials and connection topology are never exposed to the client browser.

---

## Step 13 (Phase 4): Learner History & Persistent Read APIs

### 1. HTTP GET vs POST Semantics
- **`POST` (State Mutation / Heavy Processing)**:
  - Used for submitting new video URLs (`POST /api/videos/process`), invoking Gemini AI generation (`POST /api/ai/quiz`, `POST /api/ai/summary`), or submitting quiz answers (`POST /api/ai/quiz/evaluate`).
  - Semantically implies creating or altering server state or executing non-idempotent computational pipelines.
- **`GET` (Safe, Idempotent Read Operations)**:
  - Used for retrieving stored video collections (`GET /api/videos`), restoring a video workspace (`GET /api/videos/{video_id}`), and inspecting learner history (`GET /api/quizzes/{quiz_id}/attempts`).
  - According to HTTP/1.1 RFC 9110, `GET` operations are **safe** (do not alter server state) and **idempotent** (repeating the request yields identical results without side effects).

### 2. The Persistent Read Principle: Read from DB, Don't Regenerate
- In production full-stack systems, previously processed educational resources must be reusable without repeating expensive operations.
- Calling external YouTube extraction or LLM APIs every time a user revisits a lecture introduces:
  1. **Latency**: LLM inference takes 2–8 seconds; PostgreSQL reads take 5–25 milliseconds (~100x faster).
  2. **Financial Cost**: Re-invoking LLM APIs consumes token quotas and incurs monetary costs.
  3. **Inconsistency**: LLMs are probabilistic; regenerating a quiz or summary introduces subtle drift in wording.
  4. **Fragility**: External rate limits or temporary third-party API outages break the learner's experience.
- By storing videos, transcripts, chunks, quizzes, and decks in PostgreSQL, reload operations read directly from the database with zero external dependencies.

### 3. Service / Repository Read Architecture
- **API Route Layer (`main.py`)**:
  - Handles HTTP status codes, query/path parameter parsing, and response serialization.
- **Service Layer (`video_service.py`, `quiz_service.py`)**:
  - Enforces domain rules, aggregates multiple repository models, sanitizes entities into client-facing schemas, and manages business logic.
- **Repository Layer (`video_repository.py`, `quiz_repository.py`)**:
  - Manages database interactions, writes clean SQL/ORM queries, manages loading options, and safeguards transaction boundaries.
- **ORM Models (`db/models.py`) $\rightarrow$ Pydantic Schemas (`models.py`)**:
  - Raw SQLAlchemy objects are never returned directly to the browser.
  - Conversion layers strictly project and sanitize ORM entities into type-safe Pydantic contracts, ensuring internal fields (such as quiz answer keys) are never exposed.

### 4. Relationship Loading Strategies & The N+1 Query Problem
- **The N+1 Query Problem**:
  - Occurs when loading a parent entity (e.g. 1 Video) and then lazily loading its child relationships (e.g. N chunks, N segments, N quiz questions) in separate queries inside a loop.
  - Squeezing out 1 + N queries turns a single API call into hundreds of round-trips over the database socket, killing performance.
- **Cartesian Product Explosion with Uncontrolled `joinedload`**:
  - Using `joinedload` on multiple one-to-many collections (e.g., joining 572 segments $\times$ 16 chunks) causes SQL to produce a massive Cartesian product ($572 \times 16 = 9,152$ duplicate rows transferred over the wire).
- **The `selectinload` Solution**:
  - `joinedload` is used strictly for 1-to-1 relationships (`Video.transcript`).
  - `selectinload` is used for 1-to-many collections (`VideoTranscript.segments`, `Video.chunks`, `Video.quizzes`, `Video.flashcard_decks`).
  - SQLAlchemy issues an initial `SELECT` on `videos`, followed by clean, index-accelerated `SELECT ... WHERE video_id IN (...)` queries for each collection.
  - Guarantees $O(1)$ constant query count, zero Cartesian multiplication, and optimal memory efficiency.

### 5. Why List and Detail Endpoints Have Different Payload Sizes
- **List Endpoint (`GET /api/videos`)**:
  - Designed for browsing in the Learning Library.
  - Returns a lightweight projection: title, status, timestamps, and aggregated counts (`chunk_count`, `segment_count`, `has_quiz`, `has_flashcards`).
  - Omits full transcript text, hundreds of segments, and quiz questions to maintain small payload sizes (<5 KB) and sub-10ms response times.
- **Detail / Workspace Endpoint (`GET /api/videos/{video_id}`)**:
  - Designed for active studying.
  - Returns the complete workspace: full transcript, cleaned segments, semantic chunks, and persisted quiz/flashcard decks.

### 6. Historical Attempt Retrieval & Longitudinal Learning Foundation
- `GET /api/quizzes/{quiz_id}/attempts` queries the `quiz_attempts` and `quiz_answers` tables.
- **Privacy & Security**:
  - Strips server-held `correct_answer` and `explanation` from historical answers, returning only `selected_answer` and `is_correct`.
- **Educational Foundation for Adaptive Intelligence**:
  - Logging timestamped attempts with scores, performance tiers, and `weak_chunk_ids` lays the data foundation for future:
    1. **Learning Curves**: Tracking mastery progression over time.
    2. **Concept Gap Analysis**: Identifying knowledge chunks where a learner repeatedly struggles across attempts.
    3. **Targeted Revision Loops**: Feeding persistent weak chunk IDs into future adaptive recommendation engines.

---

## Step 14 Phase 1: Deterministic Learner Knowledge Gap Engine

### 1. Learner Analytics vs. Generative AI
- **The Core Distinction**:
  - LLMs (like Gemini) excel at *synthesis, explanation, and transformation* (e.g. turning raw transcripts into structured flashcards or contextual hints).
  - LLMs are *probabilistic and nondeterministic* — asking an LLM "is this student weak in Backpropagation?" yields variable answers across runs, suffers from hallucination, is uninterpretable, and introduces unnecessary monetary cost and latency.
  - Learner knowledge analytics requires **exactness, reproducibility, and auditability**.
  - Deriving knowledge gaps deterministically using statistical and rule-based heuristics ensures:
    1. **Explainability**: Every categorization (`WEAK`, `DEVELOPING`, `STRONG`) can be justified with exact evidence (e.g. "2 consecutive errors on recent attempts").
    2. **Auditability**: In academic evaluations and student grading, every calculation is 100% reproducible.
    3. **Low Latency & Cost**: SQL joins and Python statistical reductions take <15 milliseconds with zero API costs.

### 2. Longitudinal Data & Temporal Performance Tracking
- **What is Longitudinal Data?**:
  - Repeated observations of the same subjects (learner interactions) over time.
  - Rather than treating a quiz answer as an isolated event, longitudinal tracking links answers chronologically ($t_1 < t_2 < t_3$).
- **Preserving Chronological Integrity**:
  - The knowledge gap engine preserves the timeline via `QuizAttempt.created_at ASC`.
  - Distinguishes between:
    - **Isolated Mistake**: 1 incorrect answer out of several attempts does not signify a gap.
    - **Repeated Failure**: 2+ consecutive incorrect answers indicate a systematic misconception.
    - **Recovery / Learning**: A learner who failed earlier but answered correctly in recent attempts is categorized as `IMPROVING` or `DEVELOPING`, not permanently branded as `WEAK`.

### 3. Chunk-Level Aggregation Architecture
- **Knowledge-Chunk Grounding**:
  - In VIDYORA AI, quiz questions are grounded to specific `KnowledgeChunk` records via `QuizQuestion.source_chunk_id`.
  - Traceability pipeline:
    $$\text{QuizAttempt} \rightarrow \text{QuizAnswer} \rightarrow \text{QuizQuestion} \rightarrow \text{KnowledgeChunk}$$
  - For any given chunk, the engine aggregates:
    - Total questions answered
    - Total correct vs. incorrect answers
    - Accuracy ratio ($\text{correct} / \text{total}$)
    - Consecutive streak of recent correct or incorrect answers
    - Chronological progression of scores across historical attempts

### 4. Deterministic Classification Heuristics
- The engine categorizes each knowledge chunk into 4 unambiguous states:
  - **`INSUFFICIENT_DATA`**: Less than 2 observations ($N < 2$). Prevents false positive classification from a single lucky guess or accidental typo.
  - **`WEAK`**: $N \ge 2$, with either $\ge 2$ consecutive recent errors OR overall accuracy $< 40\%$. Signifies repeated conceptual struggle.
  - **`STRONG`**: $N \ge 2$, overall accuracy $\ge 75\%$, and the most recent observation was answered correctly. Demonstrates proven mastery.
  - **`DEVELOPING`**: $N \ge 2$, mixed accuracy ($40\% \le \text{acc} < 75\%$) or high historical accuracy with a recent mistake requiring reinforcement.

### 5. Performance Trend Derivation
- To determine if a learner is improving, stable, or declining over time:
  - Requires at least 2 distinct observations.
  - Splits the chronological history into two halves: earlier baseline half vs. recent half.
  - Compares earlier accuracy ($acc_{\text{early}}$) to recent accuracy ($acc_{\text{recent}}$):
    - $\Delta \ge +0.25 \rightarrow \mathbf{IMPROVING}$
    - $\Delta \le -0.25 \rightarrow \mathbf{DECLINING}$
    - $-0.25 < \Delta < +0.25 \rightarrow \mathbf{STABLE}$

### 6. SQL Aggregation vs. Application-Level Computation
- **Where Should Computations Run?**:
  - **SQL**: Optimal for filtering (`WHERE video_id = :id`), joining relational tables (`quiz_answers` $\rightarrow$ `quiz_questions`), and chronological ordering (`ORDER BY qa.created_at ASC`).
  - **Python**: Optimal for complex temporal streak analysis (e.g. consecutive incorrect count backwards from the most recent attempt) and window-based trend calculations.
- **Eliminating the N+1 Query Anti-Pattern**:
  - Instead of querying the database in a loop for each of the $M$ chunks in a video ($M$ queries), the repository executes a single joined query:
    ```sql
    SELECT a.id, a.is_correct, a.created_at, q.source_chunk_id, ...
    FROM quiz_answers a
    JOIN quiz_questions q ON a.question_id = q.id
    JOIN quiz_attempts att ON a.attempt_id = att.id
    JOIN quizzes qz ON att.quiz_id = qz.id
    WHERE qz.video_id = :video_id
    ORDER BY a.created_at ASC;
    ```
  - Reduces database round-trips from $O(M)$ to $O(1)$ constant time.

### 7. Foundation for Future Adaptive Learning
- **Closing the Learning Loop**:
  - The knowledge gap engine produces structured outputs linking:
    $$\mathbf{Weak\ Chunk\ ID} \longrightarrow \mathbf{Source\ Timestamp} \longrightarrow \mathbf{Transcript\ Excerpt}$$
  - This structured metadata directly enables future targeted revision workflows:
    1. Jumping the video player directly to the timestamp where the misunderstood concept was taught.
    2. Generating targeted, adaptive quiz questions specifically addressing the student's identified weak chunks.

---

## Step 14 Phase 2: Knowledge Gap Visualizer UI

### 1. Why the Knowledge Gap UI Exists
- In typical educational applications, quiz evaluations end at a raw percentage score (e.g. "60% Needs Revision").
- This leaves the learner blind to *which specific ideas* they misunderstood and *where* in the lecture to review.
- The Knowledge Gap Visualizer translates raw backend assessment aggregations into an actionable diagnostic interface:
  - Highlights weak concepts needing immediate review with highest visual priority.
  - Explains the exact historical evidence (e.g., "Repeated incorrect responses (2 consecutive errors) on recent attempts").
  - Provides a 1-click **"Review in Video"** action grounded in the precise lecture timestamp.

### 2. Frontend Data Flow & Backend as Single Source of Truth
- **Strict Separation of Concerns**:
  - React components **never recalculate** accuracy, mastery status, streaks, trends, or diagnostic reasons.
  - The backend FastAPI endpoint (`GET /api/videos/{video_id}/knowledge-gaps`) is the single authoritative source of truth.
  - Flow:
    $$\text{PostgreSQL Quiz History} \xrightarrow[\text{Backend Service}]{\text{Deterministic Engine}} \text{FastAPI JSON Response} \xrightarrow[\text{aiApi.ts}]{\text{Strictly Typed Client}} \text{React State} \rightarrow \text{KnowledgeGapView}$$
- **Automatic Invalidation**:
  - When a user retakes or evaluates a quiz, `evaluateQuizApi` resolves and triggers `handleLoadKnowledgeGaps()`.
  - The knowledge gap view immediately refreshes with updated diagnostic metrics without full page reload.

### 3. Timestamp Navigation Without Fake Player Control
- **Honest Engineering**:
  - Rather than faking an embedded video player or building a non-functional scrubber timeline, the UI provides honest, reliable timestamp navigation:
  - Formats the original video URL with time offsets (e.g., `https://www.youtube.com/watch?v=aircAruvnKk&t=45s`).
  - Clicking **"Review in Video"** opens the lecture directly at the exact second where the misunderstood concept was taught.

### 4. Accessibility & UI States
- **State Handling**:
  - **Loading**: Pulse indicators inform the learner while analytics compute.
  - **Error / Retry**: Catches network faults and offers clean retry buttons.
  - **Insufficient Data**: When $\text{assessed\_chunks} = 0$, explicitly explains that at least 2 observations are needed, avoiding premature or unfair "weak" labels.
  - **Filter Controls**: Keyboard-accessible buttons with `aria-pressed` attributes and badge counts.

---

## Step 14 Phase 3: Targeted Learning Recovery Engine

### 1. Purpose & Product Direction
The Targeted Learning Recovery Engine completes the adaptive learning feedback loop:
$$\text{Video} \rightarrow \text{Knowledge Chunks} \rightarrow \text{Assessment} \rightarrow \text{Knowledge Gap Diagnosis} \rightarrow \mathbf{Targeted\ Learning\ Recovery} \rightarrow \mathbf{Micro\text{-}Quiz} \rightarrow \mathbf{Measured\ Improvement} \rightarrow \mathbf{Updated\ Knowledge\ State}$$

Unlike generic AI tutors or chatbots that generate ungrounded, endless text explanations, the Recovery Engine is an evidence-grounded remediation system:
- **Tied to Identified Weak Chunks**: Initiated directly from a verified `WEAK` knowledge gap.
- **Source-Grounded**: Explanation and micro-quiz are constructed solely from the lecture source text and its immediate chronological context.
- **Targeted Micro-Assessment**: 2–4 questions testing the specific misconceptions or weaknesses identified.
- **Deterministic Before vs. After Measurement**: Objective comparison between historical baseline accuracy and micro-quiz performance.
- **Auditable & Reproducible**: AI generates the pedagogical text; the backend deterministically grades and evaluates recovery status.

> [!NOTE]
> **Engineering Disclaimer**: This recovery status is an engineering indicator of assessment improvement, not a scientifically validated measurement of mastery.

---

### 2. Recovery Session Lifecycle
Recovery sessions adhere to an explicit, auditable finite-state enum (`RecoverySessionStatus`):

```
       [User clicks "Start Learning Recovery"]
                         │
                         ▼
                     [CREATED]
                         │
             (Fetch source chunk & context)
                         │
                         ▼
             [EXPLANATION_GENERATED]
                         │
         (Gemini generates grounded micro-quiz)
                         │
                         ▼
                    [QUIZ_READY]
                         │
           (Learner answers micro-quiz)
                         │
                         ▼
                   [IN_PROGRESS]
                         │
        (Backend deterministic grading & scoring)
                         │
                         ▼
                    [EVALUATED]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   [RECOVERED]                    [NOT_RECOVERED] / [IMPROVED]
        │                                 │
 (State updated in UI)             (Retry allowed if attempt < MAX)
```

1. **`CREATED`**: Session row initialized with target video ID, chunk ID, baseline accuracy, and originating evidence.
2. **`EXPLANATION_GENERATED`**: Source-grounded targeted explanation, worked example, and key takeaway created.
3. **`QUIZ_READY`**: Focused 2–4 question micro-quiz generated, sanitized (server-held answers), and presented to learner.
4. **`IN_PROGRESS`**: Learner interacting with recovery session.
5. **`EVALUATED`**: Micro-quiz evaluated on the backend against hidden answer keys.
6. **`RECOVERED` / `NOT_RECOVERED` / `IMPROVED` / `INSUFFICIENT_EVIDENCE`**: Final outcome state stored with timestamped metrics.

---

### 3. Database Persistence Model
Two PostgreSQL tables support auditability and longitudinal analytics:

#### `learning_recovery_sessions`
- `id` (UUID PK): Unique recovery session identifier.
- `user_id` (UUID FK -> users.id, nullable): Authenticated learner identity.
- `video_id` (String FK -> videos.id, CASCADE): Associated lecture video.
- `chunk_id` (String FK -> knowledge_chunks.id, CASCADE): Target weak knowledge chunk.
- `source_timestamp`, `source_formatted_time`: Exact lecture offset.
- `originating_evidence`: Diagnostic explanation from knowledge gap engine.
- `attempt_number`: 1 or 2 (capped at `MAX_RECOVERY_ATTEMPTS = 2`).
- `status`: Lifecycle enum string (`QUIZ_READY`, `EVALUATED`, etc.).
- `explanation_title`, `targeted_explanation`, `worked_example`, `key_takeaway`: Remediation text.
- `micro_quiz_data`: JSON array holding complete server-side quiz definition (with answers and explanations).
- `pre_recovery_accuracy`: Float baseline percentage prior to recovery.
- `post_recovery_accuracy`: Float percentage achieved on the micro-quiz.
- `absolute_improvement`: $\Delta = \text{post} - \text{pre}$.
- `total_questions`, `correct_count`: Raw integer counts.
- `recovery_result`: String enum (`RECOVERED`, `IMPROVED`, `NOT_RECOVERED`, `INSUFFICIENT_EVIDENCE`).
- `evaluated_at`, `created_at`, `updated_at`: Timestamps.

#### `recovery_quiz_answers`
- `id` (UUID PK): Unique answer submission row.
- `session_id` (UUID FK -> learning_recovery_sessions.id, CASCADE).
- `question_id`: Identifier of the micro-quiz question.
- `selected_answer`: Learner's submitted answer text.
- `is_correct`: Deterministic boolean result.
- `created_at`: Submission timestamp.

---

### 4. Separation of Responsibilities: Gemini vs. Deterministic Backend

| Responsibility | Component | Method / Technology |
| :--- | :--- | :--- |
| **Explanation Generation** | Google Gemini (`gemini-2.5-flash` / `gemini-3.5-flash-lite`) | Source-grounded prompt with temperature=0.2 |
| **Micro-Quiz Question Generation** | Google Gemini | Constrained JSON schema output (2–4 questions, 4 choices) |
| **Answer-Key Concealment** | Backend API Layer | Strips `correct_answer` and `explanation` before client dispatch |
| **Grading & Scoring** | Backend Service (`RecoveryService`) | Exact string matching between submission and hidden answer key |
| **Performance Delta Calculation** | Backend Service | Absolute improvement $\Delta = \text{post\_accuracy} - \text{pre\_accuracy}$ |
| **Recovery Decision** | Backend Service | Configurable heuristic threshold evaluation |
| **Session Lifecycle & Attempt Limit** | Backend Repository | Transactional SQLAlchemy validation (`count_attempts_for_chunk <= 2`) |

---

### 5. Source-Grounding Strategy
To prevent hallucination:
1. **Narrow Context Window**: Gemini is NOT fed the entire multi-hour transcript.
2. **Chunk + Narrow Boundary**: The prompt includes the weak knowledge chunk text plus immediately adjacent chunks when available.
3. **Negative Constraints**: The system prompt strictly prohibits introducing external domain facts or inventing details absent from the provided transcript.
4. **Pedagogical Differentiation across Attempts**:
   - **Attempt 1**: Conceptual explanation + concrete example grounded in the lecture.
   - **Attempt 2**: Simplified explanation + misconception contrast (contrasting what the concept is vs. what it is commonly confused with) + distinct micro-quiz questions.

---

### 6. Deterministic Heuristics & Decision Logic
The evaluation applies explicit, documented engineering heuristics:
- **`MIN_QUESTIONS_FOR_DECISION` = 2**: Prevents classifying recovery on trivial 1-question quizzes. Quizzes with $< 2$ questions yield `INSUFFICIENT_EVIDENCE`.
- **`RECOVERY_PASS_THRESHOLD_PCT` = 75.0%**: Performance $\ge 75\%$ with positive improvement ($\Delta > 0$) or maintaining high micro-quiz accuracy ($\ge 75\%$) yields `RECOVERED`.
- **`IMPROVEMENT_THRESHOLD_PCT` = 60.0%**: Performance between $60.0\%$ and $74.9\%$ with demonstrated improvement yields `IMPROVED`.
- **`NOT_RECOVERED`**: Score $< 60.0\%$, or failure to show improvement over baseline.
- **`MAX_RECOVERY_ATTEMPTS` = 2**: If the learner does not recover after 2 attempts, the system prevents automated loops and directs them to review the lecture video directly at the exact timestamp.

---

### 7. Security & Answer-Key Concealment
- **Client Security**: `RecoverySessionClientView` models filter out `correct_answer` and `explanation` while the session is in `QUIZ_READY` or `IN_PROGRESS`.
- **Server Evaluation**: Correct answers and pedagogical explanations are released only after evaluation is finalized in `question_results`.
- **Submission Integrity**: Submissions are validated for:
  - Unknown question IDs (HTTP 422).
  - Invalid answer choices not in the original 4 options (HTTP 422).
  - Duplicate evaluation prevention (HTTP 400).
  - Session ownership mismatch (HTTP 403).

---

### 8. Transaction Safety & Non-Destructive Analytics
- **Atomic Persistence**: Session creation and answer grading execute in explicit database transactions; failures trigger clean rollbacks.
- **Historical Preservation**: Recovery evaluations do NOT overwrite, delete, or alter previous `quiz_attempts` rows.
- **Diagnostic Enrichment**: `ChunkKnowledgeGap` exposes `has_recovered: bool` and `latest_recovery_result: Optional[str]`, allowing the UI to celebrate recovery without corrupting historical diagnostic traces.

---

## Step 15: Interactive Video Learning Workspace

### 1. Video Player Architecture
- **Official YouTube IFrame Player API**:
  - Implemented using the official, standard YouTube IFrame API (`https://www.youtube.com/iframe_api`) rather than hacky `iframe` embeds or fake UI shells.
  - Asynchronously loads the API script once (`ensureYouTubeIframeApi`), attaching to `window.onYouTubeIframeAPIReady` and resolving a singleton Promise.
  - Instantiates `new window.YT.Player(element, options)` with strict configuration: `enablejsapi: 1`, `origin: window.location.origin`, `playsinline: 1`, `controls: 1`.
  - Exposes an imperative `VideoPlayerHandle` via React `useImperativeHandle` and `forwardRef`:
    - `seekTo(seconds: number, shouldPlay?: boolean)`
    - `play()`, `pause()`, `togglePlay()`
    - `getCurrentTime(): number`, `getDuration(): number`, `isPlaying(): boolean`
- **Companion Playback Controls**:
  - Complements native YouTube player controls with Vidyora pedagogical controls:
    - Custom play/pause toggle with active playback indicators.
    - Skip -10s / +10s buttons.
    - Draggable / clickable continuous progress scrubber.
    - Current time and duration display (`MM:SS` / `HH:MM:SS`).
    - Speed selector (`0.75x`, `1x`, `1.25x`, `1.5x`, `2x`).
    - Volume mute toggle.
    - Live concept badge: Dynamically shows which Knowledge Chunk is currently being taught at the player's timestamp (`Now explaining: Chunk #X`).

### 2. Timestamp Seeking & Multi-View Grounding
- **Global Seek Pipeline**:
  - Any timestamp interaction throughout the entire workspace flows directly to `handleSeekTo(seconds, shouldPlay = true)`.
  - The embedded player executes `player.seekTo(seconds, true)` and triggers `player.playVideo()`.
  - The player shows an animated feedback toast (`"Jumped to 04:12"`).
  - Smoothly scrolls the video player into view on mobile or when scrolled out of the viewport.
- **Connected Surfaces**:
  1. **Synchronized Transcript**: Clicking any segment timestamp or spoken line seeks the player to `seg.start`.
  2. **Knowledge Chunks**: Clicking `[▶ Watch this section]` or the chunk timestamp seeks to `chunk.start_time`.
  3. **Structured Study Notes**: Clicking timestamp badges in lecture outline sections seeks to `section.start_time`.
  4. **Video Summary**: Clicking citations in "Video Source Timestamps" seeks to `ts.timestamp`.
  5. **Interactive Quiz**: Clicking source timestamps on questions and during evaluation review jumps the player.
  6. **Flashcards**: Clicking timestamp links on flashcard fronts jumps the player to the concept introduction.
  7. **Knowledge Gap Visualizer**: Clicking `Review in Video ({formatted_time})` on any concept card jumps the embedded player directly to that lecture moment without leaving the app.
  8. **Targeted Learning Recovery**: Clicking `Review in Video` inside the recovery explanation seeks the video while keeping the explanation and micro-quiz visible right beside it.

### 3. Transcript + Video Synchronization
- **Time Polling & Real-Time Coordination**:
  - When the video is playing (`YT.PlayerState.PLAYING`), the player polls `player.getCurrentTime()` every 250ms and emits `onTimeUpdate(currentTime, duration)`.
  - When paused, polling pauses immediately to preserve CPU cycles and battery life.
- **Active Segment Identification**:
  - `activeSegmentIndex = segments.findIndex(seg => currentTime >= seg.start && currentTime < seg.start + seg.duration)`.
  - Active segment receives visual accent styling (indigo background, glowing border, "Speaking" audio indicator).
- **Smooth Auto-Scroll**:
  - The transcript component tracks the active segment's relative vertical position within its scroll container.
  - Automatically centers the active segment as the lecturer speaks, with an easy toggle button (`Auto-Scroll: ON/OFF`) if the learner wishes to browse ahead manually.
- **Dialogue Search Filter**:
  - An inline search bar allows learners to instantly filter spoken words across hundreds of segments (e.g. searching "gradient" or "loss").

### 4. Coherent Learning Workspace Layout
- **Dual-Pane Desktop Architecture (`12-column grid`)**:
  - **Left Pane (7 cols)**:
    - Interactive 16:9 Video Player.
    - Player companion controls & active concept pill.
    - Sub-tabs for:
      - 📜 Synchronized Transcript (`InteractiveTranscript`)
      - 🧩 Knowledge Chunks (`KnowledgeChunksList`)
      - ℹ️ Lecture Details & Metadata
  - **Right Pane (5 cols)**:
    - Study Suite Navigation (Notes, Summary, Quiz, Flashcards, Knowledge Gaps, Recovery).
    - AI Action Triggers (Study Notes, Summary, Quiz, Flashcards).
    - Embedded Content Views.
- **Mobile & Tablet Responsive Behavior**:
  - Stacks the video player at the top with responsive 16:9 ratio.
  - Content tabs remain scrollable and touch-friendly below.
  - Tapping "Review in Video" smoothly scrolls up to the player.

### 5. Learning Recovery Side-by-Side Integration
- **Elimination of Blocking Modals**:
  - Extended `LearningRecoveryView` with `isEmbedded?: boolean`.
  - When initiated from a Knowledge Gap card, the workspace seamlessly switches the right pane to the Recovery tab rather than covering the player with an opaque backdrop.
  - **The Continuous Recovery Loop**:
    1. Learner sees why the concept is weak and its diagnostic evidence.
    2. Learner clicks `Review in Video (04:12)`.
    3. The video player in the left column seeks to 04:12 and starts playing.
    4. Learner watches the 1–2 minute section on the left while referencing the worked example on the right.
    5. Learner completes the 2–4 question micro-quiz on the right.
    6. Learner submits answers and immediately views their before vs. after accuracy delta ($\Delta = \text{post} - \text{pre}$).
    7. Learner clicks `← Back to Gaps` to return to their concept mastery overview.

### 6. Error Handling & Robustness
- **YouTube Embed Restrictions**:
  - Handled YouTube player error codes (2 = invalid parameter, 100 = video missing/private, 101/150 = owner disabled embedded playback).
  - Rather than crashing the app or showing a broken black box, displays a helpful message explaining the restriction with an external "Watch on YouTube" button.
  - The remainder of the learning workspace (notes, summary, quiz, chunks, transcript, gaps) remains 100% operational.
- **DOM Cleanup & Fast Refresh**:
  - Cleans up `playerInstanceRef.current?.destroy()` and intervals on unmount to prevent memory leaks and zombie timers.
  - Isolated pure utility functions (`formatTime`) into separate files to guarantee React Fast Refresh compatibility.

### 7. Accessibility & Learner-Centric UX Decisions
- **Keyboard Traversal & Focus Rings**:
  - All interactive timestamp buttons feature explicit focus rings (`focus:ring-2 focus:ring-indigo-500/50`) and semantic `type="button"` attributes.
  - Transcript rows include `role="button"` and `tabIndex={0}` with `onKeyDown` handlers responding to `Enter` and `Space` keys to jump the player.
  - Scrubber range input includes `aria-label="Seek video progress"`.
  - Native YouTube controls are preserved inside the iframe (`controls: 1`) allowing keyboard navigation for closed captions (CC), playback settings, and full-screen toggling.
- **Elimination of Technical UUID Jargon**:
  - Replaced internal database UUID listings (e.g. `source_chunk_id` in quiz alerts and flashcards) with friendly pedagogical counts and conceptual labels (e.g. `Concept Segment #1`, `16 knowledge chunks`).
  - Raw HTTP failure exceptions are mapped to actionable user-facing messages.

### 8. Limitations & Constraints
- **Third-Party Embedded Playback Policy**:
  - If a creator disables embedding on YouTube (`onError` code 150/101), the iframe cannot play directly due to YouTube's content licensing policy. In this case, Vidyora displays a polite notice, a direct YouTube link (`Watch on YouTube`), and keeps all AI study tools (transcript, chunks, summary, notes, quiz, flashcards, gaps, and recovery) fully functional.
- **Network Bandwidth / Autoplay Restrictions**:
  - Modern browsers prevent programmatic autoplay with unmuted audio without prior user gesture. Vidyora respects this by initializing with muted sound when required and executing user-initiated seeks cleanly.

### 9. Verification & Live Test Results
- **Backend Test Suite**: `107 passed` across 13 test suites in `.venv\Scripts\pytest -q` (zero failures).
- **Frontend Linter**: `oxlint` found `0 warnings and 0 errors` across 23 files.
- **Frontend Build**: `tsc -b && vite build` completed in `745ms` with zero TypeScript errors.
- **E2E Live Test on YouTube Video (`aircAruvnKk`)**:
  1. Processed `https://www.youtube.com/watch?v=aircAruvnKk` into active workspace (16 chunks, 286 segments).
  2. Verified real embedded YouTube player initialized with controls.
  3. Tested Play, Pause, and `+10s` seek.
  4. Tested Synchronized Transcript seeking: clicked segment at `00:19` -> player sought to `00:19`.
  5. Tested Knowledge Chunks seeking: clicked "Watch this section" on Chunk 1 -> player sought to `00:04`.
  6. Generated AI Quiz, clicked source timestamp `02:49` -> player sought to `02:49`.
  7. Answered 5 quiz questions, submitted for evaluation -> received 100% score (5/5) with rationales.
  8. Verified Gaps tab updated with concept mastery and one-click video review.
  9. Confirmed Notes, Summary, Quiz, Flashcards, and Library persist without data loss.

---

## Step 16: Authentication and Multi-User Isolation

### 1. Architectural Overview & Shift to Multi-Tenancy
In Steps 10 through 15, VIDYORA AI functioned as a single-user local development system. All processed lectures, quiz attempts, and learning recovery interventions resided in a unified database without tenant boundaries.
Step 16 transitioned VIDYORA AI into a secure, production-oriented multi-user learning platform where:
1. Every learner creates a distinct account or signs in.
2. Every learning asset—videos, transcripts, knowledge chunks, summaries, notes, quizzes, attempts, flashcards, knowledge gaps, and recovery sessions—is strictly bound to the authenticated learner.
3. Database queries enforce ownership at the SQL level, preventing Insecure Direct Object Reference (IDOR) attacks.

```
                    ┌───────────────────────────────┐
                    │       Learner (Browser)       │
                    └───────────────┬───────────────┘
                                    │ 1. POST /api/auth/login
                                    ▼
                    ┌───────────────────────────────┐
                    │     FastAPI Auth Service      │
                    │  (bcrypt verify + JWT encode) │
                    └───────────────┬───────────────┘
                                    │ 2. Return JWT Bearer Token
                                    ▼
                    ┌───────────────────────────────┐
                    │ Authenticated API Requests    │
                    │ Header: Bearer <JWT Token>    │
                    └───────────────┬───────────────┘
                                    │ 3. Depends(get_current_user)
                                    ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │                   Database Query Layer (PostgreSQL)               │
  │  - SELECT * FROM videos WHERE id = :id AND user_id = :current_user│
  │  - SELECT * FROM quizzes WHERE id = :id AND video.user_id = :user │
  │  - SELECT * FROM recovery WHERE id = :id AND user_id = :current_user│
  └───────────────────────────────────────────────────────────────────┘
```

---

### 2. Core Authentication Concepts

#### A. Password Hashing: Why Plaintext and Fast Hashes Are Dangerous
- **The Threat**: If a database is breached or leaked, passwords stored in plaintext or fast algorithms (MD5, SHA-1, SHA-256) can be cracked in seconds using precomputed rainbow tables or GPU-accelerated brute-force attacks (billions of hashes/sec).
- **The Solution (bcrypt)**:
  - VIDYORA uses `bcrypt` via the native `bcrypt` Python package.
  - **Salt Generation**: Every password receives a cryptographically secure 128-bit random salt, ensuring identical passwords yield completely different hashes, neutralizing rainbow table lookups.
  - **Work Factor (Cost Factor)**: bcrypt uses key derivation with tunable iterations ($2^{\text{cost}}$ rounds, default 12). This deliberately consumes ~100–300ms of CPU time per verification, making brute-force cracking prohibitively expensive while remaining imperceptible to an individual user.
  - **Truncation Guard**: Standard bcrypt has a 72-byte input limit; passwords are validated for minimum length (8 characters) and normalized before hashing.

#### B. JSON Web Tokens (JWT) for Stateless Authentication
- **Structure**:
  $$\text{JWT} = \text{Base64Url}(\text{Header}) \,.\, \text{Base64Url}(\text{Payload}) \,.\, \text{Signature}$$
  - **Header**: Specifies the algorithm (`HS256`) and token type (`JWT`).
  - **Payload (Claims)**: Contains standard claims:
    - `sub`: The stable learner UUID (`user.id`).
    - `email`: Normalized email string.
    - `exp`: Expiration timestamp (default: 24 hours / 1440 minutes).
    - `iat`: Issued-at timestamp.
  - **Signature**: Generated via HMAC-SHA256 using the server's private `JWT_SECRET_KEY`:
    $$\text{Signature} = \text{HMAC-SHA256}(\text{Header} + "." + \text{Payload}, \text{JWT\_SECRET\_KEY})$$
- **Stateless Verification**: The backend validates token authenticity and expiry by verifying the cryptographic signature without querying a centralized session cache (like Redis). If an attacker tampers with the user ID in the payload, the signature check fails immediately with HTTP 401.

---

### 3. Authentication vs. Authorization
- **Authentication ("Who are you?")**:
  - Handled by `get_current_user` in `services/auth_service.py`.
  - Extracts the `Authorization: Bearer <token>` header using FastAPI's `HTTPBearer`.
  - Decodes the JWT, validates signature and expiration, and fetches the corresponding active `User` record from PostgreSQL.
  - If missing, invalid, or expired, returns `HTTP 401 Unauthorized`.
- **Authorization ("What are you allowed to do?")**:
  - Handled in repository methods and endpoint handlers.
  - Verifies that the authenticated `current_user` owns the specific resource they are attempting to read, modify, or evaluate.
  - If a user requests a resource that exists in the database but belongs to another user, the server rejects the request with `HTTP 404 Not Found` (or `HTTP 403 Forbidden` where enumeration must be explicitly forbidden).

---

### 4. IDOR (Insecure Direct Object Reference) Prevention

#### The Threat
An IDOR vulnerability occurs when an application exposes a reference to an internal database object (such as a UUID in the URL: `/api/videos/d4e8...` or `/api/recovery/8f2a...`) and trusts the client without validating that the authenticated user owns that object.
Under an IDOR flaw, User B could simply copy User A's `video_id` into their own browser and read User A's private study notes, view their diagnostic knowledge gaps, or submit answers to their recovery sessions.

#### Backend Query-Level Enforcement
VIDYORA AI enforces user isolation strictly at the database query layer:
1. **Video Isolation**:
   ```python
   # In VideoRepository.get_by_id:
   query = db.query(Video).filter(Video.id == video_id)
   if user_id is not None:
       query = query.filter(Video.user_id == user_id)
   return query.first()
   ```
   If User B queries User A's `video_id`, `Video.user_id == user_b.id` evaluates to False, returning `None`. The endpoint returns `404 Not Found`, revealing zero information about whether the resource exists for other users.
2. **Quiz Attempts Isolation**:
   ```python
   # In QuizRepository.get_quiz_attempts:
   query = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id)
   if user_id is not None:
       query = query.filter(QuizAttempt.user_id == user_id)
   ```
3. **Learning Recovery Isolation**:
   ```python
   # In RecoveryRepository.get_session_by_id:
   query = db.query(LearningRecoverySession).filter(LearningRecoverySession.id == session_id)
   if user_id is not None:
       query = query.filter(LearningRecoverySession.user_id == user_id)
   ```
4. **Learner Analytics Isolation**:
   ```python
   # In main.py GET /api/learners/{user_id}/knowledge-gaps:
   if current_user and user_id != current_user.id:
       raise HTTPException(status_code=403, detail="Access denied to another learner's knowledge profile.")
   ```
5. **Multi-User Video Scoping**:
   When multiple users ingest the same public YouTube lecture (e.g. `aircAruvnKk`), each user gets a tenant-scoped video ID:
   ```python
   scoped_video_id = f"{raw_video_id}_{current_user.id.replace('-', '')[:12]}"
   ```
   This guarantees that User A and User B maintain completely distinct video records, transcripts, chunks, and attempt histories, even for identical educational lectures. The raw YouTube URL is preserved in `Video.url` so the frontend YouTube Player continues seeking and playing the 11-character video without alteration.

---

### 5. Database Schema & Alembic Migration

#### Existing User Table & Migration
Rather than introducing redundant user tables, VIDYORA reused the existing `users` table created in Step 13, adding a `hashed_password` column:
- **Migration**: `00d68d8a0fab_add_user_password_hash.py`
  - Added `hashed_password VARCHAR(255) NOT NULL` to `users`.
  - Upgraded via `alembic upgrade head`.
  - Schema confirmed on `PostgresqlImpl` with zero manual schema tampering.

#### Relational Integrity & Cascades
- `users.id` (UUID v4 string) forms the primary key.
- `videos.user_id` has Foreign Key `fk_videos_user_id_users` with `ON DELETE CASCADE`.
- `quizzes.user_id`, `quiz_attempts.user_id`, `flashcard_decks.user_id`, `learning_recovery_sessions.user_id` all maintain foreign keys back to `users.id`.
- Deleting a user cleanly purges all their associated learning assets across all tables without orphan records.

---

### 6. Frontend Authentication Flow & UX

#### Components Created & Updated
1. **`frontend/src/types/auth.ts`**:
   - Defines `User`, `TokenResponse`, `UserLoginRequest`, `UserRegisterRequest`.
2. **`frontend/src/services/authApi.ts`**:
   - Manages token storage in `localStorage` (`vidyora_auth_token`).
   - Exports `getAuthToken()`, `setAuthToken(token)`, `clearAuthToken()`.
   - Exports `getAuthHeaders()` which automatically attaches `Authorization: Bearer <token>`.
   - Wraps `loginApi`, `registerApi`, and `getCurrentUserApi()`.
3. **`frontend/src/services/aiApi.ts`**:
   - Updated all fetch requests to use `getAuthHeaders()`.
   - Added `processVideoApi(url)` for unified video intake.
   - On HTTP 401 Unauthorized, automatically clears token and redirects to login.
4. **`frontend/src/components/AuthModal.tsx`**:
   - Modern glassmorphic dark-mode modal with tabs for "Sign In" and "Create Account".
   - Input validation (minimum 8 characters for passwords).
   - Clear error banners for invalid credentials or duplicate email addresses.
   - Auto-login upon registration for frictionless onboarding.
5. **`frontend/src/App.tsx` Integration**:
   - Checks session on mount via `getCurrentUserApi()`.
   - If unauthenticated, displays an intake view prompting the user to Sign In or Create Account.
   - If authenticated, displays the full learning workspace with the learner's badge (`👤 Name / Email`) and a "Sign Out" button in the top navigation.
   - Clear button and Sign Out button gracefully reset the workspace state without leaking state to the next session.

---

### 7. Verification & Security Testing

#### Security & IDOR Test Suite (`test_auth_and_isolation.py`)
A dedicated 17-test security suite was added to validate all auth boundaries:
1. `test_registration_success_and_sanitization`: User registration succeeds; password hash is NOT returned in response.
2. `test_duplicate_email_registration_rejected`: Registering duplicate email returns HTTP 400.
3. `test_invalid_password_login_rejected`: Incorrect password returns HTTP 401.
4. `test_nonexistent_email_login_rejected`: Non-existent email returns HTTP 401.
5. `test_successful_login_and_token_retrieval`: Returns valid JWT token with Bearer scheme.
6. `test_current_user_me_endpoint`: GET `/api/auth/me` returns current learner profile.
7. `test_unauthenticated_requests_rejected`: All protected routes without token return HTTP 401.
8. `test_malformed_jwt_rejected`: Tampered or invalid JWT signatures return HTTP 401.
9. `test_expired_jwt_rejected`: Expired JWT tokens return HTTP 401.
10. `test_user_can_access_own_video_workspace`: User Alpha can view their own video.
11. `test_idor_user_cannot_access_other_users_video`: User Beta querying User Alpha's video gets HTTP 404.
12. `test_idor_user_cannot_access_other_users_knowledge_gaps`: User Beta querying User Alpha's gaps gets HTTP 404.
13. `test_idor_user_cannot_access_other_users_quiz_attempts`: User Beta querying User Alpha's attempts gets HTTP 404.
14. `test_idor_user_cannot_access_other_users_recovery_session`: User Beta querying User Alpha's recovery session gets HTTP 404.
15. `test_idor_user_cannot_submit_other_users_recovery_session`: User Beta submitting User Alpha's recovery session gets HTTP 404.
16. `test_idor_user_cannot_access_other_users_learner_profile`: User Beta inspecting User Alpha's learner gaps gets HTTP 403.
17. `test_library_isolation_between_users`: User Alpha and User Beta see strictly their own respective video libraries.

#### Full Regression Test Results
- **Backend Test Suite**: `124 passed, 3 warnings in 22.01s` via `.venv\Scripts\pytest backend\tests -q`.
  - All 107 legacy tests + 17 authentication & isolation tests pass with zero failures.
- **Frontend Linter**: `oxlint` found `0 warnings and 0 errors` across 26 files.
- **Frontend Build**: `tsc -b && vite build` completed in `786ms` with zero errors.
- **Database Status**: `alembic current` confirms revision `00d68d8a0fab (head)`.

---

### 8. Developer Takeaways & Future RAG Compatibility
1. **Never Trust Client-Side Object References**: Frontend filters can always be bypassed with curl, Postman, or script execution. Security must be enforced on the SQL query level where `user_id` is supplied directly from the validated JWT token.
2. **Keep Errors Sanitized**: Do not return 403 ("Forbidden") when a 404 ("Not Found") prevents an attacker from enumerating whether a resource ID exists.
3. **Future RAG Readiness**: Because all `videos` and their child `knowledge_chunks` are owned by `user_id`, future vector search and embeddings in `pgvector` can cleanly add `WHERE chunks.video_id IN (SELECT id FROM videos WHERE user_id = :user_id)` or direct `chunk.user_id` filtering. This ensures semantic search results and conversational LLM retrieval will remain strictly isolated to the user's private lectures.

---

## Step 17: RAG + Embeddings + pgvector Foundation

### 1. What is RAG (Retrieval-Augmented Generation)?
- **Retrieval-Augmented Generation (RAG)** is an architectural pattern that bridges static LLMs with dynamic, external, and private knowledge bases.
- Instead of relying solely on the parametric knowledge frozen in an LLM during training (or stuffing hundreds of pages of raw video transcripts directly into a prompt context window), RAG dynamically searches for only the most semantically relevant snippets of text for a given user query and provides those snippets as source context.

### 2. Why VIDYORA AI Needs RAG
- **Context Window & Cost Efficiency**: Video lectures are often 30 to 120 minutes long, generating tens of thousands of transcript words. Feeding an entire transcript on every user question is slow, expensive, and introduces "needle in a haystack" attention degradation.
- **Hallucination Prevention**: General LLMs might invent definitions or cite unrelated theorems. RAG forces downstream answers to be grounded strictly in the instructor's spoken words.
- **Precise Timestamp Navigation**: By retrieving chunk-level knowledge with exact start and end timestamps, VIDYORA can give learners instant "Watch at 12:43" interactive navigation to the exact millisecond where the concept is taught.

### 3. What Are Dense Vector Embeddings?
- An **embedding** is a numerical representation of semantic meaning in high-dimensional vector space.
- Traditional keyword search (e.g., SQL `LIKE '%neural network%'` or BM25) fails when the user asks a question using different vocabulary (e.g., "How does a deep learning model adjust its parameters?" matches a lecture mentioning "updating weights and biases with backpropagation", even if the exact phrase "deep learning model" is never used).
- An embedding model maps semantically related concepts to vectors that point in nearly the same mathematical direction.

### 4. Vector Databases & pgvector
- **Why pgvector**: Instead of operating a separate, specialized vector database cluster (such as Pinecone, Qdrant, or Milvus) which introduces synchronization lag, secondary authentication, and complex multi-database transactions, VIDYORA uses **pgvector**, a native PostgreSQL extension.
- **Single Source of Truth**: Videos, users, transcripts, quizzes, flashcards, knowledge chunks, and vector embeddings reside in the exact same ACID-compliant PostgreSQL database.
- **HNSW Indexing**: Hierarchical Navigable Small World (HNSW) graphs enable sub-millisecond approximate nearest neighbor (ANN) vector searches with logarithmic complexity even across millions of vectors.

### 5. Semantic Similarity & Cosine Distance
- **Cosine Distance vs. Cosine Similarity**:
  $$\text{Cosine Similarity}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}$$
  - For unit-normalized vectors:
    $$\text{Cosine Distance} = 1 - \text{Cosine Similarity}$$
  - In `pgvector`, the `<=>` operator computes cosine distance (ranging from 0.0 for identical vectors to 2.0 for diametrically opposed vectors).
  - In VIDYORA AI's repository layer:
    $$\text{Similarity Score} = 1.0 - \text{Cosine Distance}$$
  - A query with similarity 0.70+ signifies high semantic correlation; a query with similarity <0.30 denotes weak or unrelated topical overlap.

### 6. The Semantic Retrieval Pipeline
1. **User Query Intake**: Learner submits `{ "query": "How does gradient descent work?", "video_id": optional, "top_k": 5 }`.
2. **Query Vectorization**: `EmbeddingService` vectorizes the query using Google GenAI (`gemini-embedding-001`, 768 dimensions).
3. **Database-Level Ownership Filtering**: PostgreSQL filters candidates with `ChunkEmbedding.user_id == current_user.id` (and optionally `video_id == request.video_id`).
4. **Distance Calculation & Ranking**: `pgvector` computes cosine distance via `<=>` and orders results ascending (`ORDER BY distance ASC LIMIT :top_k`).
5. **Threshold Pruning**: Any chunk falling below `similarity_threshold` (default: 0.30) is discarded.
6. **Grounding Assembly**: Results are packaged into `RetrievedChunkResult` with original text, exact timestamps, and formatted strings (`"10:24"`).

### 7. User-Level Security & IDOR Defense
- **Strict Query-Level Isolation**: User A can NEVER retrieve chunks from User B. Chunks are filtered by `ChunkEmbedding.user_id == authenticated_user.id`.
- **Targeted Video IDOR Protection**: If User A passes `video_id="video_belonging_to_user_b"`, the service verifies video ownership against PostgreSQL and immediately returns HTTP 404 (Not Found), denying both access and resource existence enumeration.
- **No Reliance on Frontend Filters**: All access control is hard-enforced in SQL before vector similarity computation takes place.

### 8. Why Retrieval is Decoupled from LLM Generation
- Separating retrieval (`POST /api/rag/retrieve`) from response generation ensures:
  - **Observable Quality**: The retrieval ranking and cosine scores can be audited, measured, and benchmarked independently from LLM prompt quality.
  - **Lower Latency Testing**: Semantic search latency (typically 50–200ms) can be evaluated without waiting for LLM token streaming.
  - **Hot-Swappable Components**: Future upgrades to rerankers (e.g. cross-encoders), chunking strategies, or LLMs can occur without rewriting the core search engine.

### 9. Embedding Model Selection: Google GenAI `gemini-embedding-001`
- **Model Chosen**: `gemini-embedding-001` with `output_dimensionality=768`.
- **Reasoning**:
  - In the v1beta Google GenAI SDK, `text-embedding-004` is superseded by `gemini-embedding-001`.
  - Supports Matryoshka Representation Learning (MRL), allowing variable output dimensionality (`output_dimensionality=768`), maintaining full compatibility with our 768-dimensional pgvector schema.
  - Native to the existing Google GenAI SDK used across VIDYORA AI, requiring zero extra third-party SDK dependencies.

### 10. Database Schema Design (Alembic Migration `7a8e9d1f3b20`)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunk_embeddings (
    id VARCHAR(64) PRIMARY KEY,
    chunk_id VARCHAR(64) NOT NULL UNIQUE REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    video_id VARCHAR(64) NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_name VARCHAR(128) NOT NULL,
    dimension INTEGER NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX ix_chunk_embeddings_user_id ON chunk_embeddings(user_id);
CREATE INDEX ix_chunk_embeddings_video_id ON chunk_embeddings(video_id);
CREATE INDEX ix_chunk_embeddings_vector_hnsw ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);
```

### 11. Controlled Indexing Process
- Chunks are indexed idempotently: only chunks lacking an entry in `chunk_embeddings` are sent to the embedding API.
- If embedding generation fails (e.g., transient network glitch or rate limit), the underlying video ingestion and transcript generation do NOT fail permanently. Chunks remain saved and can be indexed subsequently via the idempotent `POST /api/rag/index` route.

### 12. Verification and Test Results
- **15 RAG & Security Tests**: All 13 unit/integration tests in `test_rag_and_embeddings.py` passed with 100% success.
- **Backend Regression Suite**: `137 passed` across the entire backend suite (`pytest -q`).
- **Frontend Checks**: `npm run lint` (0 errors, 0 warnings), `npm run build` (successful compilation in 906ms).
- **Live Vector Verification on `aircAruvnKk`**:
  - "What is a neural network?" $\rightarrow$ Retrieved Chunks 2 & 1 (Similarity: 0.6802, Timestamp: 02:19)
  - "How does a neural network learn?" $\rightarrow$ Retrieved Chunks 13 & 2 (Similarity: 0.7133, Timestamp: 15:22)
  - "What is gradient descent?" $\rightarrow$ Retrieved Chunk 9 (Similarity: 0.5535, Timestamp: 10:24)
  - Irrelevant Query ("How to bake a cake") $\rightarrow$ Correctly rejected with 0 results when using threshold 0.50.

### 13. Failures Encountered and How They Were Resolved
1. **Windows pgvector Missing Binary**:
   - *Issue*: `CREATE EXTENSION vector;` failed with file not found because PostgreSQL 16 on Windows does not bundle pgvector by default.
   - *Fix*: Obtained pre-compiled Windows pgvector 0.8.6 binaries for PostgreSQL 16, installed them into `C:\Program Files\PostgreSQL\16`, and verified `SELECT * FROM pg_available_extensions WHERE name='vector';`.
2. **Google GenAI v1beta Model Lookup**:
   - *Issue*: `text-embedding-004` returned 404 in the v1beta Google GenAI SDK.
   - *Fix*: Queried `client.models.list()`, identified `gemini-embedding-001` as the active embedding model, and configured `types.EmbedContentConfig(output_dimensionality=768)` to generate 768-dimensional vectors.
3. **DetachedInstanceError & Global Conftest Override**:
   - *Issue*: In `conftest.py`, an autouse fixture was overriding `get_current_user` with a legacy mock user for all non-auth test suites.
   - *Fix*: Excluded `test_rag_and_embeddings.py` from the autouse legacy override in `conftest.py` and captured email strings locally in fixtures.

### 14. What Every Developer Should Understand
- **Semantic search is not a silver bullet without thresholding**: Vectors always produce *some* numerical similarity distance even for completely nonsensical queries. Always calibrate a `similarity_threshold` to discard low-confidence matches.
- **Never decouple retrieval security from the database**: Multi-tenant RAG systems must filter by `user_id` at the SQL query level, not in Python memory after pulling top-k results. If you filter in memory after pulling top-k, an attacker could crowd out the user's results with other users' chunks.

## Step 1: Stabilize, Fix and Verify Existing Project (QuizQuestion ID VARCHAR Limit)

### 1. Root Cause Analysis
- **Symptom**: During automated quiz generation and persistence, attempts to save generated quizzes occasionally failed in PostgreSQL with string truncation errors (`value too long for type character varying(64)`).
- **Exact Mechanism**:
  - In `backend/repositories/quiz_repository.py`, question IDs are composite keys built by prefixing the quiz ID to prevent collisions across multiple quizzes:
    `db_question_id = f"{quiz.id}_{q.id}" if not q.id.startswith(f"{quiz.id}_") else q.id`
  - When Gemini generated descriptive slug-style IDs (e.g. `quiz_but_what_is_a_neural_network_chapter_1` [46 chars] + `q1_neuron_definition_and_activation_range` [42 chars]), the resulting composite string reached 89 characters.
  - In the initial persistence schema (`0001_initial_persistence_schema.py`), `quiz_questions.id` and `quiz_answers.question_id` were typed as `VARCHAR(64)`.
  - Any composite ID exceeding 64 characters triggered an immediate PostgreSQL integrity error and transaction rollback.

### 2. Schema Fix and Migration
- **Alembic Migration**: `5c0a9a22f8d1_widen_quiz_question_id_to_128.py` (Revision ID: `5c0a9a22f8d1`, Revises: `7a8e9d1f3b20`).
  1. Drops foreign key constraint `fk_quiz_answers_question_id_quiz_questions` on table `quiz_answers`.
  2. Alters `quiz_questions.id` column from `VARCHAR(64)` to `VARCHAR(128)`.
  3. Alters `quiz_answers.question_id` column from `VARCHAR(64)` to `VARCHAR(128)`.
  4. Re-creates foreign key constraint `fk_quiz_answers_question_id_quiz_questions` referencing `quiz_questions(id)` with `ON DELETE CASCADE`.
- **SQLAlchemy ORM Models** (`backend/db/models.py`):
  - `QuizQuestion.id`: `Mapped[str] = mapped_column(String(128), primary_key=True)`
  - `QuizAnswer.question_id`: `Mapped[str] = mapped_column(String(128), ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)`
- **Repository Safety** (`backend/repositories/quiz_repository.py`):
  - Added deterministic boundary guard: `if len(db_question_id) > 128: db_question_id = db_question_id[:128]`.

### 3. Verification & Live Database Testing
- **PostgreSQL Column Inspection**:
  - Verified via `information_schema.columns`:
    - `quiz_questions.id`: `character varying(128)`
    - `quiz_answers.question_id`: `character varying(128)`
  - Verified via `alembic_version`: `5c0a9a22f8d1` (head).
- **Full Quiz Workflow Regression Test**:
  - Tested with long IDs: `long_quiz_id = 'quiz_backprop_deep_neural_network_gradient_flow_001'` (51 chars), `long_q1_id = 'q1_multivariate_chain_rule_partial_derivative'` (45 chars) $\rightarrow$ Composite ID = 97 chars (> 64 chars).
  - Sequence verified:
    1. Generated and persisted quiz to PostgreSQL without truncation.
    2. Evaluated submission with deterministic scoring (100%, performance tier 'Strong').
    3. Persisted attempt and individual answers referencing 97-character foreign keys.
    4. Retrieved attempt history from PostgreSQL.
    5. Reloaded workspace via `VideoService.get_video_workspace()`, confirming clean sanitized client IDs (`q1_multivariate_chain_rule_partial_derivative`) without leaking correct answer keys or rationales.

### 4. Comprehensive Test Suite Results
- **Backend Tests (`pytest -q`)**: `139 passed, 3 warnings in ~25s`.
- **Frontend Linter (`npm run lint`)**: `0 warnings and 0 errors` (oxlint).
- **Frontend Build (`npm run build`)**: `tsc -b && vite build` completed in `1.87s` with zero errors.
- **RAG & Authentication Suites**:
  - `tests/test_rag_and_embeddings.py`: 13/13 passed.
  - `tests/test_auth_and_isolation.py`: 17/17 passed.
- **Security & Secret Leakage**:
  - Zero passwords, password hashes, JWT secrets, or DB credentials exposed in HTTP responses.
  - Cross-user IDOR protection verified (404 Not Found on unauthorized access).
  - Zero stack traces exposed on client errors.

### 5. Lessons Learned
- **Composite Primary Keys and Foreign Key Length Cascades**: When deriving primary keys by concatenating parent and child entity identifiers, always calculate the maximum potential length of the combined string. If modifying the primary key length, all foreign keys referencing it across the schema must be updated in tandem within the same migration transaction.
- **Preserve Clean Client Interfaces**: Internal database key representations (such as composite prefixes) should remain encapsulated server-side. The read/restore services (`video_service.py`) must cleanly strip prefixes before emitting data to the frontend so client state and evaluation payloads remain clean and intuitive.

## Step 2: Verify and Complete the RAG Pipeline

### 1. How Embeddings Work in VIDYORA AI
- **Embedding Model**: Google GenAI `gemini-embedding-001` with `output_dimensionality=768` configured via `config.py`.
- **Provider Architecture**: Implemented via `BaseEmbeddingProvider` in `backend/services/embedding_service.py`:
  - `GoogleGenAIEmbeddingProvider`: Production provider using `google.genai.Client(api_key=...)` and `types.EmbedContentConfig(output_dimensionality=768)`. Supports batch embedding (`embed_batch`) to minimize network round-trips.
  - `MockEmbeddingProvider`: Deterministic SHA-256 unit-normalized pseudo-embedding provider for offline/unit testing.
  - Strict vector validation: Asserts vectors are non-empty float arrays matching exactly 768 dimensions before database operations.
  - Zero key leakage: API keys remain encapsulated server-side and are never logged or returned to clients.

### 2. How Transcript Chunks Are Stored and Indexed
- **Ingestion & Persistence**: Time-aligned transcript segments are grouped into contiguous `KnowledgeChunk` entities in table `knowledge_chunks`.
- **Vector Storage**: Table `chunk_embeddings` (Alembic migration `7a8e9d1f3b20`) stores:
  - `chunk_id`: `VARCHAR(64)` FK to `knowledge_chunks.id` ON DELETE CASCADE.
  - `video_id`: `VARCHAR(64)` FK to `videos.id` ON DELETE CASCADE.
  - `user_id`: `VARCHAR(36)` FK to `users.id` ON DELETE CASCADE.
  - `embedding`: `vector(768)` pgvector column.
  - `model_name`: `VARCHAR(64)` e.g. `gemini-embedding-001`.
  - `dimension`: `INTEGER` e.g. 768.
  - Unique constraint `uq_chunk_embeddings_chunk_model` on `(chunk_id, model_name)`.
- **Controlled, Idempotent Indexing**: `IndexingService.index_video_chunks` queries only chunks lacking an embedding for the active model. Re-indexing an already-indexed video safely skips all chunks (0 new embeddings created).

### 3. How Vector Similarity Search Works
- **Distance Operator**: PostgreSQL pgvector `<=>` cosine distance operator (`ChunkEmbedding.embedding.cosine_distance(query_vector)`).
- **Similarity Calculation**: Linear transformation `similarity = 1.0 - cosine_distance` mapped to $[-1.0, 1.0]$.
- **Index Acceleration**: Accelerates search via HNSW index:
  `CREATE INDEX ix_chunk_embeddings_vector_hnsw ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);`
- **Filtering & Ordering**:
  - Filters by `user_id` and optional `video_id`.
  - Filters by `similarity >= similarity_threshold`.
  - Orders by `distance_expr.asc()` (highest similarity first) with `LIMIT top_k`.
  - Preserves exact source timestamps (`start_time`, `end_time`, and formatted MM:SS) for immediate YouTube player seek navigation.

### 4. How User Isolation Is Enforced
- **Database Level**: `user_id` is denormalized directly onto `chunk_embeddings` and indexed via `ix_chunk_embeddings_user_id` and composite `ix_chunk_embeddings_user_video`.
- **Query Level**: The search query in `EmbeddingRepository.search_similar_chunks` explicitly filters `WHERE ChunkEmbedding.user_id == user_id AND Video.user_id == user_id`.
- **IDOR Protection**: If a specific `video_id` is requested, `RetrievalService` verifies that the video exists and belongs to the authenticated user; unauthorized attempts return `404 Not Found`.

### 5. Verification and Test Results
- **Automated Test Suite**:
  - `tests/test_rag_and_embeddings.py`: 13/13 tests passed covering schema, model validation, batch embedding, duplicate prevention, ranking, thresholding, video scoping, and cross-user isolation.
  - `pytest -q`: All 139 backend tests passed.
- **Real Integration Test against PostgreSQL & Gemini**:
  - Generated live 768-dim embeddings using `gemini-embedding-001`.
  - Inserted 3 distinct knowledge chunks into PostgreSQL.
  - Query 1: Biological neuron signals $\rightarrow$ Top match Chunk 1 (`similarity = 0.8756`, `00:10 - 00:55`).
  - Query 2: Loss gradients & backprop $\rightarrow$ Top match Chunk 2 (`similarity = 0.7676`, `01:00 - 01:55`).
  - Query 3: Image filter convolutions $\rightarrow$ Top match Chunk 3 (`similarity = 0.7675`).
  - Idempotent re-indexing verified: `indexed = 0, already_indexed = 3`.
  - Cross-user retrieval isolation verified: User A querying for bread fermentation returned 0 chunks from User B's video.
- **API Behavior Verification**:
  - `POST /api/rag/index`: 401 unauthenticated, 404 on missing/foreign video, 200 on success, idempotent on second call.
  - `POST /api/rag/retrieve`: 401 unauthenticated, 422 on empty query/invalid top_k, 404 on foreign video ID, 200 with complete grounded timestamp response.

---

## Step 3: Ask VIDYORA — The Grounded AI Tutor

### 1. End-to-End Chat Request Flow
The Ask VIDYORA conversational experience orchestrates frontend presentation, authentication, pgvector RAG retrieval, Gemini synthesis, and user-isolated persistence:

1. **User Interaction**:
   - The learner navigates to the processed educational video workspace and selects the `💬 Ask VIDYORA` tab in the Study Suite.
   - The learner submits a question via the keyboard (`Enter`) or by clicking one of the suggested starter prompts.
2. **Frontend Dispatch**:
   - `AskVidyoraView.tsx` dispatches `POST /api/chat/ask` via `askVidyoraApi` in `frontend/src/services/aiApi.ts`, attaching the user's JWT bearer token in the `Authorization` header.
   - The UI displays an active thinking indicator while preserving the input state.
3. **Backend Authentication & IDOR Verification**:
   - FastAPI's `get_current_user` dependency validates the Bearer token, rejects unauthenticated requests (HTTP 401), and loads the authenticated `User` record.
   - `ChatService.ask_question` enforces strict video ownership via `VideoRepository.get_by_id(db, video_id, user_id)`. If the video does not exist or belongs to another student, it immediately rejects with HTTP 404 (preventing Insecure Direct Object Reference).
4. **Auto-Indexing & Semantic Retrieval**:
   - The service ensures any unembedded chunks are indexed into PostgreSQL pgvector (`IndexingService.index_video_chunks`).
   - `RetrievalService.retrieve_chunks` embeds the student's question and executes cosine similarity search over `chunk_embeddings` with `similarity_threshold = 0.30` and `top_k = 5`.
5. **Grounded Synthesis vs. Honest Limitation Refusal**:
   - **Case A (Evidence Found)**: Formats the retrieved chunks with moment index, timestamps, similarity, and transcript text into a prompt for Gemini with strict system grounding instructions (`temperature = 0.2`).
   - **Case B (Insufficient Evidence)**: If no chunks meet the threshold, Ask VIDYORA halts before invoking Gemini, immediately producing an honest acknowledgement: *"Based on this lecture's transcript, there is no direct discussion or sufficient evidence to answer your question."* with `sources = []`.
6. **Persistence & Return**:
   - Both question, answer, model name, and verified citations (chunk ID, chunk index, start/end timestamps, similarity percentage, snippet text) are persisted in the `chat_messages` table via `ChatRepository.save_message`.
   - The response is returned to the frontend as `AskVidyoraResponse`.
7. **Interactive Presentation & Seeking**:
   - The response renders with the Ask VIDYORA tutor avatar, model badge, formatted markdown/lists, and verified citations.
   - Clicking any citation timestamp triggers `onTimestampClick(start_time)`, which immediately seeks the embedded YouTube/video player to that exact moment.

### 2. How RAG Retrieval Provides Evidence to Gemini
- **Query Embedding**: The student's question is converted into a 768-dimensional dense vector using `text-embedding-004`.
- **User-Isolated Vector Matching**: `EmbeddingRepository.search_similar_chunks` queries pgvector using the `<=>` cosine distance operator, filtered by `user_id` and `video_id`.
- **Prompt Injection**: Only the top matching chunks (up to 5) that exceed the similarity cutoff (0.30) are injected into the Gemini prompt:
  ```
  [Moment #1 | Timestamp 00:15 - 00:45 | Relevance 92%]
  "Light reactions occur in the thylakoid membranes of chloroplasts..."
  ```
- **Context Economy**: Gemini receives only relevant excerpts rather than the full multi-hour lecture transcript, conserving tokens and preventing distraction from extraneous topics.

### 3. How Grounding and Source References Work
- **Strict Grounding Directive**: Gemini is instructed:
  - Base answers strictly and exclusively on provided transcript excerpts.
  - Never fabricate, extrapolate, or hallucinate facts absent from the spoken text.
  - State clearly when a topic is not discussed.
  - Explicitly reference timestamps (e.g., *"At [02:15], the instructor explains..."*).
- **Verified Citations**: The backend maps the exact pgvector chunks used as context into `ChatSourceCitation` objects returned with the answer.
- **Timestamp Integrity**: The start/end seconds and formatted `MM:SS` strings originate directly from the parsed transcript segments stored in PostgreSQL; timestamps are never generated or guessed by Gemini.

### 4. How Authentication and Ownership Are Enforced
- **Server-Derived Identity**: The client never supplies `user_id` in request payloads. The authenticated learner is derived exclusively from the verified JWT `sub` claim.
- **Tenant Scoping**: All database operations (`VideoRepository`, `EmbeddingRepository`, `ChatRepository`) filter on `user_id`.
- **Cascade Deletion**: The `chat_messages` table is bound to `users.id` and `videos.id` with `ondelete='CASCADE'`.
- **API Boundary Protection**:
  - `POST /api/chat/ask`: 401 unauthenticated, 404 foreign video, 422 empty inputs.
  - `GET /api/chat/{video_id}/history`: 401 unauthenticated, 404 foreign video, 200 user-isolated chronological history.
  - `DELETE /api/chat/{video_id}/history`: 401 unauthenticated, 404 foreign video, 200 clears only target user's messages for that video.

### 5. Verification and Test Results
- **Automated Backend Tests (`pytest backend/tests/test_ask_vidyora_chat.py`)**:
  - `test_ask_vidyora_unauthenticated_rejected`: 401 on missing JWT token (PASSED).
  - `test_ask_vidyora_input_validation`: 422 on empty or whitespace questions and video IDs (PASSED).
  - `test_ask_vidyora_ownership_enforcement`: 404 IDOR defense on foreign video access (PASSED).
  - `test_ask_vidyora_successful_grounded_answer`: Grounded synthesis with real timestamps (PASSED).
  - `test_ask_vidyora_empty_retrieval_insufficient_evidence`: Honest refusal on out-of-scope query without Gemini call (PASSED).
  - `test_ask_vidyora_gemini_rate_limit_error`: 429 quota exhaustion mapping (PASSED).
  - `test_ask_vidyora_gemini_timeout_error`: 504 gateway timeout mapping (PASSED).
  - `test_ask_vidyora_chat_history_and_isolation`: Chronological order and multi-tenant isolation (PASSED).
  - `test_ask_vidyora_clear_history`: Clears video messages cleanly (PASSED).
  - **Full Backend Suite**: All 148 backend tests passed in 16.39s with 0 regressions.
- **Frontend Quality**:
  - `npm run lint` (oxlint): 0 errors, 0 warnings across all 27 files.
  - `npm run build`: Vite + TypeScript production build succeeded in 786ms.
- **Browser Subagent Live Verification**:
  - Signed in as `student@vidyora.ai`.
  - Loaded processed lecture *"But what is a neural network? | Deep learning chapter 1"*.
  - Opened `💬 Ask VIDYORA` tab.
  - Asked: *"What are the core concepts explained in this lecture?"* $\rightarrow$ Received detailed, pedagogical grounded answer with 5 source citations (`08:08 - 09:17`, `15:22 - 16:26`, `07:03 - 08:07`, `09:18 - 10:23`, `02:19 - 03:34`) and similarity scores.
  - Clicked timestamp `09:18 - 10:23` $\rightarrow$ Video player smoothly seeked.
  - Asked out-of-scope question: *"What are the basic rules of cricket and how many players are on a team?"* $\rightarrow$ Ask VIDYORA honestly replied: *"Based on this video's lecture transcript, the basic rules of cricket and the number of players on a team are not discussed."*
  - Refreshed browser $\rightarrow$ Persistent history reloaded cleanly from PostgreSQL.

---

## Step 4: Build Personalized Learning Recovery

### 1. How Knowledge Gaps Are Identified
- **Deterministic Heuristics over Hallucinatory AI**: The engine evaluates real quiz attempt outcomes (`quiz_attempts`, `quiz_answers`) against source `knowledge_chunks`.
- **Distinguishing Unanswered vs. Incorrect Questions**:
  - Skipped / unanswered questions are classified distinctly from incorrect answers.
  - An unanswered question does not penalize a student as "weak" because omission reflects absence of assessment data rather than conceptual misunderstanding.
  - A concept is only flagged as `WEAK` when `accuracy < 0.60` and the student made at least 2 mistakes. If only 1 question was attempted and answered incorrectly, it is classified as `INSUFFICIENT_DATA` to prevent premature labeling.
- **Empirical Confidence Metrics**:
  - The diagnosis computes a visible, truthful `confidence_level` based on empirical observations:
    - `High (4+ observations)`: 4 or more questions answered on this concept.
    - `Moderate (2-3 observations)`: 2–3 questions answered.
    - `Low (1 observation)`: Exactly 1 question answered.
    - `None (0 answered)`: Unanswered/untested.
- **Recovery Status Tracking**:
  - `needs_review`: Flagged weak chunk without completed recovery.
  - `recovery_in_progress`: Active recovery session exists without submission.
  - `improvement_demonstrated`: Micro-quiz evaluated with score exceeding original accuracy.
  - `mastered`: Reassessed accuracy $\ge 80\%$.

### 2. How Recovery Connects to RAG and Ask VIDYORA
- **Context Grounding**: Selecting a knowledge gap passes the specific `chunk_id`, concept text, and timestamp window (`start_time`, `end_time`) directly to the Ask VIDYORA interface.
- **Interactive Player Seeking**: Clicking "Ask Tutor" or "Review in Video" dispatches `handleSeekTo(timestamp, true)`, scrolling the video player into view and seeking directly to the relevant lecture moment.
- **Grounded Clarification Flow**: Questions asked about a gap use the existing RAG embedding pipeline (`search_similar_chunks`) with pgvector cosine distance, grounding the AI explanation strictly in the lecture transcript.

### 3. How Reassessment Results Are Stored and Compared
- **Server-Side Scoring and Answer Security**:
  - The client submits only chosen option strings (`RecoveryAnswerItem`).
  - Answer keys and scoring formulas reside exclusively on the backend (`RecoveryService.record_evaluation`).
- **Persistence Across Tables**:
  - `learning_recovery_sessions`: Stores `pre_recovery_accuracy`, `post_recovery_accuracy`, `improvement_demonstrated` (boolean), `score` (e.g. 3/3), and `completed_at`.
  - `learner_progress`: Atomically upserts `mastery_score` (updated to post-recovery accuracy), increments `review_count`, sets `needs_revision = False`, and updates `last_reviewed_at`.
- **Session Reuse & Idempotency**:
  - If a learner already completed or started recovery for a chunk, `GET /api/videos/{video_id}/chunks/{chunk_id}/recovery` or `POST /api/recovery` with `reuse_existing=True` immediately returns the active or evaluated session without duplicate database records or unnecessary Gemini calls.
  - Submitting an already evaluated session is idempotent, preventing double-counting.

### 4. How User Isolation Is Enforced
- **JWT Authentication Required**: All endpoints (`GET /api/videos/{video_id}/gaps`, `POST /api/recovery`, `GET /api/videos/{video_id}/chunks/{chunk_id}/recovery`, `POST /api/recovery/{session_id}/evaluate`) require valid bearer tokens via `get_current_user`.
- **Tenant Scoping & IDOR Prevention**:
  - Recovery sessions belong to `user_id`. Queries in `RecoveryRepository` and `KnowledgeGapService` filter strictly by `user_id == current_user.id`.
  - Attempting to access or evaluate another user's recovery session raises HTTP 404 (or 403), strictly preventing cross-user data leakage.

### 5. Verification and Test Results
- **Automated Backend Tests (`pytest backend/tests/test_learning_recovery_workflow.py`)**:
  - `test_gap_distinction_incorrect_vs_unanswered`: Verifies skipped questions do not flag `WEAK` status (PASSED).
  - `test_confidence_level_computation`: Verifies empirical confidence categorization (`High`, `Moderate`, `Low`, `None`) (PASSED).
  - `test_recovery_session_creation_reuse_and_latest_endpoint`: Verifies session creation, reuse without regeneration, and chunk recovery endpoint (PASSED).
  - `test_recovery_evaluation_and_learner_progress_persistence`: Verifies server-side scoring, post-recovery accuracy, `LearnerProgress` upsert, and improvement metrics (PASSED).
  - `test_cross_user_isolation_for_recovery`: Verifies User B cannot view or submit User A's recovery session (404 IDOR defense) (PASSED).
  - `test_idempotent_recovery_submission`: Verifies repeated evaluation submissions do not corrupt progress or duplicate records (PASSED).
  - **Full Backend Suite**: All 156 backend tests passed in 43.73s with 0 regressions.
- **Frontend Code Quality**:
  - `npm run lint` (oxlint): 0 errors, 0 warnings across all 27 source files.
  - `npm run build`: TypeScript (`tsc -b`) and Vite production bundle succeeded in 878ms.
- **Live Browser Verification (`browser_subagent`)**:
  - Signed in as `recovery_tester@vidyora.ai`.
  - Loaded *"Photosynthesis & Energy Recovery Lecture"* workspace.
  - Completed initial quiz with 1 incorrect answer (Mitochondria) and 1 correct answer (Glucose and Oxygen).
  - Diagnosed knowledge gap card with `Low (1 observation)` confidence and `Needs Review` status.
  - Asked tutor follow-up in Ask VIDYORA with grounded concept context.
  - Started recovery, reviewed source transcript segment, completed 3-question targeted micro-quiz with 100% score (3/3).
  - Verified `Improvement Demonstrated` status and updated progress.
  - Refreshed browser and reloaded workspace from PostgreSQL to confirm persisted recovery state.

