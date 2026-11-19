"""Grounded AI assistant endpoint."""

import logging
from functools import lru_cache

from ai_engine.generation.groq_generator import GenerationUnavailable
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.core.config import settings
from app.database.connection import get_db
from app.models.user import User
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.conversation_service import load_conversation_history, persist_turn
from app.services.rag_service import GroundedRAGService, RAGServiceUnavailable

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])
logger = logging.getLogger("wastewise_ai.assistant")


@lru_cache(maxsize=1)
def get_rag_service() -> GroundedRAGService:
    return GroundedRAGService()


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Ask the grounded waste-management assistant",
    description=(
        "Retrieves current knowledge-base passages, generates a source-cited answer, and "
        "stores conversation history for authenticated users. Anonymous questions are not stored."
    ),
)
def chat_with_assistant(
    chat_in: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_current_user),
):
    conversation = None
    history = []
    session_id = None
    if current_user is not None:
        conversation, session_id, history = load_conversation_history(
            db, current_user, chat_in.session_id, settings.RAG_HISTORY_LIMIT
        )
    elif chat_in.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue a saved conversation.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = get_rag_service().answer(
            chat_in,
            history=history,
            session_id=session_id,
        )
    except GenerationUnavailable as exc:
        logger.warning("Assistant generation is not configured or available.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Grounded assistant generation is not configured or is temporarily unavailable.",
        ) from exc
    except RAGServiceUnavailable as exc:
        logger.exception("Assistant retrieval service is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The assistant knowledge base is temporarily unavailable.",
        ) from exc

    if current_user is not None and session_id is not None:
        persist_turn(
            db,
            user=current_user,
            conversation=conversation,
            session_id=session_id,
            question=chat_in.question,
            response=response,
        )
    return response
