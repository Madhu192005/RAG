"""
WasteWise AI – Authentication Service
--------------------------------------
Encapsulates user registration, password verification, and JWT issuance.
"""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import Token, UserRegister
from app.services.audit_service import record_audit
from app.services.notification_service import create_notification
from app.services.seed_service import get_role_by_name, seed_reference_data


def register_user(db: Session, user_in: UserRegister) -> User:
    """
    Registers a new citizen user.
    Enforces unique email check and hashes the plain-text password.
    """
    seed_reference_data(db)
    email = user_in.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    citizen_role = get_role_by_name(db, "citizen")
    user = User(
        email=email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        phone=user_in.phone,
        role_id=citizen_role.id,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
        create_notification(
            db,
            user_id=user.id,
            title="Welcome to WasteWise AI",
            message="Your citizen account was created successfully.",
        )
        record_audit(db, action="user.register", entity_type="user", entity_id=user.id, user_id=user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )
    db.refresh(user)
    return (
        db.query(User)
        .options(joinedload(User.role_rel))
        .filter(User.id == user.id)
        .first()
    )


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Verifies user credentials.
    Returns user on success, raises HTTP 401 on bad credentials.
    """
    user = (
        db.query(User)
        .options(joinedload(User.role_rel))
        .filter(User.email == email.lower())
        .first()
    )
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def issue_token_for_user(user: User) -> Token:
    """
    Generates a JWT access token for the given user.
    """
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "role": user.role},
        expires_delta=expires_delta,
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
