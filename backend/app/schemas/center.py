"""Validated recycling center management and response schemas."""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from ai_engine.classification.class_mapping import CLASS_LABELS

class RecyclingCenterCreate(BaseModel):
    center_name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    address: str = Field(min_length=5, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    center_type: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    operating_hours: Optional[str] = Field(None, max_length=100)
    verification_status: Literal["pending", "verified", "rejected"] = "pending"
    is_active: bool = True
    accepted_categories: List[str] = Field(default_factory=list, max_length=4)
    accepted_waste_types: List[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_location_and_acceptance(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        if len(set(self.accepted_categories)) != len(self.accepted_categories):
            raise ValueError("Accepted categories cannot contain duplicates.")
        if len(set(self.accepted_waste_types)) != len(self.accepted_waste_types):
            raise ValueError("Accepted waste types cannot contain duplicates.")
        invalid = set(self.accepted_waste_types) - set(CLASS_LABELS)
        if invalid:
            raise ValueError(f"Unsupported accepted waste types: {sorted(invalid)}")
        return self

class RecyclingCenterUpdate(BaseModel):
    center_name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    address: Optional[str] = Field(None, min_length=5, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    center_type: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    operating_hours: Optional[str] = Field(None, max_length=100)
    verification_status: Optional[Literal["pending", "verified", "rejected"]] = None
    is_active: Optional[bool] = None
    accepted_categories: Optional[List[str]] = Field(None, max_length=4)
    accepted_waste_types: Optional[List[str]] = Field(None, max_length=8)

    @model_validator(mode="after")
    def validate_location_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            # An omitted pair means unchanged; explicit clearing is not supported by this API.
            if self.latitude is not None or self.longitude is not None:
                raise ValueError("Latitude and longitude must be updated together.")
        return self

class RecyclingCenterResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    address: str
    city: str
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    center_type: Optional[str] = None
    operating_hours: Optional[str] = None
    accepted_categories: List[str]
    accepted_waste_types: List[str] = Field(default_factory=list)
    is_active: bool
    is_demo_data: bool = False
    verification_status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class NearbyCenterResponse(BaseModel):
    status: str
    message: Optional[str] = None
    waste_type: Optional[str] = None
    waste_stream: Optional[str] = None
    matching_centers: List[dict] = Field(default_factory=list)
