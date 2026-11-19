"""Database-backed center directory, material matching, and distance ranking."""
import math
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from ai_engine.classification.class_mapping import CLASS_LABELS, DEFAULT_CATEGORY_MAPPING
from app.models.center import AcceptedWasteType, RecyclingCenter
from app.models.classification import WasteClassification
from app.models.user import User
from app.schemas.center import RecyclingCenterCreate, RecyclingCenterResponse, RecyclingCenterUpdate
from app.services.audit_service import record_audit
from app.services.seed_service import get_category_by_name, seed_reference_data
from app.services.waste_service import validate_category_name

VERIFICATION_STATES = {"pending", "verified", "rejected"}
MAX_SEARCH_RADIUS_KM = 50.0

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance; caller validates coordinates before invoking."""
    earth_radius_km = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    a = min(1.0, max(0.0, a))
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _center_query(db: Session):
    return db.query(RecyclingCenter).options(
        joinedload(RecyclingCenter.accepted_waste_types).joinedload(AcceptedWasteType.waste_category)
    )

def _to_response(center: RecyclingCenter) -> RecyclingCenterResponse:
    return RecyclingCenterResponse(
        id=center.id, name=center.center_name, description=center.description,
        address=center.address, city=center.city, state=center.state, country=center.country,
        postal_code=center.postal_code, phone=center.phone, email=center.email,
        center_type=center.center_type, operating_hours=center.operating_hours,
        accepted_categories=center.accepted_categories, accepted_waste_types=center.accepted_materials,
        is_active=center.is_active, is_demo_data=False, verification_status=center.verification_status,
        latitude=center.latitude, longitude=center.longitude,
    )

def _replace_acceptance(db: Session, center: RecyclingCenter, categories, waste_types) -> None:
    db.query(AcceptedWasteType).filter(AcceptedWasteType.center_id == center.id).delete(synchronize_session=False)
    category_ids = {}
    for raw in categories:
        name = validate_category_name(raw)
        category = get_category_by_name(db, name)
        category_ids[name] = category.id
        db.add(AcceptedWasteType(center_id=center.id, category_id=category.id))
    for label in waste_types:
        if label not in CLASS_LABELS:
            raise HTTPException(status_code=422, detail=f"Unsupported accepted waste type: {label}")
        stream = DEFAULT_CATEGORY_MAPPING[label]
        if stream == "Requires manual review":
            raise HTTPException(status_code=422, detail="Unknown items cannot be listed as an accepted material.")
        if stream not in category_ids:
            category_ids[stream] = get_category_by_name(db, stream).id
        db.add(AcceptedWasteType(center_id=center.id, category_id=category_ids[stream], accepted_waste_label=label))

def create_center(db: Session, center_in: RecyclingCenterCreate, admin_user_id: int) -> RecyclingCenterResponse:
    seed_reference_data(db)
    if center_in.verification_status not in VERIFICATION_STATES:
        raise HTTPException(status_code=422, detail="Unsupported verification status.")
    values = center_in.model_dump(exclude={"accepted_categories", "accepted_waste_types"})
    center = RecyclingCenter(center_name=values.pop("center_name"), **values)
    db.add(center); db.flush()
    _replace_acceptance(db, center, center_in.accepted_categories, center_in.accepted_waste_types)
    record_audit(db, action="recycling_center.create", entity_type="recycling_center", entity_id=center.id, user_id=admin_user_id)
    db.commit()
    return get_center_by_id(db, center.id, include_unverified=True)

def update_center(db: Session, center_id: int, payload: RecyclingCenterUpdate, admin_user_id: int) -> RecyclingCenterResponse:
    center = db.query(RecyclingCenter).filter(RecyclingCenter.id == center_id).first()
    if center is None:
        raise HTTPException(status_code=404, detail="Recycling center was not found.")
    values = payload.model_dump(exclude_unset=True)
    categories = values.pop("accepted_categories", None)
    materials = values.pop("accepted_waste_types", None)
    if "verification_status" in values and values["verification_status"] not in VERIFICATION_STATES:
        raise HTTPException(status_code=422, detail="Unsupported verification status.")
    for key, value in values.items():
        setattr(center, key, value)
    if categories is not None or materials is not None:
        current_categories = sorted({mapping.waste_category.category_name for mapping in center.accepted_waste_types
                                     if mapping.accepted_waste_label is None and mapping.waste_category}) if categories is None else categories
        current_materials = center.accepted_materials if materials is None else materials
        _replace_acceptance(db, center, current_categories, current_materials)
    record_audit(db, action="recycling_center.update", entity_type="recycling_center", entity_id=center.id, user_id=admin_user_id)
    db.commit()
    return get_center_by_id(db, center.id, include_unverified=True)

def deactivate_center(db: Session, center_id: int, admin_user_id: int) -> RecyclingCenterResponse:
    center = db.query(RecyclingCenter).filter(RecyclingCenter.id == center_id).first()
    if center is None:
        raise HTTPException(status_code=404, detail="Recycling center was not found.")
    center.is_active = False
    record_audit(db, action="recycling_center.deactivate", entity_type="recycling_center", entity_id=center.id, user_id=admin_user_id)
    db.commit()
    return get_center_by_id(db, center.id, include_unverified=True)

def get_centers(db: Session, location: Optional[str] = None, category: Optional[str] = None,
                skip: int = 0, limit: int = 50, *, postal_code: Optional[str] = None,
                center_type: Optional[str] = None, verification_status: Optional[str] = None,
                waste_type: Optional[str] = None, active_only: bool = True,
                include_unverified: bool = False) -> List[RecyclingCenterResponse]:
    query = _center_query(db)
    if not include_unverified:
        query = query.filter(RecyclingCenter.verification_status == "verified")
    if active_only:
        query = query.filter(RecyclingCenter.is_active.is_(True))
    if verification_status:
        if verification_status not in VERIFICATION_STATES:
            raise HTTPException(status_code=422, detail="Unsupported verification status.")
        query = query.filter(RecyclingCenter.verification_status == verification_status)
    if location:
        term = f"%{location.strip()}%"
        query = query.filter((RecyclingCenter.city.ilike(term)) | (RecyclingCenter.address.ilike(term)) |
                             (RecyclingCenter.postal_code.ilike(term)) | (RecyclingCenter.center_name.ilike(term)))
    if postal_code:
        query = query.filter(RecyclingCenter.postal_code.ilike(f"%{postal_code.strip()}%"))
    if center_type:
        query = query.filter(RecyclingCenter.center_type.ilike(center_type.strip()))
    if category:
        canonical = validate_category_name(category)
        category_row = get_category_by_name(db, canonical)
        ids = db.query(AcceptedWasteType.center_id).filter(
            AcceptedWasteType.category_id == category_row.id, AcceptedWasteType.accepted_waste_label.is_(None))
        query = query.filter(RecyclingCenter.id.in_(ids))
    if waste_type:
        if waste_type in CLASS_LABELS:
            ids = db.query(AcceptedWasteType.center_id).filter(AcceptedWasteType.accepted_waste_label == waste_type)
        else:
            category_row = get_category_by_name(db, validate_category_name(waste_type))
            ids = db.query(AcceptedWasteType.center_id).filter(
                AcceptedWasteType.category_id == category_row.id, AcceptedWasteType.accepted_waste_label.is_(None))
        query = query.filter(RecyclingCenter.id.in_(ids))
    return [_to_response(row) for row in query.order_by(RecyclingCenter.center_name.asc()).offset(skip).limit(limit).all()]

def get_center_by_id(db: Session, center_id: int, *, include_unverified: bool = False) -> RecyclingCenterResponse:
    query = _center_query(db).filter(RecyclingCenter.id == center_id)
    if not include_unverified:
        query = query.filter(RecyclingCenter.verification_status == "verified", RecyclingCenter.is_active.is_(True))
    center = query.first()
    if center is None:
        raise HTTPException(status_code=404, detail="Verified recycling center was not found.")
    return _to_response(center)

def _matching_query(db: Session, waste_type: str, *, exact_material: bool):
    query = _center_query(db).join(AcceptedWasteType).filter(
        RecyclingCenter.verification_status == "verified", RecyclingCenter.is_active.is_(True)
    )
    if exact_material:
        query = query.filter(AcceptedWasteType.accepted_waste_label == waste_type)
    else:
        category = get_category_by_name(db, validate_category_name(waste_type))
        query = query.filter(AcceptedWasteType.category_id == category.id, AcceptedWasteType.accepted_waste_label.is_(None))
    return query.distinct()

def _center_match(center, distance=None, waste_type=None):
    return {"id": center.id, "center_name": center.center_name, "description": center.description,
            "address": center.address, "city": center.city, "state": center.state, "country": center.country,
            "postal_code": center.postal_code, "phone": center.phone, "email": center.email,
            "operating_hours": center.operating_hours, "center_type": center.center_type,
            "latitude": center.latitude, "longitude": center.longitude, "distance_km": distance,
            "accepted_waste_types": center.accepted_materials, "accepted_categories": center.accepted_categories,
            "verification_status": center.verification_status,
            "match_reason": f"Center explicitly accepts {waste_type}." if waste_type else "Center explicitly accepts this waste stream."}

def find_nearby_centers(db: Session, *, latitude: float, longitude: float, radius_km: float,
                        waste_type: str, center_type: Optional[str] = None):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise HTTPException(status_code=422, detail="Coordinates are outside the valid range.")
    if not 0 < radius_km <= MAX_SEARCH_RADIUS_KM:
        raise HTTPException(status_code=422, detail=f"Radius must be greater than 0 and at most {MAX_SEARCH_RADIUS_KM:g} km.")
    exact = waste_type in CLASS_LABELS
    candidates = _matching_query(db, waste_type, exact_material=exact).all()
    matches = []
    for center in candidates:
        if center_type and (center.center_type or "").casefold() != center_type.casefold():
            continue
        if center.latitude is None or center.longitude is None:
            continue
        distance = haversine_distance_km(latitude, longitude, center.latitude, center.longitude)
        if distance <= radius_km:
            matches.append(_center_match(center, round(distance, 2), waste_type))
    matches.sort(key=lambda row: row["distance_km"])
    return {"status": "success" if matches else "no_matches", "message": None if matches else "No verified recycling centers explicitly accepting this waste type were found within the selected radius.",
            "waste_type": waste_type, "matching_centers": matches}

def recommend_for_classification(db: Session, classification_id: int, user: User, *,
                                 latitude: Optional[float] = None, longitude: Optional[float] = None,
                                 radius_km: Optional[float] = None, location: Optional[str] = None):
    row = db.query(WasteClassification).filter(WasteClassification.id == classification_id,
                                               WasteClassification.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Classification was not found.")
    label = row.confirmed_class or row.predicted_class
    if row.requires_confirmation and row.confirmed_class is None:
        raise HTTPException(status_code=409, detail="Confirm the classification before requesting center recommendations.")
    location = location or row.location
    if label not in CLASS_LABELS or DEFAULT_CATEGORY_MAPPING[label] == "Requires manual review":
        return {"status": "manual_review", "message": "This item needs manual review before a recycling center can be recommended.", "waste_type": label, "matching_centers": []}
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together.")
    if latitude is not None and (not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Coordinates are outside the valid range.")
    if radius_km is not None and (latitude is None or not 0 < radius_km <= MAX_SEARCH_RADIUS_KM):
        raise HTTPException(status_code=422, detail=f"Radius requires coordinates and must be at most {MAX_SEARCH_RADIUS_KM:g} km.")
    centers = _matching_query(db, label, exact_material=True).all()
    matches = []
    for center in centers:
        if location:
            loc = location.casefold()
            if not any(loc in (value or "").casefold() for value in (center.city, center.state, center.country, center.postal_code)):
                continue
        distance = None
        if latitude is not None and center.latitude is not None and center.longitude is not None:
            distance = round(haversine_distance_km(latitude, longitude, center.latitude, center.longitude), 2)
        if radius_km is not None and (distance is None or distance > radius_km):
            continue
        matches.append(_center_match(center, distance, label))
    if latitude is not None or location:
        matches.sort(key=lambda row: (row["distance_km"] is None, row["distance_km"] or float("inf")))
    return {"status": "success" if matches else "no_matches",
            "message": None if matches else "No verified recycling centers explicitly accepting this material were found.",
            "classification_id": row.id, "waste_type": label,
            "waste_stream": DEFAULT_CATEGORY_MAPPING[label], "matching_centers": matches}
