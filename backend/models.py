import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, field_validator, computed_field, Field, model_validator


# ---------------------------------------------------------------------------
# Enums: Video Platform and Processing Lifecycle States
# ---------------------------------------------------------------------------

class VideoPlatform(str, Enum):
    """Supported video platforms for VIDYORA AI knowledge extraction."""
    YOUTUBE = "youtube"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class VideoProcessingStatus(str, Enum):
    """
    Explicit lifecycle states for video processing.
    
    Valid Transitions:
      SUBMITTED -> VALIDATING -> ACCEPTED -> PROCESSING -> COMPLETED
                                         \-> FAILED     \-> FAILED
    """
    SUBMITTED = "submitted"      # Initial URL receipt
    VALIDATING = "validating"    # Syntax and accessibility checks in progress
    ACCEPTED = "accepted"        # Validated and registered; queued for transcript extraction
    PROCESSING = "processing"    # Downstream AI / transcript extraction actively running
    COMPLETED = "completed"      # Notes, chunks, and assessments successfully generated
    FAILED = "failed"            # Error encountered during validation or extraction


# ---------------------------------------------------------------------------
# Pydantic Schemas / Data Models
# ---------------------------------------------------------------------------

class TranscriptSegment(BaseModel):
    """
    A single time-aligned caption snippet from the educational video.
    
    Fields:
      - text: Spoken text content within this interval.
      - start: Timestamp in seconds indicating when this segment begins.
      - duration: Duration of this segment in seconds.
    """
    text: str
    start: float
    duration: float


class TranscriptChunk(BaseModel):
    """
    A cohesive, contextual block of transcript text aggregated from contiguous
    cleaned segments, structured for future RAG retrieval and citation grounding.
    
    Index convention:
      - segment_start_index: Zero-based, inclusive index into cleaned_segments.
      - segment_end_index: Zero-based, inclusive index into cleaned_segments.
    """
    chunk_id: str
    chunk_index: int
    video_id: str
    text: str
    start_time: float
    end_time: float
    duration: float
    word_count: int
    segment_start_index: int
    segment_end_index: int


class VideoTranscript(BaseModel):
    """
    Structured transcript data representing the spoken educational content.
    
    Fields:
      - video_id: Unique video identifier.
      - language: Language code (e.g., 'en').
      - is_generated: True if automatically generated (ASR), False if manual creator captions.
      - full_text: Continuous aggregated spoken text.
      - segments: Ordered list of original raw time-aligned caption segments (backward-compatible).
      - segment_count: Total number of raw transcript segments.
      - cleaned_segments: Normalized speech segments with noise/filler markers removed.
      - cleaned_segment_count: Count of valid cleaned segments.
      - chunks: Contiguous semantic knowledge chunks for RAG and downstream AI.
      - chunk_count: Total number of generated chunks.
    """
    video_id: str
    language: str
    is_generated: bool
    full_text: str
    segments: list[TranscriptSegment]
    segment_count: int
    cleaned_segments: list[TranscriptSegment] = []
    cleaned_segment_count: int = 0
    chunks: list[TranscriptChunk] = []
    chunk_count: int = 0



class VideoMetadata(BaseModel):
    """
    Structured metadata representing an educational video entity in VIDYORA AI.
    
    Fields:
      - id: Unique video identifier (e.g. YouTube 11-char ID or generated token).
      - url: The original normalized video URL.
      - platform: Detected platform (e.g., youtube, direct, unknown).
      - title: Video title (extracted via YouTube metadata or oEmbed).
      - status: Current lifecycle state.
      - created_at: UTC timestamp when the video was first submitted.
      - updated_at: UTC timestamp when metadata/status was last modified.
      - error_message: Descriptive explanation if status is FAILED.
      - transcript: Structured time-aligned transcript if successfully extracted.
    """
    id: str
    url: str
    platform: VideoPlatform
    title: Optional[str] = None
    status: VideoProcessingStatus
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    transcript: Optional[VideoTranscript] = None


