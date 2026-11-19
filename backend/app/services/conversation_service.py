"""Persistence helpers for authenticated assistant conversations."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.conversation import AssistantConversation, AssistantMessage
from app.models.user import User
from app.schemas.assistant import AssistantChatResponse


def load_conversation_history(
    db: Session,
    user: User,
    session_id: Optional[str],
    limit: int,
) -> Tuple[Optional[AssistantConversation], Optional[str], List[Dict[str, str]]]:
    if session_id is None:
        return None, str(uuid4()), []
    try:
        conversation_id = str(UUID(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.") from exc
    conversation = (
        db.query(AssistantConversation)
        .filter(
            AssistantConversation.conversation_id == conversation_id,
            AssistantConversation.user_id == user.id,
        )
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if limit == 0:
        return conversation, conversation_id, []
    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
        .limit(limit)
        .all()
    )
    history = [{"role": message.role, "content": message.content} for message in reversed(messages)]
    return conversation, conversation_id, history


def persist_turn(
    db: Session,
    *,
    user: User,
    conversation: Optional[AssistantConversation],
    session_id: str,
    question: str,
    response: AssistantChatResponse,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if conversation is None:
        conversation = AssistantConversation(
            conversation_id=session_id,
            user_id=user.id,
            title=question[:255],
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
    else:
        conversation.updated_at = now
    db.add_all(
        [
            AssistantMessage(
                conversation_id=session_id,
                role="user",
                content=question,
                created_at=now,
            ),
            AssistantMessage(
                conversation_id=session_id,
                role="assistant",
                content=response.answer,
                source_metadata=[source.model_dump(mode="json") for source in response.sources],
                created_at=now,
            ),
        ]
    )
    db.commit()
