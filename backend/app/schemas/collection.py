"""Collection request API contracts; owner responses omit staff-only notes."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

COLLECTION_STATUSES = {"pending", "approved", "assigned", "scheduled", "in_progress", "completed", "rejected", "cancelled"}

class CollectionRequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    category: Optional[str] = Field(None, min_length=2, max_length=100)
    waste_classification_id: Optional[int] = Field(None, gt=0)
    recycling_center_id: Optional[int] = Field(None, gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0, max_digits=12, decimal_places=2)
    quantity_unit: str = Field(default="kg", min_length=1, max_length=20)
    weight_tier: Optional[str] = Field(None, max_length=50)
    pickup_address: str = Field(min_length=10, max_length=500)
    pickup_latitude: Optional[float] = Field(None, ge=-90, le=90)
    pickup_longitude: Optional[float] = Field(None, ge=-180, le=180)
    preferred_date: str = Field(min_length=4, max_length=50)
    time_slot: Optional[str] = Field(None, max_length=50)
    special_instructions: Optional[str] = Field(None, max_length=500)

    @field_validator("preferred_date")
    @classmethod
    def validate_future_iso_date(cls, value):
        try:
            selected = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Preferred date must use YYYY-MM-DD format.") from exc
        if selected < date.today():
            raise ValueError("Preferred date cannot be in the past.")
        return selected.isoformat()

    @model_validator(mode="before")
    @classmethod
    def accept_requested_date(cls, value):
        if isinstance(value, dict):
            data = dict(value)
            if "preferred_date" not in data and "requested_date" in data:
                data["preferred_date"] = str(data.pop("requested_date"))
            return data
        return value

    @model_validator(mode="after")
    def validate_request(self):
        if not self.category and not self.waste_classification_id:
            raise ValueError("Provide a waste category or a confirmed classification.")
        if (self.pickup_latitude is None) != (self.pickup_longitude is None):
            raise ValueError("Pickup latitude and longitude must be provided together.")
        return self

class CollectionStatusUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=50)
    internal_notes: Optional[str] = Field(None, max_length=2000)
    collected_quantity: Optional[Decimal] = Field(None, gt=0, max_digits=12, decimal_places=2)
    quantity_unit: Optional[str] = Field(None, min_length=1, max_length=20)
    record_notes: Optional[str] = Field(None, max_length=2000)

class CollectionAssignment(BaseModel):
    assigned_staff_id: int = Field(gt=0)
    internal_notes: Optional[str] = Field(None, max_length=2000)

class CollectionRecordCreate(BaseModel):
    collected_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity_unit: str = Field(default="kg", min_length=1, max_length=20)
    notes: Optional[str] = Field(None, max_length=2000)

class CollectionRequestResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    full_name: str
    email: str
    phone: str
    category: str
    waste_classification_id: Optional[int] = None
    recycling_center_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    quantity_unit: str = "kg"
    weight_tier: Optional[str] = None
    pickup_address: str
    pickup_latitude: Optional[float] = None
    pickup_longitude: Optional[float] = None
    preferred_date: str
    requested_date: Optional[str] = None
    time_slot: Optional[str] = None
    special_instructions: Optional[str] = None
    status: str
    assigned_staff_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CollectionRequestAdminResponse(CollectionRequestResponse):
    internal_notes: Optional[str] = None
    collection_records: list[dict] = Field(default_factory=list)