class VideoProcessRequest(BaseModel):
    """Request payload for submitting an educational video URL."""
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Video URL cannot be empty.")

        # Validate URL scheme (http/https) and standard hostname structure
        url_pattern = re.compile(
            r'^(https?:\/\/)'                     # http:// or https://
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'     # domain name
            r'(:\d+)?(\/.*)?$',                    # optional port and path
            re.IGNORECASE
        )
        if not url_pattern.match(trimmed):
            raise ValueError("Please provide a valid HTTP or HTTPS URL (e.g., https://www.youtube.com/watch?v=...).")

        return trimmed


class VideoProcessResponse(BaseModel):
    """
    Structured API response returned to the client upon video submission.
    Encapsulates lifecycle status, user message, and full video metadata.
    Includes backward-compatible computed fields for legacy clients.
    """
    status: VideoProcessingStatus
    message: str
    video: VideoMetadata

    @computed_field
    @property
    def video_url(self) -> str:
        return self.video.url

    @computed_field
    @property
    def video_id(self) -> Optional[str]:
        return self.video.id

    @computed_field
    @property
    def received_at(self) -> str:
        return self.video.created_at


# ---------------------------------------------------------------------------
# Step 11: AI-Powered Summarization and Structured Notes Models
# ---------------------------------------------------------------------------

class SourceTimestamp(BaseModel):
    """
    Time citation grounding AI insights into specific video moments.
    """
    timestamp: float
    formatted_time: str
    label: str

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: float) -> float:
        if v < 0:
            return 0.0
        return round(v, 2)


class VideoSummary(BaseModel):
    """
    Structured, beginner-friendly summary grounded in the video transcript.
    """
    overview: str
    main_concepts: list[str]
    takeaways: list[str]
    beginner_explanation: str
    source_timestamps: list[SourceTimestamp] = []


class TerminologyItem(BaseModel):
    """A key domain term defined in context of the lecture."""
    term: str
    definition: str
    context: Optional[str] = None


class NoteSection(BaseModel):
    """A cohesive conceptual section within the lecture notes."""
    title: str
    summary: str
    key_points: list[str]
    start_time: Optional[float] = None
    formatted_time: Optional[str] = None


class StructuredNotes(BaseModel):
    """
    Hierarchical, structured learning notes synthesizing educational video content.
    """
    topic_title: str
    introduction: str
    main_concepts: list[str]
    sections: list[NoteSection]
    terminology: list[TerminologyItem] = []
    examples: list[str] = []
    key_takeaways: list[str]
    relevant_timestamps: list[SourceTimestamp] = []


class GenerateSummaryRequest(BaseModel):
    """Request payload for generating an AI video summary."""
    video_id: str
    title: Optional[str] = None
    chunks: list[TranscriptChunk]
    full_text: Optional[str] = None

    @field_validator("chunks")
    @classmethod
    def validate_chunks(cls, v: list[TranscriptChunk]) -> list[TranscriptChunk]:
        if not v:
            raise ValueError("At least one transcript chunk is required for AI generation.")
        return v


class SummaryResponse(BaseModel):
    """API response envelope for video summary generation."""
    status: str = "completed"
    video_id: str
    summary: VideoSummary
    model_used: str
    chunk_count: int


class GenerateNotesRequest(BaseModel):
    """Request payload for generating structured study notes."""
    video_id: str
    title: Optional[str] = None
    chunks: list[TranscriptChunk]
    full_text: Optional[str] = None

    @field_validator("chunks")
    @classmethod
    def validate_chunks(cls, v: list[TranscriptChunk]) -> list[TranscriptChunk]:
        if not v:
            raise ValueError("At least one transcript chunk is required for AI generation.")
        return v


class NotesResponse(BaseModel):
    """API response envelope for structured notes generation."""
    status: str = "completed"
    video_id: str
    notes: StructuredNotes
    model_used: str
    chunk_count: int


# ---------------------------------------------------------------------------
# Step 12: AI-Powered Adaptive Quiz and Flashcard Data Models
# ---------------------------------------------------------------------------

