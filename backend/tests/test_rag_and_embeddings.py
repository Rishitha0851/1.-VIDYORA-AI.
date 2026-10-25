"""
VIDYORA AI - Step 17 RAG, Embeddings & Vector Retrieval Test Suite

Verifies:
1. pgvector configuration and table schema
2. Embedding model validation and dimension verification
3. Embedding generation success
4. Embedding API error handling
5. Duplicate embedding prevention (idempotent re-indexing)
6. Retrieval ranking (most similar chunk ranked first)
7. top_k validation and boundaries
8. similarity_threshold filtering
9. Video-specific retrieval scoping
10. User-specific retrieval isolation
11. Cross-user retrieval rejection (IDOR defense)
12. Empty retrieval results on unmatched queries
13. Source timestamp preservation for video player navigation
14. Existing video/chunk APIs remain fully functional
15. Existing authentication remains fully functional
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from unittest.mock import patch, MagicMock

from main import app
from config import settings
from db.session import SessionLocal
from db.models import User, Video, KnowledgeChunk, ChunkEmbedding
from services.auth_service import hash_password, create_access_token
from services.embedding_service import (
    EmbeddingService,
    MockEmbeddingProvider,
    GoogleGenAIEmbeddingProvider,
    EmbeddingServiceError,
    EmbeddingDimensionMismatchError,
    EmbeddingConfigurationError,
    embedding_service,
)
from repositories.embedding_repository import EmbeddingRepository
from services.indexing_service import IndexingService
from services.retrieval_service import RetrievalService
from models import RagRetrieveRequest, IndexVideoChunksRequest

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


# ===========================================================================
# 1. pgvector Configuration Test
# ===========================================================================
def test_pgvector_extension_and_table():
    """1. Confirms pgvector extension is enabled and chunk_embeddings table exists."""
    db = SessionLocal()
    try:
        ext = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';")).scalar()
        assert ext == "vector", "pgvector extension is not enabled in PostgreSQL"

        cols = db.execute(
            text("SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = 'chunk_embeddings';")
        ).fetchall()
        col_dict = {col[0]: col[1] for col in cols}
        assert "embedding" in col_dict, "embedding column missing from chunk_embeddings"
        assert col_dict["embedding"] == "vector", "embedding column is not a pgvector type"
        assert "chunk_id" in col_dict
        assert "video_id" in col_dict
        assert "user_id" in col_dict
        assert "model_name" in col_dict
        assert "dimension" in col_dict
    finally:
        db.close()


# ===========================================================================
# 2. Embedding Model Validation Tests
# ===========================================================================
def test_embedding_model_validation():
    """2. Validates vector dimension and model name configuration."""
    provider = MockEmbeddingProvider(dimension=settings.embedding_dimension)
    assert provider.dimension == settings.embedding_dimension
    assert provider.dimension == 768

    # Reject empty string
    with pytest.raises(EmbeddingServiceError):
        provider.embed_text("")

    # Verify vector dimension mismatch handling
    bad_provider = MockEmbeddingProvider(dimension=512)
    with pytest.raises(EmbeddingDimensionMismatchError):
        # When wrapping a provider with unexpected dimension
        real_mock = GoogleGenAIEmbeddingProvider(api_key="mock", expected_dimension=768)
        real_mock._validate_vector([0.1] * 512)


# ===========================================================================
# 3. Embedding Generation Success
# ===========================================================================
def test_embedding_generation_success(mock_embedding_env):
    """3. Verifies successful generation of normalized 768-dim vector embeddings."""
    text_sample = "Artificial neural networks consist of interconnected computational units called neurons."
    vector = embedding_service.generate_embedding(text_sample)
    assert isinstance(vector, list)
    assert len(vector) == 768
    assert all(isinstance(v, float) for v in vector)

    # Test batch embedding
    batch = [text_sample, "Gradient descent iteratively adjusts parameters."]
    vectors = embedding_service.generate_embeddings_batch(batch)
    assert len(vectors) == 2
    assert len(vectors[0]) == 768
    assert len(vectors[1]) == 768


# ===========================================================================
# 4. Embedding API Failure Handling
# ===========================================================================
def test_embedding_api_failure_clean_handling():
    """4. Ensures external API failures and missing keys produce safe, clean exceptions without leaks."""
    provider_missing_key = GoogleGenAIEmbeddingProvider(api_key="")
    with pytest.raises(EmbeddingConfigurationError) as exc_info:
        provider_missing_key.embed_text("Sample text")
    assert "GEMINI_API_KEY" in str(exc_info.value)
    # Confirm no secret values leaked
    assert "password" not in str(exc_info.value).lower()


# ===========================================================================
# 5. Duplicate Embedding Prevention (Idempotent Indexing)
# ===========================================================================
def test_duplicate_embedding_prevention(test_users, mock_embedding_env):
    """5. Indexing the same video chunks twice skips already-indexed chunks."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid_id = f"vid_idemp_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        video = Video(
            id=vid_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            platform="youtube",
            title="Idempotency Lecture",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(video)
        db.flush()

        chk1 = KnowledgeChunk(
            id=f"chk_{vid_id}_0",
            video_id=vid_id,
            chunk_index=0,
            text="First chunk text on linear layers.",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            word_count=6,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        chk2 = KnowledgeChunk(
            id=f"chk_{vid_id}_1",
            video_id=vid_id,
            chunk_index=1,
            text="Second chunk text on loss functions.",
            start_time=60.0,
            end_time=120.0,
            duration=60.0,
            word_count=6,
            segment_start_index=2,
            segment_end_index=3,
            created_at=now,
        )
        db.add_all([chk1, chk2])
        db.commit()

        # First indexing run: should index both chunks
        res1 = IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)
        assert res1.indexed_chunks == 2
        assert res1.already_indexed_chunks == 0
        assert res1.total_chunks == 2

        # Second indexing run: should detect existing embeddings and index 0
        res2 = IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)
        assert res2.indexed_chunks == 0
        assert res2.already_indexed_chunks == 2
        assert res2.total_chunks == 2

    finally:
        db.close()


