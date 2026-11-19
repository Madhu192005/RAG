"""Owner-scoped collection operations and staff lifecycle enforcement."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ai_engine.classification.class_mapping import CLASS_LABELS, DEFAULT_CATEGORY_MAPPING
from app.models.center import AcceptedWasteType, RecyclingCenter
from app.models.classification import WasteClassification
from app.models.collection import CollectionRecord, CollectionRequest
from app.models.user import User
from app.schemas.collection import CollectionRequestCreate, CollectionStatusUpdate
from app.services.audit_service import record_audit
from app.services.notification_service import create_notification
from app.services.seed_service import get_category_by_name, seed_reference_data
from app.services.waste_service import validate_category_name

TRANSITIONS = {
    "pending": {"approved", "rejected", "cancelled"},
    "approved": {"assigned", "rejected", "cancelled"},
    "assigned": {"scheduled", "cancelled"},
    "scheduled": {"in_progress", "cancelled"},
    "in_progress": {"completed"},
    "completed": set(), "rejected": set(), "cancelled": set(),
}

def _request_query(db: Session):
    return db.query(CollectionRequest).options(joinedload(CollectionRequest.waste_category),
        joinedload(CollectionRequest.collection_records), joinedload(CollectionRequest.recycling_center))

def create_collection_request(db: Session, request_in: CollectionRequestCreate, user: User) -> CollectionRequest:
    seed_reference_data(db)
    classification = None
    if request_in.waste_classification_id:
        classification = db.query(WasteClassification).filter(
            WasteClassification.id == request_in.waste_classification_id,
            WasteClassification.user_id == user.id,
        ).first()
        if classification is None:
            raise HTTPException(status_code=404, detail="Confirmed classification was not found.")
        item_label = classification.confirmed_class or classification.predicted_class
        if classification.requires_confirmation and not classification.confirmed_class:
            raise HTTPException(status_code=409, detail="Confirm the classification before requesting collection.")
        if item_label not in CLASS_LABELS or DEFAULT_CATEGORY_MAPPING[item_label] == "Requires manual review":
            raise HTTPException(status_code=409, detail="This item needs manual review before collection can be requested.")
        category_name = DEFAULT_CATEGORY_MAPPING[item_label]
        if request_in.category and validate_category_name(request_in.category) != category_name:
            raise HTTPException(status_code=422, detail="Selected category does not match the confirmed classification.")
    elif request_in.category:
        category_name = validate_category_name(request_in.category)
        item_label = None
    else:
        raise HTTPException(status_code=422, detail="A category or confirmed classification is required.")
    category = get_category_by_name(db, category_name)

    center = None
    if request_in.recycling_center_id:
        center = db.query(RecyclingCenter).filter(RecyclingCenter.id == request_in.recycling_center_id,
            RecyclingCenter.is_active.is_(True), RecyclingCenter.verification_status == "verified").first()
        if center is None:
            raise HTTPException(status_code=404, detail="Verified active recycling center was not found.")
        acceptance = db.query(AcceptedWasteType).filter(AcceptedWasteType.center_id == center.id,
                                                         AcceptedWasteType.category_id == category.id)
        if item_label:
            acceptance = acceptance.filter(AcceptedWasteType.accepted_waste_label == item_label)
        else:
            acceptance = acceptance.filter(AcceptedWasteType.accepted_waste_label.is_(None))
        if acceptance.first() is None:
            raise HTTPException(status_code=422, detail="The selected center does not explicitly accept this item or waste stream.")

    request = CollectionRequest(
        user_id=user.id, category_id=category.id, category_label=category_name,
        full_name=request_in.full_name, email=str(request_in.email), phone=request_in.phone,
        waste_classification_id=classification.id if classification else None,
        recycling_center_id=center.id if center else None,
        weight_tier=request_in.weight_tier, quantity=request_in.quantity,
        quantity_unit=request_in.quantity_unit, pickup_address=request_in.pickup_address,
        pickup_latitude=request_in.pickup_latitude, pickup_longitude=request_in.pickup_longitude,
        preferred_pickup_date=request_in.preferred_date, time_slot=request_in.time_slot,
        additional_notes=request_in.special_instructions, status="pending",
    )
    db.add(request); db.flush()
    record_audit(db, action="collection_request.create", entity_type="collection_request", entity_id=request.id, user_id=user.id)
    create_notification(db, user.id, "Collection request submitted", f"Request #{request.id} was submitted and is awaiting review.")
    db.commit()
    return get_collection_request_by_id(db, request.id)

def get_collection_requests(db: Session, user_id: Optional[int] = None, status_filter: Optional[str] = None,
                            staff_id: Optional[int] = None,
                            skip: int = 0, limit: int = 50) -> List[CollectionRequest]:
    query = _request_query(db)
    if user_id is not None:
        query = query.filter(CollectionRequest.user_id == user_id)
    if staff_id is not None:
        query = query.filter(CollectionRequest.assigned_staff_id == staff_id)
    if status_filter:
        normalized = status_filter.lower()
        if normalized not in TRANSITIONS:
            raise HTTPException(status_code=422, detail="Unsupported collection request status.")
        query = query.filter(CollectionRequest.status == normalized)
    return query.order_by(CollectionRequest.created_at.desc()).offset(skip).limit(limit).all()

def get_collection_request_by_id(db: Session, request_id: int) -> CollectionRequest:
    request = _request_query(db).filter(CollectionRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Collection request was not found.")
    return request

def update_collection_status(db: Session, request_id: int, status_in: CollectionStatusUpdate, actor: User) -> CollectionRequest:
    request = get_collection_request_by_id(db, request_id)
    new_status = status_in.status.strip().lower()
    allowed = TRANSITIONS.get(request.status, set())
    is_admin = actor.role == "admin"
    is_owner = request.user_id == actor.id
    is_assigned_collector = actor.role == "collector" and request.assigned_staff_id == actor.id
    if not (is_admin or is_owner or is_assigned_collector):
        raise HTTPException(status_code=404, detail="Collection request was not found.")
    if is_owner and not is_admin and new_status != "cancelled":
        raise HTTPException(status_code=403, detail="Users may only cancel their own eligible requests.")
    if actor.role == "collector" and is_assigned_collector and new_status not in {"in_progress", "completed"}:
        raise HTTPException(status_code=403, detail="Collectors can only start or complete assigned requests.")
    if new_status == "assigned":
        raise HTTPException(status_code=403, detail="Use the staff assignment endpoint to assign a request.")
    if new_status not in allowed:
        raise HTTPException(status_code=409, detail=f"Cannot transition request from '{request.status}' to '{new_status}'.")
    if new_status == "cancelled":
        if not (is_admin or (is_owner and request.status in {"pending", "approved"})):
            raise HTTPException(status_code=403, detail="Only an administrator or the owner of a pending request can cancel it.")
    elif new_status in {"approved", "rejected", "assigned", "scheduled"}:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only administrators can approve, reject, assign, or schedule requests.")
    elif new_status in {"in_progress", "completed"}:
        if not (is_admin or is_assigned_collector):
            raise HTTPException(status_code=403, detail="Only the assigned collector or an administrator can update this request.")
    if new_status == "completed":
        if status_in.collected_quantity is None:
            raise HTTPException(status_code=422, detail="A collected quantity is required to complete a request.")
        db.add(CollectionRecord(request_id=request.id, collector_id=actor.id,
            collected_quantity=status_in.collected_quantity, quantity_unit=status_in.quantity_unit or request.quantity_unit,
            notes=status_in.record_notes or status_in.internal_notes, collected_at=datetime.utcnow()))
    request.status = new_status
    request.updated_at = datetime.utcnow()
    if status_in.internal_notes and actor.role in {"admin", "collector"}:
        request.internal_notes = status_in.internal_notes
    record_audit(db, action=f"collection_request.{new_status}", entity_type="collection_request", entity_id=request.id, user_id=actor.id)
    if request.user_id:
        event_titles = {"approved": "Collection request approved", "rejected": "Collection request rejected",
                        "assigned": "Staff assigned", "scheduled": "Collection scheduled",
                        "in_progress": "Collection started", "completed": "Collection completed",
                        "cancelled": "Collection request cancelled"}
        create_notification(db, request.user_id, event_titles[new_status],
                           f"Request #{request.id} status: {new_status.replace('_', ' ')}.")
    db.commit()
    return get_collection_request_by_id(db, request.id)

def assign_collection_staff(db: Session, request_id: int, staff_id: int, internal_notes: Optional[str], admin: User):
    request = get_collection_request_by_id(db, request_id)
    if request.status not in {"approved", "assigned"}:
        raise HTTPException(status_code=409, detail="Only approved requests can be assigned to staff.")
    staff = db.query(User).filter(User.id == staff_id, User.is_active.is_(True)).first()
    if staff is None or staff.role != "collector":
        raise HTTPException(status_code=422, detail="Choose an active collector account.")
    request.assigned_staff_id = staff.id
    request.status = "assigned"
    request.updated_at = datetime.utcnow()
    if internal_notes:
        request.internal_notes = internal_notes
    record_audit(db, action="collection_request.assign", entity_type="collection_request", entity_id=request.id, user_id=admin.id)
    create_notification(db, staff.id, "Collection assigned", f"Request #{request.id} has been assigned to you.")
    if request.user_id:
        create_notification(db, request.user_id, "Collection staff assigned", f"Staff has been assigned to request #{request.id}.")
    db.commit()
    return get_collection_request_by_id(db, request.id)

def history_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 50):
    return get_collection_requests(db, user_id=user_id, skip=skip, limit=limit)
