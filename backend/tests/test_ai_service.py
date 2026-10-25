"""
Unit tests for backend/services/gemini_service.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError
from models import (
    NoteSection,
    SourceTimestamp,
    StructuredNotes,
    TranscriptChunk,
    VideoSummary,
)
from services.gemini_service import (
    GeminiConfigurationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiValidationError,
    build_chunks_context,
    format_timestamp,
    generate_structured_notes,
    generate_video_summary,
    get_gemini_client,
    sanitize_source_timestamps,
)


def sample_chunks() -> list[TranscriptChunk]:
    return [
        TranscriptChunk(
            chunk_id="test_000",
            chunk_index=0,
            video_id="test_vid",
            text="Welcome to machine learning basics. Today we explore neural networks.",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            word_count=10,
            segment_start_index=0,
            segment_end_index=2,
        ),
        TranscriptChunk(
            chunk_id="test_001",
            chunk_index=1,
            video_id="test_vid",
            text="Gradient descent is an optimization algorithm used to minimize the loss function.",
            start_time=60.0,
            end_time=120.0,
            duration=60.0,
            word_count=12,
            segment_start_index=3,
            segment_end_index=5,
        ),
    ]


# ---------------------------------------------------------------------------
# Test Helpers and Formatting
# ---------------------------------------------------------------------------

def test_format_timestamp():
    assert format_timestamp(0.0) == "00:00"
    assert format_timestamp(45.2) == "00:45"
    assert format_timestamp(125.0) == "02:05"
    assert format_timestamp(3665.0) == "01:01:05"


def test_build_chunks_context():
    chunks = sample_chunks()
    context = build_chunks_context(chunks)
    assert "[test_000 | 00:00 - 01:00 | start_seconds: 0.0]" in context
    assert "Welcome to machine learning basics." in context
    assert "[test_001 | 01:00 - 02:00 | start_seconds: 60.0]" in context


def test_sanitize_source_timestamps():
    chunks = sample_chunks()  # max end_time is 120.0
    raw_timestamps = [
        SourceTimestamp(timestamp=-5.0, formatted_time="", label="Start"),
        SourceTimestamp(timestamp=65.0, formatted_time="", label="Middle"),
        SourceTimestamp(timestamp=999.0, formatted_time="", label="Out of bounds"),
    ]
    sanitized = sanitize_source_timestamps(raw_timestamps, chunks)

    assert len(sanitized) == 3
    # First should be clamped to 0.0
    assert sanitized[0].timestamp == 0.0
    assert sanitized[0].formatted_time == "00:00"

    # Second should remain 65.0
    assert sanitized[1].timestamp == 65.0
    assert sanitized[1].formatted_time == "01:05"

    # Third should be clamped near max chunk end time (120.0 + 2.0 = 122.0)
    assert sanitized[2].timestamp == 122.0
    assert sanitized[2].formatted_time == "02:02"


# ---------------------------------------------------------------------------
# Test Client Initialization and Configuration Errors
# ---------------------------------------------------------------------------

def test_missing_api_key_raises_configuration_error():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(GeminiConfigurationError) as exc_info:
            get_gemini_client()
        assert exc_info.value.status_code == 503
        assert "not configured" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test AI Generation (Mocked Gemini API)
# ---------------------------------------------------------------------------

def test_generate_video_summary_success():
    mock_summary_json = json.dumps({
        "overview": "A foundational lesson on neural networks and gradient descent.",
        "main_concepts": ["Neural Networks", "Gradient Descent", "Loss Functions"],
        "takeaways": [
            "Neural networks model complex patterns.",
            "Gradient descent optimizes model weights.",
        ],
        "beginner_explanation": "Think of gradient descent as walking down a foggy hill to find the lowest valley.",
        "source_timestamps": [
            {"timestamp": 0.0, "formatted_time": "00:00", "label": "Introduction to Neural Networks"},
            {"timestamp": 60.0, "formatted_time": "01:00", "label": "Optimization with Gradient Descent"},
        ],
    })

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_summary_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.gemini_service.get_gemini_client", return_value=mock_client):
        summary, model = generate_video_summary(
            video_id="test_vid",
            title="Intro to Machine Learning",
            chunks=sample_chunks(),
        )

        assert isinstance(summary, VideoSummary)
        assert len(summary.main_concepts) == 3
        assert len(summary.takeaways) == 2
        assert len(summary.source_timestamps) == 2
        assert summary.source_timestamps[1].formatted_time == "01:00"
        assert model == "gemini-2.5-flash"


def test_generate_structured_notes_success():
    mock_notes_json = json.dumps({
        "topic_title": "Foundations of Neural Networks and Optimization",
        "introduction": "This lesson introduces artificial neural networks and gradient descent.",
        "main_concepts": ["Artificial Neural Networks", "Optimization Algorithms"],
        "sections": [
            {
                "title": "Introduction to Neural Networks",
                "summary": "Covers what neural networks are and their basic building blocks.",
                "key_points": ["Inspired by biological neurons", "Composed of layers"],
                "start_time": 0.0,
                "formatted_time": "00:00",
            },
            {
                "title": "Gradient Descent Optimization",
                "summary": "Explains how models adjust weights to minimize loss.",
                "key_points": ["Iterative algorithm", "Uses slope of loss function"],
                "start_time": 60.0,
                "formatted_time": "01:00",
            },
        ],
        "terminology": [
            {"term": "Gradient Descent", "definition": "An algorithm for minimizing cost functions.", "context": "Training"},
        ],
        "examples": ["Walking down a foggy mountain to demonstrate descent."],
        "key_takeaways": ["Neural networks learn by adjusting weights."],
        "relevant_timestamps": [
            {"timestamp": 0.0, "formatted_time": "00:00", "label": "Start of lecture"},
            {"timestamp": 60.0, "formatted_time": "01:00", "label": "Gradient descent explanation"},
        ],
    })

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_notes_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.gemini_service.get_gemini_client", return_value=mock_client):
        notes, model = generate_structured_notes(
            video_id="test_vid",
            title="Intro to Machine Learning",
            chunks=sample_chunks(),
        )

        assert isinstance(notes, StructuredNotes)
        assert notes.topic_title == "Foundations of Neural Networks and Optimization"
        assert len(notes.sections) == 2
        assert notes.sections[1].formatted_time == "01:00"
        assert len(notes.terminology) == 1
        assert model == "gemini-2.5-flash"


def test_generate_summary_empty_response_raises_validation_error():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""
    mock_client.models.generate_content.return_value = mock_response

    with patch("services.gemini_service.get_gemini_client", return_value=mock_client):
        with pytest.raises(GeminiValidationError) as exc:
            generate_video_summary(
                video_id="test_vid",
                title="Test Video",
                chunks=sample_chunks(),
            )
        assert exc.value.status_code == 502


def test_rate_limit_error_mapping():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.body_segments = [{"error": {"message": "RESOURCE_EXHAUSTED: Quota exceeded", "code": 429}}]
    api_error = APIError(429, mock_resp)
    mock_client.models.generate_content.side_effect = api_error

    with patch("services.gemini_service.get_gemini_client", return_value=mock_client):
        with pytest.raises(GeminiRateLimitError) as exc:
            generate_video_summary(
                video_id="test_vid",
                title="Test",
                chunks=sample_chunks(),
            )
        assert exc.value.status_code == 429
        assert "rate limit" in exc.value.message.lower()
