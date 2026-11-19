"""User-owned image classification history; files live outside public assets."""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database.connection import Base

class WasteClassification(Base):
    __tablename__ = "waste_classifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    predicted_class = Column(String(100), nullable=True)
    confirmed_class = Column(String(100), nullable=True)
    waste_category_id = Column(Integer, ForeignKey("waste_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    confidence_score = Column(Float, nullable=False)
    confidence_label = Column(String(30), nullable=False)
    model_version = Column(String(100), nullable=False)
    requires_confirmation = Column(Boolean, nullable=False, default=True)
    location = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user = relationship("User")
    waste_category = relationship("WasteCategory")
