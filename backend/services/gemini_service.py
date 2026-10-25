"""
VIDYORA AI - Gemini AI Service Layer

Encapsulates all interaction with Google's Gemini Developer API via the official
`google-genai` Python SDK. Enforces strict prompt grounding, structured Pydantic
output, source timestamp validation, and comprehensive error mapping.
"""

import json
import logging
import uuid
from typing import List, Optional, Tuple

from config import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError
from models import (
    Flashcard,
    GeneratedFlashcards,
    GeneratedQuizInternal,
    NoteSection,
    QuizClientView,
    QuizDifficulty,
    QuizQuestionClient,
    QuizQuestionInternal,
    RecoveryInterventionInternal,
    SourceTimestamp,
    StructuredNotes,
    TerminologyItem,
    TranscriptChunk,
    VideoSummary,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Domain Exceptions for Safe Application Error Mapping
# ---------------------------------------------------------------------------

class GeminiServiceError(Exception):
    """Base exception for Gemini service operations."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GeminiConfigurationError(GeminiServiceError):
    """Raised when GEMINI_API_KEY is missing or invalid."""
    def __init__(self, message: str = "Google Gemini API key is not configured. Please set GEMINI_API_KEY in your backend .env file."):
        super().__init__(message, status_code=503)


class GeminiRateLimitError(GeminiServiceError):
    """Raised when rate limits or quotas are exceeded (HTTP 429)."""
    def __init__(self, message: str = "Gemini API rate limit or quota exceeded. Please wait a moment and try again."):
        super().__init__(message, status_code=429)


class GeminiTimeoutError(GeminiServiceError):
    """Raised when a request to Gemini times out."""
    def __init__(self, message: str = "Request to Gemini API timed out while generating educational content."):
        super().__init__(message, status_code=504)


class GeminiValidationError(GeminiServiceError):
    """Raised when model response fails schema or grounding validation."""
    def __init__(self, message: str = "Failed to validate structured AI response against the expected schema."):
        super().__init__(message, status_code=502)


# ---------------------------------------------------------------------------
# Client Factory
# ---------------------------------------------------------------------------

def get_gemini_client() -> genai.Client:
    """
    Initializes and returns the official Google GenAI client.
    Raises GeminiConfigurationError if the API key is missing.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        logger.error("Attempted Gemini API call without GEMINI_API_KEY configured.")
        raise GeminiConfigurationError()

    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.exception("Failed to initialize Google GenAI Client: %s", exc)
        raise GeminiConfigurationError(f"Failed to initialize Gemini Client: {str(exc)}")


# ---------------------------------------------------------------------------
# Timestamp Formatting and Grounding Helpers
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS string."""
    total_seconds = max(0, int(round(seconds)))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_chunks_context(chunks: List[TranscriptChunk]) -> str:
    """
    Assembles time-aligned knowledge chunks into structured contextual blocks
    for the model prompt, preserving chunk IDs and time bounds.
    """
    lines = []
    for chunk in chunks:
        start_fmt = format_timestamp(chunk.start_time)
        end_fmt = format_timestamp(chunk.end_time)
        lines.append(
            f"[{chunk.chunk_id} | {start_fmt} - {end_fmt} | start_seconds: {chunk.start_time:.1f}]\n"
            f"{chunk.text}\n"
        )
    return "\n".join(lines)


def sanitize_source_timestamps(
    timestamps: List[SourceTimestamp],
    chunks: List[TranscriptChunk],
) -> List[SourceTimestamp]:
    """
    Validates and clamps source timestamps to ensure they fall within the video's
    actual timeline and adhere to consistent formatting.
    """
    if not chunks:
        return []

    min_time = 0.0
    max_time = max(c.end_time for c in chunks) + 2.0  # slight tolerance

    sanitized = []
    for ts in timestamps:
        safe_time = max(min_time, min(ts.timestamp, max_time))
        safe_fmt = format_timestamp(safe_time)
        sanitized.append(
            SourceTimestamp(
                timestamp=round(safe_time, 2),
                formatted_time=safe_fmt,
                label=ts.label.strip() or f"Discussion at {safe_fmt}",
            )
        )
    return sanitized


# ---------------------------------------------------------------------------
# Prompt Engineering (Strict Source Grounding & Anti-Hallucination)
# ---------------------------------------------------------------------------

SYSTEM_GROUNDING_INSTRUCTION = (
    "You are VIDYORA AI, an expert educational intelligence assistant designed to help students learn deeply.\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. Base all explanations, concepts, and takeaways EXCLUSIVELY on the provided transcript text and chunks.\n"
    "2. Do NOT invent, assume, or extrapolate facts, scientific claims, or historical details absent from the spoken text.\n"
    "3. You do NOT have visual access to the video stream. Never refer to 'on-screen graphics', 'the presenter is wearing', or 'the slides show'. Only reference what was spoken.\n"
    "4. Cite timestamps accurately using the provided chunk start times.\n"
    "5. If a topic is briefly mentioned or unclear in the transcript, state that the transcript only briefly touched upon it rather than inventing details.\n"
)


def build_summary_prompt(
    title: Optional[str],
    chunks_context: str,
) -> str:
    video_title = title or "Educational Lecture / Video"
    return (
        f"Video Title: {video_title}\n\n"
        "Analyze the following time-aligned transcript chunks and generate a comprehensive, beginner-friendly video summary.\n\n"
        "Requirements:\n"
        "- overview: A cohesive 2-3 paragraph synthesis summarizing what the lesson covers.\n"
        "- main_concepts: A list of 4-8 core concepts explained in the lecture.\n"
        "- takeaways: 3-6 actionable, memorable bullet takeaways.\n"
        "- beginner_explanation: An intuitive, plain-English 'ELI5' explanation of the core subject suitable for a complete beginner.\n"
        "- source_timestamps: A list of key timestamps from the transcript where crucial concepts were introduced.\n\n"
        "TRANSCRIPT KNOWLEDGE CHUNKS:\n"
        f"{chunks_context}\n"
    )


def build_notes_prompt(
    title: Optional[str],
    chunks_context: str,
) -> str:
    video_title = title or "Educational Lecture / Video"
    return (
        f"Video Title: {video_title}\n\n"
        "Analyze the following time-aligned transcript chunks and generate structured, comprehensive study notes.\n\n"
        "Requirements:\n"
        "- topic_title: Clear academic or conceptual title for the notes.\n"
        "- introduction: Clear 1-2 paragraph introduction framing the lesson's scope.\n"
        "- main_concepts: List of major thematic concepts.\n"
        "- sections: Chronological or logical breakdown of the lecture sections. Each section must have a descriptive title, a thorough summary, 3-5 key_points, and the starting timestamp.\n"
        "- terminology: Important domain-specific terms, definitions, and context derived from the lesson.\n"
        "- examples: Concrete real-world examples or demonstrations mentioned by the speaker in the transcript.\n"
        "- key_takeaways: 4-7 high-value study takeaways.\n"
        "- relevant_timestamps: Key video timestamps mapping to major milestone moments.\n\n"
        "TRANSCRIPT KNOWLEDGE CHUNKS:\n"
        f"{chunks_context}\n"
    )


def build_quiz_prompt(
    title: Optional[str],
    chunks_context: str,
    num_questions: int = 5,
) -> str:
    """Constructs a strict, source-grounded prompt for quiz generation."""
    video_title = title or "Educational Lecture / Video"
    return (
        f"Video Title: {video_title}\n\n"
        f"Analyze the following time-aligned transcript knowledge chunks and generate an interactive educational quiz consisting of exactly {num_questions} multiple-choice questions.\n\n"
        "CRITICAL QUIZ RULES:\n"
        "1. Every question must test a meaningful concept, mechanism, or principle directly discussed in the transcript chunks.\n"
        "2. Do NOT invent facts or extrapolate beyond the spoken content.\n"
        "3. Provide exactly 4 options per question. All 4 options must be unique, non-empty, and plausible.\n"
        "4. 'correct_answer' MUST exactly match one of the 4 strings in 'options'.\n"
        "5. 'explanation' must clearly explain why the answer is correct with direct reference to the video lecture context.\n"
        "6. Assign a pedagogical difficulty ('easy', 'medium', or 'hard') to each question.\n"
        "7. Assign 'source_timestamp' with the video timestamp (seconds and formatted MM:SS) where the concept is introduced.\n"
        "8. Assign 'source_chunk_id' referencing the chunk_id (e.g. vid_chunk_001) where the question is grounded.\n"
        "9. Avoid duplicate, trivial, or ambiguous questions.\n\n"
        "TRANSCRIPT KNOWLEDGE CHUNKS:\n"
        f"{chunks_context}\n"
    )


def build_flashcards_prompt(
    title: Optional[str],
    chunks_context: str,
    num_cards: int = 8,
) -> str:
    """Constructs a strict, concept-focused prompt for flashcard deck generation."""
    video_title = title or "Educational Lecture / Video"
    return (
        f"Video Title: {video_title}\n\n"
        f"Analyze the following time-aligned transcript knowledge chunks and generate a deck of {num_cards} high-yield conceptual flashcards for active recall study.\n\n"
        "CRITICAL FLASHCARD RULES:\n"
        "1. Focus each card on a core term, principle, relationship, or mechanism explained in the transcript.\n"
        "2. 'front': A focused conceptual question, term, or active recall prompt.\n"
        "3. 'back': A clear, authoritative explanation or definition grounded strictly in what the speaker explained.\n"
        "4. Assign 'difficulty' ('easy', 'medium', or 'hard').\n"
        "5. Assign 'source_timestamp' with the video timestamp where this concept is taught.\n"
        "6. Assign 'source_chunk_id' referencing the corresponding knowledge chunk.\n"
        "7. Avoid duplicate flashcards or trivia absent from the lecture.\n\n"
        "TRANSCRIPT KNOWLEDGE CHUNKS:\n"
        f"{chunks_context}\n"
    )


def build_recovery_prompt(
    video_title: Optional[str],
    weak_chunk: TranscriptChunk,
    context_chunks: List[TranscriptChunk],
    originating_evidence: str,
    attempt_number: int = 1,
    num_questions: int = 3,
) -> str:
    """Constructs a strict, source-grounded prompt for targeted learning recovery."""
    title = video_title or "Educational Lecture"
    start_fmt = format_timestamp(weak_chunk.start_time)
    end_fmt = format_timestamp(weak_chunk.end_time)

    context_text = ""
    if context_chunks:
        context_text = (
            "NARROWLY RELATED SURROUNDING CHUNKS (For Context Only):\n"
            f"{build_chunks_context(context_chunks)}\n\n"
        )

    if attempt_number <= 1:
        pedagogical_guidance = (
            "PEDAGOGICAL INSTRUCTION (Attempt 1 - Conceptual Grounding & Example):\n"
            "- Explain the core concept step-by-step at an accessible level.\n"
            "- Provide a clear, concrete worked example or analogy based on the speaker's explanation.\n"
            "- Address the specific conceptual hurdle indicated by the learner's prior mistakes.\n"
        )
    else:
        pedagogical_guidance = (
            f"PEDAGOGICAL INSTRUCTION (Attempt {attempt_number} - Misconception Contrast & Simplified Remediation):\n"
            "- The learner previously struggled with this concept. Provide a simplified, crystal-clear explanation.\n"
            "- Explicitly contrast the common misconception or pitfall with the correct principle from the transcript.\n"
            "- Provide different questions targeting this specific distinction.\n"
        )

    return (
        f"Video Title: {title}\n"
        f"TARGET WEAK CONCEPT (Chunk Index: {weak_chunk.chunk_index + 1}, Timestamp: {start_fmt} - {end_fmt}):\n"
        f"[{weak_chunk.chunk_id} | {start_fmt} - {end_fmt}]\n"
        f"{weak_chunk.text}\n\n"
        f"{context_text}"
        f"PRIOR ASSESSMENT EVIDENCE OF DIFFICULTY:\n"
        f"\"{originating_evidence}\"\n\n"
        f"{pedagogical_guidance}\n"
        "STRICT RECOVERY REQUIREMENTS:\n"
        "1. GROUNDING: Base your explanation, worked example, and micro-quiz EXCLUSIVELY on the provided weak chunk.\n"
        "2. ANTI-HALLUCINATION: Do NOT introduce external theories, facts, or assumptions not discussed by the speaker.\n"
        "3. TITLE: Concise, descriptive title for the weak concept.\n"
        "4. EXPLANATION: 2-3 focused paragraphs breaking down the concept and directly addressing why learners struggle.\n"
        "5. WORKED_EXAMPLE: Concrete walk-through or real-world example referenced in or directly illustrating the spoken text.\n"
        "6. KEY_TAKEAWAY: 1-2 sentence memorable takeaway summarizing the core principle.\n"
        f"7. MICRO_QUIZ: Exactly {num_questions} targeted multiple-choice questions testing this specific concept.\n"
        "   - Exactly 4 unique, non-empty options per question.\n"
        "   - 'correct_answer' must EXACTLY match one of the 4 options.\n"
        "   - 'explanation' must explain why the answer is correct referencing the transcript.\n"
        "   - 'difficulty' must be 'easy', 'medium', or 'hard'.\n"
        f"   - 'source_timestamp' timestamp must be between {weak_chunk.start_time:.1f} and {weak_chunk.end_time:.1f}.\n"
        f"   - 'source_chunk_id' must be '{weak_chunk.chunk_id}'.\n"
    )


# ---------------------------------------------------------------------------
# Error Translation Layer
# ---------------------------------------------------------------------------

def handle_gemini_error(exc: Exception) -> None:
    """
    Maps provider-level SDK errors into clean, typed application exceptions.
    """
    logger.exception("Gemini API call failed: %s", exc)

    if isinstance(exc, GeminiServiceError):
        raise exc

    if isinstance(exc, (ValueError, ValidationError)):
        raise GeminiValidationError(f"Failed to validate structured AI response against the expected schema: {str(exc)}")

    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", 500)
        message = str(exc)

        if code == 429 or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
            raise GeminiRateLimitError("Gemini API rate limit or quota exceeded. Please wait a few moments before trying again.")
        if code == 403 or "API_KEY_INVALID" in message or "PERMISSION_DENIED" in message:
            raise GeminiConfigurationError("The configured Gemini API key is invalid or lacks necessary permissions.")
        if code == 400:
            raise GeminiValidationError(f"Invalid request sent to Gemini: {message}")
        if code in (500, 502, 503, 504):
            raise GeminiServiceError("Gemini service is temporarily unavailable. Please retry in a few moments.", status_code=503)

        raise GeminiServiceError(f"Gemini API returned error: {message}", status_code=code)

    err_str = str(exc).lower()
    if "timeout" in err_str or "timed out" in err_str:
        raise GeminiTimeoutError("Request to Gemini API timed out.")

    raise GeminiServiceError(f"An unexpected error occurred during AI generation: {str(exc)}", status_code=500)


# ---------------------------------------------------------------------------
# Service Operations: Summary and Notes Generation
# ---------------------------------------------------------------------------

def generate_video_summary(
    video_id: str,
    title: Optional[str],
    chunks: List[TranscriptChunk],
) -> Tuple[VideoSummary, str]:
    """
    Generates a structured, source-grounded VideoSummary using Gemini.
    Returns a tuple of (VideoSummary, model_used).
    """
    if not chunks:
        raise ValueError("Cannot generate summary without transcript chunks.")

    client = get_gemini_client()
    model_name = settings.gemini_model
    chunks_context = build_chunks_context(chunks)
    prompt = build_summary_prompt(title, chunks_context)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=VideoSummary,
        temperature=0.2,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiValidationError("Gemini returned an empty response.")

        # Double-check validation through Pydantic
        summary_obj = VideoSummary.model_validate_json(raw_text)
        # Ground and sanitize timestamps
        summary_obj.source_timestamps = sanitize_source_timestamps(
            summary_obj.source_timestamps, chunks
        )

        return summary_obj, model_name

    except Exception as exc:
        handle_gemini_error(exc)


def generate_structured_notes(
    video_id: str,
    title: Optional[str],
    chunks: List[TranscriptChunk],
) -> Tuple[StructuredNotes, str]:
    """
    Generates structured, hierarchical study notes using Gemini.
    Returns a tuple of (StructuredNotes, model_used).
    """
    if not chunks:
        raise ValueError("Cannot generate structured notes without transcript chunks.")

    client = get_gemini_client()
    model_name = settings.gemini_model
    chunks_context = build_chunks_context(chunks)
    prompt = build_notes_prompt(title, chunks_context)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=StructuredNotes,
        temperature=0.25,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiValidationError("Gemini returned an empty response.")

        # Double-check validation through Pydantic
        notes_obj = StructuredNotes.model_validate_json(raw_text)

        # Sanitize and format timestamps in sections
        min_time = 0.0
        max_time = max(c.end_time for c in chunks) + 2.0
        for section in notes_obj.sections:
            if section.start_time is not None:
                safe_time = max(min_time, min(section.start_time, max_time))
                section.start_time = round(safe_time, 2)
                section.formatted_time = format_timestamp(safe_time)

        # Sanitize relevant milestone timestamps
        notes_obj.relevant_timestamps = sanitize_source_timestamps(
            notes_obj.relevant_timestamps, chunks
        )

        return notes_obj, model_name

    except Exception as exc:
        handle_gemini_error(exc)


# ---------------------------------------------------------------------------
# Step 12: Quiz and Flashcard Service Operations
# ---------------------------------------------------------------------------

def find_matching_chunk_id(
    timestamp: float,
    chunks: List[TranscriptChunk],
    candidate_id: Optional[str] = None,
) -> Optional[str]:
    """
    Resolves or validates the best-matching chunk_id for a given timestamp.
    If candidate_id is already present and matches a valid chunk in `chunks`,
    it is preserved. Otherwise, searches for the chunk encompassing the timestamp.
    """
    if not chunks:
        return candidate_id

    valid_ids = {c.chunk_id for c in chunks}
    if candidate_id and candidate_id in valid_ids:
        return candidate_id

    for c in chunks:
        if c.start_time <= timestamp <= c.end_time:
            return c.chunk_id

    # Fallback to nearest chunk by start_time
    nearest = min(chunks, key=lambda c: abs(c.start_time - timestamp))
    return nearest.chunk_id


def convert_quiz_to_client_view(internal_quiz: GeneratedQuizInternal) -> QuizClientView:
    """
    Converts an internal quiz into a sanitized client view by omitting
    correct_answer and explanation, preserving quiz integrity before grading.
    """
    client_questions = [
        QuizQuestionClient(
            id=q.id,
            question=q.question,
            options=q.options,
            difficulty=q.difficulty,
            source_timestamp=q.source_timestamp,
            source_chunk_id=q.source_chunk_id,
        )
        for q in internal_quiz.questions
    ]
    return QuizClientView(
        quiz_id=internal_quiz.quiz_id,
        video_id=internal_quiz.video_id,
        title=internal_quiz.title,
        instructions=internal_quiz.instructions,
        questions=client_questions,
        question_count=len(client_questions),
    )


def generate_quiz(
    video_id: str,
    title: Optional[str],
    chunks: List[TranscriptChunk],
    num_questions: int = 5,
) -> Tuple[GeneratedQuizInternal, str]:
    """
    Generates an interactive, source-grounded multiple-choice quiz using Gemini.
    Returns a tuple of (GeneratedQuizInternal, model_used).
    """
    if not chunks:
        raise ValueError("Cannot generate quiz without transcript chunks.")

    client = get_gemini_client()
    model_name = settings.gemini_model
    chunks_context = build_chunks_context(chunks)
    prompt = build_quiz_prompt(title, chunks_context, num_questions=num_questions)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=GeneratedQuizInternal,
        temperature=0.2,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiValidationError("Gemini returned an empty response.")

        quiz_obj = GeneratedQuizInternal.model_validate_json(raw_text)

        # Enforce unique, non-placeholder quiz_id and correct video_id
        if not quiz_obj.quiz_id or quiz_obj.quiz_id in ("string", "quiz_id"):
            quiz_obj.quiz_id = f"quiz_{uuid.uuid4().hex[:12]}"
        quiz_obj.video_id = video_id

        # Sanitize question IDs, timestamps, and chunk citations
        min_time = 0.0
        max_time = max(c.end_time for c in chunks) + 2.0
        for idx, q in enumerate(quiz_obj.questions):
            if not q.id or q.id in ("string", "q_id"):
                q.id = f"q_{idx + 1}"

            safe_time = max(min_time, min(q.source_timestamp.timestamp, max_time))
            safe_fmt = format_timestamp(safe_time)
            q.source_timestamp = SourceTimestamp(
                timestamp=round(safe_time, 2),
                formatted_time=safe_fmt,
                label=q.source_timestamp.label.strip() or f"Question topic at {safe_fmt}",
            )
            q.source_chunk_id = find_matching_chunk_id(safe_time, chunks, q.source_chunk_id)

        return quiz_obj, model_name

    except Exception as exc:
        handle_gemini_error(exc)


def generate_flashcards(
    video_id: str,
    title: Optional[str],
    chunks: List[TranscriptChunk],
    num_cards: int = 8,
) -> Tuple[GeneratedFlashcards, str]:
    """
    Generates a structured deck of active-recall educational flashcards using Gemini.
    Returns a tuple of (GeneratedFlashcards, model_used).
    """
    if not chunks:
        raise ValueError("Cannot generate flashcards without transcript chunks.")

    client = get_gemini_client()
    model_name = settings.gemini_model
    chunks_context = build_chunks_context(chunks)
    prompt = build_flashcards_prompt(title, chunks_context, num_cards=num_cards)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=GeneratedFlashcards,
        temperature=0.25,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiValidationError("Gemini returned an empty response.")

        flashcards_obj = GeneratedFlashcards.model_validate_json(raw_text)

        # Sanitize card IDs, timestamps, and chunk citations
        min_time = 0.0
        max_time = max(c.end_time for c in chunks) + 2.0
        for idx, card in enumerate(flashcards_obj.cards):
            if not card.id or card.id in ("string", "card_id"):
                card.id = f"card_{idx + 1}"

            safe_time = max(min_time, min(card.source_timestamp.timestamp, max_time))
            safe_fmt = format_timestamp(safe_time)
            card.source_timestamp = SourceTimestamp(
                timestamp=round(safe_time, 2),
                formatted_time=safe_fmt,
                label=card.source_timestamp.label.strip() or f"Concept at {safe_fmt}",
            )
            card.source_chunk_id = find_matching_chunk_id(safe_time, chunks, card.source_chunk_id)

        flashcards_obj.card_count = len(flashcards_obj.cards)
        return flashcards_obj, model_name

    except Exception as exc:
        handle_gemini_error(exc)


RECOVERY_INTERVENTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "explanation": {"type": "STRING"},
        "worked_example": {"type": "STRING"},
        "key_takeaway": {"type": "STRING"},
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "question": {"type": "STRING"},
                    "options": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                    "correct_answer": {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                    "difficulty": {"type": "STRING"},
                    "source_timestamp": {
                        "type": "OBJECT",
                        "properties": {
                            "timestamp": {"type": "NUMBER"},
                            "formatted_time": {"type": "STRING"},
                            "label": {"type": "STRING"},
                        },
                        "required": ["timestamp", "formatted_time", "label"],
                    },
                    "source_chunk_id": {"type": "STRING"},
                },
                "required": [
                    "id",
                    "question",
                    "options",
                    "correct_answer",
                    "explanation",
                    "difficulty",
                    "source_timestamp",
                ],
            },
        },
    },
    "required": [
        "title",
        "explanation",
        "worked_example",
        "key_takeaway",
        "questions",
    ],
}


def generate_recovery_intervention(
    video_title: Optional[str],
    weak_chunk: TranscriptChunk,
    context_chunks: List[TranscriptChunk],
    originating_evidence: str,
    attempt_number: int = 1,
    num_questions: int = 3,
) -> Tuple[RecoveryInterventionInternal, str]:
    """
    Generates a targeted, source-grounded remediation intervention consisting
    of an explanation, worked example, key takeaway, and focused micro-quiz.
    Returns a tuple of (RecoveryInterventionInternal, model_used).
    """
    client = get_gemini_client()
    model_name = settings.gemini_model
    prompt = build_recovery_prompt(
        video_title=video_title,
        weak_chunk=weak_chunk,
        context_chunks=context_chunks,
        originating_evidence=originating_evidence,
        attempt_number=attempt_number,
        num_questions=num_questions,
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_GROUNDING_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RECOVERY_INTERVENTION_SCHEMA,
        temperature=0.2,
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiValidationError("Gemini returned an empty response for recovery intervention.")

        intervention_obj = RecoveryInterventionInternal.model_validate_json(raw_text)

        # Sanitize questions, timestamps, and ensure grounding in the weak chunk
        min_time = weak_chunk.start_time
        max_time = weak_chunk.end_time + 1.0
        for idx, q in enumerate(intervention_obj.questions):
            if not q.id or q.id in ("string", "q_id"):
                q.id = f"rq_{idx + 1}"

            safe_time = max(min_time, min(q.source_timestamp.timestamp, max_time))
            safe_fmt = format_timestamp(safe_time)
            q.source_timestamp = SourceTimestamp(
                timestamp=round(safe_time, 2),
                formatted_time=safe_fmt,
                label=q.source_timestamp.label.strip() or f"Concept at {safe_fmt}",
            )
            q.source_chunk_id = weak_chunk.chunk_id

        return intervention_obj, model_name

    except Exception as exc:
        handle_gemini_error(exc)

