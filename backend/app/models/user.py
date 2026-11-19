"""
WasteWise AI – User Database Model
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    role_rel = relationship("Role", back_populates="users")
    waste_reports = relationship("WasteReport", back_populates="user")
    collection_requests = relationship(
        "CollectionRequest", back_populates="user", foreign_keys="CollectionRequest.user_id"
    )
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    collection_records = relationship(
        "CollectionRecord",
        back_populates="collector",
        foreign_keys="CollectionRecord.collector_id",
    )
    audit_logs = relationship("AuditLog", back_populates="user")
    assistant_conversations = relationship("AssistantConversation", back_populates="user")

    @hybrid_property
    def role(self) -> str:
        if self.role_rel is not None:
            return self.role_rel.role_name
        return "citizen"
