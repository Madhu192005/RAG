"""
WasteWise AI – User Profile Service
"""

from typing import List

from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.schemas.user import UserProfileUpdate
from app.services.audit_service import record_audit


def get_user_by_id(db: Session, user_id: int) -> User:
    return (
        db.query(User)
        .options(joinedload(User.role_rel))
        .filter(User.id == user_id)
        .first()
    )


def list_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return (
        db.query(User)
        .options(joinedload(User.role_rel))
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_user_profile(db: Session, user: User, profile_in: UserProfileUpdate) -> User:
    """
    Updates the authenticated user's profile details.
    """
    if profile_in.full_name is not None:
        user.full_name = profile_in.full_name
    if profile_in.phone is not None:
        user.phone = profile_in.phone
    if profile_in.address is not None:
        user.address = profile_in.address

    record_audit(db, action="user.update_profile", entity_type="user", entity_id=user.id, user_id=user.id)
    db.commit()
    db.refresh(user)
    return get_user_by_id(db, user.id)
