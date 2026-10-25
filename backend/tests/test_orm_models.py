"""
VIDYORA AI - ORM Model Schema & Metadata Tests

Verifies that all 12 persistence entities are registered on Base.metadata with
correct primary keys, foreign keys, unique constraints, and indexes.
"""

from db.base import Base
from db.models import (
    Flashcard,
    FlashcardDeck,
    KnowledgeChunk,
    LearnerProgress,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    TranscriptSegment,
    User,
    Video,
    VideoTranscript,
)


def test_all_twelve_tables_registered_in_metadata():
    """Verifies that all 12 required entities are present in SQLAlchemy metadata."""
    expected_tables = {
        "users",
        "videos",
        "video_transcripts",
        "transcript_segments",
        "knowledge_chunks",
        "quizzes",
        "quiz_questions",
        "quiz_attempts",
        "quiz_answers",
        "flashcard_decks",
        "flashcards",
        "learner_progress",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables)


def test_primary_keys_defined_on_all_models():
    """Verifies that every entity has an explicitly declared primary key."""
    for table_name, table in Base.metadata.tables.items():
        assert len(table.primary_key.columns) > 0, f"Table {table_name} lacks a primary key."


def test_video_and_user_foreign_keys():
    """Verifies video-to-user and transcript-to-video foreign key relationships."""
    videos_table = Base.metadata.tables["videos"]
    fk_user = [fk for fk in videos_table.foreign_keys if fk.column.table.name == "users"]
    assert len(fk_user) == 1
    assert fk_user[0].parent.name == "user_id"
    assert fk_user[0].ondelete == "SET NULL"

    transcripts_table = Base.metadata.tables["video_transcripts"]
    fk_video = [fk for fk in transcripts_table.foreign_keys if fk.column.table.name == "videos"]
    assert len(fk_video) == 1
    assert fk_video[0].parent.name == "video_id"
    assert fk_video[0].ondelete == "CASCADE"


def test_knowledge_chunk_source_grounding_foreign_keys():
    """Verifies that quiz questions and flashcards maintain FK references to knowledge chunks."""
    quiz_questions_table = Base.metadata.tables["quiz_questions"]
    fk_chunk = [fk for fk in quiz_questions_table.foreign_keys if fk.column.table.name == "knowledge_chunks"]
    assert len(fk_chunk) == 1
    assert fk_chunk[0].parent.name == "source_chunk_id"
    assert fk_chunk[0].ondelete == "SET NULL"

    flashcards_table = Base.metadata.tables["flashcards"]
    fk_card_chunk = [fk for fk in flashcards_table.foreign_keys if fk.column.table.name == "knowledge_chunks"]
    assert len(fk_card_chunk) == 1
    assert fk_card_chunk[0].parent.name == "source_chunk_id"
    assert fk_card_chunk[0].ondelete == "SET NULL"


def test_unique_constraints_defined():
    """Verifies unique constraints on users (email, username), chunks, and quiz answers."""
    users_table = Base.metadata.tables["users"]
    user_uqs = {c.name for c in users_table.constraints if hasattr(c, "columns") and len(c.columns) == 1}
    assert "uq_users_email" in user_uqs or "email" in [col.name for col in users_table.columns if col.unique]

    chunks_table = Base.metadata.tables["knowledge_chunks"]
    chunk_uq_names = {c.name for c in chunks_table.constraints}
    assert "uq_knowledge_chunks_video_chunk_index" in chunk_uq_names

    answers_table = Base.metadata.tables["quiz_answers"]
    answer_uq_names = {c.name for c in answers_table.constraints}
    assert "uq_quiz_answers_attempt_question" in answer_uq_names


def test_indexes_defined_for_foreign_keys_and_lookups():
    """Verifies critical performance indexes exist on foreign keys and frequently queried fields."""
    videos_table = Base.metadata.tables["videos"]
    video_idx_cols = [[c.name for c in idx.columns] for idx in videos_table.indexes]
    assert ["user_id"] in video_idx_cols
    assert ["status"] in video_idx_cols

    chunks_table = Base.metadata.tables["knowledge_chunks"]
    chunk_idx_cols = [[c.name for c in idx.columns] for idx in chunks_table.indexes]
    assert ["video_id", "chunk_index"] in chunk_idx_cols
    assert ["video_id", "start_time"] in chunk_idx_cols

    segments_table = Base.metadata.tables["transcript_segments"]
    segment_idx_cols = [[c.name for c in idx.columns] for idx in segments_table.indexes]
    assert ["transcript_id", "start_time"] in segment_idx_cols


def test_quiz_question_and_answer_id_column_lengths():
    """Verifies that QuizQuestion.id and QuizAnswer.question_id allow up to 128 characters."""
    qq_id_col = Base.metadata.tables["quiz_questions"].columns["id"]
    qa_qid_col = Base.metadata.tables["quiz_answers"].columns["question_id"]
    assert qq_id_col.type.length == 128, f"Expected 128, got {qq_id_col.type.length}"
    assert qa_qid_col.type.length == 128, f"Expected 128, got {qa_qid_col.type.length}"

