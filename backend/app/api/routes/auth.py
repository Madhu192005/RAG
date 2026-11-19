"""
WasteWise AI – Authentication Endpoints
----------------------------------------
POST /api/auth/register -> Register a new citizen account
POST /api/auth/login    -> Authenticate and receive a JWT token
GET  /api/auth/me       -> Inspect currently authenticated user
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token
from app.schemas.user import UserResponse
from app.services.auth_service import register_user, authenticate_user, issue_token_for_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen user",
    description="Registers a new user account with hashed password storage.",
)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    user = register_user(db, user_in)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Log in and retrieve JWT access token",
    description="Authenticates with email and password, returning a signed Bearer token.",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    token = issue_token_for_user(user)
    return token


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user info",
    description="Returns the profile details of the user extracted from the Bearer token.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