class QuizDifficulty(str, Enum):
    """Pedagogical difficulty tiers for generated questions and flashcards."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class PerformanceTier(str, Enum):
    """Adaptive learning tier classification based on quiz evaluation score."""
    STRONG = "Strong"              # >= 80%
    DEVELOPING = "Developing"      # 60% - 79.9%
    NEEDS_REVISION = "Needs Revision"  # < 60%


class QuizQuestionInternal(BaseModel):
    """
    Complete quiz question generated by Gemini.
    Held securely on the backend; correct_answer and explanation are never
    sent to the browser prior to learner submission.
    """
    id: str
    question: str
    options: list[str]
    correct_answer: str
    explanation: str
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM
    source_timestamp: SourceTimestamp
    source_chunk_id: Optional[str] = None

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str]) -> list[str]:
        if len(v) != 4:
            raise ValueError("Each quiz question must contain exactly 4 options.")
        cleaned = [opt.strip() for opt in v if opt.strip()]
        if len(cleaned) != 4:
            raise ValueError("All 4 options must be non-empty strings.")
        if len(set(cleaned)) != 4:
            raise ValueError("All 4 options must be unique.")
        return cleaned

    @field_validator("correct_answer")
    @classmethod
    def validate_correct_answer(cls, v: str, info) -> str:
        options = info.data.get("options", [])
        stripped = v.strip()
        if options and stripped not in options:
            raise ValueError(f"correct_answer '{stripped}' must exactly match one of the 4 options: {options}")
        return stripped


class GeneratedQuizInternal(BaseModel):
    """
    Internal structured quiz with full answer key and rationales.
    Cached on the server and indexed by quiz_id for deterministic evaluation.
    """
    quiz_id: str
    video_id: str
    title: str
    instructions: str
    questions: list[QuizQuestionInternal]


class QuizQuestionClient(BaseModel):
    """
    Sanitized quiz question delivered to the frontend for learner answering.
    Omission of correct_answer and explanation protects quiz integrity.
    """
    id: str
    question: str
    options: list[str]
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM
    source_timestamp: SourceTimestamp
    source_chunk_id: Optional[str] = None


class QuizClientView(BaseModel):
    """Safe, client-facing quiz representation."""
    quiz_id: str
    video_id: str
    title: str
    instructions: str
    questions: list[QuizQuestionClient]
    question_count: int


class GenerateQuizRequest(BaseModel):
    """Request payload for triggering AI quiz generation."""
    video_id: str
    title: Optional[str] = None
    chunks: list[TranscriptChunk]
    num_questions: int = 5

    @field_validator("chunks")
    @classmethod
    def validate_chunks(cls, v: list[TranscriptChunk]) -> list[TranscriptChunk]:
        if not v:
            raise ValueError("At least one transcript chunk is required for quiz generation.")
        return v

    @field_validator("num_questions")
    @classmethod
    def validate_num_questions(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("num_questions must be between 1 and 20.")
        return v


class QuizResponse(BaseModel):
    """API response envelope returned when a quiz is generated."""
    status: str = "completed"
    video_id: str
    quiz: QuizClientView
    model_used: str
    chunk_count: int


class QuizSubmissionRequest(BaseModel):
    """Payload sent by learner submitting their answers for grading."""
    quiz_id: str
    selected_answers: dict[str, str]  # question_id -> chosen option


class QuestionResult(BaseModel):
    """Detailed grading review for a single question returned after submission."""
    question_id: str
    question: str
    selected_answer: Optional[str] = None
    correct_answer: str
    is_correct: bool
    explanation: str
    difficulty: QuizDifficulty
    source_timestamp: SourceTimestamp
    source_chunk_id: Optional[str] = None


class QuizEvaluationResponse(BaseModel):
    """Complete adaptive performance analysis returned after quiz submission."""
    quiz_id: str
    total_questions: int
    correct_count: int
    score_percentage: float
    performance_tier: PerformanceTier
    performance_summary: str
    question_results: list[QuestionResult]
    weak_chunk_ids: list[str] = []


class Flashcard(BaseModel):
    """Source-grounded educational flashcard."""
    id: str
    front: str
    back: str
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM
    source_timestamp: SourceTimestamp
    source_chunk_id: Optional[str] = None


class GeneratedFlashcards(BaseModel):
    """Collection of high-yield conceptual flashcards."""
    topic: str
    cards: list[Flashcard]
    card_count: int


class GenerateFlashcardsRequest(BaseModel):
    """Request payload for triggering AI flashcard generation."""
    video_id: str
    title: Optional[str] = None
    chunks: list[TranscriptChunk]
    num_cards: int = 8

    @field_validator("chunks")
    @classmethod
    def validate_chunks(cls, v: list[TranscriptChunk]) -> list[TranscriptChunk]:
        if not v:
            raise ValueError("At least one transcript chunk is required for flashcard generation.")
        return v

    @field_validator("num_cards")
    @classmethod
    def validate_num_cards(cls, v: int) -> int:
        if v < 1 or v > 25:
            raise ValueError("num_cards must be between 1 and 25.")
        return v


class FlashcardsResponse(BaseModel):
    """API response envelope returned when flashcards are generated."""
    status: str = "completed"
    video_id: str
    flashcards: GeneratedFlashcards
    model_used: str
    chunk_count: int


# ---------------------------------------------------------------------------
# Step 13 Phase 4: Persistent Read & History Models
# ---------------------------------------------------------------------------

class VideoListItem(BaseModel):
    """Lightweight projection of a persisted video for the library view."""
    video_id: str
    platform: VideoPlatform
    url: str
    title: Optional[str] = None
    status: VideoProcessingStatus
    created_at: str
    updated_at: str
    segment_count: int = 0
    chunk_count: int = 0
    has_transcript: bool = False
    has_quiz: bool = False
    has_flashcards: bool = False


class VideoListResponse(BaseModel):
    """Enveloping response for GET /api/videos."""
    videos: list[VideoListItem]
    total_count: int


class VideoWorkspaceResponse(BaseModel):
    """
    Complete persisted workspace for an educational video loaded directly
    from PostgreSQL without triggering external YouTube or Gemini calls.
    """
    video: VideoMetadata
    latest_quiz: Optional[QuizClientView] = None
    latest_flashcards: Optional[GeneratedFlashcards] = None
    summary: Optional[VideoSummary] = None
    notes: Optional[StructuredNotes] = None
    available_quizzes_count: int = 0
    available_decks_count: int = 0


class QuizAttemptAnswerHistory(BaseModel):
    """Historical answer record for a single question in an attempt."""
    question_id: str
    selected_answer: Optional[str] = None
    is_correct: bool


class QuizAttemptHistoryItem(BaseModel):
    """A single historical quiz attempt record."""
    attempt_id: str
    quiz_id: str
    score: int
    total_questions: int
    score_percentage: float
    performance_tier: PerformanceTier
    performance_summary: Optional[str] = None
    weak_chunk_ids: list[str] = []
    submitted_at: str
    answers: list[QuizAttemptAnswerHistory] = []


class QuizAttemptHistoryResponse(BaseModel):
    """Response envelope for GET /api/quizzes/{quiz_id}/attempts."""
    quiz_id: str
    total_attempts: int
    attempts: list[QuizAttemptHistoryItem]


# ---------------------------------------------------------------------------
# Step 14 Phase 1: Deterministic Learner Knowledge Gap Engine Models
# ---------------------------------------------------------------------------

class KnowledgeGapClassification(str, Enum):
    """Deterministic classification of learner conceptual mastery per chunk."""
    STRONG = "STRONG"
    DEVELOPING = "DEVELOPING"
    WEAK = "WEAK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PerformanceTrend(str, Enum):
    """Longitudinal performance trajectory derived from chronologically ordered attempts."""
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ChunkKnowledgeGap(BaseModel):
    """
    Granular, evidence-grounded performance profile for an individual knowledge chunk.
    Enables explainable, deterministic detection of repeated learner weaknesses.
    """
    chunk_id: str
    chunk_index: int
    video_id: str
    source_timestamp: SourceTimestamp
    classification: KnowledgeGapClassification
    trend: PerformanceTrend
    accuracy: float
    total_observations: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int = 0
    concept_name: Optional[str] = None
    recommended_action: Optional[str] = None
    recovery_status: Optional[str] = None
    confidence_level: Optional[str] = None
    recovery_session_id: Optional[str] = None
    distinct_attempts_count: int
    most_recent_result: Optional[bool] = None
    most_recent_attempt_at: Optional[str] = None
    consecutive_incorrect_count: int = 0
    consecutive_correct_count: int = 0
    has_demonstrated_mastery: bool = False
    reason: str
    chunk_summary_text: Optional[str] = None
    latest_recovery_result: Optional[str] = None
    has_recovered: bool = False


class VideoKnowledgeGapSummary(BaseModel):
    """Aggregated mastery metrics across analyzed knowledge chunks."""
    total_chunks: int
    assessed_chunks: int
    weak_chunks_count: int
    developing_chunks_count: int
    strong_chunks_count: int
    insufficient_data_count: int
    overall_accuracy: float
    recovered_chunks_count: int = 0
    recovery_in_progress_count: int = 0


class VideoKnowledgeGapsResponse(BaseModel):
    """Response envelope for GET /api/videos/{video_id}/knowledge-gaps."""
    video_id: str
    summary: VideoKnowledgeGapSummary
    weak_chunk_ids: list[str]
    gaps: list[ChunkKnowledgeGap]


class LearnerOverallKnowledgeGapsResponse(BaseModel):
    """Response envelope for GET /api/learners/knowledge-gaps."""
    user_id: Optional[str] = None
    summary: VideoKnowledgeGapSummary
    weak_chunk_ids: list[str]
    gaps: list[ChunkKnowledgeGap]
    videos_analyzed: int


# ---------------------------------------------------------------------------
# Step 14 Phase 3: Targeted Learning Recovery Engine Models
# ---------------------------------------------------------------------------

class RecoverySessionStatus(str, Enum):
    """Lifecycle states of an evidence-grounded learning recovery session."""
    CREATED = "CREATED"
    EXPLANATION_GENERATED = "EXPLANATION_GENERATED"
    QUIZ_READY = "QUIZ_READY"
    IN_PROGRESS = "IN_PROGRESS"
    EVALUATED = "EVALUATED"


class RecoveryResultEnum(str, Enum):
    """
    Deterministic outcome of a recovery intervention evaluated against
    explicit engineering thresholds and baseline accuracy.
    """
    RECOVERED = "RECOVERED"
    IMPROVED = "IMPROVED"
    NOT_RECOVERED = "NOT_RECOVERED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TargetedExplanationResponse(BaseModel):
    """Source-grounded explanation and worked example generated by Gemini."""
    title: str
    explanation: str
    worked_example: Optional[str] = None
    key_takeaway: str


class RecoveryInterventionInternal(BaseModel):
    """
    Internal structured schema for Gemini recovery intervention output.
    Combines targeted explanation and a focused micro-quiz.
    """
    title: str
    explanation: str
    worked_example: Optional[str] = None
    key_takeaway: str
    questions: list[QuizQuestionInternal]


class RecoveryQuestionResult(BaseModel):
    """Detailed grading review for a single recovery micro-quiz question."""
    question_id: str
    question: str
    selected_answer: Optional[str] = None
    correct_answer: str
    is_correct: bool
    explanation: str
    source_timestamp: SourceTimestamp


class CreateRecoverySessionRequest(BaseModel):
    """Request payload to initiate a targeted learning recovery intervention."""
    video_id: str
    chunk_id: str
    user_id: Optional[str] = None
    reuse_existing: bool = False


class RecoverySessionClientView(BaseModel):
    """
    Sanitized client-facing representation of a learning recovery session.
    Protects quiz integrity by omitting correct answers and explanations before submission.
    When EVALUATED, includes full evaluation results and question reviews.
    """
    id: str
    video_id: str
    chunk_id: str
    chunk_index: int
    source_timestamp: SourceTimestamp
    originating_evidence: str
    attempt_number: int
    status: RecoverySessionStatus
    explanation_title: Optional[str] = None
    targeted_explanation: Optional[str] = None
    worked_example: Optional[str] = None
    key_takeaway: Optional[str] = None
    micro_quiz: list[QuizQuestionClient] = []
    pre_recovery_accuracy: float
    chunk_text: Optional[str] = None
    post_recovery_accuracy: Optional[float] = None
    absolute_improvement: Optional[float] = None
    recovery_result: Optional[RecoveryResultEnum] = None
    result_summary: Optional[str] = None
    question_results: list[RecoveryQuestionResult] = []
    can_retry: bool = False
    evaluated_at: Optional[str] = None


class RecoverySubmitRequest(BaseModel):
    """Payload submitted by the learner for recovery micro-quiz grading."""
    selected_answers: dict[str, str]  # question_id -> chosen option


class RecoveryEvaluationResponse(BaseModel):
    """
    Complete deterministic evaluation of a learning recovery attempt,
    comparing baseline pre-recovery accuracy with post-recovery performance.
    """
    session_id: str
    video_id: str
    chunk_id: str
    attempt_number: int
    total_questions: int
    correct_count: int
    pre_recovery_accuracy: float
    post_recovery_accuracy: float
    absolute_improvement: float
    recovery_result: RecoveryResultEnum
    result_summary: str
    question_results: list[RecoveryQuestionResult]
    can_retry: bool
    evaluated_at: str


# ---------------------------------------------------------------------------
# Step 16: Authentication & Multi-User Isolation Models
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """Request payload for new learner registration."""
    email: str
    password: str
    full_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not trimmed or "@" not in trimmed or "." not in trimmed.split("@")[-1]:
            raise ValueError("Please provide a valid email address.")
        return trimmed

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLoginRequest(BaseModel):
    """Request payload for learner authentication."""
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    """Sanitized public representation of an authenticated user entity (never exposes password hash)."""
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: str


class TokenResponse(BaseModel):
    """Envelope returned upon successful authentication containing JWT and user profile."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------------------------
