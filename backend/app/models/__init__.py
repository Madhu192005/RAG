"""
WasteWise AI – SQLAlchemy Database Models Package
"""

from app.models.audit import AuditLog
from app.models.center import AcceptedWasteType, RecyclingCenter
from app.models.collection import CollectionRecord, CollectionRequest
from app.models.conversation import AssistantConversation, AssistantMessage
from app.models.classification import WasteClassification
from app.models.knowledge import DocumentChunk, DocumentVersion, IngestionJob, KnowledgeDocument
from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User
from app.models.waste import WasteCategory, WasteReport

__all__ = [
    "Role",
    "User",
    "WasteCategory",
    "WasteReport",
    "RecyclingCenter",
    "AcceptedWasteType",
    "CollectionRequest",
    "CollectionRecord",
    "Notification",
    "AuditLog",
    "KnowledgeDocument",
    "DocumentVersion",
    "DocumentChunk",
    "IngestionJob",
    "AssistantConversation",
    "AssistantMessage",
    "WasteClassification",
]
