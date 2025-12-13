from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta

from app.config import get_settings
from app.services.vector_store import VectorStoreService

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# JWT Bearer authentication
bearer_scheme = HTTPBearer(auto_error=False)


def get_vector_store(request: Request) -> VectorStoreService:
    """Get vector store from app state."""
    return request.app.state.vector_store


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key authentication."""
    settings = get_settings()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return api_key


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:
    """Verify JWT token authentication."""
    settings = get_settings()

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=["HS256"],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired token",
        )


async def verify_api_key_or_token(
    api_key: str = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:
    """Verify either API key or JWT token authentication."""
    settings = get_settings()

    # If auth is disabled, allow all requests (for testing/private environments)
    if settings.auth_disabled:
        return {"auth_type": "none", "auth_disabled": True}

    # Try API key first
    if api_key:
        if api_key == settings.api_key:
            return {"auth_type": "api_key"}
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Try JWT token
    if credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.secret_key,
                algorithms=["HS256"],
            )
            payload["auth_type"] = "jwt"
            return payload
        except JWTError:
            raise HTTPException(status_code=403, detail="Invalid or expired token")

    raise HTTPException(
        status_code=401,
        detail="Authentication required (API key or Bearer token)",
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
