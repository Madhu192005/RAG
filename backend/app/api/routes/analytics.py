"""
WasteWise AI – Analytics & Metrics Endpoints
---------------------------------------------
GET /api/analytics/summary    -> Live operational summary
GET /api/analytics/monthly    -> Monthly collection/diversion from stored records
GET /api/analytics/categories -> Four-category stream breakdown from stored reports
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.api.deps import require_roles
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsCategoriesResponse,
    AnalyticsMonthlyResponse,
    AnalyticsSummaryResponse,
)
from app.services.analytics_service import (
    get_category_metrics,
    get_collection_operations_metrics,
    get_monthly_metrics,
    get_summary_metrics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics & ESG"])


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get operational summary KPIs",
    description="Returns live waste report counts, collection request totals, and status breakdowns.",
)
def read_summary(db: Session = Depends(get_db)):
    return get_summary_metrics(db=db)


@router.get(
    "/monthly",
    response_model=AnalyticsMonthlyResponse,
    summary="Get monthly recovery trends",
    description="Provides calendar-month statistics computed from stored collection records.",
)
def read_monthly(db: Session = Depends(get_db)):
    return get_monthly_metrics(db=db)


@router.get(
    "/categories",
    response_model=AnalyticsCategoriesResponse,
    summary="Get stream category breakdown",
    description="Returns percentage share and volume distributed across the 4 core categories from stored reports.",
)
def read_categories(db: Session = Depends(get_db)):
    return get_category_metrics(db=db)


@router.get("/collection-operations", summary="Admin collection and center operations totals")
def read_collection_operations(db: Session = Depends(get_db),
                              admin: User = Depends(require_roles("admin"))):
    return get_collection_operations_metrics(db)
