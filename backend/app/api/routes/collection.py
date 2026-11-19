"""Authenticated collection request APIs with owner and staff authorization."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.collection import (
    CollectionAssignment, CollectionRequestAdminResponse, CollectionRequestCreate, CollectionRequestResponse,
    CollectionStatusUpdate,
)
from app.services.collection_service import (
    assign_collection_staff, create_collection_request, get_collection_request_by_id,
    get_collection_requests, history_for_user, update_collection_status,
)

router = APIRouter(prefix="/collection", tags=["Collection Management"])
compat_router = APIRouter(prefix="/collections", tags=["Collection Management"])

@router.post("/requests", response_model=CollectionRequestResponse, status_code=201)
@compat_router.post("/requests", response_model=CollectionRequestResponse, status_code=201)
def schedule_pickup(request_in: CollectionRequestCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    return create_collection_request(db, request_in, current_user)

@router.get("/requests", response_model=List[CollectionRequestResponse])
@compat_router.get("/requests", response_model=List[CollectionRequestResponse])
def list_pickups(status_filter: Optional[str] = Query(None, alias="status"),
                 skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        return get_collection_requests(db, status_filter=status_filter, skip=skip, limit=limit)
    if current_user.role == "collector":
        return get_collection_requests(db, status_filter=status_filter, staff_id=current_user.id, skip=skip, limit=limit)
    return get_collection_requests(db, user_id=current_user.id, status_filter=status_filter, skip=skip, limit=limit)

@router.get("/requests/{request_id}", response_model=CollectionRequestResponse)
@compat_router.get("/requests/{request_id}", response_model=CollectionRequestResponse)
def read_pickup(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    request = get_collection_request_by_id(db, request_id)
    is_owner = request.user_id == current_user.id
    is_staff = current_user.role == "admin" or (
        current_user.role == "collector" and request.assigned_staff_id == current_user.id
    )
    if not (is_owner or is_staff):
        raise HTTPException(status_code=404, detail="Collection request was not found.")
    return request

@router.patch("/requests/{request_id}/status", response_model=CollectionRequestResponse)
@compat_router.patch("/requests/{request_id}/status", response_model=CollectionRequestResponse)
def patch_pickup_status(request_id: int, status_in: CollectionStatusUpdate,
                        db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_collection_status(db, request_id, status_in, current_user)

@compat_router.patch("/requests/{request_id}/cancel", response_model=CollectionRequestResponse)
def cancel_pickup(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return update_collection_status(db, request_id, CollectionStatusUpdate(status="cancelled"), current_user)

@compat_router.patch("/requests/{request_id}/assign", response_model=CollectionRequestResponse)
def assign_pickup(request_id: int, payload: CollectionAssignment, db: Session = Depends(get_db),
                  admin: User = Depends(require_roles("admin"))):
    return assign_collection_staff(db, request_id, payload.assigned_staff_id, payload.internal_notes, admin)

@compat_router.get("/requests/{request_id}/staff-details", response_model=CollectionRequestAdminResponse)
def read_staff_pickup_details(request_id: int, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    request = get_collection_request_by_id(db, request_id)
    if not (current_user.role == "admin" or
            (current_user.role == "collector" and request.assigned_staff_id == current_user.id)):
        raise HTTPException(status_code=404, detail="Collection request was not found.")
    result = CollectionRequestResponse.model_validate(request).model_dump()
    result["internal_notes"] = request.internal_notes
    result["collection_records"] = [{"id": record.id, "collected_quantity": float(record.collected_quantity),
        "quantity_unit": record.quantity_unit, "collected_at": record.collected_at,
        "notes": record.notes, "collector_id": record.collector_id} for record in request.collection_records]
    return result

@compat_router.get("/history", response_model=List[CollectionRequestResponse])
def collection_history(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                       db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return history_for_user(db, current_user.id, skip, limit)
