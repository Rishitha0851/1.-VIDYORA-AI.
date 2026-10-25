"""
VIDYORA AI - Ask VIDYORA Conversational Tutor Service (Step 3)

Provides lecture-grounded conversational Q&A for students. Leverages RAG retrieval
over pgvector transcript embeddings to fetch time-aligned transcript evidence,
synthesizes grounded answers via Google Gemini, and maintains persistent,
user-isolated chat history.
"""

import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from google.genai import types

from config import settings
from repositories.video_repository import VideoRepository
from repositories.chat_repository import ChatRepository
from services.indexing_service import IndexingService
from services.retrieval_service import RetrievalService
from services.gemini_service import get_gemini_client, handle_gemini_error
from models import (
    AskVidyoraRequest,
    AskVidyoraResponse,
    ChatHistoryResponse,
    ChatSourceCitation,
    RagRetrieveRequest,
    RetrievedChunkResult,
)

logger = logging.getLogger(__name__)

CHAT_GROUNDING_INSTRUCTION = (
    "You are Ask VIDYORA, an empathetic, highly knowledgeable educational AI tutor.\n"
    "Your mission is to help students deeply understand the concepts taught in this video lecture.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. Base your answer EXCLUSIVELY and STRICTLY on the provided transcript excerpts.\n"
    "2. If the provided transcript excerpts do not contain enough information to answer the question, "
    "explicitly acknowledge: 'Based on this video's lecture transcript, this topic is not discussed.' "
    "Never fabricate, hallucinate, or extrapolate facts not present in the spoken transcript.\n"
    "3. When referencing explanations, mention the relevant lecture moment or timestamp (e.g., 'At [02:15], the instructor explains...').\n"
    "4. Keep your explanations clear, structured, student-friendly, and engaging. Use concise bullet points or short paragraphs where helpful.\n"
    "5. Maintain an encouraging and pedagogical tone at all times."
)


