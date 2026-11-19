"""
WasteWise AI – User Profile Endpoints
--------------------------------------
GET /api/users            -> List users (admin)
GET /api/users/profile    -> Retrieve authenticated profile
PUT /api/users/profile    -> Update personal profile fields
GET /api/users/{user_id}  -> Retrieve a user (self or admin)
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import UserProfileUpdate, UserResponse
from app.services.user_service import get_user_by_id, list_users, update_user_profile

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List all users",
    description="Returns registered users. Restricted to administrators.",
)
def list_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return list_users(db, skip=skip, limit=limit)


@router.get(
    "/profile",
    response_model=UserResponse,
    summary="Get user profile",
    description="Fetches current profile data for the authenticated account.",
)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update user profile",
    description="Updates contact information or address for the authenticated account.",
)
def update_profile(
    profile_in: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = update_user_profile(db, current_user, profile_in)
    return updated


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Administrators may retrieve any user. Citizens may retrieve only their own record.",
)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this user profile.",
        )
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )
    return user
