"""
Security and Authentication Module
JWT-based authentication with RBAC support
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.database import User, AuditLog
from app.models.schemas import TokenData

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security = HTTPBearer()


class AuthenticationError(Exception):
    """Custom authentication error"""
    pass


class AuthorizationError(Exception):
    """Custom authorization error"""
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "iss": settings.APP_NAME
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate JWT token
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        username: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role")

        if username is None:
            raise AuthenticationError("Invalid token: missing subject")

        return TokenData(username=username, role=role)

    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = None
) -> User:
    """
    Dependency to get current authenticated user
    Validates JWT token and retrieves user from database
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        token_data = decode_access_token(token)

        if token_data.username is None:
            raise credentials_exception

    except AuthenticationError:
        raise credentials_exception

    # Get user from database
    if db:
        result = await db.execute(
            select(User).where(User.username == token_data.username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise credentials_exception

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )

        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()

        return user

    # For testing without DB
    return User(
        id=1,
        username=token_data.username,
        email=f"{token_data.username}@example.com",
        role=token_data.role or "operator",
        hashed_password="",
        is_active=True
    )


class RBACChecker:
    """
    Role-Based Access Control checker
    Validates user permissions for actions
    """

    # Permission matrix
    PERMISSIONS = {
        "admin": {
            "deployments:create",
            "deployments:read",
            "deployments:update",
            "deployments:delete",
            "deployments:control",
            "users:create",
            "users:read",
            "users:update",
            "users:delete",
            "audit:read",
        },
        "operator": {
            "deployments:create",
            "deployments:read",
            "deployments:update",
            "deployments:control",
            "audit:read",
        },
        "viewer": {
            "deployments:read",
            "audit:read",
        }
    }

    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        """
        Check if user has required permission
        """
        user_permissions = self.PERMISSIONS.get(user.role, set())

        # Check custom permissions if defined
        if user.permissions:
            user_permissions.update(user.permissions)

        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.required_permission} required"
            )

        return user


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    role: str = "operator"
) -> User:
    """
    Create a new user with hashed password
    """
    # Check if user exists
    result = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise ValueError("User with this username or email already exists")

    # Create user
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_active=True,
        is_verified=False
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str
) -> Optional[User]:
    """
    Authenticate user with username and password
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user


async def log_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    user: User,
    success: bool = True,
    error_message: Optional[str] = None,
    request_data: Optional[Dict] = None,
    response_data: Optional[Dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """
    Log audit event for compliance and security monitoring
    """
    audit_log = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user.id,
        username=user.username,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        error_message=error_message,
        request_data=request_data,
        response_data=response_data
    )

    db.add(audit_log)
    await db.commit()


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def require_operator_or_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require operator or admin role"""
    if user.role not in ["admin", "operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin access required"
        )
    return user
