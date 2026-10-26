import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from db.models import User, Video
from db.session import get_db
from repositories import FlashcardRepository, QuizRepository, VideoRepository
from models import (
    FlashcardsResponse,
    GenerateFlashcardsRequest,
    GenerateNotesRequest,
    GenerateQuizRequest,
    GenerateSummaryRequest,
    GeneratedQuizInternal,
    NotesResponse,
    PerformanceTier,
    QuestionResult,
    QuizAttemptHistoryResponse,
    QuizDifficulty,
    QuizEvaluationResponse,
    QuizResponse,
    QuizSubmissionRequest,
    SourceTimestamp,
    SummaryResponse,
    TranscriptSegment,
    VideoListItem,
    VideoListResponse,
    VideoMetadata,
    VideoPlatform,
    VideoProcessingStatus,
    VideoProcessRequest,
    VideoProcessResponse,
    VideoTranscript,
    VideoWorkspaceResponse,
    VideoKnowledgeGapsResponse,
    LearnerOverallKnowledgeGapsResponse,
    CreateRecoverySessionRequest,
    RecoverySessionClientView,
    RecoverySubmitRequest,
    RecoveryEvaluationResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    IndexVideoChunksRequest,
    IndexVideoChunksResponse,
    RagRetrieveRequest,
    RagRetrieveResponse,
    AskVidyoraRequest,
    AskVidyoraResponse,
    ChatHistoryResponse,
)
from services import (
    ChatService,
    IndexingService,
    KnowledgeGapService,
    QuizService,
    RecoveryService,
    RetrievalService,
    VideoService,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.gemini_service import (
    GeminiServiceError,
    convert_quiz_to_client_view,
    generate_flashcards,
    generate_quiz,
    generate_structured_notes,
    generate_video_summary,
)
from config import settings
from services.transcript_service import extract_youtube_transcript

logger = logging.getLogger(__name__)


# 1. Initialize the FastAPI application instance
app = FastAPI(
    title="VIDYORA AI API",
    description="Backend services for VIDYORA AI - AI-powered adaptive video learning platform",
    version="0.1.0",
)

# 2. Configure CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GeminiServiceError)
async def gemini_exception_handler(request: Request, exc: GeminiServiceError):
    """Handles domain-level Gemini AI exceptions with specific status codes."""
    logger.warning("Gemini service error on %s: %s (status=%d)", request.url.path, exc.message, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Preserves specific HTTP status codes and details for HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fallback handler to prevent unhandled 500s from dropping CORS headers."""
    logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected server error occurred while processing the request. Please try again."
        },
    )


# ---------------------------------------------------------------------------
# In-Memory Storage for Step 12 Quiz Sessions
# Note: This in-memory store acts as the temporary session cache for Step 12.
# It maintains the answer keys server-side to prevent client-side inspection.
# In a future production milestone, this will be replaced with persistent storage.
# ---------------------------------------------------------------------------
QUIZ_STORE: dict[str, GeneratedQuizInternal] = {}



# ---------------------------------------------------------------------------
# Helper Functions: Platform Detection and Identifier Resolution
# ---------------------------------------------------------------------------

def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube 11-character video ID if present in the URL."""
    patterns = [
        r"(?:v=|\/embed\/|\/watch\?v=|\/shorts\/|^youtu\.be\/|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"(?:v%3D)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def detect_platform(url: str) -> tuple[VideoPlatform, str]:
    """
    Detect video platform from URL and generate/extract a unique identifier.
    Returns a tuple of (VideoPlatform, video_id).
    """
    # 1. Check for YouTube
    youtube_id = extract_youtube_id(url)
    if youtube_id:
        return VideoPlatform.YOUTUBE, youtube_id

    # 2. Check for Direct Video Stream / File extensions
    if re.search(r'\.(mp4|webm|mkv|mov|avi)(\?.*)?$', url, re.IGNORECASE):
        file_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
        return VideoPlatform.DIRECT, f"vid_{file_hash}"

    # 3. Fallback for generic educational web sources
    web_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]
    return VideoPlatform.UNKNOWN, f"src_{web_hash}"


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

# 3. Root Endpoint (GET /)
@app.get("/", summary="Root API info", tags=["General"])
def read_root():
    """Welcome endpoint providing basic API metadata."""
    return {
        "message": "Welcome to VIDYORA AI API",
        "status": "online",
        "docs_url": "/docs",
    }


# 4. Health Check Endpoint (GET /health and GET /api/health)
@app.get("/health", summary="Health check", tags=["General"])
@app.get("/api/health", summary="Health check alias", tags=["General"])
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": "VIDYORA AI Backend",
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Authentication Endpoints (Step 16)
# ---------------------------------------------------------------------------

@app.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new learner account",
    tags=["Authentication"],
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new learner, securely hashes the password with bcrypt, and issues a JWT token."""
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    hashed_pw = hash_password(request.password)
    user = User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=hashed_pw,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
    )


@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate learner and obtain JWT",
    tags=["Authentication"],
)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticates a learner via email and password, returning a signed JWT access token."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
    )


@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated learner profile",
    tags=["Authentication"],
)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently authenticated learner."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


# 5. Video Processing Submission Endpoint (POST /api/videos/process)
@app.post(
    "/api/videos/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit video URL for processing",
    tags=["Videos"],
    description="Validates URL, constructs video metadata, and executes transcript extraction for YouTube educational videos.",
)
def process_video(
    request: VideoProcessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint to receive, validate, and process educational videos.
    Extracts time-aligned spoken transcripts for YouTube videos, assigning
    COMPLETED or FAILED lifecycle states based on caption availability,
    and persists all metadata, transcripts, and chunks into PostgreSQL with user ownership.
    """
    platform, raw_video_id = detect_platform(request.url)
    scoped_video_id = f"{raw_video_id}_{current_user.id.replace('-', '')[:12]}" if current_user else raw_video_id
    now = datetime.now(timezone.utc).isoformat()

    # If YouTube, execute transcript extraction pipeline
    if platform == VideoPlatform.YOUTUBE:
        result = extract_youtube_transcript(raw_video_id, request.url)
        updated_at = datetime.now(timezone.utc).isoformat()

        if result.success and result.transcript:
            # Re-scope transcript chunks to scoped_video_id
            for chk in result.transcript.chunks:
                chk.video_id = scoped_video_id
                chk.chunk_id = f"chk_{scoped_video_id}_{chk.chunk_index}"
            result.transcript.video_id = scoped_video_id

            # Transactionally persist Video, VideoTranscript, TranscriptSegments, and KnowledgeChunks
            VideoRepository.save_processed_video(
                db=db,
                video_id=scoped_video_id,
                url=request.url,
                platform=platform.value,
                title=result.title,
                transcript_data=result.transcript,
                user_id=current_user.id if current_user else None,
            )

            metadata = VideoMetadata(
                id=scoped_video_id,
                url=request.url,
                platform=platform,
                title=result.title,
                status=VideoProcessingStatus.COMPLETED,
                created_at=now,
                updated_at=updated_at,
                error_message=None,
                transcript=result.transcript,
            )
            return VideoProcessResponse(
                status=VideoProcessingStatus.COMPLETED,
                message=f"Transcript processed, chunked, and persisted successfully ({result.transcript.cleaned_segment_count} segments -> {result.transcript.chunk_count} chunks, {len(result.transcript.full_text.split())} words).",
                video=metadata,
            )

        else:
            # Persist failure record into PostgreSQL
            VideoRepository.save_failed_video(
                db=db,
                video_id=scoped_video_id,
                url=request.url,
                platform=platform.value,
                title=result.title,
                error_message=result.error_message or "Transcript extraction failed.",
                user_id=current_user.id if current_user else None,
            )

            metadata = VideoMetadata(
                id=scoped_video_id,
                url=request.url,
                platform=platform,
                title=result.title,
                status=VideoProcessingStatus.FAILED,
                created_at=now,
                updated_at=updated_at,
                error_message=result.error_message,
                transcript=None,
            )
            return VideoProcessResponse(
                status=VideoProcessingStatus.FAILED,
                message=result.error_message or "Transcript extraction failed.",
                video=metadata,
            )

    # Fallback for direct stream or unknown web sources
    VideoRepository.save_accepted_video(
        db=db,
        video_id=scoped_video_id,
        url=request.url,
        platform=platform.value,
        user_id=current_user.id if current_user else None,
    )

    metadata = VideoMetadata(
        id=scoped_video_id,
        url=request.url,
        platform=platform,
        title=None,
        status=VideoProcessingStatus.ACCEPTED,
        created_at=now,
        updated_at=now,
        error_message=None,
        transcript=None,
    )

    return VideoProcessResponse(
        status=VideoProcessingStatus.ACCEPTED,
        message="Video URL validated and registered. Automated transcript extraction is currently enabled for YouTube.",
        video=metadata,
    )


# 6. Persistent Read: List Processed Videos (GET /api/videos)
@app.get(
    "/api/videos",
    response_model=VideoListResponse,
    status_code=status.HTTP_200_OK,
    summary="List persisted educational videos",
    tags=["Videos"],
    description="Returns a lightweight summary of previously processed videos from PostgreSQL for the current authenticated user.",
)
def list_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves stored videos with transcript status, chunk count, quiz existence,
    and flashcard deck presence in a single optimized aggregate query scoped to current_user.
    """
    return VideoService.list_persisted_videos(db, user_id=current_user.id if current_user else None)


# 7. Persistent Read: Get Complete Video Workspace (GET /api/videos/{video_id})
@app.get(
    "/api/videos/{video_id}",
    response_model=VideoWorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete educational video workspace",
    tags=["Videos"],
    description="Loads a previously processed video, transcript segments, knowledge chunks, latest quiz, and flashcards directly from PostgreSQL.",
)
def get_video_workspace(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Restores the complete educational workspace for a video.
    Does NOT call YouTube transcript APIs or Gemini.
    Returns HTTP 404 if the video has not been ingested or does not belong to the user.
    """
    workspace = VideoService.get_video_workspace(db, video_id, user_id=current_user.id if current_user else None)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found in Vidyora database.",
        )
    return workspace


# 8. Persistent Read: Video Knowledge Gap Analysis (GET /api/videos/{video_id}/knowledge-gaps)
@app.get(
    "/api/videos/{video_id}/knowledge-gaps",
    response_model=VideoKnowledgeGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze chunk-level knowledge gaps for a video",
    tags=["Learner Analytics"],
    description="Deterministically identifies concept weaknesses, mastery tiers, and longitudinal trends for all chunks in a video based on quiz history.",
)
def get_video_knowledge_gaps(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Computes explainable chunk-level knowledge gaps from PostgreSQL attempt records.
    Returns HTTP 404 if the video has not been ingested or is not owned by the user.
    """
    gaps_response = KnowledgeGapService.analyze_video_knowledge_gaps(
        db, video_id, user_id=current_user.id if current_user else None
    )
    if gaps_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found.",
        )
    return gaps_response


# 9. Persistent Read: Overall Learner Knowledge Gap Profile (GET /api/learners/knowledge-gaps)
@app.get(
    "/api/learners/knowledge-gaps",
    response_model=LearnerOverallKnowledgeGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve cross-video learner knowledge gap profile",
    tags=["Learner Analytics"],
    description="Aggregates conceptual weaknesses across all assessed lectures for the authenticated learner.",
)
def get_learner_knowledge_gaps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates longitudinal mastery metrics across all videos for the current learner.
    """
    return KnowledgeGapService.analyze_learner_overall_gaps(
        db, user_id=current_user.id if current_user else None
    )


# 10. Persistent Read: Specific Learner Knowledge Gap Profile (GET /api/learners/{user_id}/knowledge-gaps)
@app.get(
    "/api/learners/{user_id}/knowledge-gaps",
    response_model=LearnerOverallKnowledgeGapsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve knowledge gap profile for a specific learner",
    tags=["Learner Analytics"],
    description="Aggregates conceptual weaknesses across all assessed lectures for the specified user_id with IDOR protection.",
)
def get_specific_learner_knowledge_gaps(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates longitudinal mastery metrics across all videos for a specific user ID.
    Enforces that learners cannot inspect other learners' mastery profiles (IDOR protection).
    """
    if current_user and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to another learner's knowledge profile.",
        )
    return KnowledgeGapService.analyze_learner_overall_gaps(db, user_id=user_id)


# ---------------------------------------------------------------------------
# Step 14 Phase 3: Targeted Learning Recovery Engine Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/recovery",
    response_model=RecoverySessionClientView,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate targeted learning recovery for a weak concept",
    tags=["Learning Recovery"],
    description="Generates a source-grounded remediation session with explanation, worked example, and micro-quiz for an identified knowledge gap.",
)
def create_recovery_session(
    request: CreateRecoverySessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates an evidence-grounded recovery session.
    Server holds correct answers and explanations securely until submission.
    """
    return RecoveryService.create_recovery_session(
        db=db,
        video_id=request.video_id,
        chunk_id=request.chunk_id,
        user_id=current_user.id if current_user else request.user_id,
        reuse_existing=request.reuse_existing,
    )


@app.get(
    "/api/recovery/{session_id}",
    response_model=RecoverySessionClientView,
    status_code=status.HTTP_200_OK,
    summary="Retrieve learning recovery session",
    tags=["Learning Recovery"],
    description="Retrieves a recovery session. If evaluated, includes evaluation metrics and answers; otherwise answer keys are omitted.",
)
def get_recovery_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the current state of a recovery session with user ownership checks.
    """
    return RecoveryService.get_recovery_session(
        db=db, session_id=session_id, user_id=current_user.id if current_user else None
    )


@app.post(
    "/api/recovery/{session_id}/submit",
    response_model=RecoveryEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit recovery micro-quiz for deterministic grading",
    tags=["Learning Recovery"],
    description="Deterministically grades learner responses against server-held answer keys, compares pre vs post accuracy, and determines recovery outcome.",
)
def submit_recovery_session(
    session_id: str,
    request: RecoverySubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits answers for a recovery session.
    Evaluates deterministically on backend and stores answers in PostgreSQL.
    """
    return RecoveryService.evaluate_recovery_session(
        db=db,
        session_id=session_id,
        request=request,
        user_id=current_user.id if current_user else None,
    )


@app.get(
    "/api/videos/{video_id}/chunks/{chunk_id}/recovery",
    response_model=Optional[RecoverySessionClientView],
    status_code=status.HTTP_200_OK,
    summary="Retrieve latest learning recovery session for a chunk",
    tags=["Learning Recovery"],
    description="Retrieves the most recent recovery session for a specific knowledge chunk.",
)
def get_latest_chunk_recovery(
    video_id: str,
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the latest recovery session for a chunk belonging to the authenticated user.
    """
    video = VideoRepository.get_by_id(db, video_id, user_id=current_user.id if current_user else None)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found.",
        )
    return RecoveryService.get_latest_session_for_chunk(
        db=db,
        video_id=video_id,
        chunk_id=chunk_id,
        user_id=current_user.id if current_user else None,
    )


@app.get(
    "/api/videos/{video_id}/chunks/{chunk_id}/recovery-history",
    response_model=list[RecoverySessionClientView],
    status_code=status.HTTP_200_OK,
    summary="Retrieve recovery history for a chunk",
    tags=["Learning Recovery"],
    description="Retrieves all historical recovery attempts for a specific knowledge chunk.",
)
def get_chunk_recovery_history(
    video_id: str,
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns historical recovery interventions for a chunk belonging to the authenticated user.
    """
    video = VideoRepository.get_by_id(db, video_id, user_id=current_user.id if current_user else None)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found.",
        )
    return RecoveryService.get_chunk_recovery_history(
        db=db,
        video_id=video_id,
        chunk_id=chunk_id,
        user_id=current_user.id if current_user else None,
    )


# 11. AI Video Summary Endpoint (POST /api/ai/summary)
@app.post(
    "/api/ai/summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI video summary",
    tags=["AI Generation"],
    description="Transforms processed video transcript chunks into a structured, source-grounded video summary using Gemini.",
)
def create_summary(
    request: GenerateSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyzes time-aligned knowledge chunks and generates an overview,
    core concepts, bullet takeaways, and beginner explanation.
    """
    existing_video = db.query(Video).filter(Video.id == request.video_id).first()
    if existing_video and existing_video.user_id and current_user and existing_video.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{request.video_id}' not found.",
        )
    summary, model_used = generate_video_summary(
        video_id=request.video_id,
        title=request.title,
        chunks=request.chunks,
    )
    return SummaryResponse(
        status="completed",
        video_id=request.video_id,
        summary=summary,
        model_used=model_used,
        chunk_count=len(request.chunks),
    )


# 7. AI Structured Notes Endpoint (POST /api/ai/notes)
@app.post(
    "/api/ai/notes",
    response_model=NotesResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI structured study notes",
    tags=["AI Generation"],
    description="Transforms processed video transcript chunks into comprehensive, structured lecture study notes using Gemini.",
)
def create_notes(
    request: GenerateNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyzes time-aligned knowledge chunks and generates structured outline,
    introductory framing, section breakdowns, and terminology glossary.
    """
    existing_video = db.query(Video).filter(Video.id == request.video_id).first()
    if existing_video and existing_video.user_id and current_user and existing_video.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{request.video_id}' not found.",
        )
    notes, model_used = generate_structured_notes(
        video_id=request.video_id,
        title=request.title,
        chunks=request.chunks,
    )
    return NotesResponse(
        status="completed",
        video_id=request.video_id,
        notes=notes,
        model_used=model_used,
        chunk_count=len(request.chunks),
    )


# 8. AI Multiple-Choice Quiz Endpoint (POST /api/ai/quiz)
@app.post(
    "/api/ai/quiz",
    response_model=QuizResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI multiple-choice quiz",
    tags=["AI Generation"],
    description="Generates an interactive, source-grounded multiple choice quiz from knowledge chunks using Gemini and persists it to PostgreSQL.",
)
def create_quiz(
    request: GenerateQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a structured quiz from transcript knowledge chunks.
    Persists the full quiz with answer keys in PostgreSQL, caches in QUIZ_STORE,
    and returns a sanitized QuizClientView omitting answers to the browser.
    """
    existing_video = db.query(Video).filter(Video.id == request.video_id).first()
    if existing_video and existing_video.user_id and current_user and existing_video.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{request.video_id}' not found.",
        )
    internal_quiz, model_used = generate_quiz(
        video_id=request.video_id,
        title=request.title,
        chunks=request.chunks,
        num_questions=request.num_questions,
    )

    # Persist full answer key and questions securely to PostgreSQL if video exists
    if existing_video:
        QuizRepository.save_quiz(
            db=db,
            internal_quiz=internal_quiz,
            model_used=model_used,
            user_id=current_user.id if current_user else None,
        )

    # Maintain temporary in-memory store for cache / backward compatibility
    QUIZ_STORE[internal_quiz.quiz_id] = internal_quiz

    # Build safe client view with correct_answer and explanation omitted
    client_view = convert_quiz_to_client_view(internal_quiz)

    return QuizResponse(
        status="completed",
        video_id=request.video_id,
        quiz=client_view,
        model_used=model_used,
        chunk_count=len(request.chunks),
    )


# 9. AI Quiz Evaluation Endpoint (POST /api/ai/quiz/evaluate)
@app.post(
    "/api/ai/quiz/evaluate",
    response_model=QuizEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate learner quiz submission",
    tags=["AI Generation"],
    description="Deterministically grades learner answers against server-held answer key and persists attempt in PostgreSQL.",
)
def evaluate_quiz(
    request: QuizSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates submitted answers deterministically, categorizing the learner into
    adaptive performance tiers, identifying weak knowledge chunks for review,
    and persisting the attempt and answer details to PostgreSQL.
    """
    # 1. Retrieve quiz from PostgreSQL first; fallback to in-memory store if needed
    db_quiz = QuizRepository.get_quiz_by_id(db, request.quiz_id, user_id=current_user.id if current_user else None)
    cached_quiz = QUIZ_STORE.get(request.quiz_id)

    if not db_quiz and not cached_quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz session '{request.quiz_id}' not found or expired. Please generate a new quiz.",
        )

    # Determine question items and structure
    if db_quiz and db_quiz.questions:
        questions_source = []
        for q in db_quiz.questions:
            orig_id = q.id.replace(f"{db_quiz.id}_", "", 1) if q.id.startswith(f"{db_quiz.id}_") else q.id
            questions_source.append({
                "id": orig_id,
                "db_id": q.id,
                "question": q.question_text,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "difficulty": QuizDifficulty(q.difficulty),
                "source_timestamp": SourceTimestamp(
                    timestamp=q.source_timestamp,
                    formatted_time=q.source_formatted_time,
                    label=q.source_label,
                ),
                "source_chunk_id": q.source_chunk_id,
            })
        target_quiz_id = db_quiz.id
    else:
        # Fallback to cached in-memory quiz
        questions_source = [
            {
                "id": q.id,
                "db_id": f"{cached_quiz.quiz_id}_{q.id}",
                "question": q.question,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "difficulty": q.difficulty,
                "source_timestamp": q.source_timestamp,
                "source_chunk_id": q.source_chunk_id,
            }
            for q in cached_quiz.questions
        ]
        target_quiz_id = cached_quiz.quiz_id
        # Also ensure saved in database for future persistence
        QuizRepository.save_quiz(
            db,
            cached_quiz,
            model_used="cached",
            user_id=current_user.id if current_user else None,
        )

    # Validate submitted question IDs and answer options (matching on either id or db_id)
    valid_q_map = {}
    for q in questions_source:
        valid_q_map[q["id"]] = q
        valid_q_map[q["db_id"]] = q

    for q_id, chosen_answer in request.selected_answers.items():
        if q_id not in valid_q_map:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown question ID '{q_id}' submitted.",
            )
        q_obj = valid_q_map[q_id]
        if chosen_answer is not None and chosen_answer not in q_obj["options"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid answer choice for question '{q_id}'. Must be one of the provided options.",
            )

    total_questions = len(questions_source)
    correct_count = 0
    question_results: list[QuestionResult] = []
    weak_chunk_ids: list[str] = []
    answers_for_db = []

    for q in questions_source:
        chosen = request.selected_answers.get(q["id"])
        if chosen is None:
            chosen = request.selected_answers.get(q["db_id"])

        is_correct = (chosen == q["correct_answer"])
        if is_correct:
            correct_count += 1
        else:
            if q["source_chunk_id"] and q["source_chunk_id"] not in weak_chunk_ids:
                weak_chunk_ids.append(q["source_chunk_id"])

        question_results.append(
            QuestionResult(
                question_id=q["id"],
                question=q["question"],
                selected_answer=chosen,
                correct_answer=q["correct_answer"],
                is_correct=is_correct,
                explanation=q["explanation"],
                difficulty=q["difficulty"],
                source_timestamp=q["source_timestamp"],
                source_chunk_id=q["source_chunk_id"],
            )
        )

        answers_for_db.append({
            "question_id": q["db_id"],
            "selected_answer": chosen,
            "is_correct": is_correct,
        })

    score_percentage = round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0.0

    if score_percentage >= 80.0:
        tier = PerformanceTier.STRONG
        summary = f"Excellent mastery! You scored {correct_count}/{total_questions} ({score_percentage}%). You have a strong grasp of the core concepts in this lecture."
    elif score_percentage >= 60.0:
        tier = PerformanceTier.DEVELOPING
        summary = f"Good progress! You scored {correct_count}/{total_questions} ({score_percentage}%). Review the flagged concepts and timestamps below to strengthen your understanding."
    else:
        tier = PerformanceTier.NEEDS_REVISION
        summary = f"Needs revision. You scored {correct_count}/{total_questions} ({score_percentage}%). We recommend re-watching the specific video moments highlighted in your results."

    # Persist attempt and answers to PostgreSQL
    try:
        QuizRepository.save_quiz_attempt(
            db=db,
            quiz_id=target_quiz_id,
            total_questions=total_questions,
            correct_count=correct_count,
            score_percentage=score_percentage,
            performance_tier=tier.value,
            performance_summary=summary,
            weak_chunk_ids=weak_chunk_ids,
            question_answers=answers_for_db,
            user_id=current_user.id if current_user else None,
        )
    except Exception as exc:
        logger.warning("Could not persist quiz attempt to database: %s", exc)

    return QuizEvaluationResponse(
        quiz_id=request.quiz_id,
        total_questions=total_questions,
        correct_count=correct_count,
        score_percentage=score_percentage,
        performance_tier=tier,
        performance_summary=summary,
        question_results=question_results,
        weak_chunk_ids=weak_chunk_ids,
    )


# 11. Persistent Read: Quiz Attempt History (GET /api/quizzes/{quiz_id}/attempts)
@app.get(
    "/api/quizzes/{quiz_id}/attempts",
    response_model=QuizAttemptHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get historical quiz attempts",
    tags=["AI Generation"],
    description="Retrieves historical evaluations and learner progress for a persisted quiz from PostgreSQL.",
)
def get_quiz_attempts(
    quiz_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the progression history of all attempts for a quiz.
    Returns HTTP 404 if the quiz does not exist or does not belong to the current user.
    Returns HTTP 200 with an empty list if the quiz exists but has 0 attempts.
    """
    history = QuizService.get_quiz_attempts(db, quiz_id, user_id=current_user.id if current_user else None)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz '{quiz_id}' not found.",
        )
    return history


# 12. AI Flashcard Deck Endpoint (POST /api/ai/flashcards)
@app.post(
    "/api/ai/flashcards",
    response_model=FlashcardsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI active-recall flashcards",
    tags=["AI Generation"],
    description="Transforms processed video transcript chunks into high-yield conceptual flashcards for active recall study and persists to PostgreSQL.",
)
def create_flashcards(
    request: GenerateFlashcardsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyzes knowledge chunks and synthesizes high-yield conceptual flashcards,
    persisting the deck and individual cards to PostgreSQL while preserving source timestamps.
    """
    existing_video = db.query(Video).filter(Video.id == request.video_id).first()
    if existing_video and existing_video.user_id and current_user and existing_video.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{request.video_id}' not found.",
        )

    flashcards, model_used = generate_flashcards(
        video_id=request.video_id,
        title=request.title,
        chunks=request.chunks,
        num_cards=request.num_cards,
    )

    # Persist deck and cards to PostgreSQL if video exists in database
    if existing_video:
        FlashcardRepository.save_flashcard_deck(
            db=db,
            video_id=request.video_id,
            topic=flashcards.topic,
            cards=flashcards.cards,
            model_used=model_used,
            user_id=current_user.id if current_user else None,
        )

    return FlashcardsResponse(
        status="completed",
        video_id=request.video_id,
        flashcards=flashcards,
        model_used=model_used,
        chunk_count=len(request.chunks),
    )


# ===========================================================================
# 11. Step 17: RAG & Vector Retrieval Endpoints
# ===========================================================================

@app.post(
    "/api/rag/index",
    response_model=IndexVideoChunksResponse,
    status_code=status.HTTP_200_OK,
    summary="Index Knowledge Chunks into pgvector",
    tags=["RAG & Retrieval"],
    description="Generates and persists dense vector embeddings for any unembedded chunks of a user's video.",
)
def index_video_chunks(
    request: IndexVideoChunksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Idempotently indexes knowledge chunks for the specified video into pgvector.
    Strictly verifies ownership by current_user.
    """
    return IndexingService.index_video_chunks(
        db=db,
        video_id=request.video_id,
        user_id=current_user.id,
    )


@app.post(
    "/api/rag/retrieve",
    response_model=RagRetrieveResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic similarity search over knowledge chunks",
    tags=["RAG & Retrieval"],
    description="Embeds the search query and performs cosine distance vector search over user-owned chunks in pgvector.",
)
def retrieve_relevant_chunks(
    request: RagRetrieveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves semantically relevant knowledge chunks matching the query.
    Enforces user isolation, returns similarity scores, and preserves exact source timestamps.
    """
    return RetrievalService.retrieve_chunks(
        db=db,
        user_id=current_user.id,
        request=request,
    )


# ===========================================================================
# 12. Step 3: Ask VIDYORA Grounded AI Tutor Endpoints
# ===========================================================================

@app.post(
    "/api/chat/ask",
    response_model=AskVidyoraResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask VIDYORA grounded question",
    tags=["Ask VIDYORA Chat"],
    description="Asks an educational question against a video lecture and receives an answer strictly grounded in transcript chunks.",
)
def ask_vidyora_question(
    request: AskVidyoraRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits a student question grounded in the video's transcript.
    Retrieves vector-similar chunks and generates a grounded response with citations.
    """
    return ChatService.ask_question(
        db=db,
        user_id=current_user.id,
        request=request,
    )


@app.get(
    "/api/chat/{video_id}/history",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ask VIDYORA chat history for video",
    tags=["Ask VIDYORA Chat"],
    description="Fetches chronological chat history between student and Ask VIDYORA for a specific video.",
)
def get_chat_history(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns user-scoped chat history with source citations for the requested video.
    """
    return ChatService.get_chat_history(
        db=db,
        user_id=current_user.id,
        video_id=video_id,
    )


@app.delete(
    "/api/chat/{video_id}/history",
    status_code=status.HTTP_200_OK,
    summary="Clear Ask VIDYORA chat history for video",
    tags=["Ask VIDYORA Chat"],
    description="Deletes all chat messages for a specific video belonging to the authenticated student.",
)
def clear_chat_history(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Clears all chat history for the user on this video.
    """
    return ChatService.clear_chat_history(
        db=db,
        user_id=current_user.id,
        video_id=video_id,
    )



