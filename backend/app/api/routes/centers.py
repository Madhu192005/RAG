"""Verified recycling center directory and smart recommendation endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user, require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.center import RecyclingCenterCreate, RecyclingCenterResponse, RecyclingCenterUpdate
from app.services.center_service import (
    MAX_SEARCH_RADIUS_KM, create_center, deactivate_center, find_nearby_centers,
    get_center_by_id, get_centers, recommend_for_classification, update_center,
)

router = APIRouter(prefix="/centers", tags=["Recycling Centers"])
compat_router = APIRouter(prefix="/recycling-centers", tags=["Recycling Centers"])

@router.get("", response_model=List[RecyclingCenterResponse], summary="List verified recycling centers")
@compat_router.get("", response_model=List[RecyclingCenterResponse], include_in_schema=True)
def list_centers(location: Optional[str] = Query(None, max_length=200),
                 postal_code: Optional[str] = Query(None, max_length=20),
                 category: Optional[str] = Query(None, max_length=100),
                 waste_type: Optional[str] = Query(None, max_length=100),
                 center_type: Optional[str] = Query(None, max_length=100),
                 verification_status: Optional[str] = Query(None),
                 include_unverified: bool = False, include_inactive: bool = False,
                 skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                 db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_optional_current_user)):
    admin = current_user is not None and current_user.role == "admin"
    if (verification_status or include_unverified or include_inactive) and not admin:
        raise HTTPException(status_code=403, detail="Only administrators can inspect unverified or inactive centers.")
    return get_centers(db, location=location, postal_code=postal_code, category=category,
                       waste_type=waste_type, center_type=center_type,
                       verification_status=verification_status, skip=skip, limit=limit,
                       active_only=not include_inactive, include_unverified=include_unverified)

@router.get("/nearby", summary="Find nearby centers that explicitly accept a waste type")
@compat_router.get("/nearby")
def nearby_centers(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180),
                   radius_km: float = Query(10, gt=0, le=MAX_SEARCH_RADIUS_KM),
                   waste_type: str = Query(..., min_length=2, max_length=100),
                   center_type: Optional[str] = Query(None, max_length=100), db: Session = Depends(get_db)):
    return find_nearby_centers(db, latitude=latitude, longitude=longitude, radius_km=radius_km,
                               waste_type=waste_type, center_type=center_type)

@router.get("/recommendations/{classification_id}", summary="Recommend centers for a confirmed classification")
@compat_router.get("/recommendations/{classification_id}")
def classification_recommendations(classification_id: int, db: Session = Depends(get_db),
                                   current_user: User = Depends(get_current_user),
                                   latitude: Optional[float] = Query(None, ge=-90, le=90),
                                   longitude: Optional[float] = Query(None, ge=-180, le=180),
                                   radius_km: Optional[float] = Query(None, gt=0, le=MAX_SEARCH_RADIUS_KM),
                                   location: Optional[str] = Query(None, max_length=200)):
    return recommend_for_classification(db, classification_id, current_user, latitude=latitude,
        longitude=longitude, radius_km=radius_km, location=location)

@router.post("", response_model=RecyclingCenterResponse, status_code=status.HTTP_201_CREATED)
@compat_router.post("", response_model=RecyclingCenterResponse, status_code=status.HTTP_201_CREATED)
def add_center(center_in: RecyclingCenterCreate, db: Session = Depends(get_db),
               admin: User = Depends(require_roles("admin"))):
    return create_center(db=db, center_in=center_in, admin_user_id=admin.id)

@router.put("/{center_id}", response_model=RecyclingCenterResponse)
@compat_router.put("/{center_id}", response_model=RecyclingCenterResponse)
def edit_center(center_id: int, payload: RecyclingCenterUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_roles("admin"))):
    return update_center(db, center_id, payload, admin.id)

@router.delete("/{center_id}", response_model=RecyclingCenterResponse)
@compat_router.delete("/{center_id}", response_model=RecyclingCenterResponse)
def remove_center(center_id: int, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return deactivate_center(db, center_id, admin.id)

@router.get("/{center_id}", response_model=RecyclingCenterResponse)
@compat_router.get("/{center_id}", response_model=RecyclingCenterResponse)
def read_center(center_id: int, db: Session = Depends(get_db),
                current_user: Optional[User] = Depends(get_optional_current_user)):
    return get_center_by_id(db, center_id, include_unverified=current_user is not None and current_user.role == "admin")
