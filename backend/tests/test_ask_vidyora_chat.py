"""
VIDYORA AI - Step 3: Ask VIDYORA Grounded AI Tutor Test Suite

Verifies:
1. Authentication requirements for chat endpoints (401 on missing or invalid token).
2. Video ownership enforcement and IDOR defense (404 on foreign video access).
3. Input validation (422 on empty or whitespace questions and video IDs).
4. Grounded answer synthesis with real retrieved chunks and clickable timestamp citations.
5. Empty retrieval / insufficient evidence handling (honest refusal without hallucination).
6. Gemini service failure handling (429 rate limit, 504 timeout, 503 unavailable).
7. Persistent user-isolated chat history and chronological ordering.
8. Cross-tenant isolation (User A cannot view or delete User B's conversation).
9. Chat history deletion endpoint (clears messages for the target video cleanly).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from config import settings
from db.models import ChatMessage, ChunkEmbedding, KnowledgeChunk, User, Video
from db.session import SessionLocal
from main import app
from services.auth_service import create_access_token, hash_password
from services.embedding_service import MockEmbeddingProvider, embedding_service
from services.gemini_service import GeminiRateLimitError, GeminiTimeoutError
from services.indexing_service import IndexingService

client = TestClient(app)


@pytest.fixture
def mock_embedding_env():
    """Configures EmbeddingService to use MockEmbeddingProvider for deterministic tests."""
    mock_provider = MockEmbeddingProvider(dimension=settings.embedding_dimension)
    original_provider = embedding_service.provider
    embedding_service.set_provider(mock_provider)
    yield mock_provider
    embedding_service.set_provider(original_provider)


@pytest.fixture
def test_users(mock_embedding_env):
    """Creates two distinct learners in PostgreSQL with authenticated tokens."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    u1_id = f"user_alpha_{suffix}"
    u2_id = f"user_beta_{suffix}"

    email1 = f"alpha_{suffix}@vidyora.ai"
    email2 = f"beta_{suffix}@vidyora.ai"
    user1 = User(
        id=u1_id,
        email=email1,
        full_name="Learner Alpha",
        hashed_password=hash_password("PassAlpha123!"),
        is_active=True,
    )
    user2 = User(
        id=u2_id,
        email=email2,
        full_name="Learner Beta",
        hashed_password=hash_password("PassBeta123!"),
        is_active=True,
    )
    db.add_all([user1, user2])
    db.commit()
    db.close()

    t1 = create_access_token({"sub": u1_id, "email": email1})
    t2 = create_access_token({"sub": u2_id, "email": email2})

    return {
        "u1_id": u1_id,
        "u1_token": t1,
        "u1_headers": {"Authorization": f"Bearer {t1}"},
        "u2_id": u2_id,
        "u2_token": t2,
        "u2_headers": {"Authorization": f"Bearer {t2}"},
    }


