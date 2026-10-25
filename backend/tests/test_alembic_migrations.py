"""
VIDYORA AI - Alembic Migration Execution & Verification Tests

Verifies that:
1. Alembic configuration correctly locates alembic.ini and migration scripts.
2. The initial migration (0001_initial_schema) successfully parses and compiles
   into complete, transactional PostgreSQL DDL.
3. All 12 required tables and the alembic_version tracking table are included in the migration.
"""

import contextlib
import io
import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_alembic_offline_sql_generation():
    """
    Verifies that Alembic can compile the initial migration into valid PostgreSQL DDL
    in offline mode, ensuring schema validity without requiring an active database server.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.is_file(), f"alembic.ini missing at {ini_path}"

    cfg = Config(str(ini_path))
    # Ensure script_location is resolved relative to backend directory
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)

    sql_output = buf.getvalue()

    # Verify that transactional DDL is generated
    assert len(sql_output) > 2000
    assert "0001_initial_schema" in sql_output

    # Verify creation of required tables including chat_messages
    expected_tables = [
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
        "chat_messages",
    ]
    for table_name in expected_tables:
        assert f"CREATE TABLE {table_name}" in sql_output, f"Missing table creation for {table_name}"

    # Verify version stamp insertion
    assert "INSERT INTO alembic_version" in sql_output
