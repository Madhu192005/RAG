"""
WasteWise AI – Collection Request and Collection Record Models
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.database.connection import Base


class CollectionRequest(Base):
    __tablename__ = "collection_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(
        Integer,
        ForeignKey("waste_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    category_label = Column(String(100), nullable=False)
    waste_classification_id = Column(Integer, ForeignKey("waste_classifications.id", ondelete="SET NULL"), nullable=True, index=True)
    recycling_center_id = Column(Integer, ForeignKey("recycling_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    weight_tier = Column(String(100), nullable=True)
    quantity = Column(Numeric(12, 2), nullable=True)
    quantity_unit = Column(String(20), default="kg", nullable=False)
    pickup_address = Column(Text, nullable=False)
    pickup_latitude = Column(Float, nullable=True)
    pickup_longitude = Column(Float, nullable=True)
    preferred_pickup_date = Column(String(100), nullable=False)
    time_slot = Column(String(100), nullable=True)
    additional_notes = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    assigned_staff_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    internal_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="collection_requests", foreign_keys=[user_id])
    waste_category = relationship("WasteCategory", back_populates="collection_requests")
    collection_records = relationship("CollectionRecord", back_populates="request")
    classification = relationship("WasteClassification")
    recycling_center = relationship("RecyclingCenter")
    assigned_staff = relationship("User", foreign_keys=[assigned_staff_id])

    @hybrid_property
    def category(self) -> str:
        return self.category_label

    @hybrid_property
    def preferred_date(self) -> str:
        return self.preferred_pickup_date

    @hybrid_property
    def requested_date(self) -> str:
        return self.preferred_pickup_date

    @hybrid_property
    def special_instructions(self):
        return self.additional_notes


class CollectionRecord(Base):
    __tablename__ = "collection_records"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("collection_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    collector_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    collected_quantity = Column(Numeric(12, 2), nullable=False)
    quantity_unit = Column(String(20), default="kg", nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    request = relationship("CollectionRequest", back_populates="collection_records")
    collector = relationship("User", back_populates="collection_records", foreign_keys=[collector_id])