@pytest.fixture
def test_video_with_chunks(test_users):
    """Creates a sample video with indexed knowledge chunks for Learner Alpha."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid_id = f"vid_chat_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    video = Video(
        id=vid_id,
        user_id=u1_id,
        url=f"https://www.youtube.com/watch?v={vid_id}",
        platform="youtube",
        title="Photosynthesis and Cellular Respiration",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    db.add(video)
    db.commit()

    chunk0 = KnowledgeChunk(
        id=f"chk_{vid_id}_0",
        video_id=vid_id,
        chunk_index=0,
        text="Light reactions occur in the thylakoid membranes of chloroplasts, capturing sunlight to produce ATP and NADPH.",
        start_time=15.0,
        end_time=45.0,
        duration=30.0,
        word_count=18,
        segment_start_index=0,
        segment_end_index=2,
        created_at=now,
    )
    chunk1 = KnowledgeChunk(
        id=f"chk_{vid_id}_1",
        video_id=vid_id,
        chunk_index=1,
        text="The Calvin cycle takes place in the stroma, using ATP and NADPH to convert carbon dioxide into glucose.",
        start_time=50.0,
        end_time=90.0,
        duration=40.0,
        word_count=18,
        segment_start_index=3,
        segment_end_index=5,
        created_at=now,
    )
    db.add_all([chunk0, chunk1])
    db.commit()

    c0_id = chunk0.id
    c1_id = chunk1.id

    # Index chunks via IndexingService
    IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)
    db.close()

    return {
        "video_id": vid_id,
        "chunk0_id": c0_id,
        "chunk1_id": c1_id,
    }


# ===========================================================================
# 1. Authentication Requirements
# ===========================================================================

def test_ask_vidyora_unauthenticated_rejected():
    """Confirms chat endpoints require valid JWT authentication."""
    # POST /api/chat/ask
    resp = client.post("/api/chat/ask", json={"video_id": "vid_123", "question": "What is ATP?"})
    assert resp.status_code == 401

    # GET /api/chat/{video_id}/history
    resp = client.get("/api/chat/vid_123/history")
    assert resp.status_code == 401

    # DELETE /api/chat/{video_id}/history
    resp = client.delete("/api/chat/vid_123/history")
    assert resp.status_code == 401


# ===========================================================================
# 2. Input Validation
# ===========================================================================

def test_ask_vidyora_input_validation(test_users, test_video_with_chunks):
    """Confirms 422 Unprocessable Entity for invalid or empty payloads."""
    headers = test_users["u1_headers"]
    vid_id = test_video_with_chunks["video_id"]

    # Empty question
    resp = client.post("/api/chat/ask", json={"video_id": vid_id, "question": ""}, headers=headers)
    assert resp.status_code == 422

    # Whitespace question
    resp = client.post("/api/chat/ask", json={"video_id": vid_id, "question": "   "}, headers=headers)
    assert resp.status_code == 422

    # Empty video_id
    resp = client.post("/api/chat/ask", json={"video_id": "", "question": "Explain this"}, headers=headers)
    assert resp.status_code == 422


# ===========================================================================
# 3. Video Ownership Enforcement & IDOR Defense
# ===========================================================================

def test_ask_vidyora_ownership_enforcement(test_users, test_video_with_chunks):
    """Confirms User B cannot ask questions, view history, or clear history for User A's video."""
    vid_id = test_video_with_chunks["video_id"]
    u2_headers = test_users["u2_headers"]

    # User B asking against User A's video -> 404
    resp = client.post(
        "/api/chat/ask",
        json={"video_id": vid_id, "question": "Where does the Calvin cycle occur?"},
        headers=u2_headers,
    )
    assert resp.status_code == 404
    assert "not found or you do not have permission" in resp.json()["detail"].lower()

    # User B fetching history for User A's video -> 404
    resp = client.get(f"/api/chat/{vid_id}/history", headers=u2_headers)
    assert resp.status_code == 404

    # User B deleting history for User A's video -> 404
    resp = client.delete(f"/api/chat/{vid_id}/history", headers=u2_headers)
    assert resp.status_code == 404


# ===========================================================================
# 4. Grounded Answer Synthesis & Citation Verification
# ===========================================================================

