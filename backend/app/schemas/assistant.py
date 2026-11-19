"""Grounded assistant request and response schemas."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantMetadataFilters(BaseModel):
    source_authority: Optional[str] = Field(None, max_length=255)
    waste_category: Optional[str] = Field(None, max_length=100)
    jurisdiction: Optional[str] = Field(None, max_length=255)
    state: Optional[str] = Field(None, max_length=100)
    municipality: Optional[str] = Field(None, max_length=100)
    publication_before: Optional[date] = None
    effective_on: Optional[date] = None
    document_version_id: Optional[str] = Field(None, max_length=36)
    status: Optional[Literal["unknown", "current", "superseded", "inactive"]] = None


class AssistantChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Question about waste handling.")
    message: Optional[str] = Field(None, exclude=True)
    location: Optional[str] = Field(None, min_length=2, max_length=200, description="Explicit user location.")
    session_id: Optional[str] = Field(None, max_length=36, description="Authenticated conversation identifier.")
    metadata_filters: Optional[AssistantMetadataFilters] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def support_legacy_message(cls, value):
        if isinstance(value, dict):
            payload = dict(value)
            if not payload.get("question") and payload.get("message"):
                payload["question"] = payload["message"]
            return payload
        return value

    @model_validator(mode="after")
    def validate_nonblank_question(self):
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("Question must not be blank.")
        return self


class AssistantSource(BaseModel):
    title: str
    source_authority: Optional[str] = None
    url: Optional[str] = None
    snippet: str
    document_id: str
    document_version_id: Optional[str] = None
    chunk_id: str
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    citation_id: str


class AssistantChatResponse(BaseModel):
    answer: str
    question: str
    confidence: Literal["High evidence", "Moderate evidence", "Insufficient evidence"]
    sources: List[AssistantSource] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    warning: Optional[str] = None
    status: Literal["success", "insufficient_evidence"] = "insufficient_evidence"
    retrieval_metadata: dict = Field(default_factory=dict)
    session_id: Optional[str] = None
