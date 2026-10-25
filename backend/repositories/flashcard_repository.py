"""
VIDYORA AI - Flashcard Persistence Repository

Encapsulates database operations for FlashcardDeck and Flashcard entities,
maintaining video relationships and source grounding.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from db.models import Flashcard, FlashcardDeck, KnowledgeChunk
from models import Flashcard as PydanticFlashcard
from repositories.video_repository import VideoRepository

logger = logging.getLogger(__name__)


class FlashcardRepository:
    """Repository handling persistence for generated active-recall flashcard decks."""

    @staticmethod
    def get_decks_by_video_id(db: Session, video_id: str) -> list[FlashcardDeck]:
        """Fetches all flashcard decks associated with a video."""
        return (
            db.query(FlashcardDeck)
            .options(joinedload(FlashcardDeck.cards))
            .filter(FlashcardDeck.video_id == video_id)
            .all()
        )

    @staticmethod
    def save_flashcard_deck(
        db: Session,
        video_id: str,
        topic: str,
        cards: list[PydanticFlashcard],
        model_used: str,
        user_id: Optional[str] = None,
    ) -> FlashcardDeck:
        """
        Persists a newly generated flashcard deck and its individual cards to PostgreSQL.
        Preserves source timestamps and chunk grounding.
        """
        now = datetime.now(timezone.utc)
        try:
            # 1. Ensure foreign-key parent video exists
            VideoRepository.ensure_video_stub(db, video_id, title=topic)

            # 2. Create Deck
            deck = FlashcardDeck(
                video_id=video_id,
                user_id=user_id,
                topic=topic,
                model_used=model_used,
                created_at=now,
                updated_at=now,
            )
            db.add(deck)
            db.flush()

            # 3. Create Cards
            cards_to_add = []
            for order, card in enumerate(cards, start=1):
                # Ensure source_chunk_id exists before setting FK
                valid_chunk_id = None
                if card.source_chunk_id:
                    chunk_exists = db.query(KnowledgeChunk).filter(KnowledgeChunk.id == card.source_chunk_id).first()
                    if not chunk_exists:
                        from sqlalchemy import func
                        max_idx = db.query(func.max(KnowledgeChunk.chunk_index)).filter(KnowledgeChunk.video_id == video_id).scalar()
                        next_idx = 0 if max_idx is None else max_idx + 1
                        stub_chunk = KnowledgeChunk(
                            id=card.source_chunk_id,
                            video_id=video_id,
                            chunk_index=next_idx,
                            text=f"Knowledge context for {card.source_chunk_id}",
                            start_time=card.source_timestamp.timestamp,
                            end_time=card.source_timestamp.timestamp + 30.0,
                            duration=30.0,
                            word_count=5,
                            segment_start_index=0,
                            segment_end_index=0,
                            created_at=now,
                        )
                        db.add(stub_chunk)
                        db.flush()
                    valid_chunk_id = card.source_chunk_id

                difficulty_val = (
                    card.difficulty.value if hasattr(card.difficulty, "value") else str(card.difficulty)
                )
                db_card_id = f"{deck.id}_{card.id}" if not card.id.startswith(f"{deck.id}_") else card.id

                cards_to_add.append(
                    Flashcard(
                        id=db_card_id,
                        deck_id=deck.id,
                        source_chunk_id=valid_chunk_id,
                        card_order=order,
                        front=card.front,
                        back=card.back,
                        difficulty=difficulty_val,
                        source_timestamp=card.source_timestamp.timestamp,
                        source_formatted_time=card.source_timestamp.formatted_time,
                        source_label=card.source_timestamp.label,
                        created_at=now,
                    )
                )

            db.add_all(cards_to_add)
            db.commit()
            db.refresh(deck)
            logger.info("Persisted flashcard deck %s with %d cards for video %s.", deck.id, len(cards_to_add), video_id)
            return deck

        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist flashcard deck for video %s: %s", video_id, exc)
            raise