# Step 17: RAG, Embeddings & Vector Retrieval Models
# ---------------------------------------------------------------------------

class RagRetrieveRequest(BaseModel):
    """Request payload for semantic knowledge chunk retrieval."""
    query: str = Field(..., min_length=1, description="Natural language search or question query.")
    video_id: Optional[str] = Field(None, description="Optional video ID to scope retrieval to a specific lecture.")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of relevant chunks to retrieve.")
    similarity_threshold: Optional[float] = Field(
        default=0.0, ge=-1.0, le=1.0, description="Minimum cosine similarity threshold for retrieved results."
    )


class RetrievedChunkResult(BaseModel):
    """Single semantically retrieved knowledge chunk with similarity score and timestamp grounding."""
    chunk_id: str
    video_id: str
    chunk_index: int
    text: str
    similarity: float
    start_time: float
    end_time: float
    source_formatted_start: str
    source_formatted_end: str
    video_title: Optional[str] = None


class RagRetrieveResponse(BaseModel):
    """Complete response payload for semantic retrieval query."""
    query: str
    results_count: int
    results: list[RetrievedChunkResult]


class IndexVideoChunksRequest(BaseModel):
    """Request to generate embeddings for a video's knowledge chunks."""
    video_id: str


class IndexVideoChunksResponse(BaseModel):
    """Response payload detailing embedding generation outcome for video chunks."""
    video_id: str
    indexed_chunks: int
    already_indexed_chunks: int
    total_chunks: int
    model_used: str


