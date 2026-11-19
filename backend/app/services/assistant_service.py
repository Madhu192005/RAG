"""Compatibility entry point for the grounded assistant service."""

from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.rag_service import GroundedRAGService


def process_assistant_chat(chat_in: AssistantChatRequest) -> AssistantChatResponse:
    return GroundedRAGService().answer(chat_in)
