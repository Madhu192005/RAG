"""
WasteWise AI – Unified API Router
----------------------------------
Aggregates all domain routers under the /api namespace.
"""

from fastapi import APIRouter
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.waste import router as waste_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.centers import router as centers_router, compat_router as recycling_centers_router
from app.api.routes.collection import router as collection_router, compat_router as collections_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.classification import router as classification_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(waste_router)
api_router.include_router(assistant_router)
api_router.include_router(centers_router)
api_router.include_router(recycling_centers_router)
api_router.include_router(collection_router)
api_router.include_router(collections_router)
api_router.include_router(analytics_router)
api_router.include_router(notifications_router)
api_router.include_router(classification_router)