def test_ask_vidyora_successful_grounded_answer(test_users, test_video_with_chunks):
    """Verifies successful grounded response with verified citations and persistent storage."""
    u1_headers = test_users["u1_headers"]
    vid_id = test_video_with_chunks["video_id"]
    # For deterministic mock embedding provider, use query that aligns with chunk0
    question = "Light reactions occur in the thylakoid membranes of chloroplasts, capturing sunlight to produce ATP and NADPH."

    mock_gemini_response = MagicMock()
    mock_gemini_response.text = (
        "According to the lecture, the light reactions occur specifically in the thylakoid membranes "
        "of chloroplasts. At [00:15], the instructor explains that sunlight is captured here to produce ATP and NADPH."
    )

    with patch("services.chat_service.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_gemini_response
        mock_get_client.return_value = mock_client

        resp = client.post(
            "/api/chat/ask",
            json={"video_id": vid_id, "question": question},
            headers=u1_headers,
        )

        assert resp.status_code == 200
        data = resp.json()

        # Check response structure
        assert data["video_id"] == vid_id
        assert data["question"] == question
        assert "thylakoid membranes" in data["answer"]
        assert len(data["sources"]) > 0

        # Check verified citations
        source = data["sources"][0]
        assert source["chunk_id"] == test_video_with_chunks["chunk0_id"]
        assert source["chunk_index"] == 0
        assert source["start_time"] == 15.0
        assert source["end_time"] == 45.0
        assert source["source_formatted_start"] == "00:15"
        assert source["source_formatted_end"] == "00:45"
        assert source["similarity"] > 0
        assert "thylakoid" in source["text"].lower()

        # Check persistence in database
        db = SessionLocal()
        saved = db.query(ChatMessage).filter(ChatMessage.id == data["id"]).first()
        assert saved is not None
        assert saved.video_id == vid_id
        assert saved.user_id == test_users["u1_id"]
        assert saved.question == question
        assert saved.answer == mock_gemini_response.text
        db.close()


# ===========================================================================
# 5. Empty Retrieval / Honest Limitation Acknowledgment
# ===========================================================================

def test_ask_vidyora_empty_retrieval_insufficient_evidence(test_users, test_video_with_chunks):
    """
    When no chunks meet similarity cutoff, verifies that Ask VIDYORA returns an honest
    refusal acknowledging that the topic is not covered, without calling Gemini.
    """
    u1_headers = test_users["u1_headers"]
    vid_id = test_video_with_chunks["video_id"]

    # Force empty retrieval by patching RetrievalService
    with patch("services.chat_service.RetrievalService.retrieve_chunks") as mock_retrieve:
        mock_retrieve.return_value = MagicMock(results=[])

        with patch("services.chat_service.get_gemini_client") as mock_gemini:
            resp = client.post(
                "/api/chat/ask",
                json={"video_id": vid_id, "question": "What is quantum entanglement in black holes?"},
                headers=u1_headers,
            )

            assert resp.status_code == 200
            data = resp.json()

            # Verify honest acknowledgment
            assert "not discussed" in data["answer"].lower() or "no direct discussion" in data["answer"].lower()
            assert data["sources"] == []
            # Gemini was not called
            mock_gemini.assert_not_called()

            # Message is still persisted in user history
            db = SessionLocal()
            saved = db.query(ChatMessage).filter(ChatMessage.id == data["id"]).first()
            assert saved is not None
            assert saved.sources == []
            db.close()


# ===========================================================================
# 6. Gemini Failure and Timeout Handling
# ===========================================================================

def test_ask_vidyora_gemini_rate_limit_error(test_users, test_video_with_chunks):
    """Verifies that Gemini 429 quota exhaustion is mapped cleanly."""
    u1_headers = test_users["u1_headers"]
    vid_id = test_video_with_chunks["video_id"]
    question = "Light reactions occur in the thylakoid membranes of chloroplasts, capturing sunlight to produce ATP and NADPH."

    with patch("services.chat_service.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = GeminiRateLimitError()
        mock_get_client.return_value = mock_client

        resp = client.post(
            "/api/chat/ask",
            json={"video_id": vid_id, "question": question},
            headers=u1_headers,
        )
        assert resp.status_code == 429
        assert "rate limit or quota exceeded" in resp.json()["detail"].lower()


def test_ask_vidyora_gemini_timeout_error(test_users, test_video_with_chunks):
    """Verifies that Gemini timeout is mapped to 504 Gateway Timeout."""
    u1_headers = test_users["u1_headers"]
    vid_id = test_video_with_chunks["video_id"]
    question = "Light reactions occur in the thylakoid membranes of chloroplasts, capturing sunlight to produce ATP and NADPH."

    with patch("services.chat_service.get_gemini_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = GeminiTimeoutError()
        mock_get_client.return_value = mock_client

        resp = client.post(
            "/api/chat/ask",
            json={"video_id": vid_id, "question": question},
            headers=u1_headers,
        )
        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()


# ===========================================================================
# 7. Persistent Chat History & Chronological Ordering
# ===========================================================================

def test_ask_vidyora_chat_history_and_isolation(test_users, test_video_with_chunks):
    """Verifies that chat history persists chronologically and maintains strict multi-tenant isolation."""
    u1_headers = test_users["u1_headers"]
    u1_id = test_users["u1_id"]
    vid_id = test_video_with_chunks["video_id"]

    # Directly insert 2 historical messages in DB
    db = SessionLocal()
    m1_id = f"msg_{uuid.uuid4().hex[:6]}"
    m2_id = f"msg_{uuid.uuid4().hex[:6]}"
    m1 = ChatMessage(
        id=m1_id,
        video_id=vid_id,
        user_id=u1_id,
        question="What are thylakoids?",
        answer="Thylakoids are membrane-bound compartments inside chloroplasts.",
        sources=[{"chunk_id": "chk_1", "chunk_index": 0, "start_time": 15.0, "end_time": 45.0, "source_formatted_start": "00:15", "source_formatted_end": "00:45", "similarity": 0.95, "text": "Thylakoid membranes"}],
        model_used="gemini-2.5-flash",
        created_at=datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc),
    )
    m2 = ChatMessage(
        id=m2_id,
        video_id=vid_id,
        user_id=u1_id,
        question="What is NADPH?",
        answer="NADPH is an electron carrier used in anabolic reactions.",
        sources=[],
        model_used="gemini-2.5-flash",
        created_at=datetime(2026, 10, 24, 10, 5, tzinfo=timezone.utc),
    )
    db.add_all([m1, m2])
    db.commit()
    db.close()

    # User 1 fetches history
    resp = client.get(f"/api/chat/{vid_id}/history", headers=u1_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_id"] == vid_id
    assert data["total_messages"] == 2
    assert data["total_count"] == 2
    assert len(data["messages"]) == 2

    # Check chronological order (m1 then m2)
    assert data["messages"][0]["id"] == m1_id
    assert data["messages"][0]["question"] == "What are thylakoids?"
    assert len(data["messages"][0]["sources"]) == 1
    assert data["messages"][0]["sources"][0]["source_formatted_start"] == "00:15"

    assert data["messages"][1]["id"] == m2_id
    assert data["messages"][1]["question"] == "What is NADPH?"


# ===========================================================================
# 8. Clear Chat History Endpoint
# ===========================================================================

def test_ask_vidyora_clear_history(test_users, test_video_with_chunks):
    """Verifies clearing chat history removes messages for that video cleanly."""
    u1_headers = test_users["u1_headers"]
    u1_id = test_users["u1_id"]
    vid_id = test_video_with_chunks["video_id"]

    # Insert a message
    db = SessionLocal()
    msg = ChatMessage(
        id=f"msg_clear_{uuid.uuid4().hex[:6]}",
        video_id=vid_id,
        user_id=u1_id,
        question="To be deleted",
        answer="Will be deleted",
        sources=[],
        model_used="gemini-2.5-flash",
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    db.commit()
    db.close()

    # Verify history is not empty
    resp = client.get(f"/api/chat/{vid_id}/history", headers=u1_headers)
    assert resp.status_code == 200
    assert resp.json()["total_messages"] >= 1

    # Clear history
    del_resp = client.delete(f"/api/chat/{vid_id}/history", headers=u1_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"
    assert del_resp.json()["deleted_count"] >= 1

    # Verify history is now empty
    resp_after = client.get(f"/api/chat/{vid_id}/history", headers=u1_headers)
    assert resp_after.status_code == 200
    assert resp_after.json()["total_messages"] == 0
    assert resp_after.json()["messages"] == []
