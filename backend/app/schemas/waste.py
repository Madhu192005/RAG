"""
WasteWise AI – Waste Management Schemas
Supports the 4 fundamental categories:
  • Wet waste
  • Dry waste
  • Sanitary waste
  • Special-care waste
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class WasteCategoryItem(BaseModel):
    id: str
    name: str
    description: str
    color_code: str
    icon: str
    examples: List[str]
    disposal_rules: str


class WasteReportCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    category: str = Field(..., description="Must be Wet waste, Dry waste, Sanitary waste, or Special-care waste")
    description: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = Field(None, max_length=255)
    estimated_weight_kg: Optional[str] = Field(None, max_length=50)


class WasteReportResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    category: str
    description: Optional[str] = None
    location: Optional[str] = None
    estimated_weight_kg: Optional[str] = None
    image_filename: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
