"""
Integration and endpoint tests for VIDYORA AI backend.
Covers existing endpoints (/health, /api/videos/process) and Step 11 AI endpoints
(/api/ai/summary, /api/ai/notes).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from main import app
from models import StructuredNotes, VideoSummary
from services.gemini_service import (
    GeminiConfigurationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
)

client = TestClient(app)


def dummy_chunks_payload():
    return [
        {
            "chunk_id": "test_chunk_001",
            "chunk_index": 0,
            "video_id": "dQw4w9WgXcQ",
            "text": "This is a cohesive lecture segment introducing key concepts.",
            "start_time": 0.0,
            "end_time": 65.5,
            "duration": 65.5,
            "word_count": 8,
            "segment_start_index": 0,
            "segment_end_index": 2,
        }
    ]


# ---------------------------------------------------------------------------
# Existing Endpoint Verification (Non-Regression)
# ---------------------------------------------------------------------------

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "VIDYORA AI Backend"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_process_video_invalid_url_rejected():
    response = client.post("/api/videos/process", json={"url": "not-a-valid-url"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Step 11 AI Endpoints: Summary Tests
# ---------------------------------------------------------------------------

def test_summary_endpoint_empty_chunks_fails_validation():
    response = client.post(
        "/api/ai/summary",
        json={"video_id": "vid123", "chunks": []},
    )
    assert response.status_code == 422


def test_summary_endpoint_missing_api_key_returns_503():
    with patch(
        "main.generate_video_summary",
        side_effect=GeminiConfigurationError("Google Gemini API key is not configured. Please set GEMINI_API_KEY in your backend .env file."),
    ):
        response = client.post(
            "/api/ai/summary",
            json={"video_id": "vid123", "chunks": dummy_chunks_payload()},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


def test_summary_endpoint_rate_limit_returns_429():
    with patch(
        "main.generate_video_summary",
        side_effect=GeminiRateLimitError("Gemini API rate limit exceeded."),
    ):
        response = client.post(
            "/api/ai/summary",
            json={"video_id": "vid123", "chunks": dummy_chunks_payload()},
        )
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()


def test_summary_endpoint_timeout_returns_504():
    with patch(
        "main.generate_video_summary",
        side_effect=GeminiTimeoutError("Request to Gemini API timed out."),
    ):
        response = client.post(
            "/api/ai/summary",
            json={"video_id": "vid123", "chunks": dummy_chunks_payload()},
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()


def test_summary_endpoint_successful_generation():
    mock_summary = VideoSummary(
        overview="Clear overview of the lesson.",
        main_concepts=["Concept 1", "Concept 2"],
        takeaways=["Takeaway 1"],
        beginner_explanation="Beginner friendly breakdown.",
        source_timestamps=[{"timestamp": 0.0, "formatted_time": "00:00", "label": "Start"}],
    )

    with patch("main.generate_video_summary", return_value=(mock_summary, "gemini-2.5-flash")):
        response = client.post(
            "/api/ai/summary",
            json={
                "video_id": "vid123",
                "title": "Machine Learning",
                "chunks": dummy_chunks_payload(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["video_id"] == "vid123"
        assert data["model_used"] == "gemini-2.5-flash"
        assert data["chunk_count"] == 1
        assert data["summary"]["overview"] == "Clear overview of the lesson."
        assert len(data["summary"]["main_concepts"]) == 2
        assert data["summary"]["source_timestamps"][0]["formatted_time"] == "00:00"


# ---------------------------------------------------------------------------
# Step 11 AI Endpoints: Notes Tests
# ---------------------------------------------------------------------------

def test_notes_endpoint_empty_chunks_fails_validation():
    response = client.post(
        "/api/ai/notes",
        json={"video_id": "vid123", "chunks": []},
    )
    assert response.status_code == 422


def test_notes_endpoint_successful_generation():
    mock_notes = StructuredNotes(
        topic_title="Intro to Computing",
        introduction="An introduction to computer systems.",
        main_concepts=["Hardware", "Software"],
        sections=[
            {
                "title": "Hardware",
                "summary": "Covers processors and memory.",
                "key_points": ["CPU", "RAM"],
                "start_time": 0.0,
                "formatted_time": "00:00",
            }
        ],
        terminology=[{"term": "CPU", "definition": "Central Processing Unit"}],
        examples=["Smartphone processors"],
        key_takeaways=["Hardware executes instructions."],
        relevant_timestamps=[{"timestamp": 0.0, "formatted_time": "00:00", "label": "Hardware Overview"}],
    )

    with patch("main.generate_structured_notes", return_value=(mock_notes, "gemini-2.5-flash")):
        response = client.post(
            "/api/ai/notes",
            json={
                "video_id": "vid123",
                "title": "Computer Science 101",
                "chunks": dummy_chunks_payload(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["video_id"] == "vid123"
        assert data["notes"]["topic_title"] == "Intro to Computing"
        assert len(data["notes"]["sections"]) == 1
        assert len(data["notes"]["terminology"]) == 1