class ChatService:
    """Orchestrates grounded question answering, source citations, and chat persistence."""

    @classmethod
    def ask_question(
        cls,
        db: Session,
        user_id: str,
        request: AskVidyoraRequest,
    ) -> AskVidyoraResponse:
        """
        Processes a student question against a specific video lecture.
        
        Enforces:
        - Strict user video ownership (IDOR defense)
        - Seamless automatic indexing of transcript chunks if not already indexed
        - RAG vector retrieval with similarity threshold and top-k limits
        - Grounded synthesis via Google Gemini
        - Honest limitation refusal if no relevant transcript context is retrieved
        - User-scoped persistence into chat history
        """
        video_id = request.video_id.strip() if request.video_id else ""
        question = request.question.strip() if request.question else ""

        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="video_id cannot be empty or whitespace.",
            )

        if not question:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question cannot be empty or whitespace.",
            )

        # 1. Enforce strict video ownership
        video = VideoRepository.get_by_id(db, video_id=video_id, user_id=user_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video '{video_id}' not found or you do not have permission to access it.",
            )

        # 2. Ensure transcript chunks are indexed in pgvector
        try:
            IndexingService.index_video_chunks(db, video_id=video_id, user_id=user_id)
        except Exception as exc:
            logger.warning("Auto-indexing during chat query experienced an issue: %s", exc)

        # 3. Retrieve relevant chunks via RAG
        retrieval_req = RagRetrieveRequest(
            video_id=video_id,
            query=question,
            top_k=5,
            similarity_threshold=0.30,  # generous threshold to catch relevant parts
        )
        rag_response = RetrievalService.retrieve_chunks(db, user_id=user_id, request=retrieval_req)
        retrieved_chunks = rag_response.results

        model_name = settings.gemini_model

        # 4. Handle insufficient evidence / empty retrieval
        if not retrieved_chunks:
            logger.info("No relevant chunks retrieved for question '%s' on video %s", question, video_id)
            unsupported_answer = (
                "Based on this lecture's transcript, there is no direct discussion or sufficient "
                "evidence to answer your question. Ask a question specifically related to the "
                "topics covered in this video, or browse the Summary and Notes tabs for an overview."
            )
            saved_msg = ChatRepository.save_message(
                db=db,
                user_id=user_id,
                video_id=video_id,
                question=question,
                answer=unsupported_answer,
                sources=[],
                model_used=model_name,
            )
            return AskVidyoraResponse(
                id=saved_msg.id,
                video_id=video_id,
                question=question,
                answer=unsupported_answer,
                sources=[],
                model_used=model_name,
                created_at=saved_msg.created_at.isoformat() if hasattr(saved_msg.created_at, "isoformat") else str(saved_msg.created_at),
            )

        # 5. Format retrieved chunks for the prompt context
        context_blocks = []
        for idx, chunk in enumerate(retrieved_chunks, 1):
            context_blocks.append(
                f"[Moment #{idx} | Timestamp {chunk.source_formatted_start} - {chunk.source_formatted_end} | Relevance {int(chunk.similarity * 100)}%]\n"
                f"{chunk.text}"
            )
        chunks_context = "\n\n".join(context_blocks)

        prompt = (
            f"Video Title: {video.title or 'Educational Video Lecture'}\n"
            f"Student Question: {question}\n\n"
            f"RETRIEVED TRANSCRIPT EXCERPTS:\n{chunks_context}\n\n"
            "Please provide a grounded, helpful, and concise answer to the student's question using ONLY the provided excerpts."
        )

        # 6. Invoke Gemini with strict grounding
        client = get_gemini_client()
        config = types.GenerateContentConfig(
            system_instruction=CHAT_GROUNDING_INSTRUCTION,
            temperature=0.2,
        )

        try:
            gemini_response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            answer_text = gemini_response.text or "I was unable to synthesize an answer from the transcript."
        except Exception as exc:
            handle_gemini_error(exc)

        # 7. Map retrieved chunks to source citations
        citations = [
            ChatSourceCitation(
                chunk_id=c.chunk_id,
                chunk_index=c.chunk_index,
                start_time=c.start_time,
                end_time=c.end_time,
                source_formatted_start=c.source_formatted_start,
                source_formatted_end=c.source_formatted_end,
                similarity=c.similarity,
                text=c.text,
            )
            for c in retrieved_chunks
        ]

        # 8. Persist in user-isolated chat history
        saved_msg = ChatRepository.save_message(
            db=db,
            user_id=user_id,
            video_id=video_id,
            question=question,
            answer=answer_text,
            sources=[c.model_dump() for c in citations],
            model_used=model_name,
        )

        return AskVidyoraResponse(
            id=saved_msg.id,
            video_id=video_id,
            question=question,
            answer=answer_text,
            sources=citations,
            model_used=model_name,
            created_at=saved_msg.created_at.isoformat() if hasattr(saved_msg.created_at, "isoformat") else str(saved_msg.created_at),
        )

    @classmethod
    def get_chat_history(
        cls,
        db: Session,
        user_id: str,
        video_id: str,
        limit: int = 50,
    ) -> ChatHistoryResponse:
        """
        Retrieves user-isolated historical chat messages for a video.
        """
        video_id = video_id.strip() if video_id else ""
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="video_id cannot be empty or whitespace.",
            )

        # Validate ownership
        video = VideoRepository.get_by_id(db, video_id=video_id, user_id=user_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video '{video_id}' not found or you do not have permission to access it.",
            )

        messages = ChatRepository.get_history(db, user_id=user_id, video_id=video_id, limit=limit)
        response_messages = []
        for m in messages:
            citations = []
            if m.sources and isinstance(m.sources, list):
                for src in m.sources:
                    try:
                        citations.append(ChatSourceCitation(**src))
                    except Exception:
                        pass

            response_messages.append(
                AskVidyoraResponse(
                    id=m.id,
                    video_id=m.video_id,
                    question=m.question,
                    answer=m.answer,
                    sources=citations,
                    model_used=m.model_used,
                    created_at=m.created_at.isoformat() if hasattr(m.created_at, "isoformat") else str(m.created_at),
                )
            )

        return ChatHistoryResponse(
            video_id=video_id,
            total_messages=len(response_messages),
            total_count=len(response_messages),
            messages=response_messages,
        )

    @classmethod
    def clear_chat_history(
        cls,
        db: Session,
        user_id: str,
        video_id: str,
    ) -> dict:
        """
        Clears chat history for a video belonging to the authenticated user.
        """
        video_id = video_id.strip() if video_id else ""
        if not video_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="video_id cannot be empty or whitespace.",
            )

        video = VideoRepository.get_by_id(db, video_id=video_id, user_id=user_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video '{video_id}' not found or you do not have permission to access it.",
            )

        deleted = ChatRepository.clear_history(db, user_id=user_id, video_id=video_id)
        return {
            "status": "success",
            "message": f"Cleared {deleted} chat messages for video {video_id}.",
            "deleted_count": deleted,
        }
