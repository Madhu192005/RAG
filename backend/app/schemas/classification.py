"""Classification API payloads."""
from typing import Any, Optional
from pydantic import BaseModel, Field

class ClassificationConfirmation(BaseModel):
    prediction_id: int
    confirmed_class: str = Field(min_length=1, max_length=100)

class ClassificationHistoryItem(BaseModel):
    id: int
    predicted_class: Optional[str]
    confirmed_class: Optional[str]
    waste_category: Optional[str]
    confidence_score: float
    confidence_label: str
    model_version: str
    requires_confirmation: bool
    location: Optional[str]
    created_at: Any

class ClassificationConfirmationResponse(BaseModel):
    status: str
    prediction_id: int
    confirmed_class: str
    waste_category: str
    guidance: Optional[Any] = None