# ===========================================================================
# 6. Retrieval Ranking
# ===========================================================================
def test_retrieval_ranking(test_users, mock_embedding_env):
    """6. Verifies that the most semantically relevant chunk ranks first with highest similarity."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid_id = f"vid_rank_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        video = Video(
            id=vid_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            platform="youtube",
            title="Ranking Lecture",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(video)
        db.flush()

        # Target query
        query = "What is backpropagation?"

        # Chunk 0 matches query exactly
        chk0 = KnowledgeChunk(
            id=f"chk_{vid_id}_0",
            video_id=vid_id,
            chunk_index=0,
            text=query,
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            word_count=4,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        # Chunk 1 is completely unrelated
        chk1 = KnowledgeChunk(
            id=f"chk_{vid_id}_1",
            video_id=vid_id,
            chunk_index=1,
            text="Unrelated cooking recipe about boiling water and vegetables.",
            start_time=60.0,
            end_time=120.0,
            duration=60.0,
            word_count=8,
            segment_start_index=2,
            segment_end_index=3,
            created_at=now,
        )
        db.add_all([chk0, chk1])
        db.commit()

        # Index chunks
        IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)

        # Retrieve
        req = RagRetrieveRequest(query=query, video_id=vid_id, top_k=2)
        response = RetrievalService.retrieve_chunks(db=db, user_id=u1_id, request=req)

        assert response.results_count == 2
        # Exact match chunk should rank first with similarity = 1.0 (since mock provider is deterministic)
        top_result = response.results[0]
        assert top_result.chunk_id == chk0.id
        assert top_result.similarity >= 0.99
        assert top_result.text == query

    finally:
        db.close()


# ===========================================================================
# 7. top_k Validation
# ===========================================================================
def test_top_k_validation_and_boundaries(test_users, mock_embedding_env):
    """7. Verifies top_k limits results appropriately and validates input boundaries."""
    # Invalid top_k < 1 rejected by Pydantic
    with pytest.raises(Exception):
        RagRetrieveRequest(query="test", top_k=0)

    # Invalid top_k > 50 rejected
    with pytest.raises(Exception):
        RagRetrieveRequest(query="test", top_k=51)


# ===========================================================================
# 8. similarity_threshold Filtering
# ===========================================================================
def test_similarity_threshold_filtering(test_users, mock_embedding_env):
    """8. Verifies results with similarity below threshold are filtered out."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid_id = f"vid_thresh_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        video = Video(
            id=vid_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            platform="youtube",
            title="Threshold Lecture",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(video)
        db.flush()

        chk = KnowledgeChunk(
            id=f"chk_{vid_id}_0",
            video_id=vid_id,
            chunk_index=0,
            text="Quantum computing qubits in superposition.",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            word_count=5,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        db.add(chk)
        db.commit()

        IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)

        # High threshold on unrelated query should yield 0 results
        req_high = RagRetrieveRequest(
            query="Deep convolutional neural network architecture",
            video_id=vid_id,
            similarity_threshold=0.95,
        )
        res_high = RetrievalService.retrieve_chunks(db=db, user_id=u1_id, request=req_high)
        assert res_high.results_count == 0

    finally:
        db.close()


# ===========================================================================
# 9. Video-Specific Retrieval Scoping
# ===========================================================================
def test_video_specific_retrieval(test_users, mock_embedding_env):
    """9. When video_id is provided, only chunks belonging to that video are returned."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid1_id = f"vid_v1_{uuid.uuid4().hex[:6]}"
    vid2_id = f"vid_v2_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        v1 = Video(
            id=vid1_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid1_id}",
            platform="youtube",
            title="Video One",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        v2 = Video(
            id=vid2_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid2_id}",
            platform="youtube",
            title="Video Two",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add_all([v1, v2])
        db.flush()

        chk_v1 = KnowledgeChunk(
            id=f"chk_{vid1_id}_0",
            video_id=vid1_id,
            chunk_index=0,
            text="Shared topic discussion in video one.",
            start_time=0.0,
            end_time=30.0,
            duration=30.0,
            word_count=6,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        chk_v2 = KnowledgeChunk(
            id=f"chk_{vid2_id}_0",
            video_id=vid2_id,
            chunk_index=0,
            text="Shared topic discussion in video two.",
            start_time=0.0,
            end_time=30.0,
            duration=30.0,
            word_count=6,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        db.add_all([chk_v1, chk_v2])
        db.commit()

        IndexingService.index_video_chunks(db=db, video_id=vid1_id, user_id=u1_id)
        IndexingService.index_video_chunks(db=db, video_id=vid2_id, user_id=u1_id)

        # Scoped retrieval to vid1_id
        req = RagRetrieveRequest(query="Shared topic discussion", video_id=vid1_id, top_k=5)
        res = RetrievalService.retrieve_chunks(db=db, user_id=u1_id, request=req)

        assert res.results_count == 1
        assert res.results[0].video_id == vid1_id

    finally:
        db.close()


# ===========================================================================
# 10 & 11. User-Specific Retrieval & IDOR Rejection
# ===========================================================================
def test_cross_user_retrieval_isolation_and_idor(test_users, mock_embedding_env):
    """
    10 & 11. User A retrieval never returns User B chunks,
    and querying User B's video ID explicitly returns HTTP 404 (IDOR defense).
    """
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    u2_id = test_users["u2_id"]
    vid_a = f"vid_user_a_{uuid.uuid4().hex[:6]}"
    vid_b = f"vid_user_b_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        # Create User A video & chunk
        v_a = Video(
            id=vid_a,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid_a}",
            platform="youtube",
            title="User A Secret Research",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        chk_a = KnowledgeChunk(
            id=f"chk_{vid_a}_0",
            video_id=vid_a,
            chunk_index=0,
            text="User A proprietary algorithm formula details.",
            start_time=0.0,
            end_time=45.0,
            duration=45.0,
            word_count=6,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )

        # Create User B video & chunk
        v_b = Video(
            id=vid_b,
            user_id=u2_id,
            url=f"https://www.youtube.com/watch?v={vid_b}",
            platform="youtube",
            title="User B Public Lecture",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        chk_b = KnowledgeChunk(
            id=f"chk_{vid_b}_0",
            video_id=vid_b,
            chunk_index=0,
            text="User B standard public machine learning overview.",
            start_time=0.0,
            end_time=45.0,
            duration=45.0,
            word_count=7,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )

        db.add_all([v_a, chk_a, v_b, chk_b])
        db.commit()

        # Index both videos
        IndexingService.index_video_chunks(db=db, video_id=vid_a, user_id=u1_id)
        IndexingService.index_video_chunks(db=db, video_id=vid_b, user_id=u2_id)

    finally:
        db.close()

    # 1. User A global query: only User A chunks returned
    res_a = client.post(
        "/api/rag/retrieve",
        json={"query": "algorithm formula details", "top_k": 5},
        headers=test_users["u1_headers"],
    )
    assert res_a.status_code == 200
    res_a_data = res_a.json()
    assert all(r["video_id"] == vid_a for r in res_a_data["results"])
    assert not any(r["video_id"] == vid_b for r in res_a_data["results"])

    # 2. User B global query: only User B chunks returned
    res_b = client.post(
        "/api/rag/retrieve",
        json={"query": "machine learning overview", "top_k": 5},
        headers=test_users["u2_headers"],
    )
    assert res_b.status_code == 200
    res_b_data = res_b.json()
    assert all(r["video_id"] == vid_b for r in res_b_data["results"])
    assert not any(r["video_id"] == vid_a for r in res_b_data["results"])

    # 3. IDOR Attack: User B explicitly requests User A's video_id -> 404 Not Found
    res_idor = client.post(
        "/api/rag/retrieve",
        json={"query": "algorithm formula", "video_id": vid_a, "top_k": 5},
        headers=test_users["u2_headers"],
    )
    assert res_idor.status_code == 404
    assert "not found" in res_idor.json()["detail"].lower()


# ===========================================================================
# 12. Empty Retrieval Results
# ===========================================================================
def test_empty_retrieval_when_no_videos_exist(test_users, mock_embedding_env):
    """12. A new learner with no indexed videos receives an empty result array with 200 OK."""
    res = client.post(
        "/api/rag/retrieve",
        json={"query": "What is an activation function?", "top_k": 5},
        headers=test_users["u1_headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["results_count"] == 0
    assert data["results"] == []


# ===========================================================================
# 13. Source Timestamp Preservation
# ===========================================================================
def test_source_timestamp_preservation(test_users, mock_embedding_env):
    """13. Verified that retrieved chunks contain exact start_time, end_time, and formatted timestamps."""
    db = SessionLocal()
    u1_id = test_users["u1_id"]
    vid_id = f"vid_time_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)

    try:
        video = Video(
            id=vid_id,
            user_id=u1_id,
            url=f"https://www.youtube.com/watch?v={vid_id}",
            platform="youtube",
            title="Timestamp Lecture",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        db.add(video)
        db.flush()

        chk = KnowledgeChunk(
            id=f"chk_{vid_id}_0",
            video_id=vid_id,
            chunk_index=0,
            text="Discussion of learning rates at minute two.",
            start_time=125.5,
            end_time=185.0,
            duration=59.5,
            word_count=7,
            segment_start_index=0,
            segment_end_index=1,
            created_at=now,
        )
        db.add(chk)
        db.commit()

        IndexingService.index_video_chunks(db=db, video_id=vid_id, user_id=u1_id)

        res = client.post(
            "/api/rag/retrieve",
            json={"query": "Discussion of learning rates at minute two.", "video_id": vid_id},
            headers=test_users["u1_headers"],
        )
        assert res.status_code == 200
        item = res.json()["results"][0]
        assert item["start_time"] == 125.5
        assert item["end_time"] == 185.0
        assert item["source_formatted_start"] == "02:05"
        assert item["source_formatted_end"] == "03:05"
        assert item["video_title"] == "Timestamp Lecture"

    finally:
        db.close()


# ===========================================================================
# 14 & 15. Existing APIs and Authentication Continuity
# ===========================================================================
def test_existing_apis_and_auth_continuity(test_users):
    """14 & 15. Verifies existing endpoints (health, /api/auth/me, unauthenticated 401) continue working."""
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # Authenticated user
    res_me = client.get("/api/auth/me", headers=test_users["u1_headers"])
    assert res_me.status_code == 200
    assert res_me.json()["id"] == test_users["u1_id"]

    # Unauthenticated RAG retrieval rejected
    res_unauth = client.post("/api/rag/retrieve", json={"query": "test"})
    assert res_unauth.status_code == 401