# ---------------------------------------------------------------------------
# Step 18: Ask VIDYORA - Grounded Conversational AI Tutor Models
# ---------------------------------------------------------------------------

class ChatSourceCitation(BaseModel):
    """Source reference grounded in a retrieved knowledge chunk with seekable timestamps."""
    chunk_id: str
    chunk_index: int
    start_time: float
    end_time: float
    source_formatted_start: str
    source_formatted_end: str
    similarity: float
    text: str


class AskVidyoraRequest(BaseModel):
    """Request payload for student asking a question about a processed video lecture."""
    video_id: str = Field(..., min_length=1, description="Target educational video ID.")
    question: str = Field(..., min_length=1, max_length=2000, description="Student question regarding the lecture.")


class AskVidyoraResponse(BaseModel):
    """Response payload from Ask VIDYORA containing grounded answer and verified citations."""
    id: str
    video_id: str
    question: str
    answer: str
    sources: list[ChatSourceCitation]
    model_used: str
    created_at: Union[str, datetime]


class ChatHistoryResponse(BaseModel):
    """Envelope containing persistent conversation history for a video and authenticated user."""
    video_id: str
    messages: list[AskVidyoraResponse]
    total_messages: int = 0
    total_count: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def populate_counts(cls, data: Any):
        if isinstance(data, dict):
            if "total_messages" in data and ("total_count" not in data or data["total_count"] is None):
                data["total_count"] = data["total_messages"]
            elif "total_count" in data and ("total_messages" not in data or data["total_messages"] is None):
                data["total_messages"] = data["total_count"]
        return data




