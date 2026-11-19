"""
WasteWise AI – Waste Management Service
----------------------------------------
Supports the 4 core standardized waste classification streams:
  1. Wet waste
  2. Dry waste
  3. Sanitary waste
  4. Special-care waste
"""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.waste import WasteReport
from app.schemas.waste import WasteCategoryItem, WasteReportCreate
from app.services.audit_service import record_audit
from app.services.notification_service import create_notification
from app.services.seed_service import get_category_by_name, seed_reference_data

STANDARD_CATEGORIES: List[WasteCategoryItem] = [
    WasteCategoryItem(
        id="wet_waste",
        name="Wet waste",
        description="Biodegradable organic waste including kitchen and food residuals that decompose naturally.",
        color_code="#81c784",
        icon="🌿",
        examples=[
            "Vegetable and fruit peels",
            "Leftover cooked food",
            "Coffee grounds & tea leaves",
            "Eggshells & meat bones",
            "Garden leaves & decayed flowers",
        ],
        disposal_rules="Deposit in green bins without plastic wrapping. Suitable for composting or vermicomposting.",
    ),
    WasteCategoryItem(
        id="dry_waste",
        name="Dry waste",
        description="Non-biodegradable, recyclable, or recoverable clean materials.",
        color_code="#0288d1",
        icon="♻️",
        examples=[
            "PET plastic bottles & food containers",
            "Corrugated cardboard & newspapers",
            "Metal cans, tins & foil",
            "Glass bottles & clean jars",
            "Clean tetrapak cartons",
        ],
        disposal_rules="Rinse and dry containers before disposal. Deposit in blue bins. Hand over to certified recycling collectors.",
    ),
    WasteCategoryItem(
        id="sanitary_waste",
        name="Sanitary waste",
        description="Potentially biohazardous personal hygiene items requiring safe encapsulation.",
        color_code="#f57c00",
        icon="🩹",
        examples=[
            "Used diapers & adult incontinence pads",
            "Sanitary napkins & tampons",
            "Bandages, gauze & medical cotton",
            "Used tissues & personal hygiene wipes",
        ],
        disposal_rules="Wrap securely in non-transparent paper marked with a red cross or disposal tag. Never mix into regular dry recycling.",
    ),
    WasteCategoryItem(
        id="special_care_waste",
        name="Special-care waste",
        description="Hazardous, chemical, electrical, or toxic domestic materials requiring designated drop-offs.",
        color_code="#e53935",
        icon="⚠️",
        examples=[
            "Lithium, alkaline & lead-acid batteries",
            "Discarded electronics (phones, cables, bulbs)",
            "Expired medications & pharmaceutical blister packs",
            "Paint cans, thinners, pesticides & toxic solvents",
            "Broken thermometer mercury or CFL tubes",
        ],
        disposal_rules="Store in leak-proof containers. Deliver exclusively to certified municipal hazardous drop-off depots.",
    ),
]


def get_all_categories() -> List[WasteCategoryItem]:
    """Returns the four standardized categories."""
    return STANDARD_CATEGORIES


def validate_category_name(category_name: str) -> str:
    """
    Validates or normalizes the category string against the 4 core categories.
    """
    normalized = category_name.strip()
    valid_names = {cat.name.lower(): cat.name for cat in STANDARD_CATEGORIES}
    valid_ids = {cat.id.lower(): cat.name for cat in STANDARD_CATEGORIES}

    lowered = normalized.lower()
    if lowered in valid_names:
        return valid_names[lowered]
    if lowered in valid_ids:
        return valid_ids[lowered]

    if "wet" in lowered or "organic" in lowered or "food" in lowered:
        return "Wet waste"
    if "dry" in lowered or "plastic" in lowered or "paper" in lowered or "recycl" in lowered:
        return "Dry waste"
    if "sanitary" in lowered or "hygiene" in lowered:
        return "Sanitary waste"
    if (
        "special" in lowered
        or "hazard" in lowered
        or "battery" in lowered
        or "e-waste" in lowered
        or "electronic" in lowered
    ):
        return "Special-care waste"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Invalid waste category '{category_name}'. "
            "Allowed: 'Wet waste', 'Dry waste', 'Sanitary waste', 'Special-care waste'."
        ),
    )


def _report_query(db: Session):
    return db.query(WasteReport).options(joinedload(WasteReport.waste_category))


def create_report(
    db: Session,
    report_in: WasteReportCreate,
    user_id: Optional[int] = None,
    image_filename: Optional[str] = None,
) -> WasteReport:
    """
    Persists a new waste report entry in MySQL.
    """
    seed_reference_data(db)
    canonical_category = validate_category_name(report_in.category)
    category = get_category_by_name(db, canonical_category)

    report = WasteReport(
        user_id=user_id,
        category_id=category.id,
        title=report_in.title,
        waste_description=report_in.description,
        location=report_in.location,
        estimated_weight_kg=report_in.estimated_weight_kg,
        image_path=image_filename,
        report_status="reported",
    )
    db.add(report)
    db.flush()
    record_audit(
        db,
        action="waste_report.create",
        entity_type="waste_report",
        entity_id=report.id,
        user_id=user_id,
    )
    if user_id:
        create_notification(
            db,
            user_id=user_id,
            title="Waste report submitted",
            message=f"Your report '{report.title}' was stored successfully.",
        )
    db.commit()
    return get_report_by_id(db, report.id)


def get_reports(
    db: Session,
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    report_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[WasteReport]:
    """
    Fetches waste reports with optional category, status, or user filtering.
    """
    query = _report_query(db)
    if user_id:
        query = query.filter(WasteReport.user_id == user_id)
    if category:
        canonical = validate_category_name(category)
        category_row = get_category_by_name(db, canonical)
        query = query.filter(WasteReport.category_id == category_row.id)
    if report_status:
        query = query.filter(WasteReport.report_status == report_status)

    return query.order_by(WasteReport.created_at.desc()).offset(skip).limit(limit).all()


def get_report_by_id(db: Session, report_id: int) -> WasteReport:
    """
    Fetches a single report by ID. Raises 404 if not found.
    """
    report = _report_query(db).filter(WasteReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Waste report with ID {report_id} was not found.",
        )
    return report
