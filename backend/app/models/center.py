"""
WasteWise AI – Recycling Center and Accepted Waste Type Models
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.database.connection import Base


class RecyclingCenter(Base):
    __tablename__ = "recycling_centers"

    id = Column(Integer, primary_key=True, index=True)
    center_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    center_type = Column(String(100), nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    operating_hours = Column(String(100), nullable=True)
    verification_status = Column(String(50), default="pending", nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    accepted_waste_types = relationship(
        "AcceptedWasteType",
        back_populates="center",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def name(self) -> str:
        return self.center_name

    @property
    def accepted_categories(self):
        names = set()
        for mapping in self.accepted_waste_types:
            if mapping.waste_category is not None:
                names.add(mapping.waste_category.category_name)
        return sorted(names)

    @property
    def accepted_materials(self):
        return sorted({mapping.accepted_waste_label for mapping in self.accepted_waste_types
                       if mapping.accepted_waste_label})


class AcceptedWasteType(Base):
    __tablename__ = "accepted_waste_types"
    __table_args__ = (
        UniqueConstraint("center_id", "category_id", "accepted_waste_label", name="uq_center_category_material"),
    )

    id = Column(Integer, primary_key=True, index=True)
    center_id = Column(
        Integer,
        ForeignKey("recycling_centers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("waste_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    accepted_waste_label = Column(String(100), nullable=True, index=True)

    center = relationship("RecyclingCenter", back_populates="accepted_waste_types")
    waste_category = relationship("WasteCategory", back_populates="accepted_waste_types")
