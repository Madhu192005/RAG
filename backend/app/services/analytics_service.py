"""
WasteWise AI – Analytics & Metrics Service
-------------------------------------------
All aggregates are computed from live MySQL records.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.center import RecyclingCenter
from app.models.collection import CollectionRecord, CollectionRequest
from app.models.waste import WasteCategory, WasteReport
from app.schemas.analytics import (
    AnalyticsCategoriesResponse,
    AnalyticsMonthlyResponse,
    AnalyticsSummaryResponse,
    CategoryDistributionPoint,
    CollectionStatusPoint,
    MonthlyCollectionPoint,
    WasteReportsByCategoryPoint,
)

CATEGORY_COLORS = {
    "Dry waste": "#0288d1",
    "Wet waste": "#81c784",
    "Sanitary waste": "#f57c00",
    "Special-care waste": "#e53935",
}


def _parse_weight(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).strip().replace(",", "").split()[0])
    except (TypeError, ValueError):
        return 0.0


def get_summary_metrics(db: Session) -> AnalyticsSummaryResponse:
    total_reports = db.query(func.count(WasteReport.id)).scalar() or 0
    total_requests = db.query(func.count(CollectionRequest.id)).scalar() or 0
    pending_pickups = (
        db.query(func.count(CollectionRequest.id))
        .filter(CollectionRequest.status == "pending")
        .scalar()
        or 0
    )
    active_centers = (
        db.query(func.count(RecyclingCenter.id))
        .filter(RecyclingCenter.verification_status == "verified", RecyclingCenter.is_active.is_(True))
        .scalar()
        or 0
    )

    reports = db.query(WasteReport.estimated_weight_kg).all()
    total_waste_kg = round(sum(_parse_weight(row[0]) for row in reports), 1)

    collected_qty = db.query(func.coalesce(func.sum(CollectionRecord.collected_quantity), 0)).scalar()
    if isinstance(collected_qty, Decimal):
        collected_qty = float(collected_qty)
    total_recycled_kg = round(float(collected_qty or 0), 1)

    diversion_rate = 0.0
    if total_waste_kg > 0:
        diversion_rate = round(min(total_recycled_kg / total_waste_kg, 1.0) * 100, 1)
    co2_avoided = round(total_recycled_kg * 0.28, 1)

    reports_by_category_rows = (
        db.query(WasteCategory.category_name, func.count(WasteReport.id))
        .outerjoin(WasteReport, WasteReport.category_id == WasteCategory.id)
        .group_by(WasteCategory.id, WasteCategory.category_name)
        .all()
    )
    reports_by_category = [
        WasteReportsByCategoryPoint(category=name, count=int(count or 0))
        for name, count in reports_by_category_rows
    ]

    status_rows = (
        db.query(CollectionRequest.status, func.count(CollectionRequest.id))
        .group_by(CollectionRequest.status)
        .all()
    )
    status_breakdown = [
        CollectionStatusPoint(status=name, count=int(count or 0)) for name, count in status_rows
    ]

    return AnalyticsSummaryResponse(
        total_waste_logged_kg=total_waste_kg,
        total_recycled_kg=total_recycled_kg,
        diversion_rate_pct=diversion_rate,
        co2_avoided_kg=co2_avoided,
        pending_pickups_count=pending_pickups,
        active_centers_count=active_centers,
        total_waste_reports=int(total_reports),
        total_collection_requests=int(total_requests),
        reports_by_category=reports_by_category,
        collection_status_breakdown=status_breakdown,
        is_demo_data=False,
        note="Aggregated from live database records.",
    )


def get_monthly_metrics(db: Session) -> AnalyticsMonthlyResponse:
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    collected_by_month: Dict[int, float] = defaultdict(float)
    diverted_by_month: Dict[int, float] = defaultdict(float)

    record_rows = (
        db.query(
            CollectionRecord.collected_at,
            CollectionRecord.collected_quantity,
            CollectionRequest.status,
        )
        .join(CollectionRequest, CollectionRecord.request_id == CollectionRequest.id)
        .all()
    )
    for collected_at, quantity, request_status in record_rows:
        if collected_at is None:
            continue
        qty = float(quantity or 0)
        collected_by_month[collected_at.month] += qty
        if request_status == "completed":
            diverted_by_month[collected_at.month] += qty

    points: List[MonthlyCollectionPoint] = []
    for index, label in enumerate(month_labels, start=1):
        points.append(
            MonthlyCollectionPoint(
                month=label,
                collected_kg=float(collected_by_month[index]),
                diverted_kg=float(diverted_by_month[index]),
            )
        )

    return AnalyticsMonthlyResponse(
        period="Calendar months from stored records",
        data=points,
        is_demo_data=False,
    )


def get_category_metrics(db: Session) -> AnalyticsCategoriesResponse:
    category_names = [row[0] for row in db.query(WasteCategory.category_name).all()]
    report_rows = (
        db.query(WasteCategory.category_name, WasteReport.estimated_weight_kg)
        .join(WasteReport, WasteReport.category_id == WasteCategory.id)
        .all()
    )
    counts = {name: 0 for name in category_names}
    volumes = {name: 0.0 for name in category_names}
    for name, weight in report_rows:
        counts[name] += 1
        volumes[name] += _parse_weight(weight)

    total_count = sum(counts.values())
    categories_data: List[CategoryDistributionPoint] = []
    ordered = ["Dry waste", "Wet waste", "Sanitary waste", "Special-care waste"]
    for name in ordered:
        counts.setdefault(name, 0)
        volumes.setdefault(name, 0.0)
        share = round((counts[name] / total_count) * 100, 1) if total_count else 0.0
        categories_data.append(
            CategoryDistributionPoint(
                category=name,
                share_pct=share,
                volume_kg=round(volumes[name], 1),
                color_code=CATEGORY_COLORS.get(name, "#2e7d32"),
            )
        )

    return AnalyticsCategoriesResponse(categories=categories_data, is_demo_data=False)


def get_collection_operations_metrics(db: Session) -> dict:
    """Actual lifecycle totals for the protected operations dashboard."""
    status_rows = db.query(CollectionRequest.status, func.count(CollectionRequest.id)).group_by(CollectionRequest.status).all()
    counts = {name: 0 for name in (
        "pending", "approved", "assigned", "scheduled", "in_progress", "completed", "rejected", "cancelled"
    )}
    counts.update({name: int(value) for name, value in status_rows})
    active_centers = db.query(func.count(RecyclingCenter.id)).filter(
        RecyclingCenter.verification_status == "verified", RecyclingCenter.is_active.is_(True)
    ).scalar() or 0
    unverified_centers = db.query(func.count(RecyclingCenter.id)).filter(
        RecyclingCenter.verification_status != "verified"
    ).scalar() or 0
    return {"collection_requests": counts, "active_recycling_centers": int(active_centers),
            "unverified_recycling_centers": int(unverified_centers), "is_demo_data": False}
