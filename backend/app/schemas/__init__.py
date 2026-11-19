"""
WasteWise AI – Pydantic Validation Schemas Package
"""

from app.schemas.auth import UserRegister, UserLogin, Token, TokenData
from app.schemas.user import UserResponse, UserProfileUpdate
from app.schemas.waste import WasteCategoryItem, WasteReportCreate, WasteReportResponse
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse, AssistantSource
from app.schemas.center import RecyclingCenterCreate, RecyclingCenterResponse
from app.schemas.collection import CollectionRequestCreate, CollectionRequestResponse, CollectionStatusUpdate
from app.schemas.notification import NotificationResponse
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnalyticsMonthlyResponse,
    AnalyticsCategoriesResponse,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenData",
    "UserResponse",
    "UserProfileUpdate",
    "WasteCategoryItem",
    "WasteReportCreate",
    "WasteReportResponse",
    "AssistantChatRequest",
    "AssistantChatResponse",
    "AssistantSource",
    "RecyclingCenterCreate",
    "RecyclingCenterResponse",
    "CollectionRequestCreate",
    "CollectionRequestResponse",
    "CollectionStatusUpdate",
    "NotificationResponse",
    "AnalyticsSummaryResponse",
    "AnalyticsMonthlyResponse",
    "AnalyticsCategoriesResponse",
]
