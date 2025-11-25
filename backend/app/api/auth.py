"""
Authentication API Endpoints
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    authenticate_user, create_access_token, create_user,
    get_current_user, require_admin
)
from app.core.config import settings
from app.models.database import User
from app.models.schemas import (
    LoginRequest, Token, UserCreate, UserResponse
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token, summary="Login")
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT token.

    - **username**: User's username
    - **password**: User's password
    """
    user = await authenticate_user(db, login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Register a new user (admin only).

    - **username**: Unique username (3-100 characters)
    - **email**: User's email address
    - **password**: Password (minimum 8 characters)
    - **role**: User role (admin, operator, viewer)
    """
    try:
        user = await create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role=user_data.role.value
        )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse, summary="Get current user")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information.
    """
    return current_user


@router.post("/logout", summary="Logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user.
    Note: JWT tokens are stateless, so actual invalidation should be handled client-side.
    In production, implement token blacklisting or short-lived tokens with refresh tokens.
    """
    return {"message": "Successfully logged out"}
