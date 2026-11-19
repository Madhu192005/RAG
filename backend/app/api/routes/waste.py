"""
WasteWise AI – Waste Management Endpoints
------------------------------------------
GET  /api/waste/categories          -> Standard 4 waste categories
POST /api/waste/reports             -> Submit a waste report
GET  /api/waste/reports             -> List waste reports with optional filtering
GET  /api/waste/reports/{report_id} -> Inspect single waste report
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.waste import WasteCategoryItem, WasteReportCreate, WasteReportResponse
from app.services.waste_service import (
    create_report,
    get_all_categories,
    get_report_by_id,
    get_reports,
)

router = APIRouter(prefix="/waste", tags=["Waste Management"])


@router.get(
    "/categories",
    response_model=List[WasteCategoryItem],
    summary="List standardized waste categories",
    description="Returns the 4 core streams: Wet waste, Dry waste, Sanitary waste, and Special-care waste with disposal guidelines.",
)
def list_categories():
    return get_all_categories()


@router.post(
    "/reports",
    response_model=WasteReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a waste report",
    description="Allows citizens or logged-in users to report segregated or unmanaged waste.",
)
def submit_report(
    report_in: WasteReportCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    user_id = current_user.id if current_user else None
    report = create_report(db=db, report_in=report_in, user_id=user_id)
    return report


@router.get(
    "/reports",
    response_model=List[WasteReportResponse],
    summary="List waste reports",
    description="Fetches recent waste reports with optional category and status filtering.",
)
def list_reports(
    category: Optional[str] = Query(None, description="Filter by stream category"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by report status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    reports = get_reports(
        db=db,
        category=category,
        report_status=status_filter,
        skip=skip,
        limit=limit,
    )
    return reports


@router.get(
    "/reports/{report_id}",
    response_model=WasteReportResponse,
    summary="Get waste report by ID",
    description="Fetches full audit details for a specific waste report.",
)
def read_report(report_id: int, db: Session = Depends(get_db)):
    return get_report_by_id(db=db, report_id=report_id)
