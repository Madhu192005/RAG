"""
WasteWise AI – Waste Category & Waste Report Models
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.database.connection import Base


class WasteCategory(Base):
    __tablename__ = "waste_categories"

    id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    waste_reports = relationship("WasteReport", back_populates="waste_category")
    collection_requests = relationship("CollectionRequest", back_populates="waste_category")
    accepted_waste_types = relationship("AcceptedWasteType", back_populates="waste_category")


class WasteReport(Base):
    __tablename__ = "waste_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(
        Integer,
        ForeignKey("waste_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    waste_description = Column(Text, nullable=True)
    image_path = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    estimated_weight_kg = Column(String(50), nullable=True)
    report_status = Column(String(50), default="reported", nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="waste_reports")
    waste_category = relationship("WasteCategory", back_populates="waste_reports")

    @hybrid_property
    def category(self) -> str:
        if self.waste_category is not None:
            return self.waste_category.category_name
        return ""

    @hybrid_property
    def description(self):
        return self.waste_description

    @hybrid_property
    def image_filename(self):
        return self.image_path

    @hybrid_property
    def status(self) -> str:
        return self.report_status
